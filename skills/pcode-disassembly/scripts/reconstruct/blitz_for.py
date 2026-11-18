"""Reading-only fold for one BLITZ/Austro literal, default-step FOR lowering."""
import re


def literal_header(left, right, scalars, targets):
    rows = left['instructions'] + right['instructions']
    if (len(left['instructions']) != 2 or left['kind'] != 'inferred' or right['kind'] != 'inferred' or
            [r['mnemonic'] for r in rows] != ['CONST_SMALL', 'STORE_VAR', 'CONST_SMALL', 'VAR_DESCRIPTOR', 'FOR_SETUP']):
        return None
    start, store, limit, counter, setup = rows
    if (setup.get('control') != 'for_setup' or any(r.get('control') not in (None, 'fallthrough') for r in rows[:-1]) or
            any(a.get('region') != 'main' or a['address'] + a.get('size', 0) != b['address'] for a, b in zip(rows, rows[1:])) or
            setup.get('region') != 'main' or setup.get('size') != 1 or
            not targets.isdisjoint(range(start['address'] + 1, setup['address'] + 1))):
        return None
    slot = store.get('variableIndex')
    if any(type(r.get('value')) is not int for r in (start, limit)):
        return None
    if not isinstance(slot, int) or not 0 <= slot < len(scalars) or slot != counter.get('variableIndex'):
        return None
    record = scalars[slot]
    name = record.get('name', '')
    if (record.get('index') != slot or name != store.get('variable') or name != counter.get('variable') or
            not re.fullmatch('[A-Z][A-Z0-9]?', name) or
            not record.get('bytes', '').startswith(name.encode('ascii').ljust(2, b'\0').hex())):
        return None  # Same ordinary real scalar, not merely matching displayed names.
    return {'text': f"FOR {name} = {start['value']} TO {limit['value']}", 'kind': 'inferred',
            'warnings': ['Adjacent literal counter initialization and default-step FOR setup.'],
            'evidenceAddresses': sorted(set(left['evidenceAddresses']) | set(right['evidenceAddresses'])),
            'instructions': rows}


def fold_literal_headers(groups, scalars, targets):
    out = []
    for group in groups:
        if out and group['instructions'][-1]['mnemonic'] == 'FOR_SETUP':
            header = literal_header(out[-1], group, scalars, targets)
            if header is not None:
                out[-1] = header
                continue
        out.append(group)
    return out
