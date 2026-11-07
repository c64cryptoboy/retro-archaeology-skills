"""Conservative DTL-only reading projection; detailed groups remain untouched."""
from collections import Counter
from dataclasses import replace
import expression_display as display
from dtl_for import FORMS, corridor_reason, typed_shape
from reading_projection import (expressions, references, render_statement,
                                statement_events, substitute_statement)

SCOPE = ('Local normal-path reading only: ordered reads/operations and explicit entrypoints are checked; '
         'no hidden-native-entry, asynchronous timing, original-source or numeric-equivalence proof. '
         'PRINT separator style is retained.')
PURE_FUNCTIONS = frozenset(('SGN', 'INT', 'ABS', 'SQR', 'LOG', 'EXP', 'COS', 'SIN', 'TAN',
                           'ATN', 'LEN', 'STR$', 'VAL', 'ASC', 'CHR$', 'LEFT$', 'RIGHT$', 'MID$'))
INLINE_FUNCTIONS = frozenset(('RND', 'PEEK', 'FRE', 'POS'))
OPERATORS = frozenset(('ADD', 'SUBTRACT', 'MULTIPLY', 'DIVIDE', 'POWER', 'AND', 'OR', 'NEGATE', 'NOT'))
SPACE_KEYWORDS = frozenset(('PRINT', 'READ', 'INPUT', 'GET', 'OPEN', 'CLOSE', 'SYS', 'POKE', 'WAIT',
                            'DIM', 'FOR', 'IF', 'ON', 'GOTO', 'GOSUB', 'RESTORE', 'RUN', 'DEF',
                            'NEXT', 'LET', 'THEN', 'TO', 'STEP'))


def spaced_basic(data, tokens):
    """Expand tokens with keyword boundaries; never invent punctuation/separators.

    Quoted bytes, REM and DATA payloads use the decoder's exact spelling. The
    native SYS tail does not call this routine. DATA resumes token mode at colon.
    """
    parts = []
    quoted = rem = in_data = pending_space = False
    for b in data:
        token = tokens.get(f'{b:02X}') if not (quoted or rem or in_data) else None
        text = token if token is not None else chr(b) if 32 <= b <= 126 else f'{{$%02X}}' % b
        if pending_space and text and not text[0].isspace():
            parts.append(' ')
        pending_space = False
        if token in SPACE_KEYWORDS:
            if parts and parts[-1] and not parts[-1][-1].isspace() and parts[-1][-1] not in ':;,(=':
                parts.append(' ')
            parts.append(text)
            pending_space = True
        else:
            parts.append(text)
        if b == 34 and not rem:
            quoted = not quoted
        elif token is not None:
            rem = b == 0x8f
            in_data = b == 0x83
        elif b == 58 and not quoted and not rem:
            in_data = False
    return ''.join(parts)


def instruction_events(rows):
    """Return the exact permitted operation/read order, or refuse the corridor.

    Literal pushes are immutable atoms. Everything else admitted has an event,
    including arithmetic and typed stores. Opaque calls are not silently pure.
    """
    events = []
    for i, row in enumerate(rows):
        name, control = row['mnemonic'], row.get('control')
        if row.get('grammar') == 'basic_island':
            return None
        if name.startswith('INTEGER_') or name in ('REAL_LITERAL', 'STRING_LITERAL'):
            if control != 'fallthrough':
                return None
            continue
        scalar_or_array = (name.startswith(('LOAD_', 'STORE_')) and
                           ('SCALAR' in name or 'ARRAY' in name))
        function = (name in ('FUNCTION', 'FUNCTION_F8') and
                    row.get('operands', {}).get('operation') in PURE_FUNCTIONS | INLINE_FUNCTIONS)
        if control == 'fallthrough' and (scalar_or_array or function or name in OPERATORS or
                                         name.startswith('COMPARE_') or name == 'POKE'):
            events.append(row['address'])
        elif i == len(rows)-1 and (name == 'IF_SKIP_FALSE' and control == 'conditional' or
                                  name in FORMS and typed_shape(row, FORMS)):
            events.append(row['address'])
        else:
            return None
    return events


def projection_reason(rows, statement, targets):
    reason = corridor_reason(rows, targets)
    if reason:
        return reason
    expected = instruction_events(rows)
    if expected is None:
        return 'Unsupported operation/control in reading corridor.'
    actual = statement_events(statement)
    if actual != expected:
        return 'Projected read/operation order or ownership differs from original instructions.'
    if len(actual) != len(set(actual)):
        return 'Projected evaluation identity is repeated.'
    return None


def merge(left, right, statement, action):
    return dict(indices=left['indices'] + right['indices'], rows=left['rows'] + right['rows'],
                statement=statement, arguments=expressions(statement),
                actions=left['actions'] + right['actions'] + [action],
                text=render_statement(statement))


def simple_functions(output, result, targets, tokens, uses):
    """Function-local folding; ordinary call-site temporary policy is unchanged."""
    from dtl_fn_reading import fold_functions
    return fold_functions(output, result, targets, tokens, uses, instruction_events)


def build_reading(report, result, statements, arguments, targets, tokens):
    groups = result['groups']
    assert len(groups) == len(statements) == len(arguments)
    uses = Counter()
    for args in arguments:
        for expression in args:
            uses.update(references(expression))
    loops = {x['address']: x for x in result['forIndex']['loops']}
    output, refusals = [], []
    for index, (group, statement, args) in enumerate(zip(groups, statements, arguments)):
        entry = dict(indices=[index], rows=group['instructions'], statement=statement,
                     arguments=args, actions=[], text=group['text'])
        complete = group['kind'] == 'inferred' and '<?>' not in group['text']
        if not complete:
            entry['statement'] = None
        elif statement is not None and statement.kind == 'for' and statement.default_step:
            if not entry['rows'] or not typed_shape(entry['rows'][-1], FORMS):
                entry['statement'] = replace(statement, default_step=False)
        if entry['statement'] is not None:
            # Only adjacent candidates; do not search backward across statements.
            while output:
                previous = output[-1]
                producer = previous['statement']
                consumer = entry['statement']
                if producer is None or producer.kind != 'temporary' or not producer.eligible:
                    break
                local_uses = Counter()
                for expression in expressions(consumer):
                    local_uses.update(references(expression))
                if not local_uses[producer.target]:
                    break
                reason = None
                if uses[producer.target] != 1 or local_uses[producer.target] != 1:
                    reason = 'Temporary has repeated or additional consumers.'
                proposed = substitute_statement(consumer, producer.target, producer.expressions[0])
                corridor = previous['rows'] + entry['rows']
                reason = reason or projection_reason(corridor, proposed, targets)
                if reason:
                    refusals.append(dict(kind='temporary', name=producer.target,
                                         consumer=group['instructions'][-1]['address'], reason=reason))
                    break
                output.pop()
                entry = merge(previous, entry, proposed, dict(kind='inline-temporary', name=producer.target))
            statement = entry['statement']
            if statement.kind == 'for':
                if statement.default_step:
                    # The unit-step opcode itself supplies this value, not a
                    # computed expression whose evaluation could be lost.
                    entry['text'] = render_statement(statement)
                    entry['actions'].append(dict(kind='omit-default-step'))
                loop = loops.get(statement.origin)
                if output and loop and loop['status'] == 'associated':
                    previous = output[-1]
                    initializer = previous['statement']
                    if (initializer is not None and initializer.kind == 'assignment' and
                            initializer.origin == loop['initializer']['storeAddress'] and
                            initializer.target == statement.target):
                        proposed = replace(statement, start=initializer.expressions[0],
                                           initializer_origin=initializer.origin)
                        reason = projection_reason(previous['rows'] + entry['rows'], proposed, targets)
                        if reason:
                            refusals.append(dict(kind='for-initializer', address=statement.origin, reason=reason))
                        else:
                            output.pop()
                            entry = merge(previous, entry, proposed, dict(kind='fuse-for-initializer',
                                                                         store=initializer.origin))
        if group['kind'] == 'embedded' and len(group['instructions']) == 1:
            row = group['instructions'][0]
            raw = bytes.fromhex(row['bytes'])
            if row.get('grammar') == 'basic_island' and raw[:1] == b'\0' and len(raw) == row.get('length'):
                from formats import module
                if module('dtl').basic_text(raw[1:], tokens) == group['text']:
                    text = spaced_basic(raw[1:], tokens)
                    if text != group['text']:
                        entry['text'] = text
                        entry['actions'].append(dict(kind='keyword-spacing'))
        statement = entry['statement']
        if statement is not None and statement.kind == 'conditional' and statement.false:
            expression = statement.expressions[0]
            if (expression.kind == 'binary' and expression.token in ('AND', 'OR') and
                    display.boolean_complement(expression) is not None):
                entry['statement'] = replace(statement, boolean_false=True)
                entry['text'] = render_statement(entry['statement'])
                entry['actions'].append(dict(kind='boolean-complement'))
        output.append(entry)
    output = simple_functions(output, result, targets, tokens, uses)
    projected = []
    for entry in output:
        original = [groups[i] for i in entry['indices']]
        detail_warnings = list(dict.fromkeys(w for g in original for w in g['warnings']))
        warnings = detail_warnings
        if 'definitionRepresentations' in entry:
            from dtl_fn_reading import bookkeeping_warning
            warnings = [w for w in detail_warnings if not bookkeeping_warning(w)]
        # Only folded-definition bookkeeping moves out of the compact display.
        # All original warnings remain in detailed groups and explicit metadata.
        projected.append(dict(text=entry['text'], kind=entry.get('kind', original[-1]['kind']),
                              sourceGroups=entry['indices'],
                              instructionAddresses=[r['address'] for r in entry['rows']],
                              warnings=warnings, actions=entry['actions'],
                              evaluationOrder=statement_events(entry['statement']) if entry['statement'] else None))
        if 'deferredEvaluationOrder' in entry:
            projected[-1]['deferredEvaluationOrder'] = entry['deferredEvaluationOrder']
            projected[-1]['definitionEvaluationOrder'] = entry['definitionEvaluationOrder']
            projected[-1]['definitionRepresentations'] = entry['definitionRepresentations']
            projected[-1]['detailWarnings'] = detail_warnings
    assert [i for g in projected for i in g['sourceGroups']] == list(range(len(groups)))
    return dict(schema='dtl-idiomatic-reading-v1', scope=SCOPE, groups=projected, refusals=refusals,
                counts=dict(Counter(a['kind'] for g in projected for a in g['actions'])),
                printSeparatorInsertion=False, otherCompilerContractsEnabled=False)
