from __future__ import annotations
from typing import TYPE_CHECKING
from representations.types.base_type import Type
from representations.field import Field
from representations.value import Value, RCValue
from llvm_types import VOID, I8_POINTER, DOUBLE, I32, I1, I8
from llvmlite import ir
import llvmlite.binding as llvm

if TYPE_CHECKING:
    from runtime.rc_runtime import RCRuntime
    from runtime.c_runtime import CRuntime


class StringType(Type):
    """
    The StringType represents a dynamically allocated array of chars ([u]int8s),
    and *is* reference counted even though it's a primitive type.
    """

    def __init__(self, module: ir.Module, c_runtime: CRuntime) -> None:
        super().__init__(module)

        self.destructor_type = ir.FunctionType(VOID, [I8_POINTER])
        self.destructor_func = ir.Function(self.module, self.destructor_type, "string_destructor")
        block = self.destructor_func.append_basic_block("entry")
        builder = ir.IRBuilder(block)

        string_ptr = self.destructor_func.args[0]
        start_ptr_ptr = builder.bitcast(string_ptr, I8_POINTER.as_pointer(), "start_ptr_ptr")
        start_ptr = builder.load(start_ptr_ptr, "start_ptr")
        start_void = builder.bitcast(start_ptr, I8_POINTER, "start_void")
        builder.call(c_runtime.free, [start_void])
        builder.ret_void()
    
    @property
    def llvm_type(self) -> ir.Type:
        """
        The LLVM type is ``IntType(8).as_pointer()``, making it a C-style array, where 
        the ``char`` being pointed to is the first element in the ``string``.

        .. note:: The memory being pointed to is not reference counted, it is allocated
            using ``malloc``. The pointer itself contained in the ``string`` object 
            is, however, reference counted.
        """

        return I8_POINTER
    
    @property 
    def probable_type(self) -> ir.Type:
        """
        Pointer to the "struct" that contains the pointer to the ``malloc``'d array.
        """

        return I8_POINTER.as_pointer()
    
    @property
    def name(self) -> str:
        return "string"
    
    @property
    def needs_refcount(self) -> bool:
        """
        The ``string`` type does need reference counting.
        """

        return True
    
    def add_field(self, name: str, field: Field) -> None:
        raise RuntimeError("Cannot add a field to the StringType.")
    
    def get_field(self, name: str) -> Field:
        raise RuntimeError("Cannot get a field from the StringType.")
    
    def has_field(self, name: str) -> bool:
        return False
    
    def castable_from(self, cast_from: Type) -> bool:
        """
        Can be casted from ``int``, ``float``, or ``bool``.
        """

        # Use name-based check to avoid circular imports with other primitive types
        return cast_from.name in ("int", "float", "bool")
    
    def generate_from(self, builder: ir.IRBuilder, cast_from: Value, rc_runtime: RCRuntime, c_runtime: CRuntime, target_data: llvm.TargetData) -> Value:
        """
        A ``string`` can be generated from an ``int``, a ``float``, or a ``bool``. 
        The process for generating from ``int`` or ``float`` is more complex, 
        and involves using the C function sprintf to convert the float to the 
        string.
        """
        
        assert self.castable_from(cast_from.val_type)
        val = cast_from.load_value(builder)
        if cast_from.val_type.name in ("int", "float"):
            if cast_from.val_type.name == "float":
                val = builder.fpext(val, DOUBLE, "as_double")
            b_string = bytearray("%d\0".encode("utf-8")) if cast_from.val_type.name == "int" else bytearray("%f\0".encode("utf-8"))
            constant_type = ir.ArrayType(I8, len(b_string))
            fmt_constant = constant_type(b_string)
            constant_mem = builder.alloca(constant_type, name="fmt_const_mem")
            constant_ptr = builder.bitcast(constant_mem, I8_POINTER, "fmt_constant_ptr")
            builder.store(fmt_constant, constant_mem)
            out_mem = builder.call(c_runtime.malloc, [I32(48)], "out_mem") # Max size of a float with %d
            builder.call(c_runtime.sprintf_func, [out_mem, constant_ptr, val])
            return RCValue(builder, self, out_mem, rc_runtime, target_data, f"{cast_from.val_type.name}_to_string")
        elif cast_from.val_type.name == "bool":
            truthy_block = builder.append_basic_block("truthy")
            falsey_block = builder.append_basic_block("falsey")
            continued_block = builder.append_basic_block("continue")
            
            is_true = builder.icmp_unsigned("==", val, I1(1), "is_true")
            mem_type = ir.ArrayType(I8, 6)
            out_mem = builder.alloca(mem_type, name="out_mem")
            out_ptr: ir.CastInstr = builder.bitcast(out_mem, I8_POINTER, "out_ptr") # type: ignore
            builder.cbranch(is_true, truthy_block, falsey_block)

            builder.position_at_start(truthy_block)
            true_str_bytes = bytearray("true\0\0".encode("utf-8"))
            builder.store(mem_type(true_str_bytes), out_mem)
            builder.branch(continued_block)

            builder.position_at_start(falsey_block)
            false_str_bytes = bytearray("false\0".encode("utf-8"))
            builder.store(mem_type(false_str_bytes), out_mem)
            builder.branch(continued_block)

            builder.position_at_start(continued_block)
            return RCValue(builder, self, out_ptr, rc_runtime, target_data,  f"{cast_from.val_type.name}_to_string")
        else:
            assert False
    
    def get_destructor(self) -> ir.Function | None:
        """
        Gets the destructor that the memory inside the string.
        """

        return self.destructor_func
