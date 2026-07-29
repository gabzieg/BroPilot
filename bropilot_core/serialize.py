"""Serialização do estado da party para consumo por LLM e por retrieval.

Este é o *contrato de dados* entre o SaveParser e o resto do sistema — a Fase 0
de toda a integração. O `SaveContext` é um objeto Python vivo (cheio de
dataclasses); o LLM precisa de texto, e o retriever precisa de sinais estruturados
(classes, nível) para dirigir a busca. Este módulo é a fronteira que traduz um
no outro.

Princípio de design: a "ficha da party" define O QUE o mod precisa exportar, não
o contrário. Se um campo do BuildStats não entra em nenhuma das funções abaixo,
ele é peso morto no exporter. Se uma dessas funções pede algo que o mod não dá,
essa é a lista real do que falta validar no scraper do save.

Dependência: importa `bropilot` (o pacote do SaveParser em
BroPilot-SaveParser/src/). Ver README do bropilot_core para o ajuste de sys.path
enquanto não há packaging unificado.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    # Import só-para-tipos: não força o sys.path do parser em quem só usa os tipos.
    from bropilot import SaveContext, CharacterSummary


class PartyStateSignals(TypedDict, total=False):
    """Sinais estruturados extraídos da party para DIRIGIR o retrieval.

    Não é texto para o prompt — são chaves de filtro/boost. Ex.: `classes`
    permite priorizar `build_monk_openhand.md` quando há um Monge na party.
    Todos opcionais porque sem o mod Lua o save só entrega nível/raça/classe.
    """
    levels: list[int]
    races: list[str]
    classes: list[str]          # ex.: ["Monk", "Wizard"] achatado da party
    subclasses: list[str]       # ex.: ["OpenHand", "Evocation"]
    active_statuses: list[str]  # concentração/condições — relevante p/ "melhor jogada AGORA"
    has_live_stats: bool        # False quando o mod não rodou (fidelidade degradada)


def _party_members(ctx: "SaveContext") -> list["CharacterSummary"]:
    """Só os personagens jogáveis da "Active Party".

    O SaveInfo.json mistura invocações na mesma lista: um Elemental conjurado,
    um Dryad de Conjure Woodland Beings e um Wood Woad aparecem como
    "personagens". Verificado em saves reais: o que os distingue é `Classes`
    vir nulo — membro de verdade sempre tem classe, mesmo no nível 1 (onde a
    subclasse ainda é vazia). Sem esse filtro a ficha gastaria tokens com
    invocação e os signals do retrieval viriam poluídos.
    """
    return [c for c in ctx.party.characters if c.classes]


def _classes_de(char: "CharacterSummary") -> list[tuple[str, str]]:
    """Pares (classe, subclasse) do personagem. Subclasse vazia até o nível 3."""
    pares = []
    for entrada in char.classes or []:
        principal = (entrada.get("Main") or "").strip()
        if principal:
            pares.append((principal, (entrada.get("Sub") or "").strip()))
    return pares


def _tem_stats_ao_vivo(membros: list["CharacterSummary"]) -> bool:
    """Se o snapshot do mod alimentou ESTES personagens.

    Derivado dos personagens, e não da existência do arquivo do mod, porque um
    dump que não casou com ninguém deixa a ficha igualmente sem stats — e
    prometer fidelidade que não se tem é o erro que este módulo evita.
    """
    return any(c.stats is not None for c in membros)


def serialize_party(ctx: "SaveContext", *, verbose: bool = False) -> str:
    """Converte o estado da party numa ficha de texto enxuta para o prompt.

    O texto é curto de propósito: entra em TODO prompt, então cada token custa.
    `verbose=True` inclui inventário/passivas completas (para debug ou quando o
    modelo tem contexto sobrando); o default é a versão mínima acionável.

    Degrada com honestidade: sem snapshot do mod, emite só o que o save em
    disco tem e declara explicitamente o que NÃO sabe, em vez de omitir em
    silêncio — o modelo precisa saber que não pode falar de equipamento.
    """
    membros = _party_members(ctx)
    if not membros:
        return "## Party\n(nenhum personagem encontrado no save)"

    ao_vivo = _tem_stats_ao_vivo(membros)
    linhas = [
        f"## Party ({len(membros)} personagens · stats ao vivo: "
        f"{'sim' if ao_vivo else 'não'})"
    ]
    linhas += [serialize_character(c, verbose=verbose) for c in membros]

    if not ao_vivo:
        # Sem esta linha o modelo preenche a lacuna sozinho: perguntado sobre
        # equipamento, inventa um. Declarar o limite é mais barato que corrigir
        # alucinação depois.
        linhas.append(
            "> Sem snapshot do mod: NÃO há dados de equipamento, inventário, "
            "HP/CA, spell slots ou passivas. Não afirme nada sobre esses itens."
        )
    return "\n".join(linhas)


def serialize_character(char: "CharacterSummary", *, verbose: bool = False) -> str:
    """Serializa um único personagem. Bloco de construção de serialize_party.

    Separado para permitir fichas individuais (ex.: "analise só a Shadowheart")
    sem reconstruir a party inteira.
    """
    nome = char.display_name or char.name
    # Raça vai crua ("Elf_WoodElf"): embelezar custaria tokens e inventaria uma
    # tradução que o modelo já entende sem ajuda.
    partes = [f"- {nome} — Lvl {char.level}"]
    if char.race:
        partes.append(char.race)

    classes = "/".join(
        f"{principal}:{sub}" if sub else principal
        for principal, sub in _classes_de(char)
    )
    if classes:
        partes.append(f"[{classes}]")

    linha = " ".join(partes)

    stats = char.stats
    if stats is None:
        return linha

    # Daqui para baixo só existe com o mod rodando (Windows).
    vitais = []
    if stats.vitals.max_hp is not None:
        vitais.append(f"HP {stats.vitals.hp}/{stats.vitals.max_hp}")
    if stats.vitals.armor_class is not None:
        vitais.append(f"CA {stats.vitals.armor_class}")
    if vitais:
        linha += " · " + " ".join(vitais)

    if stats.abilities:
        linha += " · " + " ".join(
            f"{nome_hab[:3].upper()} {valor}"
            for nome_hab, valor in stats.abilities.items()
        )
    if stats.statuses:
        linha += " · status: " + ", ".join(stats.statuses)

    if verbose:
        if stats.passives:
            linha += f"\n    passivas: {', '.join(stats.passives)}"
        if char.equipment:
            equipado = ", ".join(
                f"{slot}={item.stats_id or item.template_id or '?'}"
                for slot, item in char.equipment.items()
            )
            linha += f"\n    equipamento: {equipado}"
    return linha


def extract_signals(ctx: "SaveContext") -> PartyStateSignals:
    """Extrai os sinais estruturados que dirigem o retrieval state-aware.

    Separado de serialize_party porque tem propósito diferente: serialize gera
    TEXTO para o modelo ler; isto gera CHAVES para a busca filtrar/priorizar.
    O orquestrador usa os dois: signals para buscar, texto para o prompt.
    """
    membros = _party_members(ctx)

    niveis: list[int] = []
    racas: list[str] = []
    classes: list[str] = []
    subclasses: list[str] = []
    statuses: list[str] = []

    for char in membros:
        niveis.append(char.level)
        if char.race:
            racas.append(char.race)
        for principal, sub in _classes_de(char):
            classes.append(principal)
            if sub:
                subclasses.append(sub)
        if char.stats is not None:
            statuses.extend(char.stats.statuses)

    # dict.fromkeys deduplica preservando a ordem da party — o boost do
    # retriever casa por substring, então repetir "Fighter" três vezes não
    # ajudaria em nada.
    signals: PartyStateSignals = {
        "levels": niveis,
        "races": list(dict.fromkeys(racas)),
        "classes": list(dict.fromkeys(classes)),
        "subclasses": list(dict.fromkeys(subclasses)),
        "has_live_stats": _tem_stats_ao_vivo(membros),
    }
    if statuses:
        signals["active_statuses"] = list(dict.fromkeys(statuses))
    return signals
