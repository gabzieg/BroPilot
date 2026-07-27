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

Etapa 2: OpenAIProvider (GPT-4o-mini via API oficial da OpenAI). Selecionável
no boot pela env var BROPILOT_LLM=ollama|openai (default ollama) via
`create_provider()` — ver essa função no fim do módulo. Importante: embed()
do OpenAIProvider NÃO usa a OpenAI, continua delegando ao Ollama/nomic-embed-
text, porque o índice vetorial já existente foi construído com esse modelo
(ver DECISION.md e index/build.py). Geração e embedding têm back-ends
independentes nesta etapa.
"""

from __future__ import annotations

import os
from typing import Protocol, Sequence

import requests


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


class OpenAIProvider:
    """Implementação em nuvem do LLMProvider (Fase 2 do roadmap): geração via
    GPT-4o-mini pela API oficial da OpenAI, chamada via HTTP puro (`requests`)
    — mesmo estilo do OllamaProvider, sem adicionar o SDK `openai` como
    dependência nova.

    embed() NÃO usa a OpenAI. O índice vetorial existente foi construído com
    nomic-embed-text via Ollama (ver `index/build.py` e `DECISION.md`); trocar
    o modelo de embedding aqui produziria um espaço vetorial incompatível e o
    retrieval voltaria lixo sem erro nenhum. Por isso embed() delega a um
    LLMProvider local injetado (default: OllamaProvider com os defaults de
    sempre) — geração e embedding têm back-ends independentes nesta fase.
    """

    _DEFAULT_BASE_URL = "https://api.openai.com/v1"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        chat_model: str = "gpt-4o-mini",
        base_url: str = _DEFAULT_BASE_URL,
        timeout_s: float = 60.0,
        embed_provider: "LLMProvider | None" = None,
    ) -> None:
        """Guarda config; não faz chamada de rede aqui (ver health_check).

        api_key vem de OPENAI_API_KEY quando não passada explicitamente —
        nunca hardcode a chave. embed_provider é construído sob demanda (lazy,
        em embed()) para não instanciar/tocar o Ollama só porque alguém criou
        um OpenAIProvider para gerar texto.
        """
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self._chat_model = chat_model
        self._base_url = base_url.rstrip("/")
        self._timeout_s = timeout_s
        self._embed_provider = embed_provider

    def _require_api_key(self, context: str) -> str:
        if not self._api_key:
            raise RuntimeError(
                "OPENAI_API_KEY não definida. Exporte a variável de ambiente "
                f"com sua chave da OpenAI antes de {context} "
                "(export OPENAI_API_KEY=sk-...)."
            )
        return self._api_key

    def generate(self, system: str, user: str) -> str:
        """POST {base_url}/chat/completions com messages=[system, user].

        Trata: key ausente/errada (401 -> mensagem clara), API fora do ar
        (erro de conexão -> mensagem clara), e timeout — mesmo espírito do
        tratamento de erros do OllamaProvider, nunca stack trace cru.
        """
        api_key = self._require_api_key("gerar uma resposta")

        try:
            response = requests.post(
                f"{self._base_url}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": self._chat_model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                },
                timeout=self._timeout_s,
            )
        except requests.exceptions.Timeout as exc:
            raise RuntimeError(
                f"OpenAI não respondeu em {self._timeout_s}s. Tente de novo "
                "ou aumente timeout_s."
            ) from exc
        except requests.exceptions.ConnectionError as exc:
            raise RuntimeError(
                f"Não foi possível conectar em {self._base_url} — confira a "
                "rede ou o base_url configurado."
            ) from exc

        if response.status_code == 401:
            raise RuntimeError(
                "OpenAI recusou a OPENAI_API_KEY (401). Confira se a chave é "
                f"válida e tem acesso ao modelo '{self._chat_model}'."
            )
        if not response.ok:
            raise RuntimeError(
                f"Erro na API da OpenAI ({response.status_code}): "
                f"{response.text[:500]}"
            )

        return response.json()["choices"][0]["message"]["content"]

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Delega ao embed_provider local (Ollama/nomic-embed-text) — ver a
        docstring da classe para a razão de não usar embeddings da OpenAI."""
        if self._embed_provider is None:
            self._embed_provider = OllamaProvider()
        return self._embed_provider.embed(texts)

    def health_check(self) -> bool:
        """API key configurada e a API responde? Chamado no boot do CLI para
        falhar cedo com mensagem útil (mesmo padrão do OllamaProvider), em vez
        de estourar no meio da primeira pergunta do jogador."""
        api_key = self._require_api_key("rodar o health check")

        try:
            response = requests.get(
                f"{self._base_url}/models/{self._chat_model}",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=self._timeout_s,
            )
        except requests.exceptions.Timeout as exc:
            raise RuntimeError(
                f"OpenAI não respondeu em {self._timeout_s}s no health check."
            ) from exc
        except requests.exceptions.ConnectionError as exc:
            raise RuntimeError(
                f"Não foi possível conectar em {self._base_url} no health "
                "check — confira a rede ou o base_url configurado."
            ) from exc

        if response.status_code == 401:
            raise RuntimeError(
                "OpenAI recusou a OPENAI_API_KEY (401) no health check."
            )
        if not response.ok:
            raise RuntimeError(
                f"Health check da OpenAI falhou ({response.status_code}): "
                f"{response.text[:500]}"
            )

        return True


def create_provider(name: str | None = None) -> LLMProvider:
    """Escolhe o back-end de geração no boot: 'ollama' (default) ou 'openai'.

    `name` explícito tem prioridade; senão lê a env var BROPILOT_LLM; senão
    'ollama'. É este o ÚNICO ponto de seleção — quem constrói o Orchestrator
    (build_default_orchestrator / cli.py) chama isto antes de instanciar o
    Orchestrator, que continua recebendo o provider já pronto por injeção.
    """
    resolved = (name or os.environ.get("BROPILOT_LLM") or "ollama").strip().lower()

    if resolved == "ollama":
        return OllamaProvider()
    if resolved == "openai":
        return OpenAIProvider()

    raise ValueError(
        f"Provider de LLM desconhecido: '{resolved}'. Use 'ollama' ou 'openai' "
        "(env var BROPILOT_LLM ou parâmetro explícito)."
    )
