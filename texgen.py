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

class PrintNode:
    def __init__(self, operand, is_char=False, newline=False):
        self.operand = operand
        self.is_char = is_char
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
    """Evaluates to the ASCII code of character char_idx in argv[arg_idx]"""
    def __init__(self, arg_idx, char_idx):
        self.arg_idx = arg_idx
        self.char_idx = char_idx

class ArgvLenNode:
    """Evaluates to the length of argv[arg_idx]"""
    def __init__(self, arg_idx):
        self.arg_idx = arg_idx

# --- LEXER & PARSER ---

def tokenize(code: str):
    token_specification = [
        ('COMMENT',  r'#.*'),
        ('WHILE',    r'\bwhile\b'),
        ('IF',       r'\bif\b'),
        ('ELSE',     r'\belse\b'),
        ('PRINTLN',  r'\bprintln\b'),
        ('PRINT',    r'\bprint\b'),
        ('PUTC',     r'\bputc\b'),
        ('ARGV_LEN', r'\bargv_len\b'),
        ('ARGV',     r'\bargv\b'),
        ('COMMA',    r','),
        ('LBRACE',   r'\{'),
        ('RBRACE',   r'\}'),
        ('LPAREN',   r'\('),
        ('RPAREN',   r'\)'),
        ('COMP',     r'==|<|>'),
        ('OP',       r'='),
        ('MUL_OP',   r'\*|\/|%'),
        ('ADD_OP',   r'\+|-' ),
        ('INT',      r'\d+'),
        ('IDENT',    r'[a-zA-Z_]\w*'),
        ('SEMI',     r';'),
        ('NEWLINE',  r'\n'),
        ('SKIP',     r'[ \t\r]+'),
        ('MISMATCH', r'.'),
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
    """
    Makes the trailing ';' after a statement optional when the statement
    ends at a newline instead. A newline is treated as an implicit ';'
    only when the preceding token is one that can legally end a statement
    (a number, identifier, or a closing ')' from a call or condition) --
    this avoids splitting an expression that simply wraps onto the next
    line, e.g.:
        x = i +
            1;
    (no token in {INT, IDENT, RPAREN} precedes that newline, so nothing
    is inserted). As a further safeguard, no ';' is inserted if the next
    real token is '{', so a brace on its own line still attaches to its
    'if'/'while', e.g.:
        while (i < n)
        {
            ...
        }
    Real ';' tokens and blank lines are left untouched -- this only ever
    fills in a ';' that would otherwise be missing. End of input is
    treated the same as a trailing newline, so a final statement with no
    trailing newline (e.g. a file with no newline at EOF) still gets its
    implicit ';'.
    """
    ASI_TRIGGER_KINDS = {'INT', 'IDENT', 'RPAREN'}
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
            self.expect('OP')
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
        elif k == 'ARGV':
            self.expect('ARGV')
            self.expect('LPAREN')
            arg_idx = self.parse_expression()
            self.expect('COMMA')
            char_idx = self.parse_expression()
            self.expect('RPAREN')
            return ArgvCharNode(arg_idx, char_idx)
        elif k == 'ARGV_LEN':
            self.expect('ARGV_LEN')
            self.expect('LPAREN')
            arg_idx = self.parse_expression()
            self.expect('RPAREN')
            return ArgvLenNode(arg_idx)
        elif k == 'IDENT':
            self.expect('IDENT')
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
        
        # TeX output requires registers and string-parsing helper macros
        tex_code = "% --- Register Declarations ---\n"
        tex_code += "\\newcount\\tA \\newcount\\tB \\newcount\\tC \\newcount\\tD % Scratch registers\n"
        tex_code += "\\newcount\\strlen \\newcount\\charval \\newcount\\targetidx \\newcount\\curridx % Helper registers\n\n"
        
        for user_var, tex_var in self.vars.items():
            tex_code += f"\\newcount{tex_var} % {user_var}\n"
            
        tex_code += "\n% --- TeX Argv String Parsing Helpers ---\n"
        tex_code += "\\def\\calcargvlen#1{%\n"
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
        
        tex_code += "% --- Program Body ---\n"
        tex_code += body_code + "\n\\bye"
        return tex_code

    SCRATCH_POOL = ("\\tA", "\\tB", "\\tC")

    def pick_scratch(self, *exclude):
        """
        Returns a scratch register from the \\tA/\\tB/\\tC pool that is not
        in `exclude`. Used anywhere an expression needs a temporary that
        must not alias a register already holding a live value (e.g. the
        register the caller wants the result stored in, or another
        operand's register). A plain "\\tB if x==\\tA else \\tC" ternary
        only handles two of the three registers correctly -- if x is
        already \\tC, that ternary hands back \\tC again, silently
        aliasing it. This picks the first pool member not already spoken
        for, however many are excluded.
        """
        for reg in self.SCRATCH_POOL:
            if reg not in exclude:
                return reg
        raise RuntimeError("no free scratch register available")

    def emit_operand(self, node, scratch_reg):
        """
        Prepares an operand for use in a TeX numeric context where a
        register is not strictly required -- e.g. the right-hand side of
        \\ifnum, \\advance, \\multiply, \\divide, or the argument to \\the
        / \\char. TeX's <number> scanning happily expands a macro in
        place, so these contexts don't need the value pre-copied into a
        scratch register.

        Special-cases a bare reference to `argc`: since \\argc is a macro
        injected by the harness (not one of this transpiler's own
        \\newcount registers), copying its value into a scratch register
        first is unnecessary and, as observed in practice, unreliable.
        We reference \\argc directly instead.

        Returns (setup_code, token_to_use).
        """
        if isinstance(node, VarRef) and node.name == "argc":
            return "", "\\argc"
        code = self.emit_eval(node, scratch_reg)
        return code, scratch_reg

    def emit_eval(self, node, target_reg="\\tA"):
        """Evaluates an expression and stores the result in target_reg."""
        if isinstance(node, IntNode):
            return f"{target_reg}={node.val} "
        elif isinstance(node, VarRef):
            return f"{target_reg}={self.get_var(node.name)} "
        elif isinstance(node, ArgvLenNode):
            arg_reg = self.pick_scratch(target_reg)
            code = self.emit_eval(node.arg_idx, arg_reg)
            code += f"\\calcargvlen{arg_reg} "
            code += f"{target_reg}=\\strlen "
            return code
        elif isinstance(node, ArgvCharNode):
            arg_reg = self.pick_scratch(target_reg)
            char_reg = self.pick_scratch(target_reg, arg_reg)
            code = self.emit_eval(node.arg_idx, arg_reg)
            code += self.emit_eval(node.char_idx, char_reg)
            code += f"\\calcargvchar{arg_reg}{char_reg} "
            code += f"{target_reg}=\\charval "
            return code
        elif isinstance(node, BinaryOpNode):
            code = self.emit_eval(node.left, target_reg)
            
            # Right operand only needs to be a <number>, not necessarily a
            # register -- \advance/\multiply/\divide accept either. Use
            # emit_operand so a bare `argc` is referenced directly instead
            # of being copied into a scratch register first.
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
                # TeX modulo calculation: d = x - (x / y) * y
                # \tD is a dedicated scratch register used only here. It
                # must not reuse target_reg or right_val's register: when
                # target_reg is a user variable (the common top-level
                # case, e.g. `z = 3 % 2;`), right_val ends up in \tC, and
                # using \tC again as the modulo scratch would overwrite
                # the divisor with the dividend before the divide even
                # happens, corrupting the result.
                code += f"\\tD={target_reg} \\divide\\tD{right_val} \\multiply\\tD{right_val} \\advance{target_reg}-\\tD "
            return code

    def emit_block(self, nodes):
        return "\n".join(self.emit_node(n) for n in nodes)

    def emit_node(self, node):
        if isinstance(node, AssignNode):
            tex_var = self.get_var(node.target.name)
            return self.emit_eval(node.rhs, tex_var) + "%"
            
        elif isinstance(node, PrintNode):
            code, val = self.emit_operand(node.operand, "\\tA")
            if node.is_char:
                code += f"\\char{val}"
            else:
                code += f"\\the{val}"
            if node.newline:
                code += "\\hfill\\break%"
            else:
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
            code += self.emit_block(node.true_body)
            if node.false_body:
                code += "\n\\else%\n" + self.emit_block(node.false_body)
            code += "\n\\fi%"
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
            code += self.emit_block(node.body)
            code += f"\n\\let{next_macro}={loop_macro}%\n"
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