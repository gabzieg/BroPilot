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


def _build_fake_index(store_dir: Path, rows, embed_model: str = "bge-m3") -> None:
    """Monta um índice com o MESMO schema que build.py grava, mais o manifest
    de identidade do embedding que o Retriever confere no __init__."""
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

    (store_dir / "manifest.json").write_text(
        json.dumps({"embed_model": embed_model, "embed_dim": _DIM, "files": {}}),
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


class TermVariantsTest(unittest.TestCase):
    def test_camel_case_signal_also_matches_spaced_form(self):
        # "OpenHand" precisa casar tanto com o arquivo "…openhand.md" quanto
        # com o texto dos guias, que escreve "Open Hand".
        self.assertEqual(_term_variants("OpenHand"), ["openhand", "open hand"])

    def test_single_word_has_one_variant(self):
        self.assertEqual(_term_variants("Monk"), ["monk"])


if __name__ == "__main__":
    unittest.main()
