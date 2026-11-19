#!/usr/bin/env python3
"""Normalize one frozen stock C64 bank from a supported x64sc VSF.

This is not a raster replay: splits, bank changes during a frame, cartridges,
expanded RAM, and transitional VIC bank selection are not represented.  Only
PA0 and PA1 are reconstructed, not IEC or user-port input levels.  ROMs in the
snapshot are never extracted.  --chargen copies your own ROM for local use.

Layout references: VICE 3.10 release source (src/) and
https://github.com/VICE-Team/svn-mirror/tree/3.9.0/vice/src
In particular: c64/c64memsnapshot.c, core/ciacore.c, viciisc/vicii-snapshot.c,
series constants in viciisc/viciitypes.h, and the QWORD clock in snapshot.h.
All field offsets below are relative to the start of a module payload.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / '6502-code-reuse' / 'scripts'))
from extract_vice_snapshot import parse_snapshot


# Color RAM follows model + regs, raster/IRQ, vbuf/cbuf, gbuf/dbuf, Y/collision
# state, six counters, light pen (including 8-byte CLOCK), DMA, and eight bytes
# ending at refresh_counter.  mem_color_ram_to_snapshot copies 0x400 bytes.
COLOR_OFFSET = 65 + 19 + 80 + (1 + 4 + 65 * 8) + 8 + 24 + 22 + 10 + 8  # 761


def normalize(data, cia2_pins=None):
    """Return descriptor and raw blocks without writing any files."""
    parsed = parse_snapshot(data)
    version = parsed['viceVersionBytes']
    is_310 = version == [3, 10, 0, 0] and parsed['viceRevision'] == 0
    if (parsed['machine'] != 'C64SC' or (version != [3, 9, 0, 0] and not is_310)
            or parsed['fileVersion'] != {'major': 2, 'minor': 0}):
        raise ValueError('requires C64SC format 2.0 from VICE 3.9.0.0 or 3.10.0.0 (revision 0)')

    versions = {}

    def module(name, version, size=None):
        matches = [m for m in parsed['modules'] if m['name'] == name]
        if len(matches) != 1:
            raise ValueError(f'expected exactly one {name} module, found {len(matches)}')
        m = matches[0]
        if (m['major'], m['minor']) != version:
            raise ValueError(f'unsupported {name} version {m["major"]}.{m["minor"]}')
        if size is not None and m['payloadSize'] != size:
            raise ValueError(f'unsupported {name} payload size {m["payloadSize"]}')
        versions[name] = f'{version[0]}.{version[1]}'
        return memoryview(data)[m['payloadOffset']:m['endOffsetExclusive']]

    mem = module('C64MEM', (0, 1), 65555)
    # These are VICE export flags (not raw active-low line voltages).  Even
    # unmapped cartridges must also pass the independent cartridge-count check.
    cart = module('C64CART', (0, 1))
    hacks = module('C64MEMHACKS', (0, 0), 1)
    if mem[2:4] != b'\0\0' or cart != b'\0' or hacks[0] != 0:
        raise ValueError('requires stock memory: no cartridge or RAM expansion')

    cia = module('CIA2', (2, 5), 77)
    pra, ddra = cia[0], cia[2]
    if cia2_pins is None:
        if (ddra & 3) != 3:
            raise ValueError('CIA2 bank pins not both outputs; supply observed --cia2-pins')
        pins, pin_source = pra & 3, 'PA0 and PA1 from PRA outputs; upper bits unspecified (stored as zero)'
    else:
        if type(cia2_pins) is not int or not 0 <= cia2_pins <= 255:
            raise ValueError('--cia2-pins must be an observed byte (0 through 255)')
        if (cia2_pins ^ pra) & ddra & 3:
            raise ValueError('observed CIA2 pins conflict with a bank bit configured as output')
        pins, pin_source = cia2_pins, 'user-observed port A pins'

    glue_type, bank, pending = module('GLUE', (1, 0), 3)
    if glue_type not in (0, 1) or pending or bank != (~pins & 3):
        raise ValueError('GLUE does not confirm a stable matching VIC bank')

    vic = module('VIC-II', (1, 3))
    # Eight 12-byte sprite records and 174 bytes of draw-cycle state follow
    # color RAM.  Check the variable raster tail's framing, not its pixels.
    raster = COLOR_OFFSET + 1024 + 8 * 12 + 174
    if len(vic) < raster + 16 or vic[0] > 6:
        raise ValueError('short VIC-II module or unsupported VIC-II model')
    if is_310 and vic[0] != 3:
        raise ValueError('VICE 3.10.0.0 requires tested VIC-II model 3 (MOS6567R8 NTSC)')
    _, width, height, _ = struct.unpack_from('<4I', vic, raster)
    if not width or not height or len(vic) != raster + 16 + width * (height + 4):
        raise ValueError('invalid VIC-II raster payload size')

    blocks = {'ram': parsed['ram'], 'vic': bytes(vic[1:65]),
              'color_ram': bytes(vic[COLOR_OFFSET:COLOR_OFFSET + 1024])}
    spec = {key: key + '.bin' for key in blocks}
    spec.update(cia2_pins=pins, provenance={
        'machine': parsed['machine'], 'vice_version': '.'.join(map(str, version)), 'vice_revision': parsed['viceRevision'],
        'snapshot_sha256': sha256(data).hexdigest(), 'module_versions': versions,
        'payload_offsets': {'ram': ['C64MEM', 4], 'vic': ['VIC-II', 1], 'color_ram': ['VIC-II', COLOR_OFFSET]},
        'vic_model': vic[0], 'cia2_pra': pra, 'cia2_ddra': ddra, 'cia2_pins_source': pin_source,
        'scope': 'one frozen stock VIC bank, not a rendered frame',
    })
    return spec, blocks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('snapshot', type=Path, metavar='FILE.vsf')
    parser.add_argument('output', type=Path, metavar='NEW_INPUT_DIR')
    parser.add_argument('--chargen', type=Path, metavar='FILE', help='external 4096-byte character ROM')
    parser.add_argument('--cia2-pins', type=lambda s: int(s, 0), metavar='NUMBER',
                        help='observed CIA2 port A byte in decimal or 0x-prefixed hex')
    args = parser.parse_args()
    try:
        spec, blocks = normalize(args.snapshot.read_bytes(), args.cia2_pins)
        if args.chargen is not None:
            rom = args.chargen.read_bytes()
            if len(rom) != 4096:
                raise ValueError('--chargen requires a 4096-byte external ROM')
            blocks['chargen'] = rom
            spec['chargen'] = 'chargen.bin'
            spec['provenance']['external_chargen_sha256'] = sha256(rom).hexdigest()
        args.output.mkdir(exist_ok=False)
        for key, block in blocks.items():
            (args.output / spec[key]).write_bytes(block)
        capture = args.output / 'capture.json'
        capture.write_text(json.dumps(spec, indent=2) + '\n', encoding='utf-8')
    except (ValueError, OSError) as exc:
        parser.exit(1, f'capture refused: {exc}\n')
    print(f'Wrote {capture}')


if __name__ == '__main__':
    main()
