Language abstract syntax tree 
=============================

Below is the (rough) `AST <https://en.wikipedia.org/wiki/Abstract_syntax_tree>` 
for the langauge. This is basically what I'm working towards for a full implementation.

    program: 
        "class" "Main" ( "(" parameters? ")" )? "=" "(" members? ")"

    parameters: IDENTIFIER template_definition? IDENTIFIER ( "," IDENTIFIER templates? IDENTIFIER )*
    members: declaration ( "," declaration )*
    templates: "<" ( IDENTIFIER templates? ( "," IDENTIFIER templates? ) )? ">"
    template_definition: "<" IDENTIFIER ( "," IDENTIFIER )* ">"

    declaration: 
        | varDecl
        | functionDecl
        | classDecl

    varDecl: memberFlags? IDENTIFIER templates? IDENTIFIER ( "=" expression )?

    functionDecl: functionFlags? "scope" IDENTIFIER template_definition? ( "(" parameters? ")" )? ( "->" IDENTIFIER templates? )? "=" "{" scope? "}"
    functionFlags: 
        ( memberFlags
        | "cast"
        | "operator" )*

    memberFlags: 
        ( "private"? "static" 
        | "private"? "const" 
        | "private" )*

    classDecl: "class" IDENTIFIER ( ":" IDENTIFIER ( "," IDENTIFIERS )* ) ( "(" parameters? ")" )? "=" "(" members? ")"

    scope: statement ( statement )*

    statement: semicolonStatement | noSemicolonStatement

    semicolonStatement:
        ( expression 
        | function_or_variable = expression
        | IDENTIFIER templates? IDENTIFIER = expression
        | functionDecl 
        | "return" expression? )? ";"

    noSemicolonStatement: 
        | ifStmnt 
        | whileStmnt 
        | forStmnt

    ifStmnt: "if" "(" expression ")" "{" scope? "}" ( elifStmnt | elseStmnt )?
    elifStmnt: "elif" "(" expression ")" "{" scope? "}" ( elifStmnt | elseStmnt )?
    elseStmnt: "else" "{" scope? "}"
    whileStmnt: "while" "(" expression ")" "{" scope? "}"
    forStmnt: "for" "(" IDENTIFIER IDENTIFIER in expression ")" "{" scope? "}"

    expressions: expression ( "," expression )*
    expression: logic_or

    logic_or: logic_and ( "||" logic_and )*
    logic_and: equality ( "&&" equality )*

    equality: comparison ( ( "==" | "!=" ) comparison )*
    comparison: term ( ( ">" | ">=" | "<" | "<=" ) tern )*
    term: factor ( ( "+" | "-" ) factor )*
    factor: unary ( ( "/" | "*" ) unary )*

    unary:
        | ( "!" | "-" ) unary
        | primary

    primary: 
        | INT
        | FLOAT
        | STRING
        | CHARACTER
        | TRUE_KW
        | FALSE_KW 
        | function_or_variable
        | "{" scope? "}" 
        | "(" expression ")"
        | "[" expressions? "]"

    function_or_variable: 
        | IDENTIFIER ( templates? "(" expressions? ")" )? ( "." function_or_variable )?