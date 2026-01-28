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
    """
    Base class for all CBLang types. Each type is only generated
    once, even if used multiple times.
    """

    def __init__(self, module: ir.Module) -> None:
        self.module = module

    @property
    @abstractmethod
    def llvm_type(self) -> ir.Type: 
        """
        The raw LLVM IR type. For example, for ``bool`` this is 
        ``ir.IntType(1)`` and for ``int`` this is 
        ``ir.IntType(32)``
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str: 
        """
        The human-readable name of the type, including generics. 
        For example, for an ``array`` of ``int``, this would be 
        ``array<int>``.
        """
        pass
    
    @property
    @abstractmethod 
    def needs_refcount(self) -> bool:
        """
        Whether this is a reference counted type or not. Basic 
        primitives that are not refcounted include:

        - ``bool``
        - ``int`` 
        - ``char``
        - ``float``

        Types that are refcounted include:

        - Every ``UserType``
        - ``string``
        - ``array``
        """
        pass

    @abstractmethod
    def add_field(self, name: str, field: Field) -> None:
        """
        This function is typically only used on ``UserType``.
        Adds a field that will later be valid in ``get_field``
        and ``has_field``.
        """
        pass

    @abstractmethod
    def get_field(self, name: str) -> Field: 
        """
        Get a field from the type. This can be a function or a 
        variable. Make sure to check if the field actually exists
        using ``has_field`` if you aren't certain.
        """
        pass

    @abstractmethod 
    def has_field(self, name: str) -> bool: 
        """
        Check if the type has a field, for use in ``get_field``.
        """
        pass

    def castable_from(self, cast_from: Type) -> bool: 
        """
        Check if this type can be casted from another type. This 
        is used by the compiler for implicit casting support. By 
        default a type cannot be casted.
        """
        return False

    def generate_from(self, builder: ir.IRBuilder, cast_from: Value, rc_runtime: RCRuntime, c_runtime: CRuntime, target_data: llvm.TargetData) -> Value:
        """
        Generate from another type. This is inherently a copy, but
        values from the other type may not be copies. 
        """
        raise RuntimeError("This type cannot be casted!")

    def get_destructor(self) -> ir.Function | None:
        """
        Generally used for reference counted objects, destroys all
        the memory the type used.
        """
        return None
    
    def call(self, builder: ir.IRBuilder, this: Value, name: str, args: list[Value], rc_runtime: RCRuntime, target_data: llvm.TargetData) -> Value | VoidValue:
        """
        Calls a method that this type has.

        :param this: The value representing this type in code. This
            will end up being passed as the first argument to the function
            under the hood.
        """
        
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
    
    def call_static(self, builder: ir.IRBuilder, name: str, args: list[Value], rc_runtime: RCRuntime, target_data: llvm.TargetData) -> Value | VoidValue:
        """
        Same as ``call`` but without passing ``this`` to the 
        function.
        """
        
        function_field = self.get_field(name)

        assert isinstance(function_field.val_type, FunctionType)
        assert isinstance(function_field, ValueField)
        func_value = function_field.value
        assert isinstance(func_value, FunctionValue)
        return func_value.call_this(builder, args, rc_runtime, target_data)
