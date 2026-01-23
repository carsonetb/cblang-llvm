from __future__ import annotations
from typing import TYPE_CHECKING
from representations.types.base_type import Type
from llvmlite import ir

if TYPE_CHECKING:
    from representations.field import Field

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




