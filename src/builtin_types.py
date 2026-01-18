from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Container, cast

from llvmlite import ir
import llvmlite.binding as llvm

from llvm_types import I32, I8_POINTER, VOID
from parser import MemberFlag, FunctionFlag
from scanner import Token
from util import Singleton

class Value:
    I32 = ir.IntType(32)

    def __init__(self, val_type: Type, value: ir.Value) -> None:
        self.val_type = val_type
        self.value = value
    
    def call(self, builder: ir.IRBuilder, name: str, args: list[Value]) -> Value:
        return self.val_type.call(builder, self, name, args)
    
    def get(self, builder: ir.IRBuilder, name: str) -> Value:
        if not isinstance(self.val_type, UserType):
            raise RuntimeError("Primitive values don't have members.")
        zero = ir.Constant(self.I32, 0)
        idx = ir.Constant(self.I32, self.val_type.field_indices[name])
        field_type = self.val_type.get_field(name)
        return Value(field_type.value.val_type, builder.gep(self.value, [zero, idx]))

class FunctionValue(Value):
    def __init__(self, val_type: FunctionType, value: ir.Function) -> None:
        super().__init__(val_type, value)
        self.function_type = val_type
    
    def call_this(self, builder: ir.IRBuilder, args: list[Value]) -> Value:
        return Value(self.function_type.returns, builder.call(self.value, [arg.value for arg in args], self.function_type.name))

class Field:
    def __init__(self, value: Value, flags: Container[MemberFlag | FunctionFlag] = set()) -> None:
        self.value = value
        self.flags = flags
    
    @property
    def is_private(self) -> bool:
        return MemberFlag.PRIVATE in self.flags
    
    @property
    def is_mutable(self) -> bool:
        return MemberFlag.CONST in self.flags
    
    @property 
    def is_global(self) -> bool:
        return MemberFlag.STATIC in self.flags

class Type(ABC):
    def __init__(self, module: ir.Module) -> None:
        self.module = module

    @property
    @abstractmethod
    def llvm_type(self) -> ir.Type: pass

    @property
    @abstractmethod
    def name(self) -> str: pass

    @abstractmethod
    def add_field(self, name: str, field: Field) -> None: pass

    @abstractmethod
    def get_field(self, name: str) -> Field: pass

    @abstractmethod 
    def has_field(self, name: str) -> bool: pass
    
    def call(self, builder: ir.IRBuilder, this: Value, name: str, args: list[Value]) -> Value:
        field = self.get_field(name).value
        if not isinstance(field, FunctionValue):
            raise ValueError()
        return field.call_this(builder, [this] + args)

class UserType(Type):
    def __init__(self, module: ir.Module, name: str) -> None:
        super().__init__(module)
        self._name = name
        self._llvm_type = self.module.context.get_identified_type(self.name)
        self.field_names: dict[str, Field] = {}
        self.field_indices: dict[str, int] = {}
    
    @property
    def llvm_type(self) -> ir.IdentifiedStructType:
        return self._llvm_type

    @property
    def name(self) -> str:
        return self._name
    
    def add_field(self, name: str, field: Field) -> None:
        if name in self.field_names:
            raise ValueError(f"Field '{name}' already exists.")
        
        self.field_names[name] = field

        field_list = list(self.field_names.values())
        self.field_indices[name] = len(field_list) - 1
        self.llvm_type.set_body(*field_list)
    
    def get_field(self, name: str) -> Field:
        return self.field_names[name]
    
    def has_field(self, name: str) -> bool:
        return name in self.field_names

class FunctionType(Type):
    def __init__(self, module: ir.Module, name: str, args: list[Type], returns: Type) -> None:
        super().__init__(module)
        self._name = name
        self._llvm_type = ir.FunctionType(returns.llvm_type, (arg.llvm_type for arg in args))
        self.returns = returns
        self.args = args
    
    @property
    def llvm_type(self) -> ir.FunctionType:
        return self._llvm_type

    @property
    def name(self) -> str:
        return self._name
    
    def add_field(self, name: str, field: Field) -> None:
        raise RuntimeError("Cannot add a field to a FunctionType.")
    
    def get_field(self, name: str) -> Field:
        raise RuntimeError("(currently) Cannot get a field from the FunctionType.")
    
    def has_field(self, name: str) -> bool:
        return False

class InternalType(Type):
    """For types inside other classes."""

    def __init__(self, module: ir.Module, internal_type: UserType) -> None:
        super().__init__(module)
        self.internal_type = internal_type
    
    @property
    def llvm_type(self) -> ir.IdentifiedStructType:
        return self.internal_type.llvm_type

    @property
    def name(self) -> str:
        return self.internal_type.name
    
    def add_field(self, name: str, field: Field) -> None:
        raise RuntimeError("Cannot add a field to the InternalType.")
    
    def get_field(self, name: str) -> Field:
        return self.internal_type.get_field(name)
    
    def has_field(self, name: str) -> bool:
        return self.internal_type.has_field(name)

# TODO: Could be a singleton later?
class VoidType(Type):
    def __init__(self, module: ir.Module) -> None:
        super().__init__(module)
    
    @property
    def llvm_type(self) -> ir.VoidType:
        return ir.VoidType()
    
    @property
    def name(self) -> str:
        return "void"
    
    def add_field(self, name: str, field: Field) -> None:
        raise RuntimeError("Cannot add a field to the VoidType.")
    
    def get_field(self, name: str) -> Field:
        raise RuntimeError("Cannot get a field from the VoidType.")
    
    def has_field(self, name: str) -> bool:
        return False

class BoolType(Type):
    def __init__(self, module: ir.Module) -> None:
        super().__init__(module)
    
    @property
    def llvm_type(self) -> ir.IntType:
        return ir.IntType(1)
    
    @property
    def name(self) -> str:
        return "bool"
    
    def add_field(self, name: str, field: Field) -> None:
        raise RuntimeError("Cannot add a field to the BoolType.")
    
    def get_field(self, name: str) -> Field:
        raise RuntimeError("Cannot get a field from the BoolType.")
    
    def has_field(self, name: str) -> bool:
        return False
    
    def call(self, builder: ir.IRBuilder, this: Value, name: str, args: list[Value]) -> Value:
        if name == "==" or name == "!=":
            out_ir = builder.icmp_unsigned(name, this.value, args[0].value)
        elif name == "!":
            out_ir = builder.not_(this.value)
        else:
            raise ValueError(f"Cannot call '{name}' on type '{self.name}'.")
        return Value(BoolType(self.module), out_ir) # type: ignore

class IntType(Type):
    def __init__(self, module: ir.Module) -> None:
        super().__init__(module)
    
    @property
    def llvm_type(self) -> ir.IntType:
        return ir.IntType(32)
    
    @property
    def name(self) -> str:
        return "int"
    
    def add_field(self, name: str, field: Field) -> None:
        raise RuntimeError("Cannot add a field to the IntType.")
    
    def get_field(self, name: str) -> Field:
        raise RuntimeError("Cannot get a field from the IntType.")
    
    def has_field(self, name: str) -> bool:
        return False
    
    def call(self, builder: ir.IRBuilder, this: Value, name: str, args: list[Value]) -> Value:
        lhs = this.value
        rhs = args[0].value if len(args) > 0 else None
        if name == "==" or name == "!=" or name == "<" or name == ">" or name == "<=" or name == ">=":
            out_ir = builder.icmp_unsigned(name, lhs, rhs)
        elif name == "+":
            out_ir = builder.add(lhs, rhs)
        elif name == "-":
            out_ir = builder.sub(lhs, rhs)
        elif name == "*":
            out_ir = builder.mul(lhs, rhs)
        elif name == "/":
            out_ir = builder.sdiv(lhs, rhs)
        elif name == "-":
            out_ir = builder.neg(lhs)
        else:
            raise ValueError(f"Cannot call '{name}' on type '{self.name}'.")
        return Value(BoolType(self.module), out_ir) # type: ignore

class FloatType(Type):
    def __init__(self, module: ir.Module) -> None:
        super().__init__(module)
    
    @property
    def llvm_type(self) -> ir.FloatType:
        return ir.FloatType()
    
    @property
    def name(self) -> str:
        return "float"
    
    def add_field(self, name: str, field: Field) -> None:
        raise RuntimeError("Cannot add a field to the FloatType.")
    
    def get_field(self, name: str) -> Field:
        raise RuntimeError("Cannot get a field from the FloatType.")
    
    def has_field(self, name: str) -> bool:
        return False
    
    def call(self, builder: ir.IRBuilder, this: Value, name: str, args: list[Value]) -> Value:
        lhs = this.value
        rhs = args[0].value
        if name == "==" or name == "!=" or name == "<" or name == ">" or name == "<=" or name == ">=":
            out_ir = builder.fcmp_ordered(name, lhs, rhs)
        elif name == "+":
            out_ir = builder.fadd(lhs, rhs)
        elif name == "-":
            out_ir = builder.fsub(lhs, rhs)
        elif name == "*":
            out_ir = builder.fmul(lhs, rhs)
        elif name == "/":
            out_ir = builder.fdiv(lhs, rhs)
        elif name == "-":
            out_ir = builder.neg(lhs)
        else:
            raise ValueError(f"Cannot call '{name}' on type '{self.name}'.")
        return Value(BoolType(self.module), out_ir) # type: ignore

class CharType(Type):
    def __init__(self, module: ir.Module) -> None:
        super().__init__(module)
    
    @property
    def llvm_type(self) -> ir.IntType:
        return ir.IntType(8)
    
    @property
    def name(self) -> str:
        return "char"
    
    def add_field(self, name: str, field: Field) -> None:
        raise RuntimeError("Cannot add a field to the CharType.")
    
    def get_field(self, name: str) -> Field:
        raise RuntimeError("Cannot get a field from the CharType.")
    
    def has_field(self, name: str) -> bool:
        return False
    
    def call(self, builder: ir.IRBuilder, this: Value, name: str, args: list[Value]) -> Value:
        lhs = this.value
        rhs = args[0].value
        if name == "==" or name == "!=" or name == "<" or name == ">" or name == "<=" or name == ">=":
            out_ir = builder.icmp_unsigned(name, lhs, rhs)
        elif name == "+":
            out_ir = builder.add(lhs, rhs)
        elif name == "-":
            out_ir = builder.sub(lhs, rhs)
        else:
            raise ValueError(f"Cannot call '{name}' on type '{self.name}'.")
        return Value(BoolType(self.module), out_ir) # type: ignore

class StringType(Type):
    def __init__(self, module: ir.Module) -> None:
        super().__init__(module)
    
    @property
    def llvm_type(self) -> ir.LiteralStructType:
        return ir.LiteralStructType([
            ir.IntType(32), # length of string
            ir.IntType(8).as_pointer() # the string of characters (C-style)
        ])
    
    @property
    def name(self) -> str:
        return "string"
    
    def add_field(self, name: str, field: Field) -> None:
        raise RuntimeError("Cannot add a field to the StringType.")
    
    def get_field(self, name: str) -> Field:
        raise RuntimeError("Cannot get a field from the StringType.")
    
    def has_field(self, name: str) -> bool:
        return False

class ArrayType(Type):
    def __init__(self, module: ir.Module, target: llvm.TargetData, contains: Type) -> None:
        super().__init__(module)
        self.contains = contains
        self.contains_ptr_type = contains.llvm_type.as_pointer()

        # { Contains*, int32 size, int32 capacity }
        self.array_struct_type = ir.LiteralStructType([self.contains_ptr_type, I32, I32])
        self.array_pointer_type = self.array_struct_type.as_pointer()

        # void* malloc(size_t size)
        self.malloc_type = ir.FunctionType(I8_POINTER, [I32])
        self.malloc = ir.Function(self.module, self.malloc_type, name="malloc")

        # void* realloc(void* pointer, size_t size)
        self.realloc_type = ir.FunctionType(I8_POINTER, [I8_POINTER, I32])
        self.realloc = ir.Function(self.module, self.realloc_type, name="realloc")

        # void free(void* pointer)
        self.free_type = ir.FunctionType(VOID, [I8_POINTER])
        self.free = ir.Function(self.module, self.realloc_type, name="free")

        # array<T> init_array(int32 initial_capacity)
        self.init_type = ir.FunctionType(self.contains_ptr_type, [I32])
        self.init_func = ir.Function(self.module, self.init_type, name="init_array")
        block = self.init_func.append_basic_block(name="entry")
        builder = ir.IRBuilder(block)

        initial_count = self.init_func.args[0]

        struct_size = I32(24)
        storage_memory = builder.call(self.malloc, [struct_size])
        array_inst: ir.CastInstr = builder.bitcast(storage_memory, self.array_pointer_type) # type: ignore

        element_size = target.get_abi_size(contains.llvm_type)
        initial_size = builder.mul(initial_count, element_size)
        initial_memory = builder.call(self.malloc, [initial_size])
        data_ptr = builder.bitcast(initial_memory, contains)

        data_ptr_addr = self.get_struct_val(builder, array_inst, 0)
        builder.store(data_ptr, data_ptr_addr)

        size_addr = self.get_struct_val(builder, array_inst, 1)
        builder.store(I32(0), size_addr)

        capacity_addr = self.get_struct_val(builder, array_inst, 2)
        builder.store(initial_size, capacity_addr)

        builder.ret(array_inst)

        # void append_array(Array* array, T value)
        self.append_type = ir.FunctionType(ir.VoidType(), [self.array_struct_type, contains.llvm_type])
        self.append = ir.Function(self.module, self.append_type, "append_array")
        entry = self.append.append_basic_block("entry")
        grow_block = self.append.append_basic_block("grow")
        store_block = self.append.append_basic_block("store")
        builder = ir.IRBuilder(entry)

        array_pointer = self.append.args[0]
        to_append = self.append.args[1]

        data_ptr_addr = self.get_struct_val(builder, array_pointer, 0)
        size_addr = self.get_struct_val(builder, array_pointer, 1)
        cap_addr = self.get_struct_val(builder, array_pointer,2)
        current_size = builder.load(size_addr)
        current_capacity = builder.load(cap_addr)

        grow_necessary = builder.icmp_unsigned(">=", current_size, current_capacity)
        builder.cbranch(grow_necessary, grow_block, store_block)

        builder.position_at_start(grow_block)

        new_capacity = builder.mul(current_capacity, I32(2))
        new_mem_size = builder.mul(new_capacity, element_size)

        old_data_ptr = builder.load(data_ptr_addr)
        old_data_void = builder.bitcast(old_data_ptr, I8_POINTER)

        new_memory = builder.call(self.realloc, [old_data_void, new_mem_size])
        new_data_ptr = builder.bitcast(new_memory, self.contains_ptr_type)

        builder.store(new_data_ptr, data_ptr_addr)
        builder.store(new_capacity, cap_addr)
        builder.branch(store_block)

        builder.position_at_start(store_block)

        data_ptr = builder.load(data_ptr_addr)
        insert_addr = builder.gep(data_ptr, [current_size])
        builder.store(to_append, insert_addr)

        new_size = builder.add(current_size, I32(1))
        builder.store(new_size, size_addr)

        builder.ret_void()

        # void free
        self.free_arr_type = ir.FunctionType()
    
    @staticmethod
    def get_struct_val(builder: ir.IRBuilder, struct: ir.Value, index: int):
        return builder.gep(struct, [ir.Constant(I32, 0), ir.Constant(I32, index)])

