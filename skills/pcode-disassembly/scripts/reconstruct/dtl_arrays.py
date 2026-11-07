"""Static DTL DIM/registration associations, never proof of initialized storage.

Only contiguous same-region DIM + optional delimiters + complete registration
bundles qualify. Conflicts and unmatched writes to a descriptor refuse its uses.
Bounds are not evaluated; names/ranks are retained binary syntax, not source input.
"""
from collections import defaultdict
import re


CAVEAT = ('Static binary DIM/registration association only; runtime initialization, '
          'reachability, bounds and native mutation are not proved.')


def parse_dim(text):
    """Return complete [(name, rank, type), ...], or [] for unsupported syntax."""
    if not isinstance(text, str) or not text.startswith('DIM'):
        return []
    rest = text[3:]; result = []; pos = 0
    while pos < len(rest):
        match = re.match(r'\s*([A-Z][A-Z0-9]*[%$]?)\s*\(', rest[pos:])
        if not match:
            return []
        name = match.group(1); pos += match.end()
        depth = 1; rank = 1; quoted = False; argument = False
        while pos < len(rest) and depth:
            char = rest[pos]; pos += 1
            if char == '"':
                quoted = not quoted; argument = True
            elif quoted:
                continue
            elif char == '(':
                depth += 1; argument = True
            elif char == ')':
                depth -= 1
                if depth == 0 and not argument:
                    return []
            elif char == ',' and depth == 1:
                if not argument:
                    return []
                rank += 1; argument = False
            elif char in ':\r\n':
                return []
            elif not char.isspace():
                argument = True
        if depth or quoted:
            return []
        kind = 'string' if name.endswith('$') else 'integer' if name.endswith('%') else 'real'
        result.append((name, rank, kind))
        while pos < len(rest) and rest[pos].isspace():
            pos += 1
        if pos == len(rest):
            return result
        if rest[pos] != ',':
            return []
        pos += 1
    return []  # Empty DIM or dangling comma.


def array_type(mnemonic):
    match = re.fullmatch(r'(?:LOAD|STORE)_(REAL|INTEGER|STRING)_ARRAY(?:_LONG)?', mnemonic)
    return match.group(1).lower() if match else None


def analyze_arrays(report):
    rows = report['instructions']; registrations = []; uses = []
    explicit_targets = {target for r in rows for target in r.get('targets', [])}
    pending = None; previous = None

    def abandon():
        nonlocal pending
        if pending:
            for record in pending['records']:
                record['reasons'].append('Incomplete or interrupted DIM/registration bundle.')
        pending = None

    for r in rows:
        address = r['address']; region = r.get('region', 'main')
        contiguous = (previous is not None and
                      previous['address'] + previous.get('length', previous.get('size', 1)) == address and
                      previous.get('region', 'main') == region)
        if pending and (not contiguous or address in explicit_targets):
            abandon()
        mnemonic = r['mnemonic']; value = r.get('operands', {})
        if r.get('grammar') == 'basic_island':
            abandon()
            dims = parse_dim(value.get('text'))
            if dims:
                pending = {'declaration': address, 'dimensions': dims, 'records': []}
        elif mnemonic == 'ARRAY_REGISTER':
            record = {'address': address, 'region': region, 'descriptorOffset': value.get('value'),
                      'declaration': None, 'name': None, 'rank': None, 'type': None, 'reasons': []}
            registrations.append(record)
            if pending:
                name, rank, kind = pending['dimensions'][len(pending['records'])]
                record.update(declaration=pending['declaration'], name=name, rank=rank, type=kind)
                pending['records'].append(record)
                if len(pending['records']) == len(pending['dimensions']):
                    pending = None
            else:
                record['reasons'].append('Registration lacks a complete adjacent binary DIM association.')
        elif mnemonic != 'DELIMITER':
            abandon()
        kind = array_type(mnemonic)
        if kind:
            uses.append({'address': address, 'region': region, 'descriptorOffset': value.get('value'),
                         'mnemonic': mnemonic, 'type': kind,
                         'access': 'read' if mnemonic.startswith('LOAD_') else 'write'})
        previous = r
    abandon()

    by_offset = defaultdict(list); use_offsets = defaultdict(list)
    for r in registrations:
        by_offset[r['descriptorOffset']].append(r)
    for use in uses:
        use_offsets[use['descriptorOffset']].append(use)
    descriptors = []
    for offset in sorted(set(by_offset) | set(use_offsets), key=lambda x: (not isinstance(x, int), str(x))):
        records = by_offset[offset]; reasons = []
        if not isinstance(offset, int) or isinstance(offset, bool) or not 0 <= offset <= 65535:
            reasons.append('Invalid descriptor offset.')
        if not records:
            reasons.append('No binary DIM/registration association.')
        if any(r['reasons'] for r in records):
            reasons.append('At least one registration has no validated DIM association.')
        candidates = {(r['name'], r['rank'], r['type']) for r in records if not r['reasons']}
        if len(candidates) > 1:
            reasons.append('Conflicting name/rank/type declarations for this descriptor.')
        candidate = next(iter(candidates)) if len(candidates) == 1 else (None, None, None)
        if candidate[2] and any(u['type'] != candidate[2] for u in use_offsets[offset]):
            reasons.append('Typed array accesses disagree with the DIM type.')
        status = 'associated' if candidate[0] and not reasons else 'unresolved'
        descriptor = {'descriptorOffset': offset, 'status': status,
                      'name': candidate[0] if status == 'associated' else None,
                      'rank': candidate[1] if status == 'associated' else None,
                      'type': candidate[2] if status == 'associated' else None,
                      'registrations': [r['address'] for r in records],
                      'declarations': sorted({r['declaration'] for r in records if r['declaration'] is not None}),
                      'accessSites': [u['address'] for u in use_offsets[offset]], 'reasons': reasons}
        descriptors.append(descriptor)
        for use in use_offsets[offset]:
            use.update(status=status, name=descriptor['name'], rank=descriptor['rank'],
                       declarations=descriptor['declarations'], registrations=descriptor['registrations'],
                       reasons=list(reasons), precedesAllRegistrations=bool(records) and
                       all(use['address'] < r['address'] for r in records))
    return {'schema': 'dtl-array-index-v1', 'runtimeInitializationProved': False,
            'caveat': CAVEAT, 'descriptors': descriptors, 'registrations': registrations, 'accesses': uses}


def render_arrays(index):
    out = ['\n; DTL ARRAY INDEX — ' + index['caveat']]
    for d in index['descriptors']:
        name = (d['name'] + ' rank ' + str(d['rank'])) if d['status'] == 'associated' else 'unresolved'
        sites = ', '.join(f'L_{a:04X}' for a in d['registrations']) or 'none'
        out.append(f'; descriptor {d["descriptorOffset"]}: {name}; registrations: {sites}')
        out.extend(';   ' + reason for reason in d['reasons'])
    return out
