# AGENTS.md - Cblang LLVM Compiler

Guidelines for AI agents working in this codebase.

## Project Overview

This is **cblang** - a custom programming language compiler written in Python that targets LLVM IR via `llvmlite`. The language is statically-typed with class-based OOP, C-like syntax, and features like operator overloading and type casting.

### Architecture

```
Source Code → Scanner → Tokens → Parser → AST → Compiler → LLVM IR
```

| File | Purpose |
|------|---------|
| `scanner.py` | Lexer/tokenizer - converts source text to tokens |
| `parser.py` | Recursive descent parser - converts tokens to AST |
| `ast_classes.py` | AST node definitions using dataclasses |
| `builtin_types.py` | Type system (int, float, char, bool, string) and LLVM type mappings |
| `compiler.py` | Code generator - converts AST to LLVM IR |
| `doc/ast-spec.txt` | BNF-like grammar specification |

## Build & Test Commands

### Environment Setup
```bash
source .venv/bin/activate
```

### Dependencies
- `llvmlite==0.46.0`, `lark-parser==0.12.0`, `pymlir==0.5`, Python 3.13+

### Running Tests
```bash
python -m unittest discover              # Run all tests
python -m unittest test_scanner          # Run a specific test file
python -m unittest test_scanner.TestScanner                    # Specific test class
python -m unittest test_scanner.TestScanner.test_single_char_tokens  # Single test
python -m unittest -v test_scanner       # Verbose output
```

### Type Checking
```bash
pyright .
```

## Code Style Guidelines

### Imports
Order: 1) `from __future__ import annotations`, 2) stdlib, 3) third-party, 4) local

```python
from __future__ import annotations
from abc import ABC, abstractmethod
from llvmlite import ir
from scanner import Token
```

### Naming Conventions
| Type | Convention | Examples |
|------|------------|----------|
| Classes | PascalCase | `Scanner`, `TokenType`, `BinaryExpr`, `CBValue` |
| Functions/Methods | snake_case | `gen_expr`, `scan_token`, `apply_operator` |
| Variables | snake_case | `lhs_val`, `return_type`, `param_types` |
| Constants | UPPER_SNAKE_CASE | `INT_TYPE`, `FLOAT_TYPE`, `TRUE_VAL` |
| Private attributes | underscore prefix | `self._name`, `self._members` |
| Enum members | UPPER_SNAKE_CASE | `LEFT_PAREN`, `CLASS_KW` |

### Type Annotations
- Use type hints on ALL function signatures
- Use `|` for union types: `CBValue | None`
- Use lowercase generics: `list[T]`, `dict[K, V]`
- Use `# pyright: ignore` for unavoidable warnings

```python
def gen_expr(self, expr: Expression) -> CBValue | None:
    ...
```

### Dataclasses
Use `@dataclass` for AST nodes:
```python
@dataclass
class BinaryExpr(Expression):
    lhs: Expression
    op: Token
    rhs: Expression
```

### Error Handling
```python
def compile_error(token: Token, msg: str) -> RuntimeError:
    print(f"@Compiler [line {token.line}] [token {token.raw}] [ERROR] {msg}")
    return RuntimeError()

# Always raise the returned exception
raise compile_error(expr.op, f"Type mismatch: cannot apply '{expr.op.raw}'")
```

### Documentation
Use reStructuredText docstrings:
```python
def gen_expr(self, expr: Expression) -> CBValue | None:
    """
    Switch that calls other functions based on the subtype.
    
    :param expr: The expression to evaluate, must be of a subtype.
    :type expr: Expression
    :return: The evaluated type joined with the llvmlite Value.
    :rtype: CBValue | None
    """
```

### Code Organization
Use section dividers:
```python
# ========== STATEMENTS ==========
def statement(self) -> Statement:
    ...
```

### Pattern Matching
Use `isinstance()` for AST dispatch, `match` for simple tokens:
```python
if isinstance(expr, LiteralExpr):
    return self.gen_literal(expr)
elif isinstance(expr, BinaryExpr):
    return self.gen_binary_expr(expr)
```

## LLVM IR Patterns

### Type Constants
```python
INT_TYPE = ir.IntType(64)
FLOAT_TYPE = ir.FloatType()
CHAR_TYPE = ir.IntType(8)
BOOL_TYPE = ir.IntType(1)
TRUE_VAL = ir.Constant(BOOL_TYPE, 1)
FALSE_VAL = ir.Constant(BOOL_TYPE, 0)
```

### Building IR
```python
result = self.builder.fadd(lhs.value, rhs.value)
result = self.builder.icmp_signed('==', lhs.value, rhs.value)
result = self.builder.call(member.llvm_func, args)
```

## The CB Language

Key features:
- Classes with inheritance: `class Foo : Bar { ... }`
- Functions: `scope funcName(Type param) -> ReturnType { ... }`
- Modifiers: `private`, `static`, `const`, `cast`, `operator`
- Control flow: `if/elif/else`, `while`, `for...in`
- Types: `int`, `float`, `char`, `string`, `bool`
- Comments: `//` single-line, `/* */` multi-line (nested)
