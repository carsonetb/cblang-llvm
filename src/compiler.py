from typing import cast
from llvmlite import ir
import llvmlite.binding as llvm
from llvm_types import I32
from scanner import Token
from ast_classes import Accessible, BinaryExpr, Grouping, MemberFlag, Program, Class, Function, VarDecl, Expression, LiteralExpr, CallExpr, LiteralType, UnaryExpr, VariableExpr
from builtin_types import BoolType, CharType, Field, FloatType, IntType, StringType, Type, UserType, FunctionType, Value, FunctionValue, VoidType
from src.parser import ArrayExpr, ScopeExpr

def compile_error(token: Token, msg: str) -> RuntimeError:
    print(f"@Compiler [line {token.line}] [token {token.raw}] [ERROR] {msg}")
    return RuntimeError()

class Compiler:
    def __init__(self, program: Program, module_name: str, filename: str, package: str) -> None:
        self.program = program
        self.target_machine = llvm.Target.from_default_triple().create_target_machine()
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
        self.scoped_variables: list[dict[str, Field]] = [{}] # Start with the global scope.
        self.type_db: dict[str, Type] = {}
        self.inside: UserType | None = None
    
    @property
    def scope(self) -> dict[str, Field]:
        return self.scoped_variables[-1]
    
    @property 
    def builder(self) -> ir.IRBuilder:
        return self.builder_stack[-1]
    
    def get_type(self, name: Token) -> Type:
        if not name.raw in self.type_db:
            raise compile_error(name, f"Class '{name}' not found.")
        
        return self.type_db[name.raw]
    
    def add_field(self, name: Token, val: Field) -> None:
        if name.raw in self.scope:
            raise compile_error(name, f"Field '{name}' already exists within the current scope.")
        
        self.scope[name.raw] = val
    
    def get_field(self, name: Token) -> Field:
        for scope in reversed(self.scoped_variables):
            if name.raw in scope:
                return scope[name.raw]
        
        raise compile_error(name, f"Variable '{name}' doesn't exist within the current scope.")
    
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
    
    def gen_function_call(self, expr: CallExpr, on: Value | None = None) -> Value:
        # TODO: Validate arguments.
        args = [self.gen_expression(arg) for arg in expr.args]
        if not on:
            func = self.get_field(expr.callee).value
            if not isinstance(func, FunctionValue):
                raise compile_error(expr.callee, f"Cannot call '{expr.callee}' because it is not a function.")
            return func.call_this(self.builder, args)
        try:
            return on.call(self.builder, expr.callee.raw, args)
        except KeyError:
            raise compile_error(expr.callee, f"Type '{on.val_type.name}' has no member function '{expr.callee}'.")
        except ValueError:
            raise compile_error(expr.callee, f"Member '{on.val_type.name}.{expr.callee}' is not a function.")

    def gen_variable_expr(self, expr: VariableExpr, on: Value | None = None) -> Value:
        if not on:
            return self.get_field(expr.name).value
        try:
            return on.get(self.builder, expr.name.raw)
        except KeyError:
            raise compile_error(expr.name, f"Type '{on.val_type.name}' has no member '{expr.name}'")

    def gen_accessible(self, expr: Accessible) -> Value:
        if isinstance(expr, CallExpr):
            return self.gen_function_call(expr)
        if isinstance(expr, VariableExpr):
            return self.gen_variable_expr(expr)
        assert(False)

    def gen_binary(self, expr: BinaryExpr) -> Value:
        lhs = self.gen_expression(expr.lhs)
        rhs = self.gen_expression(expr.rhs)

        try:
            return lhs.call(self.builder, expr.op.raw, [rhs])
        except:
            raise compile_error(expr.op, f"Operator '{lhs.val_type.name}' {expr.op} '{rhs.val_type.name}' does not exist.")

    def gen_unary(self, expr: UnaryExpr) -> Value:
        rhs = self.gen_expression(expr.rhs)

        try:
            return rhs.call(self.builder, expr.op.raw, [])
        except:
            raise compile_error(expr.op, f"Operator {expr.op} '{rhs.val_type.name}' does not exist.")

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
        
        self.add_field(var_name, field)

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
        function_field = Field(FunctionValue(function_type, function_value), generate.member_flags | generate.function_flags)
        self.add_field(generate.name, function_field)
        
        block = function_value.append_basic_block("entry")
        self.builder_stack.append(ir.IRBuilder(block))
        self.scoped_variables.append(dict([(arg_types[i][0], Field(Value(arg_types[i][1], arg))) for i, arg in enumerate(function_value.args)]))
        # TODO: Generate the block.
        self.builder.ret_void()

        return function_field
    
    def gen_class(self, generate: Class) -> UserType:
        out = UserType(self.module, generate.name.raw)

        # This class' scope.
        self.scoped_variables.append({})

        arg_types = self.gen_arg_types(generate.args)
        initializer_type = FunctionType(
            self.module,
            generate.name.raw,
            [arg_type for _, arg_type in arg_types],
            out
        )
        initializer_value = ir.Function(self.module, initializer_type.llvm_type, generate.name.raw)
        initializer_field = Field(FunctionValue(initializer_type, initializer_value), {MemberFlag.STATIC})
        self.add_field(generate.name, initializer_field)

        block = initializer_value.append_basic_block("entry")
        self.builder_stack.append(ir.IRBuilder(block))
        this_ptr = self.builder.alloca(out.llvm_type, name="this")

        for index, arg in enumerate(initializer_value.args):
            zero = ir.Constant(I32, 0)
            idx = ir.Constant(I32, index)

            field_pointer = self.builder.gep(this_ptr, [zero, idx], name=f"ptr_field_{idx}")
            self.builder.store(arg, field_pointer)

            type_name = generate.args[index]
            self.add_field(type_name[1], Field(Value(self.get_type(type_name[0]), arg)))
        
        for member in generate.members:
            if isinstance(member, Class):
                # TODO: Inner classes
                continue
            self.gen_member(member)

        class_scope = self.scoped_variables.pop()
        for name, field in class_scope.items():
            out.add_field(name, field)

        if out.has_field("init") and isinstance(out.get_field("init").value, FunctionValue):
            init_func = cast(FunctionValue, out.get_field("init").value)
            # TODO: Check that the init function doesn't return and doesn't have any args.
            init_func.call_this(self.builder, [])
        
        self.builder.ret(this_ptr)
        self.builder_stack.pop()

        return out
