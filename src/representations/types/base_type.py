from __future__ import annotations
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING
from llvmlite import ir 
import llvmlite.binding as llvm

if TYPE_CHECKING:
    from runtime.rc_runtime import RCRuntime
    from runtime.c_runtime import CRuntime
    from representations.field import Field, ValueField
    from representations.value import Value, FunctionValue, VoidValue
    from representations.types.user_types import FunctionType

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

    def castable_from(self, cast_from: Type) -> bool: 
        return False

    def generate_from(self, builder: ir.IRBuilder, cast_from: Value, rc_runtime: RCRuntime, c_runtime: CRuntime, target_data: llvm.TargetData) -> Value:
        raise RuntimeError("This type cannot be casted!")

    def get_destructor(self) -> ir.Function | None:
        return None
    
    def call(self, builder: ir.IRBuilder, this: Value, name: str, args: list[Value], rc_runtime: RCRuntime, target_data: llvm.TargetData) -> Value | VoidValue:
        # Lazy imports to avoid circular dependencies
        from representations.field import ValueField
        from representations.value import FunctionValue
        from representations.types.user_types import FunctionType
        
        function_field = self.get_field(name)
        if not isinstance(function_field.val_type, FunctionType):
            raise ValueError()
        if not isinstance(function_field, ValueField):
            raise ValueError("Method has no associated function value")
        func_value = function_field.value
        if not isinstance(func_value, FunctionValue):
            raise ValueError()
        return func_value.call_this(builder, [this] + args, rc_runtime, target_data)
