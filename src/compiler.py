from llvmlite import ir
from scanner import Token
from ast_classes import Accessible, BinaryExpr, Grouping, Program, Class, Function, VarDecl, Expression, LiteralExpr, CallExpr, LiteralType, UnaryExpr
from builtin_types import BoolType, CharType, Field, FloatType, IntType, StringType, Type, UserType, FunctionType, Value, VoidType
from src.parser import ArrayExpr, ScopeExpr

def compile_error(token: Token, msg: str) -> RuntimeError:
    print(f"@Compiler [line {token.line}] [token {token.raw}] [ERROR] {msg}")
    return RuntimeError()

class Compiler:
    def __init__(self, program: Program, module_name: str, filename: str, package: str) -> None:
        self.program = program
        self.module_name = module_name
        self.module = ir.Module(self.module_name)
        self.di_file = self.module.add_debug_info("DIFile", {
            "filename": filename,
            "package": package,
        })
        self.di_compile_unit = self.module.add_debug_info("DICompileUnit", {
            "language": ir.DIToken("DW_LANG_Python"),
            "file": self.di_file,
            "producer": "llvmlite 0.46.0",
            "runtimeVersion": 2,
            "isOptimized": False,
        }, is_distinct=True)
        self.builder = ir.IRBuilder()
        self.type_db: dict[str, Type] = {}
        self.inside: UserType | None = None
    
    def get_type(self, name: Token) -> Type:
        if not name in self.type_db:
            raise compile_error(name, f"Class '{name}' not found")
        
        return self.type_db[name.raw]
    
    def gen_literal(self, lit: LiteralExpr) -> Value:
        match lit.ltype:
            case LiteralType.BOOL:
                ret_type = BoolType(self.module)
            case LiteralType.INT:
                ret_type = IntType(self.module)
            case LiteralType.FLOAT:
                ret_type = FloatType(self.module)
            case LiteralType.CHAR:
                ret_type = CharType(self.module)
            case LiteralType.STRING:
                ret_type = StringType(self.module)
        return Value(ret_type, ir.Constant(ret_type.llvm_type, lit.val))
    
    def gen_function_call(self, expr: CallExpr) -> Value:
        pass

    def gen_accessible(self, expr: Accessible) -> Value:
        pass

    def gen_binary(self, expr: BinaryExpr) -> Value:
        pass

    def gen_unary(self, expr: UnaryExpr) -> Value:
        pass

    def gen_array(self, expr: ArrayExpr) -> Value:
        pass

    def gen_scope(self, expr: ScopeExpr) -> Value:
        pass

    def gen_expression(self, expr: Expression) -> Value:
        if isinstance(expr, LiteralExpr):
            return self.gen_literal(expr)
        if isinstance(expr, Accessible):
            return self.gen_accessible(expr)
        if isinstance(expr, BinaryExpr):
            return self.gen_binary(expr)
        if isinstance(expr, UnaryExpr):
            return self.gen_unary(expr)
        if isinstance(expr, ArrayExpr):
            return self.gen_array(expr)
        if isinstance(expr, ScopeExpr):
            return self.gen_scope(expr)
        if isinstance(expr, Grouping):
            return self.gen_expression(expr.expr)

    def gen_args(self, args: list[tuple[Token, Token]]) -> dict[str, Type]:
        out: dict[str, Type] = {}

        for arg_type, name in args:
            out[arg_type.raw] = self.get_type(name)

        return out
    
    def gen_member(self, member: Class | Function | VarDecl, parent: UserType | None = None) -> Type:
        if isinstance(member, Class):
            return self.gen_class(member)
        if isinstance(member, Function):
            return self.gen_function_definition(member, parent)
        if isinstance(member, VarDecl):
            return self.gen_variable(member, parent)
    
    def gen_variable(self, generate: VarDecl, parent: UserType | None = None) -> Type:
        var_type = self.get_type(generate.type_name[0])
        if generate.value:
            expr_type = self.gen_expression(generate.value)
            # TODO: Check casting
            # TODO: Actually link the value to the variable?
            if not expr_type.val_type == var_type.name:
                raise compile_error(generate.type_name[0], f"Cannot assign '{expr_type.name}' to '{var_type.name}'")
        return var_type

    def gen_function_definition(self, generate: Function, parent: UserType | None = None) -> FunctionType:
        # TODO: Function flags, member flags, body.
        return FunctionType(
            self.module,
            generate.name.raw,
            list(arg for arg in self.gen_args(generate.args).values()),
            self.get_type(generate.returns) if generate.returns else VoidType(self.module)
        )
    
    def gen_class(self, generate: Class) -> UserType:
        out = UserType(self.module, generate.name.raw)

        args = self.gen_args(generate.args)
        for name in args.keys():
            out.add_field(name, Field(args[name]))

        return out
