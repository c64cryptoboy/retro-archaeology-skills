"""Detailed reading of one fresh $2267 console string field, not INPUT syntax."""
from petspeed_listing import RUNTIME


def compact_string_slots(records, initializer):
    """Exact-runtime caller supplies the scalar and initialization sections."""
    # At $2338 an initialization record can overwrite memory.  Admit only the
    # empty list ($64 at offset 2), and complete compact records tagged $FF.
    if len(initializer) < 5 or initializer[2] != 0x64:
        return []
    return [0x2800 + i for i in range(0, min(256, len(records)) - 7, 8)
            if records[i + 6] == 0xff]


def fold_console_fields(groups, report, targets, candidates):
    if report.get('runtimeSha256') != RUNTIME or not report.get('petspeedCompactStringSlots'):
        return groups
    # Do not annotate the first store of a continuing INPUT sequence, even
    # when destination preparation separates the fields in the decoded stream.
    previous = None
    skip_sites = set()
    for row in report['instructions']:
        if row['mnemonic'] == 'INPUT_BEGIN':
            previous = None
        elif row.get('opcode') in (0xd6, 0xd7):
            candidates.discard(previous)
            previous = row['address']
            skip_sites.add(previous)

    out = []
    i = 0
    while i < len(groups):
        if i + 3 < len(groups) and all(len(g['instructions']) == 1 for g in groups[i:i + 3]):
            begin, field, store, after = (g['instructions'][0] for g in groups[i:i + 4])
            pc = field['address']
            if (pc in candidates and pc not in targets and pc + 1 not in targets and
                    [r['mnemonic'] for r in (begin, field, store)] ==
                    ['INPUT_BEGIN', 'INPUT_STRING_EMPTY_SKIP', 'STORE_FAC_VAR'] and
                    [r['address'] for r in (begin, store, after)] == [pc - 1, pc + 1, pc + 2] and
                    all(r['size'] == 1 for r in (begin, field, store)) and
                    all(r.get('region') == begin.get('region') for r in (field, store, after)) and
                    0x60 <= store['opcode'] <= 0x7f and
                    store['operands']['variable'] in report['petspeedCompactStringSlots'] and
                    # $143C can advance up to three bytes before dispatch's +1.
                    # A nearby prior empty skip isn't in the encoded target set.
                    skip_sites.isdisjoint(range(pc - 4, pc - 1))):
                dest = store['operands']['variable']
                out.append({'kind': 'partial', 'text': f'REM on default console: INPUT string field -> V_{dest:04X}',
                            'warnings': [f'At ${pc:04X}, bare RETURN skips ${pc+1:04X} and keeps the current value.  '
                                         f'A parsed field executes ${pc+1:04X}; typed "" stores an empty string.  '
                                         f'Both continue at ${pc+2:04X} on normal completion.'],
                            'instructions': [begin, field, store], 'evidenceAddresses': [pc-1, pc, pc+1]})
                i += 3
                continue
        out.append(groups[i])
        i += 1
    return out
