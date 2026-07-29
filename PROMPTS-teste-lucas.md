# Prompts — branch `teste-lucas`

Sequência de prompts para o Claude Code fechar o BroPilot end-to-end, 100% local
(Ollama), rodando no Mac, usável no terminal enquanto joga BG3.

**Modelo sugerido:** Sonnet 5 para todos. Escale para Opus só se algum passo sair
torto — o passo 3 (retriever state-aware) é o candidato mais provável.

**Regra de ouro:** rode um passo, valide, só então vá para o próximo. Os prompts
3–5 assumem que o anterior funcionou; se algo mudar no caminho, ajuste.

**Pré-requisito (uma vez, no terminal):**

```bash
# instalar Ollama: https://ollama.com/download
ollama pull nomic-embed-text                 # ~275MB, embeddings
ollama pull qwen2.5:7b-instruct-q4_K_M       # ~4.7GB, geração
ollama serve                                  # deixe rodando
```

---

## Passo 1 — Implementar o `OllamaProvider` (embed + generate)

```
Contexto: estamos na branch teste-lucas, adaptando o BroPilot para rodar 100%
LOCAL no macOS (sem OpenAI, sem API key). O OpenAIProvider em bropilot_core/llm.py
já está implementado e serve de MODELO DE REFERÊNCIA de estilo: requests puro,
batching, tratamento de erro com mensagem clara. O OllamaProvider na mesma
arquivo é scaffold — todos os métodos, incluindo o __init__, dão raise
NotImplementedError. Sua tarefa é implementá-lo.

Leia primeiro:
- bropilot_core/llm.py inteiro (o Protocol LLMProvider, o OpenAIProvider já
  pronto como referência, e o OllamaProvider scaffold com os defaults e as
  docstrings dizendo o que cada método deve fazer)
- bropilot_core/index/build.py (quem consome embed() em lote)
- bropilot_core/DECISION.md (por que local, e a restrição de VRAM)

Tarefa (escopo ESTRITO): implementar OllamaProvider.__init__, embed(),
generate() e health_check(), via HTTP puro com requests contra a API do Ollama
(default http://localhost:11434). Espelhe o estilo do OpenAIProvider.
- __init__: só guarda config, nenhuma chamada de rede (como o OpenAIProvider).
- embed(): POST /api/embed. Recebe uma sequência de textos e retorna um vetor por
  texto, NA MESMA ORDEM. Atenção: confira o formato real de request/response da
  versão atual da API do Ollama para embeddings em lote (o campo de entrada e o
  de saída) — se a API não aceitar lote numa chamada só, itere, mas mantenha a
  ordem e mostre progresso se for lento.
- generate(): POST /api/chat com messages=[system, user], stream=false. Retorna
  o texto da resposta.
- health_check(): Ollama está no ar E os dois modelos (chat_model e embed_model)
  estão baixados? Use o endpoint de listagem de modelos. Deve falhar com mensagem
  ACIONÁVEL, distinguindo os casos: Ollama não está rodando ("suba o ollama
  serve"), e modelo faltando ("rode ollama pull <nome-do-modelo>"). É chamado no
  boot do CLI para falhar cedo.
- Timeouts: geração local é lenta. O default de timeout_s=120 do scaffold vale
  para generate; para embed em lote grande, considere um timeout próprio ou
  chunking das chamadas.

REGRA CRÍTICA: não altere a assinatura do Protocol LLMProvider nem o
OpenAIProvider. O create_provider() já existe e já retorna OllamaProvider no
default — não mude essa lógica de seleção.

FORA DE ESCOPO: retriever, orchestrator, cli, serialize, build.py. Nada de UI.

Estilo: PEP 8, comente só decisão de arquitetura. Ao terminar, liste os arquivos
tocados. NÃO chame o Ollama de verdade nos testes — mocke requests, como o
test_llm.py já faz para o OpenAIProvider.
```

**Verificação (segunda mensagem):**

```
Verifique sem chamar o Ollama de verdade (mocke requests):
1. embed() devolve os vetores na mesma ordem dos textos de entrada, inclusive
   quando há mais de um lote/iteração.
2. health_check() com Ollama fora do ar → mensagem mencionando "ollama serve".
3. health_check() com um dos modelos faltando na listagem → mensagem mencionando
   "ollama pull" e o nome do modelo que falta.
4. generate() extrai corretamente o texto da resposta do formato do /api/chat.
5. Rode a suíte inteira (python -m unittest discover) e confirme que os testes
   que já existiam continuam passando.
Mostre um diff resumido.
```

---

## Passo 2 — Build real do índice (você, no terminal — não é prompt)

```bash
ollama serve                                  # em outro terminal
python -m bropilot_core.index.build --rebuild
```

Grátis e offline. Depois confira que o índice presta:

```python
import lancedb
t = lancedb.connect("bropilot_core/index/store").open_table("chunks")
print(t.count_rows())
print(t.to_pandas().sample(3)[["source_file", "source_type", "text"]])
```

Você quer ver: milhares de chunks, `source_type` correto, e textos que são
pedaços coerentes (não lixo cortado no meio). Se algo estiver errado, é aqui que
se corrige — antes de empilhar o retriever em cima.

---

## Passo 3 — Implementar o `Retriever`

```
Contexto: branch teste-lucas, stack 100% local (Ollama). O índice LanceDB já foi
construído por bropilot_core/index/build.py e existe em
bropilot_core/index/store/ (tabela "chunks", schema: text, source_file,
source_type, chunk_index, vector). Agora vamos implementar a busca:
bropilot_core/index/retriever.py, que é scaffold.

Leia primeiro:
- bropilot_core/index/retriever.py (Retriever, RetrievedChunk, search,
  _apply_state_boost — as docstrings explicam a intenção de cada um)
- bropilot_core/index/build.py (como o índice foi gravado: schema, _TABLE_NAME,
  STORE_DIR)
- bropilot_core/serialize.py (o TypedDict PartyStateSignals — as chaves que
  dirigem o boost; note que é total=False, todos os campos são opcionais)
- bropilot_core/llm.py (o embed() que você vai usar para vetorizar a query)

Tarefa (escopo ESTRITO), em DUAS PARTES — implemente e me mostre a parte 1
funcionando antes de fazer a parte 2:

PARTE 1 — busca semântica pura:
- __init__: guarda o provider e abre a tabela do LanceDB em leitura. Se o índice
  não existir, falhe cedo com mensagem acionável ("rode python -m
  bropilot_core.index.build primeiro").
- search(query, signals=None, k=6): embeda a query via llm.embed() e faz kNN no
  LanceDB, retornando list[RetrievedChunk] com text, source_file e score.
  Quando signals=None, é kNN puro — sem boost nenhum.

PARTE 2 — state-aware (o diferencial do produto):
- _apply_state_boost(hits, signals): reordena os hits dando peso aos que casam
  com o estado da party. COMECE SIMPLES, como a docstring manda: match do nome
  de classe/subclasse dos signals contra source_file e contra o texto do chunk,
  e um peso por source_type (ex.: "build" pesa mais que "forum" numa pergunta de
  build). Não invente um sistema de regras de RPG elaborado agora.
- search() com signals != None aplica esse boost.

REGRA CRÍTICA de consistência de embedding: a query DEVE ser embedada com o
MESMO modelo que gerou o índice (nomic-embed-text via OllamaProvider). Use o
provider injetado, não crie um segundo caminho de embedding. Se o modelo
divergir, a busca retorna lixo sem dar erro.

REGRA de transparência do score: deixe explícito no código o que é similaridade
crua e o que é score pós-boost. Eu preciso poder depurar POR QUE um chunk subiu.
LanceDB devolve distância (menor = mais perto); se você converter para
similaridade, documente a conversão.

FORA DE ESCOPO: orchestrator, cli, serialize (só consuma o TypedDict), geração
de resposta. Nada de UI.

Estilo: PEP 8, comente só decisão de arquitetura. Testes com embed mockado e um
índice LanceDB temporário de mentira — nenhuma chamada real ao Ollama.
```

**Verificação (segunda mensagem):**

```
Verifique com embed mockado e índice temporário (sem Ollama real):
1. search() sem signals: retorna k resultados ordenados por similaridade, e o
   RetrievedChunk traz text/source_file/score preenchidos.
2. search() num índice inexistente: erro claro mandando rodar o build.
3. _apply_state_boost: com signals contendo classes=["Monk"] e
   subclasses=["OpenHand"], um chunk de build_monk_openhand.md sobe acima de um
   chunk igualmente similar de outro arquivo. Prove com um caso montado.
4. search() com signals=None e com signals produz ordenações diferentes no mesmo
   índice (o boost realmente age).
5. Suíte inteira passando.
Mostre um diff resumido.
```

---

## Passo 4 — `Orchestrator` + `CLI` (o marco: primeira resposta de verdade)

```
Contexto: branch teste-lucas, stack 100% local (Ollama). O índice existe, o
Retriever funciona, o OllamaProvider gera texto. Falta a cola: o Orchestrator
que junta tudo e o CLI que me deixa conversar com isso no terminal. Ambos são
scaffold.

IMPORTANTE — esta etapa é SEM SAVE. Quero primeiro um Q&A de BG3 funcionando
contra a knowledge base, sem depender de ler o savegame. O save entra no passo
seguinte. Portanto: torne o ctx OPCIONAL onde ele hoje é obrigatório, em vez de
me obrigar a ter um save para fazer qualquer pergunta.

Leia primeiro:
- bropilot_core/orchestrator.py (Orchestrator, Answer, SYSTEM_PERSONA, ask,
  _build_prompt, build_default_orchestrator)
- bropilot_core/cli.py (main, _bootstrap_saveparser_path — e o docstring sobre
  o --dump)
- bropilot_core/index/retriever.py (já implementado, é o que você vai chamar)
- bropilot_core/llm.py (create_provider, OllamaProvider)

Tarefa (escopo ESTRITO):
1. Orchestrator.__init__: recebe llm e retriever por injeção, só guarda.
2. Orchestrator.ask(question, ctx=None): faça ctx opcional (default None).
   Fluxo: retriever.search(question, signals=None por enquanto) -> _build_prompt
   -> llm.generate() -> devolve Answer com text, sources (os source_file dos
   chunks usados, deduplicados) e party_had_live_stats=False quando ctx é None.
3. _build_prompt(question, party_text, chunks): monta (system, user). system =
   SYSTEM_PERSONA. user = contexto recuperado + a pergunta, claramente
   demarcados. Respeite um orçamento de tokens: se o conjunto passar do teto,
   corte chunks pelos menos relevantes primeiro — NUNCA corte o estado da party
   (quando houver). Deixe o teto configurável, com um default sensato para o
   qwen2.5:7b.
4. build_default_orchestrator: monta a stack concreta (create_provider() +
   Retriever). É o único lugar que sabe COMO montar — não mude essa
   responsabilidade.
5. cli.py main(): REPL de terminal. Passos: health_check do provider (falha cedo
   com a mensagem acionável), monta o orchestrator, e entra em loop lendo
   pergunta do stdin -> ask() -> imprime a resposta E as fontes. Aceite Ctrl+C /
   Ctrl+D / "sair" para encerrar limpo, sem stack trace. Suporte a flag
   --dump CAMINHO já pode existir na interface, mas nesta etapa pode ficar
   inerte (o save entra no próximo passo).
   Não precisa implementar _bootstrap_saveparser_path ainda — só é necessário
   quando o save entrar. Se for mais simples, deixe-o como está e não o chame.

REGRA: a resposta impressa DEVE vir com as fontes (arquivos que alimentaram o
prompt). É como eu verifico se o RAG está puxando o material certo em vez de o
modelo estar inventando.

FORA DE ESCOPO: ler savegame, serialize.py, state-aware signals, UI Electron.

Estilo: PEP 8, comente só decisão de arquitetura. Testes com llm e retriever
mockados — nenhuma chamada real ao Ollama.
```

**Verificação (segunda mensagem):**

```
Verifique com llm e retriever mockados:
1. ask() sem ctx: funciona, devolve Answer com sources preenchido e
   party_had_live_stats=False.
2. _build_prompt: com chunks demais para o orçamento, corta os menos relevantes
   e o prompt final respeita o teto. Prove com um caso montado.
3. Answer.sources vem deduplicado (dois chunks do mesmo arquivo = uma fonte).
4. health_check falhando no boot do CLI: mensagem acionável, sem stack trace.
5. Suíte inteira passando.
Mostre um diff resumido e me diga o comando exato para eu rodar o CLI.
```

**Depois desta verificação — o teste que importa (você, no terminal):**

```bash
ollama serve                      # noutro terminal
python -m bropilot_core.cli
```

Pergunte coisas que você sabe responder, para julgar a qualidade: *"qual a melhor
subclasse de Monge para dano desarmado?"*, *"como funciona a economia de ação de
bônus com Dual Wielder?"*. Olhe as fontes citadas. Se o RAG puxa material certo e
a resposta é coerente, **o cérebro está provado** — esse é o marco.

---

## Passo 5 — Plugar o save do Mac (o diferencial)

```
Contexto: branch teste-lucas, stack 100% local. O CLI já responde perguntas de
BG3 contra a knowledge base. Agora quero que ele leia MEU savegame no macOS e
use o estado da party para (a) entrar no prompt como contexto e (b) dirigir o
retrieval (state-aware). Falta implementar serialize.py e ligar os fios.

LIMITAÇÃO DE PLATAFORMA que você precisa respeitar: eu estou no macOS. O mod Lua
companion (BroPilotExporter) só roda no Windows via Script Extender, então NÃO
tenho snapshot ao vivo. Do save em disco só saem nível, raça, classes e
composição da party — sem equipamento, HP/CA, spell slots ou inventário. O
sistema deve degradar com HONESTIDADE nesse cenário, nunca inventar campos
vazios nem fingir que tem stats.

Leia primeiro:
- bropilot_core/serialize.py (serialize_party, serialize_character,
  extract_signals, PartyStateSignals — as docstrings explicam a intenção)
- BroPilot-SaveParser/src/bropilot/models.py (SaveContext, CharacterSummary — o
  que realmente existe no objeto, e o que só vem do mod)
- BroPilot-SaveParser/src/bropilot/save.py (DEFAULT_SAVE_ROOT, find_saves,
  latest_save — note que o default é o caminho do WINDOWS)
- bropilot_core/cli.py e orchestrator.py (já implementados, onde o save entra)

Tarefa (escopo ESTRITO):
1. Descobrir o caminho de saves do BG3 no macOS. NÃO confie num chute: verifique
   no meu sistema qual caminho existe de verdade (candidatos prováveis incluem
   ~/Documents/Larian Studios/Baldur's Gate 3/PlayerProfiles/Public/Savegames/
   Story e algo sob ~/Library/Application Support/). Use ls/find para confirmar
   antes de codificar. Se não achar nenhum, me pergunte em vez de adivinhar.
2. Em save.py: fazer a resolução do save root ser por plataforma, sem quebrar o
   Windows. O default do Windows deve continuar funcionando para meus sócios;
   adicione a resolução do macOS (e um jeito de sobrescrever por env var ou
   parâmetro). Não remova DEFAULT_SAVE_ROOT do contrato existente.
3. Implementar serialize.py:
   - serialize_character / serialize_party: ficha de texto CURTA (entra em todo
     prompt, cada token custa). Sem stats ao vivo, emita só o que existe e
     sinalize a limitação explicitamente.
   - extract_signals: preenche PartyStateSignals com o que o save dá (levels,
     races, classes, subclasses se disponível) e has_live_stats=False quando não
     há snapshot do mod.
4. Ligar no fluxo: Orchestrator.ask() passa a usar ctx quando ele existe —
   extract_signals() alimenta retriever.search(signals=...) e serialize_party()
   entra no prompt via _build_prompt. Answer.party_had_live_stats reflete a
   realidade.
5. No CLI: carregar o save mais recente automaticamente no boot (avisando qual
   arquivo carregou e se tem stats ao vivo ou não), e manter a flag --dump para
   quando um sócio me mandar um bropilot_inventory.json do Windows. Se nenhum
   save for encontrado, o CLI deve continuar funcionando em modo sem-save (o
   comportamento do passo 4), não morrer.

REGRA: sem save ou sem mod, o sistema RESPONDE MESMO ASSIM, degradando e
avisando. Nunca trave a experiência por falta de dado opcional.

FORA DE ESCOPO: o mod Lua, empacotamento, UI Electron.

Estilo: PEP 8, comente só decisão de arquitetura. Testes: para serialize, monte
SaveContext/CharacterSummary de mentira (não dependa de eu ter um .lsv no
repo); para o resto, mocke.
```

**Verificação (segunda mensagem):**

```
Verifique:
1. serialize_party com um SaveContext fabricado SEM snapshot do mod: a ficha sai
   curta, só com nível/raça/classe, e sinaliza a ausência de stats ao vivo. Não
   aparece campo vazio nem valor inventado.
2. extract_signals do mesmo contexto: has_live_stats=False e classes/levels
   preenchidos corretamente.
3. A resolução de save root: no macOS aponta para o caminho que existe; o
   caminho do Windows continua intacto no contrato (prove que não quebrou).
4. Orchestrator.ask() com ctx: os signals chegam ao retriever.search e a ficha
   da party entra no prompt. Com ctx=None, o comportamento do passo 4 é
   preservado.
5. CLI sem nenhum save encontrado: não quebra, roda em modo sem-save.
6. Suíte inteira passando.
Mostre um diff resumido e o comando para eu rodar.
```

---

## Uso final pretendido

```bash
# terminal 1
ollama serve

# terminal 2 — enquanto joga: F5 (quicksave) no jogo, depois pergunte aqui
python -m bropilot_core.cli
```

O fluxo em jogo: dá um quicksave (F5), volta ao terminal, pergunta. O CLI lê o
save mais recente, entende sua party, e responde com o material da KB.

## Dívidas técnicas conhecidas (não são bugs)

- Sem retry/backoff nos providers em caso de rate limit — irrelevante no local.
- Teste `test_default_backend_is_still_ollama_when_env_unset` depende do
  OllamaProvider ser scaffold; ao implementar o passo 1, ele precisa virar um
  `assertIsInstance(..., OllamaProvider)`. **O prompt do passo 1 não menciona
  isso** — se a verificação apontar esse teste quebrado, é esperado: mande
  corrigir para assertIsInstance.
- Sem stats ao vivo no macOS (limitação do Script Extender, não do código).
- Inventário/equipamento só com o mod rodando no Windows.
