import struct
from io import BytesIO
from typing import List, Dict, Any, TypeVar, Generic

T = TypeVar('T')

class OsiVersion:
    VER_INITIAL = 0x0100
    VER_ADD_INIT_EXIT_CALLS = 0x0101
    VER_ADD_VERSION_STRING = 0x0102
    VER_ADD_DEBUG_FLAGS = 0x0103
    VER_SCRAMBLE = 0x0104
    VER_ADD_TYPE_MAP = 0x0105
    VER_ADD_QUERY = 0x0106
    VER_TYPE_ALIASES = 0x0109
    VER_ENHANCED_TYPES = 0x010a
    VER_EXTERNAL_STRING_TABLE = 0x010b
    VER_REMOVE_EXTERNAL_STRING_TABLE = 0x010c
    VER_ENUMS = 0x010d
    VER_VALUE_FLAGS = 0x010e
    VER_PATCH8_HOTFIX2 = 0x010f
    VER_LAST_SUPPORTED = VER_PATCH8_HOTFIX2

class OsiReader:
    def __init__(self, data: bytes):
        self.stream = BytesIO(data)
        self.scramble = 0x00
        self.major_version = 0
        self.minor_version = 0
        self.short_type_ids = False
        self.type_aliases: Dict[int, int] = {}
        self.story: Any = None  # Reference to the main Story object

    @property
    def ver(self) -> int:
        return (self.major_version << 8) | self.minor_version

    def read_byte(self) -> int:
        b = self.stream.read(1)
        if not b:
            raise EOFError("Unexpected end of file")
        return b[0]

    def read_bytes(self, size: int) -> bytes:
        b = self.stream.read(size)
        if len(b) != size:
            raise EOFError("Unexpected end of file")
        return b

    def read_uint32(self) -> int:
        return struct.unpack('<I', self.read_bytes(4))[0]

    def read_uint16(self) -> int:
        return struct.unpack('<H', self.read_bytes(2))[0]

    def read_uint64(self) -> int:
        return struct.unpack('<Q', self.read_bytes(8))[0]

    def read_bool(self) -> bool:
        b = self.read_byte()
        if b not in (0, 1):
            raise ValueError(f"Invalid boolean value: {b}")
        return b == 1

    def read_string(self) -> str:
        b = bytearray()
        while True:
            char = self.read_byte() ^ self.scramble
            if char != 0:
                b.append(char)
            else:
                break
        return b.decode('utf-8', errors='replace')

    def read_guid(self) -> bytes:
        return self.read_bytes(16)

class OsiReference(Generic[T]):
    NULL_REFERENCE = 0

    def __init__(self):
        self.index = self.NULL_REFERENCE
        self.story = None

    @property
    def is_null(self) -> bool:
        return self.index == self.NULL_REFERENCE

    @property
    def is_valid(self) -> bool:
        return self.index != self.NULL_REFERENCE

    def bind_story(self, story):
        if self.story is None:
            self.story = story
        else:
            raise ValueError("Reference already bound to a story!")

    def read(self, reader: OsiReader):
        self.index = reader.read_uint32()
        self.story = reader.story

    def resolve(self) -> T:
        raise NotImplementedError()

class NodeReference(OsiReference['Node']):
    def resolve(self):
        if self.is_null: return None
        return self.story.nodes.get(self.index)

class AdapterReference(OsiReference['Adapter']):
    def resolve(self):
        if self.is_null: return None
        return self.story.adapters.get(self.index)

class DatabaseReference(OsiReference['Database']):
    def resolve(self):
        if self.is_null: return None
        return self.story.databases.get(self.index)

class GoalReference(OsiReference['Goal']):
    def resolve(self):
        if self.is_null: return None
        return self.story.goals.get(self.index)


class SaveFileHeader:
    def __init__(self):
        self.version_str = ""
        self.major_version = 0
        self.minor_version = 0
        self.big_endian = False
        self.unused = 0
        self.debug_flags = 0

    @property
    def ver(self) -> int:
        return (self.major_version << 8) | self.minor_version

    def read(self, reader: OsiReader):
        reader.read_byte()
        self.version_str = reader.read_string()
        self.major_version = reader.read_byte()
        self.minor_version = reader.read_byte()
        self.big_endian = reader.read_bool()
        self.unused = reader.read_byte()

        ver = self.ver
        if ver >= OsiVersion.VER_ADD_VERSION_STRING:
            reader.read_bytes(0x80)

        if ver >= OsiVersion.VER_ADD_DEBUG_FLAGS:
            self.debug_flags = reader.read_uint32()
        else:
            self.debug_flags = 0

class OsirisType:
    def __init__(self):
        self.index = 0
        self.alias = 0
        self.name = ""
        self.is_builtin = False

    @staticmethod
    def make_builtin(index: int, name: str) -> 'OsirisType':
        t = OsirisType()
        t.index = index
        t.alias = 0
        t.name = name
        t.is_builtin = True
        return t

    def read(self, reader: OsiReader):
        self.name = reader.read_string()
        self.index = reader.read_byte()
        self.is_builtin = False

        if reader.ver >= OsiVersion.VER_TYPE_ALIASES:
            self.alias = reader.read_byte()
        else:
            self.alias = 3  # String alias for older versions

class OsirisEnumElement:
    def __init__(self):
        self.name = ""
        self.value = 0

    def read(self, reader: OsiReader):
        self.name = reader.read_string()
        self.value = reader.read_uint64()

class OsirisEnum:
    def __init__(self):
        self.underlying_type = 0
        self.elements: List[OsirisEnumElement] = []

    def read(self, reader: OsiReader):
        self.underlying_type = reader.read_uint16()
        count = reader.read_uint32()
        self.elements = []
        for _ in range(count):
            e = OsirisEnumElement()
            e.read(reader)
            self.elements.append(e)

class OsirisDivObject:
    def __init__(self):
        self.name = ""
        self.type = 0
        self.key1 = 0
        self.key2 = 0
        self.key3 = 0
        self.key4 = 0

    def read(self, reader: OsiReader):
        self.name = reader.read_string()
        self.type = reader.read_byte()
        self.key1 = reader.read_uint32()
        self.key2 = reader.read_uint32()
        self.key3 = reader.read_uint32()
        self.key4 = reader.read_uint32()

class ValueType:
    NONE = 0
    INTEGER = 1
    INTEGER64 = 2
    FLOAT = 3
    STRING = 4
    GUIDSTRING = 5

class ValueFlags:
    NONE_TYPE = 0
    SIMPLE_VALUE = 0x01
    TYPED_VALUE = 0x02
    VARIABLE = 0x03
    IS_VALID = 0x08
    OUT_PARAM = 0x10
    IS_A_TYPE = 0x20
    UNUSED = 0x40
    ADAPTED = 0x80

class Value:
    def __init__(self):
        self.type_id = 0
        self.int_value = 0
        self.int64_value = 0
        self.float_value = 0.0
        self.string_value = ""
        
        self.is_valid = False
        self.out_param = False
        self.is_a_type = False
        self.index = 0
        self.unused = False
        self.adapted = False

    def read(self, reader: OsiReader):
        if reader.ver >= OsiVersion.VER_VALUE_FLAGS:
            self.index = struct.unpack('<b', reader.read_bytes(1))[0]  # sbyte
            flags = reader.read_byte()
            
            if (flags & ValueFlags.IS_VALID) == ValueFlags.IS_VALID: self.is_valid = True
            if (flags & ValueFlags.OUT_PARAM) == ValueFlags.OUT_PARAM: self.out_param = True
            if (flags & ValueFlags.IS_A_TYPE) == ValueFlags.IS_A_TYPE: self.is_a_type = True
            if (flags & ValueFlags.UNUSED) == ValueFlags.UNUSED: self.unused = True
            if (flags & ValueFlags.ADAPTED) == ValueFlags.ADAPTED: self.adapted = True

            if not self.is_valid:
                return

        wtf = reader.read_byte()
        if wtf == ord('1'):
            self.type_id = reader.read_uint16() if reader.short_type_ids else reader.read_uint32()
            self.int_value = struct.unpack('<i', reader.read_bytes(4))[0]
        elif wtf == ord('0'):
            self.type_id = reader.read_uint16() if reader.short_type_ids else reader.read_uint32()
            written_type_id = self.type_id

            dos1alias = False
            if written_type_id in reader.type_aliases:
                written_type_id = reader.type_aliases[written_type_id]
                if reader.ver < OsiVersion.VER_ENHANCED_TYPES:
                    dos1alias = True

            if reader.ver < OsiVersion.VER_ENHANCED_TYPES:
                # We skip OS1ToOS2 conversion since we target BG3, but let's do a basic map
                if written_type_id == 2: written_type_id = ValueType.FLOAT
                elif written_type_id == 3: written_type_id = ValueType.STRING

            if written_type_id == ValueType.NONE:
                pass
            elif written_type_id == ValueType.INTEGER:
                self.int_value = struct.unpack('<i', reader.read_bytes(4))[0]
            elif written_type_id == ValueType.INTEGER64:
                self.int64_value = struct.unpack('<q', reader.read_bytes(8))[0]
            elif written_type_id == ValueType.FLOAT:
                self.float_value = struct.unpack('<f', reader.read_bytes(4))[0]
            elif written_type_id in (ValueType.STRING, ValueType.GUIDSTRING):
                if dos1alias:
                    self.string_value = reader.read_string()
                elif reader.read_byte() > 0:
                    self.string_value = reader.read_string()
            else:
                self.string_value = reader.read_string()
        elif wtf == ord('e'):
            self.type_id = reader.read_uint16()
            if not reader.story or self.type_id not in reader.story.enums:
                raise ValueError(f"Enum label serialized for a non-enum type: {self.type_id}")
            self.string_value = reader.read_string()
        else:
            raise ValueError(f"Unrecognized value type byte: {wtf}")

class TypedValue(Value):
    def read(self, reader: OsiReader):
        super().read(reader)
        if reader.ver < OsiVersion.VER_VALUE_FLAGS:
            self.is_valid = reader.read_bool()
            self.out_param = reader.read_bool()
            self.is_a_type = reader.read_bool()

class Variable(TypedValue):
    def __init__(self):
        super().__init__()
        self.variable_name = ""

    def read(self, reader: OsiReader):
        super().read(reader)
        if reader.ver < OsiVersion.VER_VALUE_FLAGS:
            self.index = struct.unpack('<b', reader.read_bytes(1))[0]
            self.unused = reader.read_bool()
            self.adapted = reader.read_bool()

class Tuple:
    def __init__(self):
        self.physical: List[Value] = []
        self.logical: Dict[int, Value] = {}

    def read(self, reader: OsiReader):
        self.physical.clear()
        self.logical.clear()

        count = reader.read_byte()
        for _ in range(count):
            if reader.ver >= OsiVersion.VER_VALUE_FLAGS:
                val = Value()
                val.read(reader)
                self.physical.append(val)
                self.logical[val.index] = val
            else:
                index = reader.read_byte()
                val = Value()
                val.read(reader)
                self.physical.append(val)
                self.logical[index] = val

