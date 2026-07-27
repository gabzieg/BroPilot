"""Reader for Larian LSF binary resource files (LSOF), versions 5-7.

Produces a plain-Python tree: Resource -> regions -> Node(attributes, children).
BG3 savegames use LSF v7 with LZ4-compressed sections and non-extended
(V2) node/attribute entries.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from typing import Any

from .lspk import decompress

MAGIC = b"LSOF"

_HEADER_FMT = "<4sIQ10IBBHI"  # magic, version, engine, 10 section sizes, flags..
_HEADER_SIZE = struct.calcsize(_HEADER_FMT)  # 64


class LSFError(Exception):
    pass


# -- attribute value types (LSLib NodeAttribute.DataType) -----------------

(
    DT_NONE, DT_BYTE, DT_SHORT, DT_USHORT, DT_INT, DT_UINT, DT_FLOAT, DT_DOUBLE,
    DT_IVEC2, DT_IVEC3, DT_IVEC4, DT_VEC2, DT_VEC3, DT_VEC4, DT_MAT2, DT_MAT3,
    DT_MAT3X4, DT_MAT4X3, DT_MAT4, DT_BOOL, DT_STRING, DT_PATH, DT_FIXEDSTRING,
    DT_LSSTRING, DT_ULONGLONG, DT_SCRATCHBUFFER, DT_LONG, DT_INT8,
    DT_TRANSLATEDSTRING, DT_WSTRING, DT_LSWSTRING, DT_UUID, DT_INT64,
    DT_TRANSLATEDFSSTRING,
) = range(34)

_SCALARS = {
    DT_BYTE: "<B", DT_SHORT: "<h", DT_USHORT: "<H", DT_INT: "<i", DT_UINT: "<I",
    DT_FLOAT: "<f", DT_DOUBLE: "<d", DT_ULONGLONG: "<Q", DT_LONG: "<q",
    DT_INT8: "<b", DT_INT64: "<q",
}
_VECTORS = {
    DT_IVEC2: "<2i", DT_IVEC3: "<3i", DT_IVEC4: "<4i",
    DT_VEC2: "<2f", DT_VEC3: "<3f", DT_VEC4: "<4f",
    DT_MAT2: "<4f", DT_MAT3: "<9f", DT_MAT3X4: "<12f",
    DT_MAT4X3: "<12f", DT_MAT4: "<16f",
}
_STRINGS = {DT_STRING, DT_PATH, DT_FIXEDSTRING, DT_LSSTRING, DT_WSTRING, DT_LSWSTRING}

TYPE_NAMES = {
    DT_NONE: "None", DT_BYTE: "uint8", DT_SHORT: "int16", DT_USHORT: "uint16",
    DT_INT: "int32", DT_UINT: "uint32", DT_FLOAT: "float", DT_DOUBLE: "double",
    DT_IVEC2: "ivec2", DT_IVEC3: "ivec3", DT_IVEC4: "ivec4", DT_VEC2: "fvec2",
    DT_VEC3: "fvec3", DT_VEC4: "fvec4", DT_MAT2: "mat2", DT_MAT3: "mat3",
    DT_MAT3X4: "mat3x4", DT_MAT4X3: "mat4x3", DT_MAT4: "mat4", DT_BOOL: "bool",
    DT_STRING: "string", DT_PATH: "path", DT_FIXEDSTRING: "FixedString",
    DT_LSSTRING: "LSString", DT_ULONGLONG: "uint64",
    DT_SCRATCHBUFFER: "ScratchBuffer", DT_LONG: "old_int64", DT_INT8: "int8",
    DT_TRANSLATEDSTRING: "TranslatedString", DT_WSTRING: "WString",
    DT_LSWSTRING: "LSWString", DT_UUID: "guid", DT_INT64: "int64",
    DT_TRANSLATEDFSSTRING: "TranslatedFSString",
}


@dataclass
class TranslatedString:
    handle: str
    value: str | None = None
    version: int = 0

    def __repr__(self) -> str:
        return f"<{self.handle}{'' if self.value is None else ' ' + self.value!r}>"


@dataclass
class Node:
    name: str
    attributes: dict[str, Any] = field(default_factory=dict)
    children: dict[str, list["Node"]] = field(default_factory=dict)

    def child(self, name: str) -> "Node | None":
        kids = self.children.get(name)
        return kids[0] if kids else None

    def each(self, name: str) -> list["Node"]:
        return self.children.get(name, [])

    def get(self, attr: str, default: Any = None) -> Any:
        return self.attributes.get(attr, default)

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        if self.attributes:
            out.update({k: _jsonable(v) for k, v in self.attributes.items()})
        for name, kids in self.children.items():
            out[name] = [k.to_dict() for k in kids]
        return out


@dataclass
class Resource:
    regions: dict[str, Node] = field(default_factory=dict)
    version: int = 0
    engine_version: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {name: node.to_dict() for name, node in self.regions.items()}


def _jsonable(v: Any) -> Any:
    if isinstance(v, TranslatedString):
        return {"handle": v.handle, "value": v.value}
    if isinstance(v, bytes):
        return v.hex()
    if isinstance(v, tuple):
        return list(v)
    return v


# -- reader ---------------------------------------------------------------


class LSFReader:
    def __init__(self, data: bytes):
        self.data = data
        self.names: list[list[str]] = []
        self.nodes: list[tuple[int, int, int]] = []  # name_key, parent, first_attr
        self.attributes: list[tuple[int, int, int, int, int]] = []
        self.values = b""
        self.version = 0
        self.engine_version = 0
        self.extended = False

    def read(self) -> Resource:
        self._read_header()
        self._read_names()
        self._read_nodes()
        self._read_attributes()
        return self._build_tree()

    # -- sections -------------------------------------------------------

    def _read_header(self) -> None:
        d = self.data
        if d[:4] != MAGIC:
            raise LSFError("not an LSF file (bad magic)")
        self.version = struct.unpack_from("<I", d, 4)[0]
        if not 5 <= self.version <= 7:
            raise LSFError(f"unsupported LSF version {self.version}")
        self.engine_version = struct.unpack_from("<Q", d, 8)[0]
        sizes = struct.unpack_from("<10I", d, 16)
        self.compression_flags = d[56]
        self.extended = bool(struct.unpack_from("<I", d, 60)[0])

        (
            strings_size, strings_disk,
            keys_size, keys_disk,
            nodes_size, nodes_disk,
            attrs_size, attrs_disk,
            values_size, values_disk,
        ) = sizes

        pos = _HEADER_SIZE
        self._strings_blob, pos = self._section(pos, strings_disk, strings_size)
        self._keys_blob, pos = self._section(pos, keys_disk, keys_size)
        self._nodes_blob, pos = self._section(pos, nodes_disk, nodes_size)
        self._attrs_blob, pos = self._section(pos, attrs_disk, attrs_size)
        self.values, pos = self._section(pos, values_disk, values_size)

    def _section(self, pos: int, on_disk: int, size: int) -> tuple[bytes, int]:
        """Return (decompressed section, next offset). Uncompressed when on_disk==0."""
        if size == 0 and on_disk == 0:
            return b"", pos
        if on_disk == 0:  # stored raw
            return self.data[pos : pos + size], pos + size
        blob = self.data[pos : pos + on_disk]
        return decompress(blob, self.compression_flags, size), pos + on_disk

    def _read_names(self) -> None:
        b = self._strings_blob
        if not b:
            return
        (buckets,) = struct.unpack_from("<I", b, 0)
        pos = 4
        for _ in range(buckets):
            (count,) = struct.unpack_from("<H", b, pos)
            pos += 2
            bucket = []
            for _ in range(count):
                (length,) = struct.unpack_from("<H", b, pos)
                pos += 2
                bucket.append(b[pos : pos + length].decode("utf-8", "replace"))
                pos += length
            self.names.append(bucket)

    def _read_nodes(self) -> None:
        b = self._nodes_blob
        step = 16 if self.extended else 12
        for pos in range(0, len(b) - step + 1, step):
            if self.extended:
                key, parent, _next_sibling, first_attr = struct.unpack_from(
                    "<Iiii", b, pos
                )
            else:
                key, first_attr, parent = struct.unpack_from("<Iii", b, pos)
            self.nodes.append((key, parent, first_attr))

    def _read_attributes(self) -> None:
        b = self._attrs_blob
        step = 16 if self.extended else 12
        offset = 0
        for pos in range(0, len(b) - step + 1, step):
            if self.extended:
                key, type_len, next_attr, data_offset = struct.unpack_from(
                    "<IIiI", b, pos
                )
            else:
                key, type_len, next_attr = struct.unpack_from("<IIi", b, pos)
                data_offset = offset
            type_id = type_len & 0x3F
            length = type_len >> 6
            offset += length
            self.attributes.append((key, type_id, length, data_offset, next_attr))

    # -- tree -----------------------------------------------------------

    def _name(self, key: int) -> str:
        bucket, index = key >> 16, key & 0xFFFF
        try:
            return self.names[bucket][index]
        except IndexError:
            return f"<unknown:{bucket}:{index}>"

    def _build_tree(self) -> Resource:
        # V2 stores the owning node on each attribute; V3 chains them per node.
        by_node: dict[int, list[int]] = {}
        if self.extended:
            for node_index, (_k, _p, first) in enumerate(self.nodes):
                chain, cursor = [], first
                while cursor != -1:
                    chain.append(cursor)
                    cursor = self.attributes[cursor][4]
                if chain:
                    by_node[node_index] = chain
        else:
            for attr_index, attr in enumerate(self.attributes):
                by_node.setdefault(attr[4], []).append(attr_index)

        built: list[Node] = []
        resource = Resource(version=self.version, engine_version=self.engine_version)
        for index, (key, parent, _first) in enumerate(self.nodes):
            node = Node(name=self._name(key))
            for attr_index in by_node.get(index, ()):
                akey, type_id, length, data_offset, _n = self.attributes[attr_index]
                node.attributes[self._name(akey)] = self._value(
                    type_id, data_offset, length
                )
            built.append(node)
            if parent == -1:
                resource.regions[node.name] = node
            else:
                built[parent].children.setdefault(node.name, []).append(node)
        return resource

    # -- values ---------------------------------------------------------

    def _value(self, type_id: int, offset: int, length: int) -> Any:
        raw = self.values[offset : offset + length]
        if type_id == DT_NONE:
            return None
        if type_id == DT_BOOL:
            return raw[0] != 0
        fmt = _SCALARS.get(type_id)
        if fmt:
            return struct.unpack_from(fmt, raw, 0)[0]
        fmt = _VECTORS.get(type_id)
        if fmt:
            return list(struct.unpack_from(fmt, raw, 0))
        if type_id in _STRINGS:
            return raw.split(b"\0", 1)[0].decode("utf-8", "replace")
        if type_id == DT_UUID:
            return _uuid(raw)
        if type_id in (DT_TRANSLATEDSTRING, DT_TRANSLATEDFSSTRING):
            return _translated(raw)
        return raw  # ScratchBuffer / unknown: keep bytes

    def type_name(self, type_id: int) -> str:
        return TYPE_NAMES.get(type_id, f"type{type_id}")


def _uuid(raw: bytes) -> str:
    if len(raw) != 16:
        return raw.hex()
    a, b, c, d = struct.unpack("<IHH8s", raw)
    return f"{a:08x}-{b:04x}-{c:04x}-{d[0]:02x}{d[1]:02x}-" + d[2:].hex()


def _translated(raw: bytes) -> TranslatedString | bytes:
    """BG3 layout: uint16 version, [int32 len + value if version==0], int32 len + handle."""
    try:
        pos = 0
        (version,) = struct.unpack_from("<H", raw, pos)
        pos += 2
        value = None
        if version == 0:
            (vlen,) = struct.unpack_from("<i", raw, pos)
            pos += 4
            value = raw[pos : pos + vlen].split(b"\0", 1)[0].decode("utf-8", "replace")
            pos += vlen
        (hlen,) = struct.unpack_from("<i", raw, pos)
        pos += 4
        handle = raw[pos : pos + hlen].split(b"\0", 1)[0].decode("utf-8", "replace")
        pos += hlen
        if pos > len(raw):
            return raw
        return TranslatedString(handle=handle, value=value, version=version)
    except struct.error:
        return raw


def loads(data: bytes) -> Resource:
    """Parse LSF bytes into a Resource tree."""
    return LSFReader(data).read()
