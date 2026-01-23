import sys
from scanner import Scanner
from parser import Parser
from compiler.compiler import Compiler


def main():
    if len(sys.argv) < 3:
        print("Usage: python main.py <source_file> <output_directory>")
        sys.exit(1)

    filename = sys.argv[1]

    with open(filename, "r") as f:
        source = f.read()

    scanner = Scanner(source)
    tokens = scanner.scan_source()

    parser = Parser(tokens)
    program = parser.parse()

    # Extract module name from filename (without extension)
    module_name = filename.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    package = "main"

    compiler = Compiler(program, module_name, filename, package)
    compiler.gen_program(program, sys.argv[2])


if __name__ == "__main__":
    main()
