"""Locate one mapped byte in a canonical reconstruction, without executing it."""


def describe_address(report, address):
    if not 0 <= address <= 0xffff:
        raise ValueError('lookup address outside 16-bit range')
    prefix = f'{report["family"]} ${address:04X}'
    match = None
    for group in report['groups']:
        for row in group['instructions']:
            offset = address - row['address']
            if offset < 0 or offset >= len(bytes.fromhex(row['bytes'])):
                continue
            if match is not None:
                raise ValueError(f'ambiguous instruction ownership at ${address:04X}')
            match = group, row, offset
    if match is None:
        names = [r['name'] for r in report['loadedRegions'] if r['start'] <= address < r['end']]
        location = ', '.join(names) or 'outside reported regions'
        return f'{prefix}: no decoded p-code instruction owns this byte ({location}).\n'
    group, row, offset = match
    position = 'instruction start' if not offset else f'instruction byte +{offset}'
    lines = [f'{prefix}: {position} of ${row["address"]:04X} {row["mnemonic"]} [{row["bytes"]}]',
             f'  L_{group["instructions"][0]["address"]:04X}: [{group["kind"]}] {group["text"]}']
    lines.extend('  ; ' + warning for warning in group['warnings'])
    start = row['address']
    cited_by = [g['instructions'][0]['address'] for g in report['groups']
                if g is not group and g['instructions'] and start in g.get('evidenceAddresses', ())]
    if cited_by:
        lines.append('  Other detailed groups citing this instruction: ' +
                     ', '.join(f'L_{addr:04X}' for addr in cited_by))
    view = report.get('readingView') or {}
    if view.get('schema') == 'dtl-idiomatic-reading-v1':
        for compact in view['groups']:
            if start in compact['instructionAddresses']:
                lines.append(f"  Compact reading: [{compact['kind']}] {compact['text']}")
                lines.extend('  ; ' + w for w in compact['warnings'] if w not in group['warnings'])
    elif view.get('schema') == 'petspeed-numbered-reading-v1':
        for item in view['lines']:
            if item['emissionAddress'] == start:
                lines.append(f"  Generated line emitted here: {item['number']} {item['text']}")
    return '\n'.join(lines) + '\n'
