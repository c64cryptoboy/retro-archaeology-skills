"""Structured reading expressions; no parsing or rewriting of emitted BASIC.

Parentheses preserve the evaluation tree, not merely algebraic equivalence.
Opaque leaves stay opaque. The caller supplies nodes from known VM operations.
"""
from dataclasses import dataclass
import re

COMPLEMENT = {'=': '<>', '<>': '=', '<': '>=', '>=': '<', '>': '<=', '<=': '>'}
PRECEDENCE = {'OR': 10, 'AND': 20, **{op: 40 for op in COMPLEMENT},
              '+': 50, '-': 50, '*': 60, '/': 60, '^': 80}
_ATOM = re.compile(r'(?:[A-Za-z_][A-Za-z_0-9]*[%$]?|[0-9]+(?:\.[0-9]+)?|"[^"\r\n]*"|<\?>)\Z')
_NEGATIVE = re.compile(r'-[0-9]+(?:\.[0-9]+)?\Z')


@dataclass(frozen=True)
class DisplayExpr:
    kind: str
    token: str
    children: tuple = ()
    origin: int | None = None  # Evaluation identity supplied by a VM adapter, never inferred from text.


def leaf(text, *, origin=None):
    return DisplayExpr('leaf', text, origin=origin)


def temporary(name):
    """A captured value reference, not a fresh read of the original expression."""
    return DisplayExpr('temporary', name)


def node(expression):
    return expression.display_node if expression.display_node is not None else leaf(expression.text)


def binary(symbol, left, right, *, origin=None):
    if symbol not in PRECEDENCE:
        raise ValueError('Unsupported display operator: ' + symbol)
    return DisplayExpr('binary', symbol, (left, right), origin)


def unary(symbol, argument, *, origin=None):
    if symbol not in ('-', 'NOT'):
        raise ValueError('Unsupported display unary operator: ' + symbol)
    return DisplayExpr('unary', symbol, (argument,), origin)


def call(name, arguments, *, origin=None):
    return DisplayExpr('call', name, tuple(arguments), origin)


def precedence(expression):
    if expression.kind == 'binary':
        return PRECEDENCE[expression.token]
    if expression.kind == 'unary':
        return 30 if expression.token == 'NOT' else 70
    if expression.kind in ('call', 'temporary'):
        return 100
    if expression.kind == 'leaf':
        if _ATOM.fullmatch(expression.token):
            return 100
        if _NEGATIVE.fullmatch(expression.token):
            return 70
        return 0  # Unknown/compound display leaf: never infer its parse structure.
    raise ValueError('Unsupported display node: ' + expression.kind)


def render(expression):
    kind, token, children = expression.kind, expression.token, expression.children
    if kind in ('leaf', 'temporary'):
        return token
    if kind == 'call':
        return token + '(' + ', '.join(render(child) for child in children) + ')'
    if kind == 'unary':
        child = children[0]
        text = render(child)
        # Keep explicit nesting around another unary or any power; do not rely
        # on a dialect's power/unary convention or turn --A into another token.
        if (precedence(child) <= precedence(expression) or child.kind == 'unary' or
                child.kind == 'binary' and child.token == '^'):
            text = '(' + text + ')'
        return ('NOT ' if token == 'NOT' else '-') + text
    if kind != 'binary' or len(children) != 2:
        raise ValueError('Malformed display expression')
    rendered = []
    for side, child in enumerate(children):
        lower = precedence(child) < precedence(expression)
        same = precedence(child) == precedence(expression)
        # Right nesting is significant even for +/*: roundoff/overflow and
        # string semantics prohibit reassociation. Relations never form chains.
        protect = lower or same and (side == 1 or token in COMPLEMENT)
        if token == '^' and child.kind != 'call' and precedence(child) != 100:
            protect = True  # Explicit power trees, independent of associativity.
        text = render(child)
        rendered.append('(' + text + ')' if protect else text)
    return rendered[0] + ' ' + token + ' ' + rendered[1]


def boolean_complement(expression):
    """Complement only trees of comparisons joined by Boolean AND/OR.

    This is a BASIC-like display identity (false=0, true=-1), not permission to
    convert arbitrary bitwise operands or short-circuit control flow. Preserve
    child order, grouping and all evaluation-origin identities.
    """
    if expression.kind != 'binary' or len(expression.children) != 2:
        return None
    if expression.token in COMPLEMENT:
        return binary(COMPLEMENT[expression.token], *expression.children, origin=expression.origin)
    if expression.token not in ('AND', 'OR'):
        return None
    children = tuple(boolean_complement(child) for child in expression.children)
    if any(child is None for child in children):
        return None
    return binary('OR' if expression.token == 'AND' else 'AND', *children, origin=expression.origin)


def false_test(expression):
    """Opposite direct comparison, otherwise an explicit numeric-zero test."""
    if expression.kind == 'binary' and expression.token in COMPLEMENT:
        return render(binary(COMPLEMENT[expression.token], *expression.children))
    return render(binary('=', expression, leaf('0')))
