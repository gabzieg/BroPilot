from typing import List, Dict, Any, Optional
from bropilot.osiris_common import (
    OsiReader, OsiVersion, NodeReference, AdapterReference,
    DatabaseReference, GoalReference, TypedValue, Variable, Value
)

class EntryPoint:
    NONE = 0
    LEFT = 1
    RIGHT = 2

class NodeEntryItem:
    def __init__(self):
        self.node_ref = NodeReference()
        self.entry_point = EntryPoint.NONE
        self.goal_ref = GoalReference()

    def read(self, reader: OsiReader):
        self.node_ref.read(reader)
        self.entry_point = reader.read_uint32()
        self.goal_ref.read(reader)

class NodeType:
    DATABASE = 1
    PROC = 2
    DIV_QUERY = 3
    AND = 4
    NOT_AND = 5
    REL_OP = 6
    RULE = 7
    INTERNAL_QUERY = 8
    USER_QUERY = 9

class Node:
    def __init__(self):
        self.index = 0
        self.database_ref = DatabaseReference()
        self.name = ""
        self.num_params = 0

    def node_type(self) -> int:
        raise NotImplementedError()

    def read(self, reader: OsiReader):
        self.database_ref.read(reader)
        self.name = reader.read_string()
        if len(self.name) > 0:
            self.num_params = reader.read_byte()

class TreeNode(Node):
    def __init__(self):
        super().__init__()
        self.next_node = NodeEntryItem()

    def read(self, reader: OsiReader):
        super().read(reader)
        self.next_node.read(reader)

class DataNode(Node):
    def __init__(self):
        super().__init__()
        self.referenced_by: List[NodeEntryItem] = []

    def read(self, reader: OsiReader):
        super().read(reader)
        count = reader.read_uint32()
        self.referenced_by = []
        for _ in range(count):
            item = NodeEntryItem()
            item.read(reader)
            self.referenced_by.append(item)

class DatabaseNode(DataNode):
    def node_type(self): return NodeType.DATABASE

class ProcNode(DataNode):
    def node_type(self): return NodeType.PROC

class QueryNode(Node):
    pass

class DivQueryNode(QueryNode):
    def node_type(self): return NodeType.DIV_QUERY

class InternalQueryNode(QueryNode):
    def node_type(self): return NodeType.INTERNAL_QUERY

class UserQueryNode(QueryNode):
    def node_type(self): return NodeType.USER_QUERY

class JoinNode(TreeNode):
    def __init__(self):
        super().__init__()
        self.left_parent_ref = NodeReference()
        self.right_parent_ref = NodeReference()
        self.left_adapter_ref = AdapterReference()
        self.right_adapter_ref = AdapterReference()
        
        self.left_database_node_ref = NodeReference()
        self.left_database_indirection = 0
        self.left_database_join = NodeEntryItem()
        
        self.right_database_node_ref = NodeReference()
        self.right_database_indirection = 0
        self.right_database_join = NodeEntryItem()

    def read(self, reader: OsiReader):
        super().read(reader)
        self.left_parent_ref.read(reader)
        self.right_parent_ref.read(reader)
        self.left_adapter_ref.read(reader)
        self.right_adapter_ref.read(reader)

        self.left_database_node_ref.read(reader)
        self.left_database_join.read(reader)
        self.left_database_indirection = reader.read_byte()

        self.right_database_node_ref.read(reader)
        self.right_database_join.read(reader)
        self.right_database_indirection = reader.read_byte()

class AndNode(JoinNode):
    def node_type(self): return NodeType.AND

class NotAndNode(JoinNode):
    def node_type(self): return NodeType.NOT_AND

class RelNode(TreeNode):
    def __init__(self):
        super().__init__()
        self.parent_ref = NodeReference()
        self.adapter_ref = AdapterReference()
        self.rel_database_node_ref = NodeReference()
        self.rel_join = NodeEntryItem()
        self.rel_database_indirection = 0

    def read(self, reader: OsiReader):
        super().read(reader)
        self.parent_ref.read(reader)
        self.adapter_ref.read(reader)
        self.rel_database_node_ref.read(reader)
        self.rel_join.read(reader)
        self.rel_database_indirection = reader.read_byte()

class RelOpType:
    LESS = 0
    LESS_OR_EQUAL = 1
    GREATER = 2
    GREATER_OR_EQUAL = 3
    EQUAL = 4
    NOT_EQUAL = 5

class RelOpNode(RelNode):
    def __init__(self):
        super().__init__()
        self.left_value_index = 0
        self.right_value_index = 0
        self.left_value = Value()
        self.right_value = Value()
        self.rel_op = RelOpType.EQUAL

    def node_type(self): return NodeType.REL_OP

    def read(self, reader: OsiReader):
        super().read(reader)
        self.left_value_index = int.from_bytes(reader.read_bytes(1), byteorder='little', signed=True)
        self.right_value_index = int.from_bytes(reader.read_bytes(1), byteorder='little', signed=True)
        self.left_value.read(reader)
        self.right_value.read(reader)
        self.rel_op = reader.read_uint32()

class Call:
    def __init__(self):
        self.name = ""
        self.parameters: List[TypedValue] = []
        self.negate = False
        self.goal_id_or_debug_hook = 0

    def read(self, reader: OsiReader):
        self.name = reader.read_string()
        if len(self.name) > 0:
            has_params = reader.read_byte()
            if has_params > 0:
                num_params = reader.read_byte()
                for _ in range(num_params):
                    if reader.ver >= OsiVersion.VER_VALUE_FLAGS:
                        param = Variable()
                    else:
                        type_flag = reader.read_byte()
                        param = Variable() if type_flag == 1 else TypedValue()
                    param.read(reader)
                    self.parameters.append(param)
            self.negate = reader.read_bool()
        self.goal_id_or_debug_hook = int.from_bytes(reader.read_bytes(4), byteorder='little', signed=True)

class RuleNode(RelNode):
    def __init__(self):
        super().__init__()
        self.calls: List[Call] = []
        self.variables: List[Variable] = []
        self.line = 0
        self.is_query = False

    def node_type(self): return NodeType.RULE

    def read(self, reader: OsiReader):
        super().read(reader)
        
        call_count = reader.read_uint32()
        for _ in range(call_count):
            c = Call()
            c.read(reader)
            self.calls.append(c)

        var_count = reader.read_byte()
        for _ in range(var_count):
            if reader.ver < OsiVersion.VER_VALUE_FLAGS:
                t = reader.read_byte()
                if t != 1:
                    raise ValueError("Illegal value type in rule variable list")
            var = Variable()
            var.read(reader)
            self.variables.append(var)

        self.line = reader.read_uint32()
        if reader.ver >= OsiVersion.VER_ADD_QUERY:
            self.is_query = reader.read_bool()
        else:
            self.is_query = False

def create_node(type_id: int) -> Node:
    mapping = {
        NodeType.DATABASE: DatabaseNode,
        NodeType.PROC: ProcNode,
        NodeType.DIV_QUERY: DivQueryNode,
        NodeType.AND: AndNode,
        NodeType.NOT_AND: NotAndNode,
        NodeType.REL_OP: RelOpNode,
        NodeType.RULE: RuleNode,
        NodeType.INTERNAL_QUERY: InternalQueryNode,
        NodeType.USER_QUERY: UserQueryNode,
    }
    cls = mapping.get(type_id)
    if not cls:
        raise NotImplementedError(f"No deserializer found for node type: {type_id}")
    return cls()
