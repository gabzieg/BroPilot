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


def coletar(store_dir: Path, k: int, signals=None, rotulo: str | None = None) -> dict:
    """Roda só a busca para cada pergunta e devolve os hits por id.

    `signals` liga o boost state-aware — é o que permite comparar a MESMA base
    com e sem o estado da party, isolando o efeito do boost do efeito do corpus.
    """
    provider = create_provider()
    retriever = Retriever(provider, store_dir)
    manifest = json.loads((store_dir / "manifest.json").read_text(encoding="utf-8"))
    tabela = lancedb.connect(str(store_dir)).open_table("chunks")

    hits = {}
    for pergunta in PERGUNTAS:
        resultado = retriever.search(pergunta["texto"], signals=signals, k=k)
        hits[pergunta["id"]] = [
            {"source_file": h.source_file, "score": h.score} for h in resultado
        ]
        print(f"  {pergunta['id']}: {len(resultado)} hits")

    return {
        "rotulo": rotulo or str(store_dir),
        "signals": bool(signals),
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


def _tabela(cabecalho: list[str], linhas: list[list[str]]) -> list[str]:
    out = ["| " + " | ".join(cabecalho) + " |",
           "|" + "|".join("---" for _ in cabecalho) + "|"]
    out += ["| " + " | ".join(str(c) for c in linha) + " |" for linha in linhas]
    return out


def comparar(condicoes: list[dict], k: int) -> str:
    nomes = [c["rotulo"] for c in condicoes]
    out = [
        "# Comparação de retrieval entre condições",
        "",
        f"Gerado em {datetime.now():%Y-%m-%d %H:%M:%S}. k={k}.",
        "",
        "> Métricas **só de retrieval** (sem geração). A qualidade das RESPOSTAS "
        "não entra aqui: o corpus denso não tem o conteúdo estratégico das "
        "transcrições, então piora de resposta não invalida o experimento — o "
        "que está sob teste é estabilidade e precisão de BUSCA.",
        "",
    ]
    out += _tabela(
        [""] + nomes,
        [
            ["store"] + [f"`{Path(c['store']).name}`" for c in condicoes],
            ["arquivos"] + [c["arquivos"] for c in condicoes],
            ["chunks"] + [c["chunks"] for c in condicoes],
            ["source_types"] + [str(c["source_types"] or "todos") for c in condicoes],
            ["signals (boost)"] + ["sim" if c["signals"] else "não" for c in condicoes],
        ],
    )

    out += ["", "## 1. Estabilidade entre paráfrases (Jaccard dos `source_file`)", "",
            "As três formulações da mesma intenção deveriam recuperar material "
            "parecido. Meta do ADR: **> 0.6**.", ""]
    linhas, medias = [], [[] for _ in condicoes]
    for a, b in _PARES_PARAFRASE:
        valores = []
        for i, c in enumerate(condicoes):
            j = _jaccard(_arquivos(c["hits"][a]), _arquivos(c["hits"][b]))
            medias[i].append(j)
            valores.append(f"{j:.2f}")
        linhas.append([f"`{a}` × `{b}`"] + valores)
    linhas.append(["**média**"] + [f"**{sum(m)/len(m):.2f}**" for m in medias])
    out += _tabela(["par"] + nomes, linhas)

    out += ["", "## 2. Cross-lingual (PT × EN da mesma pergunta)", "",
            "Meta do ADR: **> 0.7**.", ""]
    a, b = _PAR_CROSSLINGUAL
    out += _tabela(
        ["par"] + nomes,
        [[f"`{a}` × `{b}`"] + [
            f"{_jaccard(_arquivos(c['hits'][a]), _arquivos(c['hits'][b])):.2f}"
            for c in condicoes]],
    )

    out += ["", f"## 3. Spread de score no top-{k}", "",
            "Diferença entre o melhor e o pior score da busca. Perto de zero = "
            "candidatos empatados, ranking pouco decidível. Maior é melhor.",
            "", "> O boost muda a ESCALA do score (soma até +0.30), então o "
            "spread da coluna com signals não é comparável às outras em valor "
            "absoluto — só entre si.", ""]
    linhas, medias = [], [[] for _ in condicoes]
    for pergunta in PERGUNTAS:
        pid = pergunta["id"]
        valores = []
        for i, c in enumerate(condicoes):
            s = _spread(c["hits"][pid])
            medias[i].append(s)
            valores.append(f"{s:.3f}")
        linhas.append([f"`{pid}`"] + valores)
    linhas.append(["**média**"] + [f"**{sum(m)/len(m):.3f}**" for m in medias])
    out += _tabela(["pergunta"] + nomes, linhas)

    out += ["", f"## 4. Duplicata de documento dentro do top-{k}", "",
            "Hits que repetem um documento já presente. Cada duplicata é um "
            "slot gasto sem trazer fonte nova.", ""]
    linhas, totais = [], [0] * len(condicoes)
    for pergunta in PERGUNTAS:
        pid = pergunta["id"]
        valores = []
        for i, c in enumerate(condicoes):
            d = _duplicatas(c["hits"][pid])
            totais[i] += d
            valores.append(d)
        linhas.append([f"`{pid}`"] + valores)
    linhas.append(["**total**"] + [f"**{t}**" for t in totais])
    out += _tabela(["pergunta"] + nomes, linhas)

    out += ["", "## 5. `build_monk_openhand.md` no top-k", "",
            "> **NÃO CONCLUSIVO para o corpus denso.** Lá esse arquivo é 1 de "
            "27; no baseline é 1 de 151. Aparecer é consequência aritmética do "
            "corpus menor, não prova de retrieval melhor. Já na coluna com "
            "signals o índice é o mesmo do baseline, então ali a diferença SIM "
            "é atribuível ao boost.", ""]
    alvo = "build_monk_openhand.md"
    out += _tabela(
        ["pergunta"] + nomes,
        [[f"`{pid}`"] + ["sim" if alvo in _arquivos(c["hits"][pid]) else "não"
                         for c in condicoes]
         for pid in ("a1", "d1", "d2", "d3", "e1")],
    )
    out.append("")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m bropilot_core.scripts.compare_retrieval",
        description="Compara métricas de retrieval entre condições.",
    )
    parser.add_argument("--baseline", default=str(STORE_DIR))
    parser.add_argument("--experimento", help="segundo índice (ex.: corpus denso).")
    parser.add_argument("--com-save", action="store_true",
                        help="adiciona uma condição: baseline + boost state-aware.")
    parser.add_argument("--output", required=True)
    parser.add_argument("-k", type=int, default=6)
    args = parser.parse_args(argv)

    condicoes = []
    try:
        print("baseline (sem save):")
        condicoes.append(coletar(Path(args.baseline), args.k,
                                 rotulo="baseline (sem save)"))
        if args.experimento:
            print("experimento denso:")
            condicoes.append(coletar(Path(args.experimento), args.k,
                                     rotulo="denso (wiki+build)"))
        if args.com_save:
            from ..cli import carregar_save
            from ..serialize import extract_signals

            ctx, aviso = carregar_save()
            print(aviso)
            if ctx is None:
                print("erro: --com-save pedido mas nenhum save carregado.",
                      file=sys.stderr)
                return 1
            print("baseline + save:")
            condicoes.append(coletar(Path(args.baseline), args.k,
                                     signals=extract_signals(ctx),
                                     rotulo="baseline + save (boost)"))
    except RuntimeError as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return 1

    destino = Path(args.output)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(comparar(condicoes, args.k), encoding="utf-8")
    print(f"\nComparação: {destino}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
