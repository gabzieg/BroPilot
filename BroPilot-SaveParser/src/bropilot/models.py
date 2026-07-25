from dataclasses import dataclass, field
from typing import Any, Optional, Dict
from functools import cached_property

@dataclass
class Item:
    """Represents an item in the game world."""
    uuid: str | None = None
    template_id: str | None = None
    stats_id: str | None = None
    amount: int = 1
    global_: bool = False

@dataclass
class CharacterSummary:
    """High-level snapshot of a character."""
    name: str
    uuid: str | None = None
    level: int = 1
    xp: int = 0
    race: str = ""
    classes: list[dict[str, str]] = field(default_factory=list)
    position: tuple[float, float, float] = (0.0, 0.0, 0.0)
    inventory: list[Item] = field(default_factory=list)

    def __repr__(self) -> str:
        return f"<CharacterSummary {self.name} Lvl {self.level}>"

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

class SaveContext:
    """High-level abstraction for a savegame's data."""
    
    def __init__(self, savegame):
        self.savegame = savegame
        self._info = savegame.info

    @property
    def party(self) -> Party:
        """Returns the active party summary extracted from SaveInfo.json."""
        import os
        import json
        
        # Load the external inventory dump if available
        inventory_dump_path = os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Larian Studios', "Baldur's Gate 3", 'Script Extender', 'bropilot_inventory.json')
        inventories = {}
        if os.path.exists(inventory_dump_path):
            try:
                with open(inventory_dump_path, 'r', encoding='utf-8') as f:
                    inv_data = json.load(f)
                    for char_inv in inv_data:
                        char_uuid = char_inv.get("UUID")
                        if char_uuid:
                            items = []
                            for i in char_inv.get("Items", []):
                                items.append(Item(
                                    uuid=i.get("UUID"),
                                    template_id=i.get("Template"),
                                    stats_id=i.get("Stats"),
                                    amount=i.get("Amount", 1),
                                    global_=False
                                ))
                            inventories[char_uuid] = items
            except Exception as e:
                print(f"Failed to load inventory JSON: {e}")

        chars = []
        party_data = self._info.get("Active Party", {}).get("Characters", [])
        for c in party_data:
            char_name = c.get("Origin") or c.get("Name", "Unknown")
            # Usually the UUID is not directly in SaveInfo.json, but the character has a UUID.
            # We can map by Name if UUID is missing, or rely on future lookup.
            # For now, we will add empty inventory, or match by order/name if we had the UUID.
            # (Note: we lack the exact UUID in SaveInfo.json, so we might need a workaround later if not found).
            chars.append(CharacterSummary(
                name=char_name,
                level=c.get("Level", 1),
                xp=c.get("Experience Points (Total)", 0),
                race=c.get("Race", ""),
                classes=c.get("Classes", []),
                position=tuple(c.get("Position", (0, 0, 0))),
                # In a real implementation we would match by UUID, but since SaveInfo lacks it, 
                # we just store the inventories dict in SaveContext and let users match them manually or by name.
            ))
            
        # We store the raw mapped inventories on the context for now
        self._character_inventories = inventories
        return Party(characters=chars)
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
