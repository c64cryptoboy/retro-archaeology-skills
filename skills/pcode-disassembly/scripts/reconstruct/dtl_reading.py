"""Conservative DTL-only reading projection; detailed groups remain untouched."""
from collections import Counter
from dataclasses import replace
import expression_display as display
from dtl_branches import explicit_targets
from dtl_for import FORMS, corridor_reason, typed_shape
from reading_projection import (expressions, references, render_statement,
                                statement_events, substitute_statement)

SCOPE = ('Local normal-path reading only: ordered reads/operations and explicit entrypoints are checked; '
         'no hidden-native-entry, asynchronous timing, original-source or numeric-equivalence proof. '
         'PRINT separator style is retained.')
PURE_FUNCTIONS = frozenset(('SGN', 'INT', 'ABS', 'SQR', 'LOG', 'EXP', 'COS', 'SIN', 'TAN',
                           'ATN', 'LEN', 'STR$', 'VAL', 'ASC', 'CHR$', 'LEFT$', 'RIGHT$', 'MID$'))
INLINE_FUNCTIONS = frozenset(('RND', 'PEEK', 'FRE', 'POS'))
# Observed B8 selectors and their compatible short scalar stores.
SYSTEM_READS = {'TI': (0x18, 'STORE_REAL_SCALAR'), 'TI$': (0x19, 'STORE_STRING_SCALAR'),
                'ST': (0x1a, 'STORE_REAL_SCALAR')}
SYSTEM_STORES = {'STORE_REAL_SCALAR': (0xd0, 'real', 1), 'STORE_STRING_SCALAR': (0xd2, 'string', 1)}
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


def system_read(entry, uses):
    """Identify a single-use capture of this exact volatile B8 read."""
    producer = entry['statement']
    if (producer is None or producer.kind != 'temporary' or len(entry['rows']) != 1 or
            uses[producer.target] != 1):
        return None
    read = entry['rows'][0]
    operands = read.get('operands', {})
    name = operands.get('operation')
    if name not in SYSTEM_READS:
        return None
    selector, _ = SYSTEM_READS[name]
    if (read['mnemonic'] != 'FUNCTION' or read.get('grammar') != 'selector' or
            read.get('control') != 'fallthrough' or read.get('length') != 2 or
            read.get('opcode', 0xb8) != 0xb8 or read['bytes'] != bytes((0xb8, selector)).hex() or
            operands.get('selector') != selector or explicit_targets(read) or
            producer.expressions != (display.leaf(name, origin=read['address']),)):
        return None
    return name


def system_assignment(left, right, uses, targets):
    producer, consumer = left['statement'], right['statement']
    name = system_read(left, uses)
    if (name is None or consumer is None or consumer.kind != 'assignment' or len(right['rows']) != 1 or
            consumer.expressions != (display.temporary(producer.target),)):
        return None
    read, store = left['rows'][0], right['rows'][0]
    if (store['mnemonic'] != SYSTEM_READS[name][1] or not typed_shape(store, SYSTEM_STORES) or
            corridor_reason([read, store], targets) or consumer.origin != store['address']):
        return None
    return merge(left, right, replace(consumer, expressions=producer.expressions),
                 dict(kind='inline-system-read', name=name, read=read['address'], store=store['address']))


def status_comparison(left, right, uses, targets, regions):
    """Only ST, immutable integer, EQ/LT, and the original relative false edge."""
    from dtl_navigation import literal_value, shape
    condition = right['statement']
    if (condition is None or condition.kind != 'conditional' or not condition.false or
            len(right['rows']) != 3 or system_read(left, uses) != 'ST'):
        return None
    read = left['rows'][0]
    literal, compare, test = right['rows']
    rows = [read, literal, compare, test]
    relation = {'COMPARE_EQ': (0x2b, '='), 'COMPARE_LT': (0x2d, '<')}.get(compare['mnemonic'])
    if (relation is None or not shape(compare, relation[0], 'none', 'fallthrough', 1) or
            literal['mnemonic'] not in ('INTEGER_SMALL', 'INTEGER_BYTE') or
            explicit_targets(literal) or explicit_targets(compare) or corridor_reason(rows, targets)):
        return None
    value = literal_value(literal)
    captured = left['statement']
    if (value is None or condition.expressions != (display.binary(relation[1], display.temporary(captured.target),
            display.leaf(str(value)), origin=compare['address']),)):
        return None
    pc = test['address']
    if (test['mnemonic'] != 'IF_SKIP_FALSE' or test.get('grammar') != 'relative8' or
            test.get('control') != 'conditional' or test.get('length') != 2 or
            test.get('opcode', 0x4f) != 0x4f or len(test['targets']) != 1 or condition.origin != pc):
        return None
    dest, = test['targets']
    if (type(dest) is not int or not 2 <= dest - pc <= 255 or test['bytes'] != bytes((0x4f, dest - pc)).hex() or
            test['operands'].get('raw', test['bytes'][2:]) != test['bytes'][2:] or explicit_targets(test) != {dest} or condition.target != f'L_{dest:04X}' or
            any(regions.get(a) != test['region'] for a in (pc + 2, dest))):
        return None
    proposed = substitute_statement(condition, captured.target, captured.expressions[0])
    if statement_events(proposed) != [read['address'], compare['address'], pc]:
        return None
    return merge(left, right, proposed, dict(kind='inline-status-comparison', read=read['address'], test=pc))


def fn_value_poke(address, value, sink, calls, uses, targets):
    """An evaluated address survives a descriptor call; never re-read it after the call."""
    from dtl_fn_reading import body_events
    dest, byte, poke = (e['statement'] for e in (address, value, sink))
    if (dest is None or byte is None or dest.kind != 'temporary' or byte.kind != 'temporary' or
            len(dest.expressions) != 1 or len(byte.expressions) != 1 or dest.target == byte.target or
            uses[dest.target] != 1 or uses[byte.target] != 1 or
            poke.expressions != (display.temporary(dest.target), display.temporary(byte.target)) or
            any(e['actions'] for e in (address, value, sink)) or len(sink['rows']) != 1):
        return None
    store = sink['rows'][0]
    call = value['rows'][-1]
    expr = byte.expressions[0]
    if (store['mnemonic'] != 'POKE' or store['bytes'] != '50' or store.get('length') != 1 or
            store.get('grammar') != 'none' or poke.origin != store['address'] or
            call['mnemonic'] != 'FN_CALL' or expr.kind != 'call' or expr.origin != call['address'] or
            expr.token != calls.get(call['address'], {}).get('name') or len(expr.children) != 1):
        return None
    # No islands, other effects, nested calls, or instructions between the call and write.
    operands = address['rows'] + value['rows'][:-1]
    if any(r['mnemonic'] not in ('LOAD_REAL_SCALAR', 'INTEGER_SMALL', 'INTEGER_BYTE', 'INTEGER_WORD',
                                 'REAL_LITERAL', 'ADD', 'MULTIPLY') for r in operands):
        return None
    rows = operands + [call, store]
    proposed = replace(poke, expressions=(dest.expressions[0], expr))
    if (any(references(e) for e in proposed.expressions) or corridor_reason(rows, targets) or
            any(explicit_targets(r) for r in rows) or
            statement_events(proposed) != body_events(rows, calls, instruction_events)):
        return None
    return dict(indices=address['indices'] + value['indices'] + sink['indices'], rows=rows,
                statement=proposed, arguments=expressions(proposed), text=render_statement(proposed),
                actions=[dict(kind='fold-fn-value-poke', call=call['address'], poke=store['address'])])


def nested_fn_poke(entries, calls, uses, targets):
    """Two short scalar reads, two unary descriptor calls, one write, in that order."""
    from dtl_fn_reading import body_events
    if ([len(e['rows']) for e in entries] != [1, 2, 1, 1] or
            any(e['actions'] or e['statement'] is None for e in entries)):
        return None
    rows = [r for e in entries for r in e['rows']]
    addr, arg, inner, outer, store = rows
    dest, first, last, poke = (e['statement'] for e in entries)
    captures = (dest, first, last)
    if (any(s.kind != 'temporary' or uses[s.target] != 1 for s in captures) or
            len({s.target for s in captures}) != 3 or corridor_reason(rows, targets) or
            any(explicit_targets(r) for r in rows)):
        return None
    scalar = {'LOAD_REAL_SCALAR': (0x90, 'real', 1)}
    if (not all(typed_shape(r, scalar) and r['operands'].get('name') for r in (addr, arg)) or
            not all(r['mnemonic'] == 'FN_CALL' for r in (inner, outer)) or
            store['mnemonic'] != 'POKE' or store['bytes'] != '50' or store.get('grammar') != 'none' or
            store.get('length') != 1 or poke.origin != store['address'] or poke.target != 'POKE'):
        return None
    order = body_events(rows, calls, instruction_events)
    if order != [r['address'] for r in rows] or len(set(order)) != 5:
        return None
    # Check the actual detailed producers AND every consuming edge.  An equal-looking
    # read at another site is not the address sample already below the two call frames.
    a, x = (display.leaf(r['operands']['name'], origin=r['address']) for r in (addr, arg))
    def invocation(row, operand):
        return display.call(calls[row['address']]['name'], [operand], origin=row['address'])
    first_call = invocation(inner, x)
    if (dest.expressions != (a,) or first.expressions != (first_call,) or
            last.expressions != (invocation(outer, display.temporary(first.target)),) or
            poke.expressions != (display.temporary(dest.target), display.temporary(last.target))):
        return None
    proposed = replace(poke, expressions=(a, invocation(outer, first_call)))
    if statement_events(proposed) != order:
        return None
    return dict(indices=[i for e in entries for i in e['indices']], rows=rows, statement=proposed,
                arguments=expressions(proposed), text=render_statement(proposed),
                actions=[dict(kind='fold-nested-fn-poke', calls=order[2:4], poke=order[-1])])


def run_pair(left, right, targets):
    """The compiler emits 49 58 (clear, transfer to bootstrap) for bare RUN."""
    if len(left['rows']) != 1 or len(right['rows']) != 1:
        return False
    rows = left['rows'] + right['rows']
    return ([(r['mnemonic'], r['bytes'], r.get('control')) for r in rows] ==
            [('CLEAR_OR_RUN', '49', 'runtime-managed'), ('RUN_BOOTSTRAP', '58', 'runtime-managed-transfer')] and
            all(r.get('length') == 1 and r.get('grammar') == 'none' for r in rows) and
            not corridor_reason(rows, targets))


def conditional_goto(left, right, targets, regions, key):
    """False skips the entire GOTO; only true executes the keyed transfer."""
    predicate = left['statement']
    if (predicate is None or predicate.kind != 'conditional' or not predicate.false or
            len(right['rows']) != 1 or not left['rows']):
        return None
    test, jump = left['rows'][-1], right['rows'][0]
    fall = test['address'] + 5
    if (test['mnemonic'] != 'IF_SKIP_FALSE' or test.get('grammar') != 'relative8' or
            test.get('length') != 2 or test['bytes'] != '4f05' or test.get('targets') != [fall] or
            explicit_targets(test) != {fall} or predicate.target != f'L_{fall:04X}' or
            jump['mnemonic'] != 'GOTO' or jump.get('grammar') != 'xor_target' or
            jump.get('control') != 'jump' or jump.get('length') != 3 or len(jump['targets']) != 1):
        return None
    dest = jump['targets'][0]
    hi, lo = key.get('high'), key.get('low')
    if (not all(type(k) is int and 0 <= k <= 255 for k in (hi, lo)) or
            not 0 <= dest <= 65535 or jump['bytes'] != bytes((0x48, (dest >> 8) ^ hi, (dest & 255) ^ lo)).hex() or
            explicit_targets(jump) != {dest} or not test.get('region') or
            any(regions.get(a) != test['region'] for a in (fall, dest)) or
            projection_reason(left['rows'], predicate, targets) or corridor_reason([test, jump], targets)):
        return None
    return merge(left, right, replace(predicate, false=False, target=f'L_{dest:04X}'),
                 dict(kind='fold-conditional-goto', falseTarget=fall, trueTarget=dest, jump=jump['address']))


def build_reading(report, result, statements, arguments, targets, tokens):
    groups = result['groups']
    assert len(groups) == len(statements) == len(arguments)
    uses = Counter()
    for args in arguments:
        for expression in args:
            uses.update(references(expression))
    loops = {x['address']: x for x in result['forIndex']['loops']}
    calls = {c['address']: c for c in result.get('functionIndex', {}).get('calls', [])}
    regions = {r['address']: r.get('region') for r in report['instructions']}
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
            if statement.kind == 'statement' and statement.target == 'POKE' and len(output) >= 2:
                folded = fn_value_poke(output[-2], output[-1], entry, calls, uses, targets)
                size = 2
                if folded is None and len(output) >= 3:
                    size = 3
                    folded = nested_fn_poke(output[-3:] + [entry], calls, uses, targets)
                if folded is not None:
                    del output[-size:]
                    entry = folded
            if statement.kind == 'assignment' and output:
                folded = system_assignment(output[-1], entry, uses, targets)
                if folded is not None:
                    output.pop()
                    entry = folded
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
        if complete and output and entry['rows'] and entry['rows'][-1]['mnemonic'] == 'GOTO':
            folded = conditional_goto(output[-1], entry, targets, regions, report.get('branchKey', {}))
            if folded is not None:
                output.pop()
                entry = folded
        if complete and entry['text'] == 'RUN' and output and run_pair(output[-1], entry, targets):
            clear = output.pop()
            entry['indices'] = clear['indices'] + entry['indices']
            entry['rows'] = clear['rows'] + entry['rows']
            entry['actions'].append(dict(kind='fold-bare-run'))
        output.append(entry)
    # Give existing compound statements (notably conditional GOTO) first refusal.
    compact = []
    for entry in simple_functions(output, result, targets, tokens, uses):
        folded = status_comparison(compact[-1], entry, uses, targets, regions) if compact else None
        if folded is not None:
            compact[-1] = folded
        else:
            compact.append(entry)
    projected = []
    for entry in compact:
        statement = entry['statement']
        if statement is not None and statement.kind == 'conditional' and statement.false:
            expression = statement.expressions[0]
            if (expression.kind == 'binary' and expression.token in ('AND', 'OR') and
                    display.boolean_complement(expression) is not None):
                entry['statement'] = replace(statement, boolean_false=True)
                entry['text'] = render_statement(entry['statement'])
                entry['actions'].append(dict(kind='boolean-complement'))
        original = [groups[i] for i in entry['indices']]
        detail_warnings = list(dict.fromkeys(w for g in original for w in g['warnings']))
        warnings = detail_warnings
        if 'definitionRepresentations' in entry:
            from dtl_fn_reading import bookkeeping_warning
            warnings = [w for w in detail_warnings if not bookkeeping_warning(w)]
        if any(a['kind'] in ('fold-fn-value-poke', 'fold-nested-fn-poke') for a in entry['actions']):
            warnings = [w for w in detail_warnings if w not in (
                'Synthetic temporary preserves evaluation site/order.',
                'Synthetic value captured at its original evaluation site, before a later DTL FN call.')]
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
        if warnings is not detail_warnings:
            projected[-1]['detailWarnings'] = detail_warnings
    assert [i for g in projected for i in g['sourceGroups']] == list(range(len(groups)))
    return dict(schema='dtl-idiomatic-reading-v1', scope=SCOPE, groups=projected, refusals=refusals,
                counts=dict(Counter(a['kind'] for g in projected for a in g['actions'])),
                printSeparatorInsertion=False, otherCompilerContractsEnabled=False)
