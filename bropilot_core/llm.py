"""Camada de LLM e embeddings — abstração fininha sobre o back-end.

Por que esta abstração existe, já que o MVP é só Ollama: o roadmap tem duas
etapas ("MVP local, depois um modelo de custo baixo via API"). Essas duas etapas
SÃO dois back-ends. Sem esta fronteira, a etapa 2 vira caça a `ollama.chat(...)`
espalhado pelo código; com ela, é trocar uma classe. Custo da abstração: ~20
linhas. Custo de não tê-la: a etapa 2 inteira. Não é over-engineering — é o
próprio roadmap do projeto pedindo a costura.

MVP: OllamaProvider, tudo local, mesma GPU do jogo. Implicações que a
implementação PRECISA respeitar (setup "mesma máquina do BG3"):
- Modelo de geração pequeno/quantizado (ex.: qwen2.5:7b-instruct-q4_K_M) para
  não brigar por VRAM com o jogo aberto.
- Embeddings via nomic-embed-text (também no Ollama) — zero dependência nova, um
  runtime só serve LLM e embeddings.
- Host configurável (default http://localhost:11434); a etapa 2 aponta o mesmo
  método para um endpoint remoto sem tocar no resto.
"""

from __future__ import annotations

from typing import Protocol, Sequence


class LLMProvider(Protocol):
    """Contrato mínimo que o orquestrador conhece. Nada aqui menciona Ollama.

    Trocar de back-end (etapa 2) = fornecer outra classe que satisfaça este
    Protocol. O orquestrador não muda.
    """

    def generate(self, system: str, user: str) -> str:
        """Uma volta de inferência. system = persona + contexto RAG; user = pergunta.

        Síncrono e sem streaming no scaffold — o CLI de MVP não precisa de stream.
        Streaming vira uma variante depois, quando a UI exigir resposta incremental.
        """
        ...

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Vetoriza um lote de textos. Usado tanto na indexação (chunks) quanto
        no runtime (a pergunta). Mesmo modelo dos dois lados, senão o espaço
        vetorial não bate."""
        ...


class OllamaProvider:
    """Implementação local do LLMProvider via API HTTP do Ollama.

    Não instancia nada de pesado no __init__ — só guarda config. O Ollama já
    mantém o modelo carregado no seu próprio processo; aqui é só cliente HTTP.
    """

    def __init__(
        self,
        *,
        host: str = "http://localhost:11434",
        chat_model: str = "qwen2.5:7b-instruct-q4_K_M",
        embed_model: str = "nomic-embed-text",
        timeout_s: float = 120.0,
    ) -> None:
        """Guarda config. Ver docstring do módulo para a razão dos defaults
        (VRAM compartilhada com o BG3)."""
        raise NotImplementedError("scaffold")

    def generate(self, system: str, user: str) -> str:
        """POST /api/chat com messages=[system, user]. Retorna o texto da resposta.

        Deve tratar: Ollama offline (erro claro "suba o ollama serve"), modelo
        não baixado (erro "rode ollama pull <model>"), e timeout.
        """
        raise NotImplementedError("scaffold")

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """POST /api/embed em lote. Retorna um vetor por texto, na mesma ordem."""
        raise NotImplementedError("scaffold")

    def health_check(self) -> bool:
        """Ollama no ar e ambos os modelos disponíveis? Chamado no boot do CLI
        para falhar cedo com mensagem útil, em vez de estourar no meio da query."""
        raise NotImplementedError("scaffold")
