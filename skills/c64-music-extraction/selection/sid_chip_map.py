"""Read PSID v1 through v4 chip declarations and annotate C64 I/O addresses."""

import argparse
import json
import struct


def read_chip_map(stream):
    """Read just the fixed header.  Bases are keyed by 1-based SID slot, not pitch order."""
    prefix = stream.read(8)
    if len(prefix) != 8:
        raise ValueError('truncated PSID header')
    magic, version, offset = struct.unpack('>4sHH', prefix)
    if magic != b'PSID':
        raise ValueError('expected PSID magic; RSID is not supported')
    if version not in (1, 2, 3, 4):
        raise ValueError(f'unsupported PSID version {version}')
    size = 0x76 if version == 1 else 0x7c
    if offset != size:
        raise ValueError(f'expected fixed data offset {size:#06x}')
    header = prefix + stream.read(size - 8)
    if len(header) != size:
        raise ValueError('truncated PSID header')

    bases = {1: 0xd400}
    warnings = []
    for slot, raw in enumerate(header[0x7a:0x7c], 2):
        if raw == 0:
            continue
        base = 0xd000 + (raw << 4)
        if version < slot + 1:
            reason = f'reserved in v{version}; must be zero'
        elif not (0x42 <= raw <= 0x7e or 0xe0 <= raw <= 0xfe):
            reason = 'outside permitted address ranges'
        elif raw & 1:
            reason = 'unaligned 32-byte block (odd encoding)'
        elif base in bases.values():
            reason = 'duplicates a declared SID base'
        else:
            bases[slot] = base
            continue
        warnings.append(f'SID{slot} byte ${raw:02X} ignored: {reason}')
    return {'version': version, 'bases': bases, 'warnings': warnings}


VOICE_REGS = ('freq_lo', 'freq_hi', 'pulse_lo', 'pulse_hi', 'control', 'attack_decay', 'sustain_release')
CHIP_REGS = ('cutoff_lo', 'cutoff_hi', 'resonance_routing', 'mode_volume', 'pot_x', 'pot_y', 'osc3', 'env3')


def annotate_address(bases, address):
    """Use read_chip_map's bases, and an original CPU address (assuming I/O is visible)."""
    if not 0 <= address <= 0xffff:
        raise ValueError('expected a 16-bit address')
    for chip, base in bases.items():
        offset = address - base
        if 0 <= offset < 0x20:
            if offset < 0x15:
                register = VOICE_REGS[offset % 7]
                voice = 1 + offset // 7
            else:
                register = CHIP_REGS[offset - 0x15] if offset <= 0x1c else 'unused'
                voice = None
            return dict(address=address, region='declared_block', chip=chip, base=base,
                        offset=offset, local_voice=voice, register=register)
    region = 'possible_stock_mirror' if 0xd420 <= address <= 0xd7ff else 'outside_declared_blocks'
    return dict(address=address, region=region)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('file')
    parser.add_argument('address', nargs='*', type=lambda s: int(s, 0), help='decimal or 0x-prefixed address')
    args = parser.parse_args()
    try:
        with open(args.file, 'rb') as stream:
            result = read_chip_map(stream)
        result['annotations'] = [annotate_address(result['bases'], a) for a in args.address]
    except (OSError, ValueError) as exc:
        parser.exit(2, f'{parser.prog}: {exc}\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
