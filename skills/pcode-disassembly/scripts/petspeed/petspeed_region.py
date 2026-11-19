#!/usr/bin/env python3
"""Disassemble an explicit [start, stop) interval of the pinned JMP $2245 revision.

API: disassemble_region(prg: bytes, start: int, stop: int) -> dict.
CLI: petspeed_region.py PROGRAM --start 0x3000 --stop 0x3010
JSON is written to stdout; refusals use stderr and exit status 2.  Decimal,
0x-prefixed, and $-prefixed addresses are accepted (quote $ in a shell).

There is no custom profile/hash, whole-program admission, boundary search,
resynchronization, execution, or reachability analysis.  An arbitrary start is
caller-assumed, not independently established by successful decoding.  One
instruction at the declared code start is checked for demonstrable overlap;
unknown grammar there does not prevent decoding a separately supplied interval.
Canonical instruction lookahead uses the declared code end, not the caller's
stop, so clipping cannot hide a contextual trailing modifier.  External encoded
targets must be in declared code, but their instruction boundaries are unverified.
Runtime-managed edges are not invented.  Even an explicitly supplied full-code
interval is only a linear interval result, never whole-program admission.

Standard library only.  No specimen or private workspace dependency.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

if __package__:
    from . import petspeed as ps
else:
    import petspeed as ps


def disassemble_region(prg: bytes, start: int, stop: int) -> dict:
    """Return canonical rows for an exact interval, or raise ps.DecodeError.

    Both bounds are mandatory integer addresses within declared code; stop is
    exclusive.  No partial result is returned on refusal.  The instructions
    retain decode_one's schema, for consumption by downstream reading tools.
    encodedTargets classifies only explicitly encoded control destinations.
    """
    if type(start) is not int or type(stop) is not int:
        raise ps.DecodeError('start and stop must be integer addresses')
    profile = json.loads(Path(__file__).with_name('petspeed_profile.json').read_text())
    profile = ps.select_profile(prg, profile)
    if profile['entryBytes'] != '4c4522':
        raise ps.DecodeError('interval API supports only the pinned JMP $2245 revision')
    raw, base, layout = ps.inspect_image(prg, profile)
    code_start, code_stop = layout['codeStart'], layout['topCode']
    if not code_start <= start < stop <= code_stop:
        raise ps.DecodeError('require codeStart <= start < stop <= topCode (exclusive stop)')

    # This single anchored instruction can disprove a start, but we never sweep
    # a prefix or infer a boundary from arbitrary preceding opcode-looking bytes.
    if start != code_start:
        try:
            first = ps.decode_one(raw, base, code_start, code_stop, profile)
        except ps.DecodeError:
            first = None
        if first is not None and start < code_start + first['size']:
            raise ps.DecodeError('start falls inside the declared first instruction')

    instructions = []
    address = start
    while address < stop:
        item = ps.decode_one(raw, base, address, code_stop, profile)
        next_address = address + item['size']
        if next_address > stop:
            raise ps.DecodeError(f'stop falls inside instruction at ${address:04X}')
        instructions.append(item)
        address = next_address
    if address != stop:
        raise ps.DecodeError('interval is not an exact instruction partition')

    boundaries = {item['address'] for item in instructions}
    targets = []
    for item in instructions:
        values = item['operands']
        encoded = list(values.get('targets', []))
        if 'target' in values:
            encoded.append(values['target'])
        for target in encoded:
            if not code_start <= target < code_stop:
                raise ps.DecodeError(f'control target ${target:04X} is outside declared code')
            internal = start <= target < stop
            if internal and target not in boundaries:
                raise ps.DecodeError(f'control target ${target:04X} falls inside an instruction')
            targets.append({'source': item['address'], 'target': target,
                            'scope': 'internal' if internal else 'external',
                            'boundaryVerified': internal})

    return {'schema': 'petspeed-region-v1', 'imageSha256': ps.sha(prg),
            'profile': profile['id'],
            'profileSha256': ps.sha(json.dumps(profile, sort_keys=True).encode()),
            'layout': layout, 'start': start, 'stop': stop,
            'entryBasis': 'declared-code-start' if start == code_start else 'caller-assumed',
            'instructions': instructions, 'encodedTargets': targets,
            'decodedBytes': stop - start, 'completeIntervalDecode': True,
            'completeCodeDecode': False,
            'limitations': [
                'Exact linear partition only; no whole-program admission or reachability claim.',
                'Arbitrary entry is caller-assumed; no prefix sweep or boundary discovery.',
                'External target boundaries are unverified; runtime-managed edges are not inferred.',
                'Canonical lookahead and one declared-first-instruction overlap check may read outside the interval.',
            ]}


def _address(text: str) -> int:
    try:
        return int(text[1:], 16) if text.startswith('$') else int(text, 0)
    except ValueError as exc:
        raise argparse.ArgumentTypeError('expected decimal, 0x-prefixed, or $-prefixed address') from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('program', type=Path, help='compiled PRG, read-only')
    parser.add_argument('--start', type=_address, required=True)
    parser.add_argument('--stop', type=_address, required=True, help='exclusive end address')
    args = parser.parse_args(argv)
    try:
        result = disassemble_region(args.program.read_bytes(), args.start, args.stop)
    except (ps.DecodeError, OSError, json.JSONDecodeError) as exc:
        parser.exit(2, f'REFUSED: {exc}\n')
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
