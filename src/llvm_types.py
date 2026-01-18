from llvmlite import ir

I32 = ir.IntType(32)
I8_POINTER = ir.IntType(8).as_pointer()
VOID = ir.VoidType()