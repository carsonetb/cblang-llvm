from llvmlite import ir
from llvm_types import I8_POINTER, I32, VOID

class CRuntime:
    def __init__(self, module: ir.Module) -> None:
        self.module = module

        # void* malloc(size_t size)
        self.malloc_type = ir.FunctionType(I8_POINTER, [I32])
        self.malloc = ir.Function(self.module, self.malloc_type, name="malloc")

        # void* realloc(void* pointer, size_t size)
        self.realloc_type = ir.FunctionType(I8_POINTER, [I8_POINTER, I32])
        self.realloc = ir.Function(self.module, self.realloc_type, name="realloc")

        # void free(void* pointer)
        self.free_type = ir.FunctionType(VOID, [I8_POINTER])
        self.free = ir.Function(self.module, self.free_type, name="free")

        # int32 printf(char* str, ...)
        self.printf_type = ir.FunctionType(I32, [I8_POINTER], True)
        self.printf_func = ir.Function(self.module, self.printf_type, name="printf")

        # void sprintf(char* str, char* format, ...)
        self.sprintf_type = ir.FunctionType(VOID, [I8_POINTER, I8_POINTER], True)
        self.sprintf_func = ir.Function(self.module, self.sprintf_type, "sprintf")