"""DTL-only static descriptor associations and conservative inline-body shapes.

Input is a fresh decoder report, never source/maps. DEF_FN writes four bytes at
VARTAB + descriptorOffset + 3; FN_CALL reads that value offset directly. This
index does not prove that a definition executes, remains installed, or is pure.
"""
from collections import defaultdict
import re


SCOPE = ('Static associations from decoded DTL descriptor offsets, not runtime call targets. '
         'Definition execution/order, redefinition, embedded BASIC/native mutation, '
         'reachability and purity are not proved; body blocks describe normal-return structure only.')


def analyze_functions(report):
    rows = report['instructions']
    at = {r['address']: r for r in rows}
    scalars = defaultdict(list)
    incoming = defaultdict(list)
    for s in report.get('scalars', []):
        scalars[s['offset']].append(s)
    for r in rows:
        for target in r.get('targets', []):
            incoming[target].append(r['address'])

    def scalar_name(offset, kind):
        matches = scalars.get(offset, [])
        if len(matches) != 1 or matches[0].get('type') != kind:
            return None
        name = matches[0].get('name', '')
        pattern = r'FN [A-Z][A-Z0-9]?' if kind == 'function' else r'[A-Z][A-Z0-9]?'
        return name if re.fullmatch(pattern, name) else None

    definitions = []
    for r in rows:
        if r['mnemonic'] != 'DEF_FN':
            continue
        v = r.get('operands', {})
        header = r['address']
        encoded = v.get('descriptorOffset')
        offset = encoded + 3 if isinstance(encoded, int) else None
        parameter = v.get('parameterOffset')
        entry = v.get('bodyEntry')
        skip = v.get('skipBytes')
        end = header + skip if isinstance(skip, int) else None
        name = scalar_name(offset, 'function')
        formal = scalar_name(parameter, 'real')
        reasons = []
        if name is None:
            reasons.append('Function scalar/name is missing, ambiguous or not function-typed.')
        if formal is None:
            reasons.append('Formal scalar/name is missing, ambiguous or not real-typed.')
        if (r.get('length') != 8 or entry != header + 8 or
                not isinstance(skip, int) or not 8 < skip <= 255 or
                r.get('targets') != [entry, end] or r.get('control') != 'definition'):
            reasons.append('Header/body/skip contract is inconsistent.')
        body = ([b for b in rows if entry <= b['address'] < end]
                if isinstance(entry, int) and isinstance(end, int) and entry < end else [])
        region = r.get('region')
        if region is None or end not in at or at[end].get('region') != region:
            reasons.append('Continuation is not an instruction in the definition region.')
        cursor = entry
        for b in body:
            if b['address'] != cursor or b.get('length', 0) <= 0:
                reasons.append('Body instruction coverage is not contiguous.')
                break
            cursor += b['length']
        if not body or cursor != end:
            reasons.append('Body does not exactly cover the header-to-continuation span.')
        if any(b.get('region') != region for b in body):
            reasons.append('Body crosses a decoded region boundary.')
        if (not body or body[-1]['mnemonic'] != 'FN_RETURN' or
                body[-1].get('control') != 'function-return'):
            reasons.append('Body does not end in FN_RETURN.')
        for b in body[:-1]:
            expected = 'descriptor-indirect-call' if b['mnemonic'] == 'FN_CALL' else 'fallthrough'
            if b.get('control') != expected or b['mnemonic'] in ('DEF_FN', 'FN_RETURN'):
                reasons.append('Nested definition/return or unsupported body control.')
                break
        if any(b.get('targets') for b in body):
            reasons.append('Body has explicit control targets.')
        if any(p != header and not (entry <= p < end)
               for b in body for p in incoming[b['address']]):
            reasons.append('Body has a foreign explicit incoming edge.')
        definitions.append({'header': header, 'region': region, 'descriptorOffset': encoded,
                            'descriptorValueOffset': offset, 'name': name,
                            'parameterOffset': parameter, 'parameterName': formal,
                            'bodyEntry': entry, 'continuation': end,
                            'returnAddress': body[-1]['address'] if body else None,
                            'reasons': reasons})

    # Even a malformed nested/overlapping declaration prevents confident blocks.
    for i, d in enumerate(definitions):
        for other in definitions[i + 1:]:
            if (isinstance(d['continuation'], int) and isinstance(other['continuation'], int) and
                    max(d['header'], other['header']) < min(d['continuation'], other['continuation'])):
                for item in (d, other):
                    item['reasons'].append('Definition spans overlap or nest.')
    by_offset = defaultdict(list)
    for d in definitions:
        d['reasons'] = list(dict.fromkeys(d['reasons']))
        d['status'] = 'block' if not d['reasons'] else 'unresolved'
        by_offset[d['descriptorValueOffset']].append(d['header'])

    calls = []
    for r in rows:
        if r['mnemonic'] != 'FN_CALL':
            continue
        v = r.get('operands', {})
        offset = v.get('value')
        name = scalar_name(offset, 'function')
        reasons = []
        if name is None:
            reasons.append('Call scalar/name is missing, ambiguous or not function-typed.')
        elif 'name' in v and v['name'] != name:
            name = None
            reasons.append('Call operand name disagrees with the scalar identity.')
        candidates = list(by_offset.get(offset, [])) if offset is not None else []
        if not candidates:
            reasons.append('No p-code definition with the matching descriptor value offset.')
        status = ('unresolved' if reasons else 'one-static-candidate' if len(candidates) == 1
                  else 'multiple-static-candidates')
        calls.append({'address': r['address'], 'descriptorValueOffset': offset, 'name': name,
                      'candidateDefinitions': candidates, 'status': status, 'reasons': reasons})
    for d in definitions:
        d['callSites'] = [c['address'] for c in calls if d['header'] in c['candidateDefinitions']]
    embedded = [{'address': r['address'], 'text': r['operands']['text'],
                 'provenance': 'embedded tokenized BASIC; not a p-code descriptor association'}
                for r in rows if r.get('grammar') == 'basic_island' and
                r.get('operands', {}).get('text', '').startswith('DEF')]
    return {'schema': 'dtl-function-index-v1', 'scope': SCOPE,
            'runtimeBindingProved': False, 'purityProved': False,
            'definitions': definitions, 'calls': calls, 'embeddedDefinitions': embedded}


def render_index(index):
    lines = ['\n; DTL FUNCTION INDEX', '; ' + index['scope']]
    label = lambda address: '<?>' if address is None else f'L_{address:04X}'
    for d in index['definitions']:
        lines.append('; ' + (d['name'] or 'FN <?>') + '(' + (d['parameterName'] or '<?>') + ')'
                     + f' [{d["status"]}] definition {label(d["header"])}; body {label(d["bodyEntry"])};'
                     + f' continuation {label(d["continuation"])}; descriptor value offset {d["descriptorValueOffset"]}')
        lines.append(';   static call sites: ' + (', '.join(map(label, d['callSites'])) or 'none'))
        lines.extend(';   ' + reason for reason in d['reasons'])
    for c in index['calls']:
        if c['status'] != 'one-static-candidate':
            lines.append(f'; CALL {label(c["address"])} [{c["status"]}]; candidates: '
                         + (', '.join(map(label, c['candidateDefinitions'])) or 'none'))
            lines.extend(';   ' + reason for reason in c['reasons'])
    for e in index['embeddedDefinitions']:
        lines.append(f'; EMBEDDED {label(e["address"])}: {e["text"]} — {e["provenance"]}')
    return lines
