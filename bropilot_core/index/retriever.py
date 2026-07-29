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
import pyarrow as pa
from lancedb.rerankers import Reranker

from .build import (
    _TABLE_NAME,
    STORE_DIR,
    assert_embedding_compatible,
    assert_fts_available,
)

if TYPE_CHECKING:
    from ..llm import LLMProvider
    from ..serialize import PartyStateSignals


@dataclass
class RetrievedChunk:
    """Resultado de busca: o texto + de onde veio + quão relevante.

    `score` é o valor que ordena o resultado; `base_score` é a relevância
    híbrida da busca, antes de qualquer boost, expressa em unidades de
    cosseno (ver `_rescale_to_cosine`). Os dois são guardados separados de
    propósito: com só um número não dá para responder "por que este chunk
    subiu?" — comparar base_score com score, e ler boost_reasons, responde.

    `vector_score` e `fts_score` abrem a caixa-preta um nível mais fundo: são
    as DUAS pernas que a fusão linear combinou para chegar em `base_score`
    (ver `_HybridLinearReranker`). Sem elas não dá para responder a pergunta
    que a calibração do peso exige — "este chunk entrou pelo sinal semântico
    ou pelo casamento literal de termo?". `fts_score` é None quando o chunk
    não apareceu no lado BM25 (e `vector_score`, quando não apareceu no kNN):
    None significa "esta perna não votou", que é diferente de "votou zero".
    """
    text: str
    source_file: str
    score: float                  # relevância já ajustada pelos sinais da party
    base_score: float = 0.0       # relevância híbrida crua, pré-boost
    source_type: str = ""
    boost_reasons: list[str] = field(default_factory=list)
    vector_score: float | None = None   # cosseno cru do lado vetorial
    fts_score: float | None = None      # BM25 cru do lado lexical


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

# Busca-se sempre um pool maior que k e o corte vem DEPOIS do boost e do
# dedup. Duas razões independentes exigem isso, não só uma:
#
# (1) boost: sem pool, o boost só reordenaria o top-k que o kNN já escolheu, e
# nunca conseguiria promover um chunk relevante que ficou em 12º — que é
# justamente o comportamento prometido ("sobe no ranking mesmo que a pergunta
# não o mencione literalmente").
#
# (2) dedup por source_file (ver `_dedup_por_fonte`): um documento longo pode
# ocupar vários dos k slots com chunks vizinhos — sem pool, deduplicar um
# resultado de tamanho k já cortado só encolhe a resposta (perde slots sem
# recuperar diversidade). Buscando um pool maior, o dedup tem candidato de
# SOBRA de outras fontes para preencher os slots que a duplicata liberou.
#
# Por isso o pool é buscado incondicionalmente — COM ou SEM signals — mesmo
# que só o motivo (2) valha na ausência de boost.
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

# Quantos chunks, no máximo, um mesmo source_file pode ocupar no resultado
# final. Default 1: um documento longo não deveria monopolizar o top-k com
# vizinhos redundantes enquanto outra fonte relevante fica de fora.
_DEFAULT_MAX_POR_FONTE = 1

# Peso do lado VETORIAL na fusão linear; o lado FTS fica com (1 - peso).
# Convenção idêntica à do `LinearCombinationReranker` do LanceDB, para não
# inverter o significado do número em relação à documentação deles.
#
# NÃO é para ficar hardcodado neste valor: é o botão que a decisão manda
# calibrar com a bateria (`compare_hybrid.py` varre 0.3/0.5/0.7 e mede). O
# default abaixo é o que a varredura escolheu — ver
# `bropilot_core/eval/compare_hybrid_20260729.md`.
_DEFAULT_VECTOR_WEIGHT = 0.5


class _HybridLinearReranker(Reranker):
    """Fusão linear vetorial↔FTS: `w · vetorial + (1-w) · lexical`.

    Existe porque o `LinearCombinationReranker` do LanceDB 0.27.1 está com o
    sinal INVERTIDO e ordena do pior para o melhor. Medido, não suposto: numa
    tabela de 5 linhas, com `weight=1.0` (100% vetorial, zero FTS) ele colocou
    em 1º o chunk de MAIOR distância (4.0) e em último o de distância 0.0. A
    causa está em `_combine_score`, que faz `1 - (w·vec + (1-w)·fts)` sobre
    um `vec` que a linha de cima já converteu de distância para relevância —
    a inversão é aplicada duas vezes de um lado e uma do outro.
    """

    def __init__(self, weight: float = _DEFAULT_VECTOR_WEIGHT) -> None:
        if not 0.0 <= weight <= 1.0:
            raise ValueError(f"peso vetorial precisa estar em [0, 1], veio {weight}")
        # "all": preserva `_distance` e `_score` no resultado, que é o que
        # alimenta vector_score/fts_score no rastro de depuração. Com
        # "relevance" o LanceDB derruba as duas colunas e a fusão vira uma
        # caixa-preta de um número só.
        super().__init__("all")
        self.weight = weight

    def rerank_hybrid(self, query, vector_results, fts_results):
        """Recebe os dois lados JÁ normalizados pelo LanceDB em [0, 1]:
        `_distance` com 0 = mais perto, `_score` (BM25) com 1 = mais
        relevante. Devolve `_relevance_score` também em [0, 1], 1 = melhor.

        Chunk ausente de um dos lados não vota nele — entra com 0.0 naquela
        perna, e não com um valor de preenchimento arbitrário. É o que faz
        `weight=1.0` reproduzir exatamente o ranking vetorial puro (o baseline
        pré-híbrida) e `weight=0.0`, o BM25 puro.

        Herdada do LanceDB, uma degenerescência que vale conhecer: a
        normalização min-max acontece ANTES daqui, dentro do pool devolvido.
        Logo o pior casamento lexical do pool sempre normaliza para 0 — e se
        só UM documento casar o termo, ele normaliza para 0 e não ganha nada
        do lado FTS. Não morde na base real (uma query de regra casa dezenas
        de chunks), mas explica por que um teste com um único casamento
        lexical não veria promoção nenhuma.
        """
        combinados: dict[int, dict] = {}
        for linha in vector_results.to_pylist():
            combinados[linha["_rowid"]] = dict(linha)
        for linha in fts_results.to_pylist():
            existente = combinados.get(linha["_rowid"])
            if existente is None:
                combinados[linha["_rowid"]] = dict(linha)
            else:
                existente["_score"] = linha["_score"]

        for linha in combinados.values():
            distancia = linha.get("_distance")
            vetorial = 1.0 - distancia if distancia is not None else 0.0
            lexical = linha.get("_score") or 0.0
            linha["_relevance_score"] = (
                self.weight * vetorial + (1.0 - self.weight) * lexical
            )

        schema = pa.unify_schemas([
            vector_results.schema,
            fts_results.schema,
            pa.schema([pa.field("_relevance_score", pa.float32())]),
        ])
        return pa.Table.from_pylist(
            list(combinados.values()), schema=schema
        ).sort_by([("_relevance_score", "descending")])


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


def _rescale_to_cosine(hits: list["RetrievedChunk"]) -> list["RetrievedChunk"]:
    """Traz a relevância híbrida de volta para a ESCALA do cosseno do pool,
    preservando a ordem.

    Por que isto precisa existir: o boost state-aware soma constantes
    calibradas em unidades de cosseno (`_BOOST_SOURCE_FILE_MATCH` = 0.15 etc.)
    sobre uma paisagem que é medidamente PLANA — 0.086 de variação em 109
    posições, ver `_BOOST_POOL_FACTOR`. O LanceDB normaliza os scores do pool
    em [0, 1] antes de fundir, o que estica essa variação em ~10x. Sem
    desfazer o esticamento, a mesma constante de boost passaria a valer uma
    fração do que valia e o retrieval state-aware — o diferencial do produto —
    enfraqueceria em silêncio, sem uma linha do boost ter sido tocada.

    A volta é exata, não aproximada: a normalização do LanceDB é afim, e
    cosseno = 1 - distância/2 também é afim, então mapear a relevância de
    volta ao intervalo [menor, maior] cosseno do pool desfaz a composição.
    Consequência verificável: com `vector_weight=1.0` (FTS com coeficiente
    zero) `base_score` volta a ser exatamente a similaridade de cosseno de
    antes da híbrida — o mesmo vale sempre que o BM25 não casar nada.

    Chunk que só o BM25 achou não tem cosseno; ele entra na ordenação pelo
    score fundido e cai dentro do intervalo como qualquer outro.
    """
    cossenos = [h.vector_score for h in hits if h.vector_score is not None]
    if len(hits) < 2 or not cossenos:
        return hits

    cos_min, cos_max = min(cossenos), max(cossenos)
    rel = [h.base_score for h in hits]
    rel_min, rel_max = min(rel), max(rel)
    if rel_max == rel_min:
        return hits

    fator = (cos_max - cos_min) / (rel_max - rel_min)
    for hit in hits:
        hit.base_score = cos_min + (hit.base_score - rel_min) * fator
        hit.score = hit.base_score
    return hits


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

    def __init__(
        self,
        llm: "LLMProvider",
        store_dir: Path = STORE_DIR,
        *,
        vector_weight: float = _DEFAULT_VECTOR_WEIGHT,
    ) -> None:
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

        `vector_weight` é o peso do lado vetorial na fusão híbrida (o FTS
        fica com `1 - vector_weight`). Mora no construtor, e não em `search`,
        porque a assinatura de `search` é contrato público e porque o peso é
        propriedade da INSTALAÇÃO (calibrada uma vez contra a base), não da
        pergunta. Quem varre a calibração instancia um Retriever por peso.
        """
        self._llm = llm
        self._store_dir = Path(store_dir)
        self._reranker = _HybridLinearReranker(vector_weight)
        self.vector_weight = vector_weight

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

        # Segunda trava, mesma família da de cima: sem índice FTS o LanceDB
        # aceita a query híbrida e simplesmente devolve o lado lexical vazio,
        # degradando para vetorial pura em silêncio. Ver
        # build.assert_fts_available.
        assert_fts_available(self._table, self._store_dir)

    def _to_chunk(self, row: dict) -> RetrievedChunk:
        # base_score é a relevância FUNDIDA (0-1, 1 = melhor) — é ela que
        # ordena o pool, então é ela que o boost soma. As duas pernas vão
        # junto, cruas, só para auditoria: `_distance` vira cosseno, `_score`
        # é o BM25 como o LanceDB devolveu.
        distancia = row.get("_distance")
        bm25 = row.get("_score")
        relevancia = float(row["_relevance_score"])
        # score nasce igual a base_score; só o boost os separa.
        return RetrievedChunk(
            text=row["text"],
            source_file=row["source_file"],
            source_type=row["source_type"],
            score=relevancia,
            base_score=relevancia,
            vector_score=(
                None if distancia is None else _distance_to_similarity(distancia)
            ),
            fts_score=None if bm25 is None else float(bm25),
        )

    def search(
        self,
        query: str,
        *,
        signals: "PartyStateSignals | None" = None,
        k: int = 6,
        max_por_fonte: int = _DEFAULT_MAX_POR_FONTE,
    ) -> list[RetrievedChunk]:
        """Busca os k chunks mais relevantes para a query.

        O pool vem de busca HÍBRIDA: o mesmo texto da pergunta vai para o kNN
        vetorial (embedado) e para o BM25 (literal), e a fusão linear
        (`_HybridLinearReranker`, peso em `vector_weight`) combina os dois
        rankings. É a única coisa que a híbrida mudou — o resto da montagem do
        top-k abaixo é idêntico ao da busca vetorial pura.

        Sem `signals`: só a relevância híbrida ordena. Com `signals`: aplica
        boost/filtro pelas classes, subclasses e nível da party (state-aware).
        k pequeno de propósito — o prompt final tem que caber folgado no
        contexto local.

        Sempre busca um POOL maior que k (ver `_BOOST_POOL_FACTOR`) e corta
        para k só no fim, DEPOIS do boost e do dedup por `source_file` — nessa
        ordem, porque é o score final (pós-boost) que decide qual chunk de um
        documento repetido sobrevive. Se sobrarem menos que k fontes distintas
        no pool, o resultado sai menor que k: nunca reinsere duplicata só para
        completar a contagem.
        """
        vector = self._llm.embed([query])[0]
        limit = max(k * _BOOST_POOL_FACTOR, _BOOST_POOL_MIN)
        # `limit` vale para CADA perna (o LanceDB o repassa ao kNN e ao BM25)
        # e também para o corte do resultado fundido — o pool efetivo é a
        # união dos dois topos, truncada em `limit`.
        rows = (
            self._table.search(query_type="hybrid")
            .vector(vector)
            .text(query)
            .rerank(self._reranker)
            .limit(limit)
            .to_arrow()
            .to_pylist()
        )
        # A ordem já é a da fusão; isto só recoloca o score na escala em que
        # as constantes do boost foram calibradas (ver `_rescale_to_cosine`).
        hits = _rescale_to_cosine([self._to_chunk(row) for row in rows])

        if signals:
            hits = self._apply_state_boost(hits, signals)

        hits = self._dedup_por_fonte(hits, max_por_fonte)
        return hits[:k]

    def _dedup_por_fonte(
        self, hits: list[RetrievedChunk], max_por_fonte: int
    ) -> list[RetrievedChunk]:
        """No máximo `max_por_fonte` chunks por `source_file` sobrevivem.

        `hits` já chega ordenado por score (desc) — pelo boost quando há
        signals, pela ordem do kNN quando não há — então a PRIMEIRA ocorrência
        de cada source_file na lista já é a de maior score daquela fonte. Não
        precisa reagrupar por fonte para escolher quem fica: um passe único
        preservando a ordem já entrega os N melhores de cada uma.
        """
        if max_por_fonte < 1:
            raise ValueError("max_por_fonte precisa ser >= 1")

        contagem: dict[str, int] = {}
        deduped: list[RetrievedChunk] = []
        for hit in hits:
            vistos = contagem.get(hit.source_file, 0)
            if vistos >= max_por_fonte:
                continue
            contagem[hit.source_file] = vistos + 1
            deduped.append(hit)
        return deduped

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
                    vector_score=hit.vector_score,
                    fts_score=hit.fts_score,
                )
            )

        boosted.sort(key=lambda c: c.score, reverse=True)
        return boosted
