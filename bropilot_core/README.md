# BroPilot Core — camada de integração (scaffold)

Este pacote é a **cola** entre os três motores do repo, que hoje não se falam:
o `BroPilot-SaveParser` (estado da party ao vivo), a base de conhecimento em
`BroPilot-Knowledge/data/02_trusted/` (RAG) e um LLM local. Nenhum dos
subsistemas originais é modificado — a dependência é sempre daqui para eles,
respeitando a regra do `CLAUDE.md` de que os motores são independentes.

**Estado atual: só assinaturas e docstrings.** Todo corpo levanta
`NotImplementedError("scaffold")`. O objetivo é alinhar a arquitetura antes de
implementar.

## Por que RAG, e não context stuffing

A base tem **~1M tokens** (119 arquivos `.md`, 4.5 MB). O `bropilot.py` da raiz
enfiava tudo isso no system prompt do Gemini — funcionava só porque a janela do
Gemini é gigante. Num **LLM local** (Qwen/Llama via Ollama, 8K–32K de contexto
útil) isso **não cabe** — um único arquivo (`youtube_manual.md`, ~140K tokens) já
estoura o contexto sozinho. Por isso, no setup local, RAG deixa de ser "fase 2" e
vira o **piso mínimo**: sem retrieval, nada roda.

## Por que a abstração de LLM, se o MVP é só Ollama

O roadmap é "MVP local via Ollama → depois um modelo de custo baixo via API".
Essas duas etapas *são* dois back-ends. A interface `LLMProvider` (em `llm.py`)
custa ~20 linhas e faz a etapa 2 ser uma troca de classe em vez de uma caça a
chamadas espalhadas. Não é over-engineering — é o roadmap pedindo a costura.

## Módulos e ordem de implementação

Cada passo destrava o teste do próximo:

| # | Módulo | Papel | Testável isolado? |
|---|--------|-------|-------------------|
| 1 | `serialize.py` | `SaveContext` → ficha de texto + sinais de busca. O contrato de dados (Fase 0). | Sim, sem LLM/RAG |
| 2 | `llm.py` | `OllamaProvider` (generate + embed) atrás de `LLMProvider`. | Sim, com `ollama run` |
| 3 | `index/build.py` | Chunk dos `.md` → embeddings → LanceDB. Roda uma vez, offline. | Sim, jogo fechado |
| 4 | `index/retriever.py` | Busca top-k **dirigida pelo estado da party** (state-aware). | Depois do 3 |
| 5 | `orchestrator.py` | Junta party + retrieval + LLM numa resposta. | Depois de 1–4 |
| 6 | `cli.py` | REPL de teste no terminal. Superfície de validação antes da UI. | Ponta a ponta |

## Fluxo de runtime

```
save (.lsv) + snapshot do mod ─► serialize_party() ─► ficha (texto p/ prompt)
                                └► extract_signals() ─► chaves (dirigem a busca)
pergunta ─► retriever.search(pergunta, signals) ─► top-k chunks
         ─► orchestrator monta prompt pequeno ─► LLMProvider.generate() ─► resposta
```

O estado do save entra **duas vezes** e com papéis diferentes: como texto (o
modelo enxerga a party) e como sinal (dirige o retrieval). É o design
*state-aware* — o diferencial sobre um chatbot de wiki.

## Decisões travadas

- **Vector store: LanceDB** — embarcado, leve, sem servidor. Isolado atrás do
  `Retriever`, então trocar depois é local a `index/`.
- **Embeddings: `bge-m3` via Ollama** — mesmo runtime do LLM, zero
  dependência nova. Mesmo modelo na indexação e no runtime (senão o espaço
  vetorial não bate).
- **Chat model default: `qwen2.5:7b-instruct-q4_K_M`** — quantizado para não
  brigar por VRAM com o BG3 (setup "mesma máquina do jogo").

## Pendências conhecidas (dívida consciente do scaffold)

- **`sys.path` do SaveParser**: `cli.py` injeta `BroPilot-SaveParser/src` no path
  na mão, porque os subsistemas têm venvs separados. O certo, quando amadurecer,
  é um editable install (`pip install -e`) para o `import bropilot` funcionar sem
  gambiarra.
- **Fixture de teste no Mac**: como o mod Lua só roda no BG3/Windows, salve um
  `bropilot_inventory.json` real e passe via `--dump` para testar a integração no
  Mac sem o jogo aberto.
- **Sem `requirements.txt` ainda**: a implementação vai precisar de `lancedb` e um
  cliente HTTP (`httpx`/`requests`). Fica para a fase de implementação.

## Como rodar (quando implementado)

```bash
# 1. suba o Ollama e baixe os modelos
ollama serve
ollama pull qwen2.5:7b-instruct-q4_K_M
ollama pull bge-m3

# 2. indexe a base (uma vez, jogo fechado)
python -m bropilot_core.index.build

# 3. REPL de teste
python -m bropilot_core.cli --dump caminho/para/bropilot_inventory.json
```
