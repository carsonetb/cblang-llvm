from ast_classes import (
    ArrayExpr, AssignmentStmt, BinaryExpr, CallExpr, Class, ElseStmt,
    Expression, ForStmt, Function, FunctionFlag, Grouping, IfStmt, Import,
    LiteralExpr, LiteralType, MemberFlag, Program, ReturnStmt, ScopeStmt,
    Statement, UnaryExpr, VarDecl, VariableExpr, WhileStmt
)
from scanner import Token, TokenType


class ParseException(RuntimeError):
    pass


class Parser:
    ALL_FLAGS = (TokenType.PRIVATE_KW, TokenType.STATIC_KW, TokenType.CONST_KW, TokenType.CAST_KW, TokenType.OPERATOR_KW)

    def __init__(self, tokens: list[Token]) -> None:
        self.tokens = tokens
        self.current = 0
    
    def parse(self) -> Program: 
        imports: list[Import] = []
        statements: list[Statement] = []

        while self.match(TokenType.IMPORT_KW):
            imports.append(self.import_statement())
            self.consume_semicolon()
        
        while not self.check(TokenType.EOF):
            statements.append(self.statement())

        return Program(imports, statements)
    
    def import_statement(self) -> Import:
        path: list[Token] = [self.consume(TokenType.IDENTIFIER, "Expected start of module path after 'import'")]
        while self.match(TokenType.DOT):
            path.append(self.consume(TokenType.IDENTIFIER, "Expected module path item after '.' in import statement"))
        return Import(path)
    
    # ========== STATEMENTS ==========
    
    def statement(self) -> Statement:
        """
        Handles all statements. Defers to `semicolon_statement`
        to handle statements that need to end in a semicolon.
        """

        if self.check(TokenType.IF_KW):
            return self.if_stmt()
        if self.check(TokenType.WHILE_KW):
            return self.while_stmt()
        if self.check(TokenType.FOR_KW):
            return self.for_stmt()
        
        # Need to look ahead past any flags to see if it's a function (scope) or not
        if self.check_flags():
            lookahead = 1
            while self.peek(lookahead).ttype in (TokenType.PRIVATE_KW, TokenType.STATIC_KW, 
                                                   TokenType.CONST_KW, TokenType.CAST_KW, 
                                                   TokenType.OPERATOR_KW):
                lookahead += 1
            if self.peek(lookahead).ttype == TokenType.SCOPE_KW:
                return self.function_decl()
            # Otherwise fall through to semicolon_statement for var decl
        elif self.check(TokenType.SCOPE_KW):
            return self.function_decl()
        
        if self.check(TokenType.CLASS_KW):
            return self.class_decl()
        
        return self.semicolon_statement()
    
    def semicolon_statement(self) -> Statement:
        # For empty statements just return an empty Scope.
        # Kind of a hack.
        if self.match(TokenType.SEMICOLON):
            return ScopeStmt([])
        
        if self.match(TokenType.RETURN_KW):
            value: Expression | None = None
            if not self.check(TokenType.SEMICOLON):
                value = self.expression()
            self.consume_semicolon()
            return ReturnStmt(value)
        
        # Declaration of a variable: (flags)? IDENTIFIER IDENTIFIER
        # Need to look past any flags to find the type and name identifiers
        if self.check_var_decl():
            return self.var_decl()
        
        # Either the expression that is plain evaluated or this
        # is an Accessible that will be set.
        expr = self.expression()
        
        if self.match(TokenType.EQUAL):
            if not isinstance(expr, (VariableExpr, CallExpr)):
                raise self.error(self.previous(), "Invalid assignment target")
            value = self.expression()
            self.consume_semicolon()
            return AssignmentStmt(expr, value)
        
        self.consume_semicolon()
        return expr
    
    def var_decl(self) -> VarDecl:
        flags = self.member_flags()
        type_token = self.consume(TokenType.IDENTIFIER, "Expected type name")
        name_token = self.consume(TokenType.IDENTIFIER, "Expected variable name")
        
        value: Expression | None = None
        if self.match(TokenType.EQUAL):
            value = self.expression()
        
        self.consume_semicolon()
        return VarDecl((type_token, name_token), value, flags)
    
    def if_stmt(self, use_elif_kw: bool = False) -> IfStmt:
        statement_name = "elif" if use_elif_kw else "if"
        self.consume(TokenType.ELIF_KW if use_elif_kw else TokenType.IF_KW, f"Expected '{statement_name}'")
        self.consume(TokenType.LEFT_PAREN, f"Expected '(' after {statement_name}")
        condition = self.expression()
        self.consume(TokenType.RIGHT_PAREN, f"Expected ')' after {statement_name} condition")
        
        self.consume(TokenType.LEFT_CURLY, f"Expected '{{' before {statement_name} body")
        body = self.scope_body()
        self.consume(TokenType.RIGHT_CURLY, f"Expected '}}' after {statement_name} body")
        
        else_branch: IfStmt | ElseStmt | None = None
        if self.match(TokenType.ELIF_KW):
            # Parse elif as an IfStmt (rewind so elif_stmt can consume it)
            self.current -= 1
            else_branch = self.if_stmt(True)
        elif self.match(TokenType.ELSE_KW):
            self.consume(TokenType.LEFT_CURLY, "Expected '{' after 'else'")
            else_body = self.scope_body()
            self.consume(TokenType.RIGHT_CURLY, "Expected '}' after else body")
            else_branch = ElseStmt(ScopeStmt(else_body))
        
        return IfStmt(condition, ScopeStmt(body), else_branch)
    
    def while_stmt(self) -> WhileStmt:
        self.consume(TokenType.WHILE_KW, "Expected 'while'")
        self.consume(TokenType.LEFT_PAREN, "Expected '(' after 'while'")
        condition = self.expression()
        self.consume(TokenType.RIGHT_PAREN, "Expected ')' after while condition")
        
        self.consume(TokenType.LEFT_CURLY, "Expected '{' before while body")
        body = self.scope_body()
        self.consume(TokenType.RIGHT_CURLY, "Expected '}' after while body")
        
        return WhileStmt(condition, body)
    
    def for_stmt(self) -> ForStmt:
        self.consume(TokenType.FOR_KW, "Expected 'for'")
        self.consume(TokenType.LEFT_PAREN, "Expected '(' after 'for'")
        
        var_type = self.consume(TokenType.IDENTIFIER, "Expected type in for loop")
        var_name = self.consume(TokenType.IDENTIFIER, "Expected variable name in for loop")
        self.consume(TokenType.IN_KW, "Expected 'in' in for loop")
        iterable = self.expression()
        
        self.consume(TokenType.RIGHT_PAREN, "Expected ')' after for loop header")
        
        self.consume(TokenType.LEFT_CURLY, "Expected '{' before for body")
        body = self.scope_body()
        self.consume(TokenType.RIGHT_CURLY, "Expected '}' after for body")
        
        return ForStmt((var_type, var_name), iterable, body)
    
    def scope_body(self) -> list[Statement]:
        statements: list[Statement] = []
        while not self.check(TokenType.RIGHT_CURLY) and not self.check(TokenType.EOF):
            statements.append(self.statement())
        return statements
    
    # ========== DECLARATIONS ==========
    
    def function_decl(self) -> Function:
        member_flags, func_flags = self.function_flags()
        
        self.consume(TokenType.SCOPE_KW, "Expected 'scope' keyword")
        name = self.consume(TokenType.IDENTIFIER, "Expected function name")
        
        # Optional parameters
        args: list[tuple[Token, Token]] = []
        if self.match(TokenType.LEFT_PAREN):
            if not self.check(TokenType.RIGHT_PAREN):
                args = self.parameters()
            self.consume(TokenType.RIGHT_PAREN, "Expected ')' after parameters")
        
        # Optional return type
        returns: Token | None = None
        if self.match(TokenType.RETURN):
            returns = self.consume(TokenType.IDENTIFIER, "Expected return type after '->'")
        
        self.consume(TokenType.EQUAL, "Expected '=' before function body")
        self.consume(TokenType.LEFT_CURLY, "Expected '{' to start function body")
        body = self.scope_body()
        self.consume(TokenType.RIGHT_CURLY, "Expected '}' to end function body")
        
        return Function(name, args, returns, body, member_flags, func_flags)
    
    def class_decl(self) -> Class:
        self.consume(TokenType.CLASS_KW, "Expected 'class' keyword")
        name = self.consume(TokenType.IDENTIFIER, "Expected class name")
        
        if self.match(TokenType.COLON):
            self.consume(TokenType.IDENTIFIER, "Expected parent class name")
            while self.match(TokenType.COMMA):
                self.consume(TokenType.IDENTIFIER, "Expected parent class name")
        
        args: list[tuple[Token, Token]] = []
        if self.match(TokenType.LEFT_PAREN):
            if not self.check(TokenType.RIGHT_PAREN):
                args = self.parameters()
            self.consume(TokenType.RIGHT_PAREN, "Expected ')' after class parameters")
        
        self.consume(TokenType.EQUAL, "Expected '=' before class body")
        self.consume(TokenType.LEFT_PAREN, "Expected '(' to start class body")
        
        members: list[Class | Function | VarDecl] = []
        while not self.check(TokenType.RIGHT_PAREN) and not self.check(TokenType.EOF):
            members.append(self.member_decl())
            if not self.check(TokenType.RIGHT_PAREN):
                self.consume(TokenType.COMMA, "Expected ',' between class members")
        
        self.consume(TokenType.RIGHT_PAREN, "Expected ')' to end class body")
        
        return Class(name, args, members)
    
    def member_decl(self) -> Class | Function | VarDecl:
        if self.check(TokenType.CLASS_KW):
            return self.class_decl()
        
        # Need to look ahead past any flags to see if it's a function (scope) or variable
        if self.check_flags():
            lookahead = 1
            while self.peek(lookahead).ttype in self.ALL_FLAGS:
                lookahead += 1
            if self.peek(lookahead).ttype == TokenType.SCOPE_KW:
                return self.function_decl()
            return self.member_var_decl()
        
        if self.check(TokenType.SCOPE_KW):
            return self.function_decl()
        return self.member_var_decl()
    
    def member_var_decl(self) -> VarDecl:
        flags = self.member_flags()
        type_token = self.consume(TokenType.IDENTIFIER, "Expected type name")
        name_token = self.consume(TokenType.IDENTIFIER, "Expected variable name")
        
        value: Expression | None = None
        if self.match(TokenType.EQUAL):
            value = self.expression()
        
        return VarDecl((type_token, name_token), value, flags)
    
    def parameters(self) -> list[tuple[Token, Token]]:
        params: list[tuple[Token, Token]] = []
        
        while True:
            type_token = self.consume(TokenType.IDENTIFIER, "Expected parameter type")
            name_token = self.consume(TokenType.IDENTIFIER, "Expected parameter name")
            params.append((type_token, name_token))

            if not self.match(TokenType.COMMA):
                break
        
        return params
    
    def check_flags(self) -> bool:
        return self.check(TokenType.PRIVATE_KW) or self.check(TokenType.STATIC_KW) or \
               self.check(TokenType.CONST_KW) or self.check(TokenType.CAST_KW) or \
               self.check(TokenType.OPERATOR_KW)
    
    def member_flags(self) -> set[MemberFlag]:
        flags: set[MemberFlag] = set()
        while True:
            if self.match(TokenType.PRIVATE_KW):
                flags.add(MemberFlag.PRIVATE)
            elif self.match(TokenType.STATIC_KW):
                flags.add(MemberFlag.STATIC)
            elif self.match(TokenType.CONST_KW):
                flags.add(MemberFlag.CONST)
            else:
                break
        return flags
    
    def function_flags(self) -> tuple[set[MemberFlag], set[FunctionFlag]]:
        member_flags: set[MemberFlag] = set()
        func_flags: set[FunctionFlag] = set()
        while True:
            if self.match(TokenType.PRIVATE_KW):
                member_flags.add(MemberFlag.PRIVATE)
            elif self.match(TokenType.STATIC_KW):
                member_flags.add(MemberFlag.STATIC)
            elif self.match(TokenType.CONST_KW):
                member_flags.add(MemberFlag.CONST)
            elif self.match(TokenType.CAST_KW):
                func_flags.add(FunctionFlag.CAST)
            elif self.match(TokenType.OPERATOR_KW):
                func_flags.add(FunctionFlag.OPERATOR)
            else:
                break
        return member_flags, func_flags
    
    def check_var_decl(self) -> bool:
        """Check if we're looking at a variable declaration: (flags)? IDENTIFIER IDENTIFIER"""
        lookahead = 1
        # Skip past any member flags
        while self.peek(lookahead).ttype in (TokenType.PRIVATE_KW, TokenType.STATIC_KW, TokenType.CONST_KW):
            lookahead += 1
        # Check for IDENTIFIER IDENTIFIER pattern
        return (self.peek(lookahead).ttype == TokenType.IDENTIFIER and 
                self.peek(lookahead + 1).ttype == TokenType.IDENTIFIER)
    
    # ========== EXPRESSIONS ==========
    
    def expression(self) -> Expression:
        return self.logic_or()
    
    def logic_or(self) -> Expression:
        expr = self.logic_and()
        
        while self.match(TokenType.PIPE_PIPE):
            op = self.previous()
            right = self.logic_and()
            expr = BinaryExpr(expr, op, right)
        
        return expr
    
    def logic_and(self) -> Expression:
        expr = self.equality()
        
        while self.match(TokenType.AND_AND):
            op = self.previous()
            right = self.equality()
            expr = BinaryExpr(expr, op, right)
        
        return expr
    
    def equality(self) -> Expression:
        expr = self.comparison()
        
        while self.match(TokenType.EQUAL_EQUAL) or self.match(TokenType.BANG_EQUAL):
            op = self.previous()
            right = self.comparison()
            expr = BinaryExpr(expr, op, right)
        
        return expr
    
    def comparison(self) -> Expression:
        expr = self.term()
        
        while self.match(TokenType.RIGHT_ANGLE) or self.match(TokenType.GREATER_EQUAL) or \
              self.match(TokenType.LEFT_ANGLE) or self.match(TokenType.LESS_EQUAL):
            op = self.previous()
            right = self.term()
            expr = BinaryExpr(expr, op, right)
        
        return expr
    
    def term(self) -> Expression:
        expr = self.factor()
        
        while self.match(TokenType.PLUS) or self.match(TokenType.MINUS):
            op = self.previous()
            right = self.factor()
            expr = BinaryExpr(expr, op, right)
        
        return expr
    
    def factor(self) -> Expression:
        expr = self.unary()
        
        while self.match(TokenType.STAR) or self.match(TokenType.SLASH):
            op = self.previous()
            right = self.unary()
            expr = BinaryExpr(expr, op, right)
        
        return expr
    
    def unary(self) -> Expression:
        if self.match(TokenType.BANG) or self.match(TokenType.MINUS):
            op = self.previous()
            right = self.unary()
            return UnaryExpr(op, right)
        
        return self.primary()
    
    def primary(self) -> Expression:
        if self.match(TokenType.INT):
            tok = self.previous()
            return LiteralExpr(LiteralType.INT, tok.literal if tok.literal is not None else 0, tok)
        if self.match(TokenType.FLOAT):
            tok = self.previous()
            return LiteralExpr(LiteralType.FLOAT, tok.literal if tok.literal is not None else 0.0, tok)
        if self.match(TokenType.STRING):
            tok = self.previous()
            return LiteralExpr(LiteralType.STRING, tok.literal if tok.literal is not None else "", tok)
        if self.match(TokenType.CHARACTER):
            tok = self.previous()
            return LiteralExpr(LiteralType.CHAR, tok.literal if tok.literal is not None else "", tok)
        if self.match(TokenType.TRUE_KW):
            return LiteralExpr(LiteralType.BOOL, True, self.previous())
        if self.match(TokenType.FALSE_KW):
            return LiteralExpr(LiteralType.BOOL, False, self.previous())
        
        if self.match(TokenType.LEFT_PAREN):
            expr = self.expression()
            self.consume(TokenType.RIGHT_PAREN, "Expected ')' after expression")
            return Grouping(expr)
        
        if self.match(TokenType.LEFT_CURLY):
            elements: list[Expression] = []
            if not self.check(TokenType.RIGHT_CURLY):
                elements = self.expressions()
            self.consume(TokenType.RIGHT_CURLY, "Expected ']' after array elements")
            return ArrayExpr(elements)
        
        if self.match(TokenType.LEFT_CURLY):
            body = self.scope_body()
            self.consume(TokenType.RIGHT_CURLY, "Expected '}' after scope")
            return ScopeStmt(body)
        
        if self.check(TokenType.IDENTIFIER):
            return self.function_or_variable()
        
        raise self.error(self.peek(), "Expected expression")
    
    def function_or_variable(self) -> VariableExpr | CallExpr:
        name = self.consume(TokenType.IDENTIFIER, "Expected identifier")
        
        if self.match(TokenType.LEFT_PAREN):
            args: list[Expression] = []
            if not self.check(TokenType.RIGHT_PAREN):
                args = self.expressions()
            self.consume(TokenType.RIGHT_PAREN, "Expected ')' after arguments")
            result = CallExpr(None, name, args)
        else:
            result = VariableExpr(None, name)
        
        if self.match(TokenType.DOT):
            result.access = self.function_or_variable()
        
        return result
    
    def expressions(self) -> list[Expression]:
        exprs: list[Expression] = [self.expression()]
        while self.match(TokenType.COMMA):
            exprs.append(self.expression())
        return exprs
    
    # ========== HELPERS ==========
    
    def check(self, ttype: TokenType) -> bool:
        return self.peek().ttype == ttype

    def consume(self, ttype: TokenType, msg: str) -> Token:
        if not self.match(ttype):
            raise self.error(self.peek(), msg)
        return self.previous()
    
    def consume_semicolon(self):
        self.consume(TokenType.SEMICOLON, "Expected ';'")

    def match(self, ttype: TokenType, amount: int = 1) -> bool:
        if self.peek(amount).ttype == ttype:
            self.advance()
            return True
        return False

    def advance(self) -> Token:
        ret = self.tokens[self.current]
        self.current += 1
        return ret
    
    def peek(self, amount: int = 1) -> Token:
        idx = self.current + amount - 1
        if idx >= len(self.tokens):
            return self.tokens[-1]
        return self.tokens[idx]
    
    def previous(self) -> Token:
        return self.tokens[self.current - 1]

    def error(self, token: Token, msg: str) -> ParseException:
        print(f"[line {token.line}] [token {token.raw}] [ERROR] {msg}.")
        return ParseException()
