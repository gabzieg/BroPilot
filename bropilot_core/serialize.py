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


def serialize_party(ctx: "SaveContext", *, verbose: bool = False) -> str:
    """Converte o estado da party numa ficha de texto enxuta para o prompt.

    O texto é curto de propósito: entra em TODO prompt, então cada token custa.
    `verbose=True` inclui inventário/passivas completas (para debug ou quando o
    modelo tem contexto sobrando); o default é a versão mínima acionável.

    Deve degradar graciosamente: sem snapshot do mod, emite só o que o save em
    disco tem (nível, raça, classe, posição) e sinaliza a limitação, em vez de
    mentir com campos vazios.

    Retorna: markdown curto, ex.:
        ## Party (4 personagens · stats ao vivo: sim)
        - Laezel — Lvl 5 Githyanki [Fighter:BattleMaster] · HP 44/44 CA 18 ...
        - ...
    """
    raise NotImplementedError("scaffold")


def serialize_character(char: "CharacterSummary", *, verbose: bool = False) -> str:
    """Serializa um único personagem. Bloco de construção de serialize_party.

    Separado para permitir fichas individuais (ex.: "analise só a Shadowheart")
    sem reconstruir a party inteira.
    """
    raise NotImplementedError("scaffold")


def extract_signals(ctx: "SaveContext") -> PartyStateSignals:
    """Extrai os sinais estruturados que dirigem o retrieval state-aware.

    Separado de serialize_party porque tem propósito diferente: serialize gera
    TEXTO para o modelo ler; isto gera CHAVES para a busca filtrar/priorizar.
    O orquestrador usa os dois: signals para buscar, texto para o prompt.
    """
    raise NotImplementedError("scaffold")
