"""Compara a QUALIDADE DE RETRIEVAL entre dois índices, nas mesmas perguntas.

Por que existe separado do eval_rag: as métricas que interessam aqui
(estabilidade entre paráfrases, cross-lingual, spread de score, duplicata no
top-k) dependem só da BUSCA, não da geração. Medi-las sem chamar o LLM torna a
comparação minutos em vez de horas — e elimina a variação da geração, que não é
o que está sob teste.

Uso:
    python -m bropilot_core.scripts.compare_retrieval \\
        --baseline bropilot_core/index/store \\
        --experimento bropilot_core/index/store_denso \\
        --output comparacao.md
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

import lancedb

from ..index.build import STORE_DIR
from ..index.retriever import Retriever
from ..llm import create_provider
from .eval_rag import PERGUNTAS, _jaccard

# Pares comparados nas métricas de estabilidade.
_PARES_PARAFRASE = [("d1", "d2"), ("d1", "d3"), ("d2", "d3")]
_PAR_CROSSLINGUAL = ("a1", "e1")


def coletar(store_dir: Path, k: int) -> dict:
    """Roda só a busca para cada pergunta e devolve os hits por id."""
    provider = create_provider()
    retriever = Retriever(provider, store_dir)
    manifest = json.loads((store_dir / "manifest.json").read_text(encoding="utf-8"))
    tabela = lancedb.connect(str(store_dir)).open_table("chunks")

    hits = {}
    for pergunta in PERGUNTAS:
        resultado = retriever.search(pergunta["texto"], k=k)
        hits[pergunta["id"]] = [
            {"source_file": h.source_file, "score": h.score} for h in resultado
        ]
        print(f"  {pergunta['id']}: {len(resultado)} hits")

    return {
        "store": str(store_dir),
        "chunks": tabela.count_rows(),
        "arquivos": len(manifest.get("files", {})),
        "source_types": manifest.get("source_types"),
        "hits": hits,
    }


def _arquivos(hits: list[dict]) -> set[str]:
    return {h["source_file"] for h in hits}


def _spread(hits: list[dict]) -> float:
    """Diferença entre o melhor e o pior score do top-k. Perto de zero = o
    ranking é praticamente um sorteio entre candidatos empatados."""
    if len(hits) < 2:
        return 0.0
    scores = [h["score"] for h in hits]
    return max(scores) - min(scores)


def _duplicatas(hits: list[dict]) -> int:
    """Quantos hits do top-k são repetição de um documento já presente."""
    contagem = Counter(h["source_file"] for h in hits)
    return sum(n - 1 for n in contagem.values() if n > 1)


def _linha_delta(valor_a: float, valor_b: float, casas: int = 3) -> str:
    delta = valor_b - valor_a
    seta = "↑" if delta > 0 else ("↓" if delta < 0 else "=")
    return f"{valor_a:.{casas}f} | {valor_b:.{casas}f} | {seta} {delta:+.{casas}f}"


def comparar(base: dict, exp: dict, k: int) -> str:
    out = [
        "# Comparação de retrieval — baseline vs experimento denso",
        "",
        f"Gerado em {datetime.now():%Y-%m-%d %H:%M:%S}. k={k}.",
        "",
        "> Métricas **só de retrieval** (sem geração): são as que respondem se a "
        "hipótese de diluição procede. A qualidade das RESPOSTAS não entra aqui "
        "— o corpus denso não tem o conteúdo estratégico das transcrições, "
        "então piora esperada de resposta não invalida o experimento.",
        "",
        "| | baseline | experimento |",
        "|---|---|---|",
        f"| store | `{base['store']}` | `{exp['store']}` |",
        f"| arquivos | {base['arquivos']} | {exp['arquivos']} |",
        f"| chunks | {base['chunks']} | {exp['chunks']} |",
        f"| source_types | {base['source_types'] or 'todos'} | {exp['source_types']} |",
        "",
        "## 1. Estabilidade entre paráfrases (Jaccard dos `source_file`)",
        "",
        "As três formulações da mesma intenção deveriam recuperar material "
        "parecido. Meta declarada no ADR: **> 0.6**.",
        "",
        "| par | baseline | experimento | delta |",
        "|---|---|---|---|",
    ]

    jac_base, jac_exp = [], []
    for a, b in _PARES_PARAFRASE:
        ja = _jaccard(_arquivos(base["hits"][a]), _arquivos(base["hits"][b]))
        je = _jaccard(_arquivos(exp["hits"][a]), _arquivos(exp["hits"][b]))
        jac_base.append(ja)
        jac_exp.append(je)
        out.append(f"| `{a}` × `{b}` | {_linha_delta(ja, je, 2)} |")
    media_base = sum(jac_base) / len(jac_base)
    media_exp = sum(jac_exp) / len(jac_exp)
    out.append(f"| **média** | {_linha_delta(media_base, media_exp, 2)} |")

    out += [
        "",
        "## 2. Cross-lingual (PT × EN da mesma pergunta)",
        "",
        "Meta declarada no ADR: **> 0.7**.",
        "",
        "| par | baseline | experimento | delta |",
        "|---|---|---|---|",
    ]
    a, b = _PAR_CROSSLINGUAL
    jb = _jaccard(_arquivos(base["hits"][a]), _arquivos(base["hits"][b]))
    je = _jaccard(_arquivos(exp["hits"][a]), _arquivos(exp["hits"][b]))
    out.append(f"| `{a}` × `{b}` | {_linha_delta(jb, je, 2)} |")

    out += [
        "",
        f"## 3. Spread de score no top-{k}",
        "",
        "Diferença entre o melhor e o pior score de cada busca. Spread perto de "
        "zero = candidatos empatados, ranking pouco decidível. Maior é melhor.",
        "",
        "| pergunta | baseline | experimento | delta |",
        "|---|---|---|---|",
    ]
    spreads_base, spreads_exp = [], []
    for pergunta in PERGUNTAS:
        pid = pergunta["id"]
        sb = _spread(base["hits"][pid])
        se = _spread(exp["hits"][pid])
        spreads_base.append(sb)
        spreads_exp.append(se)
        out.append(f"| `{pid}` | {_linha_delta(sb, se)} |")
    out.append(
        f"| **média** | "
        f"{_linha_delta(sum(spreads_base)/len(spreads_base), sum(spreads_exp)/len(spreads_exp))} |"
    )

    out += [
        "",
        f"## 4. Duplicata de documento dentro do top-{k}",
        "",
        "Hits que são outro pedaço de um documento já presente no top-k. "
        "Cada duplicata é um slot gasto sem trazer fonte nova.",
        "",
        "| pergunta | baseline | experimento |",
        "|---|---|---|",
    ]
    dup_base = dup_exp = 0
    for pergunta in PERGUNTAS:
        pid = pergunta["id"]
        db_, de_ = _duplicatas(base["hits"][pid]), _duplicatas(exp["hits"][pid])
        dup_base += db_
        dup_exp += de_
        out.append(f"| `{pid}` | {db_} | {de_} |")
    out.append(f"| **total** | **{dup_base}** | **{dup_exp}** |")

    out += [
        "",
        "## 5. `build_monk_openhand.md` no top-k",
        "",
        "> **NÃO CONCLUSIVO.** No experimento este arquivo é 1 de 27; no "
        "baseline era 1 de 151. Aparecer aqui é consequência aritmética do "
        "corpus menor, não prova de que o retrieval melhorou. Registrado só "
        "para constar.",
        "",
        "| pergunta | baseline | experimento |",
        "|---|---|---|",
    ]
    alvo = "build_monk_openhand.md"
    for pid in ("a1", "d1", "d2", "d3", "e1"):
        pb = "sim" if alvo in _arquivos(base["hits"][pid]) else "não"
        pe = "sim" if alvo in _arquivos(exp["hits"][pid]) else "não"
        out.append(f"| `{pid}` | {pb} | {pe} |")

    out.append("")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m bropilot_core.scripts.compare_retrieval",
        description="Compara métricas de retrieval entre dois índices.",
    )
    parser.add_argument("--baseline", default=str(STORE_DIR))
    parser.add_argument("--experimento", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("-k", type=int, default=6)
    args = parser.parse_args(argv)

    try:
        print(f"baseline    ({args.baseline}):")
        base = coletar(Path(args.baseline), args.k)
        print(f"experimento ({args.experimento}):")
        exp = coletar(Path(args.experimento), args.k)
    except RuntimeError as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return 1

    destino = Path(args.output)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(comparar(base, exp, args.k), encoding="utf-8")
    print(f"\nComparação: {destino}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
