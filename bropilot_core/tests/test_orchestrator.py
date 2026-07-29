"""Testes do Orchestrator e do boot do CLI. llm e retriever são sempre
mockados — nenhuma chamada ao Ollama nem ao índice real.
"""

from __future__ import annotations

import io
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import MagicMock, patch

from bropilot_core import cli
from bropilot_core.index.retriever import RetrievedChunk
from bropilot_core.orchestrator import (
    SYSTEM_PERSONA,
    Answer,
    Orchestrator,
    StreamedAnswer,
    _count_tokens,
)


def _chunk(text, source_file, score=0.5):
    return RetrievedChunk(
        text=text,
        source_file=source_file,
        score=score,
        base_score=score,
        source_type="wiki",
    )


class _FakeRetriever:
    def __init__(self, chunks):
        self.chunks = chunks
        self.calls = []

    def search(self, query, *, signals=None, k=6):
        self.calls.append({"query": query, "signals": signals, "k": k})
        return list(self.chunks)


class _FakeLLM:
    def __init__(self, reply="resposta do modelo"):
        self.reply = reply
        self.calls = []
        self.stream_calls = []

    @property
    def embed_model(self):
        return "bge-m3"

    def embed(self, texts):
        return [[0.0] for _ in texts]

    def generate(self, system, user):
        self.calls.append({"system": system, "user": user})
        return self.reply

    def generate_stream(self, system, user):
        # pedaços óbvios de reconhecer no teste: a resposta fatiada em 2.
        self.stream_calls.append({"system": system, "user": user})
        meio = len(self.reply) // 2
        for pedaco in (self.reply[:meio], self.reply[meio:]):
            if pedaco:
                yield pedaco


class AskWithoutContextTest(unittest.TestCase):
    def setUp(self):
        self.retriever = _FakeRetriever(
            [_chunk("texto A", "a.md", 0.9), _chunk("texto B", "b.md", 0.8)]
        )
        self.llm = _FakeLLM()
        self.orch = Orchestrator(self.llm, self.retriever)

    def test_answers_without_ctx(self):
        answer = self.orch.ask("qual a melhor build?")

        self.assertIsInstance(answer, Answer)
        self.assertEqual(answer.text, "resposta do modelo")
        self.assertEqual(answer.sources, ["a.md", "b.md"])
        self.assertFalse(answer.party_had_live_stats)

    def test_uses_persona_as_system_prompt(self):
        self.orch.ask("pergunta")

        self.assertEqual(self.llm.calls[0]["system"], SYSTEM_PERSONA)

    def test_user_prompt_separates_context_party_and_question(self):
        self.orch.ask("como funciona sneak attack?")

        user = self.llm.calls[0]["user"]
        self.assertIn("=== CONTEXTO RECUPERADO DA BASE ===", user)
        self.assertIn("=== ESTADO DA PARTY ===", user)
        self.assertIn("=== PERGUNTA ===", user)
        self.assertIn("como funciona sneak attack?", user)
        # sem save: diz explicitamente, para o modelo não inventar party
        self.assertIn("nenhum save carregado", user)

    def test_sources_are_deduplicated(self):
        self.retriever.chunks = [
            _chunk("primeiro trecho", "mesmo.md", 0.9),
            _chunk("segundo trecho", "mesmo.md", 0.8),
            _chunk("outro arquivo", "outro.md", 0.7),
        ]

        answer = self.orch.ask("pergunta")

        self.assertEqual(answer.sources, ["mesmo.md", "outro.md"])

    def test_passes_k_to_retriever(self):
        self.orch.k = 3
        self.orch.ask("pergunta")

        self.assertEqual(self.retriever.calls[0]["k"], 3)


class AskStreamTest(unittest.TestCase):
    """ask_stream() precisa ter os MESMOS metadados de ask() (sources, boost,
    orçamento) — só o transporte da resposta muda de string pra iterator."""

    def setUp(self):
        self.retriever = _FakeRetriever(
            [_chunk("texto A", "a.md", 0.9), _chunk("texto B", "b.md", 0.8)]
        )
        self.llm = _FakeLLM(reply="use Tavern Brawler")
        self.orch = Orchestrator(self.llm, self.retriever)

    def test_returns_streamed_answer_with_same_sources_as_ask(self):
        streamed = self.orch.ask_stream("qual a melhor build?")

        self.assertIsInstance(streamed, StreamedAnswer)
        self.assertEqual(streamed.sources, ["a.md", "b.md"])
        self.assertFalse(streamed.party_had_live_stats)

    def test_chunks_concatenate_into_the_full_reply(self):
        streamed = self.orch.ask_stream("qual a melhor build?")

        self.assertEqual("".join(streamed.chunks), "use Tavern Brawler")

    def test_sources_are_known_before_any_chunk_is_consumed(self):
        # a garantia central de StreamedAnswer: sources não depende de
        # esgotar `chunks` — já vem pronto no objeto de retorno.
        streamed = self.orch.ask_stream("pergunta")

        self.assertEqual(streamed.sources, ["a.md", "b.md"])
        self.assertEqual(self.llm.stream_calls, [])  # generate_stream() nem foi chamado ainda

        list(streamed.chunks)  # só agora a geração roda de fato

        self.assertEqual(len(self.llm.stream_calls), 1)

    def test_uses_same_prompt_building_as_ask(self):
        streamed = self.orch.ask_stream("como funciona sneak attack?")
        list(streamed.chunks)  # generate_stream() é preguiçoso — precisa consumir

        user = self.llm.stream_calls[0]["user"]
        self.assertEqual(self.llm.stream_calls[0]["system"], SYSTEM_PERSONA)
        self.assertIn("=== CONTEXTO RECUPERADO DA BASE ===", user)
        self.assertIn("como funciona sneak attack?", user)


class PromptBudgetTest(unittest.TestCase):
    def test_drops_least_relevant_chunks_to_respect_budget(self):
        # 10 chunks gordos; o teto só comporta alguns.
        chunks = [
            _chunk("palavra " * 200, f"arquivo_{i}.md", score=1.0 - i / 100)
            for i in range(10)
        ]
        retriever = _FakeRetriever(chunks)
        llm = _FakeLLM()
        orch = Orchestrator(llm, retriever, max_prompt_tokens=900)

        answer = orch.ask("pergunta curta")

        user = llm.calls[0]["user"]
        self.assertLessEqual(_count_tokens(SYSTEM_PERSONA) + _count_tokens(user), 900)
        # cortou pelo fim: sobraram os primeiros (mais relevantes)
        self.assertLess(len(answer.sources), 10)
        self.assertEqual(answer.sources[0], "arquivo_0.md")
        self.assertNotIn("arquivo_9.md", answer.sources)

    def test_sources_reflect_only_chunks_that_survived_the_cut(self):
        chunks = [
            _chunk("palavra " * 200, f"arquivo_{i}.md", score=1.0 - i / 100)
            for i in range(10)
        ]
        llm = _FakeLLM()
        orch = Orchestrator(llm, _FakeRetriever(chunks), max_prompt_tokens=900)

        answer = orch.ask("pergunta")

        user = llm.calls[0]["user"]
        for source in answer.sources:
            self.assertIn(source, user)  # citou => estava no prompt
        for cortado in set(c.source_file for c in chunks) - set(answer.sources):
            self.assertNotIn(cortado, user)  # não citou => não estava

    def test_question_survives_even_when_budget_is_tiny(self):
        # orçamento absurdo: nenhum chunk cabe, mas a pergunta não pode sumir.
        chunks = [_chunk("palavra " * 500, "gordo.md", 0.9)]
        llm = _FakeLLM()
        orch = Orchestrator(llm, _FakeRetriever(chunks), max_prompt_tokens=50)

        answer = orch.ask("minha pergunta importante")

        self.assertIn("minha pergunta importante", llm.calls[0]["user"])
        self.assertEqual(answer.sources, [])


class CliBootTest(unittest.TestCase):
    def test_health_check_failure_prints_actionable_message_without_traceback(self):
        provider = MagicMock()
        provider.health_check.side_effect = RuntimeError(
            "Ollama não está no ar em http://localhost:11434. "
            "Suba o serviço com `ollama serve` e tente de novo."
        )

        err = io.StringIO()
        with patch("bropilot_core.cli.create_provider", return_value=provider):
            with redirect_stderr(err):
                code = cli.main([])

        self.assertEqual(code, 1)
        self.assertIn("ollama serve", err.getvalue())
        self.assertNotIn("Traceback", err.getvalue())

    def test_missing_index_is_reported_cleanly(self):
        provider = MagicMock()
        provider.health_check.return_value = True

        err = io.StringIO()
        with patch("bropilot_core.cli.create_provider", return_value=provider), patch(
            "bropilot_core.cli.build_default_orchestrator",
            side_effect=RuntimeError("Índice não encontrado. rode bropilot_core.index.build"),
        ):
            with redirect_stderr(err):
                code = cli.main([])

        self.assertEqual(code, 1)
        self.assertIn("bropilot_core.index.build", err.getvalue())
        self.assertNotIn("Traceback", err.getvalue())


class CliLoopTest(unittest.TestCase):
    def _run(self, entradas, chunks=("use Tavern ", "Brawler"),
              sources=("build_monk_openhand.md",)):
        provider = MagicMock()
        provider.health_check.return_value = True
        orchestrator = MagicMock()
        orchestrator.ask_stream.return_value = StreamedAnswer(
            chunks=iter(chunks), sources=list(sources), party_had_live_stats=False,
        )

        out = io.StringIO()
        with patch("bropilot_core.cli.create_provider", return_value=provider), patch(
            "bropilot_core.cli.build_default_orchestrator", return_value=orchestrator
        ), patch("builtins.input", side_effect=entradas):
            with redirect_stdout(out):
                code = cli.main([])
        return code, out.getvalue(), orchestrator

    def test_prints_answer_and_sources(self):
        code, saida, _ = self._run(["qual feat pegar?", "sair"])

        self.assertEqual(code, 0)
        # os pedaços chegam concatenados na tela, sem quebra entre eles
        self.assertIn("use Tavern Brawler", saida)
        # a regra: resposta NUNCA sai sem as fontes
        self.assertIn("build_monk_openhand.md", saida)

    def test_exits_cleanly_on_ctrl_d(self):
        code, saida, _ = self._run([EOFError()])

        self.assertEqual(code, 0)
        self.assertIn("até a próxima", saida)

    def test_exits_cleanly_on_ctrl_c_at_prompt(self):
        code, saida, _ = self._run([KeyboardInterrupt()])

        self.assertEqual(code, 0)

    def test_ctrl_c_mid_stream_stops_cleanly_and_returns_to_prompt(self):
        # Ctrl+C durante a GERAÇÃO (iterando streamed.chunks), não no input().
        # Simula com um iterator que levanta KeyboardInterrupt no meio.
        def chunks_interrompidos():
            yield "começo da resposta"
            raise KeyboardInterrupt

        provider = MagicMock()
        provider.health_check.return_value = True
        orchestrator = MagicMock()
        orchestrator.ask_stream.return_value = StreamedAnswer(
            chunks=chunks_interrompidos(), sources=["a.md"], party_had_live_stats=False,
        )

        out = io.StringIO()
        with patch("bropilot_core.cli.create_provider", return_value=provider), patch(
            "bropilot_core.cli.build_default_orchestrator", return_value=orchestrator
        ), patch("builtins.input", side_effect=["pergunta", "sair"]):
            with redirect_stdout(out):
                code = cli.main([])

        self.assertEqual(code, 0)
        saida = out.getvalue()
        self.assertIn("começo da resposta", saida)   # o que já tinha chegado ficou na tela
        self.assertIn("geração interrompida", saida)
        self.assertNotIn("Traceback", saida)
        self.assertNotIn("a.md", saida)               # interrompeu antes das fontes
        self.assertIn("até a próxima", saida)          # voltou ao prompt e seguiu até 'sair'

    def test_blank_input_does_not_call_the_model(self):
        code, _, orchestrator = self._run(["", "   ", "sair"])

        self.assertEqual(code, 0)
        orchestrator.ask_stream.assert_not_called()


if __name__ == "__main__":
    unittest.main()
