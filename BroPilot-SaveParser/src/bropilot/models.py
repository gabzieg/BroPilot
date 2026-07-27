"""Modelos do estado da party: savegame em disco + snapshot ao vivo do exporter."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path
from typing import Dict, Optional

#: Onde o mod BroPilotExporter grava o snapshot da party.
DEFAULT_INVENTORY_DUMP = (
    Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
    / "Larian Studios"
    / "Baldur's Gate 3"
    / "Script Extender"
    / "bropilot_inventory.json"
)

_GUID_SUFFIX = re.compile(
    r"_?[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}$"
)

#: Ordem dos tipos de dano no componente de resistências do engine, usada para
#: nomear o array bruto exportado pelo mod.
DAMAGE_TYPES = (
    "None", "Slashing", "Piercing", "Bludgeoning", "Acid", "Thunder",
    "Necrotic", "Fire", "Lightning", "Cold", "Psychic", "Poison",
    "Radiant", "Force",
)

#: Atributos, na ordem canônica de D&D 5e.
ABILITIES = (
    "Strength", "Dexterity", "Constitution",
    "Intelligence", "Wisdom", "Charisma",
)


def _normalize(value: str) -> str:
    """Reduz um nome a letras e dígitos minúsculos, para comparação frouxa."""
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _template_key(template: str) -> str:
    """Extrai a parte legível de um root template.

    'S_Player_Laezel_58a69333-40bf-8358-1d17-fff240d7fb12' -> 'laezel'
    """
    name = _GUID_SUFFIX.sub("", template)
    for prefix in ("S_Player_", "S_", "Player_"):
        if name.startswith(prefix):
            name = name[len(prefix):]
            break
    return _normalize(name)


@dataclass
class Item:
    """Represents an item in the game world."""
    uuid: str | None = None
    template_id: str | None = None
    stats_id: str | None = None
    amount: int = 1
    global_: bool = False
    #: Slot de equipamento ('MeleeMainHand', 'Breast', ...); vazio se na mochila.
    slot: str = ""

    @property
    def equipped(self) -> bool:
        """True quando o item está vestido em algum slot."""
        return bool(self.slot)

    def __repr__(self) -> str:
        label = self.stats_id or self.template_id or self.uuid or "?"
        return f"<Item {label}{' @' + self.slot if self.slot else ''}>"


@dataclass
class Vitals:
    """Pontos de vida e defesa. Campos None = a API não expôs o valor."""
    hp: int | None = None
    max_hp: int | None = None
    temporary_hp: int | None = None
    armor_class: int | None = None
    proficiency_bonus: int | None = None
    spellcasting_ability: str | None = None

    def __repr__(self) -> str:
        hp = f"{self.hp}/{self.max_hp}" if self.max_hp is not None else "?"
        return f"<Vitals hp={hp} ac={self.armor_class}>"


@dataclass
class ActionResource:
    """Recurso de ação: spell slot, ki point, superiority die, channel divinity."""
    name: str
    level: int = 0
    amount: float = 0.0
    max_amount: float = 0.0

    def __repr__(self) -> str:
        level = f" L{self.level}" if self.level else ""
        return f"<{self.name}{level} {self.amount:g}/{self.max_amount:g}>"


@dataclass
class BuildStats:
    """Stats de build de um personagem, vindos do mod BroPilotExporter.

    Cada bloco é independente: um vazio significa que aquela rota de API não
    resolveu nesta versão do Script Extender, não que o personagem não tenha
    o dado. Use `!bropilot_probe` no console do jogo para inspecionar os
    componentes disponíveis.
    """
    abilities: dict[str, int] = field(default_factory=dict)
    vitals: Vitals = field(default_factory=Vitals)
    action_resources: list[ActionResource] = field(default_factory=list)
    passives: list[str] = field(default_factory=list)
    skills: dict[str, object] = field(default_factory=dict)
    resistances: dict[str, str] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    statuses: list[str] = field(default_factory=list)
    position: tuple[float, float, float] | None = None
    classes: list[str] = field(default_factory=list)
    spells: list[str] = field(default_factory=list)
    story_stats: dict[str, object] = field(default_factory=dict)

    @property
    def spell_slots(self) -> list[ActionResource]:
        """Slots de magia por nível, incluindo os de Warlock."""
        return sorted(
            (r for r in self.action_resources if "spellslot" in r.name.lower()),
            key=lambda r: (r.name, r.level),
        )

    def __repr__(self) -> str:
        return (
            f"<BuildStats abilities={len(self.abilities)} "
            f"{self.vitals!r} resources={len(self.action_resources)} "
            f"passives={len(self.passives)}>"
        )


@dataclass
class CharacterSummary:
    """High-level snapshot of a character."""
    name: str
    uuid: str | None = None
    #: Nome traduzido no jogo; só o mod fornece isso.
    display_name: str = ""
    level: int = 1
    xp: int = 0
    race: str = ""
    classes: list[dict[str, str]] = field(default_factory=list)
    position: tuple[float, float, float] = (0.0, 0.0, 0.0)
    inventory: list[Item] = field(default_factory=list)
    #: Equipamento vestido, indexado por slot.
    equipment: dict[str, Item] = field(default_factory=dict)
    #: Stats de build; None quando o mod não forneceu snapshot deste personagem.
    stats: Optional[BuildStats] = None

    def __repr__(self) -> str:
        return (
            f"<CharacterSummary {self.name} Lvl {self.level} "
            f"equip={len(self.equipment)} bag={len(self.inventory)}>"
        )


@dataclass
class Party:
    characters: list[CharacterSummary]

    def __repr__(self) -> str:
        names = ", ".join(c.name for c in self.characters)
        return f"<Party [{names}]>"


@dataclass
class QuestState:
    quest_id: str
    status: str
    flags: set[str] = field(default_factory=set)

    def __repr__(self) -> str:
        return f"<QuestState {self.quest_id} - {self.status} ({len(self.flags)} flags)>"


@dataclass
class CharacterDump:
    """Snapshot ao vivo de um personagem, produzido pelo mod BroPilotExporter."""
    uuid: str
    display_name: str = ""
    template: str = ""
    items: list[Item] = field(default_factory=list)
    equipment: dict[str, Item] = field(default_factory=dict)
    stats: BuildStats = field(default_factory=BuildStats)

    @cached_property
    def template_key(self) -> str:
        """Parte legível do root template, normalizada para o join."""
        return _template_key(self.template)

    def __repr__(self) -> str:
        return f"<CharacterDump {self.template_key or self.uuid} items={len(self.items)}>"


def _read_item(raw: dict) -> Item:
    """Converte uma entrada de item do JSON do mod em Item."""
    return Item(
        uuid=raw.get("UUID") or None,
        template_id=raw.get("Template") or None,
        stats_id=raw.get("Stats") or None,
        amount=raw.get("Amount", 1),
        slot=raw.get("Slot") or "",
    )


def _as_int(value: object) -> int | None:
    """Converte para int quando o valor é numérico; None em qualquer outro caso."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return int(value)


def _read_vitals(raw: dict) -> Vitals:
    """Converte o bloco Vitals do JSON do mod."""
    # O engine devolve a string "None" para quem não conjura.
    ability = raw.get("SpellCastingAbility")
    if str(ability) in ("None", "none", ""):
        ability = None
    return Vitals(
        hp=_as_int(raw.get("Hp")),
        max_hp=_as_int(raw.get("MaxHp")),
        temporary_hp=_as_int(raw.get("TemporaryHp")),
        armor_class=_as_int(raw.get("ArmorClass")),
        proficiency_bonus=_as_int(raw.get("ProficiencyBonus")),
        spellcasting_ability=str(ability) if ability else None,
    )


def _read_resistances(raw: object) -> dict[str, str]:
    """Nomeia as resistências a dano.

    O componente é exportado cru porque seu formato varia: um array indexado
    por tipo de dano, ou um mapa já nomeado. Ambos caem aqui.
    """
    if isinstance(raw, dict):
        return {str(k): str(v) for k, v in raw.items()}
    if isinstance(raw, list):
        return {
            DAMAGE_TYPES[i]: str(v)
            for i, v in enumerate(raw)
            if i < len(DAMAGE_TYPES)
        }
    return {}


def _read_stats(entry: dict) -> BuildStats:
    """Monta os stats de build a partir de uma entrada de personagem do mod."""
    abilities = {
        name: score
        for name, score in (entry.get("Abilities") or {}).items()
        if _as_int(score) is not None
    }

    resources = [
        ActionResource(
            name=str(r.get("Name", "?")),
            level=_as_int(r.get("Level")) or 0,
            amount=float(r.get("Amount") or 0),
            max_amount=float(r.get("MaxAmount") or 0),
        )
        for r in (entry.get("ActionResources") or [])
    ]

    skills = entry.get("Skills")

    return BuildStats(
        abilities={k: int(v) for k, v in abilities.items()},
        vitals=_read_vitals(entry.get("Vitals") or {}),
        action_resources=resources,
        passives=[str(p) for p in (entry.get("Passives") or [])],
        skills=skills if isinstance(skills, dict) else {},
        resistances=_read_resistances(entry.get("Resistances")),
        tags=[str(t) for t in (entry.get("Tags") or [])],
        statuses=[str(s) for s in (entry.get("Statuses") or [])],
        position=tuple(entry.get("Position")) if entry.get("Position") else None,
        classes=[str(c) for c in (entry.get("Classes") or [])],
        spells=[str(s) for s in (entry.get("Spells") or [])],
        story_stats=entry.get("StoryStats") or {},
    )


@dataclass
class InventoryDump:
    """Conteúdo de bropilot_inventory.json já convertido."""
    characters: list[CharacterDump] = field(default_factory=list)
    schema_version: int = 0
    world_context: dict[str, str | bool] = field(default_factory=dict)
    #: Contagem, por bloco de stats, de quantos personagens tiveram o dado
    #: resolvido pelo mod. Serve para detectar rota de API que não existe
    #: nesta versão do Script Extender.
    diagnostics: dict[str, int] = field(default_factory=dict)

    def __bool__(self) -> bool:
        return bool(self.characters)

    def __len__(self) -> int:
        return len(self.characters)

    def __iter__(self):
        return iter(self.characters)

    def unresolved(self) -> list[str]:
        """Blocos de stats que não resolveram para nenhum personagem."""
        size = self.diagnostics.get("PartySize", 0)
        if not size:
            return []
        return sorted(
            key for key, count in self.diagnostics.items()
            if key != "PartySize" and count == 0
        )


def load_dump_file(path: str | Path | None = None) -> InventoryDump:
    """Lê bropilot_inventory.json inteiro, incluindo o bloco de diagnóstico.

    Devolve um dump vazio quando o arquivo não existe ou está corrompido — o mod
    é opcional, e o savegame em disco continua sendo a fonte mínima de verdade.
    """
    path = Path(path) if path else DEFAULT_INVENTORY_DUMP
    if not path.exists():
        return InventoryDump()

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[!] Falha ao ler {path.name}: {exc}")
        return InventoryDump()

    # Schema 2+ embala os personagens em um objeto; o formato antigo era a lista pura.
    is_wrapped = isinstance(raw, dict)
    entries = raw.get("Characters", []) if is_wrapped else raw

    dumps: list[CharacterDump] = []
    for entry in entries:
        uuid = entry.get("UUID")
        if not uuid:
            continue
        dumps.append(
            CharacterDump(
                uuid=uuid,
                display_name=entry.get("DisplayName") or "",
                template=entry.get("Template") or "",
                items=[_read_item(i) for i in entry.get("Items", [])],
                equipment={
                    slot: _read_item(item)
                    for slot, item in (entry.get("Equipment") or {}).items()
                },
                stats=_read_stats(entry),
            )
        )

    diagnostics = raw.get("Diagnostics") or {} if is_wrapped else {}
    return InventoryDump(
        characters=dumps,
        schema_version=raw.get("SchemaVersion", 1) if is_wrapped else 1,
        world_context=raw.get("WorldContext") or {} if is_wrapped else {},
        diagnostics={
            k: v for k, v in diagnostics.items() if isinstance(v, int)
        },
    )


def load_inventory_dump(path: str | Path | None = None) -> list[CharacterDump]:
    """Lê apenas os personagens do snapshot do mod. Veja `load_dump_file`."""
    return load_dump_file(path).characters


def _match_dump(origin: str, dumps: list[CharacterDump]) -> Optional[CharacterDump]:
    """Casa um Origin do SaveInfo.json com um dump do mod.

    SaveInfo.json não expõe UUID, então o join passa pelo root template
    exportado pelo mod: 'S_Player_Laezel_<guid>' casa com o Origin 'Laezel'.
    O nome exibido é a última tentativa, e falha para um Tav customizado.
    """
    key = _normalize(origin)
    if not key:
        return None

    for dump in dumps:
        if dump.template_key == key:
            return dump
    for dump in dumps:
        if dump.template_key and key in dump.template_key:
            return dump
    for dump in dumps:
        if key == _normalize(dump.display_name):
            return dump
    return None


class SaveContext:
    """High-level abstraction for a savegame's data."""

    def __init__(self, savegame, inventory_dump: str | Path | None = None):
        self.savegame = savegame
        self._info = savegame.info
        self._inventory_dump_path = inventory_dump

    @cached_property
    def live_dump(self) -> InventoryDump:
        """Snapshot do mod, se ele rodou nesta sessão. Vazio caso contrário."""
        return load_dump_file(self._inventory_dump_path)

    @cached_property
    def party(self) -> Party:
        """Party ativa do SaveInfo.json, enriquecida com o snapshot do mod.

        Sem o mod instalado, os personagens vêm sem UUID, equipamento e
        inventário — o SaveInfo.json só carrega nível, raça, classes e posição.
        """
        pending = list(self.live_dump)
        chars: list[CharacterSummary] = []
        unmatched: list[CharacterSummary] = []

        for c in self._info.get("Active Party", {}).get("Characters", []):
            origin = c.get("Origin") or c.get("Name", "Unknown")
            char = CharacterSummary(
                name=origin,
                level=c.get("Level", 1),
                xp=c.get("Experience Points (Total)", 0),
                race=c.get("Race", ""),
                classes=c.get("Classes", []),
                position=tuple(c.get("Position", (0.0, 0.0, 0.0))),
            )

            match = _match_dump(origin, pending)
            if match is not None:
                pending.remove(match)
                self._apply_dump(char, match)
            else:
                unmatched.append(char)

            chars.append(char)

        # Sobra exatamente um de cada lado: o par é inequívoco. Acontece com o
        # protagonista, cujo template não deriva do Origin (Tav, Dark Urge).
        if len(unmatched) == 1 and len(pending) == 1:
            self._apply_dump(unmatched[0], pending[0])

        return Party(characters=chars)

    @staticmethod
    def _apply_dump(char: CharacterSummary, dump: CharacterDump) -> None:
        """Copia os dados ao vivo do mod para o resumo do personagem."""
        char.uuid = dump.uuid
        char.display_name = dump.display_name
        char.inventory = dump.items
        char.equipment = dump.equipment
        char.stats = dump.stats

    @property
    def items(self) -> list[Item]:
        """Returns all global items extracted from the save."""
        items_list = []
        try:
            g = self.savegame.globals
            items = g.regions['Items'].children['ItemFactory'][0].children['Items'][0].children['Item']
            for i in items:
                items_list.append(Item(
                    template_id=i.attributes.get('CurrentTemplate'),
                    stats_id=i.attributes.get('Stats'),
                    amount=i.attributes.get('TypeCount', 1),
                    global_=i.attributes.get('Global', False)
                ))
        except (KeyError, IndexError, AttributeError):
            pass
        return items_list

    @property
    def thumbnail(self) -> Optional[bytes]:
        """Returns the image thumbnail (WebP or PNG) of the savegame."""
        for name in self.savegame.namelist():
            if name.lower().endswith(".webp") or name.lower().endswith(".png"):
                return self.savegame.package.read(name)
        return None

    @cached_property
    def quests(self) -> Dict[str, QuestState]:
        """Returns the current state of all tracked quests, extracted from Osiris databases."""
        story = self.savegame.story_save
        quests: Dict[str, QuestState] = {}

        def get_quest(qid: str) -> QuestState:
            if qid not in quests:
                quests[qid] = QuestState(quest_id=qid, status="Unknown", flags=set())
            return quests[qid]

        for db in story.databases.values():
            if not db.owner_node or not db.owner_node.name:
                continue

            name = db.owner_node.name
            if name == "DB_QuestIsAccepted":
                for fact in db.facts:
                    if fact.columns:
                        qid = fact.columns[0].string_value
                        if qid: get_quest(qid).status = "Accepted"
            elif name == "DB_QuestIsOpened":
                for fact in db.facts:
                    if fact.columns:
                        qid = fact.columns[0].string_value
                        if qid:
                            q = get_quest(qid)
                            if q.status != "Closed":
                                q.status = "Opened"
            elif name == "DB_QuestIsClosed":
                for fact in db.facts:
                    if fact.columns:
                        qid = fact.columns[0].string_value
                        if qid: get_quest(qid).status = "Closed"
            elif name == "DB_QuestDef_State":
                for fact in db.facts:
                    if len(fact.columns) >= 3:
                        qid = fact.columns[1].string_value
                        flag = fact.columns[2].string_value
                        if qid and flag:
                            get_quest(qid).flags.add(flag)
            elif name == "DB_QuestDef_ChainedState":
                for fact in db.facts:
                    if len(fact.columns) >= 2:
                        qid = fact.columns[0].string_value
                        flag = fact.columns[1].string_value
                        if qid and flag:
                            get_quest(qid).flags.add(flag)

        return quests
