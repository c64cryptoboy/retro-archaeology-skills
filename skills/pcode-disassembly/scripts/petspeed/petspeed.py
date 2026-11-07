#!/usr/bin/env python3
"""Conservative PETSpeed p-code decoder and source-correlated listing.

VM addresses/semantics live in the external runtime profile. Unknown lengths
stop decoding; supplied BASIC is annotation, not recovered/authenticated source.
Standard library only. Commercial runtimes are not bundled.
"""
from __future__ import annotations

import argparse
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import re


class DecodeError(ValueError):
    pass


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_at(raw: bytes, base: int, address: int, count: int) -> bytes:
    if count < 0 or address < base or address + count > base + len(raw):
        raise DecodeError(f'truncated/out-of-image read ${address:04X}+{count}')
    return raw[address - base:address - base + count]


def inspect_image(prg: bytes, profile: dict) -> tuple[bytes, int, dict]:
    if profile.get('schema') != 'petspeed-runtime-profile-v1':
        raise DecodeError('unsupported profile schema')
    if len(prg) < 3:
        raise DecodeError('truncated PRG')
    base = int.from_bytes(prg[:2], 'little')
    raw = prg[2:]
    if base != profile['loadAddress']:
        raise DecodeError('unsupported load address')
    expected = bytes.fromhex(profile['entryBytes'])
    if read_at(raw, base, profile['entryAddress'], len(expected)) != expected:
        raise DecodeError('unsupported entry stub')
    runtime = read_at(raw, base, profile['runtimeStart'], profile['runtimeEnd'] - profile['runtimeStart'])
    if sha(runtime) != profile['runtimeSha256']:
        raise DecodeError('unsupported runtime fingerprint; obtain a separately evidenced profile')
    layout = {key: int.from_bytes(read_at(raw, base, address, 2), 'little')
              for key, address in profile['headerWords'].items()}
    layout['codeStart'] = layout['codeCursor'] + 1
    boundaries = [profile['runtimeEnd'], layout['data'], layout['arrays'],
                  layout['initialization'], layout['codeStart'], layout['topCode'], base + len(raw)]
    if boundaries != sorted(boundaries) or layout['codeStart'] == layout['topCode']:
        raise DecodeError('invalid region ordering/empty code')
    layout['loadAddress'] = base
    layout['imageEnd'] = base + len(raw)
    return raw, base, layout


def parse_line_map(data: bytes, layout: dict) -> dict:
    parts = data.split(b'\r', 2)
    if len(parts) != 3 or any(not re.fullmatch(rb' *[0-9]+ *', p) for p in parts[:2]):
        raise DecodeError('invalid .W decimal headers')
    start, top = (int(p) for p in parts[:2])
    if start != layout['codeStart'] or top != layout['topCode'] + 1:
        raise DecodeError('.W headers do not match this compiled image')
    body = parts[2]
    if len(body) < 4 or len(body) % 4:
        raise DecodeError('truncated .W word pairs/footer')
    # Last four bytes vary among supplied/compiler-produced examples. They are
    # opaque, not a presumed zero line-number terminator and not instructions.
    rows = []
    for n in range(0, len(body) - 4, 4):
        line = int.from_bytes(body[n:n + 2], 'little')
        offset = int.from_bytes(body[n + 2:n + 4], 'little')
        address = start + offset
        if line > 63999 or not start <= address < layout['topCode']:
            raise DecodeError('invalid .W line/address')
        if rows and (line < rows[-1]['line'] or address < rows[-1]['address']):
            raise DecodeError('nonmonotonic .W map')
        rows.append({'line': line, 'offset': offset, 'address': address})
    return {'start': start, 'topHeader': top, 'records': rows, 'opaqueFooterHex': body[-4:].hex()}


def parse_source(text: str) -> dict[int, str]:
    result = {}
    for physical in text.splitlines():
        if not physical.strip():
            continue
        match = re.fullmatch(r'\s*(\d+)\s+(.*)', physical)
        if not match:
            raise DecodeError('source must be a numbered BASIC text listing')
        line = int(match[1])
        if line > 63999 or line in result:
            raise DecodeError('invalid/duplicate BASIC source line')
        result[line] = match[2]
    return result


def petscii_literal(data: bytes) -> str:
    # Explicit byte escapes for graphics/control bytes; no false ASCII decoding.
    return '"' + ''.join(chr(c) if 32 <= c <= 126 and c not in (34, 92)
                         else f'\\x{c:02X}' for c in data) + '"'


def decode_one(raw: bytes, base: int, address: int, end: int, profile: dict) -> dict:
    def take(n):
        if address + n > end:
            raise DecodeError(f'truncated instruction at ${address:04X}')
        return read_at(raw, base, address, n)
    opcode = take(1)[0]
    spec = profile['opcodes'].get(f'{opcode:02X}')
    values = {}
    if spec is None:
        for family in profile['families']:
            if family['first'] <= opcode <= family['last']:
                spec = family
                slot = opcode - family['first']
                values.update(slot=slot, variable=profile['variableBase'] + slot * profile['variableStride'])
                break
    if spec is None:
        raise DecodeError(f'unknown operand length for opcode ${opcode:02X} at ${address:04X}')
    prefix = 1
    if 'selectors' in spec:
        selector = take(2)[1]
        spec = spec['selectors'].get(f'{selector:02X}')
        if spec is None:
            raise DecodeError(f'unknown selector ${selector:02X} for opcode ${opcode:02X} at ${address:04X}')
        values['selector'] = selector
        prefix = 2
    if 'modifierTable' in spec:
        if spec['operand'] != 'none':
            raise DecodeError('trailing modifier requires an operand-free primary instruction')
        if address + prefix < end:
            modifier = take(prefix + 1)[prefix]
            extra = profile['modifierTables'][spec['modifierTable']].get(f'{modifier:02X}')
            if extra is not None:
                spec = dict(spec, mnemonic=spec['mnemonic'] + extra['mnemonicSuffix'],
                            comment=spec['comment'] + extra['commentSuffix'],
                            evidence=spec.get('evidence', '') + '; ' + extra['evidence'])
                values['modifier'] = modifier
                prefix += 1
    kind = spec['operand']
    payload_size = {'none': 0, 'u8': 1, 'i16le': 2, 'u16le': 2, 'u16be': 2, 'float6': 6}.get(kind)
    if kind == 'string8':
        payload_size = 1 + take(prefix + 1)[prefix]
    elif kind == 'branch_table8le':
        payload_size = take(prefix + 1)[prefix]
        if payload_size < 2 or payload_size % 2:
            raise DecodeError(f'invalid branch-table byte span at ${address:04X}')
    elif kind == 'definition16le8':
        payload_size = 5
    if payload_size is None:
        raise DecodeError(f'unsupported operand grammar {kind!r}')
    size = prefix + payload_size
    data = take(size)
    payload = data[prefix:]
    if kind in ('u8', 'i16le', 'u16le', 'u16be'):
        values['value'] = int.from_bytes(payload, 'big' if kind.endswith('be') else 'little',
                                       signed=(kind == 'i16le'))
    elif kind == 'string8':
        values.update(stringHex=payload[1:].hex(), display=petscii_literal(payload[1:]))
    elif kind == 'branch_table8le':
        mode = spec['branchModes'].get(f'{payload[1]:02X}')
        if mode is None:
            raise DecodeError(f'unknown branch-table mode ${payload[1]:02X} at ${address:04X}')
        targets = [int.from_bytes(payload[n:n + 2], 'little') for n in range(2, len(payload), 2)]
        values.update(tableBytes=payload[0], branchMode=mode, targets=targets,
                      targetList=', '.join(f'${t:04X}' for t in targets))
    elif kind == 'definition16le8':
        descriptor = int.from_bytes(payload[:2], 'little')
        body = int.from_bytes(payload[2:4], 'little')
        skip = address + payload[4]
        values.update(descriptor=descriptor, bodyTarget=body, skipTarget=skip,
                      skipBytes=payload[4], targets=[body, skip])
    elif kind == 'float6':
        exp = payload[0]
        value = Fraction(0) if exp == 0 else Fraction(int.from_bytes(payload[1:5], 'big'), 1 << 31) * Fraction(2) ** (exp - 129)
        if payload[5] & 0x80:
            value = -value
        values.update(numerator=value.numerator, denominator=value.denominator,
                      display=str(value.numerator) if value.denominator == 1 else f'{float(value):.12g} [exact {value}]')
    if 'variableIndex' in spec:
        index = spec['variableIndex']
        values['variable'] = index['base'] + index['stride'] * values['value']
        values['slot'] = index['firstSlot'] + values['value']
    if 'target' in spec:
        target = spec['target']
        values['target'] = values['value'] + target['bias'] + (address if target['relative'] else 0)
    return {'address': address, 'opcode': opcode, 'bytes': data.hex(' '), 'size': size,
            'mnemonic': spec['mnemonic'], 'operands': values,
            'comment': spec['comment'].format(**values), 'evidence': spec.get('evidence', ''),
            'control': spec.get('control', 'fallthrough')}


def disassemble(prg: bytes, profile: dict, w_data: bytes | None = None, source_text: str | None = None) -> dict:
    raw, base, layout = inspect_image(prg, profile)
    line_map = parse_line_map(w_data, layout) if w_data is not None else None
    if source_text is not None and line_map is None:
        raise DecodeError('source correlation requires the matching .W map')
    source = parse_source(source_text) if source_text is not None else {}
    result = {'schema': 'petspeed-disassembly-v1', 'imageSha256': sha(prg), 'profile': profile['id'],
              'profileSha256': sha(json.dumps(profile, sort_keys=True).encode()),
              'layout': layout, 'lineMap': line_map, 'source': source,
              'sourceQualification': 'user-supplied text associated by .W; not recovered or authenticated original source',
              'instructions': [], 'completeCodeDecode': False, 'error': None,
              'limitations': profile.get('limitations', [])}
    if w_data is not None:
        result['lineMapSha256'] = sha(w_data)
    if source_text is not None:
        result['sourceTextSha256'] = sha(source_text.encode('utf-8'))
    address = layout['codeStart']
    try:
        while address < layout['topCode']:
            item = decode_one(raw, base, address, layout['topCode'], profile)
            result['instructions'].append(item)
            address += item['size']
        boundaries = {i['address'] for i in result['instructions']}
        if line_map and any(row['address'] not in boundaries for row in line_map['records']):
            raise DecodeError('.W line anchor falls inside an instruction operand')
        for item in result['instructions']:
            values = item['operands']
            targets = list(values.get('targets', []))
            if 'target' in values:
                targets.append(values['target'])
            for target in targets:
                if target not in boundaries:
                    raise DecodeError(f'control target ${target:04X} is not a decoded instruction boundary')
        result['completeCodeDecode'] = True
    except DecodeError as exc:
        result['error'] = str(exc)
    result['decodedBytes'] = address - layout['codeStart']
    result['codeBytes'] = layout['topCode'] - layout['codeStart']
    return result


def render(result: dict) -> str:
    layout = result['layout']
    out = [f"PETSpeed profile: {result['profile']}", f"Image SHA-256: {result['imageSha256']}",
           f"P-code ${layout['codeStart']:04X}..${layout['topCode'] - 1:04X}; "
           f"{result['decodedBytes']}/{result['codeBytes']} bytes decoded",
           'Linear disassembly; listing an instruction does not prove reachability.']
    if result['lineMap']:
        out.append('BASIC lines below are supplied annotations linked through .W, not recovered source.')
        out.append('The .W opaque footer is retained in JSON; duplicate map records are preserved.')
    by_address = {}
    for row in (result['lineMap'] or {}).get('records', []):
        by_address.setdefault(row['address'], []).append(row)
    seen_lines = set()
    for item in result['instructions']:
        rows = by_address.get(item['address'], [])
        for n, row in enumerate(rows):
            line = row['line']
            source = result['source'].get(line, result['source'].get(str(line), '<source not supplied>'))
            out.extend(['', f'{line} {source}'])
            if line in seen_lines:
                out.append('  ; additional compiler map record for this source line')
            if n < len(rows) - 1:
                out.append('  ; shares the next source line\'s code boundary; no separate bytes')
            seen_lines.add(line)
        out.append(f"  ${item['address']:04X}  {item['bytes'].upper():<50} {item['mnemonic']}")
        out.append('          ; ' + item['comment'])
    if result['error']:
        out.extend(['', 'REFUSED: ' + result['error'], 'No guessed instruction lengths or resynchronization.'])
    return '\n'.join(out) + '\n'


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('program', type=Path, help='compiled .WOW PRG')
    parser.add_argument('--profile', type=Path, default=Path(__file__).with_name('petspeed_profile.json'))
    parser.add_argument('--map', type=Path, help='matching raw .W SEQ file (no PRG header)')
    parser.add_argument('--source', type=Path, help='numbered BASIC text for annotations')
    parser.add_argument('--json-output', type=Path)
    parser.add_argument('--text-output', type=Path)
    args = parser.parse_args()
    try:
        profile = json.loads(args.profile.read_text())
        result = disassemble(args.program.read_bytes(), profile,
                             args.map.read_bytes() if args.map else None,
                             args.source.read_text() if args.source else None)
    except (DecodeError, OSError, json.JSONDecodeError) as exc:
        parser.exit(2, f'REFUSED: {exc}\n')
    text = render(result)
    if args.json_output:
        args.json_output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    if args.text_output:
        args.text_output.write_text(text)
    else:
        print(text, end='')
    return 0 if result['completeCodeDecode'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
