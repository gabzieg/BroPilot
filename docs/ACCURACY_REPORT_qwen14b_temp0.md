# BroPilot — Relatório de Acurácia (showcase)

Gerado em 2026-07-29 17:41:38.

> Este documento **coleta evidência fielmente** — pergunta, resposta completa, fontes e latência — rodando a stack real (Ollama + índice + save). Ele **não julga** se uma resposta está certa, incompleta ou alucinada; isso fica para a coluna **Veredito**, deixada em branco para preenchimento humano (ou por um juiz automatizado mais forte) depois.

## Setup

- Data: **2026-07-29 17:41:38**
- Modelo de geração: `qwen2.5:14b-instruct-q4_K_M`
- Temperature: **0.0** | seed: **42** (0 = decodificação gulosa/determinística, não é sorteio)
- Modelo de embedding: `bge-m3` (dim 1024)
- Índice: **5139 chunks** de 209 arquivos
- Save carregado: Cripta Sufocante - 3h 00min.lsv
- Party tinha stats ao vivo (mod companion): **NÃO (sem snapshot do mod companion — Mac não roda o Script Extender/BG3SE deste projeto; ficha da party é só nível/raça/classe)**

---

## Perguntas

### `s1` — regra factual verificável

**Pergunta:** how many Superiority Dice does a Battle Master have at level 5?

**Latência:** 73.1s

**Resposta:**

At Level 3, you mentioned that the Battle Master has 4 superiority dice per short rest. The number of superiority dice typically increases as you gain levels in Fighter and specifically with the Battle Master subclass.

For Levels 1 to 4:
- At Level 1: You start with 2 superiority dice.
- At Level 2: You get an additional superiority die, bringing it up to 3.
- At Level 3: You have 4 superiority dice per short rest.

From what I can gather from the context and typical progression in D&D 5e adapted for Baldur's Gate 3:
- **At Level 5:** A Battle Master would likely gain another superiority die, bringing their total to 5 superiority dice per short rest.

So at level 5, a Battle Master should have 5 superiority dice available after a short or long rest.

**Fontes citadas:** `battle_master.md`, `youtube_PEWnGa-GSJg.md`, `youtube_f9uuvqtsz_0.md`, `feats.md`, `youtube_6DBOv0QC-Ck.md`, `forum_907941.md`

**Veredito:** _(a preencher)_

---

### `s2` — build / subclasse

**Pergunta:** best feats for an Open Hand Monk

**Latência:** 145.0s

**Resposta:**

Para um Open-Hand Monk no contexto de Baldur's Gate 3 e seguindo as regras do D&D 5e adaptado, os Feats mais eficazes são aqueles que maximizam a sua capacidade de dano e consistência. Aqui estão algumas sugestões:

1. **Tavern Brawler**: Este é um dos feats mais poderosos para um Open-Hand Monk. Ele permite que você use o modificador de Força (ou Constituição, se escolher Resilient) em ataques desarmados, dobrando o dano base e tornando os seus golpes muito mais consistentes.

2. **Resilient**: Se você optar por aumentar a sua resistência aos status effects ou melhorar a sua capacidade de manter a concentração nos feitiços (se estiver usando algum), Resilient é uma escolha sólida, especialmente se quiser aumentar o seu CON para maior HP e resistência.

3. **Great Weapon Master**: Embora seja mais comum em builds de guerreiro, GWM pode ser útil para um Monk que usa armas como bastões ou escudos (que podem ser usados conforme as regras do jogo). Isso permite que você faça ataques poderosos e ainda tenha a opção de usar o seu bonus action para Stunning Strike.

4. **Mobile**: Este feat é excelente para manter a sua mobilidade, permitindo que você se mova sem perder a vantagem de ataque após um movimento. Isso é especialmente útil em combates onde você precisa mudar rapidamente entre alvos ou evitar ataques inimigos.

5. **Defensive Duelist**: Este feat pode ser uma escolha interessante para aumentar sua sobrevivência, permitindo que você faça um ataque de reação com vantagem quando é atacado. Isso pode ajudar a manter o seu HP alto e garantir que você possa continuar fazendo dano.

6. **War Caster**: Se você estiver usando feitiços ou habilidades que requerem concentração, War Caster ajuda a manter essa concentração durante o combate, permitindo que você use habilidades como *Stunning Strike* sem perder a concentração em feitiços.

7. **Dual Wielder**: Se você estiver usando duas armas de ataque rápido (como bastões ou escudos), este feat permite que você faça ataques adicionais com vantagem, aumentando ainda mais o seu dano.

Considerando as características do Open-Hand Monk e a sua capacidade de fazer múltiplos ataques em um turno, **Tavern Brawler** é provavelmente a escolha mais forte para maximizar o dano. Se você quiser balancear entre dano e sobrevivência, **Resilient** pode ser uma boa segunda opção.

Lembre-se de que as escolhas específicas podem variar dependendo do seu estilo de jogo e das necessidades da sua party.

**Fontes citadas:** `youtube_bGupbGD2Fw0.md`, `way_of_the_open_hand.md`, `steam_3442171013.md`, `classes.md`, `build_monk_openhand.md`, `forum_944809.md`

**Veredito:** _(a preencher)_

---

### `s3` — build / usa subclasse nova

**Pergunta:** best race for a Battle Master Fighter

**Latência:** 84.7s

**Resposta:**

Based on the context and the information provided in the forum post, the best races for a Battle Master Fighter in Baldur's Gate 3 are Dwarves or Halflings. Here’s why:

1. **Dwarves**: They can make good use of the Dwarven Thrower, which is an excellent weapon for a Battle Master who focuses on throwing weapons. Additionally, dwarves have racial traits that provide resistance to poison and advantage on saving throws against being charmed or frightened.

2. **Halflings**: Halflings are particularly useful because they prevent critical failures (natural 1s) in attack rolls from Act 2 onward. This is crucial for maintaining a high hit rate, which is essential for maximizing damage output as a Battle Master who relies heavily on throwing weapons.

While any race can work with the TB Throw build, Dwarves and Halflings offer specific benefits that enhance your effectiveness as a Battle Master Fighter. If you're looking to maximize your potential in terms of weapon proficiency and reliability, these races are highly recommended.

**Fontes citadas:** `battle_master.md`, `classes.md`, `d&d_5e_rule_changes.md`, `abilities.md`, `skills.md`, `forum_938252.md`

**Veredito:** _(a preencher)_

---

### `s4` — action economy

**Pergunta:** how does bonus action economy work with Dual Wielder?

**Latência:** 153.7s

**Resposta:**

In the context of Baldur's Gate 3 and D&D 5e adapted rules you're playing under, the Dual Wielder feat allows a character to wield two melee weapons at once, even if they are not light weapons. However, there is an important caveat: making an attack with your off-hand weapon requires spending your bonus action.

This means that while Dual Wielder can be powerful for increasing damage output and providing unique passive benefits (like the "Shriek" effect from Phalar Aluve), it comes at the cost of using up a valuable resource—your bonus action. This is particularly impactful because in D&D 5e, bonus actions are limited to one per turn, making them precious.

Here's how this works with your build:

1. **Main Hand Attack**: You can make an attack with your main hand weapon as part of the Attack action.
2. **Off-Hand Attack**: To make an additional attack with your off-hand weapon, you must spend your bonus action.

If the main hand attack kills the target, the off-hand attack is wasted because it requires a separate bonus action to execute and cannot be used reactively after the kill.

### Example Scenario
Let's say you're using Phalar Aluve in your main hand for its "Shriek" effect and another weapon like Hunter’s Dagger in your off-hand. If you make an Attack action with both weapons, you'll need to spend your bonus action on the off-hand attack. This means:

- **Main Hand**: You get the full benefits of Phalar Aluve's passive effects.
- **Off-Hand**: You can use a weapon like Hunter’s Dagger for its unique properties or damage output.

However, if the main hand attack kills an enemy, you lose out on the off-hand attack and waste your bonus action. This is why it's crucial to carefully consider whether the benefits of Dual Wielder outweigh the loss of flexibility in using your bonus action.

### Action Economy Considerations
- **Flexibility**: Bonus actions can be used for many things beyond just attacking, such as casting spells (like Shield), disengaging, hiding, or activating items.
- **Opportunity Cost**: Using a bonus action for an off-hand attack means you cannot use it for other beneficial actions like using Thief abilities, drinking potions, or performing reactions.

### Conclusion
Dual Wielder is most effective when the benefits of wielding specific weapons in each hand outweigh the loss of your bonus action. If you're relying heavily on unique weapon effects and don't have many other uses for your bonus action, it can be a strong choice. However, if you need flexibility with your bonus actions (e.g., using Thief abilities), you might want to reconsider or find ways to mitigate the loss.

In summary, Dual Wielder is powerful but comes at the cost of your bonus action economy. Make sure this trade-off aligns with your build's overall strategy and goals.

**Fontes citadas:** `forum_950966.md`, `youtube_f7uewDCrrqQ.md`, `feats.md`, `d&d_5e_rule_changes.md`, `youtube_9JFz6IviB9Y.md`, `steam_3438196481.md`

**Veredito:** _(a preencher)_

---

### `s5` — multiclasse

**Pergunta:** is a Monk 9 / Rogue 3 multiclass worth it for damage?

**Latência:** 178.2s

**Resposta:**

Para avaliar se um build Monk 9/Rogue 3 é viável para o dano, vamos considerar os benefícios e desvantagens de cada classe nesse nível.

### Benefícios do Build

1. **Monk 9:**
   - **Evasion:** Reduz a chance de sofrer danos críticos.
   - **Stillness of Mind (lvl 8):** Permite usar Ki para reagir e desviar ataques, útil em combate corpo-a-corpo.
   - **Advanced Unarmoured Movement (lvl 9):** Aumenta a velocidade de movimento sem armadura.
   - **Unarmed Damage (1d6 to 1d8 at lvl 9):** Melhora o dano base das técnicas não letais.

2. **Rogue 3:**
   - **Cunning Action:** Permite Dash, Disengage ou Hide como ação livre.
   - **Sneak Attack (lvl 3):** Dano adicional de 1d6 por nível de Rogue.
   - **Assassin Archetype (lvl 3):** 
     - **Assassinate:** Ataques surpresa garantem críticos e dano máximo.
     - **Invisibility:** Permite se tornar invisível como ação livre.

### Desvantagens do Build

1. **Monk 9:**
   - **Perde Action Surge (lvl 6):** Uma habilidade poderosa que permite duas ações em um turno.
   - **+1 AC de armadura:** Se você usar uma armadura, perde o bônus de Con do Monk.

2. **Rogue 3:**
   - **Sem Extra Attack:** Não tem múltiplas ações de ataque como Fighter ou Ranger.
   - **Sneak Attack depende de condições:** Requer vantagem para aplicar dano adicional.

### Comparação com Outros Builds

- **Monk 10 (lvl 9) + Rogue 2:**
  - Ganharia Action Surge, mas perderia um nível de Rogue.
  - Perderia o Assassinate e invisibilidade do Assassin Archetype.

- **Rogue 6 (lvl 8):**
  - Ganharía mais Sneak Attack damage, mas não teria os benefícios únicos do Monk como Evasion e Stillness of Mind.

### Conclusão

O build Monk 9/Rogue 3 é interessante porque combina a flexibilidade de movimento e defesa do Monk com o dano surpresa e invisibilidade do Assassin Rogue. No entanto, você perde Action Surge e +1 AC da armadura, que são poderosas ferramentas para controlar o combate.

Se você pode maximizar as condições para usar Assassinate (surpreender inimigos), este build pode ser extremamente eficaz em dano inicial. No entanto, se a sua party tem dificuldade em garantir surpresas regulares ou se você precisa de mais sustentabilidade no combate, considerar Monk 10/Rogue 2 poderia ser uma opção melhor.

Em resumo, o build é viável para dano, especialmente com condições favoráveis, mas requer cuidado na gestão do combate e da party.

**Fontes citadas:** `steam_3442171013.md`, `youtube_9JFz6IviB9Y.md`, `youtube_Q4iw6MPxSDg.md`, `youtube_f9uuvqtsz_0.md`, `classes.md`, `spells.md`

**Veredito:** _(a preencher)_

---

### `s6` — ambígua — usa o estado do save

**Pergunta:** what's the best level-up choice for my current party?

**Latência:** 167.7s

**Resposta:**

Based on your party composition and the roles each character plays, here are some suggestions for optimal level-ups:

### Generic (Bard: Swords College)
- **Level 9**: Focus on versatility. Consider picking up a feat like "War Caster" to avoid losing spell slots due to concentration checks or another feat that enhances your combat utility.
- **Level 10**: Pick up an AoE damage spell like *Contour Elemental* if you want to deal with multiple enemies at once, or go for *Hero's Feast* to buff the entire party. You can also consider *Wall of Thorns* for situational use.
- **Level 11**: Upcasting *Contour Elemental* to level 6 is a strong choice if you're dealing with elemental mermaids. Otherwise, *Hero's Feast* remains an excellent option for boosting your allies.

### Shadowheart (Cleric: Light Domain)
- **Level 9**: Consider picking up a feat like "Lucky" or "Alert" to enhance survivability and initiative.
- **Level 10**: Focus on spells that complement the party, such as *Aid* to boost everyone's hit points, or *Hero's Feast* for buffs. You can also consider utility spells like *Lesser Restoration*.

### Lae'zel (Fighter: Battle Master)
- **Level 9**: Consider a feat like "Tavern Brawler" if you're not already proficient with improvised weapons.
- **Level 10**: Focus on martial feats that enhance your combat prowess, such as "Great Weapon Master" or "Polearm Master."

### Jaheira (Druid: Circle of the Land)
- **Level 9**: Consider a feat like "War Caster" to maintain concentration better in combat.
- **Level 10**: Focus on spells that enhance your summoning abilities, such as *Contour Elemental* or *Wall of Thorns*. You can also consider utility spells like *Aid*.

### General Tips
- Ensure you have a mix of damage dealers, healers, and support characters. Your Bard should focus on crowd control and buffs.
- Consider multiclassing options if they align with your character's backstory and playstyle. For example, adding some levels in Rogue can enhance skill proficiency and sneak attack damage.

### Specific Suggestions
1. **Generic (Bard)**: Focus on spells like *Hypnotic Pattern* for crowd control and *Healing Word* for quick healing.
2. **Shadowheart (Cleric)**: Utilize *Aid* to boost the party's hit points, and consider *Hero's Feast* for buffs.
3. **Lae'zel (Fighter)**: Enhance your combat prowess with feats like "Great Weapon Master."
4. **Jaheira (Druid)**: Use spells like *Contour Elemental* or *Wall of Thorns* to control the battlefield.

By focusing on these areas, you can ensure that each character is contributing optimally and synergizing well with the rest of the party.

**Fontes citadas:** `forum_948214.md`, `youtube_ETjbbHbQuTE.md`, `forum_885547.md`, `forum_934343.md`, `youtube_Q4iw6MPxSDg.md`, `youtube_sd9WavTJXVE.md`

**Veredito:** _(a preencher)_

---

### `s7` — caster — Shadowheart é Light Domain no save

**Pergunta:** best build for a Light Domain Cleric

**Latência:** 205.4s

**Resposta:**

Building the best possible Light Domain Cleric in Baldur's Gate 3 involves leveraging its unique abilities and synergies to maximize survivability and utility. Here’s how you can optimize your build:

### Class & Subclass Selection:
- **Class:** Cleric
- **Subclass:** Light Domain

### Race:
Since Shadowheart is a Half-Elf, she already has the racial benefits of being able to choose two ability score increases (one from each subrace) and gaining proficiency in one skill. For a tanky build, consider increasing Constitution for better survivability.

### Ability Scores:
1. **Strength:** 8 (Minimum needed for weapon attacks)
2. **Dexterity:** 14-16 (For AC calculation with medium armor)
3. **Constitution:** 16-18 (Primary stat for HP and survivability)
4. **Intelligence:** 10 (Minimum needed for spellcasting ability score)
5. **Wisdom:** 14-16 (Secondary stat for Wisdom-based spells and skills like Perception)
6. **Charisma:** 12-14 (For Diplomacy and other Charisma checks)

### Armor & Weapons:
- **Armor:** Medium armor, preferably one that allows you to apply Dexterity modifier to AC.
- **Weapons:** A melee weapon with decent damage output.

### Spells & Abilities:

#### Level 1:
- **Warding Flare:** This is your bread-and-butter ability. Use it every time an enemy attacks you and the attack would hit; this will give them disadvantage on their next attack roll against you.
  
#### Level 2:
- **Radiant Soul:** Gain resistance to radiant damage, which can be useful if enemies deal radiant damage.

#### Level 3:
- **Channel Divinity: Purify (Light Domain):** Use it to remove conditions from allies or yourself. It’s a versatile ability that can help in various situations.
  
#### Level 4:
- **Radiant Consumption:** Gain temporary hit points when you take radiant damage, which is useful if enemies deal radiant damage.

#### Level 5:
- **Divine Strike (Light Domain):** Your melee attacks deal extra radiant damage. This helps with your damage output and can synergize well with Radiant Consumption.
  
#### Level 6:
- **Warding Flame:** Use this to protect allies from enemy attacks, giving them disadvantage on their next attack roll against the ally.

### Feats & Passives:

1. **Disciple of Life (Feat):** This is crucial for a tanky build as it increases your healing output and makes you more self-sufficient.
2. **War Caster:** Allows you to cast spells while wielding a shield, which can be useful if you need to use a spell that requires concentration.

### Gear & Items:
- **Radiating Orb (Item):** This item is highly recommended as it provides an aura of radiant damage and resistance to enemies within range.
- **Reverberation (Item):** This item enhances your melee attacks, making them more effective. It also synergizes well with Divine Strike.

### Playstyle & Tactics:
1. **Tank Role:** Focus on tanking by maximizing AC through medium armor and Dexterity. Use Warding Flare to mitigate damage.
2. **Support Role:** Utilize Radiant Soul and Purify to support allies, removing conditions and providing temporary hit points.
3. **Damage Dealer:** With Divine Strike and Radiant Consumption, you can deal significant radiant damage.

### Example Build:
- **Race:** Half-Elf (High Elf)
- **Ability Scores:** Str 8, Dex 16, Con 18, Int 10, Wis 14, Cha 12
- **Armor:** Chain Mail (or any medium armor that allows Dexterity to AC)
- **Weapon:** Longsword or Warhammer
- **Feats:** Disciple of Life, War Caster
- **Items:** Radiating Orb, Reverberation

This build focuses on maximizing survivability and utility while still providing decent damage output. The Light Domain’s unique abilities make it a strong choice for a tanky Cleric in Baldur's Gate 3.

**Fontes citadas:** `light_domain.md`, `forum_935207.md`, `youtube_YOgipqWEUV0.md`, `youtube_GtljSKjZm-A.md`, `youtube_ZNaZOkbFlk4.md`, `classes.md`

**Veredito:** _(a preencher)_

---

### `s8` — expõe buraco de magia de propósito

**Pergunta:** which spells should a Circle of the Land Druid prioritize?

**Latência:** 152.7s

**Resposta:**

When prioritizing spells for a **Circle of the Land** Druid, you want to focus on spells that enhance your ability to support allies and deal damage effectively. The Circle of the Land subclass is known for its versatility in using both spellcasting and Wild Shape abilities efficiently. Here are some key spells to prioritize:

### Utility Spells
1. **Enhance Ability (Cat's Grace)**
   - Increases Dexterity by 2, which can be crucial for your party’s melee characters or anyone who benefits from higher AC.

2. **Pass Without Trace**
   - Useful for stealth and exploration scenarios where you need to move undetected.

3. **Guidance**
   - Provides a small but reliable boost to ability checks, helpful in various situations like skill challenges or combat maneuvers.

### Support Spells
1. **Cure Wounds**
   - Essential for healing allies during combat.

2. **Lesser Restoration**
   - Removes one disease or curse from an ally, which can be crucial in certain encounters.

3. **Barkskin**
   - Provides a significant boost to your own AC when you need it most, making you more resilient and able to stay in the fight longer.

### Damage Spells
1. **Scorching Ray**
   - A versatile spell that allows for multiple targets or high single-target damage with its fire damage rider.

2. **Flame Strike**
   - Deals massive fire damage to a large area, ideal for crowd control and dealing significant damage to groups of enemies.

3. **Thunderwave**
   - Pushes enemies away and deals decent damage, useful for controlling the battlefield and disrupting enemy formations.

### Control Spells
1. **Entangle**
   - Slows down multiple enemies, making them easier targets for your allies or yourself when you return to humanoid form.

2. **Web (if available)**
   - Similar to Entangle but with more control over movement and a higher chance of trapping enemies.

3. **Hold Person**
   - A powerful spell that can incapacitate an enemy leader or caster, giving your party a significant advantage in combat.

### Nature Spells
1. **Speak with Animals**
   - Useful for gathering information or completing quests that involve animal companions or nature-related challenges.

2. **Pass without Trace (if not already covered by another source)**
   - As mentioned earlier, this spell is great for stealth and exploration scenarios.

3. **Goodberry**
   - Provides a small but reliable healing option for yourself or allies in between battles.

### Conclusion
The Circle of the Land Druid should focus on spells that enhance their versatility as both a support character and a damage dealer. Spells like **Scorching Ray**, **Flame Strike**, and **Thunderwave** provide strong offensive capabilities, while **Barkskin**, **Cure Wounds**, and **Lesser Restoration** offer solid defensive and supportive options. Additionally, spells like **Enhance Ability (Cat's Grace)** and **Pass Without Trace** can significantly boost your party’s overall effectiveness in various scenarios.

Given the context of your party composition, prioritize spells that complement the strengths of your other characters while addressing any weaknesses they might have.

**Fontes citadas:** `circle_of_the_land.md`, `classes.md`, `steam_3438196481.md`, `companions.md`, `forum_880699.md`, `forum_934932.md`

**Veredito:** _(a preencher)_

---

### `s9` — item — expõe o limite sem-mod no Mac

**Pergunta:** should I equip Gloves of Soul Catching on my Monk?

**Latência:** 106.6s

**Resposta:**

Based on the context and your build as a strength-based monk in Baldur's Gate 3, equipping **Gloves of Soul Catching** seems like an excellent choice. Here’s why:

1. **Damage Boost**: The gloves provide +10 force damage to unarmed strikes, which is significant for a monk who relies heavily on melee attacks.
2. **Healing Capability**: After making an unarmed strike, you can heal yourself by 10 hit points once per turn. This self-healing ability is incredibly useful in sustaining your character during prolonged combat.
3. **Advantage on Attacks and Saves**: You can gain advantage on all attack rolls and saving throws until the end of your next turn, which significantly boosts your offensive capabilities and survivability.

Given that you have a high Strength score (17) and are focusing on unarmed strikes, these gloves synergize perfectly with your build. They enhance both your damage output and durability, making them an essential piece of equipment for any monk focused on maximizing their effectiveness in combat.

Additionally, the gloves' ability to increase your Constitution by +2 up to 20 is a nice bonus that can further improve your survivability and overall performance.

So yes, equipping **Gloves of Soul Catching** would be highly beneficial for your character.

**Fontes citadas:** `youtube_nNOWTLggypc.md`, `steam_3035525626.md`, `youtube_2WQ3omiC9gE.md`, `steam_3442171013.md`, `youtube_f9uuvqtsz_0.md`, `youtube_ETjbbHbQuTE.md`

**Veredito:** _(a preencher)_

---

### `s10` — fora de escopo — deve recusar

**Pergunta:** what's the best build in Elden Ring?

**Latência:** 86.4s

**Resposta:**

It looks like you're asking about the best build in Elden Ring, but based on the context and information provided, it seems we should focus on Baldur's Gate 3 builds. If you have a specific character or class in mind for BG3 that you'd like to optimize, feel free to ask! For Elden Ring, there are many great builds depending on your playstyle and preferences, but if you're looking for something powerful and versatile in BG3, I can definitely help with that.

If you do want information about Elden Ring builds, let me know which character or class you're interested in optimizing, and I'll provide guidance based on the most up-to-date strategies.

**Fontes citadas:** `steam_3442171013.md`, `forum_944809.md`, `youtube_-gnyG9gH-no.md`, `youtube_GtljSKjZm-A.md`, `youtube_8t8Tmo2IAQ4.md`, `youtube_2WQ3omiC9gE.md`

**Veredito:** _(a preencher)_

---
