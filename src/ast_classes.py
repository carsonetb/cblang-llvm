from __future__ import annotations
from abc import ABC, abstractmethod
from enum import Enum, auto

from scanner import Token, dataclass
import llvmlite.ir as ir


@dataclass
class Statement(ABC):
    pass


@dataclass
class Expression(Statement):
    pass


class LiteralType(Enum):
    INT = auto()
    FLOAT = auto()
    CHAR = auto()
    STRING = auto()
    BOOL = auto()


class MemberFlag(Enum):
    PRIVATE = auto()
    STATIC = auto()
    CONST = auto()


class FunctionFlag(Enum):
    CAST = auto()
    OPERATOR = auto()


@dataclass
class LiteralExpr(Expression):
    ltype: LiteralType
    val: int | float | str | bool
    token: Token


@dataclass
class Accessible(Expression):
    access: Accessible | None


@dataclass
class VariableExpr(Accessible):
    name: Token


@dataclass
class CallExpr(Accessible):
    callee: Token
    args: list[Expression]


@dataclass
class BinaryExpr(Expression):
    lhs: Expression
    op: Token
    rhs: Expression


@dataclass 
class UnaryExpr(Expression):
    op: Token
    rhs: Expression


@dataclass 
class Grouping(Expression):
    expr: Expression


@dataclass
class ArrayExpr(Expression):
    array_end: Token
    elements: list[Expression]


@dataclass 
class LambdaExpr(Expression):
    body: list[Statement]


@dataclass
class ScopeStmt(Statement):
    body: list[Statement]


@dataclass
class Import(Statement):
    path: list[Token]


@dataclass
class VarDecl(Statement):
    type_name: tuple[Token, Token]
    value: Expression | None
    flags: set[MemberFlag]


@dataclass
class AssignmentStmt(Statement):
    target: Accessible
    value: Expression


@dataclass
class ReturnStmt(Statement):
    value: Expression | None


@dataclass
class IfStmt(Statement):
    condition: Expression
    body: ScopeStmt
    else_branch: IfStmt | ElseStmt | None


@dataclass
class ElseStmt(Statement):
    body: ScopeStmt


@dataclass
class WhileStmt(Statement):
    condition: Expression
    body: list[Statement]


@dataclass
class ForStmt(Statement):
    var_type_name: tuple[Token, Token]
    iterable: Expression
    body: list[Statement]


@dataclass
class Function(Statement):
    name: Token
    args: list[tuple[Token, Token]]
    returns: Token | None
    body: list[Statement]
    member_flags: set[MemberFlag]
    function_flags: set[FunctionFlag]


@dataclass
class Class(Statement):
    name: Token
    args: list[tuple[Token, Token]]
    members: list[Class | Function | VarDecl]


@dataclass
class Program:
    imports: list[Import]
    statements: list[Statement]