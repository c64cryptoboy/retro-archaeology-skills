"""Read PSID song-selection metadata, not the tune or its playback rate."""

import argparse
import json
import struct
from typing import BinaryIO, Optional


def select_song(stream: BinaryIO, song: Optional[int] = None) -> dict:
    """Read one fixed PSID header at the current position; song is 1-based."""
    prefix = stream.read(8)
    if prefix[:4] == b'RSID':
        raise ValueError('RSID is unsupported; its speed field is reserved')
    if prefix[:4] != b'PSID':
        raise ValueError('expected PSID magic')
    if len(prefix) != 8:
        raise ValueError('truncated PSID header')
    version, offset = struct.unpack_from('>HH', prefix, 4)
    if version not in (1, 2, 3, 4):
        raise ValueError(f'unsupported PSID version {version}')
    size = 0x76 if version == 1 else 0x7c
    if offset != size:
        raise ValueError(f'expected fixed data offset {size:#06x}')
    header = prefix + stream.read(size - len(prefix))
    if len(header) != size:
        raise ValueError('truncated PSID header')

    count, start, speed = struct.unpack_from('>HHI', header, 0x0e)
    if not 1 <= count <= 256:
        raise ValueError('song count must be 1 through 256')
    if not 1 <= start <= count:
        raise ValueError('default song outside declared range')
    if song is None:
        song = start
    elif type(song) is not int or not 1 <= song <= count:
        raise ValueError(f'requested song must be an integer from 1 through {count}')

    # V1 ends before the flags word.  Only bit 1 of the PSID flags selects
    # PlaySID-specific behavior; in particular, bit 0 (MUS) does not.
    repeat = version == 1 or bool(struct.unpack_from('>H', header, 0x76)[0] & 2)

    def selection(number):
        a = number - 1
        index = a % 32 if repeat else min(a, 31)
        bit = (speed >> index) & 1
        return dict(song=number, init_a=a, speed_bit_index=index, speed_bit=bit,
                    initial_source='CIA1 Timer A' if bit else 'VBI')

    return dict(version=version, songs=count, speed_rule='repeat-32' if repeat else 'hold-bit-31',
                default=selection(start), selected=selection(song))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('file', help='input file with a fixed PSID v1 through v4 header')
    parser.add_argument('--song', type=int, help='1-based song number (default: header startSong)')
    args = parser.parse_args()
    try:
        with open(args.file, 'rb') as stream:
            result = select_song(stream, args.song)
    except (OSError, ValueError) as exc:
        parser.exit(2, f'{parser.prog}: {exc}\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
