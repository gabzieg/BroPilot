# Decisão de arquitetura: busca híbrida (BM25 + vetorial)

> Formato ADR (contexto → decisão → consequências), igual a
> `bropilot_core/DECISION.md`.

## Contexto

Três experimentos de retrieval, todos medidos com `eval_rag.py`, convergiram para
uma única causa. Em ordem cronológica:

1. **Hipótese de diluição — FALSEADA.** Cortar 82% do corpus (só wiki + build)
   moveu a estabilidade entre paráfrases em +0.03. Ver
   `BroPilot-Knowledge/DECISION_refined_layer.md`, seção RESULTADO.
2. **Idioma da query — RESOLVIDO parcialmente.** Perguntar com os nomes próprios
   em inglês (query mista) recupera idêntico ao inglês puro (Jaccard 1.00). Mas
   a estabilidade em inglês ainda é 0.46, longe da meta 0.6.
3. **Dedup por `source_file` — hipótese da wiki FALSEADA.** Dedup zerou as
   duplicatas (19 → 0), mas a wiki continua fora do top-6 na pergunta factual.
   Ela não estava sendo ofuscada por repetição — está **genuinamente
   mal-rankeada pela similaridade densa crua**. E o Jaccard "caiu" para 0.34,
   revelando que o 0.46 era duplicata se disfarçando de estabilidade.

### A causa única

Depois de eliminar diluição, idioma e duplicata, os dois problemas restantes têm
a mesma raiz:

| Problema | Evidência |
|---|---|
| Wiki nunca no top-6 em pergunta de regra | recall@k = 0 em PT e EN, mesmo pós-dedup |
| Instabilidade entre paráfrases | Jaccard 0.34 (meta 0.6) |

Ambos são o mesmo fenômeno: **similaridade densa (cosseno) não discrimina em
corpus mono-domínio.** Tudo em BG3 é ~0.5 similar a tudo sobre BG3, então o
ranking fino vira ruído. A wiki, que é enxuta e factual, perde para transcrição
verborrágica que "fala mais" sobre o assunto sem ser mais precisa.

O sinal que falta é **lexical**. A página de wiki do Battle Master contém
"Superiority Dice" como string literal; a pergunta factual contém esse termo; o
vetor denso não os aproxima, mas um match de palavra-chave aproximaria na hora.

## Decisão

**Adotar busca híbrida: BM25 (full-text) + vetorial, fundidos por um reranker.**

### Por que agora, e não antes

Não é palpite — é a causa que sobrou de pé após três experimentos. A disciplina
de "medir antes de construir" já rejeitou as alternativas baratas (diluição,
dedup-conserta-wiki). Três evidências independentes apontam para híbrida:

1. Wiki tem os termos de regra como string literal → BM25 casa.
2. Nomes próprios em inglês (o que faz a query mista funcionar) são sinal lexical
   de alto valor → BM25 os explora.
3. Âncora lexical estabiliza paráfrases: palavras-chave compartilhadas entre
   reformulações ganham peso que a variação semântica não desloca.

### Implementação: FTS nativo do LanceDB, não BM25 caseiro

O LanceDB já suporta híbrida nativamente: índice FTS embutido (tantivy/BM25),
`query_type="hybrid"`, e rerankers prontos (`LinearCombinationReranker`,
`CrossEncoder`, ColBERT). **Não construir BM25 na mão.** Isso reduz a decisão de
"escrever um motor de busca" para "ligar a feature e escolher a fusão".

### Reranker: começar com LinearCombination, medir, e só então sofisticar

- **Default: `LinearCombinationReranker`.** Fusão simples e auditável: peso
  configurável entre score vetorial e FTS (default do LanceDB: 0.7 vetorial /
  0.3 FTS). O peso é um botão que dá para calibrar com a bateria.
- **NÃO** usar rerankers que chamam API externa (Cohere, OpenAI) nem cross-
  encoders pesados no MVP: adicionam dependência de rede ou de GPU e latência,
  contra o princípio local-first. Ficam como opção futura se a fusão linear não
  bastar.
- O peso vetorial↔FTS é o parâmetro a varrer com o eval: rodar a bateria com
  alguns valores (ex.: 0.3, 0.5, 0.7) e escolher pelo dado, não pelo default.

### O índice FTS é responsabilidade do `build.py`

Este é o custo estrutural real da decisão: passa a existir **um segundo índice**
(FTS) que precisa ser criado e mantido em sincronia com o vetorial. Regras:

- O FTS é criado sobre a coluna `text` **no mesmo `build_index`** que grava os
  vetores — nunca em passo separado, para não sair de sincronia.
- Toda mudança que reconstrói o índice vetorial (rebuild, incremental) deve
  reconstruir/atualizar o FTS na mesma transação lógica.
- O manifest passa a registrar que o FTS existe e sua versão, análogo ao
  `embed_model` — para detectar "índice vetorial presente, FTS ausente" e falhar
  cedo com instrução de rebuild, em vez de fazer híbrida silenciosamente só com
  o vetorial.

### O contrato do `Retriever` não muda

`search(query, *, signals, k, max_por_fonte)` mantém a assinatura. Internamente:
pool híbrido → boost state-aware (inalterado) → dedup por `source_file`
(inalterado) → corte em k. A híbrida troca *como o pool é buscado*, não o resto
da montagem do top-k. `base_score`/`score`/`boost_reasons` continuam auditáveis;
adicionar o score FTS ao rastro de depuração é desejável.

## Consequências

### Como validar (o instrumento já existe)

Rodar `eval_rag.py --lang en --sem-geracao` antes/depois, e varrer o peso do
reranker. Metas, revisadas pela realidade do que já medimos:

| Métrica | Baseline (denso, pós-dedup) | Meta |
|---|---|---|
| recall@k wiki (pergunta factual) | 0/1 (falha) | **acerta** — o teste decisivo |
| Jaccard de paráfrases (EN) | 0.34 | > 0.5 |
| recall@k Monge | 4/5 | 5/5 |
| duplicatas | 0 | 0 (não regredir) |

A **pergunta factual da wiki é o teste que importa**: é o caso que só a híbrida
deveria consertar (match lexical), e o que motivou a decisão. Se o recall da wiki
não passar com híbrida, a hipótese lexical estava errada e o problema é outro.

### Trade-offs aceitos

- **Segundo índice para manter.** Mitigado por criá-lo na mesma função do
  vetorial e registrá-lo no manifest. É a dívida estrutural real desta decisão.
- **BM25 é sensível a vocabulário exato.** "Open Hand" casa; um sinônimo que o
  usuário invente, não. Aceitável: o lado vetorial cobre o sinônimo, o lexical
  cobre o termo exato — é justamente a divisão de trabalho da híbrida.
- **Idioma do FTS.** O corpus é inglês; o tokenizer FTS deve ser configurado
  para inglês. A query mista traz os nomes próprios em inglês (é o que faz ela
  funcionar), então casa. Query 100% português casaria menos no FTS — mas já
  decidimos que a convenção é nome de jogo em inglês.

### O que NÃO é resolvido por esta decisão

A **geração** continua sendo o bloqueio nº 1 do produto (qwen2.5:7b: latência de
~60s, alucinação, e saída em chinês no teste de ontem). Híbrida melhora *o que
chega* ao contexto; não conserta o modelo que raciocina sobre ele. Decisão
independente, provavelmente geração na nuvem ou modelo local maior.

## Alternativas descartadas

- **Cota por source_type** (reservar slot de wiki). Band-aid: conserta a wiki na
  pergunta factual, mas não toca na instabilidade, exige classificar tipo de
  query, e desperdiça slot onde a wiki é irrelevante. A híbrida traz a wiki pelo
  sinal lexical *sem* cota fixa e ainda estabiliza paráfrases.
- **Reranker por cross-encoder / API** (Cohere, ColBERT, OpenAI). Latência ou
  dependência externa contra o local-first. Reavaliar só se a fusão linear não
  atingir as metas.
- **Camada `03_refined` de síntese.** Justificativa de retrieval já falseada
  (ver ADR do refino). Sobrevive só como autoria de conteúdo faltante, e com
  prioridade menor que este conserto.
