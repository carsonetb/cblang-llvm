from __future__ import annotations
from typing import cast
from llvmlite import ir
import llvmlite.binding as llvm
from llvm_types import I1, I32, I8
from scanner import Token
from ast_classes import Accessible, BinaryExpr, Grouping, MemberFlag, Program, Class, Function, Statement, VarDecl, Expression, LiteralExpr, CallExpr, LiteralType, UnaryExpr, VariableExpr, ArrayExpr, ScopeStmt, WhileStmt
from builtin_types import BoolType, CRuntime, CharType, Field, FloatType, IntType, RCRuntime, RCValue, StringType, Type, UserType, FunctionType, Value, FunctionValue, ValueField, VoidType, ArrayType, VoidValue
from src.parser import AssignmentStmt, ElseStmt, ForStmt, IfStmt, ReturnStmt

def compile_error(token: Token, msg: str) -> RuntimeError:
    print(f"@Compiler [line {token.line}] [token {token.raw}] [ERROR] {msg}")
    return RuntimeError()

class Compiler:
    def __init__(self, program: Program, module_name: str, filename: str, package: str) -> None:
        llvm.initialize_native_target()
        llvm.initialize_native_asmprinter()
        self.program = program
        self.target_machine = llvm.Target.from_default_triple().create_target_machine()
        self.target_data = self.target_machine.target_data
        self.module_name = module_name
        self.module = ir.Module(self.module_name)
        self.c_runtime = CRuntime(self.module)
        self.rc_runtime = RCRuntime(self.module, self.c_runtime)
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
        self.scoped_variables: list[dict[str, ValueField]] = [{}] # Start with the global scope.
        self.type_db: dict[str, Type] = {}
        self.path_array = [package, module_name]
        arr = ArrayType(self.builder, self.module, self.target_machine.target_data, IntType(self.module), self.c_runtime, self.rc_runtime)
        print(self.module)
    
    @property
    def scope(self) -> dict[str, ValueField]:
        return self.scoped_variables[-1]
    
    @property 
    def builder(self) -> ir.IRBuilder:
        return self.builder_stack[-1]
    
    @property
    def path(self) -> str:
        return "__".join(self.path_array)
    
    def get_type(self, name: Token) -> Type:
        if not name.raw in self.type_db:
            raise compile_error(name, f"Class '{name}' not found.")
        
        return self.type_db[name.raw]
    
    def add_field(self, name: Token, val: ValueField) -> None:
        if name.raw in self.scope:
            raise compile_error(name, f"Field '{name}' already exists within the current scope.")
        
        self.scope[name.raw] = val
    
    def get_field(self, name: Token) -> ValueField:
        for scope in reversed(self.scoped_variables):
            if name.raw in scope:
                return scope[name.raw]
        
        raise compile_error(name, f"Variable '{name}' doesn't exist within the current scope.")

    def get_sizeof(self, llvm_type: ir.Type) -> ir.Value:
        null_ptr = ir.Constant(llvm_type.as_pointer(), None)
        size_ptr = self.builder.gep(null_ptr, I32(1))
        size = self.builder.ptrtoint(size_ptr, I32)
        return size # type: ignore

    def gen_string_literal(self, string: str) -> Value:
        b_string = bytearray(string.encode("utf8") + b"\0")
        string_t = StringType(self.module, len(b_string))
        constant = ir.Constant(string_t.llvm_type, len(b_string))
        return Value(self.builder, string_t, constant)
    
    def pop_scope(self) -> dict[str, ValueField]:
        scope = self.scoped_variables.pop()
        for _, field in scope.items():
            if field.value.val_type.needs_refcount:
                assert isinstance(field.value, RCValue)
                field.value.release(self.builder, self.rc_runtime)
        return scope
    
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
                return self.gen_string_literal(cast(str, lit.val))
        return Value(self.builder, ret_type, ir.Constant(ret_type.llvm_type, lit.val))
    
    def gen_function_call(self, expr: CallExpr, on: Value | None = None) -> Value:
        # TODO: Validate arguments.
        args = []
        for arg_expr in expr.args:
            arg_val = self.gen_expression(arg_expr)
            if isinstance(arg_val, RCValue):
                arg_val.retain(self.builder, self.rc_runtime)
            args.append(arg_val)
        if not on:
            field = self.get_field(expr.callee)
            if not isinstance(field.value, FunctionValue):
                raise compile_error(expr.callee, f"Cannot call '{expr.callee}' because it is not a function.")
            return field.value.call_this(self.builder, args, self.rc_runtime, self.target_data)
        try:
            return on.call(self.builder, expr.callee.raw, args, self.rc_runtime, self.target_data)
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
            return lhs.call(self.builder, expr.op.raw, [rhs], self.rc_runtime, self.target_data)
        except:
            raise compile_error(expr.op, f"Operator '{lhs.val_type.name}' {expr.op} '{rhs.val_type.name}' does not exist.")

    def gen_unary(self, expr: UnaryExpr) -> Value:
        rhs = self.gen_expression(expr.rhs)

        try:
            return rhs.call(self.builder, expr.op.raw, [], self.rc_runtime, self.target_data)
        except:
            raise compile_error(expr.op, f"Operator {expr.op} '{rhs.val_type.name}' does not exist.")

    def gen_array(self, expr: ArrayExpr) -> Value:
        if len(expr.elements) == 0:
            raise compile_error(expr.array_end, "Cannot infer type of an empty array.")
        
        values = [self.gen_expression(expr.elements[0])]
        target_type = values[0].val_type
        if len(expr.elements) >= 2:
            for element in expr.elements[1:]:
                val = self.gen_expression(element)
                if val.val_type.name != target_type.name:
                    raise compile_error(expr.array_end, "Array has values of inconsistent types.")
        
        this_type_string = f"array<{target_type.name}>"
        if this_type_string in self.type_db:
            this_type = cast(ArrayType, self.type_db[this_type_string])
        else:
            this_type = ArrayType(self.builder, self.module, self.target_data, target_type, self.c_runtime, self.rc_runtime)
        
        out = this_type.generate(self.builder)
        for value in values:
            this_type.call(self.builder, out, "append", [value], self.rc_runtime, self.target_data)

        return out

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
        if isinstance(expr, Grouping):
            return self.gen_expression(expr.expr)
        assert(False)
                
    def gen_scope(self, expr: ScopeStmt) -> Value | VoidValue | None:
        for stmt in expr.body:
            possible_ret = self.gen_statement(stmt)
            if not possible_ret is None:
                return possible_ret
    
    def gen_var_declaration(self, stmt: VarDecl) -> None:
        var_type = self.get_type(stmt.type_name[0])
        name = stmt.type_name[1]
        if stmt.value:
            value = self.gen_expression(stmt.value)
        else:
            if isinstance(var_type, (BoolType, IntType, FloatType, CharType)):
                value = Value(self.builder, var_type, ir.Constant(var_type.llvm_type, 0))
            elif isinstance(var_type, StringType):
                value = self.gen_string_literal("")
            elif isinstance(var_type, ArrayType):
                value = var_type.generate(self.builder)
            elif isinstance(var_type, UserType):
                raise compile_error(name, "Must provide an initializer for non-builtin types.")
            else:
                raise ValueError("Unknown type")
        self.add_field(name, ValueField(var_type, value, stmt.flags))

    def gen_assignment(self, stmt: AssignmentStmt) -> None:
        target = self.gen_accessible(stmt.target)
        source = self.gen_expression(stmt.value)
        if source.val_type.name != target.val_type.name:
            raise compile_error(stmt.equal_token, f"Cannot assign value of type '{source.val_type.name}' to variable of type '{target.val_type.name}'")

        if isinstance(target, RCValue):
            source.retain(self.builder, self.rc_runtime)
            target.release(self.builder, self.rc_runtime)

        target.store_value(self.builder, source.load_value(self.builder)) # TODO: This will be changed when reference semantics.

    def gen_if(self, stmt: IfStmt) -> Value | None:
        branching_val = self.gen_expression(stmt.condition)
        if branching_val.val_type.name != "bool":
            raise compile_error(stmt.keyword_tok, "The condition in an if statement must evaluate to type 'bool'.")
        branching_res = self.builder.icmp_unsigned("==", branching_val.load_value(self.builder), I1(1))

        truthy_block = self.builder.append_basic_block()
        falsey_block = self.builder.append_basic_block()
        continued_block = self.builder.append_basic_block()
        self.builder.cbranch(branching_res, truthy_block, falsey_block)

        self.builder.position_at_start(truthy_block)
        self.gen_scope(stmt.body)
        self.builder.branch(continued_block)

        # TODO: Returns

        self.builder.position_at_start(falsey_block)
        if stmt.else_branch:
            if isinstance(stmt.else_branch, IfStmt):
                self.gen_if(stmt.else_branch)
            if isinstance(stmt.else_branch, ElseStmt):
                self.gen_else(stmt.else_branch)
        
        # Either branch from falsey_block to continued_block, or, if 
        # we generated an if statement, branch from ITS continued block
        # to the higher level continued block.
        self.builder.branch(continued_block)
        
        self.builder.position_at_start(continued_block)

    def gen_else(self, stmt: ElseStmt) -> Value | VoidValue | None:
        return self.gen_scope(stmt.body)

    def gen_for(self, stmt: ForStmt) -> Value | None:
        pass
    
    def gen_while(self, stmt: WhileStmt) -> Value | None:
        pass

    def gen_return(self, stmt: ReturnStmt) -> Value | VoidValue:
        ret_val = self.gen_expression(stmt.value) if stmt.value else VoidValue()
        
        # Release all fields besides return value.
        for _, field in self.scope.items():
            if field.value != ret_val and isinstance(field.value, RCValue):
                field.value.release(self.builder, self.rc_runtime)
        
        if isinstance(ret_val, Value):
            self.builder.ret(ret_val.load_value(self.builder))
        else:
            self.builder.ret_void()
        return ret_val

    def gen_statement(self, stmt: Statement) -> Value | VoidValue | None:
        """Statements only return a value for a (possibly cascaded) return statement."""

        if isinstance(stmt, ScopeStmt):
            return self.gen_scope(stmt)
        if isinstance(stmt, VarDecl):
            return self.gen_var_declaration(stmt)
        if isinstance(stmt, AssignmentStmt):
            return self.gen_assignment(stmt)
        if isinstance(stmt, IfStmt):
            return self.gen_if(stmt)
        if isinstance(stmt, ForStmt):
            return self.gen_for(stmt)
        if isinstance(stmt, WhileStmt):
            return self.gen_while(stmt)
        if isinstance(stmt, ReturnStmt):
            return self.gen_return(stmt)
        if isinstance(stmt, Expression):
            self.gen_expression(stmt)
    
    def gen_arg_types(self, args: list[tuple[Token, Token]]) -> list[tuple[str, Type]]:
        out: list[tuple[str, Type]] = []

        for arg_type_token, name in args:
            out.append((name.raw, self.get_type(arg_type_token)))

        return out

    def gen_args(self, function: ir.Function, types: dict[str, Type]) -> dict[str, Value]:
        out: dict[str, Value] = {}

        for arg_name, arg_type in types.items():
            out[arg_name] = Value(self.builder, arg_type, ir.Argument(function, arg_type.llvm_type))

        return out
    
    def gen_member(self, member: Function | VarDecl) -> Field:
        if isinstance(member, Function):
            return self.gen_function_definition(member)
        if isinstance(member, VarDecl):
            return self.gen_variable(member)
    
    def gen_variable(self, generate: VarDecl) -> Field:
        var_name = generate.type_name[1]
        var_type = self.get_type(generate.type_name[0])
        expr_value = self.gen_expression(generate.value)
        value = expr_value.value_ptr
        # TODO: Check casting
        if not expr_value.val_type == var_type.name:
            raise compile_error(generate.type_name[0], f"Cannot assign '{expr_value.val_type.name}' to '{var_type.name}'")
    
        if var_type.needs_refcount:
            hl_value = RCValue(self.builder, var_type, value, self.rc_runtime, self.target_data)
        else:
            hl_value = Value(self.builder, var_type, value)
        field = ValueField(var_type, hl_value, generate.flags)
        
        self.add_field(var_name, field)

        return field

    def gen_function_definition(self, generate: Function) -> ValueField:
        arg_types = self.gen_arg_types(generate.args)
        type_list = [arg_type for _, arg_type in arg_types]
        return_type = self.get_type(generate.returns) if generate.returns else VoidType(self.module)
        ir_function_ty = ir.FunctionType(return_type.llvm_type, (arg.llvm_type for arg in type_list))
        function_value = ir.Function(self.module, ir_function_ty, f"{self.path}__{generate.name.raw}")
        
        block = function_value.append_basic_block("entry")
        self.builder_stack.append(ir.IRBuilder(block))
        self.scoped_variables.append(dict([(arg_types[i][0], ValueField(arg_types[i][1], Value(self.builder, arg_types[i][1], arg))) for i, arg in enumerate(function_value.args)]))
        for stmt in generate.body:
            possible_ret = self.gen_statement(stmt)
            if not possible_ret is None:
                if possible_ret is VoidValue and not generate.returns is None:
                    raise compile_error(generate.name, f"Function does not always return type '{generate.returns.raw}'")
                elif generate.returns is None and not possible_ret is VoidValue:
                    raise compile_error(generate.name, f"Function has no return type, but has a line that returns non-void.")
                elif isinstance(possible_ret, Value) and not generate.returns is None and possible_ret.val_type.name != return_type.name:
                    raise compile_error(generate.name, f"Function does not always return type '{generate.returns.raw}'")
                break
        self.builder.ret_void()
        self.builder_stack.pop()
        self.pop_scope()

        function_type = FunctionType( self.module, generate.name.raw, type_list, return_type, function_value)
        function_field = ValueField(function_type, FunctionValue(self.builder, function_type, function_value), generate.member_flags | generate.function_flags)
        self.add_field(generate.name, function_field)

        return function_field
    
    def gen_class(self, generate: Class) -> UserType:
        out = UserType(self.module, generate.name.raw, self.rc_runtime)

        # This class' scope.
        self.scoped_variables.append({})
        self.path_array.append(generate.name.raw)

        arg_types = self.gen_arg_types(generate.args)
        type_list = [arg_type for _, arg_type in arg_types]
        initializer_ir_type = ir.FunctionType(out.llvm_type, [arg_type.llvm_type for arg_type in type_list])
        initializer_value = ir.Function(self.module, initializer_ir_type, f"{self.path}__init")
        initializer_type = FunctionType(self.module, generate.name.raw, type_list, out, initializer_value)
        initializer_field = ValueField(initializer_type, FunctionValue(self.builder, initializer_type, initializer_value), {MemberFlag.STATIC})
        self.add_field(generate.name, initializer_field)

        block = initializer_value.append_basic_block("entry")
        self.builder_stack.append(ir.IRBuilder(block))
        
        size = self.get_sizeof(out.llvm_type)
        raw_ptr = self.builder.call(self.rc_runtime.rc_alloc_func, [size])
        this_ptr = self.builder.bitcast(raw_ptr, out.llvm_type.as_pointer())

        for index, arg in enumerate(initializer_value.args):
            zero = ir.Constant(I32, 0)
            idx = ir.Constant(I32, index)

            field_pointer = self.builder.gep(this_ptr, [zero, idx], name=f"ptr_field_{idx}")
            self.builder.store(arg, field_pointer)

            type_name = generate.args[index]
            arg_type = self.get_type(type_name[0])
            self.add_field(type_name[1], ValueField(arg_type, Value(self.builder, arg_type, arg)))
        
        for member in generate.members:
            if isinstance(member, Class):
                # TODO: Inner classes
                continue
            self.gen_member(member)

        class_scope = self.pop_scope()
        for name, field in class_scope.items():
            out.add_field(name, field)

        init_field = out.get_field("init") if out.has_field("init") else None
        if init_field and isinstance(init_field, ValueField) and isinstance(init_field.value, FunctionValue):
            init_func = cast(FunctionValue, init_field.value)
            # TODO: Check that the init function doesn't return and doesn't have any args.
            init_func.call_this(self.builder, [], self.rc_runtime, self.target_data)
        
        self.builder.ret(this_ptr)
        self.builder_stack.pop()
        self.path_array.pop()

        return out
