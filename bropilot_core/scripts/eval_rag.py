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
from ..index.retriever import RetrievedChunk, Retriever
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
) -> list[dict]:
    """Roda a bateria. Uma pergunta que falhar vira registro de erro e a
    bateria continua — perder as 11 seguintes por causa de uma seria pior.

    `sem_geracao=True` faz só a busca. A geração local responde por ~95% do
    tempo da bateria e não influencia nenhuma métrica de retrieval, então
    medir retrieval com ela ligada é pagar horas por nada.
    """
    resultados = []
    total = len(PERGUNTAS)

    for i, pergunta in enumerate(PERGUNTAS, start=1):
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
        f"- k (chunks por pergunta): **{k}**",
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
            out.append("| # | base_score | score | boost | arquivo | tipo | trecho |")
            out.append("|---|---|---|---|---|---|---|")
            for i, c in enumerate(r["chunks"], start=1):
                trecho = c["trecho"].replace("|", "\\|")
                delta = c["score"] - c["base_score"]
                razoes = "; ".join(c["boost_reasons"]).replace("|", "\\|")
                boost = f"+{delta:.3f} ({razoes})" if delta else "—"
                out.append(
                    f"| {i} | {c['base_score']:.3f} | {c['score']:.3f} | {boost} | "
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
    args = parser.parse_args(argv)

    store_dir = Path(args.store) if args.store else STORE_DIR

    try:
        provider = create_provider()
        provider.health_check()
        retriever = Retriever(provider, store_dir)
        meta = _metadados_indice(store_dir)
    except RuntimeError as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return 1

    ctx = None
    meta["signals"] = "**None** — sem save, o boost state-aware não age"
    if args.com_save:
        from ..cli import carregar_save

        ctx, aviso_save = carregar_save(args.dump)
        print(aviso_save)
        if ctx is None:
            print("erro: --com-save pedido mas nenhum save foi carregado.",
                  file=sys.stderr)
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

    spy = _RecordingRetriever(retriever)
    orchestrator = Orchestrator(provider, spy, k=args.k)

    print(f"Índice: {meta['chunks']} chunks / {meta['arquivos']} arquivos "
          f"({meta['embed_model']})")
    if meta["aviso"]:
        # Mesmo aviso do topo do relatório: avaliar índice desatualizado sem
        # saber disso é pior que esperar a reindexação.
        print(f"\n  ⚠️  ÍNDICE DESATUALIZADO: {meta['aviso']}\n", file=sys.stderr)
    meta["sem_geracao"] = args.sem_geracao
    if args.sem_geracao:
        print(f"Rodando {len(PERGUNTAS)} perguntas — só busca, sem geração.\n")
    else:
        print(f"Rodando {len(PERGUNTAS)} perguntas com geração local — vai demorar.\n")

    resultados = executar(orchestrator, spy, ctx, sem_geracao=args.sem_geracao)

    destino = Path(
        args.output
        or f"bropilot_core/eval/rag_eval_"
           f"{'com_save' if args.com_save else 'sem_save'}_"
           f"{'retrieval_' if args.sem_geracao else ''}"
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
