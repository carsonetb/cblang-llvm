from __future__ import annotations
from dataclasses import dataclass
from enum import Enum, auto


class TokenType(Enum):
    # Single character
    LEFT_PAREN = auto()
    RIGHT_PAREN = auto()
    LEFT_BRACKET = auto()
    RIGHT_BRACKET = auto()
    LEFT_CURLY = auto()
    RIGHT_CURLY = auto()
    LEFT_ANGLE = auto()
    RIGHT_ANGLE = auto()
    COMMA = auto()
    DOT = auto()
    MINUS = auto()
    PLUS = auto()
    SLASH = auto()
    STAR = auto()
    SEMICOLON = auto()
    COLON = auto()
    BANG = auto()
    EQUAL = auto()
    CARET = auto()
    MODULO = auto()
    PIPE = auto()
    # Two character
    BANG_EQUAL = auto()
    EQUAL_EQUAL = auto()
    GREATER_EQUAL = auto()
    LESS_EQUAL = auto()
    STAR_STAR = auto()
    RETURN = auto()
    PLUS_EQUAL = auto()
    MINUS_EQUAL = auto()
    STAR_EQUAL = auto()
    STAR_STAR_EQUAL = auto()
    SLASH_EQUAL = auto()
    CARET_EQUAL = auto()
    MODULO_EQUAL = auto()
    PIPE_EQUAL = auto()
    PIPE_PIPE = auto()
    AND_AND = auto()
    # Literals
    IDENTIFIER = auto()
    STRING = auto()
    CHARACTER = auto()
    FLOAT = auto()
    INT = auto()
    # Keywords
    CLASS_KW = auto()
    SCOPE_KW = auto()
    TRUE_KW = auto()
    FALSE_KW = auto()
    PRIVATE_KW = auto()
    STATIC_KW = auto()
    CONST_KW = auto()
    OPERATOR_KW = auto()
    CAST_KW = auto()
    SUPER_KW = auto()
    RETURN_KW = auto()
    IMPORT_KW = auto()
    IF_KW = auto()
    ELIF_KW = auto()
    ELSE_KW = auto()
    FOR_KW = auto()
    WHILE_KW = auto()
    IN_KW = auto()
    CONTINUE_KW = auto()
    BREAK_KW = auto()
    ERROR = auto()
    EOF = auto()


@dataclass 
class CodePosition:
    line: int 
    col: int 

    def __repr__(self) -> str:
        return f"({self.line}:{self.col})"


@dataclass
class Token:
    ttype: TokenType
    literal: int | float | str | bool | None
    raw: str
    pos: CodePosition

    @staticmethod
    def make_external(raw: str) -> Token:
        return Token(TokenType.IDENTIFIER, None, raw, CodePosition(-1, -1))
    
    def __repr__(self) -> str:
        return self.raw
    
    def __str__(self) -> str:
        return self.raw


class Scanner:
    def __init__(self, source: str) -> None:
        self.source = source + " "
        self.start: int = 0
        self.current: int = 0
        self.line: int = 1
        self.col: int = 1
        self.tokens: list[Token] = []

    @staticmethod
    def is_alphanumeric(character: str) -> bool:
        return character.isnumeric() or character.isalpha() or character == "_"

    def scan_token(self):
        character = self.advance()

        if self.is_at_end():
            self.add_token(TokenType.EOF)
            return

        match character:
            case " ":
                self.col += 1
            case "\r":
                pass
            case "\t":
                self.col += 4
            case "\n":
                self.line += 1
                self.col = 1
            case "(":
                self.add_token(TokenType.LEFT_PAREN)
            case ")":
                self.add_token(TokenType.RIGHT_PAREN)
            case "{":
                self.add_token(TokenType.LEFT_CURLY)
            case "}":
                self.add_token(TokenType.RIGHT_CURLY)
            case "[":
                self.add_token(TokenType.LEFT_BRACKET)
            case "]":
                self.add_token(TokenType.RIGHT_BRACKET)
            case ";":
                self.add_token(TokenType.SEMICOLON)
            case ",":
                self.add_token(TokenType.COMMA)
            case ".":
                self.add_token(TokenType.DOT)
            case ":":
                self.add_token(TokenType.COLON)
            case "+":
                self.add_token(
                    TokenType.PLUS_EQUAL if self.match("=") else TokenType.PLUS
                )
            case "^":
                self.add_token(
                    TokenType.CARET_EQUAL if self.match("=") else TokenType.CARET
                )
            case "%":
                self.add_token(
                    TokenType.MODULO_EQUAL if self.match("=") else TokenType.MODULO
                )
            case "!":
                self.add_token(
                    TokenType.BANG_EQUAL if self.match("=") else TokenType.BANG
                )
            case "=":
                self.add_token(
                    TokenType.EQUAL_EQUAL if self.match("=") else TokenType.EQUAL
                )
            case "<":
                self.add_token(
                    TokenType.LESS_EQUAL if self.match("=") else TokenType.LEFT_ANGLE
                )
            case ">":
                self.add_token(
                    TokenType.GREATER_EQUAL
                    if self.match("=")
                    else TokenType.RIGHT_ANGLE
                )
            case "|":
                if self.match("|"):
                    self.add_token(TokenType.PIPE_PIPE)
                elif self.match("="):
                    self.add_token(TokenType.PIPE_EQUAL)
                else:
                    self.add_token(TokenType.PIPE)
            case "&":
                if self.match("&"):
                    self.add_token(TokenType.AND_AND)
            case "-":
                if self.match(">"):
                    self.add_token(TokenType.RETURN)
                elif self.match("="):
                    self.add_token(TokenType.MINUS_EQUAL)
                else:
                    self.add_token(TokenType.MINUS)
            case "*":
                if self.match("*"):
                    if self.match("="):
                        self.add_token(TokenType.STAR_STAR_EQUAL)
                    else:
                        self.add_token(TokenType.STAR_STAR)
                elif self.match("="):
                    self.add_token(TokenType.STAR_EQUAL)
                else:
                    self.add_token(TokenType.STAR)
            case "/":
                if self.match("="):
                    self.add_token(TokenType.SLASH_EQUAL)
                elif self.match("/"):
                    while self.peek() != "\n" and not self.is_at_end():
                        self.advance()
                elif self.match("*"):
                    depth = 1
                    while True:
                        if self.peek() == "\n":
                            self.line += 1
                            self.advance()
                            continue
                        if self.peek() == "/" and self.peek(1) == "*":
                            depth += 1
                            self.advance()
                            self.advance()
                        elif self.peek() == "*" and self.peek(1) == "/":
                            depth -= 1
                            self.advance()
                            self.advance()
                            if depth == 0:
                                break
                        else:
                            self.advance()
                        if self.is_at_end():
                            self.error("Unterminated multi-line comment.")
                            return
                else:
                    self.add_token(TokenType.SLASH)
            case "'":
                char = self.advance()
                if char == "'":
                    self.error("No character after '")
                    return

                if not self.match("'"):
                    self.error("Characters must only have one character.")
                    return

                self.add_token(TokenType.CHARACTER, char)
            case '"':
                string = ""
                while not self.is_at_end() and self.peek() != '"':
                    if self.match("\\"):
                        if self.match("\\"):
                            string += "\\"
                        elif self.match("n"): # Down the rabbit hole...
                            string += "\n"
                        elif self.match("t"):
                            string += "\t"
                        else:
                            self.error("Unsupported escape sequence.")
                        continue

                    string += self.advance()

                if self.is_at_end():
                    self.error("Unterminated string.")
                    return

                self.advance()
                self.add_token(TokenType.STRING, string)
            case _:
                if character.isalpha() or character == "_":
                    self.identifier()
                elif character.isnumeric():
                    self.number()

    @property
    def keywords(self) -> dict[str, TokenType]:
        return {
            "class": TokenType.CLASS_KW,
            "scope": TokenType.SCOPE_KW,
            "true": TokenType.TRUE_KW,
            "false": TokenType.FALSE_KW,
            "private": TokenType.PRIVATE_KW,
            "static": TokenType.STATIC_KW,
            "const": TokenType.CONST_KW,
            "operator": TokenType.OPERATOR_KW,
            "cast": TokenType.CAST_KW,
            "super": TokenType.SUPER_KW,
            "return": TokenType.RETURN_KW,
            "import": TokenType.IMPORT_KW,
            "if": TokenType.IF_KW,
            "elif": TokenType.ELIF_KW,
            "else": TokenType.ELSE_KW,
            "in": TokenType.IN_KW,
            "continue": TokenType.CONTINUE_KW,
            "break": TokenType.BREAK_KW,
            "or": TokenType.PIPE_PIPE,
            "and": TokenType.AND_AND,
            "for": TokenType.FOR_KW,
            "while": TokenType.WHILE_KW,
        }

    def identifier(self) -> None:
        while self.is_alphanumeric(self.peek()):
            self.advance()

        text = self.get_token_raw()
        if self.keywords.get(text):
            self.add_token(self.keywords[text])
        else:
            self.add_token(TokenType.IDENTIFIER)

    def number(self) -> None:
        while self.peek().isnumeric():
            self.advance()

        if not self.peek() == ".":
            self.add_token(TokenType.INT, int(self.get_token_raw()))
            return

        self.advance()  # consume the decimal point

        while self.peek().isnumeric():
            self.advance()

        self.add_token(TokenType.FLOAT, float(self.get_token_raw()))

    def add_token(
        self, ttype: TokenType, literal: int | float | str | bool | None = None
    ):
        self.tokens.append(Token(ttype, literal, self.get_token_raw(), CodePosition(self.line, self.col)))
        self.col += len(self.tokens[-1].raw)

    def scan_source(self) -> list[Token]:
        while not self.is_at_end():
            self.start = self.current
            self.scan_token()

        return self.tokens

    def peek(self, amount: int = 0) -> str:
        if self.current + amount >= len(self.source):
            return "\0"
        return self.source[self.current + amount]

    def match(self, character: str, amount: int = 0) -> bool:
        if self.peek(amount) == character:
            self.advance()
            return True
        return False

    def advance(self) -> str:
        out = self.source[self.current]
        self.current += 1
        return out

    def is_at_end(self) -> bool:
        return self.current >= len(self.source)

    def get_token_raw(self) -> str:
        return self.source[self.start : self.current]

    def error(self, msg: str) -> None:
        print(f"Scanner Error: {msg}")
        self.add_token(TokenType.ERROR)
