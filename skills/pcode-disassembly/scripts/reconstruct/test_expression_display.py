"""Authored tree/duality/presentation tests; no target code or source oracle."""
import copy
import itertools
import operator
import re
import unittest
from expression_display import binary, call, false_test, leaf, render, unary
from symbolic import lift
from test_reconstruct import row, texts


# Independent test-only lexer/parser. It does not import formatter precedence.
TOKEN = re.compile(r'\s*(<>|<=|>=|<\?>|"[^"\r\n]*"|[0-9]+(?:\.[0-9]+)?|[A-Za-z_][A-Za-z_0-9]*[%$]?|[^\s])')


class Parser:
    def __init__(self, text):
        self.tokens = TOKEN.findall(text)
        self.i = 0

    def peek(self):
        return self.tokens[self.i] if self.i < len(self.tokens) else None

    def take(self, wanted=None):
        value = self.peek()
        if value is None or wanted is not None and value != wanted:
            raise ValueError(('Expected', wanted, 'got', value, self.tokens, self.i))
        self.i += 1
        return value

    def chain(self, child, operators):
        value = child()
        while self.peek() in operators:
            op = self.take()
            value = (op, value, child())
        return value

    def expression(self):
        return self.chain(self.and_expression, ('OR',))

    def and_expression(self):
        return self.chain(self.not_expression, ('AND',))

    def not_expression(self):
        if self.peek() == 'NOT':
            self.take()
            return ('NOT', self.not_expression())
        return self.chain(self.add_expression, ('=', '<>', '<', '<=', '>', '>='))

    def add_expression(self):
        return self.chain(self.multiply, ('+', '-'))

    def multiply(self):
        return self.chain(self.negative, ('*', '/'))

    def negative(self):
        if self.peek() == '-':
            self.take()
            return ('neg', self.negative())
        # Power nesting in the output is explicitly parenthesized, so no
        # dialect-dependent associativity needs to be inferred by the formatter.
        return self.chain(self.primary, ('^',))

    def primary(self):
        token = self.take()
        if token == '(':
            value = self.expression()
            self.take(')')
            return value
        if token == 'FN':
            token += ' ' + self.take()
        if self.peek() == '(':
            self.take()
            args = []
            if self.peek() != ')':
                args.append(self.expression())
                while self.peek() == ',':
                    self.take()
                    args.append(self.expression())
            self.take(')')
            return ('call', token, tuple(args))
        if not re.fullmatch(r'(?:[A-Za-z_][A-Za-z_0-9]*[%$]?|[0-9]+(?:\.[0-9]+)?|"[^"\r\n]*"|<\?>)', token):
            raise ValueError(('Not an atom', token))
        return ('atom', token)


def parse(text):
    parser = Parser(text)
    tree = parser.expression()
    if parser.peek() is not None:
        raise ValueError(('Trailing tokens', parser.tokens[parser.i:]))
    return tree


def explicit(node):
    if node.kind == 'leaf':
        # A negative literal is one tree leaf, not an outer unary operation on
        # its parent's power. Make that boundary explicit in this oracle too.
        return '(' + node.token + ')' if node.token.startswith('-') else node.token
    if node.kind == 'call':
        return node.token + '(' + ', '.join(map(explicit, node.children)) + ')'
    if node.kind == 'unary':
        return '(' + ('NOT ' if node.token == 'NOT' else '-') + explicit(node.children[0]) + ')'
    return '(' + explicit(node.children[0]) + ' ' + node.token + ' ' + explicit(node.children[1]) + ')'


def report(*rows):
    return {'instructions': [{'address': 0x1000 + i, **r} for i, r in enumerate(rows)]}


def scalar(name):
    return row('LOAD_REAL_SCALAR', operands={'name': name, 'value': 2})


def stored():
    return row('STORE_REAL_SCALAR', operands={'name': 'A', 'value': 9})


class ExpressionDisplayTests(unittest.TestCase):
    def test_user_arithmetic_shape(self):
        tree = binary('+', leaf('1'), call('INT', [binary('*', leaf('T_0C33'), leaf('20'))]))
        self.assertEqual(render(tree), '1 + INT(T_0C33 * 20)')

    def test_all_comparison_complements(self):
        operations = {'=': operator.eq, '<>': operator.ne, '<': operator.lt,
                      '<=': operator.le, '>': operator.gt, '>=': operator.ge}
        duals = {'=': '<>', '<>': '=', '<': '>=', '>=': '<', '>': '<=', '<=': '>'}
        for op, dual in duals.items():
            with self.subTest(op=op):
                self.assertEqual(false_test(binary(op, leaf('D$'), leaf('C$'))), 'D$ ' + dual + ' C$')
                for values in ((-7, 0, 2), ('', 'A', 'B')):
                    for a, b in itertools.product(values, repeat=2):
                        self.assertEqual(not operations[op](a, b), operations[dual](a, b))

    def test_numeric_false_is_not_bitwise_not(self):
        for text in ('0', '2', '-7', 'T_1234'):
            self.assertEqual(parse(false_test(leaf(text))), parse('(' + text + ') = 0'))
            self.assertNotIn('NOT', false_test(leaf(text)))

    def test_right_addition_not_reassociated(self):
        self.assertEqual(render(binary('+', leaf('A'), binary('+', leaf('B'), leaf('C')))), 'A + (B + C)')
        self.assertEqual(render(binary('+', binary('+', leaf('A'), leaf('B')), leaf('C'))), 'A + B + C')

    def test_subtraction_division_and_mixed_precedence(self):
        cases = [(binary('-', leaf('A'), binary('-', leaf('B'), leaf('C'))), 'A - (B - C)'),
                 (binary('/', leaf('A'), binary('*', leaf('B'), leaf('C'))), 'A / (B * C)'),
                 (binary('*', binary('+', leaf('A'), leaf('B')), leaf('C')), '(A + B) * C'),
                 (binary('+', leaf('A'), binary('*', leaf('B'), leaf('C'))), 'A + B * C')]
        for tree, expected in cases:
            self.assertEqual(render(tree), expected)
            self.assertEqual(parse(render(tree)), parse(explicit(tree)))

    def test_power_trees_do_not_assume_associativity(self):
        self.assertEqual(render(binary('^', binary('^', leaf('A'), leaf('B')), leaf('C'))), '(A ^ B) ^ C')
        self.assertEqual(render(binary('^', leaf('A'), binary('^', leaf('B'), leaf('C')))), 'A ^ (B ^ C)')
        self.assertEqual(render(binary('^', unary('-', leaf('A')), leaf('B'))), '(-A) ^ B')
        self.assertEqual(render(unary('-', binary('^', leaf('A'), leaf('B')))), '-(A ^ B)')

    def test_nested_comparisons_not_chained(self):
        for side in (0, 1):
            args = [leaf('A'), leaf('B')]
            args[side] = binary('<', leaf('C'), leaf('D'))
            tree = binary('=', *args)
            self.assertEqual(parse(render(tree)), parse(explicit(tree)))
            self.assertIn('(C < D)', render(tree))

    def test_logical_not_is_not_comparison_complement(self):
        tree = unary('NOT', binary('AND', leaf('A'), leaf('B')))
        self.assertEqual(render(tree), 'NOT (A AND B)')
        self.assertEqual(parse(false_test(tree)), parse('(' + explicit(tree) + ') = 0'))

    def test_opaque_leaf_is_not_parsed(self):
        opaque = leaf('A + B')
        self.assertEqual(render(opaque), 'A + B')
        self.assertEqual(render(binary('*', opaque, leaf('C'))), '(A + B) * C')
        self.assertEqual(false_test(leaf('(A > B)')), '((A > B)) = 0')

    def test_quotes_and_function_argument_delimiters(self):
        text = '"IF ((A > B)) = 0 + X"'
        tree = call('MID$', [leaf(text), binary('+', leaf('I'), leaf('1')), leaf('2')])
        self.assertEqual(render(tree), 'MID$(' + text + ', I + 1, 2)')
        self.assertEqual(parse(render(tree)), parse(explicit(tree)))

    def test_unknown_and_invalid_operators(self):
        self.assertEqual(render(binary('+', leaf('<?>'), leaf('2'))), '<?> + 2')
        with self.assertRaises(ValueError):
            binary('MAGIC', leaf('A'), leaf('B'))
        with self.assertRaises(ValueError):
            unary('!', leaf('A'))

    def test_exhaustive_two_operator_trees(self):
        operators = ('+', '-', '*', '/', '^', '=', '<>', '<', '<=', '>', '>=', 'AND', 'OR')
        for parent, child, side in itertools.product(operators, operators, (0, 1)):
            args = [leaf('A'), leaf('B')]
            args[side] = binary(child, leaf('C'), leaf('D'))
            tree = binary(parent, *args)
            with self.subTest(parent=parent, child=child, side=side):
                self.assertEqual(parse(render(tree)), parse(explicit(tree)))

    def test_unary_function_array_and_negative_literal_trees(self):
        trees = [unary('-', leaf('A')), unary('NOT', leaf('B')), leaf('-2'),
                 call('FN AB', [binary('+', leaf('X'), leaf('1'))]),
                 call('AR', [binary('*', leaf('X'), leaf('2')), leaf('Y')])]
        for child, op, side in itertools.product(trees, ('+', '-', '*', '/', '^', '=', 'AND', 'OR'), (0, 1)):
            args = [leaf('A'), leaf('B')]
            args[side] = child
            tree = binary(op, *args)
            with self.subTest(child=child, op=op, side=side):
                self.assertEqual(parse(render(tree)), parse(explicit(tree)))


class DTLPreservingPresentationTests(unittest.TestCase):
    def check(self, raw):
        before = copy.deepcopy(raw)
        old, new = lift('dtl', raw, readable=False), lift('dtl', raw)
        self.assertEqual(raw, before)
        projected = copy.deepcopy(new)
        # The separate compact view is additive; this test still requires every
        # original detailed field except deliberately formatted text to match.
        reading = projected.pop('readingView')
        self.assertFalse(reading['printSeparatorInsertion'])
        self.assertEqual(len(old['groups']), len(new['groups']))
        for prior, current in zip(old['groups'], projected['groups']):
            current['text'] = prior['text']
        self.assertEqual(old, projected)
        self.assertEqual(new, lift('dtl', raw))
        return old, new

    def test_function_arithmetic_heading(self):
        raw = report(row('INTEGER_BYTE', 1), scalar('T'), row('INTEGER_BYTE', 20), row('MULTIPLY'),
                     row('FUNCTION', operands={'operation': 'INT'}), row('ADD'), stored())
        old, new = self.check(raw)
        self.assertEqual(texts(old), 'A = (1 + INT((T * 20)))')
        self.assertEqual(texts(new), 'A = 1 + INT(T * 20)')

    def test_numeric_and_string_false_comparisons(self):
        for operation, wanted in (('COMPARE_GT', '<='), ('COMPARE_EQ', '<>'), ('COMPARE_NE', '=')):
            raw = report(scalar('D$'), scalar('C$'), row(operation), row('IF_SKIP_FALSE', targets=[0x1100]))
            _, new = self.check(raw)
            self.assertEqual(texts(new), 'IF D$ ' + wanted + ' C$ THEN GOTO L_1100')

    def test_unknown_false_comparison_keeps_uncertainty(self):
        raw = report(row('INTEGER_BYTE', 2), row('COMPARE_GT'), row('IF_SKIP_FALSE', targets=[0x1100]))
        _, new = self.check(raw)
        self.assertIn('IF (<?> > 2) = 0', texts(new))
        self.assertGreater(new['coverage']['partial'], 0)

    def test_effect_is_materialized_once_at_same_site(self):
        raw = report(row('INTEGER_BYTE', 1), row('FUNCTION', operands={'operation': 'RND'}),
                     row('INTEGER_BYTE', 20), row('MULTIPLY'), row('FUNCTION', operands={'operation': 'INT'}), stored())
        old, new = self.check(raw)
        self.assertEqual(texts(new), 'T_1001 = RND(1)\nA = INT(T_1001 * 20)')
        self.assertEqual(texts(old).count('RND('), texts(new).count('RND('))

    def test_fn_capture_order_and_canonical_indices(self):
        raw = report(scalar('X'), row('INTEGER_BYTE', 2), row('ADD'), row('INTEGER_BYTE', 4),
                     row('FN_CALL', operands={'name': 'F', 'value': 2}), row('ADD'), stored())
        old, new = self.check(raw)
        self.assertIn('T_VALUE_1002 = X + 2', texts(new))
        self.assertLess(texts(new).index('T_VALUE_1002 ='), texts(new).index('FN F('))
        self.assertEqual(old['functionIndex'], new['functionIndex'])

    def test_embedded_basic_never_reformatted(self):
        text = 'PRINT"IF ((A>B))=0":A=(1+INT((B*20)))'
        _, new = self.check(report(row('BASIC', grammar='basic_island', operands={'text': text})))
        self.assertEqual(texts(new), text)
        self.assertEqual(new['groups'][0]['kind'], 'embedded')

    def test_bitwise_not_numeric_test_is_not_replaced(self):
        _, new = self.check(report(row('INTEGER_BYTE', 2), row('NOT'), row('IF_SKIP_FALSE', targets=[0x1100])))
        self.assertIn('NOT 2', texts(new))
        self.assertIn('= 0 THEN', texts(new))

    def test_other_families_keep_explicit_headings(self):
        raw = report(row('CONST_U8', value=19), row('CONST_U8', value=4), row('SUBTRACT'), row('STORE_VAR', variable='A'))
        self.assertEqual(lift('blitz', raw), lift('blitz', raw, readable=False))
        self.assertEqual(texts(lift('blitz', raw)), 'A = (19 - 4)')


if __name__ == '__main__':
    unittest.main()
