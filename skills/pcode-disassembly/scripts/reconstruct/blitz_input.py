"""Recognize a straight-line selected-file INPUT list from BLITZ/Austro rows."""
import re


NAME = re.compile(r'[A-Z][A-Z0-9]?[%$]?')


def unique_input_dims(rows):
    """Keep descriptor declarations, not a guess from a nearby scalar slot."""
    dims = {}
    for row in rows:
        if row['mnemonic'] == 'DIM_INTERNAL':
            key = row['descriptorOffset']
            dims[key] = None if key in dims else row
    return dims


def scalar_name(row, scalars):
    slot = row['variableIndex']
    if 0 <= slot < min(32, len(scalars)):
        record = scalars[slot]
        name = record['name']
        if (0x41 <= (bytes.fromhex(record['bytes'])[0] & 0x7f) <= 0x5a and
                NAME.fullmatch(name) and row.get('variable') == name):
            return name
    return None


def selected_file(selector, rows, field_count, scalars, dims, targets):
    """Return a positive literal channel only for the complete observed list."""
    if ([r['mnemonic'] for r in selector] != ['CONST_SMALL', 'SELECT_INPUT_CHANNEL'] or
            field_count < 2):
        return None
    channel = selector[0]['value']
    if not 1 <= channel <= 15:  # Zero also controls a keyboard path in the handler.
        return None
    sequence = selector + rows
    if (any(r.get('region') != 'main' for r in sequence) or
            any(a['address'] + a['size'] != b['address'] or b['address'] in targets
                for a, b in zip(sequence, sequence[1:]))):
        return None

    pos = 0
    for i in range(field_count):
        if pos + 2 > len(rows):
            return None
        operand, following = rows[pos:pos + 2]
        kind = operand['mnemonic']
        name = scalar_name(operand, scalars) if kind in ('LOAD_VAR', 'VAR_DESCRIPTOR') else None
        if following['mnemonic'] == 'LOAD_ARRAY':
            # The operand is a fresh numeric index, not the file number, DIM
            # bound, descriptor offset, or the preceding field's subscript.
            if kind != 'CONST_SMALL' and not (kind == 'LOAD_VAR' and name and not name.endswith('$')):
                return None
            dim = dims.get(following['descriptorOffset'])
            if (not dim or dim['address'] >= following['address'] or dim['dimensions'] != 1 or
                    dim['flags'] != 0 or not NAME.fullmatch(dim['variable']) or
                    not 0x41 <= (bytes.fromhex(dim['bytes'])[2] & 0x7f) <= 0x5a):
                return None
            pos += 1
        elif not name or (kind == 'LOAD_VAR') != name.endswith('$'):
            return None
        pos += 1
        expected = 'INPUT_FIRST' if i == 0 else 'INPUT_FINAL' if i + 1 == field_count else 'INPUT_NEXT'
        if pos == len(rows) or rows[pos]['mnemonic'] != expected:
            return None
        pos += 1
    return channel if pos == len(rows) else None
