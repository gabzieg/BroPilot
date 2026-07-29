"""Compara retrieval ANTES × DEPOIS do dedup por `source_file`
(`Retriever._dedup_por_fonte`), na bateria EN de `eval_rag.py`.

Motivação: o experimento de idioma (`compare_language.py`) mediu dois
problemas de retrieval independentes de idioma — (a) 19-22 duplicatas no
top-6 nas baterias, um documento longo ocupando vários slots; (b) a wiki
(fonte autoritativa de regra) nunca aparecia no top-6 da pergunta factual
(`c1`). Hipótese: dedup sozinho conserta (a) e, de brinde, promove a wiki pro
top-6 em (b) — se ela já estava ali perto (rank 7-8) só sendo ofuscada por
slots gastos com repetição.

"Antes" não precisa de checkout de código nem de flag liga/desliga: alargar o
pool sem filtrar por fonte não muda o top-k (LanceDB devolve ordenado; truncar
um pool maior no mesmo corte dá o mesmo prefixo) — então
`Retriever.search(max_por_fonte=<bem alto>)` reproduz exatamente o
comportamento pré-dedup usando o MESMO código, sem duplicar lógica nem
arriscar as duas condições divergirem por outro motivo.

Uso:
    python -m bropilot_core.scripts.compare_dedup --output relatorio.md
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

from ..index.build import STORE_DIR
from ..index.retriever import Retriever
from ..llm import create_provider
from .compare_language import _arquivos, _recall, coletar
from .compare_retrieval import _duplicatas, _spread
from .eval_rag import PERGUNTAS_EN, _jaccard, _metadados_indice

_SEM_DEDUP = 10**9  # maior que qualquer contagem real de chunks por arquivo

_PARES_PARAFRASE = [("d1", "d2"), ("d1", "d3"), ("d2", "d3")]
_MONGE_IDS = ["a1", "d1", "d2", "d3", "e1"]


def _tabela(cabecalho: list[str], linhas: list[list]) -> list[str]:
    out = ["| " + " | ".join(cabecalho) + " |",
           "|" + "|".join("---" for _ in cabecalho) + "|"]
    out += ["| " + " | ".join(str(c) for c in linha) + " |" for linha in linhas]
    return out


def _media(valores: list[float]) -> float:
    return sum(valores) / len(valores) if valores else 0.0


def gerar_relatorio(meta: dict, k: int, antes: dict, depois: dict) -> str:
    out = [
        "# Dedup por source_file — antes × depois",
        "",
        f"Gerado em {datetime.now():%Y-%m-%d %H:%M:%S}. k={k}. Bateria EN "
        "(`PERGUNTAS_EN` de `eval_rag.py`), só retrieval (`--sem-geracao` "
        "equivalente — chama `Retriever.search` direto).",
        "",
        f"- Índice: **{meta['chunks']} chunks** de {meta['arquivos']} arquivos",
        f"- Embeddings: `{meta['embed_model']}` (dim {meta['embed_dim']})",
        f"- \"antes\" = `max_por_fonte={_SEM_DEDUP}` (dedup nunca aciona); "
        f"\"depois\" = `max_por_fonte=1` (default atual)",
        "",
        "---",
        "",
    ]

    # 1. duplicatas
    out += [f"## Duplicatas no top-{k}", ""]
    linhas, tot_a, tot_d = [], 0, 0
    for p in PERGUNTAS_EN:
        pid = p["id"]
        d_a, d_d = _duplicatas(antes[pid]), _duplicatas(depois[pid])
        tot_a += d_a
        tot_d += d_d
        linhas.append([f"`{pid}`", d_a, d_d])
    linhas.append(["**total**", f"**{tot_a}**", f"**{tot_d}**"])
    out += _tabela(["pergunta", "antes", "depois"], linhas)

    # 2. recall@k — wiki (c1) e monge
    out += ["", "## Recall@k — a hipótese da wiki", "",
            "`c1` é a pergunta de regra factual (Battle Master / Superiority "
            "Dice); ground truth = algum chunk `source_type=wiki` no top-k. "
            "Se o dedup sozinho desenterra a wiki, `c1` vira \"sim\" na "
            "coluna \"depois\" sem ter mudado nada além do dedup.", ""]
    linhas = [[
        "`c1` (wiki)",
        "sim" if _recall(antes["c1"], "wiki") else "**não**",
        "sim" if _recall(depois["c1"], "wiki") else "**não**",
    ]]
    acertos_a = acertos_d = 0
    for pid in _MONGE_IDS:
        h_a, h_d = _recall(antes[pid], "monk"), _recall(depois[pid], "monk")
        acertos_a += h_a
        acertos_d += h_d
        linhas.append([f"`{pid}` (monge)", "sim" if h_a else "**não**",
                        "sim" if h_d else "**não**"])
    linhas.append([f"**monge: {acertos_a}/{len(_MONGE_IDS)} vs {acertos_d}/{len(_MONGE_IDS)}**",
                    "", ""])
    out += _tabela(["pergunta", "antes", "depois"], linhas)

    hipotese_wiki = _recall(depois["c1"], "wiki") and not _recall(antes["c1"], "wiki")
    out += [
        "",
        f"> **Hipótese \"dedup sozinho desenterra a wiki\": "
        f"{'CONFIRMADA' if hipotese_wiki else 'NÃO CONFIRMADA'}.**",
        "",
    ]

    # 3. jaccard de paráfrases
    out += ["## Jaccard de paráfrases (`d1`×`d2`×`d3`)", "",
            "Não deveria piorar; pode melhorar se a duplicata estava "
            "mascarando diversidade real entre as reformulações.", ""]
    linhas, med_a, med_d = [], [], []
    for a, b in _PARES_PARAFRASE:
        j_a = _jaccard(_arquivos(antes[a]), _arquivos(antes[b]))
        j_d = _jaccard(_arquivos(depois[a]), _arquivos(depois[b]))
        med_a.append(j_a)
        med_d.append(j_d)
        linhas.append([f"`{a}`×`{b}`", f"{j_a:.2f}", f"{j_d:.2f}"])
    linhas.append(["**média**", f"**{_media(med_a):.2f}**", f"**{_media(med_d):.2f}**"])
    out += _tabela(["par", "antes", "depois"], linhas)

    # 4. spread, de brinde — o dedup não deveria mudar o score de quem
    # sobrevive, só QUAIS chunks aparecem.
    out += ["", f"## Spread no top-{k} (referência — dedup não toca score)", ""]
    linhas, sp_a, sp_d = [], [], []
    for p in PERGUNTAS_EN:
        pid = p["id"]
        s_a, s_d = _spread(antes[pid]), _spread(depois[pid])
        sp_a.append(s_a)
        sp_d.append(s_d)
        linhas.append([f"`{pid}`", f"{s_a:.3f}", f"{s_d:.3f}"])
    linhas.append(["**média**", f"**{_media(sp_a):.3f}**", f"**{_media(sp_d):.3f}**"])
    out += _tabela(["pergunta", "antes", "depois"], linhas)

    # 5. próximo passo
    out += ["", "---", "", "## Próximo passo", ""]
    if hipotese_wiki:
        out.append(
            "Dedup sozinho resolveu (a) e (b). Não abrir cota por "
            "source_type nem busca híbrida agora — seria consertar um "
            "problema que já não existe."
        )
    else:
        out.append(
            "Dedup resolveu (a) (duplicatas) mas **não** (b): a wiki segue "
            "fora do top-k em `c1` mesmo sem slots desperdiçados em "
            "repetição — ou seja, ela não estava perto (rank 7-8) sendo "
            "só ofuscada por duplicata; está genuinamente mal-rankeada pela "
            "similaridade crua para essa pergunta. Próximo candidato: cota "
            "mínima por `source_type` (garantir 1 slot de wiki quando "
            "existir candidato razoável) ou busca híbrida (BM25 + vetorial) "
            "para o termo factual específico (\"Superiority Dice\"). Não "
            "implementado aqui — fora do escopo pedido."
        )
    out.append("")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m bropilot_core.scripts.compare_dedup",
        description="Compara retrieval antes/depois do dedup por source_file.",
    )
    parser.add_argument("--store", metavar="CAMINHO")
    parser.add_argument("-k", type=int, default=6)
    parser.add_argument("--output", required=True, metavar="CAMINHO")
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

    print("antes (dedup desligado):")
    antes = coletar(retriever, PERGUNTAS_EN, args.k, max_por_fonte=_SEM_DEDUP)
    print("depois (dedup default, max_por_fonte=1):")
    depois = coletar(retriever, PERGUNTAS_EN, args.k, max_por_fonte=1)

    destino = Path(args.output)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(gerar_relatorio(meta, args.k, antes, depois), encoding="utf-8")
    print(f"\nRelatório: {destino}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
