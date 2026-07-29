"""Testes de serialize.py. Não dependem de nenhum .lsv no repo nem do
SaveParser instalado: montam CharacterSummary/SaveContext de mentira com a
mesma FORMA dos dados reais (verificada num save de verdade).
"""

from __future__ import annotations

import unittest
from dataclasses import dataclass, field
from typing import Optional

from bropilot_core.serialize import (
    extract_signals,
    serialize_character,
    serialize_party,
)


@dataclass
class _Vitals:
    hp: Optional[int] = None
    max_hp: Optional[int] = None
    armor_class: Optional[int] = None


@dataclass
class _BuildStats:
    """Só os campos que serialize consome, com os mesmos nomes do parser."""
    abilities: dict = field(default_factory=dict)
    vitals: _Vitals = field(default_factory=_Vitals)
    passives: list = field(default_factory=list)
    statuses: list = field(default_factory=list)


@dataclass
class _Char:
    name: str
    level: int = 1
    race: str = ""
    # forma real do SaveInfo.json: [{"Main": "Fighter", "Sub": "BattleMaster"}]
    classes: Optional[list] = field(default_factory=list)
    display_name: str = ""
    equipment: dict = field(default_factory=dict)
    stats: Optional[_BuildStats] = None


@dataclass
class _Party:
    characters: list


class _Ctx:
    def __init__(self, chars):
        self.party = _Party(characters=chars)


def _party_realista():
    """Espelha um save real: 4 jogáveis + 3 invocações com Classes=None."""
    return _Ctx([
        _Char("Generic", 8, "Elf_WoodElf", [{"Main": "Bard", "Sub": "SwordsCollege"}]),
        _Char("Shadowheart", 8, "HalfElf_High", [{"Main": "Cleric", "Sub": "LightDomain"}]),
        _Char("Laezel", 8, "Githyanki", [{"Main": "Fighter", "Sub": "BattleMaster"}]),
        _Char("Jaheira", 8, "HalfElf_High", [{"Main": "Druid", "Sub": "CircleOfTheLand"}]),
        _Char("Bipedal_Elemental_Azer", 1, "Azer", None),
        _Char("Bipedal_Fey_Dryad_ConjureWoodlandBeings", 7, "Fey", None),
        _Char("WoodWoad_Dryad_ConjureWoodlandBeings", 6, "Plant", None),
    ])


class SerializePartySemModTest(unittest.TestCase):
    """O cenário do macOS: save em disco, sem snapshot do mod."""

    def setUp(self):
        self.ficha = serialize_party(_party_realista())

    def test_ignora_invocacoes(self):
        # invocações têm Classes=None e não são membros da party
        self.assertIn("4 personagens", self.ficha)
        for invocacao in ("Azer", "WoodWoad", "Dryad"):
            self.assertNotIn(invocacao, self.ficha)

    def test_inclui_nivel_raca_classe_e_subclasse(self):
        self.assertIn("Laezel", self.ficha)
        self.assertIn("Lvl 8", self.ficha)
        self.assertIn("Githyanki", self.ficha)
        self.assertIn("Fighter:BattleMaster", self.ficha)

    def test_declara_ausencia_de_stats_ao_vivo(self):
        self.assertIn("stats ao vivo: não", self.ficha)
        # e diz ao modelo para não falar do que não tem
        self.assertIn("equipamento", self.ficha.lower())
        self.assertIn("Não afirme", self.ficha)

    def test_nao_inventa_campos_vazios(self):
        # nada de "HP None", "CA None", "HP /" — sem mod, esses campos somem
        for proibido in ("None", "HP /", "CA 0", "HP 0/0"):
            self.assertNotIn(proibido, self.ficha)

    def test_ficha_e_curta(self):
        # entra em todo prompt: 4 personagens não podem virar um bloco enorme
        self.assertLess(len(self.ficha), 700)
        self.assertLessEqual(len(self.ficha.splitlines()), 7)


class SerializePartyComModTest(unittest.TestCase):
    """Cenário Windows: o mod forneceu stats."""

    def setUp(self):
        stats = _BuildStats(
            abilities={"Strength": 17, "Dexterity": 14},
            vitals=_Vitals(hp=44, max_hp=52, armor_class=18),
            passives=["TavernBrawler"],
            statuses=["BLESS"],
        )
        self.ctx = _Ctx([
            _Char("Laezel", 5, "Githyanki",
                  [{"Main": "Fighter", "Sub": "BattleMaster"}], stats=stats)
        ])

    def test_inclui_vitais_e_atributos(self):
        ficha = serialize_party(self.ctx)
        self.assertIn("stats ao vivo: sim", ficha)
        self.assertIn("HP 44/52", ficha)
        self.assertIn("CA 18", ficha)
        self.assertIn("STR 17", ficha)
        self.assertIn("BLESS", ficha)

    def test_sem_o_aviso_de_degradacao(self):
        self.assertNotIn("Não afirme", serialize_party(self.ctx))

    def test_verbose_adiciona_passivas(self):
        curto = serialize_party(self.ctx)
        longo = serialize_party(self.ctx, verbose=True)
        self.assertNotIn("TavernBrawler", curto)
        self.assertIn("TavernBrawler", longo)


class SerializeCharacterTest(unittest.TestCase):
    def test_subclasse_vazia_no_nivel_1(self):
        # até o nível 3 o save traz Sub vazio; não pode virar "Monk:"
        linha = serialize_character(
            _Char("Tav", 1, "Halfling_Lightfoot", [{"Main": "Monk", "Sub": None}])
        )
        self.assertIn("[Monk]", linha)
        self.assertNotIn("Monk:", linha)

    def test_multiclasse(self):
        linha = serialize_character(
            _Char("Tav", 9, "Human",
                  [{"Main": "Monk", "Sub": "OpenHand"},
                   {"Main": "Rogue", "Sub": "Thief"}])
        )
        self.assertIn("Monk:OpenHand/Rogue:Thief", linha)

    def test_display_name_tem_prioridade(self):
        linha = serialize_character(
            _Char("Generic", 4, "Human", [{"Main": "Bard", "Sub": ""}],
                  display_name="Avenam")
        )
        self.assertIn("Avenam", linha)


class ExtractSignalsTest(unittest.TestCase):
    def setUp(self):
        self.signals = extract_signals(_party_realista())

    def test_classes_e_subclasses_da_party(self):
        self.assertEqual(
            self.signals["classes"], ["Bard", "Cleric", "Fighter", "Druid"]
        )
        self.assertEqual(
            self.signals["subclasses"],
            ["SwordsCollege", "LightDomain", "BattleMaster", "CircleOfTheLand"],
        )

    def test_ignora_invocacoes(self):
        self.assertEqual(self.signals["levels"], [8, 8, 8, 8])
        self.assertNotIn("Azer", self.signals["races"])

    def test_has_live_stats_falso_sem_mod(self):
        self.assertFalse(self.signals["has_live_stats"])

    def test_racas_deduplicadas_preservando_ordem(self):
        # HalfElf_High aparece 2x na party, mas só uma vez no sinal
        self.assertEqual(
            self.signals["races"], ["Elf_WoodElf", "HalfElf_High", "Githyanki"]
        )

    def test_sem_active_statuses_quando_nao_ha_mod(self):
        # melhor a chave ausente que uma lista vazia fingindo informação
        self.assertNotIn("active_statuses", self.signals)

    def test_has_live_stats_verdadeiro_com_mod(self):
        ctx = _Ctx([
            _Char("Laezel", 5, "Githyanki", [{"Main": "Fighter", "Sub": "BattleMaster"}],
                  stats=_BuildStats(statuses=["BLESS"]))
        ])
        signals = extract_signals(ctx)
        self.assertTrue(signals["has_live_stats"])
        self.assertEqual(signals["active_statuses"], ["BLESS"])


class PartyVaziaTest(unittest.TestCase):
    def test_party_so_com_invocacoes_nao_quebra(self):
        ctx = _Ctx([_Char("Bipedal_Elemental_Azer", 1, "Azer", None)])
        self.assertIn("nenhum personagem", serialize_party(ctx))
        self.assertEqual(extract_signals(ctx)["classes"], [])


if __name__ == "__main__":
    unittest.main()
