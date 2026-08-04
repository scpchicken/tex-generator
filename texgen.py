import sys
import re
import string

# --- AST NODES ---

class VarRef:
    def __init__(self, name: str):
        self.name = name

class IntNode:
    def __init__(self, val):
        self.val = int(val)

class UnaryOpNode:
    def __init__(self, op: str, operand):
        self.op = op
        self.operand = operand

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
    inner = s[1:-1]
    res = []
    i = 0
    n = len(inner)
    while i < n:
        if inner[i] == '\\' and i + 1 < n:
            nxt = inner[i + 1]
            if nxt == 'n': res.append('\n')
            elif nxt == 't': res.append('\t')
            elif nxt == 'r': res.append('\r')
            elif nxt == '\\': res.append('\\')
            elif nxt == '"': res.append('"')
            elif nxt == "'": res.append("'")
            elif nxt == '0': res.append('\0')
            else: res.append(nxt)
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
        ('COMP',        r'==|!=|<=|>=|<|>'),
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
    STATEMENT_START_OR_END_KINDS = {'WHILE', 'IF', 'PRINT', 'PRINTLN', 'PUTC', 'IDENT', 'RBRACE'}
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
        
        if kind in STATEMENT_START_OR_END_KINDS:
            if result and result[-1][0] in ASI_TRIGGER_KINDS:
                result.append(('SEMI', ';'))
                
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
        node = self.parse_unary()
        while self.peek()[0] == 'MUL_OP':
            _, op = self.match('MUL_OP')
            right = self.parse_unary()
            node = BinaryOpNode(node, op, right)
        return node

    def parse_unary(self):
        if self.peek()[0] == 'ADD_OP':
            _, op = self.match('ADD_OP')
            operand = self.parse_unary()
            if op == '-':
                if isinstance(operand, IntNode):
                    return IntNode(-operand.val)
                return UnaryOpNode('-', operand)
            elif op == '+':
                return operand
        return self.parse_primary()

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

# --- MACRO OPTIMIZER ---

def optimize_macros(raw_tex: str) -> str:
    reserved = set(re.findall(r'\\([a-zA-Z])(?![a-zA-Z])', raw_tex))
    candidate_letters = [c for c in (string.ascii_lowercase + string.ascii_uppercase) if c not in reserved]

    word_matches = re.findall(r'\\([a-zA-Z]{2,})', raw_tex)
    counts = {}
    for w in word_matches:
        full_w = '\\' + w
        counts[full_w] = counts.get(full_w, 0) + 1

    if not counts:
        return raw_tex

    tilde_options = [None, '\\let'] + [
        w for w in counts 
        if w != '\\let' and not re.search(re.escape(w) + r'\s', raw_tex)
    ]

    best_selected_words = []
    best_tilde = None
    best_use_let = False
    best_let_letter = None
    max_net_savings = 0

    for tilde_target in tilde_options:
        for use_let_alias in (False, True):
            if tilde_target == '\\let' and use_let_alias:
                continue

            avail = list(candidate_letters)

            let_alias_letter = None
            if use_let_alias:
                if not avail:
                    continue
                let_alias_letter = avail.pop(0)

            if tilde_target == '\\let':
                let_cmd = "~"
            elif use_let_alias:
                let_cmd = f"\\{let_alias_letter}"
            else:
                let_cmd = "\\let"

            base_hdr_cost = 0
            if tilde_target is not None:
                base_hdr_cost += len(f"\\let~{tilde_target}")
            if use_let_alias:
                base_hdr_cost += len(f"\\let\\{let_alias_letter}\\let")

            tilde_gross_savings = 0
            if tilde_target is not None and tilde_target in counts:
                cnt = counts[tilde_target]
                tilde_gross_savings = cnt * (len(tilde_target) - 1)

            remaining_words = [w for w in counts if w != tilde_target]

            word_savings = []
            for w in remaining_words:
                cnt = counts[w]
                orig_len = len(w)
                setup_cost = len(let_cmd) + 2 + orig_len
                gross = cnt * (orig_len - 2)
                net = gross - setup_cost
                if net > 0:
                    word_savings.append((net, gross, setup_cost, w))

            word_savings.sort(key=lambda x: x[0], reverse=True)
            selected_words = word_savings[:len(avail)]

            total_net = tilde_gross_savings + sum(item[0] for item in selected_words) - base_hdr_cost

            if total_net > max_net_savings:
                max_net_savings = total_net
                best_tilde = tilde_target
                best_use_let = use_let_alias
                best_let_letter = let_alias_letter
                best_selected_words = selected_words

    if max_net_savings <= 0:
        return raw_tex

    hdr_parts = []
    aliases = {}

    if best_tilde is not None:
        hdr_parts.append(f"\\let~{best_tilde}")
        if best_tilde in counts:
            aliases[best_tilde] = "~"

    if best_tilde == '\\let':
        let_cmd = "~"
    elif best_use_let:
        let_cmd = f"\\{best_let_letter}"
        hdr_parts.append(f"\\let{let_cmd}\\let")
    else:
        let_cmd = "\\let"

    avail = [c for c in candidate_letters if c != best_let_letter]
    for _, _, _, w in best_selected_words:
        letter = avail.pop(0)
        alias_macro = f"\\{letter}"
        aliases[w] = alias_macro
        hdr_parts.append(f"{let_cmd}{alias_macro}{w}")

    hdr = "".join(hdr_parts)

    sorted_replacements = sorted(aliases.items(), key=lambda x: len(x[0]), reverse=True)

    res_tex = raw_tex
    for word, alias in sorted_replacements:
        pattern = re.escape(word) + r'(?![a-zA-Z])'
        res_tex = re.sub(pattern, lambda m, a=alias: a, res_tex)

    return hdr + res_tex

# --- OPTIMIZED TEX TRANSPILER ---

class TexTranspiler:
    # 10 Scratch registers available (\a through \j)
    SCRATCH_POOL = ("\\a", "\\b", "\\c", "\\d", "\\e", "\\f", "\\g", "\\h", "\\i", "\\j")

    OP_MAP = {
        '==': ('=', False),
        '=':  ('=', False),
        '<':  ('<', False),
        '>':  ('>', False),
        '!=': ('=', True),
        '<=': ('>', True),
        '>=': ('<', True),
    }

    def __init__(self):
        self.vars = {}
        self.array_tags = {}
        self.array_tag_counter = 0
        self.var_gen = self._var_name_generator()
        self.loop_gen = self._loop_name_generator()
        self.used_scratch_regs = set()

    def _var_name_generator(self):
        for c in string.ascii_lowercase + string.ascii_uppercase:
            yield f"\\v{c}"
        for c1 in string.ascii_lowercase + string.ascii_uppercase:
            for c2 in string.ascii_lowercase + string.ascii_uppercase:
                yield f"\\v{c1}{c2}"

    def _loop_name_generator(self):
        for c in string.ascii_lowercase + string.ascii_uppercase:
            yield f"\\l{c}"
        for c1 in string.ascii_lowercase + string.ascii_uppercase:
            for c2 in string.ascii_lowercase + string.ascii_uppercase:
                yield f"\\l{c1}{c2}"

    @staticmethod
    def is_single_token(s: str) -> bool:
        if len(s) == 1:
            return True
        if s.startswith('\\') and re.match(r'^\\[a-zA-Z]+$', s):
            return True
        if s.startswith('\\') and len(s) == 2:
            return True
        return False

    @staticmethod
    def ends_with_control_word(s: str) -> bool:
        return re.search(r'\\[a-zA-Z]+$', s) is not None

    def format_macro_call(self, macro: str, args: list) -> str:
        res = macro
        for arg in args:
            arg_str = str(arg)
            if not self.is_single_token(arg_str):
                res += f"{{{arg_str}}}"
            elif self.ends_with_control_word(res):
                if re.match(r'^[a-zA-Z]', arg_str):
                    res += f"\x00{arg_str}"
                else:
                    res += arg_str
            else:
                if re.match(r'^[a-zA-Z]', arg_str) and re.search(r'[a-zA-Z]$', res):
                    res += f"{{{arg_str}}}"
                else:
                    res += arg_str
        return res

    def get_array_tag(self, name: str) -> str:
        if name not in self.array_tags:
            tag = chr(ord('a') + self.array_tag_counter)
            self.array_tag_counter += 1
            self.array_tags[name] = tag
        return self.array_tags[name]

    def get_var(self, name):
        if name == "argc":
            return "\\argc"
        if name not in self.vars:
            var_name = next(self.var_gen)
            self.vars[name] = var_name
        return self.vars[name]

    def get_loop_name(self):
        return next(self.loop_gen)

    def pick_scratch(self, busy_regs=()):
        for reg in self.SCRATCH_POOL:
            if reg not in busy_regs:
                self.used_scratch_regs.add(reg)
                return reg
        raise RuntimeError("no free scratch register available")

    def transpile(self, code: str) -> str:
        tokens = tokenize(code)
        ast = Parser(tokens).parse_program()
        body_code = self.emit_block(ast)

        # Golfed header for register allocations using active ~ alias for \newcount
        ordered_scratch = [reg for reg in self.SCRATCH_POOL if reg in self.used_scratch_regs]
        all_regs = ordered_scratch + list(self.vars.values())
        if all_regs:
            regs = "\\let~\\newcount" + "".join(f"~{reg}" for reg in all_regs)
        else:
            regs = ""

        # Dynamically append helper definitions (golfed)
        helpers = ""
        if "\\HP" in body_code:
            helpers += "\\def\\HP{\\par}"
        if "\\HS" in body_code:
            helpers += "\\def\\HS#1#2#3{\\expandafter\\edef\\csname#1:\\the#2\\endcsname{\\the#3}}"
        if "\\HG" in body_code:
            helpers += "\\def\\HG#1#2#3{\\expandafter\\ifx\\csname#1:\\the#2\\endcsname\\relax#30 \\else#3\\csname#1:\\the#2\\endcsname\\fi}"
        if "\\HL" in body_code:
            helpers += "\\def\\HL#1{\\e0\\edef\\HX{\\argv#1\\relax}\\expandafter\\HK\\HX}\\def\\HK#1{\\ifx#1\\relax\\else\\advance\\e1\\expandafter\\HK\\fi}"
        if "\\HV" in body_code:
            helpers += "\\def\\HV#1#2{\\g#2\\h0\\f0\\edef\\HX{\\argv#1\\relax}\\expandafter\\HF\\HX}\\def\\HF#1{\\ifx#1\\relax\\else\\ifnum\\h=\g\\f=`#1\\fi\\advance\\h1 \\expandafter\\HF\\fi}"

        # 1. Protect ALL spaces in helpers
        helpers_protected = helpers.replace(' ', '\x00')

        raw_tex = f"{regs}{helpers_protected}{body_code}"

        # 2. Protect explicit control spaces (\ ) for literal strings
        raw_tex = raw_tex.replace('\\ ', '\\\x00')

        # 3. Protect spaces after any digit preceding expandable control sequences
        raw_tex = re.sub(r'(\d)\s+(\\ifnum|\\the|\\char|\\HP)', lambda m: m.group(1) + '\x00' + m.group(2), raw_tex)

        # 4. Strip all remaining unprotected spaces
        raw_tex = raw_tex.replace(' ', '')

        # 5. Restore protected spaces
        raw_tex = raw_tex.replace('\x00', ' ')

        return optimize_macros(raw_tex)

    def emit_operand(self, node, scratch_reg, busy_regs=()):
        if isinstance(node, VarRef) and node.name == "argc":
            return "", "\\argc"
        code = self.emit_eval(node, scratch_reg, busy_regs)
        return code, scratch_reg

    def emit_eval(self, node, target_reg="\\a", busy_regs=()):
        self.used_scratch_regs.add(target_reg)
        current_busy = set(busy_regs) | {target_reg}
        if isinstance(node, IntNode):
            val = node.val
            # Use backtick ASCII conversion for 3-digit ASCII characters (100-127)
            if 100 <= val <= 127:
                return f"{target_reg}`{chr(val)}"
            return f"{target_reg}{val} "
        elif isinstance(node, UnaryOpNode):
            if node.op == '-':
                code = self.emit_eval(node.operand, target_reg, busy_regs)
                code += f"\\multiply{target_reg}-1 "
                return code
        elif isinstance(node, VarRef):
            return f"{target_reg}{self.get_var(node.name)}"
        elif isinstance(node, ArrayAccessNode):
            idx_reg = self.pick_scratch(current_busy)
            code = self.emit_eval(node.index, idx_reg, current_busy)
            tag = self.get_array_tag(node.name)
            code += self.format_macro_call("\\HG", [tag, idx_reg, target_reg])
            return code
        elif isinstance(node, ArgLenNode):
            self.used_scratch_regs.add("\\e")
            arg_reg = self.pick_scratch(current_busy)
            code = self.emit_eval(node.arg_idx, arg_reg, current_busy)
            code += self.format_macro_call("\\HL", [arg_reg]) + f"{target_reg}\\e"
            return code
        elif isinstance(node, ArgvCharNode):
            self.used_scratch_regs.update({"\\f", "\\g", "\\h"})
            arg_reg = self.pick_scratch(current_busy)
            char_reg = self.pick_scratch(current_busy | {arg_reg})
            code = self.emit_eval(node.arg_idx, arg_reg, current_busy)
            code += self.emit_eval(node.char_idx, char_reg, current_busy | {arg_reg})
            code += self.format_macro_call("\\HV", [arg_reg, char_reg]) + f"{target_reg}\\f"
            return code
        elif isinstance(node, BinaryOpNode):
            code = self.emit_eval(node.left, target_reg, busy_regs)
            
            if node.op == '%':
                self.used_scratch_regs.add("\\d")
                busy_for_right = current_busy | {"\\d"}
            else:
                busy_for_right = current_busy

            right_reg = self.pick_scratch(busy_for_right)
            right_code, right_val = self.emit_operand(node.right, right_reg, busy_for_right)
            code += right_code
            
            if node.op == '+':
                code += f"\\advance{target_reg}{right_val}"
            elif node.op == '-':
                code += f"\\advance{target_reg}-{right_val}"
            elif node.op == '*':
                code += f"\\multiply{target_reg}{right_val}"
            elif node.op == '/':
                code += f"\\divide{target_reg}{right_val}"
            elif node.op == '%':
                code += f"\\d{target_reg}\\divide\\d{right_val}\\multiply\\d{right_val}\\advance{target_reg}-\\d"
            return code

    def emit_block(self, nodes):
        return "".join(self.emit_node(n) for n in nodes)

    def emit_node(self, node):
        if isinstance(node, AssignNode):
            tex_var = self.get_var(node.target.name)
            return self.emit_eval(node.rhs, tex_var)

        elif isinstance(node, ArrayAssignNode):
            self.used_scratch_regs.update({"\\i", "\\j"})
            code = self.emit_eval(node.index, "\\i")
            code += self.emit_eval(node.rhs, "\\j", busy_regs={"\\i"})
            tag = self.get_array_tag(node.name)
            code += self.format_macro_call("\\HS", [tag, "\\i", "\\j"])
            return code

        elif isinstance(node, ArrayLiteralAssignNode):
            self.used_scratch_regs.update({"\\i", "\\j"})
            code_parts = []
            tag = self.get_array_tag(node.name)
            for i, elem in enumerate(node.elements):
                code = f"\\i{i} "
                code += self.emit_eval(elem, "\\j", busy_regs={"\\i"})
                code += self.format_macro_call("\\HS", [tag, "\\i", "\\j"])
                code_parts.append(code)
            return "".join(code_parts)

        elif isinstance(node, PrintNode):
            reg = self.pick_scratch()
            code, val = self.emit_operand(node.operand, reg)
            if node.is_char:
                if isinstance(node.operand, IntNode):
                    if node.operand.val in (10, 13):
                        code += "\\HP"
                    else:
                        code += f"\\char{val}"
                else:
                    code += f"\\ifnum{val}=10\\HP\\else\\ifnum{val}=13\\HP\\else\\char{val}\\fi\\fi"
            else:
                code += f"\\the{val}"
            if node.newline:
                code += "\\HP"
            return code

        elif isinstance(node, PrintStringNode):
            TEX_SPECIALS = set(r'\_{}%#~^&$')
            res = []
            for ch in node.text:
                if ch == '\n':
                    res.append("\\HP")
                elif ch == ' ':
                    res.append("\\ ")
                elif ch in TEX_SPECIALS:
                    res.append(f"\\char{ord(ch)}")
                else:
                    res.append(ch)
            if node.newline:
                res.append("\\HP")
            return "".join(res)

        elif isinstance(node, IfNode):
            left_reg = self.pick_scratch()
            right_reg = self.pick_scratch({left_reg})
            left_code, left_val = self.emit_operand(node.cond.left, left_reg, {left_reg, right_reg})
            right_code, right_val = self.emit_operand(node.cond.right, right_reg, {left_reg})
            
            tex_op, inverted = self.OP_MAP[node.cond.op]
            code = left_code + right_code + f"\\ifnum{left_val}{tex_op}{right_val}"
            true_str = self.emit_block(node.true_body)
            false_str = self.emit_block(node.false_body)
            
            if not inverted:
                code += true_str
                if false_str:
                    code += f"\\else{false_str}"
            else:
                code += false_str
                code += f"\\else{true_str}"
            code += "\\fi"
            return code

        elif isinstance(node, WhileNode):
            loop_macro = self.get_loop_name()
            left_reg = self.pick_scratch()
            right_reg = self.pick_scratch({left_reg})
            tex_op, inverted = self.OP_MAP[node.cond.op]
            left_code, left_val = self.emit_operand(node.cond.left, left_reg, {left_reg, right_reg})
            right_code, right_val = self.emit_operand(node.cond.right, right_reg, {left_reg})
            cond_code = left_code + right_code
            body_str = self.emit_block(node.body)
            
            if not inverted:
                return f"\\def{loop_macro}{{{cond_code}\\ifnum{left_val}{tex_op}{right_val}{body_str}{loop_macro}\\fi}}{loop_macro}"
            else:
                return f"\\def{loop_macro}{{{cond_code}\\ifnum{left_val}{tex_op}{right_val}\\else{body_str}{loop_macro}\\fi}}{loop_macro}"

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