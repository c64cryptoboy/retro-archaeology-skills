"""DTL function-expression projection, not callee-body inlining or execution.

Infer from p-code first. Embedded text can only corroborate an already complete
reading. All original groups/bytes and both definition representations survive.
"""
import expression_display as display
from dtl_for import corridor_reason
from reading_projection import references, statement_events, substitute_statement


def compact_spelling(text):
    """Exact lexical comparison apart from ASCII spaces outside string literals."""
    quoted = False
    output = []
    for char in text:
        if char == '"':
            quoted = not quoted
        if char != ' ' or quoted:
            output.append(char)
    return None if quoted else ''.join(output)


def bookkeeping_warning(warning):
    return (warning == 'Synthetic temporary preserves evaluation site/order.' or
            warning == 'Synthetic value captured at its original evaluation site, before a later DTL FN call.' or
            warning == 'Inline body is skipped when this definition executes; normal-return structure, not a purity claim.' or
            warning.startswith('Result of body at L_') and warning.endswith('; saved formal is restored on normal return.') or
            warning.startswith('Descriptor-indirect function; static definition candidates: ') and
            warning.endswith('; runtime binding and purity unproved.'))


def body_events(rows, calls, event_reader):
    """Keep FN_CALL as an effectful event; never assume the callee pure."""
    events = []
    for row in rows:
        if row['mnemonic'] == 'FN_CALL':
            call = calls.get(row['address'])
            offset = row.get('operands', {}).get('value')
            if (not call or not call.get('name') or type(offset) is not int or not 0 <= offset <= 65535 or
                    call['descriptorValueOffset'] != offset or
                    row.get('operands', {}).get('name') != call['name'] or
                    row.get('bytes', '').lower() != (b'\xb4' + offset.to_bytes(2, 'big')).hex() or
                    row.get('length') != 3 or row.get('grammar') != 'var16' or
                    row.get('control') != 'descriptor-indirect-call' or row.get('targets')):
                return None
            events.append(row['address'])
        else:
            if row.get('control') != 'fallthrough':
                return None
            part = event_reader([row])
            if part is None:
                return None
            events.extend(part)
    return events


def nodes(expression):
    yield expression
    for child in expression.children:
        yield from nodes(child)


def fold_body(header, body, definition, calls, targets, uses, event_reader):
    h = header['rows'][0]
    raw = bytes.fromhex(h['bytes'])
    if not (len(header['rows']) == len(header['indices']) == 1 and not header['actions'] and
            h['mnemonic'] == 'DEF_FN' and h.get('grammar') == 'fn_definition' and
            h.get('control') == 'definition' and h.get('length') == len(raw) == 8 and raw[0] == 0x53 and
            int.from_bytes(raw[1:3], 'big') == definition['descriptorOffset'] and
            int.from_bytes(raw[5:7], 'big') == definition['parameterOffset'] and
            h['address'] + raw[7] == definition['continuation'] and
            h['address'] + 8 == definition['bodyEntry'] and
            h.get('targets') == [definition['bodyEntry'], definition['continuation']] and body):
        return None
    rows = [r for entry in body for r in entry['rows']]
    result = body[-1]['statement']
    if not (rows and result is not None and result.kind == 'fn-return' and
            result.target == definition['name'] and len(result.expressions) == 1 and
            rows[0]['address'] == definition['bodyEntry'] and rows[-1]['address'] == definition['returnAddress'] and
            rows[-1]['mnemonic'] == 'FN_RETURN' and rows[-1].get('control') == 'function-return' and
            rows[-1].get('length') == 1 and rows[-1]['bytes'] == '55' and
            rows[-1]['address'] + 1 == definition['continuation'] and
            h.get('region') == rows[0].get('region') and not corridor_reason(rows, targets) and
            not any(r.get('targets') for r in rows)):
        return None
    actions = [a for entry in body for a in entry['actions']]
    if any(a['kind'] != 'inline-temporary' for a in actions):
        return None
    substituted = set()
    for entry in reversed(body[:-1]):
        producer = entry['statement']
        if (producer is None or producer.kind != 'temporary' or len(producer.expressions) != 1 or
                producer.target in substituted or uses[producer.target] != 1 or
                references(result.expressions[0])[producer.target] != 1):
            return None
        result = substitute_statement(result, producer.target, producer.expressions[0])
        substituted.add(producer.target)
        actions.append(dict(kind='inline-function-temporary', name=producer.target))
    if references(result.expressions[0]):
        return None
    order = body_events(rows[:-1], calls, event_reader)
    if order is None:
        return None
    order = order + [rows[-1]['address']]
    if statement_events(result) != order or len(order) != len(set(order)):
        return None
    # Expression call identities must agree with the independently indexed names.
    for node in nodes(result.expressions[0]):
        if node.origin in calls and (node.kind != 'call' or node.token != calls[node.origin]['name'] or
                                     len(node.children) != 1):
            return None
    actions.append(dict(kind='single-expression-function', header=h['address'],
                        bodyEntry=definition['bodyEntry'], returnAddress=definition['returnAddress']))
    return dict(indices=header['indices'] + [i for entry in body for i in entry['indices']],
                rows=header['rows'] + rows, statement=None, arguments=(), actions=actions,
                text='DEF ' + definition['name'] + '(' + definition['parameterName'] + ') = ' +
                     display.render(result.expressions[0]), kind='inferred',
                deferredEvaluationOrder=order, definitionEvaluationOrder=[h['address']],
                definitionRepresentations=[dict(kind='inferred', address=h['address'])])


def matching_embedded(entry, combined, definition, result, tokens):
    """Corroboration only: cannot repair an incomplete inferred body."""
    if len(entry['indices']) != 1 or len(entry['rows']) != 1:
        return False
    group = result['groups'][entry['indices'][0]]
    row = entry['rows'][0]
    raw = bytes.fromhex(row['bytes'])
    if not (group['kind'] == 'embedded' and row['address'] == definition['continuation'] and
            row.get('region') == definition['region'] and row.get('grammar') == 'basic_island' and
            row.get('control') == 'interpreter-fallthrough' and raw[:1] == b'\0' and
            len(raw) == row.get('length') and not row.get('targets')):
        return False
    # The definition's own skip is expected; a separately entered island stays separate.
    for source in result['groups']:
        for r in source['instructions']:
            if row['address'] in r.get('targets', []) and r['address'] != definition['header']:
                return False
    # Require actual tokenized DEF/FN, not lookalike ASCII keyword bytes.
    prefix = raw[1:].lstrip(b' ')
    if prefix[:1] != b'\x96' or prefix[1:].lstrip(b' ')[:1] != b'\xa5':
        return False
    from formats import module
    text = module('dtl').basic_text(raw[1:], tokens)
    spelling = compact_spelling(text)
    return (text == group['text'] == row.get('operands', {}).get('text') and spelling is not None and
            spelling == compact_spelling(combined['text']))


def fold_functions(output, result, targets, tokens, uses, event_reader):
    definitions = {d['header']: d for d in result.get('functionIndex', {}).get('definitions', [])
                   if d['status'] == 'block'}
    calls = {c['address']: c for c in result.get('functionIndex', {}).get('calls', [])}
    projected = []
    i = 0
    while i < len(output):
        header = output[i]
        definition = definitions.get(header['rows'][0]['address']) if header['rows'] else None
        combined = None
        j = i + 1
        if definition:
            while j < len(output) and output[j]['rows'][0]['address'] < definition['continuation']:
                j += 1
            combined = fold_body(header, output[i+1:j], definition, calls, targets, uses, event_reader)
        if combined is None:
            projected.append(header)
            i += 1
            continue
        if j < len(output) and matching_embedded(output[j], combined, definition, result, tokens):
            embedded = output[j]
            address = embedded['rows'][0]['address']
            combined['indices'] += embedded['indices']
            combined['rows'] += embedded['rows']
            combined['actions'].append(dict(kind='coalesce-embedded-function', address=address,
                                             match='exact-decoded-spelling-except-unquoted-spaces'))
            combined['definitionEvaluationOrder'].append(address)
            combined['definitionRepresentations'].append(dict(kind='embedded', address=address))
            j += 1
        projected.append(combined)
        i = j
    return projected
