"""BroPilot — Baldur's Gate 3 savegame reader and live-assist backend."""

from .lspk import Package, PackageError
from .lsf import Resource, Node, loads as load_lsf, LSFError
from .save import SaveGame, find_saves, latest_save
from .models import (
    ActionResource,
    BuildStats,
    CharacterDump,
    CharacterSummary,
    InventoryDump,
    Item,
    Party,
    QuestState,
    SaveContext,
    Vitals,
    load_dump_file,
    load_inventory_dump,
)

__all__ = [
    "Package",
    "PackageError",
    "Resource",
    "Node",
    "load_lsf",
    "LSFError",
    "SaveGame",
    "find_saves",
    "latest_save",
    "SaveContext",
    "Party",
    "CharacterSummary",
    "CharacterDump",
    "InventoryDump",
    "BuildStats",
    "Vitals",
    "ActionResource",
    "Item",
    "QuestState",
    "load_dump_file",
    "load_inventory_dump",
]

__version__ = "0.1.0"
