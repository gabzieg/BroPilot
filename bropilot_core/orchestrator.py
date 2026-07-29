"""Orquestrador — junta os três motores numa resposta. É o que o CLI (e depois a
UI Electron) chamam. Nenhum dos subsistemas originais importa este módulo; a
dependência é sempre daqui para eles.

Uma query, ponta a ponta:
    1. lê o estado do save (SaveContext) — via SaveParser
    2. serialize_party() -> ficha de texto  +  extract_signals() -> chaves de busca
    3. retriever.search(pergunta, signals) -> top-k chunks da base
    4. monta o prompt: persona + ficha da party + chunks recuperados + pergunta
    5. llm.generate() -> resposta

Repare que o estado do save entra DUAS vezes e com papéis diferentes: como texto
no prompt (o modelo "vê" a party) e como sinal de busca (dirige o retrieval). Não
é redundância — é o design state-aware.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import tiktoken

from .index.retriever import RetrievedChunk, Retriever
from .llm import create_provider
from .serialize import extract_signals, serialize_party

if TYPE_CHECKING:
    from bropilot import SaveContext
    from .llm import LLMProvider


# Mesma encoding usada em index/build.py e pela mesma razão: é aproximação para
# o tokenizer do qwen, usada como MEDIDA DE TAMANHO para caber na janela, não
# como contrato com o modelo. Errar para mais é seguro; o que não pode é o
# prompt estourar a janela e ser truncado sem aviso.
_ENCODING = tiktoken.get_encoding("cl100k_base")

# Teto do prompt. Deixa folga dentro do num_ctx do provider (8192) para a
# RESPOSTA — orçar o prompt inteiro até o limite da janela não deixaria espaço
# para o modelo escrever.
DEFAULT_MAX_PROMPT_TOKENS = 5000


# Persona do BroPilot. Fica aqui, não hardcoded no meio da lógica, para ser fácil
# de afinar por modelo (modelos diferentes respondem a prompts diferentes — a
# abstração troca o back-end de graça, mas o prompt é afinado por modelo).
SYSTEM_PERSONA = (
    "Você é o BroPilot, copiloto de min-maxing de Baldur's Gate 3. "
    "Raciocine sobre as regras (D&D 5e adaptado) com precisão; foque em "
    "action economy, damage riders e sinergias de build. Use o CONTEXTO "
    "recuperado e o ESTADO DA PARTY como fonte de verdade — se algo não estiver "
    "neles, diga que não sabe em vez de inventar. Fale como um parceiro de "
    "jogatina (bro), mas seja tecnicamente exato."
)


def _count_tokens(text: str) -> int:
    return len(_ENCODING.encode(text))


def _render_chunk(position: int, chunk: RetrievedChunk) -> str:
    """Cada chunk vai rotulado com o arquivo de origem para o modelo poder
    citar a fonte, e para a resposta ser auditável contra a base."""
    return f"\n[{position}] fonte: {chunk.source_file}\n{chunk.text}"


@dataclass
class Answer:
    """Resposta do orquestrador + rastro para depuração/citação."""
    text: str
    sources: list[str]        # arquivos que alimentaram o prompt
    party_had_live_stats: bool  # False = resposta com fidelidade degradada (sem mod)


class Orchestrator:
    """Fachada única do sistema integrado. CLI e UI só conhecem esta classe."""

    def __init__(
        self,
        llm: "LLMProvider",
        retriever: "Retriever",
        *,
        max_prompt_tokens: int = DEFAULT_MAX_PROMPT_TOKENS,
        k: int = 6,
    ) -> None:
        """Injeção de dependência de propósito: quem constrói o Orchestrator
        escolhe o provider (Ollama hoje, outro amanhã) e o retriever. O
        orquestrador não instancia back-end nenhum — só os usa.

        Públicos de propósito: o CLI precisa do provider para o health_check do
        boot sem construir um segundo.
        """
        self.llm = llm
        self.retriever = retriever
        self.max_prompt_tokens = max_prompt_tokens
        self.k = k

    def ask(self, question: str, ctx: "SaveContext | None" = None) -> Answer:
        """O método principal. Executa os 5 passos do docstring do módulo.

        `ctx` é OPCIONAL: sem save carregado o sistema responde igual, só com a
        base de conhecimento (é o modo desta fase). Com save sem snapshot do
        mod, a ficha da party é magra (só nível/raça/classe) e
        `Answer.party_had_live_stats` sai False — degradando com honestidade,
        nunca inventando stats.
        """
        # O estado do save entra DUAS vezes, com papéis diferentes: como
        # sinais que dirigem a busca, e como texto que o modelo lê. Ver o
        # docstring do módulo — é o design state-aware, não redundância.
        signals = extract_signals(ctx) if ctx is not None else None
        party_text = serialize_party(ctx) if ctx is not None else ""

        chunks = self.retriever.search(question, signals=signals, k=self.k)

        used = self._fit_chunks(chunks, party_text, question)
        system, user = self._build_prompt(question, party_text, used)
        text = self.llm.generate(system, user)

        # Fontes = o que REALMENTE alimentou o prompt (pós-corte), deduplicado
        # preservando a ordem de relevância. Citar um arquivo que foi cortado
        # por orçamento seria mentir sobre o que embasou a resposta.
        sources = list(dict.fromkeys(c.source_file for c in used))

        return Answer(
            text=text,
            sources=sources,
            party_had_live_stats=bool(signals and signals.get("has_live_stats")),
        )

    def _fit_chunks(
        self, chunks: list[RetrievedChunk], party_text: str, question: str
    ) -> list[RetrievedChunk]:
        """Quais chunks cabem no orçamento, do mais relevante para o menos.

        Corta pelo FIM (os chunks vêm ordenados por score), então o que se
        perde é sempre o menos relevante. O estado da party e a pergunta nunca
        são cortados — se só eles já estouram o teto, seguem mesmo assim, sem
        chunk nenhum: é melhor responder com a party e sem contexto do que
        descartar o estado do jogador.
        """
        fixed = self._render_prompt(question, party_text, [])
        budget = self.max_prompt_tokens - _count_tokens(fixed)

        used: list[RetrievedChunk] = []
        spent = 0
        for chunk in chunks:
            cost = _count_tokens(_render_chunk(len(used) + 1, chunk))
            if spent + cost > budget:
                break
            used.append(chunk)
            spent += cost
        return used

    def _build_prompt(
        self, question: str, party_text: str, chunks: list
    ) -> tuple[str, str]:
        """Monta (system, user) final. Ponto onde o orçamento de contexto é
        respeitado: se party_text + chunks + pergunta passar do teto do modelo
        local, corta chunks pela relevância (nunca corta o estado da party)."""
        used = self._fit_chunks(chunks, party_text, question)
        return SYSTEM_PERSONA, self._render_prompt(question, party_text, used)

    def _render_prompt(
        self, question: str, party_text: str, chunks: list[RetrievedChunk]
    ) -> str:
        """Serializa a mensagem do usuário. Seções bem demarcadas para o modelo
        distinguir o que é material recuperado, o que é estado do jogo e o que
        é a pergunta — misturar os três é o caminho curto para o modelo tratar
        a pergunta como contexto."""
        blocks = ["=== CONTEXTO RECUPERADO DA BASE ==="]
        if chunks:
            blocks.extend(
                _render_chunk(i, c) for i, c in enumerate(chunks, start=1)
            )
        else:
            blocks.append("(nada recuperado para esta pergunta)")

        blocks.append("\n=== ESTADO DA PARTY ===")
        blocks.append(
            party_text
            or "(nenhum save carregado — responda de forma geral e não invente "
               "detalhes da party)"
        )

        blocks.append("\n=== PERGUNTA ===")
        blocks.append(question)
        return "\n".join(blocks)


def build_default_orchestrator(
    *,
    llm_provider: str | None = None,
    ollama_host: str = "http://localhost:11434",
    store_dir: Path | None = None,
    llm: "LLMProvider | None" = None,
) -> "Orchestrator":
    """Monta o Orchestrator com os defaults do MVP (Ollama local + LanceDB).

    É o único lugar que sabe COMO montar a stack concreta — o resto do código
    fala com interfaces. `llm_provider` ("ollama" | "openai"; default lê a env
    var BROPILOT_LLM, senão "ollama") escolhe o back-end de geração via
    `llm.create_provider()` — é aqui, e só aqui, que a etapa 2 (modelo de
    custo baixo via API) se pluga; o Orchestrator continua recebendo o
    provider já pronto por injeção, sem saber qual back-end é.

    `llm` já construído pode ser passado para evitar instanciar dois providers
    quando o chamador precisou de um antes (o CLI faz health_check no boot).
    """
    provider = llm or create_provider(llm_provider, ollama_host=ollama_host)
    retriever = Retriever(provider, store_dir) if store_dir else Retriever(provider)
    return Orchestrator(provider, retriever)
