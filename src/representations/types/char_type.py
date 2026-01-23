from __future__ import annotations
from typing import TYPE_CHECKING
from representations.types.base_type import Type
from representations.field import Field
from representations.value import Value
from llvmlite import ir
import llvmlite.binding as llvm

if TYPE_CHECKING:
    from runtime.rc_runtime import RCRuntime
    from runtime.c_runtime import CRuntime


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
    
    def castable_from(self, cast_from: Type) -> bool:
        # Use name-based check to avoid circular imports with other primitive types
        return cast_from.name == "int"
    
    def generate_from(self, builder: ir.IRBuilder, cast_from: Value, rc_runtime: RCRuntime, c_runtime: CRuntime, target_data: llvm.TargetData) -> Value:
        assert self.castable_from(cast_from.val_type)
        val = cast_from.load_value(builder)
        as_char: ir.CastInstr = builder.trunc(val, self.llvm_type, "as_char") # type: ignore
        return Value(builder, self, as_char, f"{cast_from.val_type.name}_to_char")
    
    def call(self, builder: ir.IRBuilder, this: Value, name: str, args: list[Value], rc_runtime: RCRuntime, target_data: llvm.TargetData) -> Value:
        # Lazy import to avoid circular dependency
        from representations.types.bool_type import BoolType
        
        lhs = this.load_value(builder)
        rhs = args[0].load_value(builder)
        if name == "==" or name == "!=" or name == "<" or name == ">" or name == "<=" or name == ">=":
            out_type = BoolType(self.module)
            out_ir = builder.icmp_unsigned(name, lhs, rhs, "arith_res")
        elif name == "+":
            out_type = self
            out_ir = builder.add(lhs, rhs, "arith_res")
        elif name == "-":
            out_type = self
            out_ir = builder.sub(lhs, rhs, "arith_res")
        else:
            raise ValueError(f"Cannot call '{name}' on type '{self.name}'.")
        return Value(builder, out_type, out_ir) # type: ignore
