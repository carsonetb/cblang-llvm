from llvmlite import ir

I32 = ir.IntType(32)
I8 = ir.IntType(8)
I1 = ir.IntType(1)
I8_POINTER = I8.as_pointer()
VOID = ir.VoidType()
FLOAT = ir.FloatType()