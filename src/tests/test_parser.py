# type: ignore

from __future__ import annotations
import sys
import unittest
from pathlib import Path

# Add parent directory to path so we can import parser
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from scanner import Scanner, Token, TokenType
from parser import Parser, ParseException
from ast_classes import (
    ArrayExpr,
    AssignmentStmt,
    BinaryExpr,
    CallExpr,
    Class,
    ElseStmt,
    Expression,
    ForStmt,
    Function,
    FunctionFlag,
    Grouping,
    IfStmt,
    Import,
    LiteralExpr,
    LiteralType,
    MemberFlag,
    Program,
    ReturnStmt,
    ScopeStmt,
    Statement,
    UnaryExpr,
    VarDecl,
    VariableExpr,
    WhileStmt,
)


def tokenize(source: str) -> list[Token]:
    """
    Helper function to tokenize source code.

    :param source: The source code string to tokenize.
    :type source: str
    :return: List of tokens produced by the scanner.
    :rtype: list[Token]
    """
    scanner = Scanner(source)
    return scanner.scan_source()


def parse(source: str) -> Program:
    """
    Helper function to tokenize and parse source code into a Program AST.

    :param source: The source code string to parse.
    :type source: str
    :return: The parsed Program AST.
    :rtype: Program
    """
    tokens = tokenize(source)
    parser = Parser(tokens)
    return parser.parse()


def parse_expression(source: str) -> Expression:
    """
    Parse a single expression (will be wrapped as expression statement).

    :param source: The expression source code (without semicolon).
    :type source: str
    :return: The parsed expression.
    :rtype: Expression
    """
    program = parse(source + ";")
    assert len(program.statements) == 1
    stmt = program.statements[0]
    assert isinstance(stmt, Expression)
    return stmt


def parse_statement(source: str) -> Statement:
    """
    Parse a single statement.

    :param source: The statement source code.
    :type source: str
    :return: The parsed statement.
    :rtype: Statement
    """
    program = parse(source)
    assert len(program.statements) == 1
    return program.statements[0]


# ========== LITERAL EXPRESSIONS ==========
class TestLiteralExpressions(unittest.TestCase):
    """Test parsing of literal expressions."""

    def test_integer_literal(self):
        expr = parse_expression("42")
        self.assertIsInstance(expr, LiteralExpr)
        self.assertEqual(expr.ltype, LiteralType.INT)
        self.assertEqual(expr.val, 42)

    def test_integer_zero(self):
        expr = parse_expression("0")
        self.assertIsInstance(expr, LiteralExpr)
        self.assertEqual(expr.ltype, LiteralType.INT)
        self.assertEqual(expr.val, 0)

    def test_large_integer(self):
        expr = parse_expression("9999999999")
        self.assertIsInstance(expr, LiteralExpr)
        self.assertEqual(expr.ltype, LiteralType.INT)
        self.assertEqual(expr.val, 9999999999)

    def test_float_literal(self):
        expr = parse_expression("3.14")
        self.assertIsInstance(expr, LiteralExpr)
        self.assertEqual(expr.ltype, LiteralType.FLOAT)
        self.assertAlmostEqual(expr.val, 3.14)

    def test_float_zero(self):
        expr = parse_expression("0.0")
        self.assertIsInstance(expr, LiteralExpr)
        self.assertEqual(expr.ltype, LiteralType.FLOAT)
        self.assertEqual(expr.val, 0.0)

    def test_float_small_decimal(self):
        expr = parse_expression("0.5")
        self.assertIsInstance(expr, LiteralExpr)
        self.assertEqual(expr.ltype, LiteralType.FLOAT)
        self.assertAlmostEqual(expr.val, 0.5)

    def test_string_literal(self):
        expr = parse_expression('"hello"')
        self.assertIsInstance(expr, LiteralExpr)
        self.assertEqual(expr.ltype, LiteralType.STRING)
        self.assertEqual(expr.val, "hello")

    def test_empty_string(self):
        expr = parse_expression('""')
        self.assertIsInstance(expr, LiteralExpr)
        self.assertEqual(expr.ltype, LiteralType.STRING)
        self.assertEqual(expr.val, "")

    def test_string_with_spaces(self):
        expr = parse_expression('"hello world"')
        self.assertIsInstance(expr, LiteralExpr)
        self.assertEqual(expr.ltype, LiteralType.STRING)
        self.assertEqual(expr.val, "hello world")

    def test_character_literal(self):
        expr = parse_expression("'a'")
        self.assertIsInstance(expr, LiteralExpr)
        self.assertEqual(expr.ltype, LiteralType.CHAR)
        self.assertEqual(expr.val, "a")

    def test_true_literal(self):
        expr = parse_expression("true")
        self.assertIsInstance(expr, LiteralExpr)
        self.assertEqual(expr.ltype, LiteralType.BOOL)
        self.assertEqual(expr.val, True)

    def test_false_literal(self):
        expr = parse_expression("false")
        self.assertIsInstance(expr, LiteralExpr)
        self.assertEqual(expr.ltype, LiteralType.BOOL)
        self.assertEqual(expr.val, False)

    def test_literal_token_preserved(self):
        expr = parse_expression("42")
        self.assertIsInstance(expr, LiteralExpr)
        self.assertIsNotNone(expr.token)
        self.assertEqual(expr.token.raw, "42")


# ========== BINARY EXPRESSIONS ==========
class TestBinaryExpressions(unittest.TestCase):
    """Test parsing of binary expressions."""

    # Arithmetic operators
    def test_addition(self):
        expr = parse_expression("1 + 2")
        self.assertIsInstance(expr, BinaryExpr)
        self.assertEqual(expr.op.ttype, TokenType.PLUS)
        self.assertIsInstance(expr.lhs, LiteralExpr)
        self.assertIsInstance(expr.rhs, LiteralExpr)

    def test_subtraction(self):
        expr = parse_expression("5 - 3")
        self.assertIsInstance(expr, BinaryExpr)
        self.assertEqual(expr.op.ttype, TokenType.MINUS)

    def test_multiplication(self):
        expr = parse_expression("4 * 2")
        self.assertIsInstance(expr, BinaryExpr)
        self.assertEqual(expr.op.ttype, TokenType.STAR)

    def test_division(self):
        expr = parse_expression("10 / 2")
        self.assertIsInstance(expr, BinaryExpr)
        self.assertEqual(expr.op.ttype, TokenType.SLASH)

    # Comparison operators
    def test_greater_than(self):
        expr = parse_expression("5 > 3")
        self.assertIsInstance(expr, BinaryExpr)
        self.assertEqual(expr.op.ttype, TokenType.RIGHT_ANGLE)

    def test_less_than(self):
        expr = parse_expression("3 < 5")
        self.assertIsInstance(expr, BinaryExpr)
        self.assertEqual(expr.op.ttype, TokenType.LEFT_ANGLE)

    def test_greater_equal(self):
        expr = parse_expression("5 >= 3")
        self.assertIsInstance(expr, BinaryExpr)
        self.assertEqual(expr.op.ttype, TokenType.GREATER_EQUAL)

    def test_less_equal(self):
        expr = parse_expression("3 <= 5")
        self.assertIsInstance(expr, BinaryExpr)
        self.assertEqual(expr.op.ttype, TokenType.LESS_EQUAL)

    # Equality operators
    def test_equal_equal(self):
        expr = parse_expression("1 == 1")
        self.assertIsInstance(expr, BinaryExpr)
        self.assertEqual(expr.op.ttype, TokenType.EQUAL_EQUAL)

    def test_not_equal(self):
        expr = parse_expression("1 != 2")
        self.assertIsInstance(expr, BinaryExpr)
        self.assertEqual(expr.op.ttype, TokenType.BANG_EQUAL)

    # Logical operators
    def test_logical_and(self):
        expr = parse_expression("true && false")
        self.assertIsInstance(expr, BinaryExpr)
        self.assertEqual(expr.op.ttype, TokenType.AND_AND)

    def test_logical_or(self):
        expr = parse_expression("true || false")
        self.assertIsInstance(expr, BinaryExpr)
        self.assertEqual(expr.op.ttype, TokenType.PIPE_PIPE)

    # Chained expressions (left-to-right associativity)
    def test_chained_addition(self):
        # 1 + 2 + 3 should be (1 + 2) + 3
        expr = parse_expression("1 + 2 + 3")
        self.assertIsInstance(expr, BinaryExpr)
        self.assertEqual(expr.op.ttype, TokenType.PLUS)
        self.assertIsInstance(expr.lhs, BinaryExpr)  # (1 + 2)
        self.assertIsInstance(expr.rhs, LiteralExpr)  # 3

    def test_chained_subtraction(self):
        # 5 - 3 - 1 should be (5 - 3) - 1
        expr = parse_expression("5 - 3 - 1")
        self.assertIsInstance(expr, BinaryExpr)
        self.assertIsInstance(expr.lhs, BinaryExpr)

    def test_chained_multiplication(self):
        expr = parse_expression("2 * 3 * 4")
        self.assertIsInstance(expr, BinaryExpr)
        self.assertIsInstance(expr.lhs, BinaryExpr)

    def test_chained_comparison(self):
        # 1 < 2 < 3 should be (1 < 2) < 3
        expr = parse_expression("1 < 2 < 3")
        self.assertIsInstance(expr, BinaryExpr)
        self.assertIsInstance(expr.lhs, BinaryExpr)

    def test_chained_logical_and(self):
        expr = parse_expression("a && b && c")
        self.assertIsInstance(expr, BinaryExpr)
        self.assertIsInstance(expr.lhs, BinaryExpr)

    def test_chained_logical_or(self):
        expr = parse_expression("a || b || c")
        self.assertIsInstance(expr, BinaryExpr)
        self.assertIsInstance(expr.lhs, BinaryExpr)


# ========== OPERATOR PRECEDENCE ==========
class TestOperatorPrecedence(unittest.TestCase):
    """Test that operator precedence is handled correctly."""

    def test_multiply_before_add(self):
        # 1 + 2 * 3 should be 1 + (2 * 3)
        expr = parse_expression("1 + 2 * 3")
        self.assertIsInstance(expr, BinaryExpr)
        self.assertEqual(expr.op.ttype, TokenType.PLUS)
        self.assertIsInstance(expr.lhs, LiteralExpr)
        self.assertIsInstance(expr.rhs, BinaryExpr)
        self.assertEqual(expr.rhs.op.ttype, TokenType.STAR)

    def test_divide_before_subtract(self):
        # 6 - 4 / 2 should be 6 - (4 / 2)
        expr = parse_expression("6 - 4 / 2")
        self.assertIsInstance(expr, BinaryExpr)
        self.assertEqual(expr.op.ttype, TokenType.MINUS)
        self.assertIsInstance(expr.rhs, BinaryExpr)
        self.assertEqual(expr.rhs.op.ttype, TokenType.SLASH)

    def test_comparison_before_equality(self):
        # 1 == 2 < 3 should be 1 == (2 < 3)
        expr = parse_expression("1 == 2 < 3")
        self.assertIsInstance(expr, BinaryExpr)
        self.assertEqual(expr.op.ttype, TokenType.EQUAL_EQUAL)
        self.assertIsInstance(expr.rhs, BinaryExpr)
        self.assertEqual(expr.rhs.op.ttype, TokenType.LEFT_ANGLE)

    def test_equality_before_and(self):
        # true && 1 == 2 should be true && (1 == 2)
        expr = parse_expression("true && 1 == 2")
        self.assertIsInstance(expr, BinaryExpr)
        self.assertEqual(expr.op.ttype, TokenType.AND_AND)
        self.assertIsInstance(expr.rhs, BinaryExpr)
        self.assertEqual(expr.rhs.op.ttype, TokenType.EQUAL_EQUAL)

    def test_and_before_or(self):
        # a || b && c should be a || (b && c)
        expr = parse_expression("a || b && c")
        self.assertIsInstance(expr, BinaryExpr)
        self.assertEqual(expr.op.ttype, TokenType.PIPE_PIPE)
        self.assertIsInstance(expr.rhs, BinaryExpr)
        self.assertEqual(expr.rhs.op.ttype, TokenType.AND_AND)

    def test_complex_precedence(self):
        # 1 + 2 * 3 - 4 / 2 should be ((1 + (2 * 3)) - (4 / 2))
        expr = parse_expression("1 + 2 * 3 - 4 / 2")
        self.assertIsInstance(expr, BinaryExpr)
        self.assertEqual(expr.op.ttype, TokenType.MINUS)

    def test_full_precedence_chain(self):
        # a || b && c == d < e + f * g
        # should be a || (b && (c == (d < (e + (f * g)))))
        expr = parse_expression("a || b && c == d < e + f * g")
        self.assertIsInstance(expr, BinaryExpr)
        self.assertEqual(expr.op.ttype, TokenType.PIPE_PIPE)


# ========== UNARY EXPRESSIONS ==========
class TestUnaryExpressions(unittest.TestCase):
    """Test parsing of unary expressions."""

    def test_negation(self):
        expr = parse_expression("-5")
        self.assertIsInstance(expr, UnaryExpr)
        self.assertEqual(expr.op.ttype, TokenType.MINUS)
        self.assertIsInstance(expr.rhs, LiteralExpr)

    def test_logical_not(self):
        expr = parse_expression("!true")
        self.assertIsInstance(expr, UnaryExpr)
        self.assertEqual(expr.op.ttype, TokenType.BANG)
        self.assertIsInstance(expr.rhs, LiteralExpr)

    def test_double_negation(self):
        expr = parse_expression("--5")
        self.assertIsInstance(expr, UnaryExpr)
        self.assertEqual(expr.op.ttype, TokenType.MINUS)
        self.assertIsInstance(expr.rhs, UnaryExpr)
        self.assertEqual(expr.rhs.op.ttype, TokenType.MINUS)

    def test_double_not(self):
        expr = parse_expression("!!false")
        self.assertIsInstance(expr, UnaryExpr)
        self.assertEqual(expr.op.ttype, TokenType.BANG)
        self.assertIsInstance(expr.rhs, UnaryExpr)

    def test_negation_of_variable(self):
        expr = parse_expression("-x")
        self.assertIsInstance(expr, UnaryExpr)
        self.assertIsInstance(expr.rhs, VariableExpr)

    def test_not_of_expression(self):
        expr = parse_expression("!(a && b)")
        self.assertIsInstance(expr, UnaryExpr)
        self.assertEqual(expr.op.ttype, TokenType.BANG)
        self.assertIsInstance(expr.rhs, Grouping)

    def test_unary_in_binary(self):
        # -1 + 2
        expr = parse_expression("-1 + 2")
        self.assertIsInstance(expr, BinaryExpr)
        self.assertIsInstance(expr.lhs, UnaryExpr)
        self.assertIsInstance(expr.rhs, LiteralExpr)

    def test_unary_precedence(self):
        # -1 * 2 should be (-1) * 2
        expr = parse_expression("-1 * 2")
        self.assertIsInstance(expr, BinaryExpr)
        self.assertIsInstance(expr.lhs, UnaryExpr)


# ========== GROUPING & PARENTHESES ==========
class TestGrouping(unittest.TestCase):
    """Test parsing of grouped (parenthesized) expressions."""

    def test_simple_grouping(self):
        expr = parse_expression("(1)")
        self.assertIsInstance(expr, Grouping)
        self.assertIsInstance(expr.expr, LiteralExpr)

    def test_grouping_expression(self):
        expr = parse_expression("(1 + 2)")
        self.assertIsInstance(expr, Grouping)
        self.assertIsInstance(expr.expr, BinaryExpr)

    def test_nested_grouping(self):
        expr = parse_expression("((1))")
        self.assertIsInstance(expr, Grouping)
        self.assertIsInstance(expr.expr, Grouping)

    def test_grouping_override_precedence(self):
        # (1 + 2) * 3 should be ((1 + 2)) * 3
        expr = parse_expression("(1 + 2) * 3")
        self.assertIsInstance(expr, BinaryExpr)
        self.assertEqual(expr.op.ttype, TokenType.STAR)
        self.assertIsInstance(expr.lhs, Grouping)

    def test_complex_grouping(self):
        expr = parse_expression("((1 + 2) * (3 - 4))")
        self.assertIsInstance(expr, Grouping)
        self.assertIsInstance(expr.expr, BinaryExpr)

    def test_grouping_with_unary(self):
        expr = parse_expression("(-1)")
        self.assertIsInstance(expr, Grouping)
        self.assertIsInstance(expr.expr, UnaryExpr)


# ========== VARIABLE EXPRESSIONS ==========
class TestVariableExpressions(unittest.TestCase):
    """Test parsing of variable expressions."""

    def test_simple_variable(self):
        expr = parse_expression("x")
        self.assertIsInstance(expr, VariableExpr)
        self.assertEqual(expr.name.raw, "x")
        self.assertIsNone(expr.access)

    def test_variable_name_preserved(self):
        expr = parse_expression("myVariable")
        self.assertIsInstance(expr, VariableExpr)
        self.assertEqual(expr.name.raw, "myVariable")

    def test_member_access(self):
        expr = parse_expression("obj.field")
        self.assertIsInstance(expr, VariableExpr)
        self.assertEqual(expr.name.raw, "obj")
        self.assertIsNotNone(expr.access)
        self.assertIsInstance(expr.access, VariableExpr)
        self.assertEqual(expr.access.name.raw, "field")

    def test_chained_member_access(self):
        expr = parse_expression("a.b.c")
        self.assertIsInstance(expr, VariableExpr)
        self.assertEqual(expr.name.raw, "a")
        self.assertIsInstance(expr.access, VariableExpr)
        self.assertEqual(expr.access.name.raw, "b")
        self.assertIsInstance(expr.access.access, VariableExpr)
        self.assertEqual(expr.access.access.name.raw, "c")

    def test_variable_in_binary_expr(self):
        expr = parse_expression("x + y")
        self.assertIsInstance(expr, BinaryExpr)
        self.assertIsInstance(expr.lhs, VariableExpr)
        self.assertIsInstance(expr.rhs, VariableExpr)


# ========== FUNCTION/METHOD CALLS ==========
class TestCallExpressions(unittest.TestCase):
    """Test parsing of function and method call expressions."""

    def test_function_call_no_args(self):
        expr = parse_expression("foo()")
        self.assertIsInstance(expr, CallExpr)
        self.assertEqual(expr.callee.raw, "foo")
        self.assertEqual(len(expr.args), 0)

    def test_function_call_one_arg(self):
        expr = parse_expression("foo(1)")
        self.assertIsInstance(expr, CallExpr)
        self.assertEqual(len(expr.args), 1)
        self.assertIsInstance(expr.args[0], LiteralExpr)

    def test_function_call_multiple_args(self):
        expr = parse_expression("foo(1, 2, 3)")
        self.assertIsInstance(expr, CallExpr)
        self.assertEqual(len(expr.args), 3)

    def test_function_call_with_variables(self):
        expr = parse_expression("foo(x, y)")
        self.assertIsInstance(expr, CallExpr)
        self.assertIsInstance(expr.args[0], VariableExpr)
        self.assertIsInstance(expr.args[1], VariableExpr)

    def test_function_call_with_expressions(self):
        expr = parse_expression("foo(1 + 2, x * y)")
        self.assertIsInstance(expr, CallExpr)
        self.assertIsInstance(expr.args[0], BinaryExpr)
        self.assertIsInstance(expr.args[1], BinaryExpr)

    def test_method_call(self):
        expr = parse_expression("obj.method()")
        self.assertIsInstance(expr, VariableExpr)
        self.assertEqual(expr.name.raw, "obj")
        self.assertIsInstance(expr.access, CallExpr)
        self.assertEqual(expr.access.callee.raw, "method")

    def test_method_call_with_args(self):
        expr = parse_expression("obj.method(1, 2)")
        self.assertIsInstance(expr, VariableExpr)
        self.assertIsInstance(expr.access, CallExpr)
        self.assertEqual(len(expr.access.args), 2)

    def test_chained_method_calls(self):
        expr = parse_expression("obj.method1().method2()")
        self.assertIsInstance(expr, VariableExpr)
        self.assertIsInstance(expr.access, CallExpr)
        self.assertIsInstance(expr.access.access, CallExpr)

    def test_nested_function_calls(self):
        expr = parse_expression("foo(bar(x))")
        self.assertIsInstance(expr, CallExpr)
        self.assertIsInstance(expr.args[0], CallExpr)

    def test_function_call_in_expression(self):
        expr = parse_expression("foo() + bar()")
        self.assertIsInstance(expr, BinaryExpr)
        self.assertIsInstance(expr.lhs, CallExpr)
        self.assertIsInstance(expr.rhs, CallExpr)


# ========== ARRAY EXPRESSIONS ==========
class TestArrayExpressions(unittest.TestCase):
    """Test parsing of array expressions."""

    def test_empty_array(self):
        expr = parse_expression("{}")
        self.assertIsInstance(expr, ArrayExpr)
        self.assertEqual(len(expr.elements), 0)

    def test_array_with_integers(self):
        expr = parse_expression("{1, 2, 3}")
        self.assertIsInstance(expr, ArrayExpr)
        self.assertEqual(len(expr.elements), 3)
        self.assertIsInstance(expr.elements[0], LiteralExpr)

    def test_array_with_variables(self):
        expr = parse_expression("{x, y, z}")
        self.assertIsInstance(expr, ArrayExpr)
        self.assertEqual(len(expr.elements), 3)
        self.assertIsInstance(expr.elements[0], VariableExpr)

    def test_array_with_expressions(self):
        expr = parse_expression("{1 + 2, x * y}")
        self.assertIsInstance(expr, ArrayExpr)
        self.assertEqual(len(expr.elements), 2)
        self.assertIsInstance(expr.elements[0], BinaryExpr)

    def test_array_single_element(self):
        expr = parse_expression("{42}")
        self.assertIsInstance(expr, ArrayExpr)
        self.assertEqual(len(expr.elements), 1)

    def test_nested_arrays(self):
        expr = parse_expression("{{1, 2}, {3, 4}}")
        self.assertIsInstance(expr, ArrayExpr)
        self.assertEqual(len(expr.elements), 2)
        self.assertIsInstance(expr.elements[0], ArrayExpr)
        self.assertIsInstance(expr.elements[1], ArrayExpr)


# ========== VARIABLE DECLARATIONS ==========
class TestVariableDeclarations(unittest.TestCase):
    """Test parsing of variable declarations."""

    def test_simple_declaration(self):
        stmt = parse_statement("int x;")
        self.assertIsInstance(stmt, VarDecl)
        self.assertEqual(stmt.type_name[0].raw, "int")
        self.assertEqual(stmt.type_name[1].raw, "x")
        self.assertIsNone(stmt.value)

    def test_declaration_with_value(self):
        stmt = parse_statement("int x = 5;")
        self.assertIsInstance(stmt, VarDecl)
        self.assertIsNotNone(stmt.value)
        self.assertIsInstance(stmt.value, LiteralExpr)

    def test_declaration_with_expression(self):
        stmt = parse_statement("int x = 1 + 2;")
        self.assertIsInstance(stmt, VarDecl)
        self.assertIsInstance(stmt.value, BinaryExpr)

    def test_float_declaration(self):
        stmt = parse_statement("float y = 3.14;")
        self.assertIsInstance(stmt, VarDecl)
        self.assertEqual(stmt.type_name[0].raw, "float")

    def test_bool_declaration(self):
        stmt = parse_statement("bool flag = true;")
        self.assertIsInstance(stmt, VarDecl)
        self.assertEqual(stmt.type_name[0].raw, "bool")

    def test_private_flag(self):
        stmt = parse_statement("private int x;")
        self.assertIsInstance(stmt, VarDecl)
        self.assertIn(MemberFlag.PRIVATE, stmt.flags)

    def test_static_flag(self):
        stmt = parse_statement("static int x;")
        self.assertIsInstance(stmt, VarDecl)
        self.assertIn(MemberFlag.STATIC, stmt.flags)

    def test_const_flag(self):
        stmt = parse_statement("const int x = 5;")
        self.assertIsInstance(stmt, VarDecl)
        self.assertIn(MemberFlag.CONST, stmt.flags)

    def test_multiple_flags(self):
        stmt = parse_statement("private static int x;")
        self.assertIsInstance(stmt, VarDecl)
        self.assertIn(MemberFlag.PRIVATE, stmt.flags)
        self.assertIn(MemberFlag.STATIC, stmt.flags)

    def test_all_member_flags(self):
        stmt = parse_statement("private static const int x = 5;")
        self.assertIsInstance(stmt, VarDecl)
        self.assertIn(MemberFlag.PRIVATE, stmt.flags)
        self.assertIn(MemberFlag.STATIC, stmt.flags)
        self.assertIn(MemberFlag.CONST, stmt.flags)

    def test_custom_type(self):
        stmt = parse_statement("MyClass obj;")
        self.assertIsInstance(stmt, VarDecl)
        self.assertEqual(stmt.type_name[0].raw, "MyClass")

    def test_multiple_declarations(self):
        program = parse("int x; float y;")
        self.assertEqual(len(program.statements), 2)
        self.assertIsInstance(program.statements[0], VarDecl)
        self.assertIsInstance(program.statements[1], VarDecl)


# ========== ASSIGNMENT STATEMENTS ==========
class TestAssignmentStatements(unittest.TestCase):
    """Test parsing of assignment statements."""

    def test_simple_assignment(self):
        stmt = parse_statement("x = 5;")
        self.assertIsInstance(stmt, AssignmentStmt)
        self.assertIsInstance(stmt.target, VariableExpr)
        self.assertEqual(stmt.target.name.raw, "x")
        self.assertIsInstance(stmt.value, LiteralExpr)

    def test_assignment_with_expression(self):
        stmt = parse_statement("x = 1 + 2;")
        self.assertIsInstance(stmt, AssignmentStmt)
        self.assertIsInstance(stmt.value, BinaryExpr)

    def test_assignment_to_member(self):
        stmt = parse_statement("obj.field = 5;")
        self.assertIsInstance(stmt, AssignmentStmt)
        self.assertIsInstance(stmt.target, VariableExpr)
        self.assertIsNotNone(stmt.target.access)

    def test_assignment_chained_member(self):
        stmt = parse_statement("a.b.c = 5;")
        self.assertIsInstance(stmt, AssignmentStmt)
        self.assertIsInstance(stmt.target, VariableExpr)

    def test_assignment_from_function_call(self):
        stmt = parse_statement("x = foo();")
        self.assertIsInstance(stmt, AssignmentStmt)
        self.assertIsInstance(stmt.value, CallExpr)

    def test_assignment_from_variable(self):
        stmt = parse_statement("x = y;")
        self.assertIsInstance(stmt, AssignmentStmt)
        self.assertIsInstance(stmt.value, VariableExpr)


# ========== RETURN STATEMENTS ==========
class TestReturnStatements(unittest.TestCase):
    """Test parsing of return statements."""

    def test_return_no_value(self):
        stmt = parse_statement("return;")
        self.assertIsInstance(stmt, ReturnStmt)
        self.assertIsNone(stmt.value)

    def test_return_literal(self):
        stmt = parse_statement("return 42;")
        self.assertIsInstance(stmt, ReturnStmt)
        self.assertIsInstance(stmt.value, LiteralExpr)

    def test_return_variable(self):
        stmt = parse_statement("return x;")
        self.assertIsInstance(stmt, ReturnStmt)
        self.assertIsInstance(stmt.value, VariableExpr)

    def test_return_expression(self):
        stmt = parse_statement("return x + y;")
        self.assertIsInstance(stmt, ReturnStmt)
        self.assertIsInstance(stmt.value, BinaryExpr)

    def test_return_function_call(self):
        stmt = parse_statement("return foo();")
        self.assertIsInstance(stmt, ReturnStmt)
        self.assertIsInstance(stmt.value, CallExpr)

    def test_return_bool(self):
        stmt = parse_statement("return true;")
        self.assertIsInstance(stmt, ReturnStmt)
        self.assertIsInstance(stmt.value, LiteralExpr)
        self.assertEqual(stmt.value.ltype, LiteralType.BOOL)


# ========== IF STATEMENTS ==========
class TestIfStatements(unittest.TestCase):
    """Test parsing of if/elif/else statements."""

    def test_simple_if(self):
        stmt = parse_statement("if (true) {}")
        self.assertIsInstance(stmt, IfStmt)
        self.assertIsInstance(stmt.condition, LiteralExpr)
        self.assertIsInstance(stmt.body, ScopeStmt)
        self.assertIsNone(stmt.else_branch)

    def test_if_with_variable_condition(self):
        stmt = parse_statement("if (x) {}")
        self.assertIsInstance(stmt, IfStmt)
        self.assertIsInstance(stmt.condition, VariableExpr)

    def test_if_with_comparison(self):
        stmt = parse_statement("if (x > 5) {}")
        self.assertIsInstance(stmt, IfStmt)
        self.assertIsInstance(stmt.condition, BinaryExpr)

    def test_if_with_complex_condition(self):
        stmt = parse_statement("if (x > 5 && y < 10) {}")
        self.assertIsInstance(stmt, IfStmt)
        self.assertIsInstance(stmt.condition, BinaryExpr)

    def test_if_with_body(self):
        stmt = parse_statement("if (true) { x = 5; }")
        self.assertIsInstance(stmt, IfStmt)
        self.assertEqual(len(stmt.body.body), 1)
        self.assertIsInstance(stmt.body.body[0], AssignmentStmt)

    def test_if_with_multiple_statements(self):
        stmt = parse_statement("if (true) { x = 5; y = 10; }")
        self.assertIsInstance(stmt, IfStmt)
        self.assertEqual(len(stmt.body.body), 2)

    def test_if_else(self):
        stmt = parse_statement("if (true) {} else {}")
        self.assertIsInstance(stmt, IfStmt)
        self.assertIsNotNone(stmt.else_branch)
        self.assertIsInstance(stmt.else_branch, ElseStmt)

    def test_if_else_with_body(self):
        stmt = parse_statement("if (true) { x = 1; } else { x = 2; }")
        self.assertIsInstance(stmt, IfStmt)
        self.assertIsInstance(stmt.else_branch, ElseStmt)
        self.assertEqual(len(stmt.else_branch.body.body), 1)

    def test_if_elif(self):
        stmt = parse_statement("if (a) {} elif (b) {}")
        self.assertIsInstance(stmt, IfStmt)
        self.assertIsInstance(stmt.else_branch, IfStmt)

    def test_if_elif_else(self):
        stmt = parse_statement("if (a) {} elif (b) {} else {}")
        self.assertIsInstance(stmt, IfStmt)
        self.assertIsInstance(stmt.else_branch, IfStmt)
        self.assertIsInstance(stmt.else_branch.else_branch, ElseStmt)

    def test_multiple_elif(self):
        stmt = parse_statement("if (a) {} elif (b) {} elif (c) {} else {}")
        self.assertIsInstance(stmt, IfStmt)
        self.assertIsInstance(stmt.else_branch, IfStmt)
        self.assertIsInstance(stmt.else_branch.else_branch, IfStmt)
        self.assertIsInstance(stmt.else_branch.else_branch.else_branch, ElseStmt)

    def test_nested_if(self):
        stmt = parse_statement("if (a) { if (b) {} }")
        self.assertIsInstance(stmt, IfStmt)
        self.assertEqual(len(stmt.body.body), 1)
        self.assertIsInstance(stmt.body.body[0], IfStmt)


# ========== WHILE STATEMENTS ==========
class TestWhileStatements(unittest.TestCase):
    """Test parsing of while statements."""

    def test_simple_while(self):
        stmt = parse_statement("while (true) {}")
        self.assertIsInstance(stmt, WhileStmt)
        self.assertIsInstance(stmt.condition, LiteralExpr)
        self.assertEqual(len(stmt.body), 0)

    def test_while_with_variable_condition(self):
        stmt = parse_statement("while (x) {}")
        self.assertIsInstance(stmt, WhileStmt)
        self.assertIsInstance(stmt.condition, VariableExpr)

    def test_while_with_comparison(self):
        stmt = parse_statement("while (x < 10) {}")
        self.assertIsInstance(stmt, WhileStmt)
        self.assertIsInstance(stmt.condition, BinaryExpr)

    def test_while_with_complex_condition(self):
        stmt = parse_statement("while (x > 0 && !done) {}")
        self.assertIsInstance(stmt, WhileStmt)
        self.assertIsInstance(stmt.condition, BinaryExpr)

    def test_while_with_body(self):
        stmt = parse_statement("while (true) { x = x + 1; }")
        self.assertIsInstance(stmt, WhileStmt)
        self.assertEqual(len(stmt.body), 1)
        self.assertIsInstance(stmt.body[0], AssignmentStmt)

    def test_while_with_multiple_statements(self):
        stmt = parse_statement("while (true) { x = 1; y = 2; z = 3; }")
        self.assertIsInstance(stmt, WhileStmt)
        self.assertEqual(len(stmt.body), 3)

    def test_nested_while(self):
        stmt = parse_statement("while (a) { while (b) {} }")
        self.assertIsInstance(stmt, WhileStmt)
        self.assertEqual(len(stmt.body), 1)
        self.assertIsInstance(stmt.body[0], WhileStmt)


# ========== FOR STATEMENTS ==========
class TestForStatements(unittest.TestCase):
    """Test parsing of for statements."""

    def test_simple_for(self):
        stmt = parse_statement("for (int x in arr) {}")
        self.assertIsInstance(stmt, ForStmt)
        self.assertEqual(stmt.var_type_name[0].raw, "int")
        self.assertEqual(stmt.var_type_name[1].raw, "x")
        self.assertIsInstance(stmt.iterable, VariableExpr)

    def test_for_with_different_type(self):
        stmt = parse_statement("for (float y in numbers) {}")
        self.assertIsInstance(stmt, ForStmt)
        self.assertEqual(stmt.var_type_name[0].raw, "float")
        self.assertEqual(stmt.var_type_name[1].raw, "y")

    def test_for_with_custom_type(self):
        stmt = parse_statement("for (MyClass obj in items) {}")
        self.assertIsInstance(stmt, ForStmt)
        self.assertEqual(stmt.var_type_name[0].raw, "MyClass")

    def test_for_with_expression_iterable(self):
        stmt = parse_statement("for (int x in getItems()) {}")
        self.assertIsInstance(stmt, ForStmt)
        self.assertIsInstance(stmt.iterable, CallExpr)

    def test_for_with_member_access_iterable(self):
        stmt = parse_statement("for (int x in obj.items) {}")
        self.assertIsInstance(stmt, ForStmt)
        self.assertIsInstance(stmt.iterable, VariableExpr)
        self.assertIsNotNone(stmt.iterable.access)

    def test_for_with_body(self):
        stmt = parse_statement("for (int x in arr) { y = x; }")
        self.assertIsInstance(stmt, ForStmt)
        self.assertEqual(len(stmt.body), 1)
        self.assertIsInstance(stmt.body[0], AssignmentStmt)

    def test_for_with_multiple_statements(self):
        stmt = parse_statement("for (int x in arr) { a = 1; b = 2; }")
        self.assertIsInstance(stmt, ForStmt)
        self.assertEqual(len(stmt.body), 2)

    def test_nested_for(self):
        stmt = parse_statement("for (int i in outer) { for (int j in inner) {} }")
        self.assertIsInstance(stmt, ForStmt)
        self.assertEqual(len(stmt.body), 1)
        self.assertIsInstance(stmt.body[0], ForStmt)


# ========== FUNCTION DECLARATIONS ==========
class TestFunctionDeclarations(unittest.TestCase):
    """Test parsing of function declarations."""

    def test_simple_function(self):
        stmt = parse_statement("scope foo = {}")
        self.assertIsInstance(stmt, Function)
        self.assertEqual(stmt.name.raw, "foo")
        self.assertEqual(len(stmt.args), 0)
        self.assertIsNone(stmt.returns)

    def test_function_with_parens(self):
        stmt = parse_statement("scope foo() = {}")
        self.assertIsInstance(stmt, Function)
        self.assertEqual(len(stmt.args), 0)

    def test_function_with_one_param(self):
        stmt = parse_statement("scope foo(int x) = {}")
        self.assertIsInstance(stmt, Function)
        self.assertEqual(len(stmt.args), 1)
        self.assertEqual(stmt.args[0][0].raw, "int")
        self.assertEqual(stmt.args[0][1].raw, "x")

    def test_function_with_multiple_params(self):
        stmt = parse_statement("scope foo(int x, float y, bool z) = {}")
        self.assertIsInstance(stmt, Function)
        self.assertEqual(len(stmt.args), 3)

    def test_function_with_return_type(self):
        stmt = parse_statement("scope foo() -> int = {}")
        self.assertIsInstance(stmt, Function)
        self.assertIsNotNone(stmt.returns)
        self.assertEqual(stmt.returns.raw, "int")

    def test_function_with_params_and_return(self):
        stmt = parse_statement("scope add(int a, int b) -> int = {}")
        self.assertIsInstance(stmt, Function)
        self.assertEqual(len(stmt.args), 2)
        self.assertEqual(stmt.returns.raw, "int")

    def test_function_with_body(self):
        stmt = parse_statement("scope foo() = { return 5; }")
        self.assertIsInstance(stmt, Function)
        self.assertEqual(len(stmt.body), 1)
        self.assertIsInstance(stmt.body[0], ReturnStmt)

    def test_function_with_multiple_statements(self):
        stmt = parse_statement("scope foo() = { int x = 1; return x; }")
        self.assertIsInstance(stmt, Function)
        self.assertEqual(len(stmt.body), 2)

    def test_private_function(self):
        stmt = parse_statement("private scope foo() = {}")
        self.assertIsInstance(stmt, Function)
        self.assertIn(MemberFlag.PRIVATE, stmt.member_flags)

    def test_static_function(self):
        stmt = parse_statement("static scope foo() = {}")
        self.assertIsInstance(stmt, Function)
        self.assertIn(MemberFlag.STATIC, stmt.member_flags)

    def test_const_function(self):
        stmt = parse_statement("const scope foo() = {}")
        self.assertIsInstance(stmt, Function)
        self.assertIn(MemberFlag.CONST, stmt.member_flags)

    def test_cast_function(self):
        stmt = parse_statement("cast scope toInt() -> int = {}")
        self.assertIsInstance(stmt, Function)
        self.assertIn(FunctionFlag.CAST, stmt.function_flags)

    def test_operator_function(self):
        stmt = parse_statement("operator scope add(int other) -> int = {}")
        self.assertIsInstance(stmt, Function)
        self.assertIn(FunctionFlag.OPERATOR, stmt.function_flags)

    def test_private_static_function(self):
        stmt = parse_statement("private static scope foo() = {}")
        self.assertIsInstance(stmt, Function)
        self.assertIn(MemberFlag.PRIVATE, stmt.member_flags)
        self.assertIn(MemberFlag.STATIC, stmt.member_flags)

    def test_complex_flags_function(self):
        stmt = parse_statement("private static operator scope add(int x) -> int = {}")
        self.assertIsInstance(stmt, Function)
        self.assertIn(MemberFlag.PRIVATE, stmt.member_flags)
        self.assertIn(MemberFlag.STATIC, stmt.member_flags)
        self.assertIn(FunctionFlag.OPERATOR, stmt.function_flags)

    def test_function_nested_in_function(self):
        # Inner function declaration within outer function body
        stmt = parse_statement("scope outer() = { scope inner() = {} }")
        self.assertIsInstance(stmt, Function)
        self.assertEqual(len(stmt.body), 1)
        self.assertIsInstance(stmt.body[0], Function)


# ========== CLASS DECLARATIONS ==========
class TestClassDeclarations(unittest.TestCase):
    """Test parsing of class declarations."""

    def test_empty_class(self):
        stmt = parse_statement("class Foo = ()")
        self.assertIsInstance(stmt, Class)
        self.assertEqual(stmt.name.raw, "Foo")
        self.assertEqual(len(stmt.args), 0)
        self.assertEqual(len(stmt.members), 0)

    def test_class_with_constructor_params(self):
        stmt = parse_statement("class Foo(int x) = ()")
        self.assertIsInstance(stmt, Class)
        self.assertEqual(len(stmt.args), 1)
        self.assertEqual(stmt.args[0][0].raw, "int")
        self.assertEqual(stmt.args[0][1].raw, "x")

    def test_class_with_multiple_params(self):
        stmt = parse_statement("class Foo(int x, float y) = ()")
        self.assertIsInstance(stmt, Class)
        self.assertEqual(len(stmt.args), 2)

    def test_class_with_member_variable(self):
        stmt = parse_statement("class Foo = (int x)")
        self.assertIsInstance(stmt, Class)
        self.assertEqual(len(stmt.members), 1)
        self.assertIsInstance(stmt.members[0], VarDecl)

    def test_class_with_multiple_members(self):
        stmt = parse_statement("class Foo = (int x, float y)")
        self.assertIsInstance(stmt, Class)
        self.assertEqual(len(stmt.members), 2)

    def test_class_with_member_function(self):
        stmt = parse_statement("class Foo = (scope bar() = {})")
        self.assertIsInstance(stmt, Class)
        self.assertEqual(len(stmt.members), 1)
        self.assertIsInstance(stmt.members[0], Function)

    def test_class_with_mixed_members(self):
        stmt = parse_statement("class Foo = (int x, scope bar() = {})")
        self.assertIsInstance(stmt, Class)
        self.assertEqual(len(stmt.members), 2)
        self.assertIsInstance(stmt.members[0], VarDecl)
        self.assertIsInstance(stmt.members[1], Function)

    def test_class_with_private_member(self):
        stmt = parse_statement("class Foo = (private int x)")
        self.assertIsInstance(stmt, Class)
        self.assertIsInstance(stmt.members[0], VarDecl)
        self.assertIn(MemberFlag.PRIVATE, stmt.members[0].flags)

    def test_class_inheritance(self):
        stmt = parse_statement("class Foo : Bar = ()")
        self.assertIsInstance(stmt, Class)
        # Note: inheritance parents aren't stored in current AST, but parsing should work

    def test_class_multiple_inheritance(self):
        stmt = parse_statement("class Foo : Bar, Baz = ()")
        self.assertIsInstance(stmt, Class)

    def test_class_with_init_value(self):
        stmt = parse_statement("class Foo = (int x = 5)")
        self.assertIsInstance(stmt, Class)
        self.assertIsInstance(stmt.members[0], VarDecl)
        self.assertIsNotNone(stmt.members[0].value)

    def test_nested_class(self):
        stmt = parse_statement("class Outer = (class Inner = ())")
        self.assertIsInstance(stmt, Class)
        self.assertEqual(len(stmt.members), 1)
        self.assertIsInstance(stmt.members[0], Class)

    def test_class_params_and_members(self):
        stmt = parse_statement("class Foo(int a) = (int b, scope method() = {})")
        self.assertIsInstance(stmt, Class)
        self.assertEqual(len(stmt.args), 1)
        self.assertEqual(len(stmt.members), 2)


# ========== IMPORT STATEMENTS ==========
class TestImportStatements(unittest.TestCase):
    """Test parsing of import statements."""

    def test_simple_import(self):
        program = parse("import foo;")
        self.assertEqual(len(program.imports), 1)
        self.assertEqual(len(program.imports[0].path), 1)
        self.assertEqual(program.imports[0].path[0].raw, "foo")

    def test_nested_import(self):
        program = parse("import foo.bar;")
        self.assertEqual(len(program.imports), 1)
        self.assertEqual(len(program.imports[0].path), 2)
        self.assertEqual(program.imports[0].path[0].raw, "foo")
        self.assertEqual(program.imports[0].path[1].raw, "bar")

    def test_deeply_nested_import(self):
        program = parse("import foo.bar.baz.qux;")
        self.assertEqual(len(program.imports), 1)
        self.assertEqual(len(program.imports[0].path), 4)

    def test_multiple_imports(self):
        program = parse("import foo; import bar;")
        self.assertEqual(len(program.imports), 2)

    def test_import_before_statements(self):
        program = parse("import foo; int x;")
        self.assertEqual(len(program.imports), 1)
        self.assertEqual(len(program.statements), 1)

    def test_multiple_imports_before_statements(self):
        program = parse("import foo; import bar; int x; int y;")
        self.assertEqual(len(program.imports), 2)
        self.assertEqual(len(program.statements), 2)


# ========== EMPTY STATEMENTS ==========
class TestEmptyStatements(unittest.TestCase):
    """Test parsing of empty statements."""

    def test_empty_statement(self):
        stmt = parse_statement(";")
        self.assertIsInstance(stmt, ScopeStmt)
        self.assertEqual(len(stmt.body), 0)

    def test_multiple_empty_statements(self):
        program = parse(";;;")
        self.assertEqual(len(program.statements), 3)


# ========== PROGRAM STRUCTURE ==========
class TestProgramStructure(unittest.TestCase):
    """Test overall program structure."""

    def test_empty_program(self):
        program = parse("")
        self.assertEqual(len(program.imports), 0)
        self.assertEqual(len(program.statements), 0)

    def test_program_with_only_imports(self):
        program = parse("import foo; import bar;")
        self.assertEqual(len(program.imports), 2)
        self.assertEqual(len(program.statements), 0)

    def test_program_with_only_statements(self):
        program = parse("int x; int y;")
        self.assertEqual(len(program.imports), 0)
        self.assertEqual(len(program.statements), 2)

    def test_complete_program(self):
        source = """
        import std;
        import math.utils;
        
        int globalVar = 10;
        
        scope main() = {
            int x = 5;
            return x;
        }
        
        class MyClass = (
            int value,
            scope getValue() -> int = {
                return value;
            }
        )
        """
        program = parse(source)
        self.assertEqual(len(program.imports), 2)
        self.assertGreaterEqual(len(program.statements), 3)


# ========== COMPLEX EXPRESSIONS ==========
class TestComplexExpressions(unittest.TestCase):
    """Test parsing of complex, nested expressions."""

    def test_deeply_nested_arithmetic(self):
        expr = parse_expression("1 + 2 * 3 - 4 / 5 + 6")
        self.assertIsInstance(expr, BinaryExpr)

    def test_mixed_operators(self):
        expr = parse_expression("a + b * c > d && e || f")
        self.assertIsInstance(expr, BinaryExpr)
        self.assertEqual(expr.op.ttype, TokenType.PIPE_PIPE)

    def test_function_in_arithmetic(self):
        expr = parse_expression("foo() + bar() * baz()")
        self.assertIsInstance(expr, BinaryExpr)

    def test_member_access_in_expression(self):
        expr = parse_expression("obj.value + other.value")
        self.assertIsInstance(expr, BinaryExpr)
        self.assertIsInstance(expr.lhs, VariableExpr)
        self.assertIsNotNone(expr.lhs.access)

    def test_method_call_in_expression(self):
        expr = parse_expression("obj.getValue() * 2")
        self.assertIsInstance(expr, BinaryExpr)

    def test_deeply_nested_member_access(self):
        expr = parse_expression("a.b.c.d.e")
        self.assertIsInstance(expr, VariableExpr)

    def test_complex_condition(self):
        expr = parse_expression("(x > 0 && x < 10) || (y >= 5 && y <= 15)")
        self.assertIsInstance(expr, BinaryExpr)
        self.assertEqual(expr.op.ttype, TokenType.PIPE_PIPE)

    def test_nested_function_calls_in_expression(self):
        expr = parse_expression("foo(bar(baz(x)))")
        self.assertIsInstance(expr, CallExpr)
        self.assertIsInstance(expr.args[0], CallExpr)
        self.assertIsInstance(expr.args[0].args[0], CallExpr)


# ========== ERROR HANDLING ==========
class TestParseErrors(unittest.TestCase):
    """Test that parser raises appropriate errors for invalid input."""

    def test_missing_semicolon(self):
        with self.assertRaises(ParseException):
            parse("int x")

    def test_missing_closing_paren(self):
        with self.assertRaises(ParseException):
            parse("(1 + 2;")

    def test_missing_closing_curly(self):
        with self.assertRaises(ParseException):
            parse("if (true) {")

    def test_missing_condition_paren(self):
        with self.assertRaises(ParseException):
            parse("if true {}")

    def test_invalid_assignment_target(self):
        with self.assertRaises(ParseException):
            parse("5 = x;")

    def test_missing_function_body(self):
        with self.assertRaises(ParseException):
            parse("scope foo() =")

    def test_missing_class_body(self):
        with self.assertRaises(ParseException):
            parse("class Foo =")

    def test_unexpected_token_in_params(self):
        with self.assertRaises(ParseException):
            parse("scope foo(int) = {}")

    def test_missing_for_in_keyword(self):
        with self.assertRaises(ParseException):
            parse("for (int x arr) {}")

    def test_missing_import_path(self):
        with self.assertRaises(ParseException):
            parse("import ;")


# ========== EDGE CASES ==========
class TestEdgeCases(unittest.TestCase):
    """Test edge cases and boundary conditions."""

    def test_long_identifier(self):
        long_name = "a" * 100
        expr = parse_expression(long_name)
        self.assertIsInstance(expr, VariableExpr)
        self.assertEqual(expr.name.raw, long_name)

    def test_many_arguments(self):
        args = ", ".join([f"int arg{i}" for i in range(20)])
        stmt = parse_statement(f"scope foo({args}) = {{}}")
        self.assertIsInstance(stmt, Function)
        self.assertEqual(len(stmt.args), 20)

    def test_many_array_elements(self):
        elements = ", ".join([str(i) for i in range(50)])
        expr = parse_expression(f"{{{elements}}}")
        self.assertIsInstance(expr, ArrayExpr)
        self.assertEqual(len(expr.elements), 50)

    def test_deeply_nested_grouping(self):
        expr = parse_expression("((((((1))))))")
        # Unwrap all groupings
        current = expr
        depth = 0
        while isinstance(current, Grouping):
            depth += 1
            current = current.expr
        self.assertEqual(depth, 6)
        self.assertIsInstance(current, LiteralExpr)

    def test_expression_as_statement(self):
        # Just a function call as statement
        stmt = parse_statement("foo();")
        self.assertIsInstance(stmt, CallExpr)

    def test_variable_as_statement(self):
        # Just a variable access as statement (no-op but valid)
        stmt = parse_statement("x;")
        self.assertIsInstance(stmt, VariableExpr)

    def test_method_call_chain_as_statement(self):
        stmt = parse_statement("obj.method1().method2();")
        self.assertIsInstance(stmt, VariableExpr)


if __name__ == "__main__":
    unittest.main()
