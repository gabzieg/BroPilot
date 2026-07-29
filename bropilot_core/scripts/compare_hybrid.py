"""Varre o PESO da fusão híbrida (vetorial ↔ BM25) e mede a bateria EN em
cada valor, para escolher o peso pelo dado em vez do default.

Contexto: `bropilot_core/DECISION_hybrid_search.md`. Três experimentos
anteriores falsearam diluição, idioma e duplicata, e sobrou uma causa —
similaridade densa não discrimina em corpus mono-domínio. A híbrida adiciona o
sinal lexical que faltava; o peso entre as duas pernas é o único botão novo, e
a decisão manda calibrá-lo com a bateria (§ "Reranker").

O "antes" NÃO precisa de checkout do código anterior: com peso vetorial = 1.0
o lado FTS entra com coeficiente zero e a fusão devolve exatamente a ordem do
kNN puro. Ou seja, `peso=1.0` reproduz o baseline pré-híbrida pelo MESMO
caminho de código — mesma manobra que `compare_dedup.py` fez com
`max_por_fonte` altíssimo, e pela mesma razão: duas condições que divergem por
código diferente não são comparáveis.

Métricas (as quatro que a decisão listou como meta):
- recall@k da wiki em `c1` (regra factual) — o teste decisivo;
- Jaccard entre as paráfrases `d1`×`d2`×`d3` (estabilidade);
- recall@k de Monge nas 5 perguntas de monge (acurácia);
- duplicatas no top-k (não pode regredir de 0).

Uso:
    python -m bropilot_core.scripts.compare_hybrid --output relatorio.md
    python -m bropilot_core.scripts.compare_hybrid --output r.md --pesos 0,0.3,0.5,0.7,1
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

# 1.0 primeiro e sempre: é a coluna "antes" (vetorial pura). Os demais são a
# varredura que a decisão pediu.
_PESO_BASELINE = 1.0
_PESOS_PADRAO = [1.0, 0.7, 0.5, 0.3, 0.0]

_PARES_PARAFRASE = [("d1", "d2"), ("d1", "d3"), ("d2", "d3")]
_MONGE_IDS = ["a1", "d1", "d2", "d3", "e1"]


def _tabela(cabecalho: list[str], linhas: list[list]) -> list[str]:
    out = ["| " + " | ".join(cabecalho) + " |",
           "|" + "|".join("---" for _ in cabecalho) + "|"]
    out += ["| " + " | ".join(str(c) for c in linha) + " |" for linha in linhas]
    return out


def _media(valores: list[float]) -> float:
    return sum(valores) / len(valores) if valores else 0.0


def _rotulo(peso: float) -> str:
    if peso == _PESO_BASELINE:
        return "**1.00** (antes: vetorial pura)"
    if peso == 0.0:
        return "0.00 (BM25 puro)"
    return f"{peso:.2f}"


def _jaccard_medio(hits: dict[str, list[dict]]) -> float:
    return _media([
        _jaccard(_arquivos(hits[a]), _arquivos(hits[b]))
        for a, b in _PARES_PARAFRASE
    ])


def _monge_acertos(hits: dict[str, list[dict]]) -> int:
    return sum(_recall(hits[pid], "monk") for pid in _MONGE_IDS)


def _duplicatas_total(hits: dict[str, list[dict]]) -> int:
    return sum(_duplicatas(hits[p["id"]]) for p in PERGUNTAS_EN)


def gerar_relatorio(
    meta: dict, k: int, pesos: list[float], por_peso: dict[float, dict]
) -> str:
    out = [
        "# Busca híbrida (BM25 + vetorial) — varredura do peso",
        "",
        f"Gerado em {datetime.now():%Y-%m-%d %H:%M:%S}. k={k}. Bateria EN "
        "(`PERGUNTAS_EN` de `eval_rag.py`), só retrieval, `signals=None`.",
        "",
        f"- Índice: **{meta['chunks']} chunks** de {meta['arquivos']} arquivos",
        f"- Embeddings: `{meta['embed_model']}` (dim {meta['embed_dim']})",
        f"- FTS: `{meta.get('fts')}`",
        "- Peso = fração VETORIAL da fusão linear; o BM25 fica com `1 - peso`. "
        "`peso=1.00` é o baseline pré-híbrida reproduzido pelo mesmo código "
        "(o lado lexical entra com coeficiente zero).",
        "",
        "---",
        "",
        "## Tabela comparativa — as quatro metas da decisão",
        "",
    ]

    linhas = []
    for peso in pesos:
        hits = por_peso[peso]
        wiki = _recall(hits["c1"], "wiki")
        linhas.append([
            _rotulo(peso),
            "**sim**" if wiki else "não",
            f"{_jaccard_medio(hits):.2f}",
            f"{_monge_acertos(hits)}/{len(_MONGE_IDS)}",
            _duplicatas_total(hits),
        ])
    out += _tabela(
        ["peso vetorial", "recall wiki `c1`", "Jaccard paráfrases",
         "recall Monge", "duplicatas top-6"],
        linhas,
    )
    out += [
        "",
        "> Metas da decisão: wiki em `c1` **acerta** (era 0/1); Jaccard **> "
        "0.5** (era 0.34); Monge **5/5** (era 4/5); duplicatas **0** (não "
        "regredir).",
        "",
    ]

    # O trade-off só aparece lendo duas colunas juntas; deixar explícito
    # evita que a escolha do peso vire preferência estética.
    pesos_wiki = [p for p in pesos if _recall(por_peso[p]["c1"], "wiki")]
    if pesos_wiki:
        monge_max_wiki = max(_monge_acertos(por_peso[p]) for p in pesos_wiki)
        monge_sem_wiki = max(
            (_monge_acertos(por_peso[p]) for p in pesos if p not in pesos_wiki),
            default=0,
        )
        if monge_max_wiki < monge_sem_wiki:
            out += [
                f"> ⚠️ **Trade-off, não almoço grátis.** Nenhum peso varrido "
                f"acerta a wiki em `c1` E mantém o recall de Monge: o melhor "
                f"Monge entre os pesos que acertam a wiki é "
                f"{monge_max_wiki}/{len(_MONGE_IDS)}, contra "
                f"{monge_sem_wiki}/{len(_MONGE_IDS)} entre os que não "
                "acertam. Escolher o peso é escolher qual dos dois casos "
                "importa mais — ver o detalhe por pergunta abaixo para saber "
                "QUAL pergunta de Monge é perdida e por quê.",
                "",
            ]

    # Detalhe por pergunta do recall de monge — a média esconde QUAL pergunta
    # falha, e é sempre a mesma que decide se 4/5 vira 5/5.
    out += ["## Recall@k de Monge, pergunta a pergunta", ""]
    linhas = []
    for pid in _MONGE_IDS:
        linhas.append(
            [f"`{pid}`"]
            + ["sim" if _recall(por_peso[p][pid], "monk") else "**não**"
               for p in pesos]
        )
    out += _tabela(["pergunta"] + [f"{p:.2f}" for p in pesos], linhas)

    out += ["", "## Jaccard por par de paráfrases", ""]
    linhas = []
    for a, b in _PARES_PARAFRASE:
        linhas.append(
            [f"`{a}`×`{b}`"]
            + [f"{_jaccard(_arquivos(por_peso[p][a]), _arquivos(por_peso[p][b])):.2f}"
               for p in pesos]
        )
    linhas.append(["**média**"]
                  + [f"**{_jaccard_medio(por_peso[p]):.2f}**" for p in pesos])
    out += _tabela(["par"] + [f"{p:.2f}" for p in pesos], linhas)

    out += ["", f"## Spread no top-{k} (referência)", "",
            "Distância entre o maior e o menor score do top-k. Sobe com a "
            "híbrida porque a fusão normaliza os scores no pool — não é "
            "comparável em valor absoluto com os relatórios pré-híbrida, só "
            "entre pesos.", ""]
    linhas = [["**média**"]
              + [f"{_media([_spread(por_peso[p][q['id']]) for q in PERGUNTAS_EN]):.3f}"
                 for p in pesos]]
    out += _tabela(["métrica"] + [f"{p:.2f}" for p in pesos], linhas)

    # A pergunta que motivou a decisão inteira, com os arquivos na cara.
    out += ["", "---", "", "## `c1` em detalhe — a pergunta que motivou a decisão", "",
            "*\"how many Superiority Dice does a Battle Master have at level "
            "5?\"* — ground truth (herdado de `compare_language.py`): algum "
            "chunk com `source_type=wiki` no top-k.", "",
            "> **Limite deste ground truth, medido em 29/07:** a base NÃO tem "
            "a página de wiki do Battle Master. `grep -il superiority` em "
            "`02_trusted/` acha só `resting.md` (que cita Superiority Dice "
            "como recurso recuperado em descanso curto) e `feats.md` (que "
            "cita a feat Martial Adept). Nenhum dos dois responde \"quantos "
            "dados no nível 5\". Ou seja: o recall@k da wiki mede se a "
            "híbrida **puxa material de wiki com o termo literal** — que é "
            "exatamente o mecanismo que a decisão previu — mas acertar aqui "
            "NÃO significa que a resposta factual passou a estar no contexto. "
            "Para isso falta conteúdo na base, não retrieval.", ""]
    for peso in pesos:
        arquivos = ", ".join(
            f"`{h['source_file']}`({h['source_type']})" for h in por_peso[peso]["c1"]
        )
        out.append(f"- peso {peso:.2f}: {arquivos or '—'}")

    out += ["", "---", "", "## Veredito", ""]
    baseline = por_peso.get(_PESO_BASELINE)
    ganhou_wiki = [
        p for p in pesos
        if p != _PESO_BASELINE and _recall(por_peso[p]["c1"], "wiki")
    ]
    if baseline is not None and _recall(baseline["c1"], "wiki"):
        out.append(
            "A wiki já aparecia no top-k de `c1` no baseline vetorial puro — "
            "este índice não reproduz a condição que motivou a decisão, e a "
            "comparação da hipótese lexical fica inconclusiva."
        )
    elif ganhou_wiki:
        out.append(
            "**Hipótese lexical CONFIRMADA** para `c1`: a wiki entra no "
            f"top-{k} com peso(s) "
            + ", ".join(f"{p:.2f}" for p in ganhou_wiki)
            + " e continuava fora com o vetorial puro (peso 1.00)."
        )
    else:
        out.append(
            "**Hipótese lexical NÃO CONFIRMADA** para `c1`: em nenhum peso "
            f"varrido a wiki entrou no top-{k}. O sinal lexical não foi o que "
            "faltava para esta pergunta — o problema é outro (candidato "
            "imediato: verificar se a base sequer contém a página de wiki que "
            "responde a regra). Não forçar com cota por `source_type` nem "
            "outro band-aid: a decisão descartou isso explicitamente."
        )
    out.append("")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m bropilot_core.scripts.compare_hybrid",
        description="Varre o peso vetorial↔FTS da busca híbrida e mede a "
                    "bateria EN em cada valor.",
    )
    parser.add_argument("--store", metavar="CAMINHO")
    parser.add_argument("-k", type=int, default=6)
    parser.add_argument("--output", required=True, metavar="CAMINHO")
    parser.add_argument(
        "--pesos",
        metavar="LISTA",
        help="pesos vetoriais separados por vírgula (default: "
             + ",".join(str(p) for p in _PESOS_PADRAO) + ").",
    )
    args = parser.parse_args(argv)

    pesos = _PESOS_PADRAO
    if args.pesos:
        try:
            pesos = [float(p.strip()) for p in args.pesos.split(",") if p.strip()]
        except ValueError:
            print("erro: --pesos aceita só números separados por vírgula.",
                  file=sys.stderr)
            return 1
        if not all(0.0 <= p <= 1.0 for p in pesos):
            print("erro: todo peso precisa estar em [0, 1].", file=sys.stderr)
            return 1

    store_dir = Path(args.store) if args.store else STORE_DIR

    try:
        provider = create_provider()
        provider.health_check()
        meta = _metadados_indice(store_dir)
        # Um Retriever por peso: o peso é do construtor (a assinatura de
        # search é contrato e não muda), e abrir o índice de novo é barato.
        retrievers = {
            p: Retriever(provider, store_dir, vector_weight=p) for p in pesos
        }
    except (RuntimeError, ValueError) as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return 1

    if meta["aviso"]:
        print(f"\n  ⚠️  ÍNDICE DESATUALIZADO: {meta['aviso']}\n", file=sys.stderr)

    import json

    manifest = json.loads((store_dir / "manifest.json").read_text(encoding="utf-8"))
    meta["fts"] = manifest.get("fts")

    por_peso = {}
    for p in pesos:
        print(f"peso vetorial {p:.2f} (FTS {1 - p:.2f}):")
        por_peso[p] = coletar(retrievers[p], PERGUNTAS_EN, args.k)

    destino = Path(args.output)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(
        gerar_relatorio(meta, args.k, pesos, por_peso), encoding="utf-8"
    )
    print(f"\nRelatório: {destino}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
