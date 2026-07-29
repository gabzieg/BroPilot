# BroPilot — Acompanhamento de Acurácia (antes × depois)

Este documento é o **placar acumulado** do projeto: cada mudança que pode afetar a
qualidade das respostas é medida contra a **mesma bateria de 10 perguntas**
(`--showcase` do `eval_rag.py`), julgada por um **juiz externo** (não o próprio
modelo de geração), e registrada aqui como uma linha.

## Princípios do acompanhamento

1. **Uma variável por vez.** Cada run muda **uma só coisa** (o modelo, ou a base,
   ou o retriever) — nunca duas juntas. Assim o delta no placar é atribuível.
   Foi por isso que a primeira mudança testada foi o **modelo de geração**, com
   índice, retrieval, prompt, perguntas e save **idênticos** ao baseline: o
   relatório de acurácia mostrou que o teto era a geração, não o pipeline, então
   a variável a mexer era o modelo.
2. **O juiz não é o réu.** O julgamento de acerto/alucinação é feito por um modelo
   mais forte e conferido contra as regras de BG3 e as fontes citadas — nunca
   pelo `qwen` se autoavaliando.
3. **n=10 é retrato, não taxa.** As contagens são um retrato comparável entre
   runs, não uma métrica estatística. O valor está no **delta**, não no absoluto.

## Placar

| # | Data | Variável alterada | Modelo de geração | ✅ | 🟡 | ❌ | Latência (mediana / bateria) | Veredito da mudança |
|---|---|---|---|---|---|---|---|---|
| 1 | 29/jul | — (baseline) | `qwen2.5:7b` (temp default ~0.8) | 2 | 3 | 5 | ~60s / ~9min | baseline |
| 2 | 29/jul | modelo (7b → 14b) | `qwen2.5:14b` (temp default) | 1 | 5 | 4 | ~107s / ~18min | **não adotar** (lateral, 2x latência) |
| 3 | 29/jul | temperatura (→ 0, seed fixo) | `qwen2.5:7b` **temp 0** | 1 | 4 | 5 | ~9min | reprodutível, mas acurácia não subiu (s10 regrediu) |
| 4 | 29/jul | temperatura (→ 0) + modelo | `qwen2.5:14b` **temp 0** | 2 | 4 | 4 | ~22min | melhor ponderado (4,0), mas ainda 4/10 alucinam |

Ponderado (🟡 = ½): run1 3,5 · run2 3,5 · run3 3,0 · run4 **4,0**. Melhor config é
marginal sobre o baseline, e ainda alucina regra em 4/10.

## Delta detalhado — run #2 (14b vs 7b)

| Q | Tipo | 7b | 14b | Movimento |
|---|---|---|---|---|
| s1 | regra factual | ✅ | ❌ | **regrediu** — 7b citou "4"; 14b raciocinou um "padrão" e concluiu "6" (errado). Overthinking de um lookup. |
| s2 | build Monk | ❌ | ❌ | igual — Great Weapon Master em desarmado (erro persiste), Resilient mal descrito. |
| s3 | raça Battle Master | ❌ | ❌ | igual — confundiu com build de arremesso (Enraged Throw é Barbarian). Acertou Lucky do Halfling. |
| s4 | action economy | 🟡 | 🟡 | igual/pior — erro novo: alegou que Dual Wielder exige Finesse (é o oposto). |
| s5 | multiclasse | ❌ | ❌ | igual — "Stillness of Mind dá flurry extra" (inventado). Corrigiu Evasion. |
| s6 | party level-up | ❌ | 🟡 | **melhorou** — parou de atribuir features de Bard a Cleric/Druid; recs apropriadas por classe. |
| s7 | Light Cleric | 🟡 | 🟡 | igual — trocou os erros (Warding Flare "infinito", Lightning Bolt como radiante). |
| s8 | magia Druid | ❌ | 🟡 | **melhorou** — puxou magias reais de druid; ainda listou Scorching Ray/Flame Strike (não são). |
| s9 | item | 🟡 | 🟡 | ligeiramente melhor — não inventou stats específicos do personagem desta vez. |
| s10 | fora de escopo | ✅ | ✅ | mais limpo — recusou sem o pivô alucinado (o 7b inventou um membro de party "Starion"). |

### Conclusão do run #2

Score ponderado (parcial = meio-acerto): 7b = 3,5; 14b = 3,5 — **empate**. O modelo
maior **troca alucinações grosseiras de síntese** (s6, s8, s10 melhoraram) **por
alucinações mais sutis de raciocínio** (s1 regrediu: pensou demais num lookup que
o 7b acertava só citando). Falha líquida praticamente igual, a **2x a latência**,
num Mac de 16GB no limite de RAM.

**Decisão: não adotar o 14b.** A curva de escala local achatou. Overthinking é um
modo de falha novo que o tamanho não resolve — pode até piorar. O ganho real está
num salto de capacidade maior (instruction-following + menos alucinação de regra),
que 7b→14b não entrega.

**Próximo passo indicado:** testar um **modelo de fronteira na nuvem** (Haiku /
GPT-4o-mini) como run #3 — variável única de novo, mesma bateria. É o salto de
capacidade que o baseline pediu, e o `AnthropicProvider`/`OpenAIProvider` já está
no código. Requer key (medição pontual, ~1 centavo pelas 10 perguntas).

## Log de decisões

- **29/jul — testar modelo antes de mexer na base.** O relatório de acurácia
  (`ACCURACY_REPORT.md`) mostrou que retrieval e leitura do save funcionam nos 10
  casos; as falhas se concentram na geração. Logo, a alavanca é o modelo, não o
  conteúdo. Mexer na base agora poliria o que já funciona e deixaria o gargalo
  intocado — além de sujar o sinal (não daria pra saber se uma melhora veio do
  modelo ou do dado). Ordem: primeiro o modelo (limpa o sinal), depois cobertura
  de base (magia, item) com o teto de geração já resolvido.
- **29/jul — 14b reprovado como passo.** Ver run #2. Escala local não paga;
  seguir para nuvem.
- **29/jul — furo de método corrigido: temperatura.** Descoberto que a geração
  rodava na temperatura default do Ollama (~0.8) sem seed — cada resposta era um
  sorteio, tornando os placares amostras únicas ruidosas e não reprodutíveis.
  Corrigido: `temperature`/`seed` configuráveis, **default temperature=0** (guloso,
  determinístico), valendo para o eval E para o CLI. Prova de que pegou: os dois
  runs temp-0 (7b e 14b) produziram a MESMA alucinação determinística no s6
  ("Contour Elemental"). Decisão: **temp 0 fica como default** — para um
  assistente de regras, determinismo + resposta mais provável é o comportamento
  correto, e torna todo run futuro reprodutível.
- **29/jul — temperatura não é o conserto de acurácia.** Runs #3/#4: temp 0 deu
  reprodutibilidade mas não subiu a acurácia (o 7b até regrediu no s10; o 14b
  seguiu errando o lookup factual s1, dizendo "5" em vez de "4", ignorando o chunk
  da wiki). Alavancas locais/config esgotadas.
- **29/jul — conclusão: o teto é capacidade de modelo.** Já descartados como
  solução, cada um com dado: diluição de corpus, dedup, tamanho do modelo
  (7b→14b), temperatura (0.8→0). A alucinação de regra sobrevive a todos os
  quatro. É um teto de capacidade de modelos locais 7–14B quantizados, não um
  problema de pipeline nem de config. **Próximo (run #5): modelo de fronteira na
  nuvem** (Haiku / GPT-4o-mini) — variável única, mesma bateria, temp 0. Único
  lever não testado com salto de capacidade grande; agora com evidência, não
  palpite. Requer key (medição pontual, ~1 centavo).
