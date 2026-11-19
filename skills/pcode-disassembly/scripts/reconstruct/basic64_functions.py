"""Read a BASIC-64 descriptor declaration and its deferred numeric leaf together."""
from collections import Counter


ARG = {'LOAD_ARG', 'CONST_BYTE_FLOAT_ARG', 'CONST_SIGNED_WORD_FLOAT_ARG', 'CONST_FLOAT_ARG'}
FAC = {'LOAD_FAC', 'CONST_BYTE_FAC', 'CONST_SIGNED_WORD_FAC', 'CONST_FLOAT_FAC'}
BINARY = {'FLOAT_ADD', 'FLOAT_SUBTRACT', 'FLOAT_MULTIPLY'}


def formal_body(rows, formal):
    """One reload of the packed formal, or one ARG op FAC using that formal."""
    names = [r['mnemonic'] for r in rows]
    if names != ['LOAD_FAC'] and not (
            len(names) == 3 and names[-1] in BINARY and
            ((names[0] in ARG and names[1] in FAC) or (names[0] in FAC and names[1] in ARG))):
        return False
    loads = [r for r in rows if r['mnemonic'] in ('LOAD_ARG', 'LOAD_FAC')]
    return bool(loads) and all(r['operands']['value'] == formal for r in loads)


def scalar_ram(layout, address, size):
    return (layout and layout['loadedEnd'] <= layout['stringTop'] <= address and
            address + size <= min(layout['memoryTop'], 0xA000))


def fold_call_assignments(groups, targets, layout):
    """Fold an effectful indirect call into its only, immediate result store."""
    out = []
    for group in groups:
        rows = group['instructions']
        if (out and len(rows) == 1 and rows[0]['mnemonic'] == 'STORE_FAC' and
                len(out[-1]['instructions']) == 2):
            previous = out[-1]; arg, call = previous['instructions']; store = rows[0]
            if (arg['mnemonic'] in FAC and call['mnemonic'] == 'CALL_FUNCTION' and
                    arg.get('control') == store.get('control') == 'next' and call.get('control') == 'descriptor-call' and
                    arg.get('region') == call.get('region') == store.get('region') and
                    arg['address'] + arg['size'] == call['address'] and call['address'] + call['size'] == store['address'] and
                    not targets.intersection((call['address'], store['address'])) and
                    previous['kind'] == group['kind'] == 'inferred'):
                desc = call['operands']['value']; dest = store['operands']['value']; tmp = f'T_{call["address"]:04X}'
                target = f'V_{dest:04X}'; prefix = tmp + ' = '
                if (scalar_ram(layout, desc, 7) and scalar_ram(layout, dest, 5) and
                        (arg['mnemonic'] != 'LOAD_FAC' or scalar_ram(layout, arg['operands']['value'], 5)) and
                        (dest + 5 <= desc or desc + 7 <= dest) and
                        previous['text'].startswith(prefix + f'FN F_{desc}(') and group['text'] == target + ' = ' + tmp):
                    out[-1] = {'text': target + ' = ' + previous['text'][len(prefix):], 'kind': 'inferred',
                               'instructions': [arg, call, store],
                               'evidenceAddresses': sorted(set(previous['evidenceAddresses']) | set(group['evidenceAddresses'])),
                               'warnings': ['The descriptor selects the body at runtime.  Only on normal return does the following store pack FAC into the destination.']}
                    continue
        out.append(group)
    return out


def annotate_leaf_definitions(groups, layout):
    """Keep the body entry addressable; reuse its independently lifted expression."""
    if not layout:
        return
    headers = [i for i, g in enumerate(groups) if len(g['instructions']) == 1 and
               g['instructions'][0]['mnemonic'] == 'DEFINE_FUNCTION' and i + 2 < len(groups)]
    if not headers:
        return
    incoming = Counter()
    descriptor_bytes = Counter()
    for g in groups:
        for row in g['instructions']:
            v = row.get('operands', {})
            incoming.update(v.get('targets', ()))
            if 'target' in v:
                incoming[v['target']] += 1
            if row['mnemonic'] == 'DEFINE_FUNCTION':
                descriptor_bytes.update(range(v['descriptor'], v['descriptor'] + 7))
    for i in headers:
        declaration, body, after = groups[i:i + 3]
        h = declaration['instructions'][0]
        rows = body['instructions']; successor = after['instructions'][0]
        v = h['operands']; desc = v['descriptor']; formal = desc + 2
        if not (scalar_ram(layout, desc, 7) and
                all(descriptor_bytes[b] == 1 for b in range(desc, desc + 7))):
            continue
        if (h.get('control') != 'definition' or v['body'] != rows[0]['address'] or
                v['skip'] != successor['address'] or incoming[v['body']] != 1 or
                any(incoming[r['address']] for r in rows[1:]) or
                any(a['address'] + a['size'] != b['address'] or a.get('region') != b.get('region')
                    for a, b in zip([h] + rows, rows + [successor]))):
            continue
        if (rows[-1]['mnemonic'] != 'RETURN_FUNCTION' or rows[-1].get('control') != 'runtime-return' or
                not all(r.get('control') == 'next' for r in rows[:-1]) or not formal_body(rows[:-1], formal)):
            continue
        prefix = 'REM FN RESULT '
        if body['warnings'] or not body['text'].startswith(prefix) or '<?>' in body['text']:
            continue
        expr = body['text'][len(prefix):]
        name = f'FN F_{desc}'  # Match existing descriptor-indirect call notation.
        evidence = sorted(set(declaration['evidenceAddresses']) | set(body['evidenceAddresses']))
        declaration.update(text=f'DEF {name}(V_{formal:04X}) = {expr}', kind='inferred', evidenceAddresses=evidence,
                           warnings=[f'Declaration installs body L_{v["body"]:04X} and skips to L_{v["skip"]:04X}.  '
                                     'The expression is evaluated on a call, not here.  Names are synthetic; active call binding is not proved.'])
        body.update(text=f'RETURN {name} = {expr}', kind='structural', evidenceAddresses=evidence,
                    warnings=[f'A call packs its FAC argument at V_{formal:04X}.  Normal return restores the VM cursor, '
                              'not the previous argument bytes.  VM floating-point and error behavior still apply.'])
