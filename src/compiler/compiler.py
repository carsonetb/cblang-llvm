from __future__ import annotations
from dataclasses import dataclass
from os import makedirs
import os
from typing import cast
from llvmlite import ir
import llvmlite.binding as llvm
from compiler.compiler_data import CompilerData
from compiler.compiler_helpers import add_field, compile_error, compile_warning, gen_string_literal, get_field, get_printf, get_sizeof, get_type
from llvm_types import I1, I32, I8, VOID
from scanner import Token
from ast_classes import Accessible, BinaryExpr, Grouping, MemberFlag, Program, Class, Function, Statement, VarDecl, Expression, LiteralExpr, CallExpr, LiteralType, UnaryExpr, VariableExpr, ArrayExpr, ScopeStmt, WhileStmt, AssignmentStmt, ElseStmt, ForStmt, IfStmt, ReturnStmt
from representations.types.base_type import Type
from representations.types.user_types import UserType, FunctionType
from representations.types.void_type import VoidType
from representations.types.bool_type import BoolType
from representations.types.int_type import IntType
from representations.types.float_type import FloatType
from representations.types.char_type import CharType
from representations.types.string_type import StringType
from representations.types.array_type import ArrayType
from representations.value import Value, RCValue, FunctionValue, VoidValue
from representations.field import Field, ValueField
from runtime.c_runtime import CRuntime
from runtime.rc_runtime import RCRuntime


class Compiler:
    """Compiler takes a program AST from the parser and generates a binary."""

    def __init__(self, program: Program, module_name: str, filename: str, package: str) -> None:
        llvm.initialize_native_target()
        llvm.initialize_native_asmprinter()
        target_machine = llvm.Target.from_default_triple().create_target_machine(reloc='pic')
        module_name = module_name
        module = ir.Module(module_name)
        c_runtime = CRuntime(module)
        rc_runtime = RCRuntime(module, c_runtime)
        type_db: dict[str, Type] = {
            'bool': BoolType(module),
            'int': IntType(module),
            'float': FloatType(module),
            'char': CharType(module),
            'string': StringType(module, c_runtime),
        }
        path_array = [package, module_name]

        self.main_func_ty = ir.FunctionType(I32, [])
        self.main_func = ir.Function(module, self.main_func_ty, f"main")
        block = self.main_func.append_basic_block("entry")
        builder_stack = [ir.IRBuilder(block)]
        scoped_variables: list[dict[str, ValueField]] = [{
            "print": get_printf(module, builder_stack[0], type_db, c_runtime)
        }] # Start with the global scope.
        inside_ptr: ir.Value | None = None # The class passed to the function currently being processed.
        self.data = CompilerData(
            program, target_machine, module_name, module, c_runtime,
            rc_runtime, type_db, path_array, builder_stack, scoped_variables, inside_ptr
        )
    
    @property
    def scope(self) -> dict[str, ValueField]:
        return self.data.scoped_variables[-1]
    
    @property 
    def builder(self) -> ir.IRBuilder:
        return self.data.builder_stack[-1]
    
    @property
    def path(self) -> str:
        return "__".join(self.data.path_array)
    
    @property 
    def target_data(self) -> llvm.TargetData:
        return self.data.target_machine.target_data
    
    @property 
    def module(self) -> ir.Module:
        return self.data.module
    
    @property 
    def type_db(self) -> dict[str, Type]:
        return self.data.type_db
    
    @property 
    def c_runtime(self) -> CRuntime:
        return self.data.c_runtime
    
    @property 
    def rc_runtime(self) -> RCRuntime:
        return self.data.rc_runtime
    
    @property 
    def scoped_variables(self) -> list[dict[str, ValueField]]:
        return self.data.scoped_variables
    
    @property 
    def builder_stack(self) -> list[ir.IRBuilder]:
        return self.data.builder_stack
    
    def pop_scope(self) -> dict[str, ValueField]:
        scope = self.data.scoped_variables.pop()
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
                return gen_string_literal(self.data, cast(str, lit.val))
        return Value(self.builder, ret_type, ir.Constant(ret_type.llvm_type, lit.val), "generated_literal")
    
    def gen_function_call(self, expr: CallExpr, on: Value | None = None) -> Value | VoidValue:
        # TODO: Validate arguments.

        if on is not None:
            try:
                field = on.val_type.get_field(expr.callee.raw)
                assert isinstance(field, ValueField)
            except KeyError:
                raise compile_error(expr.callee, f"Type {on.val_type.name} has no member function {expr.callee}.")
        else:
            field = get_field(self.data, expr.callee)

        if not isinstance(field.value, FunctionValue) or not isinstance(field.val_type, FunctionType):
            raise compile_error(expr.callee, f"Cannot call '{expr.callee}' because it is not a function.")
        
        arg_types = field.val_type.args

        if len(expr.args) != len(arg_types):
            raise compile_error(expr.callee, f"Number of arguments passed ({len(expr.args)}) is different than the number expected ({len(arg_types)})")

        args = []
        for i, arg_expr in enumerate(expr.args):
            expected_type = arg_types[i]
            arg_val = self.gen_expression(arg_expr)
            assert not isinstance(arg_val, VoidValue)

            if expected_type.castable_from(arg_val.val_type):
                if arg_val.val_type.needs_refcount:
                    compile_warning(expr.callee, f"For argument {i}, argument will be casted from type '{arg_val.val_type.name} to '{expected_type.name}', meaning a copy of the variable, not a reference, will be created.")
                arg_val = expected_type.generate_from(self.builder, arg_val, self.rc_runtime, self.c_runtime, self.target_data)

            if arg_val.val_type.name != expected_type.name:
                raise compile_error(expr.callee, f"For argument {i}, cannot pass variable of type '{arg_val.val_type.name}' to parameter of type '{expected_type.name}', and it cannot be casted.")

            if isinstance(arg_val, RCValue):
                arg_val.retain(self.builder, self.rc_runtime)
            args.append(arg_val)
        
        if not on:
            if field.value.is_this_member:
                assert self.inside_ptr is not None
                converted = [self.inside_ptr] + [arg.load_value(self.builder) for arg in args]
                return field.value.call_this_basic(self.builder, converted, self.rc_runtime, self.target_data)
            return field.value.call_this(self.builder, args, self.rc_runtime, self.target_data)

        try:
            return on.call(self.builder, expr.callee.raw, args, self.rc_runtime, self.target_data)
        except KeyError:
            raise compile_error(expr.callee, f"Type '{on.val_type.name}' has no member function '{expr.callee}'.")
        except ValueError:
            raise compile_error(expr.callee, f"Member '{on.val_type.name}.{expr.callee}' is not a function.")

    def gen_variable_expr(self, expr: VariableExpr, on: Value | None = None) -> Value:
        if not on:
            return get_field(self.data, expr.name).value
        try:
            return on.get(self.builder, expr.name.raw, self.rc_runtime, self.target_data)
        except KeyError:
            raise compile_error(expr.name, f"Type '{on.val_type.name}' has no member '{expr.name}'")

    def gen_accessible(self, expr: Accessible, on: Value | None = None, can_be_void=False) -> Value | VoidValue:
        if isinstance(expr, CallExpr):
            possibly_void = self.gen_function_call(expr, on)
            if isinstance(possibly_void, VoidValue) and (not can_be_void or expr.access):
                raise compile_error(expr.callee, "Function cannot return void.")
            out = possibly_void
        elif isinstance(expr, VariableExpr):
            out = self.gen_variable_expr(expr, on)
        else:
            assert False
        
        if expr.access:
            assert not isinstance(out, VoidValue)
            return self.gen_accessible(expr.access, out, can_be_void)
        return out

    def gen_binary(self, expr: BinaryExpr) -> Value:
        lhs = self.gen_expression(expr.lhs)
        rhs = self.gen_expression(expr.rhs)
        assert not isinstance(lhs, VoidValue)
        assert not isinstance(rhs, VoidValue)

        try:
            possibly_void = lhs.call(self.builder, expr.op.raw, [rhs], self.rc_runtime, self.target_data)
            assert not isinstance(possibly_void, VoidValue)
            return possibly_void
        except:
            raise compile_error(expr.op, f"Operator '{lhs.val_type.name}' {expr.op} '{rhs.val_type.name}' does not exist.")

    def gen_unary(self, expr: UnaryExpr) -> Value:
        rhs = self.gen_expression(expr.rhs)
        assert not isinstance(rhs, VoidValue)

        try:
            possibly_void = rhs.call(self.builder, expr.op.raw, [], self.rc_runtime, self.target_data)
            assert not isinstance(possibly_void, VoidValue)
            return possibly_void
        except:
            raise compile_error(expr.op, f"Operator {expr.op} '{rhs.val_type.name}' does not exist.")

    def gen_array(self, expr: ArrayExpr) -> Value:
        if len(expr.elements) == 0:
            raise compile_error(expr.array_end, "Cannot infer type of an empty array.")
        
        values: list[Value] = [self.gen_expression(expr.elements[0])] # type: ignore
        target_type = values[0].val_type
        if len(expr.elements) >= 2:
            for element in expr.elements[1:]:
                val = self.gen_expression(element)
                assert not isinstance(val, VoidValue)
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

    def gen_expression(self, expr: Expression, can_be_void=False) -> Value | VoidValue:
        if isinstance(expr, LiteralExpr):
            return self.gen_literal(expr)
        if isinstance(expr, Accessible):
            possibly_void = self.gen_accessible(expr, can_be_void=can_be_void)
            assert not (isinstance(possibly_void, VoidValue) and not can_be_void)
            return possibly_void
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

    def gen_assignment(self, stmt: AssignmentStmt) -> None:
        target = self.gen_accessible(stmt.target)
        source = self.gen_expression(stmt.value)
        assert not isinstance(target, VoidValue)
        assert not isinstance(source, VoidValue)

        if source.val_type.name != target.val_type.name:
            raise compile_error(stmt.equal_token, f"Cannot assign value of type '{source.val_type.name}' to variable of type '{target.val_type.name}'")

        if isinstance(target, RCValue):
            source.retain(self.builder, self.rc_runtime)
            target.release(self.builder, self.rc_runtime)

        target.store_value(self.builder, source.load_value(self.builder)) # TODO: This will be changed when reference semantics.

    def gen_if(self, stmt: IfStmt) -> Value | VoidValue | None:
        branching_val = self.gen_expression(stmt.condition)
        assert not isinstance(branching_val, VoidValue)

        if branching_val.val_type.name != "bool":
            raise compile_error(stmt.keyword_tok, "The condition in an if statement must evaluate to type 'bool'.")
        branching_res = self.builder.icmp_unsigned("==", branching_val.load_value(self.builder), I1(1), "branching_res")

        truthy_block = self.builder.append_basic_block("truthy")
        falsey_block = self.builder.append_basic_block("falsey")
        continued_block = self.builder.append_basic_block("continue")
        self.builder.cbranch(branching_res, truthy_block, falsey_block)

        self.builder.position_at_start(truthy_block)
        returns = self.gen_scope(stmt.body)
        if returns is None:
            self.builder.branch(continued_block)

        self.builder.position_at_start(falsey_block)
        if stmt.else_branch:
            if isinstance(stmt.else_branch, IfStmt):
                returns = self.gen_if(stmt.else_branch) if returns else None
            if isinstance(stmt.else_branch, ElseStmt):
                returns = self.gen_else(stmt.else_branch) if returns else None
        else:
            returns = None # This if statement doesn't DEFINITELY return because it doesn't have an else case.
        
        if returns is None:
            # Either branch from falsey_block to continued_block, or, if 
            # we generated an if statement, branch from ITS continued block
            # to the higher level continued block.
            self.builder.branch(continued_block)
            
            self.builder.position_at_start(continued_block)

        return returns

    def gen_else(self, stmt: ElseStmt) -> Value | VoidValue | None:
        return self.gen_scope(stmt.body)

    def gen_for(self, stmt: ForStmt) -> Value | None:
        pass
    
    def gen_while(self, stmt: WhileStmt) -> Value | VoidValue | None:
        cond_block = self.builder.append_basic_block("while_cond")
        loop_block = self.builder.append_basic_block("while_loop")
        continued_block = self.builder.append_basic_block("continue")

        self.builder.branch(cond_block)
        self.builder.position_at_start(cond_block)

        branching_val = self.gen_expression(stmt.condition)
        assert not isinstance(branching_val, VoidValue)

        if branching_val.val_type.name != "bool":
            raise compile_error(stmt.keyword_tok, "The condition in a while statement must evaluate to type 'bool'.")
        branching_res = self.builder.icmp_unsigned("==", branching_val.load_value(self.builder), I1(1), "branching_res")

        self.builder.cbranch(branching_res, loop_block, continued_block)

        self.builder.position_at_start(loop_block)
        returns = self.gen_scope(stmt.body)
        if returns is None:
            self.builder.branch(cond_block)
        else:
            compile_warning(stmt.keyword_tok, "The while block always returns, consider using an if statement instead.")
        
        self.builder.position_at_start(continued_block)
        return returns

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
            self.gen_variable(stmt)
            return
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
            out.append((name.raw, get_type(self.data, arg_type_token)))

        return out

    def gen_args(self, function: ir.Function, types: dict[str, Type]) -> dict[str, Value]:
        out: dict[str, Value] = {}

        for arg_name, arg_type in types.items():
            out[arg_name] = Value(self.builder, arg_type, ir.Argument(function, arg_type.llvm_type), f"{function.name}_arg_{arg_name}")

        return out
    
    def gen_variable(self, generate: VarDecl) -> Field:
        var_name = generate.type_name[1]
        var_type = get_type(self.data, generate.type_name[0])
        expr_value = self.gen_expression(generate.value)
        assert not isinstance(expr_value, VoidValue)

        if var_type.castable_from(expr_value.val_type):
            compile_warning(var_name, f"Expression will be casted from '{expr_value.val_type.name} to '{var_type.name}', meaning a copy of the variable will be created.")
            expr_value = var_type.generate_from(self.builder, expr_value, self.rc_runtime, self.c_runtime, self.target_data)
        
        if expr_value.val_type.name != var_type.name:
            raise compile_error(generate.type_name[0], f"Cannot assign '{expr_value.val_type.name}' to '{var_type.name}'")
    
        if var_type.needs_refcount:
            hl_value = RCValue(self.builder, var_type, expr_value.value_ptr, self.rc_runtime, self.target_data, var_name.raw)
        else:
            hl_value = expr_value
        field = ValueField(var_type, hl_value, generate.flags)
        
        add_field(self.data, var_name, field)

        return field
    
    # TODO: Static functions don't do a lot of this shit
    def gen_function_header(self, generate: Function, inside: UserType | None = None) -> ValueField:
        arg_types = self.gen_arg_types(generate.args)
        type_list = ([cast(UserType, inside)] if inside else []) + [arg_type for _, arg_type in arg_types]
        return_type = get_type(self.data, generate.returns) if generate.returns else VoidType(self.module)
        args: list[ir.Type] = []
        for arg in type_list:
            args.append(arg.llvm_type.as_pointer() if arg.needs_refcount else arg.llvm_type)
        ir_function_ty = ir.FunctionType(return_type.llvm_type, args)
        function_value = ir.Function(self.module, ir_function_ty, f"{self.path}__{generate.name.raw}")
        
        function_type = FunctionType( self.module, generate.name.raw, type_list, return_type, function_value)
        function_field = ValueField(function_type, FunctionValue(self.builder, function_type, function_value), generate.member_flags | generate.function_flags)
        add_field(self.data, generate.name, function_field)

        return function_field

    def gen_function_definition(self, generate: Function, function_value: ir.Function, inside: UserType | None = None) -> None:
        arg_types = self.gen_arg_types(generate.args)
        return_type = get_type(self.data, generate.returns) if generate.returns else VoidType(self.module)

        block = function_value.append_basic_block("entry")
        self.builder_stack.append(ir.IRBuilder(block))
        self.scoped_variables.append({})

        # Add class members to scope.
        self.inside_ptr = None
        if inside:
            self.inside_ptr = function_value.args[0] # type: ignore
            for name, ind in inside.field_indices.items():
                member_addr = self.builder.gep(self.inside_ptr, [I32(0), I32(ind)], name=f"{name}")
                hl_field = inside.field_names[name]
                if hl_field.val_type.needs_refcount:
                    value = RCValue(self.builder, hl_field.val_type, member_addr, self.rc_runtime, self.target_data, f"{inside.name}_member_{name}", allocate=False)
                elif isinstance(hl_field.val_type, FunctionType):
                    value = FunctionValue(self.builder, hl_field.val_type, hl_field.val_type.function, is_this_member=True)
                else:
                    value = Value(self.builder, hl_field.val_type, member_addr, f"{inside.name}_member_{name}", allocate=False)
                self.scope[name] = ValueField(hl_field.val_type, value, hl_field.flags)

        # Add arguments to scope.
        if not inside or len(function_value.args) > 1:
            for i, arg in enumerate(function_value.args if not inside else function_value.args[1:]):
                self.scope[arg_types[i][0]] = ValueField(arg_types[i][1], Value(self.builder, arg_types[i][1], arg, f"arg_{arg.name}"))

        for stmt in generate.body:
            possible_ret = self.gen_statement(stmt)
            if not possible_ret is None:
                if possible_ret is VoidValue and not generate.returns is None:
                    raise compile_error(generate.name, f"Function does not always return type '{generate.returns.raw}'")
                elif generate.returns is None and not possible_ret is VoidValue:
                    raise compile_error(generate.name, f"Function has no return type, but has a line that returns non-void.")
                elif isinstance(possible_ret, Value) and not generate.returns is None and possible_ret.val_type.name != return_type.name:
                    raise compile_error(generate.name, f"Function does not always return type '{generate.returns.raw}' but instead type '{possible_ret.val_type.name}'")
                break
        
        if not self.builder.block.is_terminated: # type: ignore
            self.pop_scope()
            self.builder.ret_void()
        else:
            self.scoped_variables.pop() # RC will already be handled by return statement or above.
        self.builder_stack.pop()
    
    def gen_class(self, generate: Class) -> UserType:
        out = UserType(self.module, generate.name.raw, self.rc_runtime)

        # This class' scope.
        self.scoped_variables.append({})
        self.data.path_array.append(generate.name.raw)

        arg_types = self.gen_arg_types(generate.args)
        type_list = [arg_type for _, arg_type in arg_types]
        initializer_ir_type = ir.FunctionType(out.llvm_type.as_pointer(), [arg_type.llvm_type for arg_type in type_list])
        initializer_value = ir.Function(self.module, initializer_ir_type, f"{self.path}__init")
        initializer_type = FunctionType(self.module, generate.name.raw, type_list, out, initializer_value)
        initializer_field = ValueField(initializer_type, FunctionValue(self.builder, initializer_type, initializer_value), {MemberFlag.STATIC})

        block = initializer_value.append_basic_block("entry")
        self.builder_stack.append(ir.IRBuilder(block))
        
        size = get_sizeof(self.builder, out.llvm_type)
        raw_ptr = self.builder.call(self.rc_runtime.rc_alloc_func, [size], "raw_ptr")
        this_ptr = self.builder.bitcast(raw_ptr, out.llvm_type.as_pointer(), "this_ptr")

        member_index = 0
        for index, arg in enumerate(initializer_value.args):
            zero = ir.Constant(I32, 0)
            idx = ir.Constant(I32, index)

            field_pointer = self.builder.gep(this_ptr, [zero, idx], name=f"ptr_field_{idx}")
            self.builder.store(arg, field_pointer)

            type_name = generate.args[index]
            arg_type = get_type(self.data, type_name[0])
            add_field(self.data, type_name[1], ValueField(arg_type, Value(self.builder, arg_type, arg, f"member_{arg.name}")))
            member_index += 1
        
        for member in generate.members:
            if isinstance(member, Class):
                # TODO: Inner classes
                continue
            if isinstance(member, Function):
                self.gen_function_header(member, out)
            if isinstance(member, VarDecl):
                self.gen_variable(member)

            member_index += 1

        class_scope = self.scoped_variables[-1]
        for name, field in class_scope.items():
            out.add_field(name, field)
        if len(class_scope.items()) == 0:
            out.add_field("dummy_value", Field(BoolType(self.module), {}))
        out.finalize()

        init_field = out.get_field("init") if out.has_field("init") else None
        if init_field and isinstance(init_field, ValueField) and isinstance(init_field.value, FunctionValue):
            init_func = cast(FunctionValue, init_field.value)
            # TODO: Check that the init function doesn't return and doesn't have any args.
            init_func.call_this(self.builder, [], self.rc_runtime, self.target_data)
        
        # In the initializer, copy all initialized values into the object.
        for name, field in class_scope.items():
            index = out.field_indices[name]
            generated_member = field.value.load_value(self.builder) if not isinstance(field.value, FunctionValue) else field.value.function
            loaded = self.builder.gep(this_ptr, [I32(0), I32(index)], name="loaded")
            actual_member_ptr = self.builder.bitcast(loaded, field.val_type.llvm_type.as_pointer(), "actual_member_ptr") # Might be an unnecessary bitcast?
            self.builder.store(generated_member, actual_member_ptr)

        self.pop_scope()
        self.builder.ret(this_ptr)
        self.builder_stack.pop()
        self.data.path_array.pop()
        
        for member in generate.members:
            if isinstance(member, (Class, VarDecl)):
                continue
            func = class_scope[member.name.raw]
            assert isinstance(func.value, FunctionValue)
            self.gen_function_definition(member, func.value.function, out)

        self.type_db[out.name] = out
        add_field(self.data, generate.name, initializer_field)

        return out
    
    def gen_program(self, generate: Program, out_directory: str):
        for import_stmt in generate.imports:
            pass

        for stmt in generate.statements:
            if isinstance(stmt, Class):
                self.gen_class(stmt)
            elif isinstance(stmt, Function):
                self.gen_function_header(stmt)
                field = get_field(self.data, stmt.name)
                assert isinstance(field.value, FunctionValue)
                self.gen_function_definition(stmt, field.value.function)
            elif isinstance(stmt, VarDecl):
                self.gen_variable(stmt)
            
        try:
            main_func = get_field(self.data, Token.make_external("main"))
        except RuntimeError:
            print("ERROR: Cannot compile program without a 'main' function.")
            raise RuntimeError()
        
        if not isinstance(main_func.value, FunctionValue):
            print("ERROR: Main entrypoint must be a function.")
            raise RuntimeError()
        
        main_func.value.call_this(self.builder, [], self.rc_runtime, self.target_data)
        
        self.builder.ret(I32(0))

        makedirs(out_directory, exist_ok=True)

        with open(f"{out_directory}/llvm_ir.txt", "w") as ir_file:
            ir_file.write(self.module.__str__())

        print("Finished compiling LLVM IR!")

        mod = llvm.parse_assembly(self.module.__str__())
        mod.verify()

        obj_bytes = self.data.target_machine.emit_object(mod)
        with open(f"{out_directory}/out.o", "wb") as object_file:
            object_file.write(obj_bytes)
        
        print("Object file created. Running GCC ...")
        
        os.system(f"gcc -o {out_directory}/program {out_directory}/out.o")

        print("Done!")

        # TODO: Actually compile the module.
