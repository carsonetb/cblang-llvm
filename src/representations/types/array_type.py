from __future__ import annotations
from typing import TYPE_CHECKING
from representations.types.base_type import Type
from representations.types.user_types import FunctionType
from representations.types.void_type import VoidType
from representations.field import Field
from representations.value import Value
from ast_classes import MemberFlag
from llvm_types import I32, I8_POINTER, VOID
from llvmlite import ir
import llvmlite.binding as llvm

if TYPE_CHECKING:
    from runtime.rc_runtime import RCRuntime
    from runtime.c_runtime import CRuntime


class ArrayType(Type):
    """
    The array type is a dynamic array similar to the string type.
    It is refcounted, and can store any type inside of it.
    """

    def __init__(self, builder: ir.IRBuilder, module: ir.Module, target: llvm.TargetData, contains: Type, runtime: CRuntime, rc_runtime: RCRuntime) -> None:
        super().__init__(module)
        self.builder = builder

        #: This is the type of elements contained inside the array.
        #: An array cannot store elements of different types.
        self.contains = contains
        self.contains_ptr_type = contains.llvm_type.as_pointer()

        #: ``{ Contains*, int32 size, int32 capacity }``
        self.array_struct_type = ir.LiteralStructType([self.contains_ptr_type, I32, I32])
        self.array_pointer_type = self.array_struct_type.as_pointer()

        #: ``array<T> init_array(int32 initial_capacity)``
        self.init_type = ir.FunctionType(self.contains_ptr_type, [I32])
        self.init_func = ir.Function(self.module, self.init_type, name="init_array")
        block = self.init_func.append_basic_block(name="entry")
        builder = ir.IRBuilder(block)

        initial_count = self.init_func.args[0]

        struct_size = I32(16)
        storage_memory = builder.call(rc_runtime.rc_alloc_func, [struct_size], "storage_memory")
        array_inst: ir.CastInstr = builder.bitcast(storage_memory, self.array_pointer_type, "array_inst") # type: ignore

        element_size = self.get_type_size(target, contains.llvm_type)
        initial_size = builder.mul(initial_count, I32(element_size), "initial_size")
        initial_memory = builder.call(runtime.malloc, [initial_size], "initial_memory")
        data_ptr = builder.bitcast(initial_memory, self.contains_ptr_type, "data_ptr")

        data_addr = self.get_struct_val(builder, array_inst, 0, "data_addr")
        builder.store(data_ptr, data_addr)

        size_addr = self.get_struct_val(builder, array_inst, 1, "size_addr")
        builder.store(I32(0), size_addr)

        capacity_addr = self.get_struct_val(builder, array_inst, 2, "capacity_addr")
        builder.store(initial_size, capacity_addr)

        builder.ret(array_inst)

        #: ``void append_array(Array* array, T value)``
        self.append_type = ir.FunctionType(ir.VoidType(), [self.array_pointer_type, contains.llvm_type])
        self.append = ir.Function(self.module, self.append_type, "append_array")
        entry = self.append.append_basic_block("entry")
        grow_block = self.append.append_basic_block("grow")
        store_block = self.append.append_basic_block("store")
        builder = ir.IRBuilder(entry)

        array_pointer = self.append.args[0]
        to_append = self.append.args[1]

        data_ptr_addr = self.get_struct_val(builder, array_pointer, 0, "data_ptr_addr")
        size_addr = self.get_struct_val(builder, array_pointer, 1, "size_addr")
        cap_addr = self.get_struct_val(builder, array_pointer,2, "cap_addr")
        current_size = builder.load(size_addr, "current_size")
        current_capacity = builder.load(cap_addr, "current_capacity")

        grow_necessary = builder.icmp_unsigned(">=", current_size, current_capacity, "grow_necessary")
        builder.cbranch(grow_necessary, grow_block, store_block)

        builder.position_at_start(grow_block)

        new_capacity = builder.mul(current_capacity, I32(2), "new_capacity")
        new_mem_size = builder.mul(new_capacity, I32(element_size), "new_mem_size")

        old_data_ptr = builder.load(data_ptr_addr, "old_data_ptr")
        old_data_void = builder.bitcast(old_data_ptr, I8_POINTER, "old_data_void")

        new_memory = builder.call(runtime.realloc, [old_data_void, new_mem_size], "new_memory")
        new_data_ptr = builder.bitcast(new_memory, self.contains_ptr_type, "new_data_ptr")

        builder.store(new_data_ptr, data_ptr_addr)
        builder.store(new_capacity, cap_addr)
        builder.branch(store_block)

        builder.position_at_start(store_block)

        data_ptr = builder.load(data_ptr_addr, "data_ptr")
        insert_addr = builder.gep(data_ptr, [current_size], name="insert_addr")
        builder.store(to_append, insert_addr)

        new_size = builder.add(current_size, I32(1), "new_size")
        builder.store(new_size, size_addr)

        builder.ret_void()

        #: ``void free(Array* to_free)``
        self.free_array_type = ir.FunctionType(VOID, [self.array_pointer_type])
        self.free_array_func = ir.Function(self.module, self.free_array_type, name="free_array")
        block = self.free_array_func.append_basic_block("entry")
        builder = ir.IRBuilder(block)

        array_pointer = self.free_array_func.args[0] # TODO: This needs to be bitcasted to type?

        data_ptr_addr = self.get_struct_val(builder, array_pointer, 0, "data_ptr_addr")
        data_ptr = builder.load(data_ptr_addr, "data_ptr")
        data_void = builder.bitcast(data_ptr, I8_POINTER, "data_void")

        # Free all the elements stored in the array.
        builder.call(runtime.free, [data_void])

        # Free the whole struct.
        arr_void = builder.bitcast(array_pointer, I8_POINTER, "arr_void")
        builder.call(runtime.free, [arr_void])

        builder.ret_void()

        #: Destroys the array and calls the destructor of every
        #: value contained inside it.
        #: ``void destroy(byte*)``
        self.destructor_type = ir.FunctionType(VOID, [I8_POINTER])
        self.destructor_func = ir.Function(module, self.destructor_type, "array_destructor")
        block = self.destructor_func.append_basic_block("entry")
        loop_check_block = self.destructor_func.append_basic_block("loop_check")
        loop_body_block = self.destructor_func.append_basic_block("loop_body")
        after_loop_block = self.destructor_func.append_basic_block("after_loop")
        builder = ir.IRBuilder(block)

        array_pointer = self.destructor_func.args[0]
        this: ir.CastInstr = builder.bitcast(array_pointer, self.array_pointer_type, "this") # type: ignore
        
        size_ptr = self.get_struct_val(builder, this, 1, "size_addr")
        size = builder.load(size_ptr, "size")
        data_ptr_ptr = self.get_struct_val(builder, this, 0, "data_ptr_ptr")
        data_ptr = builder.load(data_ptr_ptr, "data_ptr")

        i = builder.alloca(I32, name="i")
        builder.store(I32(0), i)
        builder.branch(loop_check_block)

        builder.position_at_start(loop_check_block)

        current_i = builder.load(i, "current_i")
        done = builder.icmp_unsigned("==", current_i, size, "is_done")
        builder.cbranch(done, after_loop_block, loop_body_block)

        builder.position_at_start(loop_body_block)

        if contains.needs_refcount:
            elem_ptr = builder.gep(data_ptr, [current_i], name="elem_ptr")
            elem_raw = builder.bitcast(elem_ptr, I8_POINTER, "elem_raw")
            possible_destructor = contains.get_destructor()
            if possible_destructor:
                destructor_ptr = possible_destructor
            else:
                destructor_fn_ty = ir.FunctionType(VOID, [I8_POINTER])
                destructor_ptr = ir.Constant(destructor_fn_ty.as_pointer(), None)
            builder.call(rc_runtime.rc_release_func, [elem_raw, destructor_ptr]) # Not if this is how we should pass the destructor

        next_i = builder.add(current_i, I32(1), "next_i")
        builder.store(next_i, i)
        builder.branch(loop_check_block)

        builder.position_at_start(after_loop_block)

        data_void = builder.bitcast(data_ptr, I8_POINTER, "data_void")
        builder.call(runtime.free, [data_void])

        builder.ret_void()
    
    @property
    def llvm_type(self) -> ir.Type:
        """
        See ``array_struct_type``.
        """

        return self.array_struct_type
    
    @property
    def name(self) -> str:
        """
        Generics aren't fully supported, but this basically returns
        the type in the format that it will be when generics are supported.
        """

        return f"array<{self.contains.name}>"
    
    @property
    def needs_refcount(self) -> bool:
        """
        The ``array`` is reference counted.
        """

        return True
    
    def add_field(self, name: str, field: Field) -> None:
        raise RuntimeError("Cannot add a field to the ArrayType.")
    
    def get_field(self, name: str) -> Field:
        """
        Some functions are supported that are custom implemented
        in LLVM IR. These are ``init`` and ``append``, and I plan
        to implement more in the future.
        """

        if name == "init":
            hl_init_type = FunctionType(self.module, "init", [], self, self.init_func)
            return Field(hl_init_type, {MemberFlag.STATIC})
        elif name == "append":
            hl_append_type = FunctionType(self.module, "append", [self, self.contains], VoidType(self.module), self.append)
            return Field(hl_append_type)
        else:
            raise ValueError(f"Cannot call '{name}' on type '{self.name}'.")
    
    def has_field(self, name: str) -> bool:
        """
        Has function fields ``init`` and ``append``.
        """

        return name == "init" or name == "append"
    
    def get_destructor(self) -> ir.Function | None:
        """
        See ``destructor_func``.
        """
        return self.destructor_func
    
    def call(self, builder: ir.IRBuilder, this: Value, name: str, args: list[Value], rc_runtime: RCRuntime, target_data: llvm.TargetData) -> Value:
        """
        Only ``append`` can be called via this, ``init`` should be 
        called directly from the function gotten by ``get_field``.
        """
        
        if name == "init":
            raise ValueError("Call 'init' function via get_field.")
        elif name == "append":
            if args[0].val_type.name != self.contains.name:
                raise ValueError("Invalid type for append call.")
            return Value(builder, VoidType(self.module), builder.call(self.append, [this.load_value(builder), args[0].load_value(builder)]), "array_append_res")
        else:
            raise ValueError(f"Cannot call '{name}' on type '{self.name}'")
    
    def generate(self, builder: ir.IRBuilder) -> Value:
        """
        Generates a new ``array`` wrapped in a ``Value``.
        """

        return Value(builder, self, builder.call(self.init_func, [I32(1)], "initial_value"), "initial_value")
    
    @staticmethod
    def get_struct_val(builder: ir.IRBuilder, struct: ir.Value, index: int, name: str):
        """
        Not really unique to ``array``, this should be moved out
        of here.
        """
        
        return builder.gep(struct, [ir.Constant(I32, 0), ir.Constant(I32, index)], name=name)
    
    @staticmethod
    def get_type_size(target_data: llvm.TargetData, ir_type: ir.Type) -> int:
        """
        This is also definetely not related to ``array``, and should
        be moved elsewhere.
        """
        
        ir_str = str(ir_type)

        type_sizes = {
            "i1": 1,
            "i8": 1,
            "i16": 2,
            "i32": 4,
            "i64": 8,
            "float": 4,
            "double": 8,
        }

        if ir_str in type_sizes:
            return type_sizes[ir_str]

        if ir_str.endswith("*"):
            return 8

        if isinstance(ir_type, ir.LiteralStructType):
            return sum(
                ArrayType.get_type_size(target_data, elem) for elem in ir_type.elements
            )

        if isinstance(ir_type, ir.IdentifiedStructType):
            return sum(
                ArrayType.get_type_size(target_data, elem) for elem in ir_type.elements # type: ignore
            )

        if isinstance(ir_type, ir.ArrayType):
            return ir_type.count * ArrayType.get_type_size(target_data, ir_type.element)

        raise ValueError(f"Unknown type size for '{ir_str}'")