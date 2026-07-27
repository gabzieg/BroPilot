# Conditions

[![](/w/images/thumb/b/b4/Conditions.png/300px-Conditions.png.webp)](/wiki/File:Conditions.png)

Active conditions are listed on the top left of the character's portrait.

**Conditions** are changes in a character's status, both beneficial and harmful. They can be imposed by certain [Spells](/wiki/Spells "Spells"), class features, surfaces and other environmental hazards, etc. Many conditions are temporary, and some can be removed with the right spell or potion.

## Stack ID

All conditions have a stack ID that is not visible in-game. Two conditions with the same stack ID cannot be applied at the same time. For example, it is not possible to have [![Hastened](/w/images/thumb/d/de/Hastened_Condition_Icon.webp/20px-Hastened_Condition_Icon.webp)](/wiki/Hastened_(Condition) "Hastened (Condition)") [Hastened](/wiki/Hastened_(Condition) "Hastened (Condition)"), and [![Celestial Haste](/w/images/thumb/d/de/Hastened_Condition_Icon.webp/20px-Hastened_Condition_Icon.webp)](/wiki/Celestial_Haste_(Condition) "Celestial Haste (Condition)") [Celestial Haste](/wiki/Celestial_Haste_(Condition) "Celestial Haste (Condition)") and [![Haste Spores](/w/images/thumb/7/7d/Haste_Spores_Condition_Icon.webp/20px-Haste_Spores_Condition_Icon.webp)](/wiki/Haste_Spores_(Condition) "Haste Spores (Condition)") [Haste Spores](/wiki/Haste_Spores_(Condition) "Haste Spores (Condition)") at the same time since they all have the stack ID `HASTE`. What happens the same condition and / or stack ID is applied again is determined by the combination of [stack type](/wiki/Stack_type "Stack type") and [stack priority](/wiki/Stack_priority "Stack priority") of the conditions which are to be applied.

## Stack type

Stack type determines what happens when a condition is applied when that same condition or a condition with the same stack ID is already present. It resolves which condition applies or remains if multiple conditions of the same stack ID are brought upon a creature, and determines which conditions can be added on top of each other for increased duration.

There are four different stack types:

Stack
:   The new condition is applied separately, allowing multiple instances of the same condition.

Ignore
:   The new condition is not applied, and the present stays as it is, keeping its current duration. Often used by equipment variation of conditions, e.g., if a character has [Barkskin](/wiki/Barkskin_(Condition) "Barkskin (Condition)") until long rest and equips the [Barkskin Armour](/wiki/Barkskin_Armour "Barkskin Armour"), the condition from the armour does not replace the one they have until long rest.

Overwrite
:   The present condition is replaced by the new one. For example, if a character has [Hastened](/wiki/Hastened_(Condition) "Hastened (Condition)") from drinking a [![](/w/images/thumb/8/87/POT_Potion_of_Speed_Unfaded_Icon.png/20px-POT_Potion_of_Speed_Unfaded_Icon.png.webp)](/wiki/Potion_of_Speed "Potion of Speed") [Potion of Speed](/wiki/Potion_of_Speed "Potion of Speed") and drinks another one, it replaces the condition they currently have, immediately making them [![Lethargic](/w/images/thumb/3/32/Stunned_Condition_Icon.webp/20px-Stunned_Condition_Icon.webp)](/wiki/Lethargic_(Condition) "Lethargic (Condition)") [Lethargic](/wiki/Lethargic_(Condition) "Lethargic (Condition)").

Additive
:   The duration of the new condition is added onto the duration of the already present condition. So if a creature has 1 turn of [Radiating Orb](/wiki/Radiating_Orb_(Condition) "Radiating Orb (Condition)") remaining and receives it again for 2 turns, it then has 3 turns remaining.

## Duration

The duration of a condition is determined by the source the condition is applied from. Some conditions do not have durations. These may be conditions which are active based on something else, like a passive feature or standing near something. The condition [![Lightly Obscured](/w/images/thumb/b/b1/Lightly_Obscured_Condition_Icon.webp/20px-Lightly_Obscured_Condition_Icon.webp)](/wiki/Lightly_Obscured_(Condition) "Lightly Obscured (Condition)") [Lightly Obscured](/wiki/Lightly_Obscured_(Condition) "Lightly Obscured (Condition)") is a condition that does not have a duration. Instead it is automatically applied if a creature is [![Hiding](/w/images/thumb/5/59/Hiding_Condition_Icon.webp/20px-Hiding_Condition_Icon.webp)](/wiki/Hiding_(Condition) "Hiding (Condition)") [Hiding](/wiki/Hiding_(Condition) "Hiding (Condition)") in a place with scant lighting, and is automatically removed when hiding ends. There are also conditions that do not lose duration over time. These may be conditions that lose duration as a result of something else, like [![Arcane Ward](/w/images/thumb/7/7a/Arcane_Ward_Condition_Icon.webp/20px-Arcane_Ward_Condition_Icon.webp)](/wiki/Arcane_Ward_(Condition) "Arcane Ward (Condition)") [Arcane Ward](/wiki/Arcane_Ward_(Condition) "Arcane Ward (Condition)") which loses duration when its bearer is hit. Conditions also do not lose duration if a character is in in dialogue or a cutscene. However, this only counts for characters that are actuslly part of the dialogue/cutscene, not just listening in.

### Tick type

Tick type determines when a condition reduces its remaining duration and applies its effects. Most of the time this is either at the start or end of an affected creature's turn. When a party member is outside [turn-based mode](/wiki/Turn-based_mode "Turn-based mode") or combat mode, one turn is 6 seconds. Tick type is not displayed in-game, but it can be particularly important for short duration effects.

See also: [Status properties/TickingWithSource](/wiki/Status_properties/TickingWithSource "Status properties/TickingWithSource")

The different tick types are:

StartTurn
:   The condition loses its duration at the start of the creature's turn, which is the default behaviour. Conditions with this tick type effectively last one turn less than their stated duration. For example, a 1 turn duration [![Frozen](/w/images/thumb/c/c6/Frozen_Condition_Icon.webp/20px-Frozen_Condition_Icon.webp)](/wiki/Frozen_(Condition) "Frozen (Condition)") [Frozen](/wiki/Frozen_(Condition) "Frozen (Condition)") effect (from [![Chilled](/w/images/thumb/5/50/Chilled_Condition_Icon.webp/20px-Chilled_Condition_Icon.webp)](/wiki/Chilled_(Condition) "Chilled (Condition)") [Chilled](/wiki/Chilled_(Condition) "Chilled (Condition)")) ends immediately at the start of the frozen creature's turn without disabling it for a single turn. A 2 turn [![Frozen](/w/images/thumb/c/c6/Frozen_Condition_Icon.webp/20px-Frozen_Condition_Icon.webp)](/wiki/Frozen_(Condition) "Frozen (Condition)") [Frozen](/wiki/Frozen_(Condition) "Frozen (Condition)") effect (from [![Encrusted with Frost](/w/images/thumb/9/95/Encrusted_with_Frost_Condition_Icon.webp/20px-Encrusted_with_Frost_Condition_Icon.webp)](/wiki/Encrusted_with_Frost_(Condition) "Encrusted with Frost (Condition)") [Encrusted with Frost](/wiki/Encrusted_with_Frost_(Condition) "Encrusted with Frost (Condition)")) effectively lasts only for 1 turn for the same reason.

EndTurn
:   The condition loses its duration at the end of the creature's turn. An example of this is [![Blade Ward](/w/images/thumb/4/49/Blade_Ward_Condition_Icon.webp/20px-Blade_Ward_Condition_Icon.webp)](/wiki/Blade_Ward_(Condition) "Blade Ward (Condition)") [Blade Ward](/wiki/Blade_Ward_(Condition) "Blade Ward (Condition)"). If a creature applies a condition like this to itself that lasts for 1 turn it loses the condition as soon as soon as it ends its turn, for example using [![Action Surge](/w/images/thumb/4/4d/Action_Surge_Icon.webp/20px-Action_Surge_Icon.webp)](/wiki/Action_Surge "Action Surge") [Action Surge](/wiki/Action_Surge "Action Surge").

StartRound
:   The condition loses its duration at the *start* of the round. The start of the round happens before the first creature in the initiative order starts its turn.

EndRound
:   The condition loses its duration at the *end* of the round. The end of the round happens after the last creature in the initiative order ends its turn.

## Status properties

Some conditions have special properties that make them behave in different ways such as initiating combat or not losing duration over time.

Here is a list of all Status properties:

| Name | Description |
| --- | --- |
| [None](/wiki/Status_properties/None "Status properties/None") |  |
| [Performing](/wiki/Status_properties/Performing "Status properties/Performing") |  |
| [InitiateCombat](/wiki/Status_properties/InitiateCombat "Status properties/InitiateCombat") |  |
| [BringIntoCombat](/wiki/Status_properties/BringIntoCombat "Status properties/BringIntoCombat") | Upon applying a condition flagged with this tag: the party is forced into combat. |
| [ForceOverhead](/wiki/Status_properties/ForceOverhead "Status properties/ForceOverhead") | Displays the condition over the creature's model when applied and removed. |
| [IsChanneled](/wiki/Status_properties/IsChanneled "Status properties/IsChanneled") |  |
| [IsInvulnerable](/wiki/Status_properties/IsInvulnerable "Status properties/IsInvulnerable") | Creatures with this condition do not take damage. |
| [ExcludeFromPortraitRendering](/wiki/Status_properties/ExcludeFromPortraitRendering "Status properties/ExcludeFromPortraitRendering") |  |
| [LoseControl](/wiki/Status_properties/LoseControl "Status properties/LoseControl") | Suspends player control of the character, skipping their user interface |
| [ForceNeutralInteractions](/wiki/Status_properties/ForceNeutralInteractions "Status properties/ForceNeutralInteractions") |  |
| [PeaceOnly](/wiki/Status_properties/PeaceOnly "Status properties/PeaceOnly") | Can only be used outside combat. |
| [AllowLeaveCombat](/wiki/Status_properties/AllowLeaveCombat "Status properties/AllowLeaveCombat") | No forced turn-based combat: meaning enemies are still hostile but not actively attacking the party |
| [DisableImmunityOverhead](/wiki/Status_properties/DisableImmunityOverhead "Status properties/DisableImmunityOverhead") |  |
| [DisableInteractions](/wiki/Status_properties/DisableInteractions "Status properties/DisableInteractions") |  |
| [Toggle](/wiki/Status_properties/Toggle "Status properties/Toggle") |  |
| [IgnoreResting](/wiki/Status_properties/IgnoreResting "Status properties/IgnoreResting") | This condition is not removed after a [long rest](/wiki/Long_rest "Long rest"). |
| [IgnoredByImmobilized](/wiki/Status_properties/IgnoredByImmobilized "Status properties/IgnoredByImmobilized") |  |
| [Blind](/wiki/Status_properties/Blind "Status properties/Blind") |  |
| [MultiplyEffectsByDuration](/wiki/Status_properties/MultiplyEffectsByDuration "Status properties/MultiplyEffectsByDuration") | The effects of this condition is multiplied by the amount of turns remaining. |
| [TickingWithSource](/wiki/Status_properties/TickingWithSource "Status properties/TickingWithSource") | Duration ticks down on the turn of the condition's source. |
| [DisableOverhead](/wiki/Status_properties/DisableOverhead "Status properties/DisableOverhead") | Does not show the condition over the creature's model when applied and removed. |
| [DisableCombatlog](/wiki/Status_properties/DisableCombatlog "Status properties/DisableCombatlog") | Does not show the condition in the combat log when applied or removed. |
| [DisablePortraitIndicator](/wiki/Status_properties/DisablePortraitIndicator "Status properties/DisablePortraitIndicator") | This condition is hidden and does not shown on the creature. |
| [ExecuteFunctorsOnOwner](/wiki/Status_properties/ExecuteFunctorsOnOwner "Status properties/ExecuteFunctorsOnOwner") |  |
| [IsInvulnerableVisible](/wiki/Status_properties/IsInvulnerableVisible "Status properties/IsInvulnerableVisible") |  |
| [ApplyToDead](/wiki/Status_properties/ApplyToDead "Status properties/ApplyToDead") | This condition *persists* even if the object/creatures dies, and remains both in death and after resurrection. |
| [GiveExp](/wiki/Status_properties/GiveExp "Status properties/GiveExp") | Flag used to give the party expierence points upon: resolving a (potential) combat situation |
| [Burning](/wiki/Status_properties/Burning "Status properties/Burning") |  |
| [NonExtendable](/wiki/Status_properties/NonExtendable "Status properties/NonExtendable") |  |
| [FreezeDuration](/wiki/Status_properties/FreezeDuration "Status properties/FreezeDuration") | This condition does not lose duration over time. |
| [UnavailableInActiveRoll](/wiki/Status_properties/UnavailableInActiveRoll "Status properties/UnavailableInActiveRoll") |  |
| [OverheadOnTurn](/wiki/Status_properties/OverheadOnTurn "Status properties/OverheadOnTurn") | Displays the condition over the creatrues model at the start of their turn. |
| [UnsheathInstrument](/wiki/Status_properties/UnsheathInstrument "Status properties/UnsheathInstrument") |  |
| [IndicateDarkness](/wiki/Status_properties/IndicateDarkness "Status properties/IndicateDarkness") |  |
| [LoseControlFriendly](/wiki/Status_properties/LoseControlFriendly "Status properties/LoseControlFriendly") |  |
| [DisableCapabilitiesMessage](/wiki/Status_properties/DisableCapabilitiesMessage "Status properties/DisableCapabilitiesMessage") |  |
| [AllowLeaveDisallowJoinCombat](/wiki/Status_properties/AllowLeaveDisallowJoinCombat "Status properties/AllowLeaveDisallowJoinCombat") |  |

## Condition types

Some conditions have a "type" which indicates how the condition can be removed, prevented, or how it reacts to other actions.

Here are some ways to remove or prevent certain conditions. For a full list of cures and preventions for each condition type, see their articles.

| Type | Representative | Removal | Prevention |
| --- | --- | --- | --- |
| Blinded [Blinded](/wiki/Blinded_(status_group) "Blinded (status group)") | [Blinded](/wiki/Blinded_(Condition) "Blinded (Condition)") [Blinded](/wiki/Blinded_(Condition) "Blinded (Condition)") | [Heal](/wiki/Heal "Heal") [Heal](/wiki/Heal "Heal")  [Lesser Restoration](/wiki/Lesser_Restoration "Lesser Restoration") [Lesser Restoration](/wiki/Lesser_Restoration "Lesser Restoration")  [Remedial Potion](/wiki/Remedial_Potion "Remedial Potion")  [(more)](/wiki/Blinded_(Condition_Type)#Removal "Blinded (Condition Type)") | [Shar's Spear of Evening](/wiki/Shar%27s_Spear_of_Evening "Shar's Spear of Evening")  [Steelwatcher Helmet](/wiki/Steelwatcher_Helmet "Steelwatcher Helmet")  [(more)](/wiki/Blinded_(Condition_Type)#Immunity "Blinded (Condition Type)") |
| Charmed [Charmed](/wiki/Charmed_(status_group) "Charmed (status group)") | [Charmed](/wiki/Charmed_(Condition) "Charmed (Condition)") [Charmed](/wiki/Charmed_(Condition) "Charmed (Condition)") | [Dispel Evil And Good: Break Enchantment](/wiki/Dispel_Evil_And_Good:_Break_Enchantment "Dispel Evil And Good: Break Enchantment") [Dispel Evil And Good: Break Enchantment](/wiki/Dispel_Evil_And_Good:_Break_Enchantment "Dispel Evil And Good: Break Enchantment")  [Stillness of Mind](/wiki/Stillness_of_Mind "Stillness of Mind") [Stillness of Mind](/wiki/Stillness_of_Mind "Stillness of Mind")  [(more)](/wiki/Charmed_(Condition_Type)#Removal "Charmed (Condition Type)") | [Beguiling Defences](/wiki/Beguiling_Defences "Beguiling Defences") [Beguiling Defences](/wiki/Beguiling_Defences "Beguiling Defences")  [Calm Emotions](/wiki/Calm_Emotions "Calm Emotions") [Calm Emotions](/wiki/Calm_Emotions "Calm Emotions")  [Fey Ancestry](/wiki/Fey_Ancestry "Fey Ancestry") [Fey Ancestry](/wiki/Fey_Ancestry "Fey Ancestry")  [(more)](/wiki/Charmed_(Condition_Type)#Immunity "Charmed (Condition Type)") |
| Cursed [Cursed](/wiki/Cursed_(status_group) "Cursed (status group)") | *(none)* | [Greater Restoration](/wiki/Greater_Restoration "Greater Restoration") [Greater Restoration](/wiki/Greater_Restoration "Greater Restoration")  [Remove Curse](/wiki/Remove_Curse "Remove Curse") [Remove Curse](/wiki/Remove_Curse "Remove Curse")  [(more)](/wiki/Cursed_(Condition_Type)#Removal "Cursed (Condition Type)") | [(more)](/wiki/Cursed_(Condition_Type)#Immunity "Cursed (Condition Type)") |
| Diseased [Diseased](/wiki/Diseased_(status_group) "Diseased (status group)") | *(none)* | [Heal](/wiki/Heal "Heal") [Heal](/wiki/Heal "Heal")  [Lay on Hands](/wiki/Lay_on_Hands "Lay on Hands") [Lay on Hands](/wiki/Lay_on_Hands "Lay on Hands")  [Lesser Restoration](/wiki/Lesser_Restoration "Lesser Restoration") [Lesser Restoration](/wiki/Lesser_Restoration "Lesser Restoration")  [(more)](/wiki/Diseased_(Condition_Type)#Removal "Diseased (Condition Type)") | [Divine Health](/wiki/Divine_Health "Divine Health") [Divine Health](/wiki/Divine_Health "Divine Health")  [Purity of Body](/wiki/Purity_of_Body "Purity of Body") [Purity of Body](/wiki/Purity_of_Body "Purity of Body")  [(more)](/wiki/Diseased_(Condition_Type)#Immunity "Diseased (Condition Type)") |
| Frightened [Frightened](/wiki/Frightened_(status_group) "Frightened (status group)") | [Frightened](/wiki/Frightened_(Condition) "Frightened (Condition)") [Frightened](/wiki/Frightened_(Condition) "Frightened (Condition)") | [Dispel Evil and Good](/wiki/Dispel_Evil_and_Good "Dispel Evil and Good") [Dispel Evil and Good](/wiki/Dispel_Evil_and_Good "Dispel Evil and Good")  [Stillness of Mind](/wiki/Stillness_of_Mind "Stillness of Mind") [Stillness of Mind](/wiki/Stillness_of_Mind "Stillness of Mind")  [(more)](/wiki/Frightened_(Condition_Type)#Removal "Frightened (Condition Type)") | [Aura of Courage](/wiki/Aura_of_Courage "Aura of Courage") [Aura of Courage](/wiki/Aura_of_Courage "Aura of Courage")  [Calm Emotions](/wiki/Calm_Emotions "Calm Emotions") [Calm Emotions](/wiki/Calm_Emotions "Calm Emotions")  [Heroism](/wiki/Heroism "Heroism") [Heroism](/wiki/Heroism "Heroism")  [Nature's Ward](/wiki/Nature%27s_Ward "Nature's Ward") [Nature's Ward](/wiki/Nature%27s_Ward "Nature's Ward")  [(more)](/wiki/Frightened_(Condition_Type)#Immunity "Frightened (Condition Type)") |
| Incapacitated [Incapacitated](/wiki/Incapacitated_(status_group) "Incapacitated (status group)") | [Incapacitated](/wiki/Incapacitated_(Condition) "Incapacitated (Condition)") [Incapacitated](/wiki/Incapacitated_(Condition) "Incapacitated (Condition)") | [(more)](/wiki/Incapacitated_(Condition_Type)#Removal "Incapacitated (Condition Type)") | [(more)](/wiki/Incapacitated_(Condition_Type)#Immunity "Incapacitated (Condition Type)") |
| Paralyzed [Paralyzed](/wiki/Paralyzed_(status_group) "Paralyzed (status group)") | [Paralysed](/wiki/Paralysed_(Condition) "Paralysed (Condition)") [Paralysed](/wiki/Paralysed_(Condition) "Paralysed (Condition)") | [Arrow of Salving](/wiki/Arrow_of_Salving "Arrow of Salving")  [Lesser Restoration](/wiki/Lesser_Restoration "Lesser Restoration") [Lesser Restoration](/wiki/Lesser_Restoration "Lesser Restoration")  [(more)](/wiki/Paralyzed_(Condition_Type)#Removal "Paralyzed (Condition Type)") | [Elixir of Guileful Movement](/wiki/Elixir_of_Guileful_Movement "Elixir of Guileful Movement")  [Ring of Free Action](/wiki/Ring_of_Free_Action "Ring of Free Action")  [Freedom of Movement](/wiki/Freedom_of_Movement "Freedom of Movement") [Freedom of Movement](/wiki/Freedom_of_Movement "Freedom of Movement")  [(more)](/wiki/Paralyzed_(Condition_Type)#Immunity "Paralyzed (Condition Type)") |
| Petrified [Petrified](/wiki/Petrified_(status_group) "Petrified (status group)") | [Petrified](/wiki/Petrified_(Condition) "Petrified (Condition)") [Petrified](/wiki/Petrified_(Condition) "Petrified (Condition)") | [Basilisk Oil](/wiki/Basilisk_Oil "Basilisk Oil")  [Greater Restoration](/wiki/Greater_Restoration "Greater Restoration") [Greater Restoration](/wiki/Greater_Restoration "Greater Restoration")  [(more)](/wiki/Petrified_(Condition_Type)#Removal "Petrified (Condition Type)") |  |
| Poisoned [Poisoned](/wiki/Poisoned_(status_group) "Poisoned (status group)") | [Poisoned](/wiki/Poisoned_(Condition) "Poisoned (Condition)") [Poisoned](/wiki/Poisoned_(Condition) "Poisoned (Condition)") | [Antidote](/wiki/Antidote "Antidote")  [Lay on Hands](/wiki/Lay_on_Hands "Lay on Hands") [Lay on Hands](/wiki/Lay_on_Hands "Lay on Hands")  [Lesser Restoration](/wiki/Lesser_Restoration "Lesser Restoration") [Lesser Restoration](/wiki/Lesser_Restoration "Lesser Restoration")  [(more)](/wiki/Poisoned_(Condition_Type)#Removal "Poisoned (Condition Type)") | [Elixir of Poison Resistance](/wiki/Elixir_of_Poison_Resistance "Elixir of Poison Resistance")  [Protection from Poison](/wiki/Protection_from_Poison "Protection from Poison") [Protection from Poison](/wiki/Protection_from_Poison "Protection from Poison")  [Purity of Body](/wiki/Purity_of_Body "Purity of Body") [Purity of Body](/wiki/Purity_of_Body "Purity of Body")  [(more)](/wiki/Poisoned_(Condition_Type)#Immunity "Poisoned (Condition Type)") |
| Polymorphed [Polymorphed](/wiki/Polymorphed_(status_group) "Polymorphed (status group)") | [Polymorphed](/wiki/Polymorphed_(Condition) "Polymorphed (Condition)") [Polymorphed](/wiki/Polymorphed_(Condition) "Polymorphed (Condition)") | Losing all your hit points [hit points](/wiki/Hit_points "Hit points")[[*verify*](/wiki/bg3wiki:Verification "bg3wiki:Verification")]  [(more)](/wiki/Polymorphed_(Condition_Type)#Removal "Polymorphed (Condition Type)") | [Immutable Form](/wiki/Immutable_Form "Immutable Form") [Immutable Form](/wiki/Immutable_Form "Immutable Form")  [(more)](/wiki/Polymorphed_(Condition_Type)#Immunity "Polymorphed (Condition Type)") |
| Prone [Prone](/wiki/Prone_(status_group) "Prone (status group)") | [Prone](/wiki/Prone_(Condition) "Prone (Condition)") [Prone](/wiki/Prone_(Condition) "Prone (Condition)") | [Help](/wiki/Help "Help") [Help](/wiki/Help "Help")  [(more)](/wiki/Prone_(Condition_Type)#Removal "Prone (Condition Type)") | [(more)](/wiki/Prone_(Condition_Type)#Immunity "Prone (Condition Type)") |
| Restrained [Restrained](/wiki/Restrained_(status_group) "Restrained (status group)") | [Restrained](/wiki/Restrained_(Condition) "Restrained (Condition)") [Restrained](/wiki/Restrained_(Condition) "Restrained (Condition)") | [Help](/wiki/Help "Help") [Help](/wiki/Help "Help")  [(more)](/wiki/Restrained_(Condition_Type)#Removal "Restrained (Condition Type)") | [Elixir of Guileful Movement](/wiki/Elixir_of_Guileful_Movement "Elixir of Guileful Movement")  [Ring of Free Action](/wiki/Ring_of_Free_Action "Ring of Free Action")  [Freedom of Movement](/wiki/Freedom_of_Movement "Freedom of Movement") [Freedom of Movement](/wiki/Freedom_of_Movement "Freedom of Movement")  [(more)](/wiki/Restrained_(Condition_Type)#Immunity "Restrained (Condition Type)") |
| Sleeping [Sleeping](/wiki/Sleeping_(status_group) "Sleeping (status group)") | [Sleeping](/wiki/Sleeping_(Condition) "Sleeping (Condition)") [Sleeping](/wiki/Sleeping_(Condition) "Sleeping (Condition)") | [Shove](/wiki/Shove "Shove") [Shove](/wiki/Shove "Shove")  [Prone](/wiki/Prone_(Condition) "Prone (Condition)") [Prone](/wiki/Prone_(Condition) "Prone (Condition)")  [Wet](/wiki/Wet_(Condition) "Wet (Condition)") [Wet](/wiki/Wet_(Condition) "Wet (Condition)")  [(more)](/wiki/Sleeping_(Condition_Type)#Removal "Sleeping (Condition Type)") |  |
| Stunned [Stunned](/wiki/Stunned_(status_group) "Stunned (status group)") | [Stunned](/wiki/Stunned_(Condition) "Stunned (Condition)") [Stunned](/wiki/Stunned_(Condition) "Stunned (Condition)") | [Freedom of Movement](/wiki/Freedom_of_Movement "Freedom of Movement") [Freedom of Movement](/wiki/Freedom_of_Movement "Freedom of Movement")  [Greater Restoration](/wiki/Greater_Restoration "Greater Restoration") [Greater Restoration](/wiki/Greater_Restoration "Greater Restoration")  [(more)](/wiki/Stunned_(Condition_Type)#Removal "Stunned (Condition Type)") |  |
| Unconscious [Unconscious](/wiki/Unconscious_(status_group) "Unconscious (status group)") | *(none)* | [(more)](/wiki/Unconscious_(Condition_Type)#Removal "Unconscious (Condition Type)") | [(more)](/wiki/Unconscious_(Condition_Type)#Immunity "Unconscious (Condition Type)") |

1. [↑](#cite_ref-representative_1-0) Many Condition Types have a specific condition that serves as the most basic form.
2. ↑ [2.0](#cite_ref-adv_2-0) [2.1](#cite_ref-adv_2-1) Gives [![Advantage](/w/images/thumb/f/fc/Advantage_Icon.png/28px-Advantage_Icon.png.webp)](/wiki/Advantage "Advantage") [Advantage](/wiki/Advantage "Advantage") on ![Saving Throw](/w/images/thumb/e/e7/Saving_Throw_Icon.png/25px-Saving_Throw_Icon.png.webp) [Saving Throws](/wiki/Saving_Throw "Saving Throw")
3. [↑](#cite_ref-elemental-fey_3-0) Elemental and fey only.

## List of Conditions

The list of all conditions in the game is split into the following pages so as to limit the size of each page:

- [Conditions/List (1-500)](/wiki/Conditions/List_(1-500) "Conditions/List (1-500)")
- [Conditions/List (501-1000)](/wiki/Conditions/List_(501-1000) "Conditions/List (501-1000)")
- [Conditions/List (1001-1500)](/wiki/Conditions/List_(1001-1500) "Conditions/List (1001-1500)")