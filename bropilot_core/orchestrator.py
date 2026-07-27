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

if TYPE_CHECKING:
    from bropilot import SaveContext
    from .llm import LLMProvider
    from .index.retriever import Retriever


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


@dataclass
class Answer:
    """Resposta do orquestrador + rastro para depuração/citação."""
    text: str
    sources: list[str]        # arquivos que alimentaram o prompt
    party_had_live_stats: bool  # False = resposta com fidelidade degradada (sem mod)


class Orchestrator:
    """Fachada única do sistema integrado. CLI e UI só conhecem esta classe."""

    def __init__(self, llm: "LLMProvider", retriever: "Retriever") -> None:
        """Injeção de dependência de propósito: quem constrói o Orchestrator
        escolhe o provider (Ollama hoje, outro amanhã) e o retriever. O
        orquestrador não instancia back-end nenhum — só os usa."""
        raise NotImplementedError("scaffold")

    def ask(self, question: str, ctx: "SaveContext") -> Answer:
        """O método principal. Executa os 5 passos do docstring do módulo.

        `ctx` pode vir sem snapshot do mod: nesse caso a ficha da party é magra
        (só nível/raça/classe) e `Answer.party_had_live_stats` sai False — o
        sistema responde mesmo assim, degradando com honestidade.
        """
        raise NotImplementedError("scaffold")

    def _build_prompt(
        self, question: str, party_text: str, chunks: list
    ) -> tuple[str, str]:
        """Monta (system, user) final. Ponto onde o orçamento de contexto é
        respeitado: se party_text + chunks + pergunta passar do teto do modelo
        local, corta chunks pela relevância (nunca corta o estado da party)."""
        raise NotImplementedError("scaffold")


def build_default_orchestrator(
    *,
    ollama_host: str = "http://localhost:11434",
    store_dir: Path | None = None,
) -> "Orchestrator":
    """Monta o Orchestrator com os defaults do MVP (Ollama local + LanceDB).

    É o único lugar que sabe COMO montar a stack concreta — o resto do código
    fala com interfaces. A etapa 2 (modelo de custo baixo via API) troca este
    factory, e nada mais.
    """
    raise NotImplementedError("scaffold")
