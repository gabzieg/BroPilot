"""Reader for Larian .pak / .lsv packages (LSPK format).

BG3 savegames (.lsv) are LSPK v18 archives holding SaveInfo.json, meta.lsf,
Globals.lsf, StorySave.bin and per-level caches.
"""

from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass
from pathlib import Path

import lz4.block
import lz4.frame
import zstandard

MAGIC = b"LSPK"

METHOD_NONE = 0
METHOD_ZLIB = 1
METHOD_LZ4 = 2
METHOD_ZSTD = 3

_ENTRY_SIZE = {15: 272, 16: 272, 18: 272}
_ENTRY_FMT = "<IHBBII"  # offset_lo, offset_hi, part, flags, size_on_disk, size


class PackageError(Exception):
    pass


def decompress(blob: bytes, flags: int, uncompressed_size: int) -> bytes:
    """Decompress a package/LSF chunk given its compression flag byte."""
    method = flags & 0x0F
    if method == METHOD_NONE:
        return blob
    if method == METHOD_ZLIB:
        return zlib.decompress(blob)
    if method == METHOD_LZ4:
        if blob.startswith(b'\x04\x22\x4d\x18'):
            return lz4.frame.decompress(blob)
        return lz4.block.decompress(blob, uncompressed_size=uncompressed_size)
    if method == METHOD_ZSTD:
        return zstandard.ZstdDecompressor().decompress(
            blob, max_output_size=uncompressed_size
        )
    raise PackageError(f"unknown compression method {method} (flags 0x{flags:02x})")


@dataclass(frozen=True)
class PackagedFile:
    name: str
    offset: int
    part: int
    flags: int
    size_on_disk: int
    size: int


class Package:
    """Random-access reader over an LSPK archive."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._data = self.path.read_bytes()
        self.version, self.files = self._read_header()

    # -- header ---------------------------------------------------------

    def _read_header(self) -> tuple[int, dict[str, PackagedFile]]:
        d = self._data
        if d[:4] != MAGIC:
            raise PackageError(f"{self.path.name}: not an LSPK package")
        version = struct.unpack_from("<I", d, 4)[0]
        if version not in _ENTRY_SIZE:
            raise PackageError(f"unsupported LSPK version {version}")
        list_offset, list_size = struct.unpack_from("<QI", d, 8)
        entries = self._read_file_list(list_offset, list_size, version)
        return version, entries

    def _read_file_list(
        self, offset: int, size: int, version: int
    ) -> dict[str, PackagedFile]:
        d = self._data
        num_files, compressed_size = struct.unpack_from("<II", d, offset)
        entry_size = _ENTRY_SIZE[version]
        blob = d[offset + 8 : offset + 8 + compressed_size]
        raw = self._decompress_file_list(blob, num_files * entry_size)

        files: dict[str, PackagedFile] = {}
        for i in range(num_files):
            base = i * entry_size
            name = raw[base : base + 256].split(b"\0", 1)[0].decode("utf-8")
            lo, hi, part, flags, on_disk, usize = struct.unpack_from(
                _ENTRY_FMT, raw, base + 256
            )
            files[name] = PackagedFile(
                name=name,
                offset=lo | (hi << 32),
                part=part,
                flags=flags,
                size_on_disk=on_disk,
                size=usize,
            )
        return files

    @staticmethod
    def _decompress_file_list(blob: bytes, uncompressed_size: int) -> bytes:
        if len(blob) == uncompressed_size:
            return blob
        # v16/v18 compress the entry table; the codec is not recorded anywhere,
        # so probe LZ4 (historic) then zstd (recent patches).
        try:
            return lz4.block.decompress(blob, uncompressed_size=uncompressed_size)
        except Exception:
            return zstandard.ZstdDecompressor().decompress(
                blob, max_output_size=uncompressed_size
            )

    # -- access ---------------------------------------------------------

    def __contains__(self, name: str) -> bool:
        return name in self.files

    def namelist(self) -> list[str]:
        return list(self.files)

    def read(self, name: str) -> bytes:
        try:
            entry = self.files[name]
        except KeyError:
            raise PackageError(
                f"{name!r} not in {self.path.name}; have {sorted(self.files)}"
            ) from None
        if entry.part != 0:
            raise PackageError(f"{name!r} lives in archive part {entry.part}")
        blob = self._data[entry.offset : entry.offset + entry.size_on_disk]
        out = decompress(blob, entry.flags, entry.size)
        if entry.size and len(out) != entry.size:
            raise PackageError(
                f"{name!r}: expected {entry.size} bytes, got {len(out)}"
            )
        return out

    def extract_all(self, dest: str | Path) -> list[Path]:
        dest = Path(dest)
        written = []
        for name in self.files:
            target = dest / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(self.read(name))
            written.append(target)
        return written
