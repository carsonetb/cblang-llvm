from __future__ import annotations
from abc import ABC, abstractmethod

from llvmlite import ir

from parser import MemberFlag, FunctionFlag
from util import Singleton

class Value:
    def __init__(self, val_type: Type, value: ir.Value) -> None:
        self.val_type = val_type
        self.value = value

class Field:
    def __init__(self, field_type: Type, value: Value, flags: set[MemberFlag | FunctionFlag] = set()) -> None:
        self.field_type = field_type
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

class UserType(Type):
    def __init__(self, module: ir.Module, name: str) -> None:
        super().__init__(module)
        self._name = name
        self._llvm_type = self.module.context.get_identified_type(self.name)
        self.field_names: dict[str, Field] = {}
    
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
        self.llvm_type.set_body(*list(self.field_names.values()))
    
    def get_field(self, name: str) -> Field:
        return self.field_names[name]

class FunctionType(Type):
    def __init__(self, module: ir.Module, name: str, args: list[Type], returns: Type) -> None:
        super().__init__(module)
        self._name = name
        self._llvm_type = ir.FunctionType(returns.llvm_type, (arg.llvm_type for arg in args))
    
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
