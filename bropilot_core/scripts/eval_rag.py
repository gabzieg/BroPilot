"""Avaliação de QUALIDADE do RAG — roda uma bateria de perguntas contra a stack
real (Ollama + índice LanceDB) e gera um relatório em Markdown para leitura
humana.

Não é teste automatizado: não afirma se uma resposta é boa. Coleta evidência —
chunks recuperados com score, resposta completa, fontes citadas, latência — e
faz só verificações MECÂNICAS (as fontes batem com os chunks? as paráfrases
recuperaram o mesmo material? a resposta fora de escopo admitiu não saber?). O
julgamento de qualidade é de quem lê.

Uso:
    python -m bropilot_core.scripts.eval_rag [--output CAMINHO] [-k N]

Chama o Ollama de verdade — é lento de propósito, o custo de latência é um dos
dados coletados.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import lancedb

from ..index.build import STORE_DIR, TRUSTED_DIR, classify_source
from ..index.retriever import _DEFAULT_VECTOR_WEIGHT, RetrievedChunk, Retriever
from ..llm import create_provider
from ..orchestrator import Orchestrator
from ..serialize import extract_signals

# id, categoria e grupo. `grupo` liga perguntas que devem ser comparadas entre
# si nas checagens mecânicas do fim do relatório.
PERGUNTAS = [
    # (a) build/otimização — o caso de uso central
    {"id": "a1", "categoria": "build/otimização", "grupo": "monge_pt",
     "texto": "qual a melhor subclasse de Monge para dano desarmado?"},
    {"id": "a2", "categoria": "build/otimização", "grupo": None,
     "texto": "como montar um Ladrão focado em dano por turno?"},

    # (b) action economy — o diferencial declarado
    {"id": "b1", "categoria": "action economy", "grupo": None,
     "texto": "como funciona a economia de ação usando Dual Wielder?"},
    {"id": "b2", "categoria": "action economy", "grupo": None,
     "texto": "vale a pena usar Ação Bônus para desengajar ou atacar?"},

    # (c) regra factual verificável
    {"id": "c1", "categoria": "regra factual", "grupo": None,
     "texto": "quantos dados de Superioridade de Combate um Battle Master tem "
              "no nível 5?"},

    # (d) paráfrases da mesma intenção — robustez do retrieval
    {"id": "d1", "categoria": "paráfrase", "grupo": "parafrase_monge",
     "texto": "melhor build de monge"},
    {"id": "d2", "categoria": "paráfrase", "grupo": "parafrase_monge",
     "texto": "como otimizar um Monge Open Hand no BG3?"},
    {"id": "d3", "categoria": "paráfrase", "grupo": "parafrase_monge",
     "texto": "open hand monk build guide"},

    # (e) cross-lingual — mesma intenção de a1, em inglês
    {"id": "e1", "categoria": "cross-lingual", "grupo": "monge_en",
     "texto": "which is the best Monk subclass for unarmed damage?"},

    # (f) fora de escopo — deve admitir que não sabe
    {"id": "f1", "categoria": "fora de escopo", "grupo": "fora_escopo",
     "texto": "qual a melhor build de Elden Ring?"},
    {"id": "f2", "categoria": "fora de escopo", "grupo": "fora_escopo",
     "texto": "quem ganhou a Copa do Mundo de 2022?"},

    # (g) ambígua — deve pedir contexto em vez de chutar
    {"id": "g1", "categoria": "ambígua", "grupo": None,
     "texto": "qual a melhor classe?"},
]

# Mesmas 12 perguntas, mesmos id/categoria/grupo — só `texto` traduzido para
# inglês natural com os termos do jogo nativos. Existe para medir se o
# IDIOMA DA QUERY (não do corpus, que já é ~97% inglês) muda acurácia e
# estabilidade do retrieval. Ver `bropilot_core/scripts/compare_language.py`
# para a bateria de controle de idioma e o relatório comparativo — este
# módulo só expõe a lista para reuso, não a bateria completa em EN.
PERGUNTAS_EN = [
    {"id": "a1", "categoria": "build/otimização", "grupo": "monge_pt",
     "texto": "which Monk subclass is best for unarmed damage?"},
    {"id": "a2", "categoria": "build/otimização", "grupo": None,
     "texto": "how do I build a Rogue focused on damage per turn?"},

    {"id": "b1", "categoria": "action economy", "grupo": None,
     "texto": "how does action economy work with Dual Wielder?"},
    {"id": "b2", "categoria": "action economy", "grupo": None,
     "texto": "is it worth spending a Bonus Action to disengage or attack?"},

    {"id": "c1", "categoria": "regra factual", "grupo": None,
     "texto": "how many Superiority Dice does a Battle Master have at level 5?"},

    {"id": "d1", "categoria": "paráfrase", "grupo": "parafrase_monge",
     "texto": "best monk build"},
    {"id": "d2", "categoria": "paráfrase", "grupo": "parafrase_monge",
     "texto": "how do I optimize an Open Hand Monk in BG3?"},
    {"id": "d3", "categoria": "paráfrase", "grupo": "parafrase_monge",
     "texto": "open hand monk build guide"},

    {"id": "e1", "categoria": "cross-lingual", "grupo": "monge_en",
     "texto": "which is the best Monk subclass for unarmed damage?"},

    {"id": "f1", "categoria": "fora de escopo", "grupo": "fora_escopo",
     "texto": "what's the best Elden Ring build?"},
    {"id": "f2", "categoria": "fora de escopo", "grupo": "fora_escopo",
     "texto": "who won the 2022 World Cup?"},

    {"id": "g1", "categoria": "ambígua", "grupo": None,
     "texto": "what's the best class?"},
]

# As 10 perguntas do relatório de acurácia para o README (`--showcase`).
# Ordem fixa e proposital — cada uma testa uma dimensão diferente do sistema
# (regra factual, build, subclasse nova, action economy, multiclasse,
# ambiguidade usando o save, caster, buraco conhecido da base, limite
# sem-mod, fora de escopo). Ao contrário de PERGUNTAS/PERGUNTAS_EN, esta
# lista não tem `grupo` — o showcase não faz as checagens mecânicas
# cruzadas (paráfrase/cross-lingual), só coleta pergunta→resposta.
PERGUNTAS_SHOWCASE = [
    {"id": "s1", "categoria": "regra factual verificável",
     "texto": "how many Superiority Dice does a Battle Master have at level 5?"},
    {"id": "s2", "categoria": "build / subclasse",
     "texto": "best feats for an Open Hand Monk"},
    {"id": "s3", "categoria": "build / usa subclasse nova",
     "texto": "best race for a Battle Master Fighter"},
    {"id": "s4", "categoria": "action economy",
     "texto": "how does bonus action economy work with Dual Wielder?"},
    {"id": "s5", "categoria": "multiclasse",
     "texto": "is a Monk 9 / Rogue 3 multiclass worth it for damage?"},
    {"id": "s6", "categoria": "ambígua — usa o estado do save",
     "texto": "what's the best level-up choice for my current party?"},
    {"id": "s7", "categoria": "caster — Shadowheart é Light Domain no save",
     "texto": "best build for a Light Domain Cleric"},
    {"id": "s8", "categoria": "expõe buraco de magia de propósito",
     "texto": "which spells should a Circle of the Land Druid prioritize?"},
    {"id": "s9", "categoria": "item — expõe o limite sem-mod no Mac",
     "texto": "should I equip Gloves of Soul Catching on my Monk?"},
    {"id": "s10", "categoria": "fora de escopo — deve recusar",
     "texto": "what's the best build in Elden Ring?"},
]

# Marcadores de "não sei / não está na base". Heurística de SUBSTRING, reportada
# como sinal mecânico, não como veredito: serve para o leitor achar rápido as
# respostas que admitiram ignorância, não para decidir se a resposta prestou.
_MARCADORES_NAO_SEI = [
    "não sei", "nao sei", "não tenho informa", "nao tenho informa",
    "não há informa", "nao ha informa", "não encontrei", "nao encontrei",
    "não está no contexto", "nao esta no contexto", "não consta",
    "fora do escopo", "não posso responder", "nao posso responder",
    "não foi possível encontrar", "não é sobre",
    # Recusa por tema: precisa ser a FRASE, não a palavra "baldur" sozinha —
    # num assistente de BG3 quase toda resposta cita o jogo, então a palavra
    # solta daria falso positivo justamente nas perguntas fora de escopo.
    "só falo de baldur", "so falo de baldur", "apenas sobre baldur",
    "só respondo sobre baldur", "so respondo sobre baldur",
    "especializado em baldur", "sou um copiloto de baldur",
]

_TRECHO_CHARS = 200


class _RecordingRetriever:
    """Espia o que o Orchestrator realmente recuperou.

    Envolve o Retriever real em vez de repetir a busca por fora: repetir
    embedaria a query duas vezes e, pior, o relatório passaria a mostrar uma
    busca diferente da que alimentou o prompt.
    """

    def __init__(self, inner: Retriever) -> None:
        self._inner = inner
        self.ultima_busca: list[RetrievedChunk] = []

    def search(self, query, *, signals=None, k=6):
        hits = self._inner.search(query, signals=signals, k=k)
        self.ultima_busca = list(hits)
        return hits


def _fmt_trecho(texto: str, limite: int = _TRECHO_CHARS) -> str:
    limpo = " ".join(texto.split())
    return limpo[:limite] + ("…" if len(limpo) > limite else "")


def _jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b) if (a | b) else 0.0


def _metadados_indice(store_dir: Path, trusted_dir: Path = TRUSTED_DIR) -> dict:
    """Metadados do índice + detecção de índice DESATUALIZADO.

    Avaliar respostas contra um índice que não cobre a base inteira produz
    conclusões erradas sem dar nenhum sinal — o relatório pareceria normal. Daí
    comparar o que o manifest registra com os .md que existem de fato em
    trusted_dir, e gritar quando divergirem.
    """
    manifest_path = store_dir / "manifest.json"
    if not manifest_path.exists():
        raise RuntimeError(
            f"Índice sem manifest em {store_dir}. Construa a base antes:\n"
            "  python -m bropilot_core.index.build"
        )
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Manifest do índice ilegível ({manifest_path}): {exc}. "
            "Reconstrua com:\n  python -m bropilot_core.index.build --rebuild"
        ) from exc

    tabela = lancedb.connect(str(store_dir)).open_table("chunks")
    indexados = len(manifest.get("files", {}))

    # O esperado é o que o FILTRO do índice seleciona, não todo o 02_trusted:
    # um índice de experimento (--only-types wiki,build) cobre 27 de 151
    # arquivos por decisão, e gritar "desatualizado" nele treinaria o leitor a
    # ignorar o alerta justo quando ele for verdadeiro.
    tipos = manifest.get("source_types")
    if trusted_dir.exists():
        no_disco = sum(
            1 for p in trusted_dir.glob("*.md")
            if tipos is None or classify_source(p.name) in set(tipos)
        )
    else:
        no_disco = 0

    aviso = None
    if no_disco and indexados != no_disco:
        escopo = f" (source_types={tipos})" if tipos else ""
        aviso = (
            f"índice cobre {indexados} de {no_disco} arquivos elegíveis em "
            f"{trusted_dir}{escopo} — rode `python -m bropilot_core.index.build` "
            "antes de tirar conclusões"
        )

    return {
        "chunks": tabela.count_rows(),
        "arquivos": indexados,
        "arquivos_no_disco": no_disco,
        "source_types": tipos,
        "embed_model": manifest.get("embed_model"),
        "embed_dim": manifest.get("embed_dim"),
        "aviso": aviso,
    }


def executar(
    orchestrator: Orchestrator,
    spy: _RecordingRetriever,
    ctx=None,
    *,
    sem_geracao: bool = False,
    perguntas: list[dict] | None = None,
) -> list[dict]:
    """Roda a bateria. Uma pergunta que falhar vira registro de erro e a
    bateria continua — perder as 11 seguintes por causa de uma seria pior.

    `sem_geracao=True` faz só a busca. A geração local responde por ~95% do
    tempo da bateria e não influencia nenhuma métrica de retrieval, então
    medir retrieval com ela ligada é pagar horas por nada.

    `perguntas` default PERGUNTAS (PT) — passar PERGUNTAS_EN, a bateria de
    controle de idioma, ou qualquer lista no mesmo formato reusa esta função
    sem duplicar o laço.
    """
    if perguntas is None:
        perguntas = PERGUNTAS
    resultados = []
    total = len(perguntas)

    for i, pergunta in enumerate(perguntas, start=1):
        print(f"[{i}/{total}] ({pergunta['categoria']}) {pergunta['texto']}",
              flush=True)
        spy.ultima_busca = []
        registro = dict(pergunta)
        registro["sem_geracao"] = sem_geracao

        inicio = time.perf_counter()
        try:
            if sem_geracao:
                # Mesmo caminho de busca do ask(): signals do ctx quando existe,
                # senão None. Replicar aqui manteria as duas versões da bateria
                # medindo coisas diferentes.
                signals = extract_signals(ctx) if ctx is not None else None
                spy.search(pergunta["texto"], signals=signals, k=orchestrator.k)
                registro["erro"] = None
                registro["resposta"] = None
                registro["fontes"] = []
            else:
                resposta = orchestrator.ask(pergunta["texto"], ctx)
                registro["erro"] = None
                registro["resposta"] = resposta.text
                registro["fontes"] = resposta.sources
        except Exception as exc:  # noqa: BLE001 — a bateria não pode morrer aqui
            registro["erro"] = f"{type(exc).__name__}: {exc}"
            registro["resposta"] = None
            registro["fontes"] = []
            print(f"      !! falhou: {registro['erro']}")

        registro["segundos"] = time.perf_counter() - inicio
        registro["chunks"] = [
            {
                "source_file": c.source_file,
                "source_type": c.source_type,
                "score": c.score,
                "base_score": c.base_score,
                "vector_score": c.vector_score,
                "fts_score": c.fts_score,
                "boost_reasons": list(c.boost_reasons),
                "trecho": _fmt_trecho(c.text),
            }
            for c in spy.ultima_busca
        ]
        print(f"      {registro['segundos']:.1f}s, "
              f"{len(registro['chunks'])} chunks, "
              f"{len(registro['fontes'])} fontes", flush=True)
        resultados.append(registro)

    return resultados


def _checagens_mecanicas(resultados: list[dict]) -> list[str]:
    """Só fatos verificáveis por código. Nada de julgar qualidade."""
    linhas = []
    por_id = {r["id"]: r for r in resultados}

    sem_geracao = all(r.get("sem_geracao") for r in resultados)

    # 1. fontes citadas ⊆ arquivos dos chunks que alimentaram o prompt
    linhas.append("### Fontes citadas batem com os chunks recuperados?\n")
    if sem_geracao:
        linhas.append("**N/A** — bateria rodada com `--sem-geracao`: não houve "
                      "resposta, logo não há fontes citadas para conferir.")
    else:
        linhas.append("| pergunta | fontes citadas | fontes fora dos chunks |")
        linhas.append("|---|---|---|")
        for r in resultados:
            arquivos = {c["source_file"] for c in r["chunks"]}
            extras = set(r["fontes"]) - arquivos
            linhas.append(
                f"| `{r['id']}` | {len(r['fontes'])} | "
                f"{'**' + ', '.join(sorted(extras)) + '**' if extras else 'nenhuma'} |"
            )

    # 2. paráfrases: os três conjuntos de arquivos deveriam se parecer
    grupo = [r for r in resultados if r["grupo"] == "parafrase_monge"]
    if len(grupo) > 1:
        linhas.append("\n### Paráfrases recuperaram o mesmo material?\n")
        linhas.append("Jaccard entre os conjuntos de `source_file` "
                      "(1.00 = idênticos, 0.00 = disjuntos).\n")
        linhas.append("| par | jaccard | em comum |")
        linhas.append("|---|---|---|")
        for i in range(len(grupo)):
            for j in range(i + 1, len(grupo)):
                a = {c["source_file"] for c in grupo[i]["chunks"]}
                b = {c["source_file"] for c in grupo[j]["chunks"]}
                comum = ", ".join(sorted(a & b)) or "—"
                linhas.append(
                    f"| `{grupo[i]['id']}` × `{grupo[j]['id']}` | "
                    f"{_jaccard(a, b):.2f} | {comum} |"
                )

    # 3. cross-lingual: PT vs EN da mesma intenção
    pt, en = por_id.get("a1"), por_id.get("e1")
    if pt and en:
        a = {c["source_file"] for c in pt["chunks"]}
        b = {c["source_file"] for c in en["chunks"]}
        linhas.append("\n### Cross-lingual: PT vs EN da mesma pergunta\n")
        linhas.append(f"- `a1` (PT): {', '.join(sorted(a)) or '—'}")
        linhas.append(f"- `e1` (EN): {', '.join(sorted(b)) or '—'}")
        linhas.append(f"- **Jaccard: {_jaccard(a, b):.2f}** "
                      f"| em comum: {', '.join(sorted(a & b)) or 'nenhum'}")

    # 4. fora de escopo: a resposta contém algum marcador de "não sei"?
    fora = [r for r in resultados if r["grupo"] == "fora_escopo"]
    if fora and sem_geracao:
        linhas.append("\n### Fora de escopo: a resposta admitiu não saber?\n")
        linhas.append("**N/A** — sem geração, não há resposta para inspecionar.")
        fora = []
    if fora:
        linhas.append("\n### Fora de escopo: a resposta admitiu não saber?\n")
        linhas.append("Detecção por substring — sinal para achar o trecho, "
                      "não veredito. Confira o texto completo acima.\n")
        linhas.append("| pergunta | marcador encontrado |")
        linhas.append("|---|---|")
        for r in fora:
            texto = (r["resposta"] or "").lower()
            achados = [m for m in _MARCADORES_NAO_SEI if m in texto]
            linhas.append(
                f"| `{r['id']}` | {', '.join(f'`{a}`' for a in achados) or '**nenhum**'} |"
            )

    # 5. latência
    ok = [r for r in resultados if r["erro"] is None]
    if ok:
        tempos = sorted(r["segundos"] for r in ok)
        rotulo = " (só busca, sem geração)" if sem_geracao else ""
        linhas.append(f"\n### Latência{rotulo}\n")
        linhas.append(f"- respostas: {len(ok)}/{len(resultados)}")
        linhas.append(f"- min: {tempos[0]:.1f}s | mediana: "
                      f"{tempos[len(tempos)//2]:.1f}s | max: {tempos[-1]:.1f}s")
        linhas.append(f"- total da bateria: {sum(tempos):.0f}s")

    return linhas


def gerar_relatorio(resultados: list[dict], meta: dict, k: int) -> str:
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    peso = meta.get("vector_weight", _DEFAULT_VECTOR_WEIGHT)
    out = ["# Relatório de avaliação do RAG — BroPilot", ""]

    # Antes de qualquer número: se o índice não cobre a base, o leitor precisa
    # saber ANTES de ler as respostas.
    if meta.get("aviso"):
        out += [
            f"> ## ⚠️ ÍNDICE DESATUALIZADO",
            f"> **{meta['aviso']}**",
            ">",
            "> Os resultados abaixo foram gerados contra um índice incompleto.",
            "",
        ]

    modo = ("**Modo `--sem-geracao`**: só retrieval; nenhuma resposta foi "
            "gerada." if meta.get("sem_geracao") else "")
    out += [
        f"Gerado em {agora}.",
        "",
        *([modo, ""] if modo else []),
        "> Este relatório **coleta evidência**, não julga qualidade. As únicas "
        "marcações automáticas são mecânicas (fontes × chunks, sobreposição "
        "entre paráfrases, presença de marcadores de recusa, latência).",
        "",
        "## Setup",
        "",
        f"- Índice: **{meta['chunks']} chunks** de {meta['arquivos']} arquivos "
        f"({meta['arquivos_no_disco']} elegíveis em `{TRUSTED_DIR}`)",
        f"- Filtro de corpus: {meta['source_types'] or 'nenhum (todos os tipos)'}",
        f"- Embeddings: `{meta['embed_model']}` (dim {meta['embed_dim']})",
        f"- Busca híbrida: peso vetorial **{peso:.2f}** / FTS {1 - peso:.2f}",
        f"- k (chunks por pergunta): **{k}**",
        f"- Idioma da bateria: **{meta.get('lang', 'pt')}**",
        f"- `signals`: {meta['signals']}",
        "",
        "---",
        "",
        "## Perguntas",
        "",
    ]

    for r in resultados:
        out.append(f"### `{r['id']}` — {r['categoria']}")
        out.append("")
        out.append(f"**Pergunta:** {r['texto']}")
        out.append("")
        out.append(f"*Latência: {r['segundos']:.1f}s*")
        out.append("")

        if r["erro"]:
            out.append(f"> **FALHOU:** `{r['erro']}`")
            out.append("")
            out.append("---")
            out.append("")
            continue

        out.append("**Chunks recuperados:**")
        out.append("")
        if r["chunks"]:
            # base_score e score separados: hoje são iguais (signals=None), mas
            # quando o boost state-aware ligar é a diferença entre as duas
            # colunas que mostra o que o estado da party fez com o ranking.
            # base_score é a relevância HÍBRIDA fundida; `vec` e `fts` são as
            # duas pernas cruas que a fusão combinou — sem elas não dá para
            # dizer se um chunk entrou pelo sentido ou pelo termo literal.
            # "—" em fts = o chunk não apareceu no lado BM25.
            out.append("| # | vec | fts | base_score | score | boost | arquivo | tipo | trecho |")
            out.append("|---|---|---|---|---|---|---|---|---|")
            for i, c in enumerate(r["chunks"], start=1):
                trecho = c["trecho"].replace("|", "\\|")
                delta = c["score"] - c["base_score"]
                razoes = "; ".join(c["boost_reasons"]).replace("|", "\\|")
                boost = f"+{delta:.3f} ({razoes})" if delta else "—"
                vec = "—" if c.get("vector_score") is None else f"{c['vector_score']:.3f}"
                fts = "—" if c.get("fts_score") is None else f"{c['fts_score']:.2f}"
                out.append(
                    f"| {i} | {vec} | {fts} | "
                    f"{c['base_score']:.3f} | {c['score']:.3f} | {boost} | "
                    f"`{c['source_file']}` | {c['source_type']} | {trecho} |"
                )
        else:
            out.append("*(nenhum)*")
        out.append("")

        if r.get("sem_geracao"):
            out.append("*(geração pulada — `--sem-geracao`)*")
        else:
            out.append("**Resposta:**")
            out.append("")
            out.append(r["resposta"] or "*(vazia)*")
            out.append("")
            out.append(
                f"**Fontes citadas:** "
                f"{', '.join(f'`{f}`' for f in r['fontes']) or '—'}"
            )
        out.append("")
        out.append("---")
        out.append("")

    out.append("## Checagens mecânicas")
    out.append("")
    out.extend(_checagens_mecanicas(resultados))
    out.append("")
    return "\n".join(out)


def gerar_relatorio_showcase(resultados: list[dict], meta: dict) -> str:
    """Relatório do `--showcase`: material BRUTO para anexar ao README.

    Deliberadamente mais magro que `gerar_relatorio` — sem tabela de chunks,
    sem checagens mecânicas, sem boost. Só o que um leitor humano (ou um
    juiz mais forte, depois) precisa para julgar acerto/alucinação: a
    pergunta, a resposta INTEGRAL, as fontes citadas e a latência. O campo
    `veredito` fica vazio de propósito — não é este script que julga
    qualidade, ver docstring do módulo.
    """
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    out = ["# BroPilot — Relatório de Acurácia (showcase)", ""]

    if meta.get("aviso"):
        out += [
            "> ## ⚠️ ÍNDICE DESATUALIZADO",
            f"> **{meta['aviso']}**",
            "",
        ]

    stats_txt = (
        "SIM" if meta.get("has_live_stats")
        else "NÃO (sem snapshot do mod companion — Mac não roda o Script "
             "Extender/BG3SE deste projeto; ficha da party é só nível/raça/"
             "classe)"
    )
    out += [
        f"Gerado em {agora}.",
        "",
        "> Este documento **coleta evidência fielmente** — pergunta, resposta "
        "completa, fontes e latência — rodando a stack real (Ollama + índice "
        "+ save). Ele **não julga** se uma resposta está certa, incompleta ou "
        "alucinada; isso fica para a coluna **Veredito**, deixada em branco "
        "para preenchimento humano (ou por um juiz automatizado mais forte) "
        "depois.",
        "",
        "## Setup",
        "",
        f"- Data: **{agora}**",
        f"- Modelo de geração: `{meta['chat_model']}`",
        f"- Modelo de embedding: `{meta['embed_model']}` (dim {meta['embed_dim']})",
        f"- Índice: **{meta['chunks']} chunks** de {meta['arquivos']} arquivos",
        # meta['save'] já vem de carregar_save() como frase pronta ("Save
        # carregado: X.lsv" ou o aviso de falha) — sem prefixo aqui, senão
        # duplica ("Save carregado: Save carregado: ...").
        f"- {meta.get('save', 'Nenhum save carregado')}",
        f"- Party tinha stats ao vivo (mod companion): **{stats_txt}**",
        "",
        "---",
        "",
        "## Perguntas",
        "",
    ]

    for r in resultados:
        out.append(f"### `{r['id']}` — {r['categoria']}")
        out.append("")
        out.append(f"**Pergunta:** {r['texto']}")
        out.append("")
        out.append(f"**Latência:** {r['segundos']:.1f}s")
        out.append("")

        if r["erro"]:
            out.append(f"> **FALHOU:** `{r['erro']}`")
            out.append("")
            out.append("**Veredito:** _(a preencher)_")
            out.append("")
            out.append("---")
            out.append("")
            continue

        out.append("**Resposta:**")
        out.append("")
        out.append(r["resposta"] or "*(vazia)*")
        out.append("")
        out.append(
            f"**Fontes citadas:** "
            f"{', '.join(f'`{f}`' for f in r['fontes']) or '—'}"
        )
        out.append("")
        out.append("**Veredito:** _(a preencher)_")
        out.append("")
        out.append("---")
        out.append("")

    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m bropilot_core.scripts.eval_rag",
        description="Roda uma bateria de perguntas contra o RAG e gera relatório .md",
    )
    parser.add_argument("--output", metavar="CAMINHO", help="arquivo .md de saída.")
    parser.add_argument("-k", type=int, default=6, help="chunks por pergunta.")
    parser.add_argument("--store", metavar="CAMINHO", help="diretório do índice.")
    parser.add_argument(
        "--com-save",
        action="store_true",
        help="carrega o save mais recente e roda a bateria COM signals, para "
             "comparar com o relatório sem save (as colunas base_score/score/"
             "boost mostram o que o boost state-aware fez).",
    )
    parser.add_argument(
        "--dump", metavar="CAMINHO", help="bropilot_inventory.json do mod."
    )
    parser.add_argument(
        "--sem-geracao",
        action="store_true",
        help="só busca, sem chamar o LLM. A geração local é ~95%% do tempo da "
             "bateria e não afeta métrica de retrieval nenhuma.",
    )
    parser.add_argument(
        "--peso-vetorial",
        type=float,
        default=_DEFAULT_VECTOR_WEIGHT,
        metavar="P",
        help="peso do lado vetorial na fusão híbrida (0-1); o FTS/BM25 fica "
             f"com 1-P. Default {_DEFAULT_VECTOR_WEIGHT}. P=1.0 "
             "reproduz a busca vetorial pura (o baseline pré-híbrida) pelo "
             "MESMO caminho de código; P=0.0 é BM25 puro. Para varrer vários "
             "pesos de uma vez, ver `compare_hybrid.py`.",
    )
    parser.add_argument(
        "--lang", choices=["en", "pt"], default="pt",
        help="idioma das 12 perguntas (default pt). 'en' roda PERGUNTAS_EN — "
             "mesmos id/categoria/grupo, texto traduzido. Não muta a bateria "
             "PT nem o relatório baseline existente.",
    )
    parser.add_argument(
        "--showcase",
        action="store_true",
        help="roda as 10 perguntas fixas de PERGUNTAS_SHOWCASE (material bruto "
             "para o relatório de acurácia do README) em vez da bateria "
             "PERGUNTAS/PERGUNTAS_EN. Sempre com geração ligada e sempre com "
             "save carregado (implica --com-save); ignora --lang e produz um "
             "relatório mais magro via gerar_relatorio_showcase (sem tabela "
             "de chunks nem checagens mecânicas — só pergunta, resposta "
             "completa, fontes, latência e um campo 'veredito' vazio para "
             "preenchimento humano). Incompatível com --sem-geracao.",
    )
    args = parser.parse_args(argv)

    if args.showcase and args.sem_geracao:
        print("erro: --showcase é incompatível com --sem-geracao — o "
              "relatório de acurácia precisa da resposta gerada de verdade.",
              file=sys.stderr)
        return 1

    perguntas = PERGUNTAS_SHOWCASE if args.showcase else (
        PERGUNTAS_EN if args.lang == "en" else PERGUNTAS
    )
    store_dir = Path(args.store) if args.store else STORE_DIR

    try:
        provider = create_provider()
        provider.health_check()
        retriever = Retriever(
            provider, store_dir, vector_weight=args.peso_vetorial
        )
        meta = _metadados_indice(store_dir)
    except (RuntimeError, ValueError) as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return 1

    meta["vector_weight"] = args.peso_vetorial
    meta["chat_model"] = provider.chat_model
    ctx = None
    meta["signals"] = "**None** — sem save, o boost state-aware não age"
    meta["has_live_stats"] = False
    if args.com_save or args.showcase:
        from ..cli import carregar_save

        ctx, aviso_save = carregar_save(args.dump)
        print(aviso_save)
        if ctx is None:
            print("erro: --com-save/--showcase pedido mas nenhum save foi "
                  "carregado.", file=sys.stderr)
            return 1
        from ..serialize import extract_signals

        sinais = extract_signals(ctx)
        meta["signals"] = (
            f"ativos — classes={sinais.get('classes')} "
            f"subclasses={sinais.get('subclasses')} "
            f"levels={sinais.get('levels')} "
            f"has_live_stats={sinais.get('has_live_stats')}"
        )
        meta["save"] = aviso_save
        meta["has_live_stats"] = bool(sinais.get("has_live_stats"))

    spy = _RecordingRetriever(retriever)
    orchestrator = Orchestrator(provider, spy, k=args.k)

    print(f"Índice: {meta['chunks']} chunks / {meta['arquivos']} arquivos "
          f"({meta['embed_model']})")
    if meta["aviso"]:
        # Mesmo aviso do topo do relatório: avaliar índice desatualizado sem
        # saber disso é pior que esperar a reindexação.
        print(f"\n  ⚠️  ÍNDICE DESATUALIZADO: {meta['aviso']}\n", file=sys.stderr)
    meta["sem_geracao"] = args.sem_geracao
    meta["lang"] = args.lang
    if args.sem_geracao:
        print(f"Rodando {len(perguntas)} perguntas ({args.lang}) — só busca, sem geração.\n")
    else:
        print(f"Rodando {len(perguntas)} perguntas ({args.lang}) com geração local — vai demorar.\n")

    resultados = executar(
        orchestrator, spy, ctx, sem_geracao=args.sem_geracao, perguntas=perguntas
    )

    if args.showcase:
        destino = Path(
            args.output
            or f"bropilot_core/eval/showcase_accuracy_"
               f"{datetime.now():%Y%m%d_%H%M%S}.md"
        )
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(gerar_relatorio_showcase(resultados, meta), encoding="utf-8")
    else:
        destino = Path(
            args.output
            or f"bropilot_core/eval/rag_eval_"
               f"{'com_save' if args.com_save else 'sem_save'}_"
               f"{'retrieval_' if args.sem_geracao else ''}"
               f"{'en_' if args.lang == 'en' else ''}"
               f"{datetime.now():%Y%m%d_%H%M%S}.md"
        )
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(gerar_relatorio(resultados, meta, args.k), encoding="utf-8")

    falhas = sum(1 for r in resultados if r["erro"])
    print(f"\nRelatório: {destino}")
    if falhas:
        print(f"({falhas} pergunta(s) falharam — registradas no relatório)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
