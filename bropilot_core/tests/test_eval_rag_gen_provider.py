"""Testes do run #5 (geração via nuvem, embedding sempre local): cobre a
função `_resolve_gen_provider` e a fiação de `main()` em `eval_rag.py`.

Nenhum destes testes toca rede — nem Ollama nem OpenAI. `create_provider`,
`Retriever`, `Orchestrator`, `_metadados_indice` e `executar` são todos
mockados. O que se prova aqui é a invariante crítica do run: o Retriever
SEMPRE recebe o provider de EMBEDDING (Ollama/bge-m3, o mesmo espaço vetorial
do índice), nunca o de geração — mesmo quando a geração vai para a OpenAI.
"""

from __future__ import annotations

import tempfile
import unittest
from unittest.mock import MagicMock, call, patch

from bropilot_core.scripts import eval_rag


class ResolveGenProviderTest(unittest.TestCase):
    """`_resolve_gen_provider` é o ponto único onde geração e embedding podem
    divergir — testado isolado, sem depender do resto de main()."""

    def test_without_gen_provider_name_reuses_the_embed_provider(self):
        embed_provider = MagicMock(name="embed_provider")

        with patch.object(eval_rag, "create_provider") as mock_create_provider:
            resultado = eval_rag._resolve_gen_provider(None, embed_provider)

        # Mesmo objeto, não uma cópia equivalente — é isto que preserva o
        # comportamento anterior (tudo-Ollama) byte a byte.
        self.assertIs(resultado, embed_provider)
        mock_create_provider.assert_not_called()
        embed_provider.health_check.assert_not_called()

    def test_with_gen_provider_name_creates_a_separate_instance(self):
        embed_provider = MagicMock(name="embed_provider(ollama)")
        gen_provider = MagicMock(name="gen_provider(openai)")

        with patch.object(
            eval_rag, "create_provider", return_value=gen_provider
        ) as mock_create_provider:
            resultado = eval_rag._resolve_gen_provider("openai", embed_provider)

        mock_create_provider.assert_called_once_with("openai")
        self.assertIs(resultado, gen_provider)
        # health_check roda no provider de GERAÇÃO...
        gen_provider.health_check.assert_called_once()
        # ...e o de EMBEDDING nunca é tocado por esta função.
        embed_provider.health_check.assert_not_called()
        embed_provider.embed.assert_not_called()
        embed_provider.generate.assert_not_called()

    def test_empty_string_gen_provider_name_also_reuses_embed_provider(self):
        # args.gen_provider=None e env var ausente resolvem para "" via
        # `args.gen_provider or os.environ.get(...)` só se ambos forem
        # falsy — cobrindo o caso de string vazia por segurança.
        embed_provider = MagicMock(name="embed_provider")
        resultado = eval_rag._resolve_gen_provider("", embed_provider)
        self.assertIs(resultado, embed_provider)


class MainGenProviderWiringTest(unittest.TestCase):
    """Fiação de `main()`: com --gen-provider openai, o Retriever tem que
    continuar recebendo o provider de EMBEDDING (o primeiro, default/Ollama)
    e o Orchestrator tem que receber o de GERAÇÃO (o segundo, OpenAI) — nunca
    o contrário e nunca o mesmo objeto nos dois papéis carregando o backend
    errado."""

    def _run_main_with_mocks(self, argv):
        embed_provider = MagicMock(name="embed_provider(ollama/bge-m3)")
        embed_provider.chat_model = "qwen2.5:7b-instruct-q4_K_M"
        embed_provider.temperature = 0.0
        embed_provider.seed = 42

        gen_provider = MagicMock(name="gen_provider(openai/gpt-4o-mini)")
        gen_provider.chat_model = "gpt-4o-mini"
        gen_provider.temperature = 0.0
        gen_provider.seed = 42

        def fake_create_provider(name=None, **kwargs):
            if name == "openai":
                return gen_provider
            return embed_provider

        fake_retriever_instance = MagicMock(name="retriever_instance")

        with tempfile.NamedTemporaryFile(suffix=".md") as tmp, patch.object(
            eval_rag, "create_provider", side_effect=fake_create_provider
        ) as mock_create_provider, patch.object(
            eval_rag, "Retriever", return_value=fake_retriever_instance
        ) as mock_retriever_cls, patch.object(
            eval_rag, "Orchestrator"
        ) as mock_orchestrator_cls, patch.object(
            eval_rag, "_metadados_indice"
        ) as mock_metadados, patch.object(
            eval_rag, "executar", return_value=[]
        ), patch.object(
            eval_rag, "gerar_relatorio", return_value="relatorio fake"
        ):
            mock_metadados.return_value = {
                "chunks": 1,
                "arquivos": 1,
                "arquivos_no_disco": 1,
                "source_types": None,
                "embed_model": "bge-m3",
                "embed_dim": 1024,
                "aviso": None,
            }

            rc = eval_rag.main(argv + ["--output", tmp.name])

        return {
            "rc": rc,
            "embed_provider": embed_provider,
            "gen_provider": gen_provider,
            "mock_create_provider": mock_create_provider,
            "mock_retriever_cls": mock_retriever_cls,
            "mock_orchestrator_cls": mock_orchestrator_cls,
        }

    def test_gen_provider_openai_keeps_retriever_on_embed_provider(self):
        resultado = self._run_main_with_mocks(["--gen-provider", "openai"])

        self.assertEqual(resultado["rc"], 0)

        # create_provider foi chamado 2x: uma vez default (embedding) e uma
        # vez explicitamente "openai" (geração).
        resultado["mock_create_provider"].assert_any_call()
        resultado["mock_create_provider"].assert_any_call("openai")

        # O Retriever recebeu o provider de EMBEDDING (default/Ollama) como
        # primeiro argumento posicional — nunca o de geração.
        retriever_args = resultado["mock_retriever_cls"].call_args
        self.assertIs(retriever_args[0][0], resultado["embed_provider"])

        # O Orchestrator recebeu o provider de GERAÇÃO (OpenAI) — nunca o de
        # embedding.
        orchestrator_args = resultado["mock_orchestrator_cls"].call_args
        self.assertIs(orchestrator_args[0][0], resultado["gen_provider"])

        # Nunca houve contaminação cruzada: o provider de embedding nunca
        # gerou texto, e o de geração nunca embedou nada.
        resultado["embed_provider"].generate.assert_not_called()
        resultado["gen_provider"].embed.assert_not_called()

    def test_without_gen_provider_reuses_single_provider_for_both_roles(self):
        """Comportamento anterior preservado: sem --gen-provider, Retriever e
        Orchestrator recebem o MESMO objeto (tudo-Ollama)."""
        resultado = self._run_main_with_mocks([])

        self.assertEqual(resultado["rc"], 0)

        retriever_args = resultado["mock_retriever_cls"].call_args
        orchestrator_args = resultado["mock_orchestrator_cls"].call_args
        self.assertIs(retriever_args[0][0], resultado["embed_provider"])
        self.assertIs(orchestrator_args[0][0], resultado["embed_provider"])

        # create_provider("openai") nunca é chamado neste caminho.
        chamadas = resultado["mock_create_provider"].call_args_list
        self.assertNotIn(call("openai"), chamadas)


if __name__ == "__main__":
    unittest.main()
