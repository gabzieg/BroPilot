"""BroPilot — Baldur's Gate 3 savegame reader and live-assist backend."""

from .lspk import Package, PackageError
from .lsf import Resource, Node, loads as load_lsf, LSFError
from .save import SaveGame, find_saves, latest_save
from .models import SaveContext, Party, CharacterSummary

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
]

__version__ = "0.1.0"
