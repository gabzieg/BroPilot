# Decisão de arquitetura: camada `03_refined` como base indexável

> Formato ADR (contexto → decisão → consequências), igual a
> `bropilot_core/DECISION.md`.

## Contexto

A bateria de avaliação do RAG (`bropilot_core/eval/rag_eval_20260728_211219.md`,
12 perguntas contra 4.409 chunks de 151 arquivos) mediu três problemas que têm a
mesma causa:

| Sintoma medido | Número |
|---|---|
| Spread de score no top-6 | **0.006 – 0.057** (paisagem plana) |
| Jaccard entre paráfrases da mesma intenção | **0.12 – 0.29** |
| Jaccard cross-lingual (PT vs EN, mesma pergunta) | **0.14** |
| `build_monk_openhand.md` (1 KB, curado) no top-6 | **nunca apareceu** |
| Documento duplicado dentro do mesmo top-6 | ocorreu em a1, f1 |

A causa comum é **diluição do corpus**. Indexamos `02_trusted`, que é conteúdo
*limpo mas cru*: transcrição de YouTube com divagação, thread de fórum com
discussão. Um documento curado e denso de 1 KB compete por força bruta de
quantidade contra milhares de chunks de baixa densidade informacional sobre o
mesmo assunto — e perde.

Consequência importante: **busca híbrida (BM25) e piso de similaridade são
compensações no momento da query para um problema que está na origem do dado.**
Tratam sintoma. A camada de refino trata a doença.

O Medallion do projeto já prevê o lugar disso: `01_raw` → `02_trusted` →
`03_refined`. Hoje `03_refined` só tem `dialog_index.json` e matrizes de item.
**A camada existe no desenho e está vazia.**

## Decisão

**Indexar `03_refined`, não `02_trusted`.** O `03_refined` passa a conter
*documentos canônicos por tópico*, sintetizados a partir de múltiplas fontes de
`02_trusted`.

### 1. Unidade de consolidação: tópico, com taxonomia enumerada

Não usar clustering para descobrir tópicos. O domínio de BG3 é derivado de D&D 5e
e portanto **finito e enumerável** — isso é uma vantagem estrutural que seria
desperdiçada com descoberta automática.

Escopo do MVP (bounded, ~60–80 documentos):

- **Builds**: um doc por classe × subclasse (12 classes, ~40 subclasses).
- **Mecânicas**: action economy, concentração, damage riders, resistências,
  vantagem/desvantagem, multiclasse, feats relevantes.
- **Fora do MVP**: itens individuais (centenas), spells (centenas), diálogos.
  Ficam para depois — a matriz de itens em `03_refined` já ataca parte disso.

Cobre o caso de uso central (otimização de build + economia de ação) sem explodir
escopo.

### 2. Roteamento de fonte → tópico: reusar o próprio RAG

Para cada tópico da taxonomia, **usar o índice de `02_trusted` que já existe**
para recuperar os top-N chunks sobre aquele tópico, e sintetizar o documento
canônico a partir deles.

Vantagens de fazer assim, em vez de classificar arquivo por arquivo:

- Reaproveita a infra já construída e testada (`Retriever`).
- Naturalmente incremental: arquivo novo em `02_trusted` → só os tópicos afetados
  são regerados.
- Mensurável: dá para reportar quantas fontes distintas alimentaram cada tópico e
  identificar tópicos com cobertura pobre.

Isso mantém `02_trusted` indexado — mas como **índice de trabalho do ETL**, não
como base de resposta ao usuário. Duas tabelas LanceDB, propósitos diferentes.

### 3. Estrutura do documento canônico

O formato é escolhido para *retrieval*, não para leitura humana:

```markdown
---
topico: monk_open_hand
tipo: build
entidades: [Monk, Open Hand, Monge, Mão Aberta]
aliases_pt: [monge mão aberta, monge desarmado]
aliases_en: [open hand monk, unarmed monk]
fontes: [youtube_nNOWTLggypc.md, forum_880699.md, steam_3442171013.md]
gerado_em: 2026-07-28
---

## Resumo acionável
(3–5 linhas densas: o que essa build faz e por que se escolhe ela)

## Progressão por nível
(níveis-chave, o que se pega em cada um)

## Sinergias e itens
## Erros comuns
## Divergência da comunidade
(onde as fontes discordam — ver decisão 5)
```

**Termos em PT e EN no mesmo documento, explicitamente** (`entidades`,
`aliases_pt`, `aliases_en`). Isso **corrige o problema cross-lingual por
construção**, em vez de depender do `bge-m3` fazer a ponte sozinho — o Jaccard de
0.14 mostra que ele não faz. Pergunta em qualquer idioma cai no mesmo documento.

### 4. Wiki como âncora numérica; comunidade só para estratégia

O maior risco da síntese por LLM é **canonizar regra inventada**. Mitigação por
hierarquia de fonte:

- **Números concretos** (dados de dano, nível, custo de recurso, número de usos)
  só podem vir de chunks da **wiki**. São fatos de regra.
- **Fórum, YouTube e Steam** entram para *estratégia, prioridade e opinião de
  meta* — não para afirmar regra.
- Número que aparece só em fonte comunitária entra marcado como **não
  verificado**, nunca como fato.

### 5. Divergência é conteúdo, não ruído

Min-maxing é assunto disputado. A síntese **não deve escolher um lado
silenciosamente**. Onde as fontes discordam, o documento registra o consenso e a
posição minoritária explicitamente. Um copiloto que apresenta o trade-off é mais
útil que um que finge unanimidade.

### 6. Proveniência preservada no frontmatter

A citação degrada de "chunk do vídeo X" para "doc canônico, sintetizado de X, Y,
Z". Aceitável — e discutivelmente mais útil ao usuário. O campo `fontes` mantém a
rastreabilidade para auditoria.

### 7. Incrementalidade pelo padrão que já existe

Reusar o padrão de manifest de `bropilot_core/index/build.py`: hash das fontes
que alimentaram cada tópico. Fonte mudou → só os tópicos afetados são regerados.
Gravar o doc antes do manifest (mesma garantia crash-safe já implementada lá).

## Consequências

### Custo

Síntese de ~70 tópicos × ~20 chunks × ~400 tokens ≈ **~600K tokens de input**.
Em `gpt-4o-mini`: centavos. Em `qwen2.5:7b` local: horas de batch, grátis. Roda
uma vez, e depois só incremental por patch.

### O que melhora, e por quê

- Menos chunks e mais distintos entre si → a paisagem plana de similaridade
  (spread 0.006) se separa, porque docs canônicos de tópicos diferentes são
  semanticamente mais distantes que 300 pedaços de transcrição sobre o mesmo
  assunto.
- Fim da duplicata no top-k: um tópico, um documento.
- Prompt mais barato e resposta mais rápida — menos token de divagação.
- Provavelmente **torna a busca híbrida desnecessária**. Reavaliar só depois de
  medir.

### Trade-offs aceitos

- **Interpretação congelada.** Erro de síntese fica canonizado e é mais difícil
  de rastrear que um chunk cru. Mitigado pela hierarquia de fonte (decisão 4) e
  pelo `fontes` no frontmatter.
- **Manutenção por patch.** Balanceamento muda → tópicos afetados precisam
  regerar. O incremental limita o custo.
- **Perda de long tail.** Detalhe que não entrou em nenhum tópico fica
  inacessível. Se a avaliação mostrar lacunas, a saída é indexar `02_trusted`
  como tabela de *fallback* consultada quando o score em `03_refined` vier baixo
  — não voltar a misturar tudo num índice só.

### Como validar (instrumento já existe)

A bateria `eval_rag.py` é o instrumento. Rodar contra `03_refined` e comparar com
o relatório de `02_trusted`, nas mesmas 12 perguntas. Métricas que devem melhorar:

| Métrica | Baseline (02_trusted) | Meta |
|---|---|---|
| Jaccard entre paráfrases | 0.12 – 0.29 | > 0.6 |
| Jaccard cross-lingual | 0.14 | > 0.7 |
| Spread de score no top-6 | 0.006 – 0.057 | maior (ranking decidível) |
| Doc de Monge no top-6 de pergunta de Monge | nunca | sempre |
| Duplicata de doc no top-6 | ocorria | zero |

Se essas não melhorarem materialmente, a hipótese de diluição estava errada e o
caminho é busca híbrida.

## Alternativas descartadas

- **Busca híbrida (BM25 + denso) primeiro.** Compensa no query time o que está
  errado na origem. Continua sendo o plano B se a métrica acima não mover.
- **Piso de similaridade.** Provado ineficaz pela própria bateria: a pergunta
  fora de escopo (Elden Ring, 0.526–0.550) pontuou *acima* de perguntas
  legítimas (Monge 0.516–0.533). Qualquer piso que corte uma corta a outra.
- **Clustering para descobrir tópicos.** Desnecessário num domínio enumerável;
  adiciona não-determinismo e dificulta incrementalidade.
- **Fine-tuning.** Já descartado em `bropilot_core/DECISION.md`: regra muda por
  patch, fine-tuning congela conhecimento e ensina estilo, não fatos.

## Teste barato antes de investir

Antes de construir a camada: **indexar só os `build_*.md` + wiki**, deixando
YouTube/fórum/Steam de fora, e rodar a bateria. Se a qualidade subir muito, a
hipótese de diluição está confirmada e o refino tem retorno garantido. Se não
subir, o problema é outro e o refino seria trabalho desperdiçado.

Custo do teste: uma reindexação. Vale fazer primeiro.
