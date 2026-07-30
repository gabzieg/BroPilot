# BroPilot — Relatório de Acurácia (showcase)

Gerado em 2026-07-30 10:04:20.

> Este documento **coleta evidência fielmente** — pergunta, resposta completa, fontes e latência — rodando a stack real (Ollama + índice + save). Ele **não julga** se uma resposta está certa, incompleta ou alucinada; isso fica para a coluna **Veredito**, deixada em branco para preenchimento humano (ou por um juiz automatizado mais forte) depois.

## Setup

- Data: **2026-07-30 10:04:20**
- Backend de geração: **openai** | Modelo de geração: `gpt-4o-mini`
- Temperature: **0.0** | seed: **42** (0 = decodificação gulosa/determinística, não é sorteio)
- Backend de embedding: **ollama** (SEMPRE local, fixo — é o espaço vetorial com que o índice foi construído) | Modelo de embedding: `bge-m3` (dim 1024)
- Índice: **5139 chunks** de 209 arquivos
- Save carregado: Cripta Sufocante - 3h 00min.lsv
- Party tinha stats ao vivo (mod companion): **NÃO (sem snapshot do mod companion — Mac não roda o Script Extender/BG3SE deste projeto; ficha da party é só nível/raça/classe)**

---

## Perguntas

### `s1` — regra factual verificável

**Pergunta:** how many Superiority Dice does a Battle Master have at level 5?

**Latência:** 5.4s

**Resposta:**

Um Battle Master tem 4 Superiority Dice a partir do nível 3, e isso não muda com o nível 5. Portanto, a resposta é que ele ainda tem 4 Superiority Dice. Esses dados são d8 e são recuperados após um Short Rest ou Long Rest.

**Fontes citadas:** `battle_master.md`, `youtube_PEWnGa-GSJg.md`, `youtube_f9uuvqtsz_0.md`, `feats.md`, `youtube_6DBOv0QC-Ck.md`, `forum_907941.md`

**Veredito:** _(a preencher)_

---

### `s2` — build / subclasse

**Pergunta:** best feats for an Open Hand Monk

**Latência:** 7.2s

**Resposta:**

Para um Open Hand Monk, as melhores feats geralmente se concentram em maximizar a eficácia em combate corpo a corpo e aumentar a sobrevivência. Aqui estão algumas sugestões:

1. **Tavern Brawler**: Essa é uma escolha quase obrigatória. Ela aumenta seu modificador de Força ou Constituição em +1 e permite que você use seu modificador de Força para dano em ataques desarmados, dobrando o dano. Isso se alinha perfeitamente com a mecânica de ataque do Monk, especialmente com a Flurry of Blows.

2. **Mobile**: Essa feat aumenta sua velocidade em 10 pés e permite que você não provoque ataques de oportunidade de criaturas que você atacou no seu turno. Isso é ótimo para um Monk, pois você pode entrar e sair do combate com facilidade, mantendo-se fora do alcance de ataques.

3. **Alert**: Aumenta sua iniciativa em +5 e você não pode ser pego de surpresa. Isso é útil para garantir que você possa agir rapidamente e aplicar suas habilidades de controle e dano antes que os inimigos tenham a chance de reagir.

4. **Resilient (Constitution)**: Essa feat aumenta sua Constituição em +1 e lhe dá proficiência em salvamentos de Constituição. Isso é crucial para manter a concentração em feitiços e habilidades que você pode usar, além de aumentar sua durabilidade em combate.

5. **Lucky**: Uma escolha versátil que permite que você re-rolar ataques, testes de habilidade ou salvamentos. Isso pode ser um divisor de águas em situações críticas, aumentando sua consistência em combate.

6. **Fighting Style (Dueling)**: Se você estiver considerando um multi-classe com Fighter, essa opção pode aumentar seu dano em ataques com uma única arma corpo a corpo, o que pode ser útil se você estiver usando uma arma em vez de ataques desarmados.

Essas feats não apenas aumentam seu potencial de dano, mas também melhoram sua mobilidade e sobrevivência, o que é essencial para um Monk que frequentemente se coloca em situações de combate corpo a corpo.

**Fontes citadas:** `youtube_bGupbGD2Fw0.md`, `way_of_the_open_hand.md`, `steam_3442171013.md`, `classes.md`, `build_monk_openhand.md`, `forum_944809.md`

**Veredito:** _(a preencher)_

---

### `s3` — build / usa subclasse nova

**Pergunta:** best race for a Battle Master Fighter

**Latência:** 8.1s

**Resposta:**

Para um Battle Master Fighter, a escolha da raça pode influenciar bastante a eficácia do personagem, especialmente em termos de atributos e habilidades raciais. Aqui estão algumas boas opções:

1. **Humanos**: Eles são versáteis, recebendo um bônus em todos os atributos, o que pode ser útil para um Fighter que precisa de força (ou destreza, dependendo da build) e constituição.

2. **Dwarves**: Especialmente os Dwarves de Montanha, que recebem um bônus em Constituição e podem ser ótimos para aumentar a durabilidade do seu Fighter. Além disso, eles têm resistência a venenos, o que é uma vantagem em combate.

3. **Half-Orcs**: Eles têm um bônus em Força e Constituição, além da habilidade de "Relentless Endurance", que permite que você fique com 1 ponto de vida em vez de cair quando receber um golpe que o derrubaria. Isso é ótimo para um Fighter que está na linha de frente.

4. **Elfos (Wood Elves)**: Se você optar por uma build mais ágil, os Wood Elves oferecem bônus em Destreza e têm habilidades como "Fleet of Foot", que aumenta a velocidade de movimento, e "Mask of the Wild", que pode ser útil para furtividade.

5. **Halflings**: Eles têm a habilidade "Lucky", que permite rerrolar 1s em ataques, e "Brave", que dá vantagem em testes de resistência contra medo. Isso pode ser útil para um Fighter que precisa estar em combate constante.

A escolha da raça deve alinhar-se com a sua estratégia de combate e o estilo de jogo que você deseja adotar. Se você está focando em maximizar dano e resistência, Dwarves ou Half-Orcs são ótimas escolhas. Se você quer um Fighter mais ágil e furtivo, considere os Elfos ou Halflings.

**Fontes citadas:** `battle_master.md`, `classes.md`, `d&d_5e_rule_changes.md`, `abilities.md`, `skills.md`, `forum_938252.md`

**Veredito:** _(a preencher)_

---

### `s4` — action economy

**Pergunta:** how does bonus action economy work with Dual Wielder?

**Latência:** 6.0s

**Resposta:**

Beleza, bro! Vamos falar sobre a economia de ações e como o feat Dual Wielder se encaixa nisso.

No D&D 5e, a economia de ações é crucial para maximizar o que você pode fazer em um turno. Normalmente, você tem uma ação, um movimento e, se tiver, uma ação bônus. O feat Dual Wielder permite que você use duas armas que não precisam ser leves, mas não altera a regra básica de que você ainda precisa de uma ação para atacar.

Aqui está o ponto chave: quando você ataca com uma arma em uma mão, você pode usar sua ação para fazer esse ataque e, se estiver usando a regra de combate com duas armas, você pode usar sua ação bônus para fazer um ataque com a arma na outra mão. No entanto, sem o estilo de luta "Two-Weapon Fighting", você não adiciona seu modificador de habilidade ao dano do ataque da arma secundária.

Isso significa que, se você matar um inimigo com seu ataque principal, você ainda pode usar sua ação bônus para atacar com a arma na outra mão, mas isso pode ser um desperdício se o inimigo já estiver fora de combate. Isso é algo que muitos jogadores consideram frustrante, como mencionado no contexto que você trouxe.

Além disso, se você estiver jogando com um personagem que já tem uma ação bônus ocupada (como um Rogue usando a habilidade de Esquiva ou um Barbarian que precisa usar a ação bônus para entrar em fúria), isso pode limitar ainda mais sua economia de ações.

Em resumo, o Dual Wielder pode ser útil para aumentar sua versatilidade em combate, mas você precisa estar ciente de como isso se encaixa na sua economia de ações geral. Se você não tiver maneiras de maximizar o uso da sua ação bônus, pode ser mais vantajoso focar em outras opções de build que não dependam tanto de ataques de off-hand.

**Fontes citadas:** `forum_950966.md`, `youtube_f7uewDCrrqQ.md`, `feats.md`, `d&d_5e_rule_changes.md`, `youtube_9JFz6IviB9Y.md`, `steam_3438196481.md`

**Veredito:** _(a preencher)_

---

### `s5` — multiclasse

**Pergunta:** is a Monk 9 / Rogue 3 multiclass worth it for damage?

**Latência:** 11.7s

**Resposta:**

Bro, um multiclass de Monk 9 e Rogue 3 pode ser bem interessante, especialmente se você está focando em maximizar o dano e a ação em combate. Vamos analisar isso.

### Vantagens do Multiclass Monk 9 / Rogue 3:

1. **Dano de Ataque**: 
   - No nível 9, o Monk melhora seu dano desarmado para 1d8 e ganha a habilidade de **Movimento Desarmado Avançado**, que aumenta sua mobilidade. Isso é ótimo para posicionamento e para evitar ataques de oportunidade.
   - Com 3 níveis de Rogue, você ganha **Sneak Attack** de 2d6, que é um aumento significativo de dano em ataques furtivos, especialmente se você conseguir vantagem ou atacar um inimigo que não tenha agido ainda.

2. **Ação Extra**: 
   - O Monk tem acesso a **Flurry of Blows**, que permite fazer dois ataques adicionais como uma ação bônus, aumentando sua ação econômica. Com a habilidade de Rogue, você pode usar **Cunning Action** para se mover ou se esconder como uma ação bônus, o que é uma sinergia poderosa.

3. **Sinergia de Habilidades**: 
   - O Monk se beneficia de sua alta Destreza e Sabedoria, enquanto o Rogue pode usar Destreza para ataques e habilidades. Isso significa que você pode maximizar seu potencial de dano e utilidade.

4. **Evasão e Resistência**: 
   - Ao chegar no nível 9 como Monk, você também ganha **Evasion**, que é uma habilidade defensiva incrível, permitindo que você evite dano de área com um teste de Destreza bem-sucedido.

### Considerações:

- **Ação Surge**: Um dos pontos que você perde ao não pegar mais níveis de Fighter é a **Ação Surge**, que é uma habilidade poderosa para aumentar sua ação em um turno. Isso pode ser um fator limitante em situações onde você precisa de mais ataques.

- **Dano Sustentado vs. Dano Burst**: O Monk é mais focado em dano sustentado, enquanto o Rogue pode oferecer explosões de dano em situações específicas (como ataques furtivos). Se você conseguir surpreender inimigos frequentemente, o Rogue pode compensar a falta de ataques extras.

### Conclusão:

Se o seu foco é maximizar o dano em situações onde você pode surpreender os inimigos e usar a mobilidade do Monk, um multiclass de Monk 9 / Rogue 3 pode ser muito eficaz. No entanto, se você está buscando um dano mais consistente e a capacidade de fazer múltiplos ataques em um único turno, considerar um nível adicional em Fighter para Ação Surge pode ser mais vantajoso. 

No geral, a escolha depende do estilo de jogo que você prefere e das situações que você enfrenta na campanha. Se você gosta de ser ágil e causar dano explosivo, essa build pode funcionar bem!

**Fontes citadas:** `steam_3442171013.md`, `youtube_9JFz6IviB9Y.md`, `youtube_Q4iw6MPxSDg.md`, `youtube_f9uuvqtsz_0.md`, `classes.md`, `spells.md`

**Veredito:** _(a preencher)_

---

### `s6` — ambígua — usa o estado do save

**Pergunta:** what's the best level-up choice for my current party?

**Latência:** 11.8s

**Resposta:**

Bro, com a sua party atual, você tem uma boa mistura de classes e habilidades. Vamos analisar as opções de level-up para cada um dos seus personagens e como isso pode impactar a action economy e a sinergia do grupo.

1. **Generic (Bard: Swords College)**:
   - **Nível 9**: Você vai ganhar um aumento de habilidade ou um feat. Considerando que você já está focado em Charisma, aumentar para 18 é uma boa escolha. Além disso, você pode considerar feats como **Inspiring Leader** para aumentar a durabilidade do grupo com pontos temporários de vida, ou **War Caster** para manter a concentração em feitiços enquanto está em combate.
   - **Spells**: Ao atingir o nível 5, você também ganha acesso a feitiços de 3º nível. **Hypnotic Pattern** é uma escolha excelente para controle de multidão, e **Fear** pode ser útil para desestabilizar grupos de inimigos.

2. **Shadowheart (Cleric: Light Domain)**:
   - **Nível 9**: Aqui, você também pode optar por um aumento de habilidade ou um feat. **Resilient (Constitution)** é uma boa escolha para melhorar suas chances de manter a concentração em feitiços. Além disso, você pode considerar **Tough** para aumentar seus pontos de vida.
   - **Spells**: Você pode escolher feitiços de 5º nível, como **Greater Restoration** ou **Flame Strike**, que são ótimos para curar ou causar dano em área.

3. **Laezel (Fighter: Battle Master)**:
   - **Nível 9**: Um aumento de habilidade em Força ou Destreza é sempre bom, mas você também pode considerar um feat como **Great Weapon Master** se estiver usando armas pesadas, ou **Shield Master** se estiver focando em defesa.
   - **Maneuvers**: Certifique-se de que ela tenha uma boa seleção de manobras que complementem o resto do grupo, como **Menacing Attack** para desestabilizar inimigos.

4. **Jaheira (Druid: Circle of the Land)**:
   - **Nível 9**: Um aumento em Sabedoria é sempre uma boa escolha, mas você também pode considerar um feat como **Spell Sniper** para aumentar a eficácia dos seus feitiços de ataque.
   - **Spells**: Ao atingir o nível 5, você pode escolher feitiços de 3º nível, como **Call Lightning** ou **Plant Growth**, que podem ser muito úteis em combate e controle de área.

### Sinergias e Action Economy
- **Bard e Cleric**: O Bard pode fornecer suporte e controle, enquanto o Cleric pode curar e causar dano. A combinação de feitiços de controle do Bard com os de cura do Cleric pode manter o grupo saudável e os inimigos desestabilizados.
- **Fighter e Druid**: O Fighter pode atuar como o tanque, enquanto o Druid pode fornecer controle de área e suporte. O Druid pode usar feitiços como **Entangle** para manter os inimigos em cheque, permitindo que o Fighter se concentre em causar dano.

### Conclusão
Para maximizar a eficácia do seu grupo, considere aumentar as habilidades principais de cada personagem e escolher feats que melhorem a ação em combate. O Bard e o Cleric devem focar em feitiços de controle e cura, enquanto o Fighter e o Druid devem se concentrar em aumentar seu dano e controle de área. Isso deve garantir que sua party tenha uma boa ação em combate e sinergia entre os membros. Boa sorte, bro!

**Fontes citadas:** `forum_948214.md`, `youtube_ETjbbHbQuTE.md`, `forum_885547.md`, `forum_934343.md`, `youtube_Q4iw6MPxSDg.md`, `youtube_sd9WavTJXVE.md`

**Veredito:** _(a preencher)_

---

### `s7` — caster — Shadowheart é Light Domain no save

**Pergunta:** best build for a Light Domain Cleric

**Latência:** 10.4s

**Resposta:**

Beleza, bro! Vamos falar sobre como maximizar o potencial da sua Cleric do Light Domain. Essa build pode ser super poderosa, especialmente se você focar em sinergias e na economia de ações.

### 1. **Atributos**
Priorize Sabedoria (Wisdom) para aumentar a eficácia dos seus feitiços e habilidades. Um bom ponto de partida seria algo como:
- **Sabedoria**: 16-20 (dependendo de como você distribui os pontos)
- **Constituição**: 14-16 (para aumentar seus pontos de vida)
- **Destreza**: 14 (se você estiver usando armaduras médias)

### 2. **Habilidades e Feitos**
- **Warding Flare**: Essa habilidade é incrível para tanking, pois permite que você dê desvantagem nos ataques dos inimigos. Use-a sempre que possível para proteger a si mesmo e seus aliados.
- **Spellcasting**: Foque em feitiços que causam dano em área e controle, como *Flaming Sphere* e *Spirit Guardians*. Eles não só causam dano, mas também podem ajudar a controlar o campo de batalha.
- **Healing**: Use *Healing Word* como sua principal forma de cura, pois é uma ação bônus e permite que você ainda ataque ou use outras ações no mesmo turno.

### 3. **Feitiços**
Aqui estão alguns feitiços que você deve considerar:
- **Cantrips**: *Guidance* (para ajudar em testes de habilidade) e *Sacred Flame* (dano e não requer ataque).
- **1º Nível**: *Healing Word* e *Bless* (para buffar seus aliados).
- **2º Nível**: *Flaming Sphere* e *Spiritual Weapon* (dano e controle).
- **3º Nível**: *Spirit Guardians* (dano em área e proteção) e *Daylight* (para controle de luz e escuridão).

### 4. **Equipamentos**
Embora você não tenha dados de equipamentos, procure por itens que aumentem sua Sabedoria ou que ofereçam bônus de proteção. Armaduras médias que permitam o uso de Destreza são ideais, já que você pode maximizar sua CA.

### 5. **Sinergias com a Party**
- **Bard**: O Bard pode fornecer buffs e controle, então combine suas habilidades de cura e dano com os feitiços de suporte dele.
- **Fighter**: Laezel pode ser seu tanque, então use *Warding Flare* para proteger ela enquanto ela lida com os inimigos.
- **Druid**: Jaheira pode fornecer controle e cura, então você pode focar mais em causar dano e buffar a party.

### 6. **Economia de Ações**
A economia de ações é crucial. Sempre que possível, use ações bônus para curar ou buffar, e reserve suas ações principais para causar dano ou controlar o campo. Isso maximiza o que você pode fazer em cada turno.

Com essa abordagem, sua Cleric do Light Domain pode se tornar uma força poderosa no campo de batalha, equilibrando cura, dano e controle. Boa sorte, e que os dados estejam sempre a seu favor!

**Fontes citadas:** `light_domain.md`, `forum_935207.md`, `youtube_YOgipqWEUV0.md`, `youtube_GtljSKjZm-A.md`, `youtube_ZNaZOkbFlk4.md`, `classes.md`

**Veredito:** _(a preencher)_

---

### `s8` — expõe buraco de magia de propósito

**Pergunta:** which spells should a Circle of the Land Druid prioritize?

**Latência:** 8.6s

**Resposta:**

Beleza, bro! Vamos falar sobre as prioridades de feitiços para a Jaheira, que é uma Druid Circle of the Land. Essa subclass é bem versátil, então ela pode se destacar tanto em suporte quanto em dano.

### Feitiços de Nível 1
1. **Entangle**: Excelente para controle de multidão. Pode prender inimigos e dar vantagem para seus aliados.
2. **Healing Word**: Um feitiço de cura rápido que pode ser lançado como uma ação bônus, ótimo para manter os aliados de pé.

### Feitiços de Nível 2
1. **Pass Without Trace**: Um buff incrível para furtividade, especialmente útil para evitar emboscadas ou se aproximar de inimigos sem ser notado.
2. **Moonbeam**: Um feitiço de dano em área que pode ser muito eficaz contra inimigos que mudam de forma, além de causar dano radiante.

### Feitiços de Nível 3
1. **Call Lightning**: Um ótimo feitiço de dano em área que se encaixa bem em situações de combate, especialmente em ambientes abertos.
2. **Plant Growth**: Pode ser usado para controle de campo, dificultando o movimento dos inimigos e ajudando a proteger seus aliados.

### Feitiços de Nível 4
1. **Conjure Woodland Beings**: Chamar criaturas para ajudar em combate pode mudar o rumo da batalha, oferecendo tanto dano quanto distração.
2. **Grasping Vine**: Um feitiço que pode puxar inimigos para mais perto ou afastá-los, oferecendo controle adicional.

### Feitiços de Nível 5
1. **Wall of Thorns**: Um excelente feitiço de controle que causa dano e pode bloquear o movimento dos inimigos.
2. **Greater Restoration**: Uma cura poderosa que pode remover condições negativas, essencial em batalhas mais difíceis.

### Considerações Finais
- **Sinergia com a Party**: Como você tem um Bard e um Cleric, você pode focar mais em controle e dano, enquanto eles cuidam da cura e suporte. 
- **Spell Recovery**: Lembre-se de que a Circle of the Land permite recuperar slots de feitiço, então não hesite em usar seus feitiços mais poderosos quando necessário.

Com essa seleção, a Jaheira pode ser uma força da natureza no campo de batalha, equilibrando suporte e dano. Manda ver!

**Fontes citadas:** `circle_of_the_land.md`, `classes.md`, `steam_3438196481.md`, `companions.md`, `forum_880699.md`, `forum_934932.md`

**Veredito:** _(a preencher)_

---

### `s9` — item — expõe o limite sem-mod no Mac

**Pergunta:** should I equip Gloves of Soul Catching on my Monk?

**Latência:** 8.9s

**Resposta:**

Sim, você definitivamente deve equipar as **Gloves of Soul Catching** no seu Monk. Elas oferecem várias vantagens que se alinham perfeitamente com a sua build, especialmente se você está focando em ataques desarmados.

Aqui estão os principais benefícios:

1. **Dano Adicional**: As luvas adicionam 1d10 de dano de força aos seus ataques desarmados, o que é uma grande melhoria no seu potencial de dano.

2. **Cura**: A habilidade de curar 10 pontos de vida uma vez por turno após um ataque desarmado é extremamente útil, especialmente em combates prolongados, permitindo que você se mantenha mais tempo no campo de batalha.

3. **Vantagem em Ataques e Testes de Resistência**: Ganhar vantagem em todos os ataques e testes de resistência até o final do seu próximo turno é uma habilidade poderosa, aumentando suas chances de sucesso em ataques e ajudando a evitar efeitos negativos.

4. **Aumento de Constituição**: O aumento de +2 na sua Constituição pode ser muito valioso, especialmente se você ainda não tiver atingido o máximo de 20.

Essas luvas se encaixam bem na sua estratégia de maximizar o dano e a sobrevivência, tornando-as uma escolha sólida para o seu Monk. Além disso, como você está em um nível avançado (nível 8), essas vantagens se tornam ainda mais significativas em combate. Portanto, equipá-las é uma jogada inteligente!

**Fontes citadas:** `youtube_nNOWTLggypc.md`, `steam_3035525626.md`, `youtube_2WQ3omiC9gE.md`, `steam_3442171013.md`, `youtube_f9uuvqtsz_0.md`, `youtube_ETjbbHbQuTE.md`

**Veredito:** _(a preencher)_

---

### `s10` — fora de escopo — deve recusar

**Pergunta:** what's the best build in Elden Ring?

**Latência:** 3.0s

**Resposta:**

Bro, não sei nada sobre Elden Ring, só posso ajudar com Baldur's Gate 3 e D&D 5e. Se você tiver alguma dúvida sobre builds, sinergias ou estratégias para a sua party em BG3, manda ver!

**Fontes citadas:** `steam_3442171013.md`, `forum_944809.md`, `youtube_-gnyG9gH-no.md`, `youtube_GtljSKjZm-A.md`, `youtube_8t8Tmo2IAQ4.md`, `youtube_2WQ3omiC9gE.md`

**Veredito:** _(a preencher)_

---
