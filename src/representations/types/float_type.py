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
    
    def castable_from(self, cast_from: Type) -> bool:
        # Use name-based check to avoid circular imports with other primitive types
        return cast_from.name in ("int", "bool")
    
    def generate_from(self, builder: ir.IRBuilder, cast_from: Value, rc_runtime: RCRuntime, c_runtime: CRuntime, target_data: llvm.TargetData) -> Value:
        assert self.castable_from(cast_from.val_type)
        val = cast_from.load_value(builder)
        as_float: ir.CastInstr = builder.sitofp(val, self.llvm_type, "as_float") # type: ignore
        return Value(builder, self, as_float, f"{cast_from.val_type.name}_to_float")
    
    def call(self, builder: ir.IRBuilder, this: Value, name: str, args: list[Value], rc_runtime: RCRuntime, target_data: llvm.TargetData) -> Value:
        # Lazy import to avoid circular dependency
        from representations.types.bool_type import BoolType
        
        lhs = this.load_value(builder)
        rhs = args[0].load_value(builder)
        if name == "==" or name == "!=" or name == "<" or name == ">" or name == "<=" or name == ">=":
            out_type = BoolType(self.module)
            out_ir = builder.fcmp_ordered(name, lhs, rhs, "arith_res")
        elif name == "+":
            out_type = self
            out_ir = builder.fadd(lhs, rhs, "arith_res")
        elif name == "-":
            out_type = self
            out_ir = builder.fsub(lhs, rhs, "arith_res")
        elif name == "*":
            out_type = self
            out_ir = builder.fmul(lhs, rhs, "arith_res")
        elif name == "/":
            out_type = self
            out_ir = builder.fdiv(lhs, rhs, "arith_res")
        elif name == "-":
            out_type = self
            out_ir = builder.neg(lhs, "arith_res")
        else:
            raise ValueError(f"Cannot call '{name}' on type '{self.name}'.")
        return Value(builder, out_type, out_ir, "float_comp_res") # type: ignore
