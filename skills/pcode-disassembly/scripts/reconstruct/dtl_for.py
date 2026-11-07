"""Bounded DTL FOR provenance and zero-only register-carryover contracts.

No loop matching, assignment fusion, general store-state survival or execution
proof. Operates on fresh decoder records; original instruction objects are read
only. The initialized supported RTL and its normal local path are assumed.
"""
from copy import deepcopy
from dtl_branches import explicit_targets

FORMS = {'FOR_REAL': (0x42, 'real'), 'FOR_REAL_STEP': (0x43, 'real'),
         'FOR_INTEGER': (0x44, 'integer'), 'FOR_INTEGER_STEP': (0x45, 'integer')}
STORES = {'STORE_REAL_SCALAR': (0xd0, 'real', 1),
          'STORE_REAL_SCALAR_LONG': (0xd4, 'real', 2),
          'STORE_INTEGER_SCALAR': (0xd1, 'integer', 1),
          'STORE_INTEGER_SCALAR_LONG': (0xd5, 'integer', 2)}
ZERO_SCOPE = ('Limit zero inherited only through the evidenced small-zero/long-real-store/unit-real-FOR '
              'handlers on the completed-initialization normal path; no general typed-store value preservation.')
SCOPE = ('Local initializer provenance only: assignment stays at its original site before limit/step '
         'evaluation and is not repeated. No original-source, reachability, hidden-native-entry, '
         'asynchronous-state or FOR/NEXT pairing proof.')


def site(row):
    return deepcopy({k: row[k] for k in ('address', 'region', 'mnemonic', 'grammar', 'control',
                                       'length', 'bytes', 'operands', 'targets') if k in row})


def typed_shape(row, forms):
    """Require mnemonic, width, control, bytes and decoded offset to agree."""
    form = forms.get(row.get('mnemonic'))
    if form is None:
        return False
    opcode, _kind, *widths = form
    width = widths[0] if widths else 2
    offset = row.get('operands', {}).get('value')
    if type(offset) is not int or not 0 <= offset < 1 << (width * 8):
        return False
    raw = bytes([opcode]) + offset.to_bytes(width, 'big')
    return (row.get('opcode', opcode) == opcode and row.get('length') == len(raw) and
            row.get('bytes', '').lower() == raw.hex() and
            row.get('grammar') == ('var8' if width == 1 else 'var16') and
            row.get('control') == ('loop-runtime' if forms is FORMS else 'fallthrough') and
            not explicit_targets(row))


def scalar_matches(report, row, kind):
    offset = row.get('operands', {}).get('value')
    records = [s for s in report.get('scalars', []) if s.get('offset') == offset]
    return len(records) == 1 and records[0].get('type') == kind


def corridor_reason(rows, targets):
    if not rows or rows[0].get('region') is None:
        return 'Missing same-region local corridor.'
    if any(a['address'] + a.get('length', 0) != b['address'] or
           a.get('region') != b.get('region') for a, b in zip(rows, rows[1:])):
        return 'Noncontiguous or cross-region initializer corridor.'
    start, end = rows[0]['address'], rows[-1]['address'] + rows[-1].get('length', 0)
    if any(start < address < end for address in targets):
        return 'Alternate entry into initializer/limit/FOR corridor.'
    return None


def zero_candidates(report, targets):
    """Static triple gate; singleton producer state must additionally pass live lifting."""
    found = {}
    rows = report['instructions']
    for i, loop in enumerate(rows):
        if i < 2 or loop.get('mnemonic') != 'FOR_REAL' or not typed_shape(loop, FORMS):
            continue
        literal, store = rows[i-2:i]
        if (store.get('mnemonic') != 'STORE_REAL_SCALAR_LONG' or not typed_shape(store, STORES) or
                store['operands']['value'] != loop['operands']['value'] or
                not scalar_matches(report, loop, 'real')):
            continue
        if (literal.get('mnemonic') != 'INTEGER_SMALL' or literal.get('bytes', '').lower() != '80' or
                literal.get('length') != 1 or literal.get('grammar') != 'none' or
                literal.get('control') != 'fallthrough' or literal.get('opcode', 0x80) != 0x80 or
                type(literal.get('operands', {}).get('constant')) is not int or
                literal['operands']['constant'] != 0 or explicit_targets(literal) or
                corridor_reason([literal, store, loop], targets)):
            continue
        found[loop['address']] = {'producerAddress': literal['address'], 'storeAddress': store['address'],
                                 'forAddress': loop['address'], 'offset': loop['operands']['value'],
                                 'sites': [site(r) for r in (literal, store, loop)]}
    return found


def annotate_initializers(report, groups, targets, recoveries):
    """Add warnings/index only, never edit assignment or limit text or owned rows."""
    entries = []
    for i, group in enumerate(groups):
        rows = group['instructions']
        if not rows or rows[-1]['mnemonic'] not in FORMS:
            continue
        loop = rows[-1]
        previous = groups[i-1] if i else None
        prior = previous['instructions'] if previous else []
        store = prior[-1] if prior else None
        reasons = []
        kind = FORMS[loop['mnemonic']][1]
        if not typed_shape(loop, FORMS) or not scalar_matches(report, loop, kind):
            reasons.append('FOR encoding or unique typed scalar identity is not established.')
        if (not store or not typed_shape(store, STORES) or STORES[store['mnemonic']][1] != kind or
                store['operands']['value'] != loop['operands'].get('value')):
            reasons.append('Immediately preceding emitted group is not a compatible same-offset scalar assignment.')
        if previous and (previous['kind'] != 'inferred' or '<?>' in previous['text'] or
                         any('unknown' in w for w in previous['warnings'])):
            reasons.append('Preceding assignment value is incomplete.')
        corridor = prior + rows
        reason = corridor_reason(corridor, targets)
        if reason:
            reasons.append(reason)
        if any(r.get('control') != 'fallthrough' or r.get('grammar') == 'basic_island' or
               r['mnemonic'] == 'SYS' or r.get('operands', {}).get('operation') == 'USR'
               for r in corridor[:-1]):
            reasons.append('Unsupported control or opaque operation in initializer corridor.')
        entry = {'address': loop['address'], 'offset': loop['operands'].get('value'),
                 'type': kind, 'forSite': site(loop), 'status': 'associated' if not reasons else 'unassociated',
                 'reasons': reasons, 'initializer': None, 'limitRecovery': deepcopy(recoveries.get(loop['address']))}
        if not reasons:
            entry['initializer'] = {'groupAddress': prior[0]['address'], 'storeAddress': store['address'],
                                    'sites': [site(r) for r in prior]}
            group['warnings'].append(f'Initializer provenance: assignment at L_{prior[0]["address"]:04X} '
                                     f'(store L_{store["address"]:04X}); not repeated or moved past limit/step evaluation.')
        entries.append(entry)
    return {'schema': 'dtl-for-provenance-v1', 'scope': SCOPE, 'zeroLimitScope': ZERO_SCOPE,
            'nextPairingProved': False, 'runtimeReachabilityProved': False, 'loops': entries}


def render_for(index):
    if not index['loops']:
        return []
    lines = ['\n; DTL FOR INITIALIZER PROVENANCE', '; ' + index['scope'], '; ' + index['zeroLimitScope']]
    for entry in index['loops']:
        text = f'; L_{entry["address"]:04X} [{entry["status"]}] {entry["type"]} offset {entry["offset"]}'
        if entry['initializer']:
            init = entry['initializer']
            text += f'; assignment L_{init["groupAddress"]:04X}, store L_{init["storeAddress"]:04X}'
        if entry['limitRecovery']:
            text += '; inherited limit 0 (normal initialized path only)'
        lines.append(text)
        lines.extend(';   ' + reason for reason in entry['reasons'])
    return lines
