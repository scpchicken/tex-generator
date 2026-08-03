import sys
import re

# --- AST NODES ---

class VarRef:
    def __init__(self, name: str):
        self.name = name

class IntNode:
    def __init__(self, val):
        self.val = int(val)

class BinaryOpNode:
    def __init__(self, left, op: str, right):
        self.left = left
        self.op = op
        self.right = right

class AssignNode:
    def __init__(self, target: VarRef, rhs):
        self.target = target
        self.rhs = rhs

class ArrayAccessNode:
    def __init__(self, name: str, index):
        self.name = name
        self.index = index

class ArrayAssignNode:
    def __init__(self, name: str, index, rhs):
        self.name = name
        self.index = index
        self.rhs = rhs

class ArrayLiteralAssignNode:
    def __init__(self, name: str, elements: list):
        self.name = name
        self.elements = elements

class PrintNode:
    def __init__(self, operand, is_char=False, newline=False):
        self.operand = operand
        self.is_char = is_char
        self.newline = newline

class PrintStringNode:
    def __init__(self, text: str, newline=False):
        self.text = text
        self.newline = newline

class IfNode:
    def __init__(self, cond, true_body, false_body):
        self.cond = cond
        self.true_body = true_body
        self.false_body = false_body

class WhileNode:
    def __init__(self, cond, body):
        self.cond = cond
        self.body = body

class ArgvCharNode:
    def __init__(self, arg_idx, char_idx):
        self.arg_idx = arg_idx
        self.char_idx = char_idx

class ArgLenNode:
    def __init__(self, arg_idx):
        self.arg_idx = arg_idx

# --- UNESCAPE HELPER ---

def unescape_string(s: str) -> str:
    """Strips quotes and expands escape sequences."""
    inner = s[1:-1]
    res = []
    i = 0
    n = len(inner)
    while i < n:
        if inner[i] == '\\' and i + 1 < n:
            nxt = inner[i + 1]
            if nxt == 'n':
                res.append('\n')
            elif nxt == 't':
                res.append('\t')
            elif nxt == 'r':
                res.append('\r')
            elif nxt == '\\':
                res.append('\\')
            elif nxt == '"':
                res.append('"')
            elif nxt == "'":
                res.append("'")
            elif nxt == '0':
                res.append('\0')
            else:
                res.append(nxt)
            i += 2
        else:
            res.append(inner[i])
            i += 1
    return "".join(res)

# --- LEXER & PARSER ---

def tokenize(code: str):
    token_specification = [
        ('COMMENT',     r'#.*'),
        ('WHILE',       r'\bwhile\b'),
        ('IF',          r'\bif\b'),
        ('ELSE',        r'\belse\b'),
        ('PRINTLN',     r'\bprintln\b'),
        ('PRINT',       r'\bprint\b'),
        ('PUTC',        r'\bputc\b'),
        ('ARGLEN',      r'\barglen\b'),
        ('ARGV',        r'\bargv\b'),
        ('STRING',      r'"([^"\\]|\\.)*"'),
        ('CHAR',        r"'([^'\\]|\\.)'"),
        ('COMMA',       r','),
        ('LBRACE',      r'\{'),
        ('RBRACE',      r'\}'),
        ('LBRACK',      r'\['),
        ('RBRACK',      r'\]'),
        ('LPAREN',      r'\('),
        ('RPAREN',      r'\)'),
        ('COMP',        r'==|<|>'),
        ('COMPOUND_OP', r'\+=|-=|\*=|/=|%='),
        ('OP',          r'='),
        ('MUL_OP',      r'\*|\/|%'),
        ('ADD_OP',      r'\+|-' ),
        ('INT',         r'\d+'),
        ('IDENT',       r'[a-zA-Z_]\w*'),
        ('SEMI',        r';'),
        ('NEWLINE',     r'\n'),
        ('SKIP',        r'[ \t\r]+'),
        ('MISMATCH',    r'.'),
    ]
    tok_regex = '|'.join('(?P<%s>%s)' % pair for pair in token_specification)
    tokens = []
    for mo in re.finditer(tok_regex, code):
        kind = mo.lastgroup
        value = mo.group()
        if kind in ('SKIP', 'COMMENT'):
            continue
        elif kind == 'MISMATCH':
            raise SyntaxError(f"Unexpected character {value!r}")
        tokens.append((kind, value))
    return _insert_automatic_semicolons(tokens)


def _insert_automatic_semicolons(tokens):
    ASI_TRIGGER_KINDS = {'INT', 'IDENT', 'RPAREN', 'STRING', 'CHAR', 'RBRACK'}
    result = []
    n = len(tokens)
    for i, (kind, value) in enumerate(tokens):
        if kind == 'NEWLINE':
            if result and result[-1][0] in ASI_TRIGGER_KINDS:
                j = i + 1
                while j < n and tokens[j][0] == 'NEWLINE':
                    j += 1
                next_kind = tokens[j][0] if j < n else None
                if next_kind != 'LBRACE':
                    result.append(('SEMI', ';'))
            continue
        result.append((kind, value))
    if result and result[-1][0] in ASI_TRIGGER_KINDS:
        result.append(('SEMI', ';'))
    return result

class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    def peek(self):
        return self.tokens[self.pos] if self.pos < len(self.tokens) else (None, None)

    def match(self, kind):
        k, v = self.peek()
        if k == kind:
            self.pos += 1
            return (k, v)
        return None

    def expect(self, kind):
        res = self.match(kind)
        if not res:
            raise SyntaxError(f"Expected {kind}")
        return res

    def parse_program(self):
        statements = []
        while self.peek()[0] not in (None, 'RBRACE'):
            statements.append(self.parse_statement())
        return statements

    def parse_statement(self):
        kind, val = self.peek()
        if kind == 'WHILE':
            self.expect('WHILE')
            cond = self.parse_expression()
            self.expect('LBRACE')
            body = self.parse_program()
            self.expect('RBRACE')
            return WhileNode(cond, body)
        elif kind == 'IF':
            self.expect('IF')
            cond = self.parse_expression()
            self.expect('LBRACE')
            true_body = self.parse_program()
            self.expect('RBRACE')
            false_body = []
            if self.match('ELSE'):
                self.expect('LBRACE')
                false_body = self.parse_program()
                self.expect('RBRACE')
            return IfNode(cond, true_body, false_body)
        elif kind in ('PRINT', 'PRINTLN', 'PUTC'):
            self.expect(kind)
            self.expect('LPAREN')
            if self.peek()[0] == 'STRING':
                _, str_val = self.expect('STRING')
                self.expect('RPAREN')
                self.expect('SEMI')
                return PrintStringNode(
                    unescape_string(str_val),
                    newline=(kind == 'PRINTLN')
                )
            else:
                operand = self.parse_expression()
                self.expect('RPAREN')
                self.expect('SEMI')
                return PrintNode(
                    operand,
                    is_char=(kind == 'PUTC'),
                    newline=(kind == 'PRINTLN')
                )
        elif kind == 'IDENT':
            _, name = self.expect('IDENT')
            if self.match('LBRACK'):
                index = self.parse_expression()
                self.expect('RBRACK')
                if self.peek()[0] == 'COMPOUND_OP':
                    _, compound_op = self.expect('COMPOUND_OP')
                    op = compound_op[0]
                    rhs = self.parse_expression()
                    self.expect('SEMI')
                    return ArrayAssignNode(name, index, BinaryOpNode(ArrayAccessNode(name, index), op, rhs))
                else:
                    self.expect('OP')
                    rhs = self.parse_expression()
                    self.expect('SEMI')
                    return ArrayAssignNode(name, index, rhs)
            else:
                if self.peek()[0] == 'COMPOUND_OP':
                    _, compound_op = self.expect('COMPOUND_OP')
                    op = compound_op[0]
                    rhs = self.parse_expression()
                    self.expect('SEMI')
                    return AssignNode(VarRef(name), BinaryOpNode(VarRef(name), op, rhs))
                else:
                    self.expect('OP')
                    if self.peek()[0] == 'STRING':
                        _, str_val = self.expect('STRING')
                        self.expect('SEMI')
                        text = unescape_string(str_val)
                        elements = [IntNode(ord(ch)) for ch in text]
                        return ArrayLiteralAssignNode(name, elements)
                    elif self.match('LBRACK'):
                        elements = []
                        if self.peek()[0] != 'RBRACK':
                            elements.append(self.parse_expression())
                            while self.match('COMMA'):
                                elements.append(self.parse_expression())
                        self.expect('RBRACK')
                        self.expect('SEMI')
                        return ArrayLiteralAssignNode(name, elements)
                    else:
                        rhs = self.parse_expression()
                        self.expect('SEMI')
                        return AssignNode(VarRef(name), rhs)
        else:
            raise SyntaxError(f"Unexpected token {kind}")

    def parse_expression(self):
        node = self.parse_additive()
        while self.peek()[0] == 'COMP':
            _, op = self.match('COMP')
            right = self.parse_additive()
            node = BinaryOpNode(node, op, right)
        return node

    def parse_additive(self):
        node = self.parse_multiplicative()
        while self.peek()[0] == 'ADD_OP':
            _, op = self.match('ADD_OP')
            right = self.parse_multiplicative()
            node = BinaryOpNode(node, op, right)
        return node

    def parse_multiplicative(self):
        node = self.parse_primary()
        while self.peek()[0] == 'MUL_OP':
            _, op = self.match('MUL_OP')
            right = self.parse_primary()
            node = BinaryOpNode(node, op, right)
        return node

    def parse_primary(self):
        k, val = self.peek()
        if k == 'INT':
            self.expect('INT')
            return IntNode(val)
        elif k == 'CHAR':
            _, char_val = self.expect('CHAR')
            ch_str = unescape_string(char_val)
            if len(ch_str) != 1:
                raise SyntaxError(f"Character literal must be a single character, got {char_val}")
            return IntNode(ord(ch_str))
        elif k == 'ARGV':
            self.expect('ARGV')
            self.expect('LPAREN')
            arg_idx = self.parse_expression()
            self.expect('COMMA')
            char_idx = self.parse_expression()
            self.expect('RPAREN')
            return ArgvCharNode(arg_idx, char_idx)
        elif k == 'ARGLEN':
            self.expect('ARGLEN')
            self.expect('LPAREN')
            arg_idx = self.parse_expression()
            self.expect('RPAREN')
            return ArgLenNode(arg_idx)
        elif k == 'IDENT':
            self.expect('IDENT')
            if self.match('LBRACK'):
                index = self.parse_expression()
                self.expect('RBRACK')
                return ArrayAccessNode(val, index)
            return VarRef(val)
        elif k == 'LPAREN':
            self.expect('LPAREN')
            expr = self.parse_expression()
            self.expect('RPAREN')
            return expr
        raise SyntaxError(f"Expected expression, got {k}")

# --- TEX TRANSPILER ---

class TexTranspiler:
    def __init__(self):
        self.vars = {}
        self.var_counter = 0
        self.loop_counter = 0

    def get_var(self, name):
        if name == "argc":
            return "\\argc"
        if name not in self.vars:
            self.vars[name] = f"\\v{chr(65 + self.var_counter)}"
            self.var_counter += 1
        return self.vars[name]

    def get_loop_names(self):
        c = self.loop_counter
        self.loop_counter += 1
        res = ""
        c_temp = c
        while True:
            res = chr(65 + (c_temp % 26)) + res
            c_temp = c_temp // 26 - 1
            if c_temp < 0:
                break
        return f"\\loop{res}", f"\\next{res}"

    def transpile(self, code: str) -> str:
        tokens = tokenize(code)
        ast = Parser(tokens).parse_program()
        
        body_code = self.emit_block(ast)

        tex_code = "% --- Register Declarations ---\n"
        tex_code += "\\newcount\\tA \\newcount\\tB \\newcount\\tC \\newcount\\tD % Scratch registers\n"
        tex_code += "\\newcount\\strlen \\newcount\\charval \\newcount\\targetidx \\newcount\\curridx % Helper registers\n"
        tex_code += "\\newcount\\arridx \\newcount\\arrval % Array helper registers\n\n"
        
        for user_var, tex_var in self.vars.items():
            tex_code += f"\\newcount{tex_var} % {user_var}\n"
            
        tex_code += "\n% --- TeX Argv & Array Parsing Helpers ---\n"
        tex_code += "\\def\\calcarglen#1{%\n"
        tex_code += "  \\strlen=0\n"
        tex_code += "  \\edef\\argstr{\\argv#1\\relax}%\n"
        tex_code += "  \\expandafter\\countlen\\argstr\n"
        tex_code += "}\n"
        tex_code += "\\def\\countlen#1{\\ifx#1\\relax\\else\\advance\\strlen 1 \\expandafter\\countlen\\fi}\n\n"
        
        tex_code += "\\def\\calcargvchar#1#2{%\n"
        tex_code += "  \\targetidx=#2\\relax \\curridx=0\\relax \\charval=0\\relax\n"
        tex_code += "  \\edef\\argstr{\\argv#1\\relax}%\n"
        tex_code += "  \\expandafter\\findchar\\argstr\n"
        tex_code += "}\n"
        tex_code += "\\def\\findchar#1{%\n"
        tex_code += "  \\ifx#1\\relax\n"
        tex_code += "  \\else\n"
        tex_code += "    \\ifnum\\curridx=\\targetidx\\charval=`#1\\fi\n"
        tex_code += "    \\advance\\curridx 1\n"
        tex_code += "    \\expandafter\\findchar\n"
        tex_code += "  \\fi\n"
        tex_code += "}\n\n"

        tex_code += "\\def\\setarray#1#2#3{%\n"
        tex_code += "  \\expandafter\\edef\\csname arr@#1:\\the#2\\endcsname{\\the#3}%\n"
        tex_code += "}\n"
        tex_code += "\\def\\getarray#1#2#3{%\n"
        tex_code += "  \\expandafter\\ifx\\csname arr@#1:\\the#2\\endcsname\\relax\n"
        tex_code += "    #3=0\\relax\n"
        tex_code += "  \\else\n"
        tex_code += "    #3=\\csname arr@#1:\\the#2\\endcsname\\relax\n"
        tex_code += "  \\fi\n"
        tex_code += "}\n\n"
        
        tex_code += "% --- Program Body ---\n"
        tex_code += body_code + "\n\\bye"
        return tex_code

    SCRATCH_POOL = ("\\tA", "\\tB", "\\tC")

    def pick_scratch(self, *exclude):
        for reg in self.SCRATCH_POOL:
            if reg not in exclude:
                return reg
        raise RuntimeError("no free scratch register available")

    def emit_operand(self, node, scratch_reg):
        if isinstance(node, VarRef) and node.name == "argc":
            return "", "\\argc"
        code = self.emit_eval(node, scratch_reg)
        return code, scratch_reg

    def emit_eval(self, node, target_reg="\\tA"):
        if isinstance(node, IntNode):
            return f"{target_reg}={node.val} "
        elif isinstance(node, VarRef):
            return f"{target_reg}={self.get_var(node.name)} "
        elif isinstance(node, ArrayAccessNode):
            idx_reg = self.pick_scratch(target_reg)
            code = self.emit_eval(node.index, idx_reg)
            code += f"\\getarray{{{node.name}}}{{{idx_reg}}}{{{target_reg}}}"
            return code
        elif isinstance(node, ArgLenNode):
            arg_reg = self.pick_scratch(target_reg)
            code = self.emit_eval(node.arg_idx, arg_reg)
            code += f"\\calcarglen{arg_reg}"
            code += f"{target_reg}=\\strlen "
            return code
        elif isinstance(node, ArgvCharNode):
            arg_reg = self.pick_scratch(target_reg)
            char_reg = self.pick_scratch(target_reg, arg_reg)
            code = self.emit_eval(node.arg_idx, arg_reg)
            code += self.emit_eval(node.char_idx, char_reg)
            code += f"\\calcargvchar{arg_reg}{char_reg}"
            code += f"{target_reg}=\\charval "
            return code
        elif isinstance(node, BinaryOpNode):
            code = self.emit_eval(node.left, target_reg)
            right_reg = self.pick_scratch(target_reg)
            right_code, right_val = self.emit_operand(node.right, right_reg)
            code += right_code
            
            if node.op == '+':
                code += f"\\advance{target_reg}{right_val} "
            elif node.op == '-':
                code += f"\\advance{target_reg}-{right_val} "
            elif node.op == '*':
                code += f"\\multiply{target_reg}{right_val} "
            elif node.op == '/':
                code += f"\\divide{target_reg}{right_val} "
            elif node.op == '%':
                code += f"\\tD={target_reg} \\divide\\tD{right_val} \\multiply\\tD{right_val} \\advance{target_reg}-\\tD "
            return code

    def emit_block(self, nodes):
        return "\n".join(self.emit_node(n) for n in nodes)

    def emit_node(self, node):
        if isinstance(node, AssignNode):
            tex_var = self.get_var(node.target.name)
            return self.emit_eval(node.rhs, tex_var) + "%"

        elif isinstance(node, ArrayAssignNode):
            code = self.emit_eval(node.index, "\\arridx")
            code += self.emit_eval(node.rhs, "\\arrval")
            code += f"\\setarray{{{node.name}}}{{\\arridx}}{{\\arrval}}%"
            return code

        elif isinstance(node, ArrayLiteralAssignNode):
            code_parts = []
            for i, elem in enumerate(node.elements):
                code = f"\\arridx={i} "
                code += self.emit_eval(elem, "\\arrval")
                code += f"\\setarray{{{node.name}}}{{\\arridx}}{{\\arrval}}%"
                code_parts.append(code)
            return "\n".join(code_parts)

        elif isinstance(node, PrintNode):
            code, val = self.emit_operand(node.operand, "\\tA")
            if node.is_char:
                code += f"\\char{val}"
            else:
                code += f"\\the{val}"
            if node.newline:
                code += "\\leavevmode\\par%\n"
            else:
                code += "%"
            return code

        elif isinstance(node, PrintStringNode):
            code = ""
            for ch in node.text:
                if ch == '\n':
                    code += "\\leavevmode\\par%\n"
                else:
                    code += f"\\char{ord(ch)} "
            if node.newline:
                code += "\\leavevmode\\par%\n"
            else:
                if not code.endswith("%") and not code.endswith("\n"):
                    code += "%"
            return code
            
        elif isinstance(node, IfNode):
            left_reg = "\\tA"
            right_reg = "\\tB"
            left_code, left_val = self.emit_operand(node.cond.left, left_reg)
            right_code, right_val = self.emit_operand(node.cond.right, right_reg)
            code = left_code + right_code
            
            op = "=" if node.cond.op == "==" else node.cond.op
            code += f"\\ifnum{left_val}{op}{right_val}%\n"
            true_str = self.emit_block(node.true_body)
            if true_str:
                code += true_str + "\n"
            if node.false_body:
                code += "\\else%\n"
                false_str = self.emit_block(node.false_body)
                if false_str:
                    code += false_str + "\n"
            code += "\\fi%"
            return code
            
        elif isinstance(node, WhileNode):
            loop_macro, next_macro = self.get_loop_names()
            left_reg = "\\tA"
            right_reg = "\\tB"
            op = "=" if node.cond.op == "==" else node.cond.op
            
            left_code, left_val = self.emit_operand(node.cond.left, left_reg)
            right_code, right_val = self.emit_operand(node.cond.right, right_reg)
            code = f"\\def{loop_macro}{{"
            code += left_code
            code += right_code
            code += f"\\ifnum{left_val}{op}{right_val}%\n"
            body_str = self.emit_block(node.body)
            if body_str:
                code += body_str + "\n"
            code += f"\\let{next_macro}={loop_macro}%\n"
            code += f"\\else\\let{next_macro}=\\relax\\fi%\n"
            code += f"{next_macro}}}%\n"
            code += f"{loop_macro}%"
            return code

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 texgen.py <input.src> [output.tex]")
        sys.exit(1)

    in_file = sys.argv[1]
    out_file = sys.argv[2] if len(sys.argv) > 2 else in_file.rsplit('.', 1)[0] + '.tex'

    with open(in_file, 'r', encoding='utf-8') as f:
        source_code = f.read()

    transpiler = TexTranspiler()
    tex_code = transpiler.transpile(source_code)

    with open(out_file, 'w', encoding='utf-8') as f:
        f.write(tex_code)