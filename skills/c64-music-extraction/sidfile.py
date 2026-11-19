"""Read or package a narrow, documented executable PSID v2NG profile (Python 3.8+).

No instruction execution, code generation, relocation, or automatic PRG detection.
See SKILL.md for the caller's driver, memory, and timing obligations.
"""
import argparse
import json
import struct
from dataclasses import dataclass, fields
from pathlib import Path


@dataclass(frozen=True)
class Tune:
    payload: bytes       # 6502 code + data, NO load-address prefix
    load: int            # effective address even for the prefixed form
    init: int            # explicit JSR entry, A = 0 for the sole song
    play: int            # explicit periodic JSR entry
    clock: str           # PAL or NTSC
    rate: str            # vbi or cia1a (not a literal Hz value)
    model: str           # unknown, 6581, 8580, or both
    name: str
    author: str
    released: str
    prefix: bool = True  # zero header load with a little-endian data prefix


_CLOCK = {'PAL': 4, 'NTSC': 8}
_RATE = {'vbi': 0, 'cia1a': 1}
_MODEL = {'unknown': 0, '6581': 16, '8580': 32, 'both': 48}
_HEAD = struct.Struct('>4s7HI32s32s32sH4B')


def _text(s):
    if not isinstance(s, str):
        raise ValueError('metadata must be Windows-1252 text')
    raw = s.encode('cp1252')
    if b'\0' in raw or len(raw) > 32:
        raise ValueError('metadata must fit 32 Windows-1252 bytes without embedded NUL')
    return raw.ljust(32, b'\0')


def _decode(raw):
    value, _, pad = raw.partition(b'\0')
    if any(pad):
        raise ValueError('nonzero metadata padding outside supported profile')
    return value.decode('cp1252')


def _check(t):
    if not isinstance(t.payload, bytes) or not t.payload:
        raise ValueError('payload must be nonempty raw bytes')
    if any(type(v) is not int for v in (t.load, t.init, t.play)):
        raise ValueError('addresses must be integers')
    end = t.load + len(t.payload)
    if not (0x0400 <= t.load < end <= 0xA000):
        raise ValueError('payload must fit in $0400 through $9FFF inclusive')
    if not all(t.load <= a < end for a in (t.init, t.play)):
        raise ValueError('explicit init and play must be inside payload')
    if t.clock not in _CLOCK or t.rate not in _RATE or t.model not in _MODEL:
        raise ValueError('unsupported clock, rate, or SID model')
    if type(t.prefix) is not bool:
        raise ValueError('prefix must be True or False')


def _driver_fields(t, dirty_pages):
    # Profile: ordinary bank-visible driver RAM with $01=$37.  An empty
    # declaration retains the original clean-image contract, not a code audit.
    windows = (range(0x04, 0xA0), range(0xC0, 0xD0))
    used = set(range(t.load >> 8, ((t.load + len(t.payload) - 1) >> 8) + 1))
    dirty = tuple(dirty_pages)
    if not dirty:
        return 0, 0
    for p in dirty:
        if type(p) is not int or not any(p in w for w in windows):
            raise ValueError('expected a dirty page number in bank-visible driver RAM')
        used.add(p)
    best_start = best_length = 0
    for window in windows:
        length = 0
        for p in window:
            length = 0 if p in used else length + 1
            if length > best_length:  # first largest run wins ties
                best_start, best_length = p + 1 - length, length
    if not best_length:
        raise ValueError('no free driver page; $FF/0 is outside this profile')
    return best_start, best_length


def write_psid(t: Tune, *, dirty_pages=()) -> bytes:
    """Pack linked bytes; declare pages used outside the load range in driver RAM."""
    _check(t)
    page, pages = _driver_fields(t, dirty_pages)
    flags = _CLOCK[t.clock] | _MODEL[t.model]
    hdr = _HEAD.pack(b'PSID', 2, 0x7C, 0 if t.prefix else t.load, t.init, t.play,
                     1, 1, _RATE[t.rate], _text(t.name), _text(t.author), _text(t.released),
                     flags, page, pages, 0, 0)
    return hdr + (t.load.to_bytes(2, 'little') if t.prefix else b'') + t.payload


def read_psid(data: bytes, *, dirty_pages=()) -> Tune:
    """Check driver fields against the caller's declaration; default is clean only."""
    if not isinstance(data, bytes) or len(data) < _HEAD.size:
        raise ValueError('expected at least a PSID v2NG header')
    (magic, version, off, load, init, play, songs, start, speed, name, author, released,
     flags, page, pages, second, third) = _HEAD.unpack_from(data)
    if (magic, version, off) != (b'PSID', 2, 0x7C):
        raise ValueError('only PSID v2NG with data offset $007C is supported')
    if (songs, start) != (1, 1) or speed not in (0, 1):
        raise ValueError('expected one song, start song 1, and speed 0 or 1')
    if flags & ~0x3C or (flags & 12) not in (4, 8):
        raise ValueError('expected internal C64 player and explicit PAL or NTSC, no extra flags')
    if not dirty_pages and (page or pages or second or third):
        raise ValueError('expected clean relocation fields and one SID only')
    if second or third:
        raise ValueError('expected one SID only')
    prefix = load == 0
    if prefix:
        if len(data) < off + 2:
            raise ValueError('truncated little-endian load address')
        load = int.from_bytes(data[off:off + 2], 'little')
        off += 2
    model = next(k for k, v in _MODEL.items() if v == (flags & 48))
    t = Tune(data[off:], load, init, play, 'PAL' if flags & 4 else 'NTSC',
             'cia1a' if speed else 'vbi', model, _decode(name), _decode(author),
             _decode(released), prefix)
    _check(t)
    if (page, pages) != _driver_fields(t, dirty_pages):
        raise ValueError('driver fields do not match the declared memory use')
    return t


def _address(s):
    return int(s, 0)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest='action', required=True)
    pack = sub.add_parser('pack', help='wrap raw code/data, without adding a player')
    pack.add_argument('payload', type=Path, help='already linked machine code, not a PRG or trace')
    pack.add_argument('output', type=Path)
    for key in ('load', 'init', 'play'):
        pack.add_argument('--' + key, type=_address, required=True, help='decimal or 0x-prefixed')
    for key, choices in [('clock', _CLOCK), ('rate', _RATE), ('model', _MODEL)]:
        pack.add_argument('--' + key, choices=list(choices), required=True)
    for key in ('name', 'author', 'released'):
        pack.add_argument('--' + key, required=True)
    pack.add_argument('--header-load', action='store_true', help='store load address in header instead')
    info = sub.add_parser('inspect')
    info.add_argument('sid', type=Path)
    info.add_argument('--payload-out', type=Path, help='extract raw payload (no load prefix)')
    args = ap.parse_args()
    try:
        if args.action == 'pack':
            t = Tune(args.payload.read_bytes(), args.load, args.init, args.play, args.clock,
                     args.rate, args.model, args.name, args.author, args.released, not args.header_load)
            packed = write_psid(t)
            with args.output.open('xb') as f:  # never replace an original
                f.write(packed)
        else:
            t = read_psid(args.sid.read_bytes())
            print(json.dumps({**{f.name: getattr(t, f.name) for f in fields(t) if f.name != 'payload'},
                              'payload_bytes': len(t.payload)}, sort_keys=True))
            if args.payload_out:
                with args.payload_out.open('xb') as f:
                    f.write(t.payload)
    except (ValueError, OSError) as e:
        ap.exit(1, f'{ap.prog}: {e}\n')


if __name__ == '__main__':
    main()
