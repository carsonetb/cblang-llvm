from llvmlite import ir
from ast_classes import MemberFlag, Span
from compiler.compiler_data import CompilerData
from llvm_types import I32, I8
from representations.field import ValueField
from representations.types.base_type import Type
from representations.types.user_types import FunctionType
from representations.value import FunctionValue, RCValue, Value
from runtime.c_runtime import CRuntime
from scanner import Token
from rich import print


def compile_error(token: Token | Span, msg: str) -> RuntimeError:
    line_repr = f"[at [i]{token.pos}[i]]" if token is Token else f"[from [i]{token}[/i]]"
    raw = f" [token [bold][i]{token.raw}[/i][/bold]]" if token is Token else ""
    print(f"[Compiler] {line_repr}{raw} [bold red][ERROR] {msg}[/bold red]")
    return RuntimeError()


def compile_warning(token: Token | Span, msg: str) -> RuntimeError:
    line_repr = f"[at [i]{token.pos}[i]]" if token is Token else f"[from [i]{token}[/i]]"
    raw = f" [token [bold][i]{token.raw}[/i][/bold]]" if token is Token else ""
    print(f"[Compiler] {line_repr}{raw} [i yellow][WARNING] {msg}[/i yellow]")
    return RuntimeError()


def get_printf(module: ir.Module, builder: ir.IRBuilder, type_db: dict[str, Type], c_runtime: CRuntime) -> ValueField:
    printf_type = FunctionType(module, "printf", [type_db["string"]], type_db["int"], c_runtime.printf_func)
    printf_val = FunctionValue(builder, printf_type, c_runtime.printf_func)
    return ValueField(printf_type, printf_val, {MemberFlag.STATIC})\

    
def get_type(data: CompilerData, name: Token) -> Type:
    if not name.raw in data.type_db:
        raise compile_error(name, f"Class '{name}' not found.")
    
    return data.type_db[name.raw]

    
def add_field(data: CompilerData, name: Token, val: ValueField) -> None:
    scope = data.scoped_variables[-1]
    if name.raw in scope:
        raise compile_error(name, f"Field '{name}' already exists within the current scope.")
    
    scope[name.raw] = val

def get_field(data: CompilerData, name: Token) -> ValueField:
    for scope in reversed(data.scoped_variables):
        if name.raw in scope.keys():
            return scope[name.raw]
    
    raise compile_error(name, f"Variable/function/class '{name}' doesn't exist within the current scope.")


def get_sizeof(builder: ir.IRBuilder, llvm_type: ir.Type) -> ir.Value:
    null_ptr = ir.Constant(llvm_type.as_pointer(), None)
    size_ptr = builder.gep(null_ptr, [I32(1)], name="size_ptr")
    size = builder.ptrtoint(size_ptr, I32, "size")
    return size # type: ignore


def gen_string_literal(data: CompilerData, string: str) -> Value:
    builder = data.builder_stack[-1]
    b_string = bytearray(string.encode("utf8") + b"\0")
    constant_type = ir.ArrayType(I8, len(b_string))
    constant = constant_type(b_string)
    mem = builder.call(data.c_runtime.malloc, [I32(len(b_string))], "mem")
    alloced_array = builder.bitcast(mem, constant_type.as_pointer(), "alloced_array")
    builder.store(constant, alloced_array)
    return RCValue(builder, data.type_db["string"], mem, data.rc_runtime, data.target_machine.target_data, "string_literal")