"""Testes mínimos do OpenAIProvider e da seleção de back-end (create_provider).

Não há suíte de testes no repo ainda (ver CLAUDE.md) — este arquivo cobre só o
que foi pedido ao adicionar o back-end OpenAI: health_check falhando com
mensagem clara sem tocar rede de verdade, e o default de back-end permanecendo
Ollama quando BROPILOT_LLM não está setada.
"""

from __future__ import annotations

import os
import unittest
from unittest.mock import MagicMock, patch

from bropilot_core.llm import OpenAIProvider, create_provider


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


class CreateProviderDefaultTest(unittest.TestCase):
    def test_default_backend_is_still_ollama_when_env_unset(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("BROPILOT_LLM", None)

            # OllamaProvider ainda é scaffold (__init__ levanta
            # NotImplementedError) — isso É a prova de que create_provider()
            # tentou construir Ollama, e não OpenAI, quando BROPILOT_LLM não
            # está setada. Se o default tivesse virado "openai" sem querer,
            # esta linha não levantaria nada (OpenAIProvider() não falha
            # eager no __init__ mesmo sem key).
            with self.assertRaises(NotImplementedError):
                create_provider()

    def test_explicit_openai_selection_returns_openai_provider(self):
        provider = create_provider("openai")
        self.assertIsInstance(provider, OpenAIProvider)

    def test_env_var_selection_returns_openai_provider(self):
        with patch.dict(os.environ, {"BROPILOT_LLM": "openai"}):
            provider = create_provider()
            self.assertIsInstance(provider, OpenAIProvider)


if __name__ == "__main__":
    unittest.main()
