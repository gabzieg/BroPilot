"""Testes mínimos do OpenAIProvider e da seleção de back-end (create_provider).

Não há suíte de testes no repo ainda (ver CLAUDE.md) — este arquivo cobre só o
que foi pedido ao adicionar o back-end OpenAI: health_check e embed()
falhando com mensagem clara sem tocar rede de verdade, o batching de embed()
respeitando o teto de itens por request, e o default de back-end permanecendo
Ollama quando BROPILOT_LLM não está setada.
"""

from __future__ import annotations

import os
import unittest
from unittest.mock import MagicMock, patch

import requests

from bropilot_core.llm import OllamaProvider, OpenAIProvider, create_provider


class OpenAIProviderHealthCheckTest(unittest.TestCase):
    @patch("bropilot_core.llm.requests.get")
    def test_health_check_fails_clearly_on_bad_key(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.ok = False
        mock_get.return_value = mock_response

        provider = OpenAIProvider(api_key="sk-fake-nao-existe")

        with self.assertRaises(RuntimeError) as ctx:
            provider.health_check()

        # mock_get foi chamado (e só o mock) — nenhuma chamada de rede real ocorreu.
        mock_get.assert_called_once()
        self.assertIn("401", str(ctx.exception))
        self.assertIn("OPENAI_API_KEY", str(ctx.exception))

    @patch("bropilot_core.llm.requests.get")
    def test_health_check_fails_without_any_key_and_skips_http(self, mock_get):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("OPENAI_API_KEY", None)
            provider = OpenAIProvider(api_key=None)

            with self.assertRaises(RuntimeError) as ctx:
                provider.health_check()

        # Sem key, nem tenta HTTP — falha antes, mensagem clara.
        mock_get.assert_not_called()
        self.assertIn("OPENAI_API_KEY", str(ctx.exception))


class OpenAIProviderEmbedTest(unittest.TestCase):
    @patch("bropilot_core.llm.requests.post")
    def test_embed_batches_requests_by_batch_size(self, mock_post):
        provider = OpenAIProvider(api_key="sk-fake")
        provider._EMBED_BATCH_SIZE = 2  # facilita forçar múltiplos lotes no teste

        def fake_response(texts):
            resp = MagicMock()
            resp.status_code = 200
            resp.ok = True
            resp.json.return_value = {
                "data": [
                    {"index": i, "embedding": [float(i)]} for i, _ in enumerate(texts)
                ]
            }
            return resp

        mock_post.side_effect = [
            fake_response(["a", "b"]),
            fake_response(["c"]),
        ]

        vectors = provider.embed(["a", "b", "c"])

        self.assertEqual(mock_post.call_count, 2)
        self.assertEqual(vectors, [[0.0], [1.0], [0.0]])
        first_call_body = mock_post.call_args_list[0].kwargs["json"]
        self.assertEqual(first_call_body["model"], "text-embedding-3-small")
        self.assertEqual(first_call_body["input"], ["a", "b"])

    @patch("bropilot_core.llm.requests.post")
    def test_embed_fails_clearly_on_bad_key(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.ok = False
        mock_post.return_value = mock_response

        provider = OpenAIProvider(api_key="sk-fake-nao-existe")

        with self.assertRaises(RuntimeError) as ctx:
            provider.embed(["algum texto"])

        self.assertIn("401", str(ctx.exception))

    def test_embed_returns_empty_list_without_any_call(self):
        provider = OpenAIProvider(api_key="sk-fake")
        self.assertEqual(provider.embed([]), [])


class OllamaProviderTest(unittest.TestCase):
    """Todos os testes mockam requests — nenhuma chamada real ao Ollama."""

    @staticmethod
    def _ok(payload):
        response = MagicMock()
        response.status_code = 200
        response.ok = True
        response.json.return_value = payload
        return response

    @patch("bropilot_core.llm.requests.post")
    def test_generate_extracts_text_from_chat_response(self, mock_post):
        mock_post.return_value = self._ok(
            {"model": "qwen2.5", "message": {"role": "assistant", "content": "Tavern Brawler."}, "done": True}
        )

        answer = OllamaProvider().generate("persona", "qual feat?")

        self.assertEqual(answer, "Tavern Brawler.")
        body = mock_post.call_args.kwargs["json"]
        self.assertIs(body["stream"], False)
        self.assertEqual(
            [m["role"] for m in body["messages"]], ["system", "user"]
        )

    @patch("bropilot_core.llm.requests.post")
    def test_embed_preserves_input_order_across_batches(self, mock_post):
        provider = OllamaProvider(embed_batch_size=2)
        texts = ["a", "b", "c", "d", "e"]

        # cada vetor carrega o texto que o gerou, pra provar o alinhamento
        # texto->vetor mesmo com a resposta chegando em 3 lotes distintos.
        def respond(url, json, timeout):
            return self._ok(
                {"embeddings": [[float(ord(t))] for t in json["input"]]}
            )

        mock_post.side_effect = respond

        vectors = provider.embed(texts)

        self.assertEqual(mock_post.call_count, 3)  # 2 + 2 + 1
        self.assertEqual(vectors, [[float(ord(t))] for t in texts])

    @patch("bropilot_core.llm.requests.post")
    def test_embed_rejects_response_with_mismatched_length(self, mock_post):
        # se o Ollama devolvesse menos vetores que textos, gravar assim
        # desalinharia texto e vetor no índice silenciosamente.
        mock_post.return_value = self._ok({"embeddings": [[0.1]]})

        with self.assertRaises(RuntimeError) as ctx:
            OllamaProvider().embed(["a", "b"])

        self.assertIn("desalinhado", str(ctx.exception))

    @patch("bropilot_core.llm.requests.post")
    def test_generate_reports_missing_model_with_pull_command(self, mock_post):
        response = MagicMock()
        response.status_code = 404
        response.ok = False
        mock_post.return_value = response

        with self.assertRaises(RuntimeError) as ctx:
            OllamaProvider(chat_model="qwen2.5:7b-instruct-q4_K_M").generate("s", "u")

        self.assertIn("ollama pull qwen2.5:7b-instruct-q4_K_M", str(ctx.exception))

    @patch("bropilot_core.llm.requests.get")
    def test_health_check_when_ollama_is_down(self, mock_get):
        mock_get.side_effect = requests.exceptions.ConnectionError()

        with self.assertRaises(RuntimeError) as ctx:
            OllamaProvider().health_check()

        self.assertIn("ollama serve", str(ctx.exception))

    @patch("bropilot_core.llm.requests.get")
    def test_health_check_reports_which_model_is_missing(self, mock_get):
        # chat instalado, embed faltando
        mock_get.return_value = self._ok(
            {"models": [{"name": "qwen2.5:7b-instruct-q4_K_M"}]}
        )

        with self.assertRaises(RuntimeError) as ctx:
            OllamaProvider().health_check()

        message = str(ctx.exception)
        self.assertIn("ollama pull bge-m3", message)
        self.assertNotIn("ollama pull qwen2.5", message)  # esse está instalado

    @patch("bropilot_core.llm.requests.get")
    def test_health_check_accepts_latest_tag_for_untagged_model(self, mock_get):
        # /api/tags devolve "bge-m3:latest"; o config diz "bge-m3".
        # Sem normalizar, reportaria falta do que existe.
        mock_get.return_value = self._ok(
            {
                "models": [
                    {"name": "bge-m3:latest"},
                    {"name": "qwen2.5:7b-instruct-q4_K_M"},
                ]
            }
        )

        self.assertTrue(OllamaProvider().health_check())


class CreateProviderDefaultTest(unittest.TestCase):
    def test_default_backend_is_still_ollama_when_env_unset(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("BROPILOT_LLM", None)

            # Antes o OllamaProvider era scaffold e este teste provava o
            # default via NotImplementedError; agora que ele está implementado,
            # a prova é o tipo devolvido.
            self.assertIsInstance(create_provider(), OllamaProvider)

    def test_explicit_openai_selection_returns_openai_provider(self):
        provider = create_provider("openai")
        self.assertIsInstance(provider, OpenAIProvider)

    def test_env_var_selection_returns_openai_provider(self):
        with patch.dict(os.environ, {"BROPILOT_LLM": "openai"}):
            provider = create_provider()
            self.assertIsInstance(provider, OpenAIProvider)


if __name__ == "__main__":
    unittest.main()
