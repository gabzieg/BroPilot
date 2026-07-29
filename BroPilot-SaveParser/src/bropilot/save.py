"""High-level savegame access: locate .lsv files and read their contents."""

from __future__ import annotations

import json
import os
import sys
from functools import cached_property
from pathlib import Path

from . import lsf
from .lspk import Package

#: Caminho do Windows. Mantido como está: é o contrato existente e o que roda
#: na máquina dos parceiros. `default_save_root()` é quem escolhe por
#: plataforma; esta constante continua sendo o valor do Windows.
DEFAULT_SAVE_ROOT = (
    Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
    / "Larian Studios"
    / "Baldur's Gate 3"
    / "PlayerProfiles"
    / "Public"
    / "Savegames"
    / "Story"
)

#: No macOS o BG3 grava em ~/Documents, não em Application Support. Verificado
#: numa instalação real (40 saves), com a mesma estrutura de subpastas do
#: Windows, incluindo o nível "Story".
MACOS_SAVE_ROOT = (
    Path.home()
    / "Documents"
    / "Larian Studios"
    / "Baldur's Gate 3"
    / "PlayerProfiles"
    / "Public"
    / "Savegames"
    / "Story"
)

#: Sobrescreve a resolução por plataforma. Existe porque o caminho varia com
#: instalação via Steam/GOG, iCloud sincronizando ~/Documents, e Proton no
#: Linux — casos demais para adivinhar.
SAVE_ROOT_ENV = "BROPILOT_SAVE_ROOT"


def default_save_root() -> Path:
    """Onde procurar saves nesta máquina.

    Ordem: env var BROPILOT_SAVE_ROOT > caminho da plataforma. Fora do macOS
    cai no DEFAULT_SAVE_ROOT (Windows), que também é o palpite menos ruim para
    Linux sob Proton, onde o prefixo Wine reproduz a árvore do Windows.
    """
    override = os.environ.get(SAVE_ROOT_ENV)
    if override:
        return Path(override).expanduser()
    if sys.platform == "darwin":
        return MACOS_SAVE_ROOT
    return DEFAULT_SAVE_ROOT


def find_saves(root: str | Path | None = None) -> list[Path]:
    """All .lsv savegames under the profile, newest first."""
    root = Path(root) if root else default_save_root()
    if not root.exists():
        return []
    saves = list(root.glob("*/*.lsv"))
    saves.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return saves


def latest_save(root: str | Path | None = None) -> Path | None:
    saves = find_saves(root)
    return saves[0] if saves else None


from .osiris_parser import parse_story, Story

class SaveGame:
    """Lazy reader over one .lsv savegame."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        if self.path.is_dir():  # accept the save folder too
            candidates = sorted(self.path.glob("*.lsv"))
            if not candidates:
                raise FileNotFoundError(f"no .lsv inside {self.path}")
            self.path = candidates[0]
        self.package = Package(self.path)

    @property
    def name(self) -> str:
        return self.path.stem

    @property
    def modified(self) -> float:
        return self.path.stat().st_mtime

    def namelist(self) -> list[str]:
        return self.package.namelist()

    @cached_property
    def info(self) -> dict:
        """SaveInfo.json — party summary, level, difficulty, game version."""
        return json.loads(self.package.read("SaveInfo.json").decode("utf-8"))

    @cached_property
    def meta(self) -> lsf.Resource:
        """meta.lsf — save name, timestamps, mod list."""
        return lsf.loads(self.package.read("meta.lsf"))

    @cached_property
    def globals(self) -> lsf.Resource:
        """Globals.lsf — characters, inventories, flags, world state."""
        return lsf.loads(self.package.read("Globals.lsf"))

    def level_cache(self, level: str) -> lsf.Resource:
        return lsf.loads(self.package.read(f"LevelCache/{level}.lsf"))

    @cached_property
    def story_save(self) -> Story:
        """StorySave.bin — parsed Osiris database (quest facts, nodes, goals)."""
        return parse_story(self.package.read("StorySave.bin"))

    def __repr__(self) -> str:
        return f"<SaveGame {self.name!r} files={len(self.package.files)}>"

