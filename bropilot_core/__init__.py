"""BroPilot Core — camada de integração entre os três motores do projeto.

Este pacote é a *cola* que faltava: liga o SaveParser (estado da party ao vivo)
à base de conhecimento (RAG) e a um LLM local (Ollama), sem que nenhum dos
subsistemas originais precise saber da existência do outro. Segue a mesma regra
do repo: os motores não se importam entre si — quem os orquestra é aqui.

Fluxo de runtime (uma query do jogador):

    save (.lsv) + snapshot do mod  ─┐
                                    ├─►  serialize_party()  ──►  ficha enxuta
    pergunta do jogador  ───────────┘                                │
                                                                     ▼
                              retriever.search(query, party_state)  ─┴─►  top-k chunks
                                                                     │
                                                                     ▼
                              orchestrator monta prompt pequeno  ──►  LLMProvider.generate()
                                                                     │
                                                                     ▼
                                                              resposta ao jogador

Decisão de arquitetura que motiva a estrutura abaixo:

- A base tem ~1M tokens de markdown (119 arquivos, 4.5 MB). Não cabe no contexto
  de um LLM local (8K–32K úteis). Por isso RAG não é "fase 2", é o piso: o
  stuffing que funcionava no Gemini está descartado para o setup local.
- O LLM é plugável de propósito. O MVP usa Ollama local; a etapa seguinte troca
  o back-end sem tocar em mais nada, atrás de `LLMProvider`.
- O estado do save não entra no prompt como texto solto — ele *dirige* o
  retrieval (state-aware). É o que separa "chatbot de wiki" de "copiloto".

Ordem de implementação sugerida (cada módulo destrava o teste do próximo):
    1. serialize.py      — party -> texto. Testável isolado, sem LLM nem RAG.
    2. llm.py            — provider Ollama (generate + embed). Testável com `ollama run`.
    3. index/build.py    — chunk + embed + grava no vector store. Roda uma vez, offline.
    4. index/retriever.py— busca top-k dirigida pelo estado da party.
    5. orchestrator.py   — junta tudo. É o que o CLI e (depois) a UI chamam.
"""

__version__ = "0.0.1"  # scaffold — sem implementação ainda
