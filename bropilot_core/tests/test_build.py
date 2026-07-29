"""Testes de index/build.py — chunking, classificação de fonte e o pipeline
de indexação em LanceDB. Nenhum teste aqui chama a API da OpenAI de verdade
(embed() é sempre mockado) nem toca BroPilot-Knowledge/data/02_trusted/ real —
tudo roda contra .md sintéticos em diretórios temporários.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import lancedb

from bropilot_core.index.build import (
    _MAX_CHUNK_TOKENS,
    _count_tokens,
    assert_embedding_compatible,
    build_index,
    chunk_document,
    classify_source,
)


class _FakeProvider:
    """LLMProvider de mentira: embed determinístico, sem rede. Existe para
    injetar uma identidade de embed_model diferente e exercitar as travas de
    compatibilidade do índice."""

    def __init__(self, embed_model: str, dim: int = 2) -> None:
        self._embed_model = embed_model
        self._dim = dim

    @property
    def embed_model(self) -> str:
        return self._embed_model

    def embed(self, texts):
        return [[float(i)] * self._dim for i, _ in enumerate(texts)]

    def generate(self, system: str, user: str) -> str:
        raise NotImplementedError


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


class _BuildIndexFixture(unittest.TestCase):
    """Base sem testes: só a base de 3 .md, o embed mockado e os leitores do
    índice. Compartilhada por `BuildIndexTest` e `FtsIndexStaysInSyncTest` —
    herdar de uma classe COM testes faria a suíte rodar os dela duas vezes."""

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
        # assinatura bate com <Provider>.embed (self, texts) porque é usado
        # como side_effect de um patch autospec no método da classe.
        return [[float(i), float(len(text))] for i, text in enumerate(texts)]

    def _patch_ollama_embed(self):
        """Mocka o embed do provider DEFAULT (Ollama). Nenhuma rede real."""
        return patch(
            "bropilot_core.llm.OllamaProvider.embed",
            autospec=True,
            side_effect=self._fake_embed,
        )

    def _read_manifest(self):
        return json.loads((self.store_dir / "manifest.json").read_text(encoding="utf-8"))


class BuildIndexTest(_BuildIndexFixture):
    def test_build_index_creates_table_with_expected_schema_and_row_count(self):
        with self._patch_ollama_embed() as mock_embed:
            n = build_index(trusted_dir=self.trusted_dir, store_dir=self.store_dir, rebuild=False)

        mock_embed.assert_called()  # embed foi chamado (mockado) — nunca requests real
        self.assertEqual(n, self.expected_chunk_count)

        db = lancedb.connect(str(self.store_dir))
        table = db.open_table("chunks")

        self.assertEqual(set(table.schema.names), {"text", "source_file", "source_type", "chunk_index", "vector"})
        self.assertEqual(table.count_rows(), self.expected_chunk_count)

    def test_rebuild_true_does_not_duplicate_rows_across_runs(self):
        with self._patch_ollama_embed():
            n1 = build_index(trusted_dir=self.trusted_dir, store_dir=self.store_dir, rebuild=True)
            n2 = build_index(trusted_dir=self.trusted_dir, store_dir=self.store_dir, rebuild=True)

        self.assertEqual(n1, self.expected_chunk_count)
        self.assertEqual(n2, self.expected_chunk_count)  # rebuild reprocessa tudo de novo, não é 0

        db = lancedb.connect(str(self.store_dir))
        table = db.open_table("chunks")
        self.assertEqual(table.count_rows(), self.expected_chunk_count)  # não duplicou

    def test_uses_ollama_by_default_when_env_unset(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("BROPILOT_LLM", None)

            with self._patch_ollama_embed() as ollama_embed, patch(
                "bropilot_core.llm.OpenAIProvider.embed",
                autospec=True,
                side_effect=AssertionError("OpenAI não deveria ser usado no default"),
            ) as openai_embed:
                build_index(trusted_dir=self.trusted_dir, store_dir=self.store_dir, rebuild=True)

        ollama_embed.assert_called()
        openai_embed.assert_not_called()
        self.assertEqual(self._read_manifest()["embed_model"], "bge-m3")

    def test_manifest_records_embed_model_and_dim(self):
        with self._patch_ollama_embed():
            build_index(trusted_dir=self.trusted_dir, store_dir=self.store_dir, rebuild=True)

        manifest = self._read_manifest()
        self.assertEqual(manifest["embed_model"], "bge-m3")
        self.assertEqual(manifest["embed_dim"], 2)  # _fake_embed devolve vetores de 2 posições
        self.assertEqual(set(manifest["files"]), {"build_a.md", "forum_b.md", "steam_c.md"})

    def test_incremental_is_refused_when_embed_model_changed(self):
        with self._patch_ollama_embed():
            build_index(trusted_dir=self.trusted_dir, store_dir=self.store_dir, rebuild=True)

        outro_modelo = _FakeProvider(embed_model="text-embedding-3-small")

        with self.assertRaises(RuntimeError) as ctx:
            build_index(
                trusted_dir=self.trusted_dir,
                store_dir=self.store_dir,
                rebuild=False,
                llm=outro_modelo,
            )

        message = str(ctx.exception)
        self.assertIn("bge-m3", message)
        self.assertIn("text-embedding-3-small", message)
        self.assertIn("--rebuild", message)
        # e não escreveu nada com o modelo novo por cima do índice antigo
        self.assertEqual(self._read_manifest()["embed_model"], "bge-m3")

    def test_incremental_is_refused_when_manifest_is_lost(self):
        with self._patch_ollama_embed():
            build_index(trusted_dir=self.trusted_dir, store_dir=self.store_dir, rebuild=True)

        (self.store_dir / "manifest.json").unlink()  # tabela fica, manifest some

        with self._patch_ollama_embed():
            with self.assertRaises(RuntimeError) as ctx:
                build_index(
                    trusted_dir=self.trusted_dir, store_dir=self.store_dir, rebuild=False
                )

        self.assertIn("--rebuild", str(ctx.exception))
        # índice intacto, não duplicou
        table = lancedb.connect(str(self.store_dir)).open_table("chunks")
        self.assertEqual(table.count_rows(), self.expected_chunk_count)

    def test_rebuild_is_allowed_after_embed_model_changed(self):
        with self._patch_ollama_embed():
            build_index(trusted_dir=self.trusted_dir, store_dir=self.store_dir, rebuild=True)

        outro_modelo = _FakeProvider(embed_model="text-embedding-3-small", dim=3)
        n = build_index(
            trusted_dir=self.trusted_dir,
            store_dir=self.store_dir,
            rebuild=True,
            llm=outro_modelo,
        )

        self.assertEqual(n, self.expected_chunk_count)
        manifest = self._read_manifest()
        self.assertEqual(manifest["embed_model"], "text-embedding-3-small")
        self.assertEqual(manifest["embed_dim"], 3)


class FtsIndexStaysInSyncTest(_BuildIndexFixture):
    """O custo estrutural da busca híbrida é um SEGUNDO índice (FTS/BM25) que
    pode sair de sincronia com o vetorial. A decisão fecha essa porta criando-o
    dentro do mesmo `build_index` — estes testes são o que garante que ela
    continua fechada nos dois caminhos (rebuild e incremental)."""

    def _colunas_fts(self):
        table = lancedb.connect(str(self.store_dir)).open_table("chunks")
        return {
            coluna
            for indice in table.list_indices()
            if str(indice.index_type).upper().endswith("FTS")
            for coluna in indice.columns
        }

    def _stats_fts(self):
        table = lancedb.connect(str(self.store_dir)).open_table("chunks")
        return table.index_stats("text_idx")

    def test_every_row_is_actually_inside_the_fts_index(self):
        """A armadilha que custou uma bateria inteira: criar o índice FTS
        antes de escrever as linhas deixa `num_indexed_rows=0`. Nada falha —
        `list_indices()` mostra o índice e a busca FTS até responde, por uma
        varredura das linhas não indexadas com pontuação BM25 diferente. Na
        base real isso derrubou o recall de Monge de 4/5 para 1/5. Conferir a
        EXISTÊNCIA do índice não pega isso; só conferir a COBERTURA pega."""
        with self._patch_ollama_embed():
            build_index(trusted_dir=self.trusted_dir, store_dir=self.store_dir,
                        rebuild=True)

        stats = self._stats_fts()
        self.assertEqual(stats.num_unindexed_rows, 0)
        self.assertEqual(stats.num_indexed_rows, self.expected_chunk_count)

    def test_incremental_folds_new_rows_into_the_fts_index(self):
        """Mesma cobertura, no caminho incremental: todo `table.add` posterior
        cai num delta fora do índice até alguém incorporá-lo."""
        with self._patch_ollama_embed():
            build_index(trusted_dir=self.trusted_dir, store_dir=self.store_dir,
                        rebuild=True)
        (self.trusted_dir / "forum_novo.md").write_text(
            "# Novo\n\nzorblaxian cascade\n", encoding="utf-8"
        )
        with self._patch_ollama_embed():
            build_index(trusted_dir=self.trusted_dir, store_dir=self.store_dir,
                        rebuild=False)

        self.assertEqual(self._stats_fts().num_unindexed_rows, 0)

    def test_rebuild_creates_the_fts_index_and_records_it(self):
        with self._patch_ollama_embed():
            build_index(trusted_dir=self.trusted_dir, store_dir=self.store_dir,
                        rebuild=True)

        self.assertIn("text", self._colunas_fts())
        self.assertEqual(self._read_manifest()["fts"]["column"], "text")
        # inglês, não o default neutro: o corpus é ~97% inglês e o stemming
        # é o que faz "dice"/"dices" casarem.
        self.assertEqual(self._read_manifest()["fts"]["language"], "English")

    def test_incremental_backfills_fts_into_a_pre_hybrid_index(self):
        """O caso real de migração: um índice construído ANTES da decisão tem
        vetores e nenhum FTS. Rodar o incremental tem que consertá-lo, sem
        exigir um rebuild completo e sem re-embedar nada."""
        with self._patch_ollama_embed():
            build_index(trusted_dir=self.trusted_dir, store_dir=self.store_dir,
                        rebuild=True)

        # desfaz a híbrida, simulando o índice legado
        table = lancedb.connect(str(self.store_dir)).open_table("chunks")
        table.drop_index("text_idx")
        manifest = self._read_manifest()
        manifest["fts"] = None
        (self.store_dir / "manifest.json").write_text(json.dumps(manifest))
        self.assertEqual(self._colunas_fts(), set())

        with self._patch_ollama_embed() as mock_embed:
            n = build_index(trusted_dir=self.trusted_dir, store_dir=self.store_dir,
                            rebuild=False)

        self.assertEqual(n, 0)  # nenhum arquivo mudou: nada reindexado
        mock_embed.assert_not_called()  # e nada re-embedado
        self.assertIn("text", self._colunas_fts())  # mas o FTS voltou
        self.assertEqual(self._read_manifest()["fts"]["column"], "text")

    def test_fts_covers_rows_added_after_the_index_was_created(self):
        """O incremental adiciona linhas DEPOIS de o índice FTS existir. Se o
        FTS não acompanhasse as escritas, o doc novo ficaria invisível para a
        perna lexical — sincronia quebrada sem nenhum erro."""
        with self._patch_ollama_embed():
            build_index(trusted_dir=self.trusted_dir, store_dir=self.store_dir,
                        rebuild=True)

        (self.trusted_dir / "forum_novo.md").write_text(
            "# Novo\n\nzorblaxian cascade zorblaxian\n", encoding="utf-8"
        )
        with self._patch_ollama_embed():
            build_index(trusted_dir=self.trusted_dir, store_dir=self.store_dir,
                        rebuild=False)

        table = lancedb.connect(str(self.store_dir)).open_table("chunks")
        achados = (
            table.search("zorblaxian", query_type="fts")
            .limit(5).to_arrow().to_pylist()
        )
        self.assertEqual([r["source_file"] for r in achados], ["forum_novo.md"])


class AssertEmbeddingCompatibleTest(unittest.TestCase):
    """A trava que o Retriever vai chamar no __init__ (ver docstring dele)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.store_dir = Path(self._tmp.name) / "store"
        self.store_dir.mkdir()

    def _write_manifest(self, embed_model):
        (self.store_dir / "manifest.json").write_text(
            json.dumps({"embed_model": embed_model, "embed_dim": 2, "files": {}}),
            encoding="utf-8",
        )

    def test_passes_when_models_match(self):
        self._write_manifest("nomic-embed-text")
        assert_embedding_compatible(_FakeProvider("nomic-embed-text"), self.store_dir)

    def test_raises_actionable_error_when_models_diverge(self):
        self._write_manifest("nomic-embed-text")

        with self.assertRaises(RuntimeError) as ctx:
            assert_embedding_compatible(
                _FakeProvider("text-embedding-3-small"), self.store_dir
            )

        message = str(ctx.exception)
        self.assertIn("nomic-embed-text", message)
        self.assertIn("text-embedding-3-small", message)
        self.assertIn("--rebuild", message)

    def test_silent_when_there_is_no_index_yet(self):
        # sem manifest, quem abre o índice é que trata a ausência
        assert_embedding_compatible(_FakeProvider("qualquer"), self.store_dir)


if __name__ == "__main__":
    unittest.main()
