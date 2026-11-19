"""Read consecutive simple current-channel output items ending in a newline."""

# Each pair evaluates its own operand immediately before emitting it.  In
# particular, a float load and a page-three integer load are not interchangeable.
ITEMS = {
    ('PUSH_INLINE_STRING', 'PRINT_STRING'),
    ('PUSH_STRING_PAGE3', 'PRINT_STRING'),
    ('LOAD_FAC', 'PRINT_FLOAT'),
    ('LOAD_INTEGER_PAGE3', 'PRINT_INTEGER'),
    ('CONST_BYTE_INTEGER', 'PRINT_TAB'),
    ('CONST_BYTE_INTEGER', 'PRINT_SPC'),
}


def falls_into(left, right, targets):
    return (left.get('control') == 'next' and left['address'] + left['size'] == right['address']
            and left.get('region') == right.get('region') and right['address'] not in targets)


def fold_print_lines(groups, targets):
    out = []
    for end in groups:
        newline = end['instructions']
        # PRINT# (including an unknown selected file) is a separate contract.
        if end['text'] != 'PRINT' or len(newline) != 1 or newline[0]['mnemonic'] != 'PRINT_NEWLINE':
            out.append(end)
            continue
        start = len(out)
        following = newline[0]
        while start:
            item = out[start - 1]
            rows = item['instructions']
            if (len(rows) != 2 or tuple(r['mnemonic'] for r in rows) not in ITEMS
                    or not falls_into(rows[1], following, targets) or not falls_into(rows[0], rows[1], targets)
                    or not item['text'].startswith('PRINT ') or not item['text'].endswith(';')
                    or item['kind'] != end['kind'] or item['warnings'] != end['warnings']):
                break
            start -= 1
            following = rows[0]
        if start == len(out):
            out.append(end)
            continue
        items = out[start:]
        # Strip only the lifter's fixed PRINT framing, never parse/requote the
        # literal or move an operand across an output operation.
        text = 'PRINT ' + '; '.join(item['text'][6:-1] for item in items)
        owned = [*items, end]
        out[start:] = [{**end, 'text': text,
                        'instructions': [r for g in owned for r in g['instructions']],
                        'evidenceAddresses': sorted(set().union(*(g['evidenceAddresses'] for g in owned)))}]
    return out
