"""Compara o RETRIEVAL entre IDIOMA DA QUERY — não idioma do corpus.

Achado de 28/07: o corpus já é ~97%% inglês (146 de 150 arquivos — wiki, forum
e YouTube são todos ingleses). A variável que falta testar não é o idioma da
base, é o idioma de QUEM PERGUNTA. Este script mede duas coisas, contra o
MESMO índice (sem tocar em index/retriever, sem "melhorar" busca nenhuma):

1. A bateria completa de 12 perguntas (PERGUNTAS/PERGUNTAS_EN de eval_rag) em
   PT vs EN — Jaccard de paráfrases, recall@k, spread, duplicatas.
2. O GRUPO DE CONTROLE de idioma — a parte mais importante: duas intenções
   (build de Monge Open Hand; action economy com Dual Wielder), cada uma nas
   três formas EN / PT / MISTA (português com termos do jogo em inglês). É
   isto que decide se o jogador precisa trocar o idioma do jogo ou se dá para
   perguntar em PT com termos EN e recuperar tão bem quanto em EN puro.

Depois, opcionalmente (--com-geracao), roda uma amostra pequena (n=4, EN: as
duas fora-de-escopo + duas de build) com geração REAL, para uma checagem
secundária de alucinação — não é conclusiva, é indício.

Tudo em --sem-geracao roda em segundos: é busca pura, sem LLM. Ver
`eval_rag.py` (bateria completa com geração) e `compare_retrieval.py` (mesmo
padrão de comparação, mas entre ÍNDICES em vez de idiomas) — este script segue
a convenção dos dois.

Uso:
    python -m bropilot_core.scripts.compare_language --output relatorio.md
    python -m bropilot_core.scripts.compare_language --output relatorio.md --com-geracao
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

from ..index.build import STORE_DIR
from ..index.retriever import Retriever
from ..llm import create_provider
from ..orchestrator import Orchestrator
from .compare_retrieval import _duplicatas, _spread
from .eval_rag import (
    PERGUNTAS,
    PERGUNTAS_EN,
    _MARCADORES_NAO_SEI,
    _RecordingRetriever,
    _jaccard,
    _metadados_indice,
    executar,
)

# Grupo de controle: 2 intenções x 3 formas de query. A intenção de Monge usa
# "Open Hand" (termo do jogo) mesmo na forma PT pura, porque o nome da
# subclasse não tem tradução natural em uso — é assim que o jogador PT-BR
# realmente digitaria. A forma MISTA é a hipótese central: frase em português,
# termos de jogo em inglês.
CONTROLE_IDIOMA = [
    {"id": "ctl_monk_en", "intencao": "monge_openhand", "forma": "en",
     "texto": "best Open Hand Monk build for unarmed damage"},
    {"id": "ctl_monk_pt", "intencao": "monge_openhand", "forma": "pt",
     "texto": "melhor build de monge mão aberta para dano desarmado"},
    {"id": "ctl_monk_mista", "intencao": "monge_openhand", "forma": "mista",
     "texto": "melhor build de Open Hand Monk pra dano desarmado"},

    {"id": "ctl_ae_en", "intencao": "action_economy_dualwielder", "forma": "en",
     "texto": "how does action economy work with Dual Wielder?"},
    {"id": "ctl_ae_pt", "intencao": "action_economy_dualwielder", "forma": "pt",
     "texto": "como funciona a economia de ação usando Dual Wielder?"},
    {"id": "ctl_ae_mista", "intencao": "action_economy_dualwielder", "forma": "mista",
     "texto": "como funciona a action economy usando Dual Wielder?"},
]

_INTENCOES = ["monge_openhand", "action_economy_dualwielder"]
_FORMAS = ["en", "pt", "mista"]

# Ground truth MÍNIMO e defensável (não elaborado): a fonte autoritativa para
# a pergunta de regra factual é a wiki; para as perguntas de Monge, qualquer
# doc com "monk" no nome do arquivo, ou o vídeo "One Punch Monk"
# (youtube_nNOWTLggypc.md, que não tem "monk" no nome). Recall = pelo menos
# UM chunk assim aparece no top-k — não é ranking, é presença/ausência.
_RECALL_WIKI_IDS = {"c1"}
_RECALL_MONK_IDS = {
    "a1", "d1", "d2", "d3", "e1",
    "ctl_monk_en", "ctl_monk_pt", "ctl_monk_mista",
}
_MONK_VIDEO = "youtube_nNOWTLggypc.md"

# A amostra pequena de geração (item 5): as duas fora-de-escopo + duas de
# build, só em EN. n=4 — ver aviso explícito no relatório.
_IDS_GERACAO_PEQUENA = ["f1", "f2", "a1", "a2"]


def coletar(
    retriever: Retriever, perguntas: list[dict], k: int, *, max_por_fonte: int = 1
) -> dict[str, list[dict]]:
    """Só busca (sem signals — mesma condição do baseline PT, sem save
    carregado). Devolve hits por id, com source_type incluído (o recall@k da
    pergunta de regra precisa saber se o chunk é wiki).

    `max_por_fonte` repassa direto pro Retriever.search — default 1 é o
    comportamento atual (dedup ligado); um valor bem alto reproduz o
    comportamento PRÉ-dedup (ver `compare_dedup.py`), porque alargar o pool
    sem filtrar por fonte não muda o top-k, só o widening já é invariante a
    isso (LanceDB devolve ordenado; truncar um pool maior no mesmo ponto dá o
    mesmo prefixo).
    """
    hits = {}
    for p in perguntas:
        resultado = retriever.search(
            p["texto"], signals=None, k=k, max_por_fonte=max_por_fonte
        )
        hits[p["id"]] = [
            {"source_file": h.source_file, "source_type": h.source_type, "score": h.score}
            for h in resultado
        ]
        print(f"  {p['id']}: {len(resultado)} hits")
    return hits


def _arquivos(hits: list[dict]) -> set[str]:
    return {h["source_file"] for h in hits}


def _recall(hits: list[dict], kind: str) -> bool:
    if kind == "wiki":
        return any(h["source_type"] == "wiki" for h in hits)
    return any(
        "monk" in h["source_file"].lower() or h["source_file"] == _MONK_VIDEO
        for h in hits
    )


def _tabela(cabecalho: list[str], linhas: list[list]) -> list[str]:
    out = ["| " + " | ".join(cabecalho) + " |",
           "|" + "|".join("---" for _ in cabecalho) + "|"]
    out += ["| " + " | ".join(str(c) for c in linha) + " |" for linha in linhas]
    return out


def _media(valores: list[float]) -> float:
    return sum(valores) / len(valores) if valores else 0.0


def gerar_relatorio(
    meta: dict,
    k: int,
    hits_pt: dict[str, list[dict]],
    hits_en: dict[str, list[dict]],
    hits_ctl: dict[str, list[dict]],
    geracao: list[dict] | None,
) -> str:
    out = [
        "# Idioma da query vs. retrieval — PT × EN × MISTA",
        "",
        f"Gerado em {datetime.now():%Y-%m-%d %H:%M:%S}. k={k}.",
        "",
        "> O corpus já é ~97% inglês (medido em 28/07). A pergunta aqui não é "
        "\"o corpus está no idioma certo\" — é \"em que idioma eu devo "
        "PERGUNTAR\". Como no `eval_rag.py`, isto **coleta evidência**: "
        "Jaccard mede ESTABILIDADE (as reformulações recuperam o mesmo "
        "material?), recall@k mede ACURÁCIA (o material certo aparece?). São "
        "coisas diferentes — um retrieval pode ser estável e errado, ou "
        "instável e ainda assim acertar.",
        "",
        "## Setup",
        "",
        f"- Índice: **{meta['chunks']} chunks** de {meta['arquivos']} arquivos "
        f"({meta['arquivos_no_disco']} elegíveis)",
        f"- Embeddings: `{meta['embed_model']}` (dim {meta['embed_dim']})",
        f"- k: **{k}** | `signals`: None (sem save — mesma condição do "
        f"baseline PT `rag_eval_20260728_211219.md`, não sobrescrito)",
        "",
        "---",
        "",
    ]

    # ------------------------------------------------------------------
    # 1. A TABELA DE RELANCE — grupo de controle EN × PT × MISTA
    # ------------------------------------------------------------------
    out += [
        "## 1. Grupo de controle de idioma — a tabela de relance",
        "",
        "Mesma intenção, três formas de digitar. Jaccard dos `source_file` "
        "recuperados entre pares de formas (1.00 = idênticos).",
        "",
    ]
    linhas_jac = []
    jac_medias = {"en×pt": [], "en×mista": [], "pt×mista": []}
    for intencao in _INTENCOES:
        ids = {f["forma"]: f["id"] for f in CONTROLE_IDIOMA if f["intencao"] == intencao}
        a_en = _arquivos(hits_ctl[ids["en"]])
        a_pt = _arquivos(hits_ctl[ids["pt"]])
        a_mista = _arquivos(hits_ctl[ids["mista"]])
        j_en_pt = _jaccard(a_en, a_pt)
        j_en_mista = _jaccard(a_en, a_mista)
        j_pt_mista = _jaccard(a_pt, a_mista)
        jac_medias["en×pt"].append(j_en_pt)
        jac_medias["en×mista"].append(j_en_mista)
        jac_medias["pt×mista"].append(j_pt_mista)
        linhas_jac.append([
            f"`{intencao}`", f"{j_en_pt:.2f}", f"{j_en_mista:.2f}", f"{j_pt_mista:.2f}",
        ])
    linhas_jac.append([
        "**média**",
        f"**{_media(jac_medias['en×pt']):.2f}**",
        f"**{_media(jac_medias['en×mista']):.2f}**",
        f"**{_media(jac_medias['pt×mista']):.2f}**",
    ])
    out += _tabela(["intenção", "EN × PT", "EN × MISTA", "PT × MISTA"], linhas_jac)

    out += ["", "**Recall@k (só a intenção de Monge tem ground truth — "
            "ver §3):**", ""]
    linhas_rec = []
    for forma in _FORMAS:
        fid = next(f["id"] for f in CONTROLE_IDIOMA
                   if f["intencao"] == "monge_openhand" and f["forma"] == forma)
        hit = _recall(hits_ctl[fid], "monk")
        linhas_rec.append([forma, f"`{fid}`", "sim" if hit else "**não**"])
    out += _tabela(["forma", "pergunta", "recall monge"], linhas_rec)

    out += ["", "**Spread e duplicatas por forma (média das 2 intenções):**", ""]
    linhas_sd = []
    for forma in _FORMAS:
        ids = [f["id"] for f in CONTROLE_IDIOMA if f["forma"] == forma]
        spreads = [_spread(hits_ctl[i]) for i in ids]
        dups = [_duplicatas(hits_ctl[i]) for i in ids]
        linhas_sd.append([forma, f"{_media(spreads):.3f}", str(sum(dups))])
    out += _tabela(["forma", "spread médio", "duplicatas (total)"], linhas_sd)

    out += ["", "### Arquivos recuperados por forma (detalhe)", ""]
    for intencao in _INTENCOES:
        out.append(f"**`{intencao}`**")
        for forma in _FORMAS:
            fid = next(f["id"] for f in CONTROLE_IDIOMA
                       if f["intencao"] == intencao and f["forma"] == forma)
            arquivos = ", ".join(sorted(_arquivos(hits_ctl[fid]))) or "—"
            out.append(f"- {forma} (`{fid}`): {arquivos}")
        out.append("")

    # ------------------------------------------------------------------
    # 2. Bateria completa (12 perguntas): PT vs EN
    # ------------------------------------------------------------------
    out += ["---", "", "## 2. Bateria completa (12 perguntas): PT vs EN", ""]

    out += ["### Jaccard de paráfrases (`d1`×`d2`×`d3`)", ""]
    pares = [("d1", "d2"), ("d1", "d3"), ("d2", "d3")]
    linhas = []
    med_pt, med_en = [], []
    for a, b in pares:
        j_pt = _jaccard(_arquivos(hits_pt[a]), _arquivos(hits_pt[b]))
        j_en = _jaccard(_arquivos(hits_en[a]), _arquivos(hits_en[b]))
        med_pt.append(j_pt)
        med_en.append(j_en)
        linhas.append([f"`{a}`×`{b}`", f"{j_pt:.2f}", f"{j_en:.2f}"])
    linhas.append(["**média**", f"**{_media(med_pt):.2f}**", f"**{_media(med_en):.2f}**"])
    out += _tabela(["par", "PT", "EN"], linhas)

    out += ["", "### Recall@k", "",
            "Regra factual (`c1`): algum chunk `source_type=wiki` no top-k? "
            "Monge (`a1`,`d1`,`d2`,`d3`,`e1`): algum arquivo com \"monk\" no "
            "nome, ou o vídeo One Punch Monk, no top-k?", ""]
    linhas = [["`c1` (wiki)",
               "sim" if _recall(hits_pt["c1"], "wiki") else "**não**",
               "sim" if _recall(hits_en["c1"], "wiki") else "**não**"]]
    monge_ids = ["a1", "d1", "d2", "d3", "e1"]
    acertos_pt = acertos_en = 0
    for pid in monge_ids:
        h_pt = _recall(hits_pt[pid], "monk")
        h_en = _recall(hits_en[pid], "monk")
        acertos_pt += h_pt
        acertos_en += h_en
        linhas.append([f"`{pid}` (monge)", "sim" if h_pt else "**não**",
                        "sim" if h_en else "**não**"])
    linhas.append([f"**monge: {acertos_pt}/{len(monge_ids)} vs {acertos_en}/{len(monge_ids)}**",
                    "", ""])
    out += _tabela(["pergunta", "PT", "EN"], linhas)

    out += ["", f"### Spread e duplicatas no top-{k} (todas as 12 perguntas)", ""]
    linhas = []
    spreads_pt, spreads_en = [], []
    dups_pt = dups_en = 0
    for p in PERGUNTAS:
        pid = p["id"]
        s_pt, s_en = _spread(hits_pt[pid]), _spread(hits_en[pid])
        d_pt, d_en = _duplicatas(hits_pt[pid]), _duplicatas(hits_en[pid])
        spreads_pt.append(s_pt)
        spreads_en.append(s_en)
        dups_pt += d_pt
        dups_en += d_en
        linhas.append([f"`{pid}`", f"{s_pt:.3f}", f"{s_en:.3f}", d_pt, d_en])
    linhas.append(["**média/total**", f"**{_media(spreads_pt):.3f}**",
                    f"**{_media(spreads_en):.3f}**", f"**{dups_pt}**", f"**{dups_en}**"])
    out += _tabela(["pergunta", "spread PT", "spread EN", "dup. PT", "dup. EN"], linhas)

    # ------------------------------------------------------------------
    # 3. Geração pequena (n=4, EN) — hipótese secundária
    # ------------------------------------------------------------------
    if geracao is not None:
        out += ["---", "", "## 3. Geração pequena (n=4, EN) — indício, não conclusão", "",
                "> **n=4.** Só as duas perguntas fora-de-escopo (Elden Ring, "
                "Copa do Mundo) e duas de build, em inglês, com geração REAL. "
                "Serve para uma hipótese secundária — se o prompt em inglês "
                "reduz a alucinação vista no baseline PT (o modelo é mais "
                "forte na sua língua dominante de treino) — não para "
                "concluir nada com confiança estatística.", ""]
        for r in geracao:
            out.append(f"### `{r['id']}` — {r['categoria']}")
            out.append("")
            out.append(f"**Pergunta (EN):** {r['texto']}")
            out.append("")
            if r["erro"]:
                out.append(f"> **FALHOU:** `{r['erro']}`")
                out.append("")
                continue
            texto = (r["resposta"] or "").lower()
            achados = [m for m in _MARCADORES_NAO_SEI if m in texto]
            if r["grupo"] == "fora_escopo":
                out.append(f"*Marcador de \"não sei\" encontrado:* "
                            f"{', '.join(f'`{a}`' for a in achados) or '**nenhum**'}")
                out.append("")
            out.append("**Resposta:**")
            out.append("")
            out.append(r["resposta"] or "*(vazia)*")
            out.append("")
            out.append(f"**Fontes citadas:** "
                        f"{', '.join(f'`{f}`' for f in r['fontes']) or '—'}")
            out.append("")
            out.append("---")
            out.append("")

    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m bropilot_core.scripts.compare_language",
        description="Compara retrieval por IDIOMA DA QUERY (PT/EN/MISTA), "
                     "mesmo índice, mesmas 12 perguntas + grupo de controle.",
    )
    parser.add_argument("--store", metavar="CAMINHO", help="diretório do índice.")
    parser.add_argument("-k", type=int, default=6, help="chunks por pergunta.")
    parser.add_argument("--output", required=True, metavar="CAMINHO")
    parser.add_argument(
        "--com-geracao", action="store_true",
        help="além do retrieval, roda a amostra pequena (n=4, EN) com "
             "geração real do LLM local — lento, é opcional.",
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

    if meta["aviso"]:
        print(f"\n  ⚠️  ÍNDICE DESATUALIZADO: {meta['aviso']}\n", file=sys.stderr)

    print("bateria PT (12 perguntas, só busca):")
    hits_pt = coletar(retriever, PERGUNTAS, args.k)
    print("bateria EN (12 perguntas, só busca):")
    hits_en = coletar(retriever, PERGUNTAS_EN, args.k)
    print("grupo de controle (6 perguntas, só busca):")
    hits_ctl = coletar(retriever, CONTROLE_IDIOMA, args.k)

    geracao = None
    if args.com_geracao:
        print("\namostra pequena (n=4, EN) — geração real, vai demorar:")
        perguntas_pequenas = [p for p in PERGUNTAS_EN if p["id"] in _IDS_GERACAO_PEQUENA]
        spy = _RecordingRetriever(retriever)
        orchestrator = Orchestrator(provider, spy, k=args.k)
        geracao = executar(orchestrator, spy, None, sem_geracao=False,
                            perguntas=perguntas_pequenas)

    destino = Path(args.output)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(
        gerar_relatorio(meta, args.k, hits_pt, hits_en, hits_ctl, geracao),
        encoding="utf-8",
    )
    print(f"\nRelatório: {destino}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
