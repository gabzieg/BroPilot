"""Testes do Retriever. Nenhum toca o Ollama nem o índice real de
bropilot_core/index/store/ — cada teste monta um índice LanceDB temporário com
vetores fabricados e um provider de mentira.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import lancedb
import pyarrow as pa

from bropilot_core.index.build import ensure_fts_index
from bropilot_core.index.retriever import (
    _BOOST_SOURCE_FILE_MATCH,
    _SOURCE_TYPE_BOOST,
    Retriever,
    RetrievedChunk,
    _distance_to_similarity,
    _term_variants,
)

_DIM = 4


class _FakeProvider:
    """Devolve um vetor fixo para qualquer query, definido no construtor. O
    embedding é irrelevante para o que se testa aqui — o que importa é a
    ordenação que o índice devolve e como o Retriever a traduz."""

    def __init__(self, query_vector, embed_model: str = "bge-m3") -> None:
        self._query_vector = query_vector
        self._embed_model = embed_model

    @property
    def embed_model(self) -> str:
        return self._embed_model

    def embed(self, texts):
        return [list(self._query_vector) for _ in texts]

    def generate(self, system: str, user: str) -> str:
        raise NotImplementedError


def _build_fake_index(
    store_dir: Path, rows, embed_model: str = "bge-m3", *, com_fts: bool = True
) -> None:
    """Monta um índice com o MESMO schema que build.py grava, mais o manifest
    de identidade do embedding que o Retriever confere no __init__.

    O índice FTS sai da própria `build.ensure_fts_index` — reimplementar a
    criação aqui deixaria os testes passando contra uma configuração de
    tokenizer que a produção não usa, que é exatamente o tipo de divergência
    que a busca híbrida não pode ter.

    `com_fts=False` fabrica o caso patológico que a trava de falha-cedo
    existe para pegar: vetores válidos, nenhum FTS.
    """
    store_dir.mkdir(parents=True, exist_ok=True)
    schema = pa.schema(
        [
            pa.field("text", pa.string()),
            pa.field("source_file", pa.string()),
            pa.field("source_type", pa.string()),
            pa.field("chunk_index", pa.int64()),
            pa.field("vector", pa.list_(pa.float32(), _DIM)),
        ]
    )
    db = lancedb.connect(str(store_dir))
    table = db.create_table("chunks", schema=schema)
    table.add(rows)
    # depois do add, igual à produção: índice FTS criado sobre tabela vazia
    # não indexa linha nenhuma (ver build.ensure_fts_index).
    fts = ensure_fts_index(table) if com_fts else None

    (store_dir / "manifest.json").write_text(
        json.dumps({
            "embed_model": embed_model,
            "embed_dim": _DIM,
            "fts": fts,
            "files": {},
        }),
        encoding="utf-8",
    )


def _row(text, source_file, source_type, vector, chunk_index=0):
    return {
        "text": text,
        "source_file": source_file,
        "source_type": source_type,
        "chunk_index": chunk_index,
        "vector": vector,
    }


class DistanceToSimilarityTest(unittest.TestCase):
    def test_zero_distance_is_perfect_similarity(self):
        self.assertAlmostEqual(_distance_to_similarity(0.0), 1.0)

    def test_is_monotonic_decreasing(self):
        # mais longe => menos similar; é o que garante que ordenar por score
        # desc equivale a ordenar por distância asc.
        sims = [_distance_to_similarity(d) for d in (0.0, 0.5, 1.0, 2.0)]
        self.assertEqual(sims, sorted(sims, reverse=True))


class RetrieverPureSearchTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.store_dir = Path(self._tmp.name) / "store"

        # vetores unitários; o mais próximo de [1,0,0,0] é "perto.md"
        _build_fake_index(
            self.store_dir,
            [
                _row("chunk bem perto da query", "perto.md", "wiki", [1.0, 0.0, 0.0, 0.0]),
                _row("chunk mais ou menos", "medio.md", "forum", [0.0, 1.0, 0.0, 0.0]),
                _row("chunk oposto", "longe.md", "steam", [-1.0, 0.0, 0.0, 0.0]),
            ],
        )
        self.provider = _FakeProvider([1.0, 0.0, 0.0, 0.0])

    def test_returns_k_results_ordered_by_similarity(self):
        r = Retriever(self.provider, self.store_dir)

        hits = r.search("qualquer pergunta", k=3)

        self.assertEqual(len(hits), 3)
        self.assertEqual([h.source_file for h in hits], ["perto.md", "medio.md", "longe.md"])
        scores = [h.score for h in hits]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_respects_k(self):
        r = Retriever(self.provider, self.store_dir)

        self.assertEqual(len(r.search("q", k=1)), 1)
        self.assertEqual(len(r.search("q", k=2)), 2)

    def test_fields_are_populated(self):
        r = Retriever(self.provider, self.store_dir)

        hit = r.search("q", k=1)[0]

        self.assertIsInstance(hit, RetrievedChunk)
        self.assertEqual(hit.text, "chunk bem perto da query")
        self.assertEqual(hit.source_file, "perto.md")
        self.assertEqual(hit.source_type, "wiki")
        self.assertAlmostEqual(hit.score, 1.0, places=4)  # vetor idêntico à query
        # sem signals, nada de boost: score == base_score e sem justificativa
        self.assertEqual(hit.score, hit.base_score)
        self.assertEqual(hit.boost_reasons, [])


class RetrieverBootstrapErrorsTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.base = Path(self._tmp.name)

    def test_missing_store_dir_tells_user_to_build(self):
        with self.assertRaises(RuntimeError) as ctx:
            Retriever(_FakeProvider([1.0, 0, 0, 0]), self.base / "nao_existe")

        self.assertIn("bropilot_core.index.build", str(ctx.exception))

    def test_store_dir_without_table_tells_user_to_build(self):
        empty = self.base / "vazio"
        empty.mkdir()

        with self.assertRaises(RuntimeError) as ctx:
            Retriever(_FakeProvider([1.0, 0, 0, 0]), empty)

        self.assertIn("bropilot_core.index.build", str(ctx.exception))

    def test_refuses_provider_with_different_embedding_model(self):
        # o índice foi construído com bge-m3; consultar com outro modelo
        # devolveria chunks errados sem erro — tem que falhar no __init__.
        store = self.base / "store"
        _build_fake_index(
            store,
            [_row("t", "a.md", "wiki", [1.0, 0.0, 0.0, 0.0])],
            embed_model="bge-m3",
        )

        with self.assertRaises(RuntimeError) as ctx:
            Retriever(_FakeProvider([1.0, 0, 0, 0], embed_model="nomic-embed-text"), store)

        message = str(ctx.exception)
        self.assertIn("bge-m3", message)
        self.assertIn("nomic-embed-text", message)
        self.assertIn("--rebuild", message)


class StateBoostTest(unittest.TestCase):
    """A prova do diferencial: o estado da party muda o ranking."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.store_dir = Path(self._tmp.name) / "store"
        self.query_vector = [1.0, 0.0, 0.0, 0.0]

        # Os dois primeiros têm vetores IDÊNTICOS -> similaridade idêntica.
        # Assim o desempate só pode vir do boost, não da semântica.
        _build_fake_index(
            self.store_dir,
            [
                _row("guia de build detalhado", "build_monk_openhand.md", "build",
                     [1.0, 0.0, 0.0, 0.0]),
                _row("discussao aleatoria", "forum_999.md", "forum",
                     [1.0, 0.0, 0.0, 0.0]),
                _row("texto qualquer", "outro.md", "wiki", [0.0, 1.0, 0.0, 0.0]),
            ],
        )
        self.provider = _FakeProvider(self.query_vector)

    def test_party_signals_promote_matching_build_file(self):
        r = Retriever(self.provider, self.store_dir)
        signals = {"classes": ["Monk"], "subclasses": ["OpenHand"]}

        hits = r.search("qual minha melhor jogada?", signals=signals, k=2)

        self.assertEqual(hits[0].source_file, "build_monk_openhand.md")
        # empatados na semântica crua, separados pelo boost
        self.assertAlmostEqual(hits[0].base_score, hits[1].base_score, places=4)
        self.assertGreater(hits[0].score, hits[1].score)

    def test_boost_is_auditable(self):
        r = Retriever(self.provider, self.store_dir)
        signals = {"classes": ["Monk"], "subclasses": ["OpenHand"]}

        top = r.search("q", signals=signals, k=1)[0]

        # o quanto subiu é exatamente score - base_score, e as razões explicam
        self.assertAlmostEqual(
            top.score - top.base_score,
            _BOOST_SOURCE_FILE_MATCH + _SOURCE_TYPE_BOOST["build"],
            places=4,
        )
        justificativa = " ".join(top.boost_reasons)
        self.assertIn("monk", justificativa)
        self.assertIn("source_type=build", justificativa)

    def test_same_index_orders_differently_with_and_without_signals(self):
        # Índice próprio: aqui o chunk do fórum é SEMANTICAMENTE mais próximo
        # da query que o do monge. Sem signals ele vence; com signals o boost
        # tem de virar o resultado. (No índice do setUp os dois empatam e a
        # ordem já saía "certa" por desempate de inserção — não provaria nada.)
        store = Path(self._tmp.name) / "store_ordem"
        _build_fake_index(
            store,
            [
                _row("post de forum", "forum_999.md", "forum", [1.0, 0.0, 0.0, 0.0]),
                _row("build de monge", "build_monk_openhand.md", "build",
                     [1.0, 0.25, 0.0, 0.0]),
            ],
        )
        r = Retriever(_FakeProvider(self.query_vector), store)

        sem = [h.source_file for h in r.search("q", k=2)]
        com = [h.source_file for h in r.search("q", signals={"classes": ["Monk"]}, k=2)]

        self.assertEqual(sem[0], "forum_999.md")          # semântica sozinha
        self.assertEqual(com[0], "build_monk_openhand.md")  # estado da party virou
        self.assertNotEqual(sem, com, "o boost não alterou a ordenação")

    def test_signals_that_match_nothing_leave_scores_untouched(self):
        r = Retriever(self.provider, self.store_dir)

        hits = r.search("q", signals={"classes": ["Bard"]}, k=3)

        for h in hits:
            # só o peso de source_type pode agir; nenhum match de nome/texto
            esperado = _SOURCE_TYPE_BOOST.get(h.source_type, 0.0)
            self.assertAlmostEqual(h.score - h.base_score, esperado, places=4)

    def test_empty_signals_behave_like_no_signals(self):
        r = Retriever(self.provider, self.store_dir)

        com_vazio = [h.source_file for h in r.search("q", signals={}, k=3)]
        sem = [h.source_file for h in r.search("q", k=3)]

        self.assertEqual(com_vazio, sem)

    def test_boost_pool_lets_a_lower_ranked_chunk_be_promoted(self):
        """O ponto do pool: sem buscar mais que k, o boost nunca promoveria um
        chunk que ficou fora do top-k do kNN puro."""
        store = Path(self._tmp.name) / "store2"
        rows = [
            # 8 chunks genéricos mais próximos da query que o do monge
            _row(f"ruido {i}", f"ruido_{i}.md", "wiki", [1.0, 0.05 * (i + 1), 0.0, 0.0])
            for i in range(8)
        ]
        rows.append(
            _row("build de monge", "build_monk_openhand.md", "build", [1.0, 0.6, 0.0, 0.0])
        )
        _build_fake_index(store, rows)
        r = Retriever(_FakeProvider(self.query_vector), store)

        sem = [h.source_file for h in r.search("q", k=3)]
        com = [h.source_file for h in r.search("q", signals={"classes": ["Monk"]}, k=3)]

        self.assertNotIn("build_monk_openhand.md", sem)  # fora do top-3 puro
        self.assertIn("build_monk_openhand.md", com)     # promovido pelo boost


    def test_candidate_pool_does_not_shrink_with_small_k(self):
        """k controla quantos resultados voltam, não QUAIS candidatos existem.
        Sem o piso do pool, um k pequeno tornava um chunk relevante inalcançável
        pelo boost (medido na base real: invisível com k=4, 1º lugar com k=6)."""
        store = Path(self._tmp.name) / "store_pool"
        # 60 chunks de ruído, do mais perto ao mais longe da query; o do monge
        # cai no meio (~rank 50) — fora de qualquer top-k testado, mas dentro
        # do piso do pool. O gap semântico até o 1º é vencível pelo boost.
        rows = [
            _row(f"ruido {i}", f"ruido_{i}.md", "wiki", [1.0, 0.01 * (i + 1), 0.0, 0.0])
            for i in range(60)
        ]
        rows.append(
            _row("guia de build", "build_monk_openhand.md", "build", [1.0, 0.5, 0.0, 0.0])
        )
        _build_fake_index(store, rows)
        r = Retriever(_FakeProvider(self.query_vector), store)

        # sem signals ele não aparece em nenhum dos k testados
        self.assertNotIn(
            "build_monk_openhand.md", [h.source_file for h in r.search("q", k=6)]
        )

        for k in (1, 2, 4, 6):
            with self.subTest(k=k):
                hits = r.search("q", signals={"classes": ["Monk"]}, k=k)
                self.assertEqual(hits[0].source_file, "build_monk_openhand.md")


class DedupBySourceTest(unittest.TestCase):
    """O ponto do dedup: um documento longo não deveria monopolizar o top-k
    com vizinhos redundantes enquanto outra fonte relevante fica de fora."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.store_dir = Path(self._tmp.name) / "store"
        self.query_vector = [1.0, 0.0, 0.0, 0.0]

    def test_keeps_only_best_chunk_per_source_by_default(self):
        # 3 chunks de a.md (scores decrescentes) + 1 de b.md entre o 1º e o
        # 2º de a.md: sem dedup o top-2 cru seria [a.md, b.md] só por sorte
        # de posição; aqui o que importa é que a.md não aparece duas vezes.
        _build_fake_index(
            self.store_dir,
            [
                _row("A melhor", "a.md", "forum", [1.0, 0.0, 0.0, 0.0]),
                _row("A médio", "a.md", "forum", [1.0, 0.1, 0.0, 0.0]),
                _row("A pior", "a.md", "forum", [1.0, 0.2, 0.0, 0.0]),
                _row("B único", "b.md", "wiki", [1.0, 0.05, 0.0, 0.0]),
            ],
        )
        r = Retriever(_FakeProvider(self.query_vector), self.store_dir)

        hits = r.search("q", k=2)

        self.assertEqual([h.source_file for h in hits], ["a.md", "b.md"])
        self.assertEqual(hits[0].text, "A melhor")  # o de maior score sobrevive

    def test_returns_fewer_than_k_when_too_few_distinct_sources(self):
        # só 1 fonte no pool inteiro; k=2 não deve inventar uma segunda.
        _build_fake_index(
            self.store_dir,
            [
                _row("A1", "a.md", "forum", [1.0, 0.0, 0.0, 0.0]),
                _row("A2", "a.md", "forum", [1.0, 0.1, 0.0, 0.0]),
                _row("A3", "a.md", "forum", [1.0, 0.2, 0.0, 0.0]),
            ],
        )
        r = Retriever(_FakeProvider(self.query_vector), self.store_dir)

        hits = r.search("q", k=2)

        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].source_file, "a.md")

    def test_max_por_fonte_keeps_n_best_per_source(self):
        _build_fake_index(
            self.store_dir,
            [
                _row("A1", "a.md", "forum", [1.0, 0.0, 0.0, 0.0]),
                _row("A2", "a.md", "forum", [1.0, 0.1, 0.0, 0.0]),
                _row("A3", "a.md", "forum", [1.0, 0.2, 0.0, 0.0]),
                _row("B1", "b.md", "wiki", [1.0, 0.05, 0.0, 0.0]),
            ],
        )
        r = Retriever(_FakeProvider(self.query_vector), self.store_dir)

        hits = r.search("q", k=3, max_por_fonte=2)

        # ordem crua por similaridade: A1, B1, A2, A3 — com max_por_fonte=2,
        # A3 é o único cortado (a.md já bateu o teto em A2).
        self.assertEqual([h.source_file for h in hits], ["a.md", "b.md", "a.md"])
        self.assertEqual([h.text for h in hits], ["A1", "B1", "A2"])

    def test_dedup_survivor_is_chosen_after_boost_not_before(self):
        # a.md tem 2 chunks: o cru mais parecido (sem termo do sinal) e um
        # levemente mais distante mas cujo TEXTO cita o sinal — o boost de
        # texto (+0.05) precisa virar a ordem para o segundo sobreviver.
        _build_fake_index(
            self.store_dir,
            [
                _row("random text no match", "a.md", "forum", [1.0, 0.0, 0.0, 0.0]),
                _row("an elf ranger writeup", "a.md", "forum", [1.0, 0.09, 0.0, 0.0]),
            ],
        )
        r = Retriever(_FakeProvider(self.query_vector), self.store_dir)

        hits = r.search("q", signals={"classes": ["Elf"]}, k=1)

        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].text, "an elf ranger writeup")

    def test_rejects_max_por_fonte_below_one(self):
        _build_fake_index(
            self.store_dir, [_row("t", "a.md", "wiki", [1.0, 0.0, 0.0, 0.0])]
        )
        r = Retriever(_FakeProvider(self.query_vector), self.store_dir)

        with self.assertRaises(ValueError):
            r.search("q", k=1, max_por_fonte=0)


class HybridSearchTest(unittest.TestCase):
    """A prova da busca híbrida: um termo literal raro alcança um chunk que o
    vetor sozinho jamais traria.

    O índice é construído para separar as duas pernas de propósito: os
    `denso_*.md` são semanticamente colados na query (vetor idêntico ou quase)
    e não contêm o termo raro; os `lexical_*.md` são o OPOSTO vetorial da
    query e só têm o termo. Nenhum chunk é bom nos dois eixos, então quem
    aparecer no topo denuncia qual sinal mandou.
    """

    _QUERY_VECTOR = [1.0, 0.0, 0.0, 0.0]
    # Palavra inventada: qualquer termo real do domínio correria o risco de
    # também casar por sentido e embaralhar o que o teste isola.
    _TERMO_RARO = "zorblaxian"

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.store_dir = Path(self._tmp.name) / "store"
        _build_fake_index(
            self.store_dir,
            [
                _row("generic guide about combat tactics and positioning",
                     "denso_0.md", "forum", [1.0, 0.0, 0.0, 0.0]),
                _row("more generic advice on combat and positioning",
                     "denso_1.md", "forum", [1.0, 0.02, 0.0, 0.0]),
                _row("further notes about tactics in combat",
                     "denso_2.md", "forum", [1.0, 0.04, 0.0, 0.0]),
                # dois chunks com o termo, e não um: o LanceDB normaliza os
                # scores do BM25 por min-max DENTRO do pool, então um único
                # casamento lexical normalizaria para 0 e não pontuaria nada.
                _row("zorblaxian resonance zorblaxian cascade zorblaxian",
                     "lexical_forte.md", "wiki", [-1.0, 0.0, 0.0, 0.0]),
                _row("a long text mentioning zorblaxian once among many "
                     "other unrelated words here",
                     "lexical_fraco.md", "steam", [-0.9, 0.3, 0.0, 0.0]),
            ],
        )
        self.provider = _FakeProvider(self._QUERY_VECTOR)

    def _busca(self, vector_weight):
        r = Retriever(self.provider, self.store_dir, vector_weight=vector_weight)
        return [h.source_file for h in r.search(self._TERMO_RARO, k=3)]

    def test_rare_literal_term_reaches_a_chunk_the_vector_alone_never_would(self):
        # peso 1.00 = FTS com coeficiente zero = a busca vetorial pura de
        # antes da híbrida. É a condição de controle, pelo MESMO código.
        self.assertNotIn("lexical_forte.md", self._busca(1.0))
        # com o lado lexical pesando, o mesmo chunk vira o 1º resultado
        self.assertEqual(self._busca(0.3)[0], "lexical_forte.md")

    def test_fts_score_is_in_the_debug_trail(self):
        r = Retriever(self.provider, self.store_dir, vector_weight=0.3)

        por_arquivo = {h.source_file: h for h in r.search(self._TERMO_RARO, k=5)}

        # quem casou o termo tem score de BM25; quem não casou tem None —
        # "não votou" é diferente de "votou zero", e o rastro precisa
        # distinguir os dois para a fusão ser auditável.
        self.assertIsNotNone(por_arquivo["lexical_forte.md"].fts_score)
        self.assertGreater(por_arquivo["lexical_forte.md"].fts_score,
                            por_arquivo["lexical_fraco.md"].fts_score)
        self.assertIsNone(por_arquivo["denso_0.md"].fts_score)
        # a perna vetorial continua auditável em paralelo
        self.assertAlmostEqual(por_arquivo["denso_0.md"].vector_score, 1.0, places=4)

    def test_full_vector_weight_reproduces_pure_vector_scores(self):
        """`vector_weight=1.0` tem que devolver exatamente a similaridade de
        cosseno de antes da híbrida — é o que autoriza `compare_hybrid.py` a
        usar esse peso como coluna "antes" em vez de um checkout do código
        anterior."""
        r = Retriever(self.provider, self.store_dir, vector_weight=1.0)

        hits = r.search(self._TERMO_RARO, k=5)

        for hit in hits:
            with self.subTest(arquivo=hit.source_file):
                self.assertAlmostEqual(hit.base_score, hit.vector_score, places=4)

    def test_rejects_weight_outside_zero_one(self):
        for peso in (-0.1, 1.5):
            with self.subTest(peso=peso), self.assertRaises(ValueError):
                Retriever(self.provider, self.store_dir, vector_weight=peso)


class MissingFtsIndexTest(unittest.TestCase):
    """Índice vetorial válido + FTS ausente é o pior cenário da híbrida: o
    LanceDB aceita a query, o lado lexical volta vazio, e o resultado é
    silenciosamente o ranking vetorial puro. Tem que explodir no __init__."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.store_dir = Path(self._tmp.name) / "store"

    def test_vector_index_without_fts_fails_early_asking_for_rebuild(self):
        _build_fake_index(
            self.store_dir,
            [_row("um texto qualquer", "a.md", "wiki", [1.0, 0.0, 0.0, 0.0])],
            com_fts=False,
        )

        with self.assertRaises(RuntimeError) as ctx:
            Retriever(_FakeProvider([1.0, 0.0, 0.0, 0.0]), self.store_dir)

        mensagem = str(ctx.exception)
        self.assertIn("FTS", mensagem)
        self.assertIn("--rebuild", mensagem)

    def test_manifest_claiming_fts_that_the_table_lacks_also_fails(self):
        # Deriva ao contrário: o manifest promete FTS, a tabela não tem. Se
        # só o manifest fosse conferido, isto passaria batido e cairia
        # exatamente no modo de falha silenciosa que a trava evita.
        _build_fake_index(
            self.store_dir,
            [_row("um texto qualquer", "a.md", "wiki", [1.0, 0.0, 0.0, 0.0])],
            com_fts=False,
        )
        manifest = json.loads((self.store_dir / "manifest.json").read_text())
        manifest["fts"] = {"column": "text", "language": "English", "version": 1}
        (self.store_dir / "manifest.json").write_text(json.dumps(manifest))

        with self.assertRaises(RuntimeError) as ctx:
            Retriever(_FakeProvider([1.0, 0.0, 0.0, 0.0]), self.store_dir)

        self.assertIn("--rebuild", str(ctx.exception))


class TermVariantsTest(unittest.TestCase):
    def test_camel_case_signal_also_matches_spaced_form(self):
        # "OpenHand" precisa casar tanto com o arquivo "…openhand.md" quanto
        # com o texto dos guias, que escreve "Open Hand".
        self.assertEqual(_term_variants("OpenHand"), ["openhand", "open hand"])

    def test_single_word_has_one_variant(self):
        self.assertEqual(_term_variants("Monk"), ["monk"])


if __name__ == "__main__":
    unittest.main()
