from __future__ import annotations
import sys
import unittest
from pathlib import Path

# Add parent directory to path so we can import scanner
sys.path.insert(0, str(Path(__file__).parent.parent))

from scanner import Scanner, Token, TokenType


def tokenize(source: str) -> list[Token]:
    """
    Helper function to tokenize source code.

    Excludes the trailing EOF token for cleaner test assertions.

    :param source: The source code string to tokenize.
    :type source: str
    :return: List of tokens produced by the scanner (excluding EOF).
    :rtype: list[Token]
    """
    scanner = Scanner(source)
    tokens = scanner.scan_source()
    # Exclude EOF token for cleaner tests
    if tokens and tokens[-1].ttype == TokenType.EOF:
        return tokens[:-1]
    return tokens


# ========== SINGLE CHARACTER TOKENS ==========
class TestSingleCharacterTokens(unittest.TestCase):
    """Test scanning of single-character tokens."""

    def test_parentheses(self):
        tokens = tokenize("()")
        self.assertEqual(tokens[0].ttype, TokenType.LEFT_PAREN)
        self.assertEqual(tokens[0].raw, "(")
        self.assertEqual(tokens[1].ttype, TokenType.RIGHT_PAREN)
        self.assertEqual(tokens[1].raw, ")")

    def test_curly_braces(self):
        tokens = tokenize("{}")
        self.assertEqual(tokens[0].ttype, TokenType.LEFT_CURLY)
        self.assertEqual(tokens[0].raw, "{")
        self.assertEqual(tokens[1].ttype, TokenType.RIGHT_CURLY)
        self.assertEqual(tokens[1].raw, "}")

    def test_brackets(self):
        tokens = tokenize("[]")
        self.assertEqual(tokens[0].ttype, TokenType.LEFT_BRACKET)
        self.assertEqual(tokens[0].raw, "[")
        self.assertEqual(tokens[1].ttype, TokenType.RIGHT_BRACKET)
        self.assertEqual(tokens[1].raw, "]")

    def test_angle_brackets(self):
        tokens = tokenize("< >")
        self.assertEqual(tokens[0].ttype, TokenType.LEFT_ANGLE)
        self.assertEqual(tokens[0].raw, "<")
        self.assertEqual(tokens[1].ttype, TokenType.RIGHT_ANGLE)
        self.assertEqual(tokens[1].raw, ">")

    def test_semicolon(self):
        tokens = tokenize(";")
        self.assertEqual(tokens[0].ttype, TokenType.SEMICOLON)
        self.assertEqual(tokens[0].raw, ";")

    def test_comma(self):
        tokens = tokenize(",")
        self.assertEqual(tokens[0].ttype, TokenType.COMMA)
        self.assertEqual(tokens[0].raw, ",")

    def test_dot(self):
        tokens = tokenize(".")
        self.assertEqual(tokens[0].ttype, TokenType.DOT)
        self.assertEqual(tokens[0].raw, ".")

    def test_colon(self):
        tokens = tokenize(":")
        self.assertEqual(tokens[0].ttype, TokenType.COLON)
        self.assertEqual(tokens[0].raw, ":")

    def test_plus(self):
        tokens = tokenize("+")
        self.assertEqual(tokens[0].ttype, TokenType.PLUS)
        self.assertEqual(tokens[0].raw, "+")

    def test_minus(self):
        tokens = tokenize("-")
        self.assertEqual(tokens[0].ttype, TokenType.MINUS)
        self.assertEqual(tokens[0].raw, "-")

    def test_star(self):
        tokens = tokenize("*")
        self.assertEqual(tokens[0].ttype, TokenType.STAR)
        self.assertEqual(tokens[0].raw, "*")

    def test_slash(self):
        tokens = tokenize("/")
        self.assertEqual(tokens[0].ttype, TokenType.SLASH)
        self.assertEqual(tokens[0].raw, "/")

    def test_bang(self):
        tokens = tokenize("!")
        self.assertEqual(tokens[0].ttype, TokenType.BANG)
        self.assertEqual(tokens[0].raw, "!")

    def test_equal(self):
        tokens = tokenize("=")
        self.assertEqual(tokens[0].ttype, TokenType.EQUAL)
        self.assertEqual(tokens[0].raw, "=")

    def test_caret(self):
        tokens = tokenize("^")
        self.assertEqual(tokens[0].ttype, TokenType.CARET)
        self.assertEqual(tokens[0].raw, "^")

    def test_modulo(self):
        tokens = tokenize("%")
        self.assertEqual(tokens[0].ttype, TokenType.MODULO)
        self.assertEqual(tokens[0].raw, "%")

    def test_pipe(self):
        tokens = tokenize("|")
        self.assertEqual(tokens[0].ttype, TokenType.PIPE)
        self.assertEqual(tokens[0].raw, "|")


# ========== MULTI-CHARACTER TOKENS ==========
class TestMultiCharacterTokens(unittest.TestCase):
    """Test scanning of multi-character tokens."""

    def test_bang_equal(self):
        tokens = tokenize("!=")
        self.assertEqual(tokens[0].ttype, TokenType.BANG_EQUAL)
        self.assertEqual(tokens[0].raw, "!=")

    def test_equal_equal(self):
        tokens = tokenize("==")
        self.assertEqual(tokens[0].ttype, TokenType.EQUAL_EQUAL)
        self.assertEqual(tokens[0].raw, "==")

    def test_greater_equal(self):
        tokens = tokenize(">=")
        self.assertEqual(tokens[0].ttype, TokenType.GREATER_EQUAL)
        self.assertEqual(tokens[0].raw, ">=")

    def test_less_equal(self):
        tokens = tokenize("<=")
        self.assertEqual(tokens[0].ttype, TokenType.LESS_EQUAL)
        self.assertEqual(tokens[0].raw, "<=")

    def test_star_star(self):
        tokens = tokenize("**")
        self.assertEqual(tokens[0].ttype, TokenType.STAR_STAR)
        self.assertEqual(tokens[0].raw, "**")

    def test_return_arrow(self):
        tokens = tokenize("->")
        self.assertEqual(tokens[0].ttype, TokenType.RETURN)
        self.assertEqual(tokens[0].raw, "->")

    def test_plus_equal(self):
        tokens = tokenize("+=")
        self.assertEqual(tokens[0].ttype, TokenType.PLUS_EQUAL)
        self.assertEqual(tokens[0].raw, "+=")

    def test_minus_equal(self):
        tokens = tokenize("-=")
        self.assertEqual(tokens[0].ttype, TokenType.MINUS_EQUAL)
        self.assertEqual(tokens[0].raw, "-=")

    def test_star_equal(self):
        tokens = tokenize("*=")
        self.assertEqual(tokens[0].ttype, TokenType.STAR_EQUAL)
        self.assertEqual(tokens[0].raw, "*=")

    def test_star_star_equal(self):
        tokens = tokenize("**=")
        self.assertEqual(tokens[0].ttype, TokenType.STAR_STAR_EQUAL)
        self.assertEqual(tokens[0].raw, "**=")

    def test_slash_equal(self):
        tokens = tokenize("/=")
        self.assertEqual(tokens[0].ttype, TokenType.SLASH_EQUAL)
        self.assertEqual(tokens[0].raw, "/=")

    def test_caret_equal(self):
        tokens = tokenize("^=")
        self.assertEqual(tokens[0].ttype, TokenType.CARET_EQUAL)
        self.assertEqual(tokens[0].raw, "^=")

    def test_modulo_equal(self):
        tokens = tokenize("%=")
        self.assertEqual(tokens[0].ttype, TokenType.MODULO_EQUAL)
        self.assertEqual(tokens[0].raw, "%=")

    def test_pipe_equal(self):
        tokens = tokenize("|=")
        self.assertEqual(tokens[0].ttype, TokenType.PIPE_EQUAL)
        self.assertEqual(tokens[0].raw, "|=")

    def test_pipe_pipe(self):
        tokens = tokenize("||")
        self.assertEqual(tokens[0].ttype, TokenType.PIPE_PIPE)
        self.assertEqual(tokens[0].raw, "||")

    def test_and_and(self):
        tokens = tokenize("&&")
        self.assertEqual(tokens[0].ttype, TokenType.AND_AND)
        self.assertEqual(tokens[0].raw, "&&")


# ========== LITERALS ==========
class TestLiterals(unittest.TestCase):
    """Test scanning of literal values."""

    def test_integer(self):
        tokens = tokenize("42")
        self.assertEqual(tokens[0].ttype, TokenType.INT)
        self.assertEqual(tokens[0].literal, 42)
        self.assertEqual(tokens[0].raw, "42")

    def test_integer_zero(self):
        tokens = tokenize("0")
        self.assertEqual(tokens[0].ttype, TokenType.INT)
        self.assertEqual(tokens[0].literal, 0)

    def test_integer_large(self):
        tokens = tokenize("123456789")
        self.assertEqual(tokens[0].ttype, TokenType.INT)
        self.assertEqual(tokens[0].literal, 123456789)

    def test_float(self):
        tokens = tokenize("3.14")
        self.assertEqual(tokens[0].ttype, TokenType.FLOAT)
        self.assertEqual(tokens[0].literal, 3.14)
        self.assertEqual(tokens[0].raw, "3.14")

    def test_float_with_trailing_zeros(self):
        tokens = tokenize("1.500")
        self.assertEqual(tokens[0].ttype, TokenType.FLOAT)
        self.assertEqual(tokens[0].literal, 1.5)

    def test_float_starting_with_zero(self):
        tokens = tokenize("0.123")
        self.assertEqual(tokens[0].ttype, TokenType.FLOAT)
        self.assertEqual(tokens[0].literal, 0.123)

    def test_string(self):
        tokens = tokenize('"hello"')
        self.assertEqual(tokens[0].ttype, TokenType.STRING)
        self.assertEqual(tokens[0].literal, "hello")
        self.assertEqual(tokens[0].raw, '"hello"')

    def test_string_empty(self):
        tokens = tokenize('""')
        self.assertEqual(tokens[0].ttype, TokenType.STRING)
        self.assertEqual(tokens[0].literal, "")

    def test_string_with_spaces(self):
        tokens = tokenize('"hello world"')
        self.assertEqual(tokens[0].ttype, TokenType.STRING)
        self.assertEqual(tokens[0].literal, "hello world")

    def test_character(self):
        tokens = tokenize("'a'")
        self.assertEqual(tokens[0].ttype, TokenType.CHARACTER)
        self.assertEqual(tokens[0].literal, "a")
        self.assertEqual(tokens[0].raw, "'a'")

    def test_character_digit(self):
        tokens = tokenize("'5'")
        self.assertEqual(tokens[0].ttype, TokenType.CHARACTER)
        self.assertEqual(tokens[0].literal, "5")

    def test_character_space(self):
        tokens = tokenize("' '")
        self.assertEqual(tokens[0].ttype, TokenType.CHARACTER)
        self.assertEqual(tokens[0].literal, " ")

    def test_identifier_simple(self):
        tokens = tokenize("foo")
        self.assertEqual(tokens[0].ttype, TokenType.IDENTIFIER)
        self.assertEqual(tokens[0].raw, "foo")
        self.assertIsNone(tokens[0].literal)

    def test_identifier_with_underscore(self):
        tokens = tokenize("foo_bar")
        self.assertEqual(tokens[0].ttype, TokenType.IDENTIFIER)
        self.assertEqual(tokens[0].raw, "foo_bar")

    def test_identifier_with_numbers(self):
        tokens = tokenize("foo123")
        self.assertEqual(tokens[0].ttype, TokenType.IDENTIFIER)
        self.assertEqual(tokens[0].raw, "foo123")

    def test_identifier_starting_with_underscore(self):
        tokens = tokenize("_private")
        self.assertEqual(tokens[0].ttype, TokenType.IDENTIFIER)
        self.assertEqual(tokens[0].raw, "_private")

    def test_identifier_all_caps(self):
        tokens = tokenize("CONSTANT")
        self.assertEqual(tokens[0].ttype, TokenType.IDENTIFIER)
        self.assertEqual(tokens[0].raw, "CONSTANT")


# ========== KEYWORDS ==========
class TestKeywords(unittest.TestCase):
    """Test scanning of language keywords."""

    def test_class(self):
        tokens = tokenize("class")
        self.assertEqual(tokens[0].ttype, TokenType.CLASS_KW)
        self.assertEqual(tokens[0].raw, "class")

    def test_scope(self):
        tokens = tokenize("scope")
        self.assertEqual(tokens[0].ttype, TokenType.SCOPE_KW)
        self.assertEqual(tokens[0].raw, "scope")

    def test_true(self):
        tokens = tokenize("true")
        self.assertEqual(tokens[0].ttype, TokenType.TRUE_KW)
        self.assertEqual(tokens[0].raw, "true")

    def test_false(self):
        tokens = tokenize("false")
        self.assertEqual(tokens[0].ttype, TokenType.FALSE_KW)
        self.assertEqual(tokens[0].raw, "false")

    def test_private(self):
        tokens = tokenize("private")
        self.assertEqual(tokens[0].ttype, TokenType.PRIVATE_KW)
        self.assertEqual(tokens[0].raw, "private")

    def test_static(self):
        tokens = tokenize("static")
        self.assertEqual(tokens[0].ttype, TokenType.STATIC_KW)
        self.assertEqual(tokens[0].raw, "static")

    def test_const(self):
        tokens = tokenize("const")
        self.assertEqual(tokens[0].ttype, TokenType.CONST_KW)
        self.assertEqual(tokens[0].raw, "const")

    def test_operator(self):
        tokens = tokenize("operator")
        self.assertEqual(tokens[0].ttype, TokenType.OPERATOR_KW)
        self.assertEqual(tokens[0].raw, "operator")

    def test_cast(self):
        tokens = tokenize("cast")
        self.assertEqual(tokens[0].ttype, TokenType.CAST_KW)
        self.assertEqual(tokens[0].raw, "cast")

    def test_super(self):
        tokens = tokenize("super")
        self.assertEqual(tokens[0].ttype, TokenType.SUPER_KW)
        self.assertEqual(tokens[0].raw, "super")

    def test_return(self):
        tokens = tokenize("return")
        self.assertEqual(tokens[0].ttype, TokenType.RETURN_KW)
        self.assertEqual(tokens[0].raw, "return")

    def test_import(self):
        tokens = tokenize("import")
        self.assertEqual(tokens[0].ttype, TokenType.IMPORT_KW)
        self.assertEqual(tokens[0].raw, "import")

    def test_if(self):
        tokens = tokenize("if")
        self.assertEqual(tokens[0].ttype, TokenType.IF_KW)
        self.assertEqual(tokens[0].raw, "if")

    def test_elif(self):
        tokens = tokenize("elif")
        self.assertEqual(tokens[0].ttype, TokenType.ELIF_KW)
        self.assertEqual(tokens[0].raw, "elif")

    def test_else(self):
        tokens = tokenize("else")
        self.assertEqual(tokens[0].ttype, TokenType.ELSE_KW)
        self.assertEqual(tokens[0].raw, "else")

    def test_in(self):
        tokens = tokenize("in")
        self.assertEqual(tokens[0].ttype, TokenType.IN_KW)
        self.assertEqual(tokens[0].raw, "in")

    def test_continue(self):
        tokens = tokenize("continue")
        self.assertEqual(tokens[0].ttype, TokenType.CONTINUE_KW)
        self.assertEqual(tokens[0].raw, "continue")

    def test_break(self):
        tokens = tokenize("break")
        self.assertEqual(tokens[0].ttype, TokenType.BREAK_KW)
        self.assertEqual(tokens[0].raw, "break")

    def test_or_keyword(self):
        """Test 'or' is scanned as PIPE_PIPE."""
        tokens = tokenize("or")
        self.assertEqual(tokens[0].ttype, TokenType.PIPE_PIPE)
        self.assertEqual(tokens[0].raw, "or")

    def test_and_keyword(self):
        """Test 'and' is scanned as AND_AND."""
        tokens = tokenize("and")
        self.assertEqual(tokens[0].ttype, TokenType.AND_AND)
        self.assertEqual(tokens[0].raw, "and")

    def test_keyword_not_identifier_prefix(self):
        """Ensure keyword prefixes are identifiers, not keywords."""
        tokens = tokenize("classes")
        self.assertEqual(tokens[0].ttype, TokenType.IDENTIFIER)
        self.assertEqual(tokens[0].raw, "classes")

    def test_keyword_not_identifier_suffix(self):
        """Ensure keyword suffixes are identifiers, not keywords."""
        tokens = tokenize("myclass")
        self.assertEqual(tokens[0].ttype, TokenType.IDENTIFIER)
        self.assertEqual(tokens[0].raw, "myclass")


# ========== COMMENTS ==========
class TestComments(unittest.TestCase):
    """Test scanning of comments."""

    def test_single_line_comment(self):
        tokens = tokenize("// this is a comment\nx")
        self.assertEqual(tokens[0].ttype, TokenType.IDENTIFIER)
        self.assertEqual(tokens[0].raw, "x")

    def test_single_line_comment_at_end(self):
        tokens = tokenize("x // comment")
        self.assertEqual(len(tokens), 1)
        self.assertEqual(tokens[0].ttype, TokenType.IDENTIFIER)
        self.assertEqual(tokens[0].raw, "x")

    def test_multi_line_comment(self):
        tokens = tokenize("/* comment */x")
        self.assertEqual(tokens[0].ttype, TokenType.IDENTIFIER)
        self.assertEqual(tokens[0].raw, "x")

    def test_multi_line_comment_spanning_lines(self):
        tokens = tokenize("/* line1\nline2 */x")
        self.assertEqual(tokens[0].ttype, TokenType.IDENTIFIER)
        self.assertEqual(tokens[0].raw, "x")

    def test_nested_multi_line_comment(self):
        tokens = tokenize("/* outer /* inner */ outer */x")
        self.assertEqual(tokens[0].ttype, TokenType.IDENTIFIER)
        self.assertEqual(tokens[0].raw, "x")

    def test_deeply_nested_multi_line_comment(self):
        tokens = tokenize("/* a /* b /* c */ b */ a */x")
        self.assertEqual(tokens[0].ttype, TokenType.IDENTIFIER)
        self.assertEqual(tokens[0].raw, "x")

    def test_comment_between_tokens(self):
        tokens = tokenize("x /* comment */ y")
        self.assertEqual(len(tokens), 2)
        self.assertEqual(tokens[0].ttype, TokenType.IDENTIFIER)
        self.assertEqual(tokens[0].raw, "x")
        self.assertEqual(tokens[1].ttype, TokenType.IDENTIFIER)
        self.assertEqual(tokens[1].raw, "y")


# ========== LINE NUMBER TRACKING ==========
class TestLineTracking(unittest.TestCase):
    """Test that line numbers are tracked correctly."""

    def test_single_line(self):
        tokens = tokenize("x")
        self.assertEqual(tokens[0].line, 1)

    def test_newline_increments_line(self):
        tokens = tokenize("x\ny")
        self.assertEqual(tokens[0].line, 1)
        self.assertEqual(tokens[1].line, 2)

    def test_multiple_newlines(self):
        tokens = tokenize("x\n\n\ny")
        self.assertEqual(tokens[0].line, 1)
        self.assertEqual(tokens[1].line, 4)

    def test_line_tracking_with_single_line_comment(self):
        tokens = tokenize("x\n// comment\ny")
        self.assertEqual(tokens[0].line, 1)
        self.assertEqual(tokens[1].line, 3)

    def test_line_tracking_with_multi_line_comment(self):
        tokens = tokenize("x\n/* comment\nspanning\nlines */\ny")
        self.assertEqual(tokens[0].line, 1)
        self.assertEqual(tokens[1].line, 5)


# ========== EDGE CASES ==========
class TestEdgeCases(unittest.TestCase):
    """Test edge cases and whitespace handling."""

    def test_empty_source(self):
        tokens = tokenize("")
        self.assertEqual(len(tokens), 0)

    def test_whitespace_only(self):
        tokens = tokenize("   \t\n\r   ")
        self.assertEqual(len(tokens), 0)

    def test_multiple_tokens_no_space(self):
        tokens = tokenize("x+y")
        self.assertEqual(len(tokens), 3)
        self.assertEqual(tokens[0].ttype, TokenType.IDENTIFIER)
        self.assertEqual(tokens[1].ttype, TokenType.PLUS)
        self.assertEqual(tokens[2].ttype, TokenType.IDENTIFIER)

    def test_multiple_tokens_with_space(self):
        tokens = tokenize("x + y")
        self.assertEqual(len(tokens), 3)
        self.assertEqual(tokens[0].ttype, TokenType.IDENTIFIER)
        self.assertEqual(tokens[1].ttype, TokenType.PLUS)
        self.assertEqual(tokens[2].ttype, TokenType.IDENTIFIER)

    def test_multiple_spaces(self):
        tokens = tokenize("x    y")
        self.assertEqual(len(tokens), 2)
        self.assertEqual(tokens[0].raw, "x")
        self.assertEqual(tokens[1].raw, "y")

    def test_tabs(self):
        tokens = tokenize("x\ty")
        self.assertEqual(len(tokens), 2)
        self.assertEqual(tokens[0].raw, "x")
        self.assertEqual(tokens[1].raw, "y")

    def test_carriage_return(self):
        tokens = tokenize("x\ry")
        self.assertEqual(len(tokens), 2)
        self.assertEqual(tokens[0].raw, "x")
        self.assertEqual(tokens[1].raw, "y")

    def test_token_make_external(self):
        """Test Token.make_external static method."""
        token = Token.make_external("test_name")
        self.assertEqual(token.ttype, TokenType.IDENTIFIER)
        self.assertEqual(token.raw, "test_name")
        self.assertEqual(token.line, -1)
        self.assertIsNone(token.literal)

    def test_eof_token_at_end(self):
        """Test that scanner appends EOF token at end of source."""
        scanner = Scanner("x")
        tokens = scanner.scan_source()
        self.assertEqual(tokens[-1].ttype, TokenType.EOF)


# ========== INTEGRATION TESTS ==========
class TestIntegration(unittest.TestCase):
    """Test scanning of realistic code snippets."""

    def test_function_signature(self):
        source = "scope add(int a, int b) -> int"
        tokens = tokenize(source)
        expected = [
            (TokenType.SCOPE_KW, "scope"),
            (TokenType.IDENTIFIER, "add"),
            (TokenType.LEFT_PAREN, "("),
            (TokenType.IDENTIFIER, "int"),
            (TokenType.IDENTIFIER, "a"),
            (TokenType.COMMA, ","),
            (TokenType.IDENTIFIER, "int"),
            (TokenType.IDENTIFIER, "b"),
            (TokenType.RIGHT_PAREN, ")"),
            (TokenType.RETURN, "->"),
            (TokenType.IDENTIFIER, "int"),
        ]
        self.assertEqual(len(tokens), len(expected))
        for token, (expected_type, expected_raw) in zip(tokens, expected):
            self.assertEqual(token.ttype, expected_type)
            self.assertEqual(token.raw, expected_raw)

    def test_class_declaration(self):
        source = "class Foo : Bar { }"
        tokens = tokenize(source)
        expected = [
            (TokenType.CLASS_KW, "class"),
            (TokenType.IDENTIFIER, "Foo"),
            (TokenType.COLON, ":"),
            (TokenType.IDENTIFIER, "Bar"),
            (TokenType.LEFT_CURLY, "{"),
            (TokenType.RIGHT_CURLY, "}"),
        ]
        self.assertEqual(len(tokens), len(expected))
        for token, (expected_type, expected_raw) in zip(tokens, expected):
            self.assertEqual(token.ttype, expected_type)
            self.assertEqual(token.raw, expected_raw)

    def test_if_statement(self):
        source = "if x == 5 { return true; }"
        tokens = tokenize(source)
        expected = [
            (TokenType.IF_KW, "if"),
            (TokenType.IDENTIFIER, "x"),
            (TokenType.EQUAL_EQUAL, "=="),
            (TokenType.INT, "5"),
            (TokenType.LEFT_CURLY, "{"),
            (TokenType.RETURN_KW, "return"),
            (TokenType.TRUE_KW, "true"),
            (TokenType.SEMICOLON, ";"),
            (TokenType.RIGHT_CURLY, "}"),
        ]
        self.assertEqual(len(tokens), len(expected))
        for token, (expected_type, expected_raw) in zip(tokens, expected):
            self.assertEqual(token.ttype, expected_type)
            self.assertEqual(token.raw, expected_raw)

    def test_expression_with_operators(self):
        source = "a + b * c ** d"
        tokens = tokenize(source)
        expected = [
            (TokenType.IDENTIFIER, "a"),
            (TokenType.PLUS, "+"),
            (TokenType.IDENTIFIER, "b"),
            (TokenType.STAR, "*"),
            (TokenType.IDENTIFIER, "c"),
            (TokenType.STAR_STAR, "**"),
            (TokenType.IDENTIFIER, "d"),
        ]
        self.assertEqual(len(tokens), len(expected))
        for token, (expected_type, expected_raw) in zip(tokens, expected):
            self.assertEqual(token.ttype, expected_type)
            self.assertEqual(token.raw, expected_raw)

    def test_assignment_operators(self):
        source = "x += 1; y -= 2; z *= 3;"
        tokens = tokenize(source)
        expected = [
            (TokenType.IDENTIFIER, "x"),
            (TokenType.PLUS_EQUAL, "+="),
            (TokenType.INT, "1"),
            (TokenType.SEMICOLON, ";"),
            (TokenType.IDENTIFIER, "y"),
            (TokenType.MINUS_EQUAL, "-="),
            (TokenType.INT, "2"),
            (TokenType.SEMICOLON, ";"),
            (TokenType.IDENTIFIER, "z"),
            (TokenType.STAR_EQUAL, "*="),
            (TokenType.INT, "3"),
            (TokenType.SEMICOLON, ";"),
        ]
        self.assertEqual(len(tokens), len(expected))
        for token, (expected_type, expected_raw) in zip(tokens, expected):
            self.assertEqual(token.ttype, expected_type)
            self.assertEqual(token.raw, expected_raw)

    def test_logical_operators(self):
        source = "a && b || c and d or e"
        tokens = tokenize(source)
        expected = [
            (TokenType.IDENTIFIER, "a"),
            (TokenType.AND_AND, "&&"),
            (TokenType.IDENTIFIER, "b"),
            (TokenType.PIPE_PIPE, "||"),
            (TokenType.IDENTIFIER, "c"),
            (TokenType.AND_AND, "and"),
            (TokenType.IDENTIFIER, "d"),
            (TokenType.PIPE_PIPE, "or"),
            (TokenType.IDENTIFIER, "e"),
        ]
        self.assertEqual(len(tokens), len(expected))
        for token, (expected_type, expected_raw) in zip(tokens, expected):
            self.assertEqual(token.ttype, expected_type)
            self.assertEqual(token.raw, expected_raw)


if __name__ == "__main__":
    unittest.main()
