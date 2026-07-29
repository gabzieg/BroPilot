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
- Embeddings via bge-m3 (também no Ollama) — zero dependência nova, um runtime
  só serve LLM e embeddings. bge-m3 e não nomic-embed-text porque a base é
  quase toda em inglês mas as perguntas vêm em português: medido, o nomic dá
  similaridade 0.443 entre "dano desarmado" e "unarmed damage" contra 0.380 de
  um par não-relacionado — separação perto de zero, retrieval vira sorteio. O
  bge-m3 é multilíngue e leva o mesmo par a 0.723 contra 0.282 do controle.
- Host configurável (default http://localhost:11434); a etapa 2 aponta o mesmo
  método para um endpoint remoto sem tocar no resto.

Etapa 2: OpenAIProvider (GPT-4o-mini via API oficial da OpenAI). Selecionável
no boot pela env var BROPILOT_LLM=ollama|openai (default ollama) via
`create_provider()` — ver essa função no fim do módulo.

Decisão de MVP revista para full-cloud (DECISION.md/README.md ainda descrevem
a versão anterior, local-only, e precisam de atualização): embed() do
OpenAIProvider usa de verdade a API de embeddings da OpenAI
(text-embedding-3-small) — não delega mais ao Ollama. Geração e embedding
compartilham o mesmo back-end nesta etapa. Um índice já construído com
nomic-embed-text é incompatível com este espaço vetorial e precisa ser
reconstruído (`build_index(rebuild=True)`) antes do retriever poder usá-lo.
"""

from __future__ import annotations

import json
import os
from typing import Iterator, Protocol, Sequence

import requests


class LLMProvider(Protocol):
    """Contrato mínimo que o orquestrador conhece. Nada aqui menciona Ollama.

    Trocar de back-end (etapa 2) = fornecer outra classe que satisfaça este
    Protocol. O orquestrador não muda.
    """

    def generate(self, system: str, user: str) -> str:
        """Uma volta de inferência. system = persona + contexto RAG; user = pergunta.

        Síncrono, devolve o texto inteiro de uma vez. É o que eval_rag.py e a
        suíte de testes consomem — não precisam de streaming, só do resultado
        final. Ver generate_stream() para o caminho incremental.
        """
        ...

    def generate_stream(self, system: str, user: str) -> Iterator[str]:
        """Como generate(), mas produz PEDAÇOS de texto conforme chegam do
        back-end, em vez do texto inteiro de uma vez ao final.

        Existe para latência PERCEBIDA, não para latência real: o tempo total
        de geração não muda, mas quem está lendo vê a resposta se formando em
        vez de encarar um prompt vazio por ~60s — é o que decide se dá pra
        usar isto junto com o jogo aberto. generate() continua existindo e
        continua sendo o caminho que eval_rag.py e os testes usam.
        """
        ...

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Vetoriza um lote de textos. Usado tanto na indexação (chunks) quanto
        no runtime (a pergunta). Mesmo modelo dos dois lados, senão o espaço
        vetorial não bate."""
        ...

    @property
    def embed_model(self) -> str:
        """Identidade do modelo de embedding, exposta para que o índice possa
        REGISTRAR com que espaço vetorial foi construído e o retriever possa
        RECUSAR consultá-lo com outro (ver index/build.py:
        assert_embedding_compatible). Sem isso, indexar com um modelo e
        consultar com outro devolve resultados errados sem erro nenhum — o
        modo de falha mais caro do RAG, porque parece que funciona."""
        ...

    @property
    def chat_model(self) -> str:
        """Identidade do modelo de geração, exposta para relatórios/eval
        registrarem CONTRA qual modelo uma resposta foi produzida — sem isso
        um relatório de acurácia fica mudo sobre a variável mais óbvia."""
        ...


def _model_is_installed(model: str, installed: set[str]) -> bool:
    """O /api/tags devolve o nome COM tag ("nomic-embed-text:latest"), mas o
    usuário configura sem tag ("nomic-embed-text"). Comparar string crua
    reportaria "modelo faltando" com o modelo instalado — daí a normalização:
    sem tag configurada, casa contra o nome base do que está instalado."""
    if model in installed:
        return True
    if ":" in model:
        return False
    return any(name.split(":", 1)[0] == model for name in installed)


class OllamaProvider:
    """Implementação local do LLMProvider via API HTTP do Ollama.

    Não instancia nada de pesado no __init__ — só guarda config. O Ollama já
    mantém o modelo carregado no seu próprio processo; aqui é só cliente HTTP.
    """

    def __init__(
        self,
        *,
        host: str = "http://localhost:11434",
        chat_model: str | None = None,
        embed_model: str = "bge-m3",
        timeout_s: float = 120.0,
        embed_timeout_s: float = 300.0,
        embed_batch_size: int = 32,
        num_ctx: int = 8192,
        temperature: float | None = None,
        seed: int | None = None,
    ) -> None:
        """Guarda config. Ver docstring do módulo para a razão dos defaults
        (VRAM compartilhada com o BG3).

        chat_model vem de BROPILOT_CHAT_MODEL quando não passado explicitamente
        (mesmo padrão de api_key no OpenAIProvider) — permite trocar o modelo
        de geração para comparação (ex.: eval_rag.py --showcase contra um 14b)
        sem editar código nem duplicar caminho de configuração. Default
        inalterado (qwen2.5:7b-instruct-q4_K_M) para não quebrar nada quando a
        env var não está setada.

        temperature/seed vêm de BROPILOT_TEMPERATURE/BROPILOT_SEED quando não
        passados. DEFAULT temperature=0.0 (decodificação gulosa) + seed fixo:
        sem isso o Ollama roda na temperature default (~0.8) sem seed, e cada
        chamada é um sorteio — para um assistente de REGRAS (fatos, não
        criatividade) isso torna qualquer avaliação de acurácia uma amostra
        única ruidosa, não reprodutível. Vale tanto para o CLI quanto para
        eval_rag.py, porque os dois passam por este mesmo __init__.

        embed_timeout_s é separado de timeout_s porque indexar a base manda
        lotes grandes para uma GPU que também roda o jogo — o teto de 120s que
        serve para uma geração interativa estoura numa fila de embeddings.

        num_ctx é explícito porque o default do Ollama (medido: 4096, mesmo em
        modelo que suporta 32768) trunca o prompt SEM AVISAR quando o RAG manda
        vários chunks — e trunca pelo começo, que é onde está a persona. Um
        orçamento de tokens no orquestrador só significa alguma coisa se a
        janela real for conhecida. 8192 é folga para prompt + resposta sem
        inchar a VRAM disputada com o BG3.
        """
        self._host = host.rstrip("/")
        self._chat_model = (
            chat_model or os.environ.get("BROPILOT_CHAT_MODEL")
            or "qwen2.5:7b-instruct-q4_K_M"
        )
        self._embed_model = embed_model
        self._timeout_s = timeout_s
        self._embed_timeout_s = embed_timeout_s
        self._embed_batch_size = embed_batch_size
        self._num_ctx = num_ctx
        self._temperature = (
            temperature if temperature is not None
            else float(os.environ.get("BROPILOT_TEMPERATURE", 0.0))
        )
        self._seed = (
            seed if seed is not None
            else int(os.environ.get("BROPILOT_SEED", 42))
        )

    @property
    def num_ctx(self) -> int:
        """Janela de contexto pedida ao Ollama. O orquestrador usa isto para
        dimensionar o orçamento do prompt."""
        return self._num_ctx

    @property
    def embed_model(self) -> str:
        return self._embed_model

    @property
    def chat_model(self) -> str:
        return self._chat_model

    @property
    def temperature(self) -> float:
        return self._temperature

    @property
    def seed(self) -> int:
        return self._seed

    def _post(
        self, path: str, payload: dict, *, timeout_s: float, model: str, context: str
    ) -> dict:
        """POST + tratamento de erro comum a generate() e embed().

        Centralizado porque os três modos de falha (Ollama fora do ar, modelo
        não baixado, timeout) são idênticos nos dois métodos e cada um precisa
        virar mensagem acionável, nunca stack trace cru.
        """
        try:
            response = requests.post(
                f"{self._host}{path}", json=payload, timeout=timeout_s
            )
        except requests.exceptions.Timeout as exc:
            raise RuntimeError(
                f"Ollama não respondeu em {timeout_s}s ao {context}. Modelo "
                "local é lento na primeira chamada (carrega na VRAM); tente de "
                "novo ou aumente o timeout."
            ) from exc
        except requests.exceptions.ConnectionError as exc:
            raise RuntimeError(
                f"Não foi possível conectar no Ollama em {self._host}. "
                "Suba o serviço com `ollama serve` e tente de novo."
            ) from exc

        # 404 no Ollama = modelo não baixado; é o erro mais comum no primeiro uso.
        if response.status_code == 404:
            raise RuntimeError(
                f"Ollama não encontrou o modelo '{model}'. "
                f"Baixe com: ollama pull {model}"
            )
        if not response.ok:
            raise RuntimeError(
                f"Erro na API do Ollama ({response.status_code}) ao {context}: "
                f"{response.text[:500]}"
            )

        return response.json()

    def _post_stream(
        self, path: str, payload: dict, *, timeout_s: float, model: str, context: str
    ) -> Iterator[dict]:
        """Como `_post`, mas para o endpoint respondendo NDJSON (`stream=True`
        no corpo do request): mesmo tratamento de erro (offline, timeout,
        modelo ausente), só que devolve um generator de dicts — uma por linha
        — em vez de carregar a resposta inteira com `response.json()`, que
        pressupõe um único objeto JSON e quebraria contra um corpo NDJSON.

        `stream=True` aqui é o parâmetro do `requests` (não baixa o corpo
        inteiro antes de retornar); é isso que permite `iter_lines()` entregar
        cada linha assim que ela chega pela rede, em vez de só depois que o
        Ollama termina de gerar a resposta inteira.
        """
        try:
            response = requests.post(
                f"{self._host}{path}", json=payload, timeout=timeout_s, stream=True
            )
        except requests.exceptions.Timeout as exc:
            raise RuntimeError(
                f"Ollama não respondeu em {timeout_s}s ao {context}. Modelo "
                "local é lento na primeira chamada (carrega na VRAM); tente de "
                "novo ou aumente o timeout."
            ) from exc
        except requests.exceptions.ConnectionError as exc:
            raise RuntimeError(
                f"Não foi possível conectar no Ollama em {self._host}. "
                "Suba o serviço com `ollama serve` e tente de novo."
            ) from exc

        if response.status_code == 404:
            raise RuntimeError(
                f"Ollama não encontrou o modelo '{model}'. "
                f"Baixe com: ollama pull {model}"
            )
        if not response.ok:
            raise RuntimeError(
                f"Erro na API do Ollama ({response.status_code}) ao {context}: "
                f"{response.text[:500]}"
            )

        for line in response.iter_lines():
            if not line:
                continue
            yield json.loads(line)

    def generate(self, system: str, user: str) -> str:
        """Retorna o texto completo da resposta.

        Wrapper sobre generate_stream(): consome o stream até o fim e
        concatena. Um único caminho de request para as duas formas — quem
        chama generate() (eval_rag.py, a suíte) não vê diferença nenhuma no
        contrato, só ganha o benefício de não haver duas implementações de
        POST /api/chat para manter em sincronia.
        """
        return "".join(self.generate_stream(system, user))

    def generate_stream(self, system: str, user: str) -> Iterator[str]:
        """POST /api/chat com stream=True. Produz cada pedaço de texto
        (`message.content`) assim que a linha NDJSON correspondente chega —
        é isto que faz a resposta aparecer token a token no terminal em vez
        de tudo de uma vez ao final. Mesmos erros de generate() (offline,
        timeout, modelo ausente), com as mesmas mensagens acionáveis — só o
        transporte muda (ver `_post_stream`).
        """
        for chunk in self._post_stream(
            "/api/chat",
            {
                "model": self._chat_model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "stream": True,
                "options": {
                    "num_ctx": self._num_ctx,
                    "temperature": self._temperature,
                    "seed": self._seed,
                },
            },
            timeout_s=self._timeout_s,
            model=self._chat_model,
            context="gerar uma resposta",
        ):
            content = chunk.get("message", {}).get("content", "")
            if content:
                yield content

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """POST /api/embed em lote. Retorna um vetor por texto, na mesma ordem.

        /api/embed aceita uma lista em `input` e devolve `embeddings` na mesma
        ordem, mas mandar milhares de chunks de uma vez (um doc grande da base)
        vira um request gigante numa GPU compartilhada com o jogo. Por isso
        fatia em lotes de embed_batch_size e imprime progresso quando há mais
        de um lote — indexar a base não é instantâneo e o usuário precisa ver
        que anda. Uma query solta (1 texto) não imprime nada.
        """
        if not texts:
            return []

        vectors: list[list[float]] = []
        total_batches = (len(texts) + self._embed_batch_size - 1) // self._embed_batch_size

        for batch_number, start in enumerate(
            range(0, len(texts), self._embed_batch_size), start=1
        ):
            batch = list(texts[start : start + self._embed_batch_size])

            payload = self._post(
                "/api/embed",
                {"model": self._embed_model, "input": batch},
                timeout_s=self._embed_timeout_s,
                model=self._embed_model,
                context="gerar embeddings",
            )

            embeddings = payload["embeddings"]
            if len(embeddings) != len(batch):
                raise RuntimeError(
                    "Ollama devolveu "
                    f"{len(embeddings)} embeddings para {len(batch)} textos — "
                    "resposta inconsistente, o índice ficaria desalinhado."
                )
            vectors.extend(embeddings)

            if total_batches > 1:
                print(
                    f"  embeddings: lote {batch_number}/{total_batches} "
                    f"({len(vectors)}/{len(texts)} textos)"
                )

        return vectors

    def health_check(self) -> bool:
        """Ollama no ar e ambos os modelos disponíveis? Chamado no boot do CLI
        para falhar cedo com mensagem útil, em vez de estourar no meio da query."""
        try:
            response = requests.get(f"{self._host}/api/tags", timeout=self._timeout_s)
        except requests.exceptions.Timeout as exc:
            raise RuntimeError(
                f"Ollama não respondeu em {self._timeout_s}s no health check "
                f"({self._host})."
            ) from exc
        except requests.exceptions.ConnectionError as exc:
            raise RuntimeError(
                f"Ollama não está no ar em {self._host}. "
                "Suba o serviço com `ollama serve` e tente de novo."
            ) from exc

        if not response.ok:
            raise RuntimeError(
                f"Health check do Ollama falhou ({response.status_code}): "
                f"{response.text[:500]}"
            )

        installed = {model.get("name", "") for model in response.json().get("models", [])}
        missing = [
            model
            for model in (self._chat_model, self._embed_model)
            if not _model_is_installed(model, installed)
        ]
        if missing:
            comandos = "\n".join(f"  ollama pull {model}" for model in missing)
            raise RuntimeError(
                "Modelo(s) não baixado(s) no Ollama: "
                f"{', '.join(missing)}.\nBaixe com:\n{comandos}"
            )

        return True


class OpenAIProvider:
    """Implementação em nuvem do LLMProvider: geração via GPT-4o-mini e
    embeddings via text-embedding-3-small, ambos pela API oficial da OpenAI,
    chamados via HTTP puro (`requests`) — mesmo estilo do OllamaProvider, sem
    adicionar o SDK `openai` como dependência nova.

    embed() usa o MESMO modelo (embed_model, default text-embedding-3-small)
    que index/build.py usa para indexar a base — build e query PRECISAM
    concordar, senão o espaço vetorial não bate e o retrieval volta lixo sem
    erro nenhum. Por isso não existe um segundo caminho de embedding no
    projeto: tudo passa por este método.
    """

    _DEFAULT_BASE_URL = "https://api.openai.com/v1"
    _EMBED_BATCH_SIZE = 100  # textos por request; folga generosa sob o limite de 2048 itens/lote da OpenAI

    def __init__(
        self,
        *,
        api_key: str | None = None,
        chat_model: str | None = None,
        embed_model: str = "text-embedding-3-small",
        base_url: str = _DEFAULT_BASE_URL,
        timeout_s: float = 60.0,
        temperature: float | None = None,
        seed: int | None = None,
    ) -> None:
        """Guarda config; não faz chamada de rede aqui (ver health_check).

        api_key vem de OPENAI_API_KEY quando não passada explicitamente —
        nunca hardcode a chave. chat_model, por simetria com o OllamaProvider,
        vem de BROPILOT_CHAT_MODEL quando não passado (default inalterado:
        gpt-4o-mini). temperature/seed, mesma simetria, vêm de
        BROPILOT_TEMPERATURE/BROPILOT_SEED — default temperature=0.0 e seed
        fixo, mesma razão do OllamaProvider (assistente de regras precisa de
        determinismo, não de criatividade).
        """
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self._chat_model = (
            chat_model or os.environ.get("BROPILOT_CHAT_MODEL") or "gpt-4o-mini"
        )
        self._embed_model = embed_model
        self._base_url = base_url.rstrip("/")
        self._timeout_s = timeout_s
        self._temperature = (
            temperature if temperature is not None
            else float(os.environ.get("BROPILOT_TEMPERATURE", 0.0))
        )
        self._seed = (
            seed if seed is not None
            else int(os.environ.get("BROPILOT_SEED", 42))
        )

    @property
    def embed_model(self) -> str:
        return self._embed_model

    @property
    def chat_model(self) -> str:
        return self._chat_model

    @property
    def temperature(self) -> float:
        return self._temperature

    @property
    def seed(self) -> int:
        return self._seed

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
                    "temperature": self._temperature,
                    "seed": self._seed,
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

    def generate_stream(self, system: str, user: str) -> Iterator[str]:
        """FALLBACK — NÃO é streaming de verdade: chama generate() (uma volta
        síncrona inteira) e produz o resultado inteiro como um único pedaço.

        A API da OpenAI suporta SSE de verdade (`stream=True` + parsing das
        linhas `data: ...`), mas o back-end cloud não é o caminho ativo hoje
        (CLI usa Ollama local — ver docstring do módulo); implementar o SSE
        de verdade fica para quando a etapa 2 voltar a ser usada de fato, em
        vez de manter dois parsers de streaming sem uso real testando um
        deles às cegas. Documentado explicitamente aqui para não ser
        confundido com o streaming real do OllamaProvider.
        """
        yield self.generate(system, user)

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """POST {base_url}/embeddings em lotes de até _EMBED_BATCH_SIZE
        textos. Retorna um vetor por texto, na mesma ordem de entrada.

        Mesmo tratamento de erro de generate(): key ausente/errada (401),
        API fora do ar, timeout — nunca stack trace cru.
        """
        if not texts:
            return []

        api_key = self._require_api_key("gerar embeddings")
        vectors: list[list[float]] = []

        for start in range(0, len(texts), self._EMBED_BATCH_SIZE):
            batch = texts[start : start + self._EMBED_BATCH_SIZE]

            try:
                response = requests.post(
                    f"{self._base_url}/embeddings",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={"model": self._embed_model, "input": batch},
                    timeout=self._timeout_s,
                )
            except requests.exceptions.Timeout as exc:
                raise RuntimeError(
                    f"OpenAI não respondeu em {self._timeout_s}s ao gerar "
                    "embeddings. Tente de novo ou aumente timeout_s."
                ) from exc
            except requests.exceptions.ConnectionError as exc:
                raise RuntimeError(
                    f"Não foi possível conectar em {self._base_url} — confira "
                    "a rede ou o base_url configurado."
                ) from exc

            if response.status_code == 401:
                raise RuntimeError(
                    "OpenAI recusou a OPENAI_API_KEY (401). Confira se a "
                    f"chave é válida e tem acesso ao modelo "
                    f"'{self._embed_model}'."
                )
            if not response.ok:
                raise RuntimeError(
                    f"Erro na API da OpenAI ({response.status_code}): "
                    f"{response.text[:500]}"
                )

            # a API não garante ordem de retorno == ordem de entrada; "index" reordena
            data = sorted(response.json()["data"], key=lambda item: item["index"])
            vectors.extend(item["embedding"] for item in data)

        return vectors

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


def create_provider(
    name: str | None = None, *, ollama_host: str | None = None
) -> LLMProvider:
    """Escolhe o back-end de geração no boot: 'ollama' (default) ou 'openai'.

    `name` explícito tem prioridade; senão lê a env var BROPILOT_LLM; senão
    'ollama'. É este o ÚNICO ponto de seleção — quem constrói o Orchestrator
    (build_default_orchestrator / cli.py) chama isto antes de instanciar o
    Orchestrator, que continua recebendo o provider já pronto por injeção.

    `ollama_host` só se aplica ao back-end local; é repassado aqui para que a
    seleção continue num lugar só, em vez de o chamador instanciar o provider
    na mão quando precisa mudar o host.
    """
    resolved = (name or os.environ.get("BROPILOT_LLM") or "ollama").strip().lower()

    if resolved == "ollama":
        return OllamaProvider(host=ollama_host) if ollama_host else OllamaProvider()
    if resolved == "openai":
        return OpenAIProvider()

    raise ValueError(
        f"Provider de LLM desconhecido: '{resolved}'. Use 'ollama' ou 'openai' "
        "(env var BROPILOT_LLM ou parâmetro explícito)."
    )
