"""Testes de index/build.py — chunking, classificação de fonte e o pipeline
de indexação em LanceDB. Nenhum teste aqui chama a API da OpenAI de verdade
(embed() é sempre mockado) nem toca BroPilot-Knowledge/data/02_trusted/ real —
tudo roda contra .md sintéticos em diretórios temporários.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from bropilot_core.index.build import (
    _MAX_CHUNK_TOKENS,
    _OVERLAP_TOKENS,
    _count_tokens,
    build_index,
    chunk_document,
    classify_source,
)


class ClassifySourceTest(unittest.TestCase):
    def test_known_prefixes(self):
        cases = {
            "forum_652913.md": "forum",
            "youtube_manual.md": "youtube",
            "youtube_dS8rrFCVSBc.md": "youtube",
            "steam_3044736769.md": "steam",
            "build_monk_openhand.md": "build",
        }
        for filename, expected in cases.items():
            with self.subTest(filename=filename):
                self.assertEqual(classify_source(filename), expected)

    def test_unknown_prefix_falls_back_to_wiki(self):
        for filename in ["abilities.md", "weapons.md", "d&d_5e_rule_changes.md"]:
            with self.subTest(filename=filename):
                self.assertEqual(classify_source(filename), "wiki")


class ChunkDocumentSmallFileTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)

    def test_small_markdown_yields_sequential_chunks_with_metadata(self):
        path = self.dir / "build_teste.md"
        path.write_text(
            "# Build: Teste\n\n"
            "## Visão Geral\n\nFoco em algo qualquer, texto curto.\n\n"
            "## Progressão\n\nNível 3: X. Nível 6: Y.\n",
            encoding="utf-8",
        )

        chunks = list(chunk_document(path))

        self.assertGreaterEqual(len(chunks), 1)
        self.assertEqual([c.chunk_index for c in chunks], list(range(len(chunks))))
        for c in chunks:
            self.assertEqual(c.source_file, "build_teste.md")
            self.assertEqual(c.source_type, "build")
            self.assertLessEqual(_count_tokens(c.text), _MAX_CHUNK_TOKENS)


class ChunkDocumentGiantOutlierTest(unittest.TestCase):
    """Reproduz o formato do outlier real (youtube_manual.md): um único bloco
    de texto contínuo, sem quebras de parágrafo, grande o bastante pra exigir
    a janela deslizante de tokens (_window_tokens), não só o empacotamento por
    parágrafo."""

    @classmethod
    def setUpClass(cls):
        target_tokens = 140_000

        sample = " ".join(f"palavra{i}" for i in range(2000))
        tokens_per_word = _count_tokens(sample) / 2000
        word_count = int(target_tokens / tokens_per_word) + 500

        big_blob = " ".join(f"palavra{i}" for i in range(word_count))
        cls.markdown = f"# Dossiê Gigante (Teste)\n\n## Transcript\n\n{big_blob}\n"
        cls.total_tokens = _count_tokens(cls.markdown)

        cls._tmp = tempfile.TemporaryDirectory()
        cls.path = Path(cls._tmp.name) / "youtube_fabricado.md"
        cls.path.write_text(cls.markdown, encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_fabrication_sanity_is_actually_giant(self):
        # confere que o texto fabricado realmente está na ordem de ~140K
        # tokens, senão o teste abaixo não estaria testando o outlier de verdade.
        self.assertGreater(self.total_tokens, 100_000)

    def test_giant_document_becomes_many_chunks_within_cap(self):
        chunks = list(chunk_document(self.path))

        self.assertGreater(len(chunks), 100, "esperava MUITOS chunks pro outlier gigante")
        max_tokens = max(_count_tokens(c.text) for c in chunks)
        self.assertLessEqual(max_tokens, _MAX_CHUNK_TOKENS)
        self.assertEqual([c.chunk_index for c in chunks], list(range(len(chunks))))
        for c in chunks:
            self.assertEqual(c.source_file, "youtube_fabricado.md")
            self.assertEqual(c.source_type, "youtube")

    def test_consecutive_chunks_overlap(self):
        chunks = list(chunk_document(self.path))

        # palavraN é um token único e sequencial — se a cauda de um chunk
        # aparece dentro do próximo, é overlap de verdade, não coincidência.
        overlapping_pairs = 0
        for i in range(len(chunks) - 1):
            tail = chunks[i].text[-60:]
            if tail and tail in chunks[i + 1].text:
                overlapping_pairs += 1

        self.assertGreater(
            overlapping_pairs,
            0,
            "nenhum par de chunks consecutivos compartilhou conteúdo — overlap não está acontecendo",
        )
        # overlap é esperado na maioria das transições da janela deslizante,
        # não só numa transição isolada.
        self.assertGreater(overlapping_pairs, len(chunks) * 0.5)


class BuildIndexTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        base = Path(self._tmp.name)
        self.trusted_dir = base / "trusted"
        self.store_dir = base / "store"
        self.trusted_dir.mkdir()

        (self.trusted_dir / "build_a.md").write_text(
            "# Build A\n\n## Sec\n\nConteudo curto A.\n", encoding="utf-8"
        )
        (self.trusted_dir / "forum_b.md").write_text(
            "# B\n\nConteudo curto B.\n", encoding="utf-8"
        )
        (self.trusted_dir / "steam_c.md").write_text(
            "# C\n\n## Guia\n\nConteudo curto C.\n", encoding="utf-8"
        )

        self.expected_chunk_count = sum(
            len(list(chunk_document(p))) for p in sorted(self.trusted_dir.glob("*.md"))
        )

    @staticmethod
    def _fake_embed(self, texts):
        # assinatura bate com OpenAIProvider.embed (self, texts) porque é
        # usado como side_effect de um patch no método da classe.
        return [[float(i), float(len(text))] for i, text in enumerate(texts)]

    def test_build_index_creates_table_with_expected_schema_and_row_count(self):
        with patch(
            "bropilot_core.llm.OpenAIProvider.embed",
            autospec=True,
            side_effect=self._fake_embed,
        ) as mock_embed:
            n = build_index(trusted_dir=self.trusted_dir, store_dir=self.store_dir, rebuild=False)

        mock_embed.assert_called()  # embed foi chamado (mockado) — nunca requests real
        self.assertEqual(n, self.expected_chunk_count)

        import lancedb

        db = lancedb.connect(str(self.store_dir))
        table = db.open_table("chunks")

        self.assertEqual(set(table.schema.names), {"text", "source_file", "source_type", "chunk_index", "vector"})
        self.assertEqual(table.count_rows(), self.expected_chunk_count)

    def test_rebuild_true_does_not_duplicate_rows_across_runs(self):
        with patch(
            "bropilot_core.llm.OpenAIProvider.embed",
            autospec=True,
            side_effect=self._fake_embed,
        ):
            n1 = build_index(trusted_dir=self.trusted_dir, store_dir=self.store_dir, rebuild=True)
            n2 = build_index(trusted_dir=self.trusted_dir, store_dir=self.store_dir, rebuild=True)

        self.assertEqual(n1, self.expected_chunk_count)
        self.assertEqual(n2, self.expected_chunk_count)  # rebuild reprocessa tudo de novo, não é 0

        import lancedb

        db = lancedb.connect(str(self.store_dir))
        table = db.open_table("chunks")
        self.assertEqual(table.count_rows(), self.expected_chunk_count)  # não duplicou


if __name__ == "__main__":
    unittest.main()
