# Decisão de arquitetura: refino 1:1 de fontes da comunidade (02_trusted → 03_refined)

> Formato ADR, igual a `DECISION_refined_layer.md` e `bropilot_core/DECISION.md`.
> **Estado: implementado, validação em andamento.** Ver "Onde paramos" no fim.

## Contexto

Este trabalho parte da **justificativa que sobreviveu** ao falseamento registrado
em `DECISION_refined_layer.md`: a camada de refino foi descartada como
*otimização de retrieval* (a hipótese de diluição foi testada e reprovada), mas
sobreviveu como **autoria do conteúdo que falta**.

O corpus tem **um** arquivo de build curado (`build_monk_openhand.md`, 4 KB)
contra 54% do volume em transcrição de YouTube, onde o conhecimento de build está
preso em forma divagante. O conteúdo é valioso — é onde mora a *estratégia* de
min-max, que a wiki não tem. A forma é que é ruim.

Existe um **padrão-ouro feito à mão** que define a qualidade alvo:

| | entrada | saída |
|---|---|---|
| arquivo | `02_trusted/youtube_nNOWTLggypc.md` | `03_refined/youtube_nNOWTLggypc.md` |
| tokens | 6.659 | 3.124 (**−53%**) |
| headers | 2 | 20 |

Ganho para o RAG: o chunker de `bropilot_core/index/build.py` é *header-aware*.
Dar headers reais é metade do benefício — um documento com 20 headers vira 20
chunks coerentes por assunto, em vez de fatias arbitrárias de transcrição.

## Escopo

**1:1 — um documento de entrada, um de saída.** Não há síntese de múltiplas
fontes num doc canônico por tópico: isso é fase futura, com risco próprio
(interpretação congelada, proveniência diluída) e depende deste estágio existir
primeiro.

Fora de escopo por ora: fórum e Steam. Têm estrutura diferente (thread com
respostas, guia já seccionado) e vão precisar do próprio padrão-ouro. A wiki
**não é alvo de refino** — já é densa e estruturada, e aqui ela é a *fonte* do
glossário.

## Decisões

### 1. O glossário vem da wiki, não da memória do modelo

Este é o achado central do piloto manual. A transcrição destrói exatamente os
termos que o retrieval precisa casar:

| transcrição | real |
|---|---|
| "Devon brawler" / "an umbrella" | Tavern Brawler |
| "held the scar more" | Helldusk Armour |
| "anti-zatho gift" | presente da Auntie Ethel |
| "micronut colony" | Myconid Colony |
| "coded weak" | Cull the Weak |
| "huge giant Elixir" | Elixir of Hill Giant Strength |
| "shoots" | shields |

Esse conteúdo era **literalmente irrecuperável por qualquer busca**. Mas corrigir
de memória é convite a canonizar erro — e erro canonizado fica invisível, porque
o refinado passa a *parecer* uma fonte confiável.

Por isso `scripts/wiki_glossary.py` extrai a lista canônica dos 26 arquivos de
wiki e grava em `data/03_refined/glossario_wiki.json` (**3.019 termos**,
categorizados). A correção de nomes casa contra essa lista. **Nome que não casar
fica como está no original e vai para o log.**

Extração por 5 padrões: título de link `/wiki/…"Título"`, headers, alt de imagem,
negrito, e sequências Title Case na prosa.

**Detalhe que custou uma iteração:** o regex de Title Case casa o span mais
longo, então `"Get Help from Auntie Ethel"` engolia `"Auntie Ethel"` e o nome
próprio que interessa nunca entrava. A correção — registrar também os trechos
internos, quebrando nas palavras funcionais — subiu o glossário de 2.638 para
3.019 termos e trouxe `Auntie Ethel`, `Shadowheart`, `Lae'zel`.

### 2. Cobertura do glossário é parcial, e isso é aceito

Os arquivos de wiki em `02_trusted` são páginas de **visão geral**, não a base
completa de itens e magias. Medido contra os casos difíceis: **10 de 14**.

Ausentes: `Risky Ring`, `Gloves of Soul Catching`, `Boots of Uninhibited
Kushigo`, `Cloak of Displacement` — lendários de ato 3 que nenhuma página de
visão geral lista. `Flurry of Blows` e `Deflect Missiles` também não aparecem em
wiki nenhuma do corpus.

Consequência assumida: nomes assim **não serão corrigidos**, ficam como o autor
falou. É a escolha certa dado o risco — não corrigir é recuperável, canonizar
errado não é.

### 3. Glossário filtrado por trecho, não injetado inteiro

3 mil termos estourariam o contexto e afogariam o modelo. O filtro é por
sobreposição de tokens entre o termo e o trecho, com limiar **mais frouxo para
nomes compostos** (metade das palavras) do que para termos de uma palavra (match
exato). A razão: é justamente o composto que a transcrição quebra — "micronut
colony" perdeu "myconid" mas preservou "colony".

Na prática, ~120 termos por trecho.

### 4. Documento longo em partes com continuidade, nunca truncado

Corte por tamanho (~9.000 chars) com recuo até um fim de frase provável.
Transcrição não tem parágrafo, então não há fronteira natural. Cada parte recebe
a **cauda do refinado anterior** como contexto, com instrução de não repetir e
não reabrir headers. O `youtube_manual.md` (560 KB) vira ~62 partes encadeadas.

### 5. Verificação mecânica obrigatória, com resultado no log

O risco desta etapa é canonizar erro de forma invisível. Toda saída passa por
duas checagens comparando refinado × original:

- **(a) números** — todo número do refinado existe no original? Dado de dano,
  nível, usos e custo de recurso são copiados, nunca recalculados.
- **(b) nomes próprios** — todo nome do refinado existe no original **ou** no
  glossário? Os que não existem em nenhum dos dois são candidatos a invenção.

Documento que falha em (a) ou (b) é marcado **SUSPEITO** no log
(`03_refined/refino_log.jsonl`), **não descartado em silêncio**.

#### Calibração do verificador contra o padrão-ouro

As checagens foram rodadas sobre o par feito **à mão** — se acusassem muito num
documento sabidamente bom, seriam inúteis:

| checagem | resultado no padrão-ouro |
|---|---|
| (a) números | **0 divergências** |
| (b) nomes próprios | **13 sinalizados** |

Os 13 são todos correções *corretas* que a wiki não tem como confirmar
(`Helldusk Armor`, `Hill Giant Elixir`, `Resonating Punch`, `Sarevok's Horned
Helmet`, `Vest of Soul Rejuvenation`…).

**Portanto: SUSPEITO significa "não consegui verificar", não "está errado".** O
piso de ruído é ~13 nomes num documento perfeito. A lista existe para revisão
humana, que é o que a ADR anterior identificou como mitigação do risco de
canonizar erro.

No caminho, um artefato do próprio verificador foi corrigido: markup virando
espaço colava spans e inventava falsos nomes ("Guild Artisan    Insight"); agora
markup vira separador. Isso tirou 3 dos 16 falsos positivos originais.

### 6. Idempotência e gravação incremental

Mesmo padrão skip-if-exists dos scrapers do repo: pula saída que já existe, e
grava documento a documento. Queda no meio de um lote não perde o que já foi
refinado, e a re-execução retoma de onde parou.

## Regras de conteúdo (no prompt do refinador)

1. **Não inventar** — nada no refinado que não esteja no original. Trecho
   incompreensível é omitido, não completado.
2. **Números são sagrados** — cópia exata; ambíguo vira "(incerto)", nunca um
   valor escolhido.
3. **Não corrigir estratégia** — as opiniões de meta do autor *são* o conteúdo.
   Preservadas como opinião dele ("o autor considera"), como o padrão-ouro faz
   com "Stagger não é tão bom" e "Tavern Brawler é levemente OP".
4. **Nomes próprios só pelo glossário.**
5. Remover saudação, despedida, pedido de like, autopromoção, divagação.
6. Estruturar com headers markdown reais e prosa legível.

## Consequências

- O que entra em `03_refined` passa a ser material **derivado**, não fonte. A
  proveniência fica no frontmatter (`fonte_original`, `url`).
- `03_refined` já tinha `dialog_index.json` (manifesto do moxifer) e agora tem
  três tipos de artefato distintos: o índice de diálogo, o glossário e os
  documentos refinados. Nomeados de forma a não se misturarem.
- O índice do RAG **ainda aponta para `02_trusted`**. Trocar a base indexada é
  decisão separada, que deve vir com medição — e a ADR anterior deixou claro que
  a expectativa de ganho de retrieval não se sustenta. O ganho esperado aqui é de
  *conteúdo*, e a validação deve refletir isso.

## Onde paramos (para retomar em outra sessão)

### Feito

- `scripts/wiki_glossary.py` implementado e rodado → `03_refined/glossario_wiki.json` (3.019 termos).
- `scripts/youtube_refiner.py` implementado: flags `--limit`, `--only-types`,
  `--dry-run`, `--only-file`, `--out-dir`; verificação mecânica embutida; log em
  `03_refined/refino_log.jsonl`.
- Verificador calibrado contra o padrão-ouro (0 números / 13 nomes).

### Etapa 1 executada: REPROVOU com qwen2.5:7b

Pipeline rodado sobre o próprio `youtube_nNOWTLggypc.md` (240 s, 3 partes) e
comparado com o padrão-ouro.

| | original | padrão-ouro | pipeline |
|---|---|---|---|
| chars | 26.639 | 12.092 | 10.249 |
| headers | 2 | 20 | 36 |
| palavras | 4.988 | 2.047 | 1.595 |
| nomes sinalizados | — | 13 | **43** |

Os números de superfície parecem bons (61% de redução, mais headers que o
padrão-ouro). **O conteúdo não é.** Três defeitos, em ordem de gravidade:

**1. Erro factual introduzido.** O original diz *"add both your **wisdom** and
dexterity modifier to Armor class"*. O pipeline escreveu *"Permite adicionar
tanto a **inteligência** quanto à destreza ao cálculo do CA"*. Trocou o atributo.
Isso é exatamente o risco que esta ADR existe para evitar: erro canonizado com
aparência de fonte confiável.

**2. Distorção material de número.** O original diz que o ki *"eventually you can
end up with more than **20 uses**"*. O pipeline escreveu *"permite que o
personagem realize até **20 ataques** em um único turno"*. Trocou o referente do
número. **A checagem (a) não pega isso** — o "20" existe no original, só que
significando outra coisa. Limite conhecido do verificador: ele valida
*presença* de número, não *atribuição*.

**3. Nomes próprios traduzidos — o oposto do objetivo.** "Bracers of Defence"
virou "Bracetas de Defesa"; "Cloak of Displacement" virou "Capa de
Deslocamento"; "Sarevok's Horned Helmet" virou "Capelo de Cerevox"; "Martial
Arts" virou "Arts Martial". O padrão-ouro **mantém os nomes em inglês de
propósito** — é a grafia canônica que o retrieval precisa casar. Traduzir destrói
o mesmo acesso que o refino deveria criar, e é o que explica 43 nomes
sinalizados contra 13.

Além disso o título saiu inventado ("Monarca Guerreiro", que não está em lugar
nenhum do original) e a corrupção "key points" foi preservada em vez de
corrigida para ki points.

**Conclusão: não soltar na base.** O `--limit 3` da Etapa 2 fica bloqueado até
isto ser resolvido.

### Hipóteses para a próxima sessão, em ordem de custo

1. **O prompt não proíbe traduzir nome próprio.** Correção barata: regra
   explícita de manter itens/feats/magias/subclasses na grafia em inglês do
   glossário, com exemplo. Provável causa direta do defeito 3, e talvez do 1
   (o modelo está *traduzindo* em vez de *reescrever*).
2. **qwen2.5:7b é fraco demais para a tarefa.** Ele faz três coisas ao mesmo
   tempo — traduzir, estruturar e preservar fidelidade — e derrapa na terceira.
   Testar com `BROPILOT_LLM=openai` (gpt-4o-mini) num único documento mede isso
   direto; o custo é de centavos e a comparação é contra o mesmo padrão-ouro.
3. **Talvez o documento não deva ser traduzido.** O padrão-ouro é em português,
   mas nada obriga: manter em inglês eliminaria de uma vez o vetor dos defeitos
   1 e 3. Decisão de produto — quem lê o refinado é o LLM, não você.

Verificador a melhorar junto: a checagem (a) precisa de uma forma de detectar
número reatribuído (ex.: comparar a janela de palavras ao redor do número no
original e no refinado), senão o defeito 2 continua invisível.

### Comandos da validação

**Etapa 1** (a que reprovou):

```bash
python scripts/youtube_refiner.py --only-file youtube_nNOWTLggypc.md \
    --out-dir /tmp/refino_validacao
diff /tmp/refino_validacao/youtube_nNOWTLggypc.md \
     data/03_refined/youtube_nNOWTLggypc.md
```

**Etapa 2 — BLOQUEADA** até a Etapa 1 passar. Seria `--limit 3` em outros
vídeos, com antes/depois lado a lado, e só então os 64 documentos restantes.

```bash
python scripts/youtube_refiner.py --limit 3 --out-dir /tmp/refino_validacao
```

> Rodar com o venv da **raiz** do repo (`~/bropilot/venv`), não o do
> BroPilot-Knowledge: o refinador importa `bropilot_core.llm.create_provider()`
> para respeitar `BROPILOT_LLM`. Precisa do Ollama no ar (`ollama serve`).

### Questão em aberto para decidir depois da validação

Se o refino ficar bom, **o que fazer com o índice**: indexar `03_refined` em vez
de `02_trusted`, indexar os dois, ou manter `02_trusted` e usar o refinado só
como fonte de documentos curados. A ADR anterior sugere que a resposta não deve
vir de expectativa, e sim de medição com `eval_rag.py --sem-geracao`, que agora
custa 2,5 s por bateria.
