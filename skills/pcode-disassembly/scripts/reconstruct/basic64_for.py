"""Reading-only reconstruction of adjacent BASIC-64 literal FOR headers."""

FAC_LITERALS = {'CONST_BYTE_FAC', 'CONST_SIGNED_WORD_FAC'}


def literal(row):
    operands = row['operands']
    return operands['signedValue' if row['mnemonic'] == 'CONST_SIGNED_WORD_FAC' else 'value']


def literal_header(left, right, targets):
    init, header = left['instructions'], right['instructions']
    if len(init) != 2 or left['kind'] != 'inferred' or right['kind'] != 'inferred':
        return None
    start, store = init
    limit, setup = header[0], header[-1]
    names = [r['mnemonic'] for r in header]
    step = ''
    if setup['mnemonic'] == 'FOR_INTEGER_UNIT_STEP':
        # $A7 has a page-three byte offset, whereas $75 has an absolute pointer.
        if (start['mnemonic'] != 'CONST_BYTE_INTEGER' or store['mnemonic'] != 'STORE_INTEGER_PAGE3' or
                names != ['CONST_BYTE_INTEGER', 'FOR_INTEGER_UNIT_STEP']):
            return None
        counter = 0x300 + store['operands']['value']
    else:
        if start['mnemonic'] not in FAC_LITERALS or store['mnemonic'] != 'STORE_FAC' or limit['mnemonic'] not in FAC_LITERALS:
            return None
        # $74/$76 take a packed limit from the alternate stack.  Only the
        # admitted integer literals survive that round/pack exactly.  $76
        # additionally takes the explicit step from FAC, *not* the stack.
        if setup['mnemonic'] == 'FOR_FLOAT_EXPLICIT_STEP':
            if len(names) != 4 or names[1] != 'PUSH_FAC' or names[2] not in FAC_LITERALS:
                return None
            step = f' STEP {literal(header[2])}'
        elif names[1:] != ['PUSH_FAC', 'FOR_FLOAT_UNIT_STEP']:
            return None
        counter = store['operands']['value']
    rows = init + header
    if (counter != setup['operands']['value'] or setup.get('control') != 'loop-setup' or
            any(a.get('control') != 'next' or a['address'] + a['size'] != b['address'] or
                a.get('region') != b.get('region') for a, b in zip(rows, rows[1:])) or
            any(r['address'] in targets for r in rows[1:])):
        return None
    return {'text': f'FOR V_{counter:04X} = {literal(start)} TO {literal(limit)}{step}', 'kind': 'inferred',
            'warnings': [], 'instructions': rows,
            'evidenceAddresses': sorted(set(left['evidenceAddresses']) | set(right['evidenceAddresses']))}


def fold_literal_headers(groups, targets):
    out = []
    for group in groups:
        if out and group['instructions'][-1]['mnemonic'] in ('FOR_INTEGER_UNIT_STEP', 'FOR_FLOAT_UNIT_STEP', 'FOR_FLOAT_EXPLICIT_STEP'):
            folded = literal_header(out[-1], group, targets)
            if folded is not None:
                out[-1] = folded
                continue
        out.append(group)
    return out
