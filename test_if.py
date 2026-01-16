from __future__ import annotations
from scanner import Scanner
from parser import Parser
from compiler import Compiler

# Test simple if statement
test_code = """
if (true) {
    1 + 1;
}
"""


def test_basic_if():
    scanner = Scanner(test_code)
    tokens = scanner.scan_tokens()
    parser = Parser(tokens)
    ast = parser.parse()

    compiler = Compiler(ast)
    llvm_module = compiler.generate_code()

    print("Generated LLVM IR:")
    print(str(llvm_module))
    return True


if __name__ == "__main__":
    test_basic_if()
