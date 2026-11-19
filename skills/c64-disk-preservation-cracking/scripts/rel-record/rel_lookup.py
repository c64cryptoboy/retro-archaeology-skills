"""Look up one fixed-width REL record on a plain 35-track D64, read-only."""
import argparse
import json
from pathlib import Path

TRACKS = (21,) * 17 + (19,) * 7 + (18,) * 6 + (17,) * 5
IMAGE_SIZE = 256 * sum(TRACKS)


def sector_offset(ts):
    t, s = ts
    if not (1 <= t <= 35 and 0 <= s < TRACKS[t - 1]):
        raise ValueError(f'invalid track/sector {t}/{s}')
    return 256 * (sum(TRACKS[:t - 1]) + s)


def lookup(image: bytes, name: bytes, number: int) -> dict:
    if len(image) != IMAGE_SIZE:
        raise ValueError(f'expected a plain {IMAGE_SIZE}-byte D64')
    if not 1 <= len(name) <= 16 or name.endswith(b'\xa0'):
        raise ValueError('expected 1 through 16 filename bytes without trailing padding')

    def block(ts):
        start = sector_offset(ts)
        return image[start:start + 256]

    at = (18, 1)
    metadata = {(18, 0)}
    entries = []
    while at[0]:
        if at[0] != 18 or at in metadata:
            raise ValueError('invalid or repeated ordinary directory sector')
        metadata.add(at)
        directory = block(at)
        for base in range(0, 256, 32):
            slot = directory[base:base + 32]
            if slot[2] & 15 and slot[5:21].rstrip(b'\xa0') == name:
                entries.append(slot)
        at = tuple(directory[:2])
    if not entries:
        raise ValueError('filename not found')
    if len(entries) != 1:
        raise ValueError('ambiguous filename')
    entry = entries[0]
    if entry[2] not in (0x84, 0xc4):
        raise ValueError('not a closed REL file')

    width = entry[23]
    side_ts = tuple(entry[21:23])
    pointers = []
    side_count = 0
    while True:
        if side_ts in metadata:
            raise ValueError('repeated side sector or overlap with directory or BAM')
        metadata.add(side_ts)
        side = block(side_ts)
        if side[2] != side_count:
            raise ValueError('invalid side-sector ordinal')
        if not 1 <= width <= 254 or side[3] != width:
            raise ValueError('invalid or inconsistent record length')
        if side_count == 0:
            if tuple(side[4:6]) != side_ts:
                raise ValueError('side-sector self pointer mismatch')
            # Build the expected six pairs from the directory start and actual link.
            peers = (bytes(side_ts) + (bytes(side[:2]) if side[0] else b'')).ljust(12, b'\0')
        elif side[0]:
            raise ValueError('more than two linked side sectors unsupported')
        if side[4:16] != peers:
            raise ValueError('inconsistent side-sector list or link for multiple side sectors')

        # A linked side uses all 120 pairs; only a terminal link encodes an extent.
        end = 255 if side[0] else side[1]
        if end < 17 or end % 2 != 1 or any(side[end + 1:]):
            raise ValueError('invalid side-sector pointer extent')
        pointers.extend(tuple(side[i:i + 2]) for i in range(16, end, 2))
        side_count += 1
        if not side[0]:
            break
        side_ts = tuple(side[:2])

    if int.from_bytes(entry[30:32], 'little') != side_count + len(pointers):
        raise ValueError('directory block count disagrees with side-sector pointer count')

    # Walk the actual links from the directory start, checking against the
    # index at every hop, including the terminator, before returning any data.
    at = tuple(entry[3:5])
    seen = set()
    for expected in pointers:
        if at != expected or not at[0]:
            raise ValueError('data chain disagrees with side-sector pointer order or count')
        if at in seen or at in metadata:
            raise ValueError('repeated or overlapping data sector')
        seen.add(at)
        at = tuple(block(at)[:2])
    if at[0] or not at[1]:
        raise ValueError('missing or invalid terminal data count')
    size = 254 * (len(pointers) - 1) + at[1] - 1
    count, remainder = divmod(size, width)
    if remainder:
        raise ValueError('terminal data length leaves a partial record')
    if not 1 <= number <= count:
        raise ValueError(f'record {number} outside 1 through {count}')

    index, skip = divmod((number - 1) * width, 254)
    data = bytearray()
    spans = []
    while len(data) < width:
        t, s = pointers[index]
        offset = 2 + skip
        start = sector_offset((t, s)) + offset
        length = min(width - len(data), 256 - offset)
        spans.append(dict(track=t, sector=s, sector_offset=offset,
                          image_offset=start, record_offset=len(data), length=length))
        data.extend(image[start:start + length])
        index, skip = index + 1, 0
    return dict(filename_hex=name.hex(), record=number, count=count,
                record_length=width, hex=data.hex(), spans=spans)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('image', type=Path)
    parser.add_argument('filename', help='exact ASCII filename, or raw hex with --hex-name')
    parser.add_argument('number', type=int, help='one-based record number')
    parser.add_argument('--hex-name', action='store_true')
    args = parser.parse_args()
    try:
        name = bytes.fromhex(args.filename) if args.hex_name else args.filename.encode('ascii')
        with args.image.open('rb') as stream:
            result = lookup(stream.read(IMAGE_SIZE + 1), name, args.number)
    except (OSError, ValueError) as error:
        parser.exit(1, f'{error}\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
