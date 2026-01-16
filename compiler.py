from __future__ import annotations
from typing import cast
from ast_classes import (
    Accessible,
    AssignmentStmt,
    BinaryExpr,
    CallExpr,
    ElseStmt,
    Expression,
    Grouping,
    IfStmt,
    LiteralType,
    LiteralExpr,
    Program,
    Statement,
    UnaryExpr,
    VariableExpr,
    VarDecl,
)
import llvmlite.ir as ir
from scanner import Token
from errors import compile_error
from builtin_types import (
    INT_TYPE,
    FLOAT_TYPE,
    CHAR_TYPE,
    TRUE_VAL,
    FALSE_VAL,
    CB_INT,
    CB_FLOAT,
    CB_CHAR,
    CB_BOOL,
    CBType,
    CBValue,
    StringType,
    Member,
    FunctionMember,
    VariableMember,
)


class Compiler:
    def __init__(self, program: Program) -> None:
        self.program = program
        self.global_members: dict[str, Member] = {}
        self.module = ir.Module()
        self._builder: ir.IRBuilder | None = None

    @property
    def builder(self) -> ir.IRBuilder:
        """
        Returns the current IRBuilder. Raises if compile() hasn't been called.

        :return: The current IRBuilder.
        :rtype: ir.IRBuilder
        :raises RuntimeError: If called before compile().
        """
        if self._builder is None:
            raise RuntimeError(
                "Compiler.compile() must be called before accessing builder"
            )
        return self._builder

    def generate_code(self) -> ir.Module:
        """
        Main entry point for code generation.

        :return: The compiled LLVM module.
        :rtype: ir.Module
        """
        # Create main function
        main_type = ir.FunctionType(ir.VoidType(), [])
        main_func = ir.Function(self.module, main_type, "main")
        entry_block = main_func.append_basic_block("entry")
        self._builder = ir.IRBuilder(entry_block)

        # Process top-level statements
        for stmt in self.program.statements:
            self.gen_stmt(stmt)

        # Terminate main
        self._builder.ret_void()

        return self.module

    def gen_expr(self, expr: Expression) -> CBValue | None:
        """
        Switch that calls other functions based on the subtype of
        the expression.

        :param expr: The expression to evaluate, must be of a subtype.
        :type expr: Expression
        :return: The evaluated type joined with the llvmlite Value.
        :rtype: CBValue | None
        """

        if isinstance(expr, LiteralExpr):
            return self.gen_literal(expr)
        elif isinstance(expr, BinaryExpr):
            return self.gen_binary_expr(expr)
        elif isinstance(expr, UnaryExpr):
            return self.gen_unary_expr(expr)
        elif isinstance(expr, Grouping):
            return self.gen_expr(expr.expr)
        elif isinstance(expr, Accessible):
            return self.gen_accessible(expr)
        return None

    def gen_stmt(self, stmt: Statement) -> None:
        """
        Switch that calls other functions based on the subtype of
        the statement.

        :param stmt: The statement to compile, must be of a subtype.
        :type stmt: Statement
        """

        if isinstance(stmt, Expression):
            self.gen_expression_stmt(stmt)
        elif isinstance(stmt, IfStmt):
            self.gen_if_stmt(stmt)
        elif isinstance(stmt, ElseStmt):
            self.gen_else_stmt(stmt)
        elif isinstance(stmt, VarDecl):
            self.gen_var_decl(stmt)
        elif isinstance(stmt, AssignmentStmt):
            self.gen_assignment_stmt(stmt)
        else:
            # For now, ignore unimplemented statement types
            pass

    def gen_binary_expr(self, expr: BinaryExpr) -> CBValue | None:
        """
        Binary expressions, like adding and comparison.

        :param expr: For example '1 + 1' or 'true == false'
        :type expr: BinaryExpr
        :return: Generates the evaluated type.
        :rtype: CBValue | None
        """

        lhs = self.gen_expr(expr.lhs)
        rhs = self.gen_expr(expr.rhs)

        if not lhs or not rhs:
            return None

        if not lhs.type.is_compatible_with(rhs.type):
            raise compile_error(
                expr.op,
                f"Type mismatch: cannot apply '{expr.op.raw}' to '{lhs.type.name}' and '{rhs.type.name}'.",
            )

        if not lhs.type.supports_operator(expr.op.raw):
            raise compile_error(
                expr.op,
                f"Operator '{expr.op.raw}' not supported by type '{lhs.type.name}'.",
            )

        return lhs.type.apply_operator(self.builder, lhs, expr.op, rhs)

    def gen_unary_expr(self, expr: UnaryExpr) -> CBValue | None:
        """
        Unary expressions, aka operator expression.

        :param expr: For example, '!true' or '!(1 + 1 == 2)'
        :type expr: UnaryExpr
        :return: Generates the evaluated type.
        :rtype: CBValue | None
        """

        operand = self.gen_expr(expr.rhs)
        if not operand:
            return None

        if not operand.type.supports_unary_operator(expr.op.raw):
            raise compile_error(
                expr.op,
                f"Unary operator '{expr.op.raw}' not supported by type '{operand.type.name}'.",
            )

        return operand.type.apply_unary_operator(self.builder, operand, expr.op)

    def gen_accessible(
        self, expr: Accessible, context: CBType | None = None
    ) -> CBValue | None:
        """
        Generate return type after processing accessible.

        :param expr: The whole expression.
        :type expr: Accessible
        :return: The type
        :rtype: CBValue | None
        """

        this_out: CBValue | None = None
        if isinstance(expr, CallExpr):
            this_out = self.gen_call_expr(expr, context)
            if not this_out:
                raise compile_error(expr.callee, "Function must evaluate to something.")
        elif isinstance(expr, VariableExpr):
            this_out = self.gen_variable_expr(expr, context)

        if not this_out:  # Should never happen, just to make the type checker happy.
            return

        if expr.access:
            return self.gen_accessible(expr.access, this_out.type)

        return this_out

    def gen_call_expr(
        self, expr: CallExpr, context: CBType | None = None
    ) -> CBValue | None:
        """
        Evaluates the validity of calling a function.

        :param expr: For example, 'func(a, b)'
        :type expr: CallExpr
        :return: The returned value of the function, or None if the function doesn't return.
        :rtype: CBValue | None
        """

        callee_name = expr.callee.raw
        member = (
            context.get_member(callee_name)
            if context
            else self.global_members.get(callee_name)
        )
        if not member:
            raise compile_error(expr.callee, f"Unknown function '{callee_name}'.")

        if not isinstance(member, FunctionMember):
            raise compile_error(expr.callee, f"'{callee_name}' is not a function.")

        if len(member.param_types) != len(expr.args):
            raise compile_error(
                expr.callee,
                f"Function '{callee_name}' expects {len(member.param_types)} arguments, got {len(expr.args)}.",
            )

        args: list[ir.Value] = []
        for i, (arg_expr, expected_type) in enumerate(
            zip(expr.args, member.param_types)
        ):
            arg_val = self.gen_expr(arg_expr)
            if arg_val is None:
                raise compile_error(
                    expr.callee, f"Argument {i + 1} to '{callee_name}' cannot be void."
                )

            if not arg_val.type.is_compatible_with(expected_type):
                raise compile_error(
                    expr.callee,
                    f"Argument {i + 1} to '{callee_name}' expected '{expected_type.name.raw}', got '{arg_val.type.name.raw}'.",
                )

            args.append(arg_val.value)

        result = self.builder.call(member.llvm_func, args)

        if not member.return_type:
            return None

        return CBValue(result, member.return_type)

    def gen_expression_stmt(self, expr: Expression) -> None:
        """
        Compiles an expression as a statement. The result value is discarded.

        :param expr: The expression to compile as a statement.
        :type expr: Expression
        """
        result = self.gen_expr(expr)
        # For expression statements, we discard the result
        # This handles function calls, arithmetic expressions, etc.

    def gen_if_stmt(self, stmt: IfStmt) -> None:
        """
        Compiles an if statement with optional elif/else branches.

        :param stmt: The if statement to compile.
        :type stmt: IfStmt
        """
        # Evaluate the condition
        condition_val = self.gen_expr(stmt.condition)
        if not condition_val:
            # Create a dummy token for error reporting
            dummy_token = Token("condition", 0)  # type: ignore
            raise compile_error(dummy_token, "If condition cannot be void")

        # Convert condition to boolean (i1)
        bool_condition = self.convert_to_bool(condition_val)

        # Create basic blocks
        if_block = self.builder.append_basic_block("if_true")
        else_block = self.builder.append_basic_block("if_false")
        end_block = self.builder.append_basic_block("if_end")

        # Conditional branch
        self.builder.cbranch(bool_condition, if_block, else_block)

        # Generate if body
        self.builder.position_at_end(if_block)
        self.gen_scope_expr(stmt.body)
        self.builder.branch(end_block)

        # Generate else/elif body
        self.builder.position_at_end(else_block)
        if stmt.else_branch:
            if isinstance(stmt.else_branch, IfStmt):
                # Elif - recursively handle as nested if
                self.gen_if_stmt(stmt.else_branch)
            elif isinstance(stmt.else_branch, ElseStmt):
                # Else statement
                self.gen_else_stmt(stmt.else_branch)
            self.builder.branch(end_block)
        else:
            # No else branch - just branch to end
            self.builder.branch(end_block)

        # Position builder at end block
        self.builder.position_at_end(end_block)

    def gen_else_stmt(self, stmt: ElseStmt) -> None:
        """
        Compiles an else statement body.

        :param stmt: The else statement to compile.
        :type stmt: ElseStmt
        """
        self.gen_scope_expr(stmt.body)

    def gen_scope_expr(self, scope_expr) -> None:
        """
        Compiles a scope expression (body of if/else statements).

        :param scope_expr: The scope expression to compile.
        """
        # ScopeExpr contains statements - compile each one
        for stmt in scope_expr.statements:
            self.gen_stmt(stmt)

    def convert_to_bool(self, value: CBValue) -> ir.Value:
        """
        Converts any value to a boolean (i1) for condition testing.

        :param value: The value to convert.
        :type value: CBValue
        :return: Boolean value (i1).
        :rtype: ir.Value
        """
        if value.type == CB_BOOL:
            return value.value
        elif value.type == CB_INT:
            return self.builder.icmp_signed("!=", value.value, ir.Constant(INT_TYPE, 0))
        elif value.type == CB_FLOAT:
            return self.builder.fcmp_unordered(
                "!=", value.value, ir.Constant(FLOAT_TYPE, 0.0)
            )
        elif value.type == CB_CHAR:
            return self.builder.icmp_signed(
                "!=", value.value, ir.Constant(CHAR_TYPE, 0)
            )
        else:
            # For other types, compare with null/zero as appropriate
            llvm_type = value.type.llvm_type  # Get the LLVM type from CBType
            return self.builder.icmp_signed(
                "!=", value.value, ir.Constant(llvm_type, 0)
            )

    def gen_var_decl(self, stmt: VarDecl) -> None:
        """
        Compiles a variable declaration statement.

        :param stmt: The variable declaration to compile.
        :type stmt: VarDecl
        """
        # For now, skip variable declarations - this is a placeholder
        # TODO: Implement proper variable storage and initialization
        pass

    def gen_assignment_stmt(self, stmt: AssignmentStmt) -> None:
        """
        Compiles an assignment statement.

        :param stmt: The assignment statement to compile.
        :type stmt: AssignmentStmt
        """
        # For now, skip assignments - this is a placeholder
        # TODO: Implement proper assignment to variables
        pass

    def gen_variable_expr(self, expr: VariableExpr, context: CBType | None) -> CBValue:
        """
        Evaluates a variable.

        :param expr: Contains the variable name.
        :type expr: VariableExpr
        :return: The type of the variable.
        :rtype: CBValue | None
        """

        member = (
            context.get_member(expr.name.raw)
            if context
            else self.global_members.get(expr.name.raw)
        )
        if not member:
            raise compile_error(expr.name, "Unknown variable name.")

        if not isinstance(member, VariableMember):
            raise compile_error(expr.name, f"'{expr.name.raw}' is not a variable.")

        return member.value

    def register_function(
        self,
        name: Token,
        llvm_func: ir.Function,
        param_types: list[CBType],
        return_type: CBType | None,
    ) -> FunctionMember:
        """
        Registers a global (module) function.

        :param name: Name of the function.
        :type name: Token
        :param llvm_func: The generated LLVM function.
        :type llvm_func: ir.Function
        :param param_types: Types of all the parameters that are passed in.
        :type param_types: list[CBType]
        :param return_type: Type the function returns, can be None if the function doesn't return anything.
        :type return_type: CBType | None
        :return: The member generated, which is also inside `global_members` by key `name.raw`.
        :rtype: FunctionMember
        """

        func_member = FunctionMember(name, llvm_func, param_types, return_type)
        self.global_members[name.raw] = func_member
        return func_member

    def gen_literal(self, literal: LiteralExpr) -> CBValue:
        """
        Generates a typed value from a literal AST node.

        :param literal: The AST node.
        :type literal: LiteralExpr
        :return: The typed value.
        :rtype: CBValue
        """

        if literal.ltype == LiteralType.INT:
            return CBValue(ir.Constant(INT_TYPE, literal.val), CB_INT)
        if literal.ltype == LiteralType.FLOAT:
            return CBValue(ir.Constant(FLOAT_TYPE, literal.val), CB_FLOAT)
        if literal.ltype == LiteralType.CHAR:
            char_val = bytearray(cast(str, literal.val).encode("utf8"))[0]
            return CBValue(ir.Constant(CHAR_TYPE, char_val), CB_CHAR)
        if literal.ltype == LiteralType.STRING:
            str_val = cast(str, literal.val)
            llvm_val = self.make_byte_string(str_val)
            return CBValue(
                llvm_val, StringType(len(str_val) + 1)
            )  # +1 for null terminator
        # LiteralType.BOOL
        bool_val = TRUE_VAL if literal.val else FALSE_VAL
        return CBValue(bool_val, CB_BOOL)

    @staticmethod
    def make_byte_string(val: str) -> ir.Constant:
        """
        Generates an llvmlite constant from a string.

        :param val: String value
        :type val: str
        :return: Constant
        :rtype: Constant
        """

        str_bytes = bytearray(val.encode("utf8"))
        if not str_bytes.endswith(b"\0"):
            str_bytes += b"\0"

        str_type = ir.ArrayType(CHAR_TYPE, len(str_bytes))
        return ir.Constant(str_type, str_bytes)
