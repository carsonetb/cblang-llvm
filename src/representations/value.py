from __future__ import annotations
from typing import TYPE_CHECKING
from llvmlite import ir
from llvm_types import I32, I8_POINTER
import llvmlite.binding as llvm

if TYPE_CHECKING:
    from representations.types.base_type import Type
    from representations.types.user_types import UserType, FunctionType
    from representations.types.array_type import ArrayType
    from representations.types.void_type import VoidType
    from runtime.rc_runtime import RCRuntime

class Value:
    """Base value for CBLang. Contains a Type and LLVM Value.
    This value is stack allocated, and copied when referenced (
    besides some specific cases)."""

    def __init__(self, builder: ir.IRBuilder, val_type: Type, initial_value: ir.Value, name: str, allocate=True) -> None:
        self.name = name
        self.val_type = val_type
        if allocate:
            with builder.goto_block(builder.function.blocks[0]):
                self.value_ptr = builder.alloca(val_type.llvm_type, name=f"{name}_ptr")
            builder.store(initial_value, self.value_ptr)
        else:
            self.value_ptr = initial_value
    
    def load_value(self, builder: ir.IRBuilder) -> ir.Value:
        return builder.load(self.value_ptr, "load_value")
    
    def store_value(self, builder: ir.IRBuilder, value: ir.Value) -> None:
        builder.store(value, self.value_ptr)
    
    def call(self, builder: ir.IRBuilder, name: str, args: list[Value], rc_runtime: RCRuntime, target_data: llvm.TargetData) -> Value | VoidValue:
        return self.val_type.call(builder, self, name, args, rc_runtime, target_data)
    
    def get(self, builder: ir.IRBuilder, name: str, rc_runtime: RCRuntime, target_data: llvm.TargetData) -> Value:
        # Lazy imports to avoid circular dependencies
        from representations.types.user_types import UserType
        from representations.types.array_type import ArrayType
        
        if isinstance(self.val_type, ArrayType):
            pass
            # TODO: Array type.
        if not isinstance(self.val_type, UserType):
            raise RuntimeError("Primitive values don't have members.")
        zero = I32(0)
        idx = ir.Constant(I32, self.val_type.field_indices[name])
        field_type = self.val_type.get_field(name)
        internal_val_mem = builder.gep(self.value_ptr, [zero, idx], name="internal_val_mem")
        internal_val_ptr: ir.CastInstr = builder.bitcast(internal_val_mem, field_type.val_type.llvm_type.as_pointer()) # type: ignore
        if field_type.val_type.needs_refcount:
            return RCValue(builder, field_type.val_type, internal_val_ptr, rc_runtime, target_data, f"{self.name}_get_{name}", allocate=False)
        else:
            internal_val = builder.load(internal_val_ptr, "internal_val")
            return Value(builder, field_type.val_type, internal_val, f"{self.name}_get_{name}")

    def retain(self, builder: ir.IRBuilder, rc_runtime: RCRuntime) -> None:
        pass

    def release(self, builder: ir.IRBuilder, rc_runtime: RCRuntime) -> None:
        pass


class RCValue(Value):
    def __init__(self, builder: ir.IRBuilder, val_type: Type, initial_value: ir.Value, rc_runtime: RCRuntime, target_data: llvm.TargetData, name: str, allocate=True) -> None:
        # Lazy import to avoid circular dependency
        from representations.types.array_type import ArrayType
        
        self.name = name
        self.val_type = val_type
        if allocate:
            value_memory = builder.call(rc_runtime.rc_alloc_func, [I32(ArrayType.get_type_size(target_data, val_type.llvm_type))], f"{name}_memory")
            self.value_ptr = builder.bitcast(value_memory, val_type.llvm_type.as_pointer(), f"{name}_memory")
            builder.store(initial_value, self.value_ptr)
        else:
            self.value_ptr = initial_value
    
    def retain(self, builder: ir.IRBuilder, rc_runtime: RCRuntime) -> None:
        raw_ptr = builder.bitcast(self.value_ptr, I8_POINTER, "raw_ptr")
        builder.call(rc_runtime.rc_retain_func, [raw_ptr])
    
    def release(self, builder: ir.IRBuilder, rc_runtime: RCRuntime) -> None:
        raw_ptr = builder.bitcast(self.value_ptr, I8_POINTER, "raw_ptr")
        destructor = self.val_type.get_destructor()
        destructor_ptr = destructor if destructor else rc_runtime.destructor_ptr_type(None)
        builder.call(rc_runtime.rc_release_func, [raw_ptr, destructor_ptr])


class FunctionValue(Value):
    """Type for functions passed as values, has a call_this with args."""

    def __init__(self, builder: ir.IRBuilder, val_type: FunctionType, value: ir.Function, is_this_member=False) -> None:
        self.val_type = val_type
        self.function_type = val_type
        self.function = value
        self.value_ptr = None
        self.is_this_member = False
    
    def call_this(self, builder: ir.IRBuilder, args: list[Value], rc_runtime: RCRuntime, target_data: llvm.TargetData) -> Value | VoidValue:
        return self.call_this_basic(builder, [arg.load_value(builder) for arg in args], rc_runtime, target_data)
    
    def call_this_basic(self, builder: ir.IRBuilder, args: list[ir.Value], rc_runtime: RCRuntime, target_data: llvm.TargetData) -> Value | VoidValue:
        # Lazy import to avoid circular dependency
        from representations.types.void_type import VoidType
        
        # TODO: Copy all primitive types.
        result = builder.call(self.function, args, self.function_type.name)

        if isinstance(self.function_type.returns, VoidType):
            return VoidValue()

        if self.function_type.returns.needs_refcount:
            return RCValue(builder, self.function_type.returns, result, rc_runtime, target_data, f"{self.function.name}_return", allocate=False)
        else:
            return Value(builder, self.function_type.returns, result, f"{self.function.name}_return")


class VoidValue:
    pass
