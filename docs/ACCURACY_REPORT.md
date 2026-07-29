# BroPilot — Relatório de Acurácia (showcase)

Gerado em 2026-07-29 15:44:50.

> As saídas foram **coletadas fielmente** rodando a stack real (Ollama + índice + save) — as respostas abaixo são verbatim, não editadas. O **veredito de cada uma** foi preenchido por um juiz externo (ver seção Avaliação). Resumo: **2 corretas, 3 parciais, 5 com alucinação de regra** em 10 — o retrieval e o save funcionam; o teto é o modelo de geração local.

## Setup

- Data: **2026-07-29 15:44:50**
- Modelo de geração: `qwen2.5:7b-instruct-q4_K_M`
- Modelo de embedding: `bge-m3` (dim 1024)
- Índice: **5139 chunks** de 209 arquivos
- Save carregado: Cripta Sufocante - 3h 00min.lsv
- Party tinha stats ao vivo (mod companion): **NÃO (sem snapshot do mod companion — Mac não roda o Script Extender/BG3SE deste projeto; ficha da party é só nível/raça/classe)**

---

## Avaliação

**Metodologia.** As saídas foram coletadas automaticamente rodando a stack real
(sem cherry-pick — as 10 perguntas incluem, de propósito, casos que expõem
limites conhecidos: buraco de conteúdo de magia, limite sem-mod de item, e um
fora-de-escopo). O julgamento de acerto foi feito por um **juiz externo mais
forte** (Claude, conferido contra as regras de BG3 e as fontes citadas), não pelo
próprio modelo de geração — deixar o `qwen2.5:7b` se autoavaliar seria o réu
julgando a causa. Amostra pequena (n=10): as contagens abaixo são um retrato, não
uma taxa estatística.

**Placar.**

| Veredito | Perguntas | Total |
|---|---|---|
| ✅ Correto / recusou certo | s1, s10 | 2 |
| 🟡 Parcial (núcleo certo, com erro ou vago) | s4, s7, s9 | 3 |
| ❌ Alucinou regra de BG3 | s2, s3, s5, s6, s8 | 5 |

**O que o retrato mostra — a divisão é limpa e importa:**

- **Lookup de fato único funciona** (s1): quando a resposta exata está num chunk
  recuperado, o modelo a cita corretamente.
- **Recusa de fora-de-escopo funciona** (s10): reconheceu Elden Ring e não
  inventou build de outro jogo.
- **Síntese de build multi-fato alucina** (s2, s3, s5, s6): inventa feats que não
  existem, aplica feats que não funcionam na build (Great Weapon Master em golpe
  desarmado), e atribui features de uma classe a outra (Bardic Inspiration a um
  Cleric). É justamente o caso de uso central de um assistente de min-max.
- **A falha se concentra na GERAÇÃO, não no pipeline.** Em todos os casos ruins,
  o retrieval recuperou os arquivos certos e o save foi lido corretamente (party,
  subclasses). O erro nasce quando o `qwen2.5:7b` **sintetiza** — ele inventa
  regra. Duas falhas específicas de honestidade também apareceram: fabricar
  atributos do personagem que não estão na ficha (s9) e trocar de idioma no meio
  da resposta (s3, s6).

**Conclusão acionável.** O investimento em RAG (busca híbrida, dedup, save-aware,
raspagem de subclasses) pagou: o encanamento entrega o contexto certo. O teto
agora é o **modelo de geração local (7B quantizado)**, que não é confiável para
sintetizar conselho de build. O próximo passo indicado é um modelo de geração
mais forte (nuvem — Haiku/GPT-4o-mini — ou um local bem maior), medido de novo
contra esta mesma bateria.

---

## Perguntas

### `s1` — regra factual verificável

**Pergunta:** how many Superiority Dice does a Battle Master have at level 5?

**Latência:** 23.4s

**Resposta:**

Bro, at level 3 you get 4 superiority dice per short rest, and since that's the only time you regain them, you'll still have those 4 at level 5. So, to answer your question: A Battle Master has 4 superiority dice at level 5. These dice are d8s and can be used to enhance attacks or aid allies through maneuvers.

**Fontes citadas:** `battle_master.md`, `youtube_PEWnGa-GSJg.md`, `youtube_f9uuvqtsz_0.md`, `feats.md`, `youtube_6DBOv0QC-Ck.md`, `forum_907941.md`

**Veredito:** ✅ **CORRETO.** 4 dados no nível 5, d8 — bate com `battle_master.md` (a fonte #1). Ressalva menor: "é a única hora que você recupera" está errado (recupera em descanso curto *ou* longo), mas o número, que era a pergunta, está certo. Caso de lookup factual estreito: a resposta exata estava num chunk recuperado.

---

### `s2` — build / subclasse

**Pergunta:** best feats for an Open Hand Monk

**Latência:** 39.4s

**Resposta:**

Bro, when it comes to a maxed-out Open Hand Monk build, the key is stacking as many damage and action economy feats as you can. Here are some top picks for your build:

1. **Tavern Brawler (Lv4)**: This is a no-brainer for any monk who wants to boost their unarmed strikes significantly. It’s crucial for increasing your damage output.

2. **War Caster (Lv5)**: While this feat might seem like it's more suited for spellcasters, it can be incredibly useful if you want to use Flurry of Blows with spells that require concentration, such as *Shield* or *Blink*. It also allows you to make attacks from within a concentration spell.

3. **Great Weapon Master (Lv6)**: This is particularly powerful when combined with your monk’s high Dexterity and extra attack actions. Since Open Hand Monks can make multiple Flurry of Blows, this feat can deal massive damage on hit.

4. **Relentless Fighting (Lv8-9)**: While the additional damage is nice, the real power comes from making more attacks before being forced to stop. With your 10+ attacks per turn and a few extra, this feat can be game-changing for keeping up a relentless assault.

5. **Indomitable Will (Lv12-13)**: If you want to ensure you keep concentration spells active while dealing with lots of damage, this feat is great. While not as directly tied to your primary combat abilities, it's still valuable in ensuring you stay in the fight longer.

6. **Action Surge (Fighter Feat Lv20+)**: While not a level 4-9 feat, if you plan on playing the monk for a long time and have access to it later, this can be incredibly useful for boosting your already high action economy even further.

7. **Extra Attack (Lv6-8)**: For those few levels where you don't get Tavern Brawler, adding an extra attack can still help boost your damage output slightly, but the real power comes from Flurry of Blows and other action economy feats.

Given that you're looking for a build that focuses on pure melee damage, Tavern Brawler and War Caster are going to be the most beneficial. Great Weapon Master will also synergize well with your damage potential, especially if you can use it to boost critical hits or certain spells.

Remember, the key is to maximize your Flurry of Blows and ensure every attack counts for maximum damage. The feats mentioned above will help you do exactly that!

**Fontes citadas:** `youtube_bGupbGD2Fw0.md`, `way_of_the_open_hand.md`, `steam_3442171013.md`, `classes.md`, `build_monk_openhand.md`, `forum_944809.md`

**Veredito:** ❌ **ALUCINOU.** Só Tavern Brawler está correto. Great Weapon Master **não funciona em golpe desarmado** (requer arma pesada) — recomendação mecanicamente inútil para a build. "Relentless Fighting" e "Indomitable Will" **não existem** como feats em BG3. Action Surge e Extra Attack são features de classe, não feats. Fontes certas recuperadas, feats inventados na síntese.

---

### `s3` — build / usa subclasse nova

**Pergunta:** best race for a Battle Master Fighter

**Latência:** 41.9s

**Resposta:**

Para um Guerrero de Batalla (Battle Master Fighter) em Baldur's Gate 3, vamos considerar os aspectos técnicos e estratégicos do jogo, bem como as sinergias específicas da build que você descreveu. 

### Considerações Gerais

1. **HP**: Você mencionou uma prioridade moderada por HP na build, o que sugere que a saúde não é o foco principal.
2. **Damage Riders**: A build inclui habilidades que aumentam a eficiência do lançamento de itens e dano físico.
3. **Action Economy**: O Battle Master tem várias oportunidades para uso de ações e bonus actions, especialmente com Enraged Throw.

### Melhor Raça

Dada a natureza da build, que foca em lançar itens e criando situações desfavoráveis aos inimigos (como provocar a Prone), **Halflings** parecem ser uma excelente escolha. Aqui estão as razões:

1. **Fast Hands**: A habilidade Fast Hands do Halfling fornece um bonus action adicional, o que é perfeito para Enraged Throw e outros lançamentos de itens.

2. **Critical Fail Prevention**: Desde a Act 2 em diante, o fato de evitar críticas falhas (critical fails) pode ser vital, pois isso ajuda a manter a consistência dos seus ataques.

3. **Condições Adversas**: Halflings têm +1 AC natural e uma resistência adicional contra golpes Críticos, o que é útil para evitar status negativos como envenenado ou imobilizado.

### Race Alternativas

- **Dwarf (Humanoid)**: Dwarf Thrower pode ser útil se você planeja lançar itens frequentemente. Além disso, a resistência a dano físico devido à sua raça também pode ser benéfica.
  
- **Gnome**: Gnomos têm uma variedade interessante de habilidades, mas suas vantagens em termos de dano podem não se encaixar tão bem com a build focada em lançamentos.

### Conclusão

**Halflings** são a melhor escolha para um Guerrero de Batalla, principalmente devido à combinação de Fast Hands e resistência contra críticas falhas. No entanto, se você planeja intensamente usar itens como o Dwarven Thrower, **Dwarf** também pode ser uma opção viável.

Espero que isso ajude! Você tem alguma outra pergunta sobre a build ou estratégias específicas?

**Fontes citadas:** `battle_master.md`, `classes.md`, `d&d_5e_rule_changes.md`, `abilities.md`, `skills.md`, `forum_938252.md`

**Veredito:** ❌ **ALUCINOU (e trocou para português no meio do showcase).** Descreveu uma build de **arremesso de Barbarian** — "Enraged Throw" é do Berserker, não do Battle Master. Atribuiu **"Fast Hands" como racial de Halfling**: Fast Hands é do Thief (Rogue); Halfling tem Lucky. Confundiu arquétipo e fatos raciais apesar de recuperar `battle_master.md`.

---

### `s4` — action economy

**Pergunta:** how does bonus action economy work with Dual Wielder?

**Latência:** 56.8s

**Resposta:**

### Bonus Action Economy with Dual Wielder

When it comes to bonus action economy in Baldur's Gate 3, the **Dual Wielder** feat is quite important for certain builds. Here’s how it works:

1. **Basic Operation:**
   - The Dual Wielder feat allows you to wield two non-light weapons (one in each hand) and gives a +1 bonus to your Armor Class while doing so.
   - You cannot use this feat with two-handed weapons.

2. **Two-Weapon Fighting:**
   - Without the Two-Weapon Fighting style, using Dual Wielder does not grant you any additional benefits for off-hand attacks other than the +1 AC bonus and access to the bonus action for your main hand weapon.
   - You still have to rely on regular attack rolls for both weapons.

3. **Action Economy Considerations:**
   - The primary benefit of Dual Wielder is maintaining a high Armor Class without needing a shield, which can be useful in combat scenarios where you want to avoid taking hits and have off-hand attacks available.
   - Since the feat only gives +1 AC and no additional damage from the off-hand weapon unless you use Two-Weapon Fighting, it’s generally not as powerful as some other feats like **Alert** or **Defensive Duelist**, which offer more flexibility.

4. **Versatility:**
   - If your build involves using two staves (which have passive effects), Dual Wielder can be quite useful because it allows you to use both without the restriction of Two-Weapon Fighting.
   - For other builds, especially those that focus on finesse weapons or need to maintain AC, Dual Wielder provides a good balance between protection and the ability to make off-hand attacks.

5. **Comparative Analysis:**
   - As mentioned in the context, for characters who are already using finesse weapons (like rapiers or daggers) and trading damage in favor of defense, Dual Wielder might not be as strong as other feats like **Alert**.
   - However, it can still offer significant benefits in specific situations where you need high AC and occasional off-hand attacks.

6. **Example Build:**
   - A rogue who is focused on stealth and wants to avoid taking hits while maintaining the ability to make off-hand attacks could benefit from Dual Wielder combined with other feats like **Sharpshooter** or **Moderately Armoured**.
   - For a character like Shadowheart (the Cleric), if she needs high AC but can afford to use non-light weapons, Dual Wielder might be a good choice.

In summary, the Dual Wielder feat primarily boosts your Armor Class and gives you an option for making off-hand weapon attacks. However, it doesn’t provide as much action economy or damage potential compared to other feats that offer more flexibility in combat scenarios.

**Fontes citadas:** `forum_950966.md`, `youtube_f7uewDCrrqQ.md`, `feats.md`, `d&d_5e_rule_changes.md`, `youtube_9JFz6IviB9Y.md`, `steam_3438196481.md`

**Veredito:** 🟡 **PARCIAL.** O núcleo está correto (+1 AC, permite empunhar duas armas não-leves, ataque off-hand como ação bônus), mas a resposta é enrolada, cheia de enchimento, e não responde limpo "como funciona a economia de ação de bônus". Sem erro factual grave, mas sem clareza acionável.

---

### `s5` — multiclasse

**Pergunta:** is a Monk 9 / Rogue 3 multiclass worth it for damage?

**Latência:** 77.9s

**Resposta:**

Bro, let's break this down step-by-step. You're looking at a Monk 9/Rogue 3 build for damage output. Here’s how we can analyze it:

### Key Abilities and Features

1. **Monk Level 8 and Below:**
   - Gain Evasion (immunity to opportunity attacks)
   - Get Stillness of Mind (advantage on saving throws against being charmed or frightened)
   - Ki points, but lose Action Surge
   - Improved unarmed damage from 1d6 to 1d8 at level 9

2. **Rogue Level 3:**
   - Gain Cunning Action (extra action per turn)
   - Sneak Attack damage increases to 2d6
   - Choose an archetype, like Assassin for guaranteed critical hits and an extra action on the first attack of combat.

### Damage Analysis:

1. **Initial Turn (Assassin Rogue):**
   - With Cunning Action, you get two turns in a row.
   - First turn: Make your initial attack as an Assassin with the additional bonus action.
     - Guaranteed critical hit (if you surprise the enemy) or standard hit.
     - Second attack with normal actions.

2. **Subsequent Turns (Monk):**
   - Flurry of Blows (extra action for monk) gives you another flurry.
   - Each flurry allows three attacks, two unarmed and one from a weapon (assuming you have a secondary weapon).

3. **Sneak Attack Damage:**
   - With 2d6 sneak attack damage, you can deal significant additional damage per hit.

### Action Economy:

- **Monk:** You get an extra action at the start of combat due to Cunning Action and Flurry of Blows.
- **Rogue:** Additional actions from both classes stack well, giving you more opportunities to land critical hits and apply sneak attack.

### Example Combat Scenario

1. **Turn 1 (Assassin Rogue):**
   - Use Cunning Action for two turns in a row.
   - First turn: Guaranteed critical hit with your initial attack if the enemy is surprised.
     - Damage: 2d6 + weapon damage + sneak attack (2d6) = potential 8-15 damage on this single hit.
   - Second turn: Normal attack, potentially another critical or just a standard hit.

2. **Turns 2+ (Monk):**
   - Use Flurry of Blows for three attacks each round:
     - Two unarmed and one from your weapon.
     - Sneak Attack applies to these hits if the target is surprised.

### Comparison to Other Classes

- **Compared to a Fighter with Extra Attack:** 
  - A full six levels into Rogue gives you an extra action, which can be more impactful than just two attacks at level 3. The guaranteed critical and additional sneak attack damage make up for the loss of Extra Attack.
  
- **Compared to Pure Rogue:**
  - You lose Action Surge but gain Evasion and Stillness of Mind, making your survival better in combat.

### Conclusion

Yeah, man, a Monk 9/Rogue 3 is definitely worth it for damage. The extra action from Cunning Action paired with Flurry of Blows gives you significant burst potential. Plus, the sneak attack damage increases to 2d6 and the Assurance Strike (if you choose Rogue assassin) make your critical hits even more deadly.

So, if you're looking for a build that can deal massive damage in a short burst, this is a solid choice. Just make sure you have good positioning and opportunities to surprise enemies for those guaranteed criticals!

**Fontes citadas:** `steam_3442171013.md`, `youtube_9JFz6IviB9Y.md`, `youtube_Q4iw6MPxSDg.md`, `youtube_f9uuvqtsz_0.md`, `classes.md`, `spells.md`

**Veredito:** ❌ **ALUCINOU.** A premissa de dano inteira é falsa: **Sneak Attack não funciona com punho** (não conta como arma acurada) — fato que está no próprio doc refinado do One Punch Monk. Além disso: "Evasion = imunidade a ataque de oportunidade" (errado, é save de Destreza), "Cunning Action te dá dois turnos" (errado), e "Assurance Strike" (feat inventado).

---

### `s6` — ambígua — usa o estado do save

**Pergunta:** what's the best level-up choice for my current party?

**Latência:** 79.1s

**Resposta:**

Com base no estado atual da sua party e nas recomendações dos recursos fornecidos, vou analisar as melhores opções para o nível de upgrade (9) de cada personagem. Vamos considerar as sinergias, a action economy e os benefícios específicos de cada classe.

### 1. Generic - Bard: Swords College
**Atualmente em Nível 8**
- **Skill Proficiencies:** Acrobatics, Performance, Persuasion
- **Expertise (Slight of Hand)**
- **Bardic Inspiration d6**

**Melhor Opção de Nível 9: War Caster**

#### Raisons:
1. **Action Economy:** War Caster permite que você use uma ação de ataque para lançar um feitiço, o que pode ser extremamente útil em combates.
2. **Versatilidade:** Com Expertise (Slight of Hand) e a habilidade de lançar feitiços durante ações de ataque, você se torna muito mais versátil no campo de batalha.

### 2. Shadowheart - Cleric: Light Domain
**Atualmente em Nível 8**
- **Spell Slots:** 1/3, 2/5, 3/7, 4/9 (Restante)
- **Cantrips:** Sacred Flame, Lesser Infliction, Vicious Mockery
- **Domains:** Light

**Melhor Opção de Nível 9: Bardic Inspiration d8 e Font of Inspiration**

#### Raisons:
1. **Bardic Inspiration d8:** Maior magnitude para seus buff de inspiração.
2. **Font of Inspiration:** Permite que você use Inspirations em combate, o que pode ser crucial para manter seus aliados vivos.

### 3. Laezel - Fighter: Battle Master
**Atualmente em Nível 8**
- **Skill Proficiencies:** Athletics, Perception
- **Action Surge:** 2/Day

**Melhor Opção de Nível 9: Expertise (Slight of Hand) ou Action Surge**

#### Raisons:
1. **Expertise (Slight of Hand):** Melhora sua habilidade de desarmar armadilhas e fazer furtos, o que pode ser útil em cenários não-combativos.
2. **Action Surge:** Com mais uma ação adicional, você pode se tornar ainda mais agressivo no campo de batalha.

### 4. Jaheira - Druid: Circle of the Land
**Atualmente em Nível 8**
- **Skill Proficiencies:** Insight, Perception
- **Spell Slots:** 1/2, 3/5 (Restante)
- **Domain Spells:** Lesser Restoration, Spirit Guardians

**Melhor Opção de Nível 9: Bardic Inspiration d8 e Font of Inspiration**

#### Raisons:
1. **Bardic Inspiration d8:** Mesmo benefício para a party que o Shadowheart terá.
2. **Font of Inspiration:** Mesma vantagem de combate.

### Sumarizando as escolhas:

- **Generic (Swords College):** War Caster
- **Shadowheart (Light Domain):** Bardic Inspiration d8 e Font of Inspiration
- **Laezel (Battle Master):** Expertise (Slight of Hand) ou Action Surge
- **Jaheira (Circle of the Land):** Bardic Inspiration d8 e Font of Inspiration

Essas escolhas maximizam a versatilidade, a action economy e os benefícios de cada personagem, proporcionando uma party ainda mais forte em combates.

**Fontes citadas:** `forum_948214.md`, `youtube_ETjbbHbQuTE.md`, `forum_885547.md`, `forum_934343.md`, `youtube_Q4iw6MPxSDg.md`, `youtube_sd9WavTJXVE.md`

**Veredito:** ❌ **ALUCINOU (e trocou para português).** Leu a party corretamente (os 4 personagens e suas subclasses — o save funciona). Mas recomendou **"Bardic Inspiration + Font of Inspiration" para a Shadowheart (Cleric) e a Jaheira (Druid)** — são features de **Bard**. E "Expertise" para a Laezel (Fighter não tem). Recomendação cross-class sem sentido: retrieval + save certos, síntese errada.

---

### `s7` — caster — Shadowheart é Light Domain no save

**Pergunta:** best build for a Light Domain Cleric

**Latência:** 65.1s

**Resposta:**

Bro, considering the state of your party and the context you've provided, the best build for a Light Domain cleric in Baldur's Gate 3 would be focusing on Shadowheart. Here’s why:

1. **Role Fit**: Shadowheart is already established as a tank with a heavy focus on defensive capabilities and damage reduction. Transitioning her into a Light Domain cleric aligns well with her character concept.

2. **Defensive Focus**: The Light Domain provides a powerful defensive ability through "Warding Flare," which can give enemies disadvantage on their attacks against Shadowheart. This is a game-changing feature, especially for a tanky character like her.

3. **Action Economy**: Since Light Domain grants the "Warding Flare" reaction, it optimizes your action economy by allowing you to protect yourself and allies from attacks without needing to take an extra action or provoke reactions yourself.

4. **Healing Potential**: While Light Domain doesn't excel in direct healing like Life Domain, it still provides a decent amount of healing through "Bless," which can be buffed further with the "Disciple of Life" feat. However, the main focus should remain on defense and crowd control.

5. **Spell Choices**: With Light Domain, you get access to spells like "Reverberate" and "Radiant Orb," which are highly effective in AoE damage and status effects. These can complement Shadowheart's existing abilities well.

Given these points, let’s break down the build:

### Key Features of a Light Domain Cleric

1. **Warding Flare**: This reaction gives enemies disadvantage on attacks against you, making it almost impossible for them to hit you unless they have exceptional accuracy or features that ignore this effect (e.g., Extra Attack).

2. **Reverberate and Radiant Orb**: These spells can be used offensively to deal significant AoE damage and debuff enemies.

3. **Bless**: While not as powerful as direct healing, it still provides a useful buff to allies, especially with the "Disciple of Life" feat for extra healing power.

### Feats and Abilities

- **Disciple of Life (feat)**: This gives you +2 bonus healing per spell slot level used on "Healing Word." This is crucial as Shadowheart can use her bonus actions effectively for healing.
  
- **Heavy Armor Proficiency**: To maximize your AC, consider equipping heavy armor. With medium dexterity from being a High Elf, you should still be able to achieve high AC.

### Summary

Shadowheart as a Light Domain cleric would excel in providing both defensive and offensive support. Her "Warding Flare" ability is unparalleled for a tank character, and her spell choices can synergize well with the party's overall strategy.

So, bro, let’s go with this build. It fits Shadowheart's role perfectly and maximizes her potential as a formidable tank in combat.

**Fontes citadas:** `light_domain.md`, `forum_935207.md`, `youtube_YOgipqWEUV0.md`, `youtube_GtljSKjZm-A.md`, `youtube_ZNaZOkbFlk4.md`, `classes.md`

**Veredito:** 🟡 **PARCIAL.** Acertou o essencial (Warding Flare é o núcleo do Light Domain, recuperado de `light_domain.md`). Mas "Disciple of Life" descrito como feat (é feature de Life Domain) e "Radiant Orb" como magia (é condição de item). Núcleo correto, bordas com conflação de regra.

---

### `s8` — expõe buraco de magia de propósito

**Pergunta:** which spells should a Circle of the Land Druid prioritize?

**Latência:** 63.5s

**Resposta:**

Bro, you're asking aboutCircle of the Land Druids, and that's your girl Jaheira right there. So let's break down what she can focus on to make her build shine in combat.

### Key Aspects for Circle of the Land Druid:
1. **Action Economy**: Maximize your spell slots and use them efficiently.
2. **Damage Riders**: Look for spells that stack well with each other or offer significant damage boosts.
3. **Buff Companions**: Support your party through buffs and utility spells.

### Prioritizing Spells:

#### 1. **Wild Shape**
   - Since Circle of the Land Druids are all about using both spells and Wild Shape, you'll want to ensure you have a mix of forms that offer good damage or utility.
   - Bear Form: Great for close combat with strong physical attacks.
   - Wolf Form: Useful for ranged attacks and movement.
   - Eagle Form: Good for scouting and long-range support.

#### 2. **Utility Spells**
   - *Pass Without Trace*: Essential for stealth and avoiding detection, especially since you have access to other utility skills like Cat's Grace.
   - *Animal Friendship* (or similar spells): Helps with crowd control or healing allies in animal form.
   - *Entangle*: Useful for controlling the battlefield.

#### 3. **Damage Spells**
   - *Nature's Ward* (Circle of the Land Spell Slot 1): Provides a decent amount of temporary hit points and can be used to protect yourself or an ally.
   - *Flame Blade* (Warlock Spell Slot, if you have access): A good way to deal consistent damage while maintaining your spell slots.

#### 4. **Buff Spells**
   - *Guidance*: Essential for buffing allies with ability checks.
   - *Cure Wounds*: Always useful for healing allies.
   - *Augury* (Circle of the Land Spell Slot 1): Provides insight into future events, which can be crucial in combat.

### Example Spell List:
- **Wild Shape**: Bear Form (for physical damage and protection), Eagle Form (for scouting).
- **Nature's Ward** or similar buff spells.
- *Guidance* for allies.
- *Cure Wounds* to support the party.
- *Animal Friendship* or *Entangle* for crowd control.

### Tips:
1. **Wild Shape Wisely**: Use your forms based on the situation. Bear Form is great for tanking, while Eagle Form can be used for scouting or long-range attacks.
2. **Spell Slot Management**: Prioritize spells that have a high impact and use your spell slots efficiently. Don't waste them on less effective options.
3. **Buff Companions**: Keep an eye on the party’s health and buffs. Use *Guidance* and *Cure Wounds* to keep everyone healthy and performing at their best.

By focusing on these spells, Jaheira can provide balanced support and direct damage in combat, making her a valuable asset to the party.

**Fontes citadas:** `circle_of_the_land.md`, `classes.md`, `steam_3438196481.md`, `companions.md`, `forum_880699.md`, `forum_934932.md`

**Veredito:** ❌ **ALUCINOU.** Pergunta desenhada para expor o buraco de conteúdo de magia (a base só tem `spells.md` de categoria, sem página por magia) — e o modelo preencheu o vazio com erro: "Flame Blade como magia de Warlock" (é de Druid), "Nature's Ward como magia" (é feature). Lacuna de conteúdo + alucinação de regra.

---

### `s9` — item — expõe o limite sem-mod no Mac

**Pergunta:** should I equip Gloves of Soul Catching on my Monk?

**Latência:** 59.1s

**Resposta:**

Bro, considering your build and the context you've provided, equipping the Gloves of Soul Catching would be a solid choice for your monk. Here’s why:

1. **Buffed Unarmed Damage**: Your monk has high Strength (likely 17) and Wisdom (at least 14), which makes the Gloves of Soul Catching's +1d10 Force damage to unarmed strikes very appealing. This can significantly boost your damage output when you choose to use your fists.

2. **Healing on Unarmed Strikes**: The gloves offer a potent healing effect, giving you 10 HP per turn if you make an unarmed strike. This can be incredibly useful for staying in the fight longer and regaining health without relying solely on potions or other consumables.

3. **Advantage on All Attack Rolls and Saving Throws Until Next Turn**: Although this benefit isn't as strong as the Gloves of Soul Catching's healing, it’s still a valuable asset. It allows you to take advantage of situations where your enemies might be more vulnerable due to reduced hit points or other debuffs.

4. **Recovery During Rests**: The gloves can also provide a +2 Constitution bonus when worn, which is significant for improving your base stats and overall survivability.

5. **Coordinating with Your Party**: As you mentioned having the Shadowheart (Cleric) in the party, it might be beneficial to coordinate with her spells like *Sanctuary* or *Bless*. The Gloves of Soul Catching’s healing effect can synergize well with these types of buffs.

6. **Combat Strategy**: Given your build focuses on high AC and dodging attacks (with your Tavern Brawler feat), the gloves won't hinder this strategy. In fact, you might find yourself in a position where you’re taking fewer hits while still dealing significant damage, thanks to your enhanced unarmed strikes and potential healing.

In summary, equipping the Gloves of Soul Catching aligns well with your build’s strengths and offers substantial benefits that can enhance both your offensive capabilities and survivability. Go for it, bro!

**Fontes citadas:** `youtube_nNOWTLggypc.md`, `steam_3035525626.md`, `youtube_2WQ3omiC9gE.md`, `steam_3442171013.md`, `youtube_f9uuvqtsz_0.md`, `youtube_ETjbbHbQuTE.md`

**Veredito:** 🟡 **PARCIAL — com a falha crítica de honestidade.** Os fatos do item estão corretos (vieram do doc refinado `youtube_nNOWTLggypc.md`). Mas **inventou os atributos do personagem** — "provavelmente 17 de Força, 14 de Sabedoria" — que ele **não tem como ver** sem o mod companion (não roda no Mac). É exatamente a falha de honestidade-de-degradação que o aviso do boot deveria impedir: afirmar sobre stats que não existem na ficha.

---

### `s10` — fora de escopo — deve recusar

**Pergunta:** what's the best build in Elden Ring?

**Latência:** 68.6s

**Resposta:**

Bro, you're asking about Elden Ring while we've been deep in Baldur's Gate 3 discussions! Those are two different games with totally distinct mechanics and builds. If you want advice on Baldur's Gate 3, I can give you the lowdown, but for Elden Ring, that’s more of a FromSoftware thing.

However, if you're looking to shift gears in BG3, here's what we've got:

### Bardic Swordmaster (College of Swords)
- **Generic**: Level 8 Wood Elf [Bard:Swords College]
This build is fantastic for its high attack frequency and damage output. It leverages the Slashing Flourish ability from College of Swords to double your attacks per turn, making it incredibly versatile.

### Spellblade (High Charisma Build)
- **Shadowheart**: Level 8 Half-Elf [Cleric:Light Domain]
This build focuses on Eldritch Blast and the Duellist's Prerogative for extra melee attacks. The Dual Wielder feat and Ring of Arcane Synergy stack to give you an impressive amount of damage, making this build both potent in spells and melee.

### Gloomstalker Rogue
- **Starion**: Level 8 Githyanki [Rogue:Gloom]
This build is highly damaging with a good balance between stealth and direct combat. The Titanstring Bow can be incredibly effective when paired with Strength Elixirs for flat damage output, making it a strong solo runner.

### Fighter (Battle Master)
- **Laezel**: Level 8 Githyanki [Fighter: Battle Master]
This build excels in close-combat and utility. The Extra Attack from Fighter levels combined with maneuvers like Trip or Disengage can make Laezel a formidable frontliner.

Given your party setup, if you're looking for the best damage output and versatility:

1. **Generic** should focus on maxing out attacks using Slashing Flourish.
2. **Shadowheart** could use her spells but also benefit from Eldritch Blast and extra melee attacks.
3. **Laezel** as a Fighter can be a solid tank with Extra Attack, making him more reliable in front-line combat.
4. **Jaherira**, as a Druid, is already very versatile and can handle a wide range of scenarios.

Remember, the best build often depends on your playstyle and party dynamics. If you're looking for raw damage output, Gloomstalker Rogue or Bardic Swordmaster might be top contenders, but a balanced approach with multiple roles covered by your party could also yield great results!

**Fontes citadas:** `steam_3442171013.md`, `forum_944809.md`, `youtube_-gnyG9gH-no.md`, `youtube_GtljSKjZm-A.md`, `youtube_8t8Tmo2IAQ4.md`, `youtube_2WQ3omiC9gE.md`

**Veredito:** ✅ **RECUSOU CORRETAMENTE (o teste principal) — pivô com erros.** Reconheceu que Elden Ring é outro jogo e não deu build de Elden Ring: comportamento desejado, e melhor que a alucinação de execuções anteriores. O pivô para BG3, porém, inventou um membro de party ("Starion", que não existe nesta party) e deu Eldritch Blast (Warlock) para a Shadowheart (Cleric). Recusa: passou. Pivô: porco.

---
