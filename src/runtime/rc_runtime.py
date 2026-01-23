from runtime.c_runtime import CRuntime
from llvmlite import ir
from llvm_types import I8_POINTER, I32, VOID

class RCRuntime:
    HEADER_SIZE = 4 # bytes

    def __init__(self, module: ir.Module, runtime: CRuntime) -> None:

        # byte* rc_alloc(int32 size)
        self.rc_alloc_type = ir.FunctionType(I8_POINTER, [I32])
        self.rc_alloc_func = ir.Function(module, self.rc_alloc_type, "rc_alloc")
        block = self.rc_alloc_func.append_basic_block("entry")
        builder = ir.IRBuilder(block)

        size = self.rc_alloc_func.args[0]
        total_size = builder.add(size, I32(self.HEADER_SIZE), "total_size")
        mem = builder.call(runtime.malloc, [total_size], "mem")
        count_ptr = builder.bitcast(mem, I32.as_pointer(), "count_ptr")
        builder.store(I32(1), count_ptr)
        data = builder.gep(mem, [I32(4)], name="data")
        builder.ret(data)

        # void rc_retain(byte* ptr)
        self.rc_retain_type = ir.FunctionType(VOID, [I8_POINTER])
        self.rc_retain_func = ir.Function(module, self.rc_retain_type, "rc_retain")
        block = self.rc_retain_func.append_basic_block("entry")
        builder = ir.IRBuilder(block)

        ptr = self.rc_retain_func.args[0]
        header = builder.gep(ptr, [I32(-self.HEADER_SIZE)], inbounds=False, name="header")
        count_ptr = builder.bitcast(header, I32.as_pointer(), "count_ptr")
        old_count = builder.load(count_ptr, "old_count")
        new_count = builder.add(old_count, I32(1), "new_count")
        builder.store(new_count, count_ptr)
        builder.ret_void()

        # void rc_release(byte* pointer)
        self.destructor_fn_type = ir.FunctionType(VOID, [I8_POINTER])
        self.destructor_ptr_type = self.destructor_fn_type.as_pointer()

        self.rc_release_type = ir.FunctionType(VOID, [I8_POINTER, self.destructor_ptr_type])
        self.rc_release_func = ir.Function(module, self.rc_release_type, name="rc_release")

        entry_block = self.rc_release_func.append_basic_block("entry")
        free_block = self.rc_release_func.append_basic_block("free_block")
        free_call_dtor_block = self.rc_release_func.append_basic_block("free_call_dtor")
        free_do_free_block = self.rc_release_func.append_basic_block("free_do_free")
        end_block = self.rc_release_func.append_basic_block("end")

        builder = ir.IRBuilder(entry_block)

        data_ptr = self.rc_release_func.args[0]
        destructor = self.rc_release_func.args[1]

        header_ptr = builder.gep(data_ptr, [I32(-self.HEADER_SIZE)], inbounds=False, name="header_ptr")
        count_ptr = builder.bitcast(header_ptr, I32.as_pointer(), "count_ptr")
        old_count = builder.load(count_ptr, name="old_count")
        new_count = builder.sub(old_count, I32(1), name="new_count")
        builder.store(new_count, count_ptr)
        is_zero = builder.icmp_unsigned("==", new_count, I32(0), name="is_zero")
        builder.cbranch(is_zero, free_block, end_block)

        # Free block just chooses between calling dtor or just freeing.
        builder.position_at_start(free_block)

        null_dtor = self.destructor_ptr_type(None) # basically just a nullptr
        has_dtor = builder.icmp_unsigned("!=", destructor, null_dtor, "has_dtor")
        builder.cbranch(has_dtor, free_call_dtor_block, free_do_free_block)

        builder.position_at_start(free_call_dtor_block)

        builder.call(destructor, [data_ptr])
        builder.branch(free_do_free_block)

        builder.position_at_start(free_do_free_block)

        builder.call(runtime.free, [header_ptr])
        builder.branch(end_block)

        builder.position_at_start(end_block)
        builder.ret_void()
