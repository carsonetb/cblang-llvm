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
        self.builder_stack = [ir.IRBuilder()]
        self.type_db: dict[str, Type] = {}
        self.scoped_variables: list[dict[str, Field]] = []
        self.inside: UserType | None = None
    
    def get_type(self, name: Token) -> Type:
        if not name in self.type_db:
            raise compile_error(name, f"Class '{name}' not found")
        
        return self.type_db[name.raw]
    
    @property
    def scope(self) -> dict[str, Field]:
        if len(self.scoped_variables) == 0:
            raise ValueError("Cannot get a scope because no scope has been created yet.")

        return self.scoped_variables[-1]
    
    @property 
    def builder(self) -> ir.IRBuilder:
        return self.builder_stack[-1]
    
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
    
    def gen_arg_types(self, args: list[tuple[Token, Token]]) -> list[tuple[str, Type]]:
        out: list[tuple[str, Type]] = []

        for arg_type_token, name in args:
            out.append((name.raw, self.get_type(arg_type_token)))

        return out

    def gen_args(self, function: ir.Function, types: dict[str, Type]) -> dict[str, Value]:
        out: dict[str, Value] = {}

        for arg_name, arg_type in types.items():
            out[arg_name] = Value(arg_type, ir.Argument(function, arg_type.llvm_type))

        return out
    
    def gen_member(self, member: Function | VarDecl) -> Field:
        if isinstance(member, Function):
            return self.gen_function_definition(member)
        if isinstance(member, VarDecl):
            return self.gen_variable(member)
    
    def gen_variable(self, generate: VarDecl) -> Field:
        var_name = generate.type_name[1]
        var_type = self.get_type(generate.type_name[0])
        if generate.value:
            expr_value = self.gen_expression(generate.value)
            value = expr_value.value
            # TODO: Check casting
            if not expr_value.val_type == var_type.name:
                raise compile_error(generate.type_name[0], f"Cannot assign '{expr_value.val_type.name}' to '{var_type.name}'")
        else:
            value = self.builder.alloca(var_type) # Stack allocation? Hmmm...
        
        field = Field(Value(var_type, value), generate.flags)
        
        if var_name.raw in self.scope:
            raise compile_error(var_name, "Variable already exists in the current scope.")
        self.scope[var_name.raw] = field

        return field

    def gen_function_definition(self, generate: Function) -> Field:
        arg_types = self.gen_arg_types(generate.args)
        function_type = FunctionType(
            self.module,
            generate.name.raw,
            [arg_type for _, arg_type in arg_types],
            self.get_type(generate.returns) if generate.returns else VoidType(self.module)
        )
        function_value = ir.Function(self.module, function_type.llvm_type, generate.name.raw)
        
        block = function_value.append_basic_block("entry")
        self.builder_stack.append(ir.IRBuilder(block))
        self.scoped_variables.append(dict([(arg_types[i][0], Field(Value(arg_types[i][1], arg))) for i, arg in enumerate(function_value.args)]))
        # TODO: Generate the block.
        self.builder.ret_void()

        return Field(Value(function_type, function_value), generate.member_flags | generate.function_flags)
    
    def gen_class(self, generate: Class) -> UserType:
        out = UserType(self.module, generate.name.raw)

        args = self.gen_args(generate.args)
        for name in args.keys():
            out.add_field(name, Field(args[name]))

        return out
