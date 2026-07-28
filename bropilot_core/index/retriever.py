"""Busca no índice vetorial — o coração do RAG state-aware.

O diferencial do BroPilot mora aqui. Um retriever burro embeda a pergunta e
devolve os k chunks mais próximos. Este devolve os k mais próximos PONDERADOS
pelo estado da party: se há um Monge Open Hand nível 5, `build_monk_openhand.md`
e os feats de nível 4-5 sobem no ranking mesmo que a pergunta não os mencione
literalmente. É o que transforma "chatbot de wiki" em "copiloto que enxerga o
jogo".
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import lancedb

from .build import _TABLE_NAME, STORE_DIR, assert_embedding_compatible

if TYPE_CHECKING:
    from ..llm import LLMProvider
    from ..serialize import PartyStateSignals


@dataclass
class RetrievedChunk:
    """Resultado de busca: o texto + de onde veio + quão relevante.

    `score` é o valor que ordena o resultado; `base_score` é a similaridade
    crua do kNN, antes de qualquer boost. Os dois são guardados separados de
    propósito: com só um número não dá para responder "por que este chunk
    subiu?" — comparar base_score com score, e ler boost_reasons, responde.
    """
    text: str
    source_file: str
    score: float                  # similaridade já ajustada pelos sinais da party
    base_score: float = 0.0       # similaridade crua (cosseno), pré-boost
    source_type: str = ""
    boost_reasons: list[str] = field(default_factory=list)


# Quanto o boost soma à similaridade de cosseno. Somar (em vez de multiplicar)
# porque a conta fica auditável: `score - base_score` é exatamente o boost, e
# `boost_reasons` diz de onde veio. Os pesos são pequenos de propósito — a
# semântica continua mandando; o estado da party desempata e promove, não
# atropela. Cada categoria entra no máximo uma vez, então o boost total é
# limitado a 0.30 por construção, sem precisar de um teto separado.
_BOOST_SOURCE_FILE_MATCH = 0.15   # classe/subclasse no NOME do arquivo: sinal forte
_BOOST_TEXT_MATCH = 0.05          # classe/subclasse no CORPO do chunk: sinal fraco
_SOURCE_TYPE_BOOST = {
    "build": 0.10,   # guia de build é o material mais acionável p/ min-max
    "wiki": 0.02,    # factual e confiável, mas genérico
    "steam": 0.0,
    "youtube": 0.0,
    "forum": 0.0,    # opinião/debate: sem penalidade, só sem promoção
}

# Com signals, busca-se um pool maior que k e o corte vem DEPOIS do boost.
# Sem isso o boost só reordenaria o top-k que o kNN já escolheu, e nunca
# conseguiria promover um chunk relevante que ficou em 12º — que é justamente
# o comportamento prometido ("sobe no ranking mesmo que a pergunta não o
# mencione literalmente").
#
# 20 e não 5 por medição, não por gosto: na base real, "como montar minha build
# de monge" deixa build_monk_openhand.md em 109º, e a similaridade é achatada
# (0.513 no 1º contra 0.427 no 109º — 0.086 de variação em 109 posições). Com
# pool=k*5=30 o boost nunca alcançaria o arquivo; com k*20=120 alcança, e o gap
# de 0.068 até o corte cabe folgado no boost.
#
# Cuidado ao subir mais: como a paisagem é plana, o boost (até 0.30) já supera
# toda a variação semântica do pool. Pool grande demais faz QUALQUER chunk que
# cite a classe da party ganhar de conteúdo realmente relevante à pergunta.
# Este é o principal parâmetro a recalibrar quando houver uso real.
#
# O piso existe porque amarrar o pool só a k dá comportamento surpreendente:
# medido, com k=4 (pool 80) o build_monk_openhand.md fica inalcançável e com
# k=6 (pool 120) ele vira o 1º resultado. Um k menor não deveria mudar QUAIS
# candidatos existem, só quantos são devolvidos.
_BOOST_POOL_FACTOR = 20
_BOOST_POOL_MIN = 150


def _term_variants(term: str) -> list[str]:
    """Variantes de busca para um sinal da party.

    Os sinais vêm em CamelCase do save ("OpenHand"), mas o texto dos guias
    escreve "Open Hand" e o nome do arquivo escreve "openhand". Sem gerar as
    duas formas, `build_monk_openhand.md` casaria e o corpo do chunto não.
    """
    lowered = term.strip().lower()
    if not lowered:
        return []
    spaced = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", term.strip()).lower()
    return list(dict.fromkeys([lowered, spaced]))


def _signal_terms(signals: "PartyStateSignals") -> list[str]:
    """Classes e subclasses da party, achatadas. Nível/raça ficam de fora de
    propósito: começar simples (ver docstring de _apply_state_boost)."""
    terms: list[str] = []
    for key in ("classes", "subclasses"):
        for value in signals.get(key, []) or []:
            terms.extend(_term_variants(value))
    return list(dict.fromkeys(terms))


def _distance_to_similarity(distance: float) -> float:
    """Converte a distância do LanceDB em similaridade de cosseno (maior=melhor).

    Duas propriedades do nosso setup tornam isto exato, e não uma heurística:
    o LanceDB com métrica l2 devolve a distância euclidiana AO QUADRADO, e os
    vetores do modelo de embedding são unitários. Então |a-b|² = 2 - 2·cos,
    ou seja cos = 1 - d/2. Verificado contra o produto escalar real dos
    vetores: erro < 1e-4. (A leitura ingênua "d é a L2, logo cos = 1 - d²/2"
    dá um número plausível mas errado — 0.618 onde o cosseno real é 0.563.)
    """
    return 1.0 - distance / 2.0


class Retriever:
    """Encapsula o vector store. Todo acesso ao LanceDB passa por aqui, para que
    trocar de store seja local a esta classe (ver __init__ do subpacote index).
    """

    def __init__(self, llm: "LLMProvider", store_dir: Path = STORE_DIR) -> None:
        """Guarda o provider (para embedar a query) e abre o índice em modo
        leitura. Falha cedo com mensagem útil se o índice não existe ("rode
        python -m bropilot_core.index.build primeiro").

        OBRIGATÓRIO ao implementar: chamar `assert_embedding_compatible(llm,
        store_dir)` (de .build) antes de servir qualquer query. Ela compara o
        modelo de embedding gravado no manifest do índice com o do provider
        que vetorizará a query, e falha alto se divergirem. Sem essa trava,
        indexar com um modelo e consultar com outro não dá erro — só devolve
        os chunks errados, que é o modo de falha mais caro do RAG porque
        parece que está funcionando.
        """
        self._llm = llm
        self._store_dir = Path(store_dir)

        if not self._store_dir.exists():
            raise RuntimeError(
                f"Índice não encontrado em {self._store_dir}. "
                "Construa a base antes de consultar:\n"
                "  python -m bropilot_core.index.build"
            )

        db = lancedb.connect(str(self._store_dir))
        if _TABLE_NAME not in set(db.list_tables().tables):
            raise RuntimeError(
                f"O diretório {self._store_dir} existe mas não contém a tabela "
                f"'{_TABLE_NAME}'. Construa a base antes de consultar:\n"
                "  python -m bropilot_core.index.build"
            )

        # Antes de servir qualquer query: o índice e este provider precisam
        # falar o mesmo espaço vetorial (ver build.assert_embedding_compatible).
        assert_embedding_compatible(llm, self._store_dir)

        self._table = db.open_table(_TABLE_NAME)

    def _to_chunk(self, row: dict) -> RetrievedChunk:
        similarity = _distance_to_similarity(row["_distance"])
        # score nasce igual a base_score; só o boost os separa.
        return RetrievedChunk(
            text=row["text"],
            source_file=row["source_file"],
            source_type=row["source_type"],
            score=similarity,
            base_score=similarity,
        )

    def search(
        self,
        query: str,
        *,
        signals: "PartyStateSignals | None" = None,
        k: int = 6,
    ) -> list[RetrievedChunk]:
        """Busca os k chunks mais relevantes para a query.

        Sem `signals`: kNN vetorial puro. Com `signals`: aplica boost/filtro
        pelas classes, subclasses e nível da party (state-aware). k pequeno de
        propósito — o prompt final tem que caber folgado no contexto local.
        """
        vector = self._llm.embed([query])[0]
        limit = max(k * _BOOST_POOL_FACTOR, _BOOST_POOL_MIN) if signals else k
        rows = self._table.search(vector).limit(limit).to_arrow().to_pylist()
        hits = [self._to_chunk(row) for row in rows]

        if signals:
            hits = self._apply_state_boost(hits, signals)

        return hits[:k]

    def _apply_state_boost(
        self, hits: list[RetrievedChunk], signals: "PartyStateSignals"
    ) -> list[RetrievedChunk]:
        """Reordena os hits crus dando peso aos que casam com o estado da party.

        Onde a lógica de RPG vira código: mapear classe/subclasse -> arquivos e
        tópicos relevantes. Começar simples (match por nome de arquivo e
        source_type) e sofisticar depois.

        Versão simples de propósito: casa classe/subclasse contra o nome do
        arquivo e o corpo do chunk, e soma um peso por source_type. Nível e
        raça dos signals ainda NÃO entram — ficam para quando houver material
        indexado que os justifique.

        Não muta os hits recebidos: devolve cópias com score/boost_reasons
        preenchidos, para que base_score continue sendo a similaridade crua e
        a comparação entre os dois siga possível.
        """
        terms = _signal_terms(signals)
        boosted: list[RetrievedChunk] = []

        for hit in hits:
            bonus = 0.0
            reasons: list[str] = []

            filename = re.sub(r"[^a-z0-9]", "", hit.source_file.lower())
            matched_in_name = [t for t in terms if re.sub(r"[^a-z0-9]", "", t) in filename]
            if matched_in_name:
                bonus += _BOOST_SOURCE_FILE_MATCH
                reasons.append(
                    f"arquivo casa com {', '.join(matched_in_name)} "
                    f"(+{_BOOST_SOURCE_FILE_MATCH:.2f})"
                )

            lowered_text = hit.text.lower()
            matched_in_text = [
                t for t in terms if re.search(rf"\b{re.escape(t)}\b", lowered_text)
            ]
            if matched_in_text:
                bonus += _BOOST_TEXT_MATCH
                reasons.append(
                    f"texto cita {', '.join(matched_in_text)} "
                    f"(+{_BOOST_TEXT_MATCH:.2f})"
                )

            type_bonus = _SOURCE_TYPE_BOOST.get(hit.source_type, 0.0)
            if type_bonus:
                bonus += type_bonus
                reasons.append(f"source_type={hit.source_type} (+{type_bonus:.2f})")

            boosted.append(
                RetrievedChunk(
                    text=hit.text,
                    source_file=hit.source_file,
                    score=hit.base_score + bonus,
                    base_score=hit.base_score,
                    source_type=hit.source_type,
                    boost_reasons=reasons,
                )
            )

        boosted.sort(key=lambda c: c.score, reverse=True)
        return boosted
