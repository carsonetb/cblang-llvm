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

# Constants needed for casting
from llvm_types import I32, FLOAT

class BoolType(Type):
    """
    The ``bool`` type wraps ``IntType(1)``. It is not refcounted,
    and is constructed by the literal ``true`` or ``false``.
    """

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
    
    def castable_from(self, cast_from: Type) -> bool:
        """
        Castable from ``int``, ``float``, and ``char``.
        """
        return cast_from.name in ("int", "float", "char")
    
    def generate_from(self, builder: ir.IRBuilder, cast_from: Value, rc_runtime: RCRuntime, c_runtime: CRuntime, target_data: llvm.TargetData) -> Value:
        assert self.castable_from(cast_from.val_type)
        val = cast_from.load_value(builder)
        if cast_from.val_type.name in ("int", "char"):
            as_bool: ir.Instruction = builder.not_(builder.icmp_unsigned("==", val, I32(0), "is_zero"), "as_bool") # type: ignore
        elif cast_from.val_type.name == "float":
            as_bool: ir.Instruction = builder.not_(builder.fcmp_ordered("==", val, FLOAT(0), "is_zero"), "as_bool") # type: ignore
        else:
            assert False
        return Value(builder, self, as_bool, f"{cast_from.val_type.name}_to_bool") # type: ignore
    
    def call(self, builder: ir.IRBuilder, this: Value, name: str, args: list[Value], rc_runtime: RCRuntime, target_data: llvm.TargetData) -> Value:
        """
        Supports ``==``, ``!=``, and ``!`` operators.
        """
        
        if name == "==" or name == "!=":
            out_ir = builder.icmp_unsigned(name, this.load_value(builder), args[0].load_value(builder), "arith_res")
        elif name == "!":
            out_ir: ir.Instruction = builder.not_(this.load_value(builder), "arith_res") # type: ignore
        else:
            raise ValueError(f"Cannot call '{name}' on type '{self.name}'.")
        return Value(builder, self, out_ir, f"bool_comp_res")

