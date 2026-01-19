from __future__ import annotations
from abc import ABC, abstractmethod
from logging.handlers import DatagramHandler
from typing import Container, cast

from llvmlite import ir
import llvmlite.binding as llvm

from llvm_types import I32, I8, I8_POINTER, VOID
from parser import MemberFlag, FunctionFlag
from util import Singleton


class CRuntime:
    def __init__(self, module: ir.Module) -> None:
        self.module = module

            # void* malloc(size_t size)
        self.malloc_type = ir.FunctionType(I8_POINTER, [I32])
        self.malloc = ir.Function(self.module, self.malloc_type, name="malloc")

        # void* realloc(void* pointer, size_t size)
        self.realloc_type = ir.FunctionType(I8_POINTER, [I8_POINTER, I32])
        self.realloc = ir.Function(self.module, self.realloc_type, name="realloc")

        # void free(void* pointer)
        self.free_type = ir.FunctionType(VOID, [I8_POINTER])
        self.free = ir.Function(self.module, self.free_type, name="free")


class RCRuntime:
    HEADER_SIZE = 4 # bytes

    def __init__(self, module: ir.Module, runtime: CRuntime) -> None:

        # byte* rc_alloc(int32 size)
        self.rc_alloc_type = ir.FunctionType(I8_POINTER, [I32])
        self.rc_alloc_func = ir.Function(module, self.rc_alloc_type, "rc_alloc")
        block = self.rc_alloc_func.append_basic_block("entry")
        builder = ir.IRBuilder(block)

        size = self.rc_alloc_func.args[0]
        total_size = builder.add(size, I32(self.HEADER_SIZE))
        mem = builder.call(runtime.malloc, [total_size])
        count_ptr = builder.bitcast(mem, I32.as_pointer(), "count_ptr")
        builder.store(I32(1), count_ptr)
        data = builder.gep(mem, [I32(4)])
        builder.ret(data)

        # void rc_retain(byte* ptr)
        self.rc_retain_type = ir.FunctionType(VOID, [I8_POINTER])
        self.rc_retain_func = ir.Function(module, self.rc_retain_type, "rc_retain")
        block = self.rc_retain_func.append_basic_block("entry")
        builder = ir.IRBuilder(block)

        ptr = self.rc_retain_func.args[0]
        header = builder.gep(ptr, [I32(-self.HEADER_SIZE)], inbounds=False)
        count_ptr = builder.bitcast(header, I32.as_pointer(), "count_ptr")
        old_count = builder.load(count_ptr, "old_count")
        new_count = builder.add(old_count, I32(1), "new_count")
        builder.store(new_count, count_ptr)
        builder.ret_void()

        # void rc_release(byte* pointer)
        self.destructor_fn_type = ir.FunctionType(VOID, [I8_POINTER])
        self.destructor_ptr_type = self.destructor_fn_type.as_pointer()

        self.rc_release_type = ir.FunctionType(VOID, [I8_POINTER, self.destructor_ptr_type])
        self.rc_release_func = ir.Function(module, self.rc_release_type, name="rc_release")

        entry_block = self.rc_release_func.append_basic_block("entry")
        free_block = self.rc_release_func.append_basic_block("free_block")
        free_call_dtor_block = self.rc_release_func.append_basic_block("free_call_dtor")
        free_do_free_block = self.rc_release_func.append_basic_block("free_do_free")
        end_block = self.rc_release_func.append_basic_block("end")

        builder = ir.IRBuilder(entry_block)

        data_ptr = self.rc_release_func.args[0]
        destructor = self.rc_release_func.args[1]

        header_ptr = builder.gep(data_ptr, [I32(-self.HEADER_SIZE)], inbounds=False)
        count_ptr = builder.bitcast(header_ptr, I32.as_pointer())
        old_count = builder.load(count_ptr, name="old_count")
        new_count = builder.sub(old_count, I32(1), name="new_count")
        builder.store(new_count, count_ptr)
        is_zero = builder.icmp_unsigned("==", new_count, I32(0), name="is_zero")
        builder.cbranch(is_zero, free_block, end_block)

        # Free block just chooses between calling dtor or just freeing.
        builder.position_at_start(free_block)

        null_dtor = self.destructor_ptr_type(None) # basically just a nullptr
        has_dtor = builder.icmp_unsigned("!=", destructor, null_dtor)
        builder.cbranch(has_dtor, free_call_dtor_block, free_do_free_block)

        builder.position_at_start(free_call_dtor_block)

        builder.call(destructor, [data_ptr])
        builder.branch(free_do_free_block)

        builder.position_at_start(free_do_free_block)

        builder.call(runtime.free, [header_ptr])
        builder.branch(end_block)

        builder.position_at_start(end_block)
        builder.ret_void()


class Value:
    """Base value for CBLang. Contains a Type and LLVM Value."""

    def __init__(self, builder: ir.IRBuilder, val_type: Type, initial_value: ir.Value) -> None:
        self.val_type = val_type
        self.value_ptr = builder.alloca(self.val_type.llvm_type)
        builder.store(initial_value, self.value_ptr)
    
    def load_value(self, builder: ir.IRBuilder) -> ir.Value:
        return builder.load(self.value_ptr)
    
    def store_value(self, builder: ir.IRBuilder, value: ir.Value) -> None:
        builder.store(value, self.value_ptr)
    
    def call(self, builder: ir.IRBuilder, name: str, args: list[Value], rc_runtime: RCRuntime, target_data: llvm.TargetData) -> Value:
        return self.val_type.call(builder, self, name, args, rc_runtime, target_data)
    
    def get(self, builder: ir.IRBuilder, name: str) -> Value:
        if isinstance(self.val_type, ArrayType):
            pass
            # TODO: Array type.
        if not isinstance(self.val_type, UserType):
            raise RuntimeError("Primitive values don't have members.")
        zero = ir.Constant(I32, 0)
        idx = ir.Constant(I32, self.val_type.field_indices[name])
        field_type = self.val_type.get_field(name)
        internal_val_ptr = builder.gep(self.load_value(builder), [zero, idx])
        internal_val = builder.load(internal_val_ptr)
        return Value(builder, field_type.val_type, internal_val)

    def retain(self, builder: ir.IRBuilder, rc_runtime: RCRuntime) -> None:
        pass

    def release(self, builder: ir.IRBuilder, rc_runtime: RCRuntime) -> None:
        pass


class RCValue(Value):
    def __init__(self, builder: ir.IRBuilder, val_type: Type, initial_value: ir.Value, rc_runtime: RCRuntime, target_data: llvm.TargetData, allocate=True) -> None:
        self.val_type = val_type
        if allocate:
            value_memory = builder.call(rc_runtime.rc_alloc_func, [I32(ArrayType.get_type_size(target_data, val_type.llvm_type))])
            self.value_ptr = builder.bitcast(value_memory, val_type.llvm_type.as_pointer())
            builder.store(initial_value, self.value_ptr)
        else:
            self.value_ptr = initial_value
    
    def retain(self, builder: ir.IRBuilder, rc_runtime: RCRuntime) -> None:
        raw_ptr = builder.bitcast(self.value_ptr, I8_POINTER)
        builder.call(rc_runtime.rc_retain_func, [raw_ptr])
    
    def release(self, builder: ir.IRBuilder, rc_runtime: RCRuntime) -> None:
        raw_ptr = builder.bitcast(self.value_ptr, I8_POINTER)
        destructor = self.val_type.get_destructor()
        destructor_ptr = destructor if destructor else rc_runtime.destructor_ptr_type(None)
        builder.call(rc_runtime.rc_release_func, [raw_ptr, destructor_ptr])


class FunctionValue(Value):
    """Type for functions passed as values, has a call_this with args."""

    def __init__(self, builder: ir.IRBuilder, val_type: FunctionType, value: ir.Function) -> None:
        super().__init__(builder, val_type, value)
        self.function_type = val_type
    
    def call_this(self, builder: ir.IRBuilder, args: list[Value], rc_runtime: RCRuntime, target_data: llvm.TargetData) -> Value:
        # TODO: Copy all primitive types.
        result = builder.call(self.load_value(builder), [arg.load_value(builder) for arg in args], self.function_type.name)

        if self.function_type.returns.needs_refcount:
            return RCValue(builder, self.function_type.returns, result, rc_runtime, target_data, allocate=False)
        else:
            return Value(builder, self.function_type.returns, result)


class VoidValue:
    pass


class Field:
    """Joins a CBLang Type and with MemberFlags and FunctionFlags."""

    def __init__(self, val_type: Type, flags: Container[MemberFlag | FunctionFlag] = set()) -> None:
        self.val_type = val_type
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


class ValueField(Field):
    def __init__(self, val_type: Type, value: Value, flags: Container[MemberFlag | FunctionFlag] = set()) -> None:
        super().__init__(val_type, flags)
        self.value = value


class Type(ABC):
    """Base class for all CBLang types. Each type is only generated
    once, even if used multiple times."""

    def __init__(self, module: ir.Module) -> None:
        self.module = module

    @property
    @abstractmethod
    def llvm_type(self) -> ir.Type: pass

    @property
    @abstractmethod
    def name(self) -> str: pass
    
    @property
    @abstractmethod 
    def needs_refcount(self) -> bool: pass

    @abstractmethod
    def add_field(self, name: str, field: Field) -> None: pass

    @abstractmethod
    def get_field(self, name: str) -> Field: pass

    @abstractmethod 
    def has_field(self, name: str) -> bool: pass

    def get_destructor(self) -> ir.Function | None:
        return None
    
    def call(self, builder: ir.IRBuilder, this: Value, name: str, args: list[Value], rc_runtime: RCRuntime, target_data: llvm.TargetData) -> Value:
        field = self.get_field(name)
        if not isinstance(field.val_type, FunctionType):
            raise ValueError()
        if not isinstance(field, ValueField):
            raise ValueError("Method has no associated function value")
        func_value = field.value
        if not isinstance(func_value, FunctionValue):
            raise ValueError()
        return func_value.call_this(builder, [this] + args, rc_runtime, target_data)


class UserType(Type):
    def __init__(self, module: ir.Module, name: str, rc_runtime: RCRuntime) -> None:
        super().__init__(module)
        self._name = name
        self._llvm_type = self.module.context.get_identified_type(self.name)
        self.rc_runtime = rc_runtime
        self.field_names: dict[str, Field] = {}
        self.field_indices: dict[str, int] = {}

        self.destructor_type = ir.FunctionType(VOID, [I8_POINTER])
        self.destructor_func = ir.Function(self.module, self.destructor_type, f"{name}_destructor")
        self.destructor_generated = False
    
    @property
    def llvm_type(self) -> ir.IdentifiedStructType:
        return self._llvm_type

    @property
    def name(self) -> str:
        return self._name
    
    @property
    def needs_refcount(self) -> bool:
        return True
    
    def add_field(self, name: str, field: Field) -> None:
        if name in self.field_names:
            raise ValueError(f"Field '{name}' already exists.")
        
        self.field_names[name] = field

        field_list = [f.val_type.llvm_type for f in self.field_names.values()]
        self.field_indices[name] = len(field_list) - 1
        self.llvm_type.set_body(*field_list)
    
    def get_field(self, name: str) -> Field:
        return self.field_names[name]
    
    def has_field(self, name: str) -> bool:
        return name in self.field_names
    
    def get_destructor(self) -> ir.Function | None:
        if not self.destructor_generated:
            self.generate_destructor()
            self.destructor_generated = True
        return self.destructor_func

    def generate_destructor(self) -> None:
        block = self.destructor_func.append_basic_block("entry")
        builder = ir.IRBuilder(block)

        raw_ptr = self.destructor_func.args[0]
        self_ptr = builder.bitcast(raw_ptr, self.llvm_type.as_pointer())

        for field_name, field in self.field_names.items():
            field_type = field.val_type
            if not field_type.needs_refcount:
                continue
            idx = self.field_indices[field_name]
            field_ptr = builder.gep(self_ptr, [I32(0), I32(idx)])
            field_value = builder.load(field_ptr)
            field_raw = builder.bitcast(field_value, I8_POINTER)
            field_destructor = field_type.get_destructor()
            if field_destructor:
                destructor_ptr = field_destructor
            else:
                destructor_fn_ty = ir.FunctionType(VOID, [I8_POINTER])
                destructor_ptr = ir.Constant(destructor_fn_ty.as_pointer(), None)
            builder.call(self.rc_runtime.rc_release_func, [field_raw, destructor_ptr])
        
        builder.ret_void()


class FunctionType(Type):
    """Class for CBLang functions. Extends the base Type class."""

    def __init__(self, module: ir.Module, name: str, args: list[Type], returns: Type, function: ir.Function) -> None:
        super().__init__(module)
        self._name = name
        self._llvm_type = ir.FunctionType(returns.llvm_type, (arg.llvm_type for arg in args))
        self.returns = returns
        self.args = args
        self.function = function
    
    @property
    def llvm_type(self) -> ir.FunctionType:
        return self._llvm_type

    @property
    def name(self) -> str:
        return self._name
    
    @property
    def needs_refcount(self) -> bool:
        return False
    
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
    
    @property
    def needs_refcount(self) -> bool:
        return self.internal_type.needs_refcount
    
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
    
    @property
    def needs_refcount(self) -> bool:
        return False
    
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
    
    @property
    def needs_refcount(self) -> bool:
        return False
    
    def add_field(self, name: str, field: Field) -> None:
        raise RuntimeError("Cannot add a field to the BoolType.")
    
    def get_field(self, name: str) -> Field:
        raise RuntimeError("Cannot get a field from the BoolType.")
    
    def has_field(self, name: str) -> bool:
        return False
    
    def call(self, builder: ir.IRBuilder, this: Value, name: str, args: list[Value], rc_runtime: RCRuntime, target_data: llvm.TargetData) -> Value:
        if name == "==" or name == "!=":
            out_ir = builder.icmp_unsigned(name, this.load_value(builder), args[0].load_value(builder))
        elif name == "!":
            out_ir: ir.Instruction = builder.not_(this.load_value(builder)) # type: ignore
        else:
            raise ValueError(f"Cannot call '{name}' on type '{self.name}'.")
        return Value(builder, self, out_ir)


class IntType(Type):
    def __init__(self, module: ir.Module) -> None:
        super().__init__(module)
    
    @property
    def llvm_type(self) -> ir.IntType:
        return ir.IntType(32)
    
    @property
    def name(self) -> str:
        return "int"
    
    @property
    def needs_refcount(self) -> bool:
        return False
    
    def add_field(self, name: str, field: Field) -> None:
        raise RuntimeError("Cannot add a field to the IntType.")
    
    def get_field(self, name: str) -> Field:
        raise RuntimeError("Cannot get a field from the IntType.")
    
    def has_field(self, name: str) -> bool:
        return False
    
    def call(self, builder: ir.IRBuilder, this: Value, name: str, args: list[Value], rc_runtime: RCRuntime, target_data: llvm.TargetData) -> Value:
        lhs = this.load_value(builder)
        rhs = args[0].load_value(builder) if len(args) > 0 else None
        out_type = None
        if name == "==" or name == "!=" or name == "<" or name == ">" or name == "<=" or name == ">=":
            out_type = BoolType(self.module)
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
        return Value(builder, out_type if out_type else self, out_ir) # type: ignore


class FloatType(Type):
    def __init__(self, module: ir.Module) -> None:
        super().__init__(module)
    
    @property
    def llvm_type(self) -> ir.FloatType:
        return ir.FloatType()
    
    @property
    def name(self) -> str:
        return "float"
    
    @property
    def needs_refcount(self) -> bool:
        return False
    
    def add_field(self, name: str, field: Field) -> None:
        raise RuntimeError("Cannot add a field to the FloatType.")
    
    def get_field(self, name: str) -> Field:
        raise RuntimeError("Cannot get a field from the FloatType.")
    
    def has_field(self, name: str) -> bool:
        return False
    
    def call(self, builder: ir.IRBuilder, this: Value, name: str, args: list[Value], rc_runtime: RCRuntime, target_data: llvm.TargetData) -> Value:
        lhs = this.load_value(builder)
        rhs = args[0].load_value(builder)
        if name == "==" or name == "!=" or name == "<" or name == ">" or name == "<=" or name == ">=":
            out_type = BoolType(self.module)
            out_ir = builder.fcmp_ordered(name, lhs, rhs)
        elif name == "+":
            out_type = self
            out_ir = builder.fadd(lhs, rhs)
        elif name == "-":
            out_type = self
            out_ir = builder.fsub(lhs, rhs)
        elif name == "*":
            out_type = self
            out_ir = builder.fmul(lhs, rhs)
        elif name == "/":
            out_type = self
            out_ir = builder.fdiv(lhs, rhs)
        elif name == "-":
            out_type = self
            out_ir = builder.neg(lhs)
        else:
            raise ValueError(f"Cannot call '{name}' on type '{self.name}'.")
        return Value(builder, out_type, out_ir) # type: ignore


class CharType(Type):
    def __init__(self, module: ir.Module) -> None:
        super().__init__(module)
    
    @property
    def llvm_type(self) -> ir.IntType:
        return ir.IntType(8)
    
    @property
    def name(self) -> str:
        return "char"
    
    @property
    def needs_refcount(self) -> bool:
        return False
    
    def add_field(self, name: str, field: Field) -> None:
        raise RuntimeError("Cannot add a field to the CharType.")
    
    def get_field(self, name: str) -> Field:
        raise RuntimeError("Cannot get a field from the CharType.")
    
    def has_field(self, name: str) -> bool:
        return False
    
    def call(self, builder: ir.IRBuilder, this: Value, name: str, args: list[Value], rc_runtime: RCRuntime, target_data: llvm.TargetData) -> Value:
        lhs = this.load_value(builder)
        rhs = args[0].load_value(builder)
        if name == "==" or name == "!=" or name == "<" or name == ">" or name == "<=" or name == ">=":
            out_type = BoolType(self.module)
            out_ir = builder.icmp_unsigned(name, lhs, rhs)
        elif name == "+":
            out_type = self
            out_ir = builder.add(lhs, rhs)
        elif name == "-":
            out_type = self
            out_ir = builder.sub(lhs, rhs)
        else:
            raise ValueError(f"Cannot call '{name}' on type '{self.name}'.")
        return Value(builder, out_type, out_ir) # type: ignore


class StringType(Type):
    def __init__(self, module: ir.Module, length: int) -> None:
        super().__init__(module)
        self.length = length
    
    @property
    def llvm_type(self) -> ir.ArrayType:
        return ir.ArrayType(I8, I32(self.length))
    
    @property
    def name(self) -> str:
        return "string"
    
    @property
    def needs_refcount(self) -> bool:
        return False
    
    def add_field(self, name: str, field: Field) -> None:
        raise RuntimeError("Cannot add a field to the StringType.")
    
    def get_field(self, name: str) -> Field:
        raise RuntimeError("Cannot get a field from the StringType.")
    
    def has_field(self, name: str) -> bool:
        return False


class ArrayType(Type):
    def __init__(self, builder: ir.IRBuilder, module: ir.Module, target: llvm.TargetData, contains: Type, runtime: CRuntime, rc_runtime: RCRuntime) -> None:
        super().__init__(module)
        self.builder = builder
        self.contains = contains
        self.contains_ptr_type = contains.llvm_type.as_pointer()

        # { Contains*, int32 size, int32 capacity }
        self.array_struct_type = ir.LiteralStructType([self.contains_ptr_type, I32, I32])
        self.array_pointer_type = self.array_struct_type.as_pointer()

        # array<T> init_array(int32 initial_capacity)
        self.init_type = ir.FunctionType(self.contains_ptr_type, [I32])
        self.init_func = ir.Function(self.module, self.init_type, name="init_array")
        block = self.init_func.append_basic_block(name="entry")
        builder = ir.IRBuilder(block)

        initial_count = self.init_func.args[0]

        struct_size = I32(16)
        storage_memory = builder.call(rc_runtime.rc_alloc_func, [struct_size])
        array_inst: ir.CastInstr = builder.bitcast(storage_memory, self.array_pointer_type) # type: ignore

        element_size = self.get_type_size(target, contains.llvm_type)
        initial_size = builder.mul(initial_count, I32(element_size))
        initial_memory = builder.call(runtime.malloc, [initial_size])
        data_ptr = builder.bitcast(initial_memory, self.contains_ptr_type)

        data_addr = self.get_struct_val(builder, array_inst, 0)
        builder.store(data_ptr, data_addr)

        size_addr = self.get_struct_val(builder, array_inst, 1)
        builder.store(I32(0), size_addr)

        capacity_addr = self.get_struct_val(builder, array_inst, 2)
        builder.store(initial_size, capacity_addr)

        builder.ret(array_inst)

        # void append_array(Array* array, T value)
        self.append_type = ir.FunctionType(ir.VoidType(), [self.array_pointer_type, contains.llvm_type])
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
        new_mem_size = builder.mul(new_capacity, I32(element_size))

        old_data_ptr = builder.load(data_ptr_addr)
        old_data_void = builder.bitcast(old_data_ptr, I8_POINTER)

        new_memory = builder.call(runtime.realloc, [old_data_void, new_mem_size])
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

        # void free(Array* to_free)
        self.free_array_type = ir.FunctionType(VOID, [self.array_pointer_type])
        self.free_array_func = ir.Function(self.module, self.free_array_type, name="free_array")
        block = self.free_array_func.append_basic_block("entry")
        builder = ir.IRBuilder(block)

        array_pointer = self.free_array_func.args[0] # TODO: This needs to be bitcasted to type?

        data_ptr_addr = self.get_struct_val(builder, array_pointer, 0)
        data_ptr = builder.load(data_ptr_addr)
        data_void = builder.bitcast(data_ptr, I8_POINTER)

        # Free all the elements stored in the array.
        builder.call(runtime.free, [data_void])

        # Free the whole struct.
        arr_void = builder.bitcast(array_pointer, I8_POINTER)
        builder.call(runtime.free, [arr_void])

        builder.ret_void()

        self.destructor_type = ir.FunctionType(VOID, [I8_POINTER])
        self.destructor_func = ir.Function(module, self.destructor_type, "array_destructor")
        block = self.destructor_func.append_basic_block("entry")
        loop_check_block = self.destructor_func.append_basic_block("loop_check")
        loop_body_block = self.destructor_func.append_basic_block("loop_body")
        after_loop_block = self.destructor_func.append_basic_block("after_loop")
        builder = ir.IRBuilder(block)

        array_pointer = self.destructor_func.args[0]
        this: ir.CastInstr = builder.bitcast(array_pointer, self.array_pointer_type) # type: ignore
        
        size_ptr = self.get_struct_val(builder, this, 1)
        size = builder.load(size_ptr, "size")
        data_ptr_ptr = self.get_struct_val(builder, this, 0)
        data_ptr = builder.load(data_ptr_ptr)

        i = builder.alloca(I32)
        builder.store(I32(0), i)
        builder.branch(loop_check_block)

        builder.position_at_start(loop_check_block)

        current_i = builder.load(i, "current_i")
        done = builder.icmp_unsigned("==", current_i, size)
        builder.cbranch(done, after_loop_block, loop_body_block)

        builder.position_at_start(loop_body_block)

        if contains.needs_refcount:
            elem_ptr = builder.gep(data_ptr, [current_i])
            elem_raw = builder.bitcast(elem_ptr, I8_POINTER)
            possible_destructor = contains.get_destructor()
            if possible_destructor:
                destructor_ptr = possible_destructor
            else:
                destructor_fn_ty = ir.FunctionType(VOID, [I8_POINTER])
                destructor_ptr = ir.Constant(destructor_fn_ty.as_pointer(), None)
            builder.call(rc_runtime.rc_release_func, [elem_raw, destructor_ptr]) # Not if this is how we should pass the destructor

        next_i = builder.add(current_i, I32(1))
        builder.store(next_i, i)
        builder.branch(loop_check_block)

        builder.position_at_start(after_loop_block)

        data_void = builder.bitcast(data_ptr, I8_POINTER)
        builder.call(runtime.free, [data_void])

        builder.ret_void()

    
    @property
    def llvm_type(self) -> ir.Type:
        return self.array_struct_type
    
    @property
    def name(self) -> str:
        return f"array<{self.contains.name}>"
    
    @property
    def needs_refcount(self) -> bool:
        return True
    
    def add_field(self, name: str, field: Field) -> None:
        raise RuntimeError("Cannot add a field to the ArrayType.")
    
    def get_field(self, name: str) -> Field:
        if name == "init":
            hl_init_type = FunctionType(self.module, "init", [], self, self.init_func)
            return Field(hl_init_type, {MemberFlag.STATIC})
        elif name == "append":
            hl_append_type = FunctionType(self.module, "append", [self, self.contains], VoidType(self.module), self.append)
            return Field(hl_append_type)
        else:
            raise ValueError(f"Cannot call '{name}' on type '{self.name}'.")
    
    def has_field(self, name: str) -> bool:
        return name == "init" or name == "append"
    
    def get_destructor(self) -> ir.Function | None:
        return self.destructor_func
    
    def call(self, builder: ir.IRBuilder, this: Value, name: str, args: list[Value], rc_runtime: RCRuntime, target_data: llvm.TargetData) -> Value:
        if name == "init":
            raise ValueError("Call 'init' function via get_field.")
        elif name == "append":
            if args[0].val_type.name != self.contains.name:
                raise ValueError("Invalid type for append call.")
            return Value(builder, VoidType(self.module), builder.call(self.append, [this.load_value(builder), args[0].load_value(builder)]))
        else:
            raise ValueError(f"Cannot call '{name}' on type '{self.name}'")
    
    def generate(self, builder: ir.IRBuilder) -> Value:
        return Value(builder, self, builder.call(self.init_func, [I32(1)]))
    
    @staticmethod
    def get_struct_val(builder: ir.IRBuilder, struct: ir.Value, index: int):
        return builder.gep(struct, [ir.Constant(I32, 0), ir.Constant(I32, index)])
    
    @staticmethod
    def get_type_size(target_data: llvm.TargetData, ir_type: ir.Type) -> int:
        ir_str = str(ir_type)

        type_sizes = {
            "i1": 1,
            "i8": 1,
            "i16": 2,
            "i32": 4,
            "i64": 8,
            "float": 4,
            "double": 8,
        }

        if ir_str in type_sizes:
            return type_sizes[ir_str]

        if ir_str.endswith("*"):
            return 8

        if isinstance(ir_type, ir.LiteralStructType):
            return sum(
                ArrayType.get_type_size(target_data, elem) for elem in ir_type.elements
            )

        if isinstance(ir_type, ir.IdentifiedStructType):
            return sum(
                ArrayType.get_type_size(target_data, elem) for elem in ir_type.elements # type: ignore
            )

        if isinstance(ir_type, ir.ArrayType):
            return ir_type.count * ArrayType.get_type_size(target_data, ir_type.element)

        raise ValueError(f"Unknown type size for '{ir_str}'")