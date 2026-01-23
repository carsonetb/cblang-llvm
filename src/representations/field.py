from __future__ import annotations
from typing import TYPE_CHECKING, Container
from ast_classes import MemberFlag, FunctionFlag

if TYPE_CHECKING:
    from representations.types.base_type import Type
    from representations.value import Value

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