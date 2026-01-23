from __future__ import annotations
from typing import TYPE_CHECKING
from llvmlite import ir
from llvm_types import VOID, I8_POINTER, I32
import llvmlite.binding as llvm
from representations.types.base_type import Type

if TYPE_CHECKING:
    from runtime.rc_runtime import RCRuntime
    from runtime.c_runtime import CRuntime
    from representations.field import Field
    from representations.value import Value

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
    
    def finalize(self) -> None:
        field_list = [f.val_type.llvm_type for f in self.field_names.values()]
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
        self_ptr = builder.bitcast(raw_ptr, self.llvm_type.as_pointer(), "self_ptr")

        for field_name, fld in self.field_names.items():
            field_type = fld.val_type
            if not field_type.needs_refcount:
                continue
            idx = self.field_indices[field_name]
            field_ptr = builder.gep(self_ptr, [I32(0), I32(idx)], name="field_ptr")
            field_value = builder.load(field_ptr, "field_value")
            field_raw = builder.bitcast(field_value, I8_POINTER, "field_raw")
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
        self._llvm_type = ir.FunctionType(returns.llvm_type, ((arg.llvm_type.as_pointer() if arg.needs_refcount else arg.llvm_type) for arg in args)).as_pointer()
        self.returns = returns
        self.args = args
        self.function = function
    
    @property
    def llvm_type(self) -> ir.Type:
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
    
    def castable_from(self, cast_from: Type) -> bool: 
        return self.internal_type.castable_from(cast_from)
    
    def generate_from(self, builder: ir.IRBuilder, cast_from: Value, rc_runtime: RCRuntime, c_runtime: CRuntime, target_data: llvm.TargetData) -> Value:
        return self.internal_type.generate_from(builder, cast_from, rc_runtime, c_runtime, target_data)
