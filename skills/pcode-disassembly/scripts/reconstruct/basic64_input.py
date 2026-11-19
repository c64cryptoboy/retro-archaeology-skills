"""Separate prompt-bounded INPUT lists from individual DATA fields."""

# Field result, matching store, unsigned destination address base, and display type.
STRING_PAIR = ('READ_STRING_FIELD', 'STORE_STRING_REFERENCE_PAGE3')
SCALARS = {
    ('READ_FLOAT_FIELD', 'STORE_FAC'): (0, 'floating-point'),
    ('READ_INTEGER_FIELD', 'STORE_INTEGER_PAGE3'): (0x300, 'signed integer'),
    STRING_PAIR: (0x300, 'string descriptor'),
}


def follows(a, b):
    return a['address'] + a['size'] == b['address'] and a.get('region') == b.get('region')


def fold_data_fields(groups, targets, layout):
    """A DATA selector persists along an uninterrupted run of scalar field/stores."""
    out = []
    selector = previous = None
    i = 0
    while i < len(groups):
        group = groups[i]
        rows = group['instructions']
        field = rows[0]
        if len(rows) == 1 and field['mnemonic'] == 'SELECT_DATA_INPUT' and field.get('control') == 'next':
            selector = previous = field  # Entry here still executes the selector.
            numeric_slots = {}  # Byte -> start, only for the uninterrupted numeric prefix.
        elif previous is not None:
            stores = groups[i + 1]['instructions'] if i + 1 < len(groups) else []
            store = stores[0] if stores else None
            if (len(rows) == len(stores) == 1 and group['kind'] == groups[i + 1]['kind'] == 'inferred'
                    and follows(previous, field) and follows(field, store)
                    and all(r.get('control') == 'next' and r['address'] not in targets for r in (field, store))
                    and (field['mnemonic'], store['mnemonic']) in SCALARS):
                value = store['operands']['value']
                pair = field['mnemonic'], store['mnemonic']
                addr = SCALARS[pair][0] + value
                warning = None
                if pair == STRING_PAIR:
                    warning = 'One DATA string field and its descriptor store; original READ grouping is not known.'
                    numeric_slots = None  # Do not extend numeric proof through indirect string-heap bookkeeping.
                elif pair[1] == 'STORE_FAC' and not (
                        layout and layout['loadedEnd'] <= layout['stringTop'] <= addr
                        and addr + 5 <= min(layout['memoryTop'], 0xA000)):
                    previous = None  # Absolute write might alias the input mode, cursor, or loaded code.
                elif numeric_slots is not None:
                    word = pair[1] == 'STORE_INTEGER_PAGE3'
                    span = range(addr, addr + (2 if word else 5))
                    if ((word and not (0x033C <= addr and span.stop <= 0x03FC)) or
                            any(numeric_slots.get(b, addr) != addr for b in span)):
                        numeric_slots = None  # Vector, spill, or partially aliased scalar name.
                    else:
                        numeric_slots.update(dict.fromkeys(span, addr))
                        action = ('convert FAC to a VM signed word, then store low and high bytes' if word else
                                  'pack FAC into the five-byte destination')
                        warning = ('On successful DATA field parsing, ' + action +
                                   '.  One transfer, not evidence of original READ syntax or grouping.')
                if previous is not None:
                    if warning is None:
                        out.extend(groups[i:i + 2])
                    else:
                        out.append({'kind': 'inferred', 'text': f'READ V_{addr:04X}',
                                    'instructions': [field, store],
                                    'evidenceAddresses': [selector['address'], field['address'], store['address']],
                                    'warnings': [warning]})
                    previous = store
                    i += 2
                    continue
            previous = None  # Including prompts, file selection, joins, calls, and opaque effects.
        out.append(group)
        i += 1
    return out


# Earlier fragment callers used the original name of this pass.
fold_data_string_fields = fold_data_fields


def scalar_input(groups, index, targets):
    prompt_group = groups[index]
    prompt = prompt_group['instructions'][0]
    if len(prompt_group['instructions']) != 1 or prompt.get('control') != 'conditional-input':
        return None
    payload = bytes.fromhex(prompt['operands']['payloadHex'])
    # BASIC INPUT takes a quoted prompt, not a CHR$ expression.  Withhold
    # characters that don't have a plain shared PETSCII/ASCII spelling.
    if any(b < 32 or b > 90 or b == 34 for b in payload):
        return None
    prefix = '"' + payload.decode('ascii') + '";' if payload else ''
    skip = prompt['operands']['target']
    previous = prompt
    destinations = []
    i = index + 1
    while i + 2 < len(groups):
        field_group, store_group, successor = groups[i:i + 3]
        if (len(field_group['instructions']) != 1 or len(store_group['instructions']) != 1 or
                store_group['kind'] != 'inferred'):
            return None
        field, store, after = (g['instructions'][0] for g in (field_group, store_group, successor))
        pair = (field['mnemonic'], store['mnemonic'])
        if (pair not in SCALARS or field.get('control') != 'next' or store.get('control') != 'next' or
                not follows(previous, field) or not follows(field, store) or not follows(store, after) or
                field['address'] in targets or store['address'] in targets or after['address'] > skip):
            return None
        # Only repeated string-descriptor fields have a multi-field contract here.
        if pair != STRING_PAIR and (destinations or after['address'] != skip):
            return None
        base, field_type = SCALARS[pair]
        destinations.append(f"V_{base + store['operands']['value']:04X}")
        i += 2
        if after['address'] == skip:
            owned = groups[index:i]
            warning = (f'Runtime {field_type} field; empty input skips the store.' if len(destinations) == 1 else
                       'String fields are read and stored as descriptors in order; an initially empty line skips all stores.  No logical file selected by this INPUT.')
            return {'kind': 'inferred', 'text': 'INPUT ' + prefix + ', '.join(destinations),
                    'instructions': [g['instructions'][0] for g in owned], 'warnings': [warning],
                    'evidenceAddresses': sorted(set().union(*(g['evidenceAddresses'] for g in owned)))}
        previous = store
    return None


def indexed_input(groups, index, targets, layout):
    """Empty prompt enclosing two separately indexed, rank-one field stores."""
    if not layout or index + 5 >= len(groups):
        return None
    owned = groups[index:index + 5]
    if [len(g['instructions']) for g in owned] != [1, 3, 1, 3, 1]:
        return None
    rows = [r for g in owned for r in g['instructions']]
    prompt = rows[0]
    after = groups[index + 5]['instructions'][0]
    if (prompt.get('control') != 'conditional-input' or prompt['operands']['payloadHex'] != '' or
            prompt['operands']['target'] != after['address'] or
            any(not follows(a, b) for a, b in zip(rows, rows[1:] + [after])) or
            any(r['address'] in targets or r.get('control') != 'next' for r in rows[1:])):
        return None
    lo, hi = layout['stringTop'], layout['memoryTop']
    if layout['loadedEnd'] > lo:
        return None
    destinations, arrays, indices = [], [], []
    for start, field, store, stride, suffix in (
            (1, 'READ_INTEGER_FIELD', 'STORE_INTEGER_ARRAY', 2, '%'),
            (5, 'READ_STRING_FIELD', 'STORE_STRING_ARRAY_REFERENCE', 3, '$')):
        load, push, read, write = rows[start:start + 4]
        if [r['mnemonic'] for r in (push, read, write)] != ['PUSH_INTEGER', field, store]:
            return None
        d = write['operands']
        if (len(d.get('extentsReversed', [])) != 1 or d.get('elementSize') != stride or
                d['value'] + 4 > 255):  # Descriptor bytes reached with an 8-bit Y.
            return None
        base = d['arrayBase']
        end = base + stride * d['extentsReversed'][0]
        if not lo <= base < end <= hi:
            return None
        arrays.append((base, end))
        addr = load['operands'].get('value')
        if load['mnemonic'] == 'LOAD_FLOAT_AS_INTEGER':
            if not lo <= addr < addr + 5 <= min(hi, 0xA000):
                return None
            indices.append((addr, addr + 5))
        elif load['mnemonic'] == 'LOAD_INTEGER_PAGE3':
            addr += 0x300
            indices.append((addr, addr + 2))
        else:
            return None
        destinations.append(f'AR_{base:04X}{suffix}(V_{addr:04X})')
    # Generated symbols must not hide overlapping arrays or a subscript slot
    # inside either array.  Identical index loads remain two separate samples.
    spans = arrays + sorted(set(indices))
    if any(a < d and c < b for i, (a, b) in enumerate(spans) for c, d in spans[i + 1:]):
        return None
    warnings = ['An empty prompt response jumps past both fields.  A bad numeric delimiter can re-enter the prompt; no stack rollback is implied.',
                'For each field, sample and save its subscript before reading.  Convert the numeric field to a VM integer, then bounds-check and store before sampling the string subscript.  After reading the string, check its saved index and install its descriptor.']
    if any(r['mnemonic'] == 'LOAD_FLOAT_AS_INTEGER' for r in rows):
        warnings.append('Each floating subscript undergoes VM float-to-integer conversion at its own load, not BASIC INT().')
    return {'kind': 'inferred', 'text': 'INPUT ' + ', '.join(destinations), 'instructions': rows,
            'evidenceAddresses': [r['address'] for r in rows], 'warnings': warnings}


def fold_inputs(groups, targets, layout):
    out = []
    i = 0
    while i < len(groups):
        group = groups[i]
        if group['instructions'][0]['mnemonic'] == 'INPUT_PROMPT':
            indexed = indexed_input(groups, i, targets, layout)
            if indexed is not None:
                out.append(indexed)
                i += 5  # Prompt and two (index/push/field, store) group pairs.
                continue
            folded = scalar_input(groups, i, targets)
            if folded is not None:
                out.append(folded)
                i += len(folded['instructions'])  # Each consumed group owns exactly one row.
                continue
        out.append(group)
        i += 1
    return out
