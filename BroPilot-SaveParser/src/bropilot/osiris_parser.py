from typing import List, Dict, Optional
from bropilot.osiris_common import (
    OsiReader, OsiVersion, SaveFileHeader, OsirisType, OsirisEnum,
    OsirisDivObject, Tuple, NodeReference, GoalReference, Value
)
from bropilot.osiris_nodes import (
    create_node, Node, Call, AdapterReference
)

class ParameterList:
    def __init__(self):
        self.types: List[int] = []

    def read(self, reader: OsiReader):
        count = reader.read_byte()
        for _ in range(count):
            if reader.short_type_ids is None:
                # Heuristic to detect short_type_ids for Patch 8+
                pos = reader.stream.tell()
                id_val = reader.read_uint32()
                reader.stream.seek(pos)
                reader.short_type_ids = (id_val > 0xff)

            if reader.short_type_ids:
                self.types.append(reader.read_uint16())
            else:
                self.types.append(reader.read_uint32())

class FunctionSignature:
    def __init__(self):
        self.name = ""
        self.out_param_mask: List[int] = []
        self.parameters = ParameterList()

    def read(self, reader: OsiReader):
        self.name = reader.read_string()
        out_param_bytes = reader.read_uint32()
        for _ in range(out_param_bytes):
            self.out_param_mask.append(reader.read_byte())
        self.parameters.read(reader)

class FunctionType:
    EVENT = 1
    QUERY = 2
    CALL = 3
    DATABASE = 4
    PROC = 5
    SYS_QUERY = 6
    SYS_CALL = 7
    USER_QUERY = 8

class Function:
    def __init__(self):
        self.line = 0
        self.condition_references = 0
        self.action_references = 0
        self.node_ref = NodeReference()
        self.type = 0
        self.meta1 = 0
        self.meta2 = 0
        self.meta3 = 0
        self.meta4 = 0
        self.signature = FunctionSignature()

    def read(self, reader: OsiReader):
        self.line = reader.read_uint32()
        self.condition_references = reader.read_uint32()
        self.action_references = reader.read_uint32()
        self.node_ref.read(reader)
        self.type = reader.read_byte()
        self.meta1 = reader.read_uint32()
        self.meta2 = reader.read_uint32()
        self.meta3 = reader.read_uint32()
        self.meta4 = reader.read_uint32()
        self.signature.read(reader)

class Fact:
    def __init__(self):
        self.columns: List[Value] = []

    def read(self, reader: OsiReader):
        count = reader.read_byte()
        for _ in range(count):
            val = Value()
            val.read(reader)
            self.columns.append(val)

class Database:
    def __init__(self):
        self.index = 0
        self.parameters = ParameterList()
        self.facts: List[Fact] = []
        self.owner_node: Optional[Node] = None

    def read(self, reader: OsiReader):
        self.index = reader.read_uint32()
        self.parameters.read(reader)
        
        count = reader.read_uint32()
        for _ in range(count):
            fact = Fact()
            fact.read(reader)
            self.facts.append(fact)

class Adapter:
    def __init__(self):
        self.index = 0
        self.constants = Tuple()
        self.logical_indices: List[int] = []
        self.logical_to_physical_map: Dict[int, int] = {}
        self.owner_node: Optional[Node] = None

    def read(self, reader: OsiReader):
        self.index = reader.read_uint32()
        self.constants.read(reader)
        
        count = reader.read_byte()
        for _ in range(count):
            self.logical_indices.append(int.from_bytes(reader.read_bytes(1), byteorder='little', signed=True))
            
        count = reader.read_byte()
        for _ in range(count):
            key = reader.read_byte()
            value = reader.read_byte()
            self.logical_to_physical_map[key] = value

class Goal:
    def __init__(self):
        self.index = 0
        self.name = ""
        self.sub_goal_combination = 0
        self.parent_goals: List[GoalReference] = []
        self.sub_goals: List[GoalReference] = []
        self.flags = 0
        self.init_calls: List[Call] = []
        self.exit_calls: List[Call] = []

    def read(self, reader: OsiReader):
        self.index = reader.read_uint32()
        self.name = reader.read_string()
        self.sub_goal_combination = reader.read_byte()

        count = reader.read_uint32()
        for _ in range(count):
            g = GoalReference()
            g.read(reader)
            self.parent_goals.append(g)

        count = reader.read_uint32()
        for _ in range(count):
            g = GoalReference()
            g.read(reader)
            self.sub_goals.append(g)

        self.flags = reader.read_byte()

        if reader.ver >= OsiVersion.VER_ADD_INIT_EXIT_CALLS:
            count = reader.read_uint32()
            for _ in range(count):
                c = Call()
                c.read(reader)
                self.init_calls.append(c)

            count = reader.read_uint32()
            for _ in range(count):
                c = Call()
                c.read(reader)
                self.exit_calls.append(c)


class Story:
    def __init__(self):
        self.minor_version = 0
        self.major_version = 0
        self.short_type_ids = False
        self.header = SaveFileHeader()
        
        self.types: Dict[int, OsirisType] = {}
        self.enums: Dict[int, OsirisEnum] = {}
        self.div_objects: List[OsirisDivObject] = []
        self.functions: List[Function] = []
        self.nodes: Dict[int, Node] = {}
        self.adapters: Dict[int, Adapter] = {}
        self.databases: Dict[int, Database] = {}
        self.goals: Dict[int, Goal] = {}
        self.global_actions: List[Call] = []
        self.external_string_table: List[str] = []

    @property
    def ver(self) -> int:
        return (self.major_version << 8) | self.minor_version

    def find_builtin_type_id(self, type_id: int) -> int:
        alias_id = type_id
        while type_id != 0 and self.types[alias_id].alias != 0:
            alias_id = self.types[alias_id].alias
        return alias_id


def parse_story(data: bytes) -> Story:
    story = Story()
    reader = OsiReader(data)
    reader.story = story

    header = SaveFileHeader()
    header.read(reader)
    reader.minor_version = header.minor_version
    reader.major_version = header.major_version
    story.minor_version = header.minor_version
    story.major_version = header.major_version

    if reader.ver > OsiVersion.VER_LAST_SUPPORTED:
        raise ValueError(f"Osiris version v{reader.major_version}.{reader.minor_version} unsupported")

    if reader.ver < OsiVersion.VER_REMOVE_EXTERNAL_STRING_TABLE:
        reader.short_type_ids = False
    elif reader.ver >= OsiVersion.VER_ENUMS:
        reader.short_type_ids = True

    if reader.ver >= OsiVersion.VER_SCRAMBLE:
        reader.scramble = 0xAD

    # Read Types
    if reader.ver >= OsiVersion.VER_ADD_TYPE_MAP:
        count = reader.read_uint32()
        for _ in range(count):
            t = OsirisType()
            t.read(reader)
            story.types[t.index] = t

        for t in story.types.values():
            if t.alias != 0:
                alias_id = t.alias
                while alias_id != 0 and alias_id in story.types and story.types[alias_id].alias != 0:
                    alias_id = story.types[alias_id].alias
                reader.type_aliases[t.index] = alias_id

    # External String Table
    if OsiVersion.VER_EXTERNAL_STRING_TABLE <= reader.ver < OsiVersion.VER_REMOVE_EXTERNAL_STRING_TABLE:
        count = reader.read_uint32()
        for _ in range(count):
            story.external_string_table.append(reader.read_string())

    story.types[0] = OsirisType.make_builtin(0, "UNKNOWN")
    story.types[1] = OsirisType.make_builtin(1, "INTEGER")

    if reader.ver >= OsiVersion.VER_ENHANCED_TYPES:
        story.types[2] = OsirisType.make_builtin(2, "INTEGER64")
        story.types[3] = OsirisType.make_builtin(3, "REAL")
        story.types[4] = OsirisType.make_builtin(4, "STRING")
        if 5 not in story.types:
            story.types[5] = OsirisType.make_builtin(5, "GUIDSTRING")
    else:
        story.types[2] = OsirisType.make_builtin(2, "FLOAT")
        story.types[3] = OsirisType.make_builtin(3, "STRING")
        if reader.ver < OsiVersion.VER_ADD_TYPE_MAP:
            for type_id in range(4, 18):
                story.types[type_id] = OsirisType.make_builtin(type_id, f"TYPE{type_id}")
                story.types[type_id].alias = 3
                reader.type_aliases[type_id] = 3

    # Enums
    if reader.ver >= OsiVersion.VER_ENUMS:
        count = reader.read_uint32()
        for _ in range(count):
            e = OsirisEnum()
            e.read(reader)
            story.enums[e.underlying_type] = e

    # DivObjects
    count = reader.read_uint32()
    for _ in range(count):
        div = OsirisDivObject()
        div.read(reader)
        story.div_objects.append(div)

    # Functions
    count = reader.read_uint32()
    for _ in range(count):
        f = Function()
        f.read(reader)
        story.functions.append(f)

    # Nodes
    count = reader.read_uint32()
    for _ in range(count):
        type_id = reader.read_byte()
        node_id = reader.read_uint32()
        node = create_node(type_id)
        node.index = node_id
        node.read(reader)
        story.nodes[node_id] = node

    # Adapters
    count = reader.read_uint32()
    for _ in range(count):
        a = Adapter()
        a.read(reader)
        story.adapters[a.index] = a

    # Databases
    count = reader.read_uint32()
    for _ in range(count):
        db = Database()
        db.read(reader)
        story.databases[db.index] = db

    # Goals
    count = reader.read_uint32()
    for _ in range(count):
        g = Goal()
        g.read(reader)
        story.goals[g.index] = g

    # Global Actions
    count = reader.read_uint32()
    for _ in range(count):
        c = Call()
        c.read(reader)
        story.global_actions.append(c)

    story.short_type_ids = reader.short_type_ids

    # PostLoad bindings
    for node in story.nodes.values():
        if node.database_ref.is_valid:
            db = node.database_ref.resolve()
            if db:
                db.owner_node = node
        # Full PostLoad implementation can be skipped if we only care about reading Databases.

    return story
