from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Mapping

from llvmlite import ir

from compiler import compile_error
from scanner import Token


INT_TYPE = ir.IntType(64)
FLOAT_TYPE = ir.FloatType()
CHAR_TYPE = ir.IntType(8)
BOOL_TYPE = ir.IntType(1)
TRUE_VAL = ir.Constant(BOOL_TYPE, 1)
FALSE_VAL = ir.Constant(BOOL_TYPE, 0)


class Member(ABC):
    @property
    @abstractmethod
    def name(self) -> Token:
        pass


class FunctionMember(Member):
    def __init__(self, name_token: Token, llvm_func: ir.Function, param_types: list[CBType], return_type: CBType | None):
        self._name = name_token
        self.llvm_func = llvm_func
        self.param_types = param_types
        self.return_type = return_type
    
    @property
    def name(self) -> Token:
        return self._name

    def __repr__(self) -> str:
        param_str = ", ".join(pt.name.raw for pt in self.param_types)
        ret_str = self.return_type.name.raw if self.return_type else "void"
        return f"FunctionMember({self._name.raw}({param_str}) -> {ret_str})"


class VariableMember(Member):
    def __init__(self, name_token: Token, value: CBValue) -> None:
        self._name = name_token
        self.value = value
    
    @property
    def name(self) -> Token:
        return self._name
    
    def __repr__(self) -> str:
        return f"VariableMember({self.value.type.name.raw}: {self.name.raw})"


class CBType(ABC):
    @property
    @abstractmethod
    def name(self) -> Token:
        pass
    
    @property
    @abstractmethod
    def llvm_type(self) -> ir.Type:
        pass
    
    @abstractmethod
    def supports_operator(self, op: str) -> bool:
        pass
    
    @abstractmethod
    def apply_operator(self, builder: ir.IRBuilder, lhs: CBValue, op: Token, rhs: CBValue) -> CBValue:
        pass
    
    @abstractmethod
    def supports_unary_operator(self, op: str) -> bool:
        pass
    
    @abstractmethod
    def apply_unary_operator(self, builder: ir.IRBuilder, operand: CBValue, op: Token) -> CBValue:
        pass
    
    def get_member(self, name: str) -> Member | None:
        return None
    
    def has_member(self, name: str) -> bool:
        return not self.get_member(name) is None


class CBValue:
    def __init__(self, value: ir.Value, cb_type: CBType) -> None:
        self.value = value
        self.type = cb_type
    
    def __repr__(self) -> str:
        return f"CBValue({self.type.name}, {self.value})"


class UserType(CBType):
    def __init__(self, name: Token, members: Mapping[str, Member] | None = None) -> None:
        self.user_name = name
        self._members: dict[str, Member] = dict(members) if members else {}
        self._llvm_type: ir.Type | None = None
    
    @property
    def name(self) -> Token:
        return self.user_name
    
    @property
    def llvm_type(self) -> ir.Type:
        if self._llvm_type is None:
            # For now, just create an empty struct - this can be enhanced later
            self._llvm_type = ir.LiteralStructType([])
        return self._llvm_type
    
    def get_member(self, name: str) -> Member | None:
        return self._members.get(name)
    
    def add_member(self, member: Member) -> None:
        """Add a member to this type."""
        self._members[member.name.raw] = member
    
    def supports_operator(self, op: str) -> bool:
        return False  # Custom operators can be added later
    
    def apply_operator(self, builder: ir.IRBuilder, lhs: CBValue, op: Token, rhs: CBValue) -> CBValue:
        raise compile_error(op, f"Operator '{op.raw}' not supported by class '{self.name}'.")
    
    def supports_unary_operator(self, op: str) -> bool:
        return False  # Custom operators can be added later
    
    def apply_unary_operator(self, builder: ir.IRBuilder, operand: CBValue, op: Token) -> CBValue:
        raise compile_error(op, f"Unary operator '{op.raw}' not supported by class '{self.name}'.")


class IntType(CBType):
    @property
    def name(self) -> Token:
        return Token.make_external("int")
    
    @property
    def llvm_type(self) -> ir.Type:
        return INT_TYPE
    
    def supports_operator(self, op: str) -> bool:
        return op in ("+", "-", "*", "/", "%", "==", "!=", "<", ">", "<=", ">=")
    
    def supports_unary_operator(self, op: str) -> bool:
        return op == "-"
    
    def apply_unary_operator(self, builder: ir.IRBuilder, operand: CBValue, op: Token) -> CBValue:
        if op.raw == "-":
            result = builder.neg(operand.value)
            return CBValue(result, self)  # pyright: ignore[reportArgumentType]
        else:
            raise compile_error(op, f"Unary operator '{op.raw}' not supported by 'int' type.")
    
    def apply_operator(self, builder: ir.IRBuilder, lhs: CBValue, op: Token, rhs: CBValue) -> CBValue:
        lhs_val, rhs_val = lhs.value, rhs.value
        
        if op.raw == "+":
            result = builder.add(lhs_val, rhs_val)
        elif op.raw == "-":
            result = builder.sub(lhs_val, rhs_val)
        elif op.raw == "*":
            result = builder.mul(lhs_val, rhs_val)
        elif op.raw == "/":
            result = builder.sdiv(lhs_val, rhs_val)
        elif op.raw == "%":
            result = builder.srem(lhs_val, rhs_val)
        elif op.raw == "==":
            result = builder.icmp_signed("==", lhs_val, rhs_val)
            return CBValue(result, CB_BOOL)  # pyright: ignore[reportReturnType]
        elif op.raw == "!=":
            result = builder.icmp_signed("!=", lhs_val, rhs_val)
            return CBValue(result, CB_BOOL)  # pyright: ignore[reportReturnType]
        elif op.raw == "<":
            result = builder.icmp_signed("<", lhs_val, rhs_val)
            return CBValue(result, CB_BOOL)  # pyright: ignore[reportReturnType]
        elif op.raw == ">":
            result = builder.icmp_signed(">", lhs_val, rhs_val)
            return CBValue(result, CB_BOOL)  # pyright: ignore[reportReturnType]
        elif op.raw == "<=":
            result = builder.icmp_signed("<=", lhs_val, rhs_val)
            return CBValue(result, CB_BOOL)  # pyright: ignore[reportReturnType]
        elif op.raw == ">=":
            result = builder.icmp_signed(">=", lhs_val, rhs_val)
            return CBValue(result, CB_BOOL)  # pyright: ignore[reportArgumentType]
        else:
            raise compile_error(op, f"Operator '{op.raw}' not supported by 'int' type.")
        
        return CBValue(result, self)  # pyright: ignore[reportArgumentType, reportPossiblyUnbound]


class FloatType(CBType):
    @property
    def name(self) -> Token:
        return Token.make_external("float")
    
    @property
    def llvm_type(self) -> ir.Type:
        return FLOAT_TYPE
    
    def supports_operator(self, op: str) -> bool:
        return op in ("+", "-", "*", "/", "==", "!=", "<", ">", "<=", ">=")
    
    def supports_unary_operator(self, op: str) -> bool:
        return op == "-"
    
    def apply_unary_operator(self, builder: ir.IRBuilder, operand: CBValue, op: Token) -> CBValue:
        if op.raw == "-":
            result = builder.fneg(operand.value)
            return CBValue(result, self)  # pyright: ignore[reportArgumentType]
        else:
            raise compile_error(op, f"Unary operator '{op.raw}' not supported by 'float' type.")
    
    def apply_operator(self, builder: ir.IRBuilder, lhs: CBValue, op: Token, rhs: CBValue) -> CBValue:
        lhs_val, rhs_val = lhs.value, rhs.value
        
        if op.raw == "+":
            result = builder.fadd(lhs_val, rhs_val)
        elif op.raw == "-":
            result = builder.fsub(lhs_val, rhs_val)
        elif op.raw == "*":
            result = builder.fmul(lhs_val, rhs_val)
        elif op.raw == "/":
            result = builder.fdiv(lhs_val, rhs_val)
        elif op.raw == "==":
            result = builder.fcmp_ordered("==", lhs_val, rhs_val)
            return CBValue(result, CB_BOOL)  # pyright: ignore[reportReturnType]
        elif op.raw == "!=":
            result = builder.fcmp_ordered("!=", lhs_val, rhs_val)
            return CBValue(result, CB_BOOL)  # pyright: ignore[reportReturnType]
        elif op.raw == "<":
            result = builder.fcmp_ordered("<", lhs_val, rhs_val)
            return CBValue(result, CB_BOOL)  # pyright: ignore[reportReturnType]
        elif op.raw == ">":
            result = builder.fcmp_ordered(">", lhs_val, rhs_val)
            return CBValue(result, CB_BOOL)  # pyright: ignore[reportReturnType]
        elif op.raw == "<=":
            result = builder.fcmp_ordered("<=", lhs_val, rhs_val)
            return CBValue(result, CB_BOOL)  # pyright: ignore[reportReturnType]
        elif op.raw == ">=":
            result = builder.fcmp_ordered(">=", lhs_val, rhs_val)
            return CBValue(result, CB_BOOL)  # pyright: ignore[reportArgumentType]
        else:
            raise compile_error(op, f"Operator '{op.raw}' not supported by 'float' type.")
        
        return CBValue(result, self)  # pyright: ignore[reportArgumentType, reportPossiblyUnbound]


class CharType(CBType):
    @property
    def name(self) -> Token:
        return Token.make_external("char")
    
    @property
    def llvm_type(self) -> ir.Type:
        return CHAR_TYPE
    
    def supports_operator(self, op: str) -> bool:
        return op in ("==", "!=")
    
    def supports_unary_operator(self, op: str) -> bool:
        return False
    
    def apply_unary_operator(self, builder: ir.IRBuilder, operand: CBValue, op: Token) -> CBValue:
        raise compile_error(op, f"Unary operator '{op.raw}' not supported by 'char' type.")
    
    def apply_operator(self, builder: ir.IRBuilder, lhs: CBValue, op: Token, rhs: CBValue) -> CBValue:
        lhs_val, rhs_val = lhs.value, rhs.value
        
        if op.raw == "==":
            result = builder.icmp_unsigned("==", lhs_val, rhs_val)
            return CBValue(result, CB_BOOL)  # pyright: ignore[reportReturnType]
        elif op.raw == "!=":
            result = builder.icmp_unsigned("!=", lhs_val, rhs_val)
            return CBValue(result, CB_BOOL)  # pyright: ignore[reportReturnType]
        else:
            raise compile_error(op, f"Operator '{op.raw}' not supported by 'char' type.")


class BoolType(CBType):
    @property
    def name(self) -> Token:
        return Token.make_external("bool")
    
    @property
    def llvm_type(self) -> ir.Type:
        return BOOL_TYPE
    
    def supports_operator(self, op: str) -> bool:
        return op in ("==", "!=", "&&", "||")
    
    def supports_unary_operator(self, op: str) -> bool:
        return op == "!"
    
    def apply_unary_operator(self, builder: ir.IRBuilder, operand: CBValue, op: Token) -> CBValue:
        if op.raw == "!":
            result = builder.not_(operand.value)
            return CBValue(result, self)  # pyright: ignore[reportArgumentType]
        else:
            raise compile_error(op, f"Unary operator '{op.raw}' not supported by 'bool' type.")
    
    def apply_operator(self, builder: ir.IRBuilder, lhs: CBValue, op: Token, rhs: CBValue) -> CBValue:
        lhs_val, rhs_val = lhs.value, rhs.value
        
        if op.raw == "==":
            result = builder.icmp_unsigned("==", lhs_val, rhs_val)
        elif op.raw == "!=":
            result = builder.icmp_unsigned("!=", lhs_val, rhs_val)
        elif op.raw == "&&":
            result = builder.and_(lhs_val, rhs_val)
        elif op.raw == "||":
            result = builder.or_(lhs_val, rhs_val)
        else:
            raise compile_error(op, f"Operator '{op.raw}' not supported by 'bool' type.")
        
        return CBValue(result, self)  # pyright: ignore[reportArgumentType, reportPossiblyUnbound]


class StringType(CBType):
    def __init__(self, length: int = 0) -> None:
        self._length = length
    
    @property
    def name(self) -> Token:
        return Token.make_external("string")
    
    @property
    def llvm_type(self) -> ir.Type:
        return ir.ArrayType(CHAR_TYPE, self._length)
    
    def supports_operator(self, op: str) -> bool:
        return False  # String operators would need runtime support
    
    def apply_operator(self, builder: ir.IRBuilder, lhs: CBValue, op: Token, rhs: CBValue) -> CBValue:
        raise compile_error(op, f"Operator '{op.raw}' not supported by 'string' type.")
    
    def supports_unary_operator(self, op: str) -> bool:
        return False
    
    def apply_unary_operator(self, builder: ir.IRBuilder, operand: CBValue, op: Token) -> CBValue:
        raise compile_error(op, f"Unary operator '{op.raw}' not supported by 'string' type.")


# Singleton instances for primitive types
CB_INT = IntType()
CB_FLOAT = FloatType()
CB_CHAR = CharType()
CB_BOOL = BoolType()