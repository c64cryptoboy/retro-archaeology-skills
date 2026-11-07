"""VM-neutral structured reading helpers. Adapters, not text, supply semantics.

Origin identities include reads and arithmetic, not only side-effectful calls.
A client must compare the resulting order against its original instructions.
"""
from collections import Counter
from dataclasses import dataclass, replace
import expression_display as display


@dataclass(frozen=True)
class Statement:
    kind: str
    expressions: tuple = ()
    target: str = ''
    suffix: str = ''
    origin: int | None = None
    false: bool = False
    eligible: bool = False
    default_step: bool = False
    start: display.DisplayExpr | None = None
    initializer_origin: int | None = None
    boolean_false: bool = False


def expression_events(expression):
    result = [event for child in expression.children for event in expression_events(child)]
    if expression.origin is not None:
        result.append(expression.origin)
    return result


def references(expression):
    found = Counter({expression.token: 1}) if expression.kind == 'temporary' else Counter()
    for child in expression.children:
        found.update(references(child))
    return found


def expressions(statement):
    return ((statement.start,) if statement.start is not None else ()) + statement.expressions


def substitute(expression, name, value):
    if expression.kind == 'temporary' and expression.token == name:
        return value
    return replace(expression, children=tuple(substitute(c, name, value) for c in expression.children))


def substitute_statement(statement, name, value):
    return replace(statement, expressions=tuple(substitute(e, name, value) for e in statement.expressions),
                   start=substitute(statement.start, name, value) if statement.start is not None else None)


def statement_events(statement):
    result = []
    if statement.start is not None:
        result.extend(expression_events(statement.start))
        if statement.initializer_origin is not None:
            result.append(statement.initializer_origin)
    for expression in statement.expressions:
        result.extend(expression_events(expression))
    if statement.origin is not None:
        result.append(statement.origin)
    return result


def render_statement(statement):
    text = [display.render(e) for e in statement.expressions]
    kind, target = statement.kind, statement.target
    if kind in ('assignment', 'temporary'):
        return target + ' = ' + text[0]
    if kind == 'array-assignment':
        return text[0] + ' = ' + text[1]
    if kind == 'conditional':
        condition = display.false_test(statement.expressions[0]) if statement.false else text[0]
        if statement.boolean_false and statement.false:
            opposite = display.boolean_complement(statement.expressions[0])
            if opposite is None:
                raise ValueError('Reading Boolean complement lost its proved comparison tree')
            condition = display.render(opposite)
        return 'IF ' + condition + ' THEN GOTO ' + target
    if kind == 'on':
        return 'ON ' + text[0] + ' ' + target
    if kind == 'statement':
        return target + ' ' + ', '.join(text) + statement.suffix
    if kind == 'sys':
        return 'SYS ' + text[0] + statement.suffix
    if kind == 'fn-return':
        return 'RETURN ' + target + ' = ' + text[0]
    if kind == 'for':
        start = display.render(statement.start) if statement.start is not None else target
        return ('FOR ' + target + ' = ' + start + ' TO ' + text[0] +
                ('' if statement.default_step else ' STEP ' + text[1]))
    raise ValueError('Unsupported reading statement: ' + kind)


def render_reading(report):
    """Portable compact renderer; detailed evidence remains in report['groups']."""
    view = report.get('readingView')
    if view is None:
        raise ValueError('No evidenced reading projection for this compiler family')
    lines = ['; BASIC-like reading projection; not original or runnable BASIC.',
             '; Original groups, warnings, encoded targets and bytes remain in the detailed report.',
             '; ' + view['scope']]
    for item in view['groups']:
        addresses = item['instructionAddresses']
        first, last = (addresses[0], addresses[-1]) if addresses else (0, 0)
        lines.append(f'\n[{item["kind"]} ${first:04X}..${last:04X}] ' + item['text'])
        lines.extend('; ' + warning for warning in item['warnings'])
    for datum in report.get('retainedData', []):
        lines.append(f'\n; DATA ${datum["address"]:04X}: ' + (datum['text'] or 'opaque bytes'))
        lines.append('; ' + datum['caveat'])
    return '\n'.join(lines) + '\n'
