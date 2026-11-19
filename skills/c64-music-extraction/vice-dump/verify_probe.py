#!/usr/bin/env python3
"""Check a normalized CSV for the seven stores in probe.s, not an arbitrary tune."""
import csv
import sys


# Count from the first STA.  For the sixth store: 2 + 64*2 + 63*3 + 2 + 4 = 325.
EXPECTED = [(0, 0xd404, 0x20), (6, 0xd400, 0x34), (12, 0xd401, 0x12),
            (18, 0xd404, 0x21), (22, 0xd404, 0x21), (347, 0xd404, 0x21),
            (353, 0xd404, 0x20)]


def check(rows):
    if len(rows) != len(EXPECTED):
        raise ValueError(f'expected 7 writes, found {len(rows)}')
    for n, (got, want) in enumerate(zip(rows, EXPECTED), 1):
        if got != want:
            raise ValueError(f'write {n}: got {got}, expected {want}')


if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit('usage: verify_probe.py probe.csv')
    try:
        with open(sys.argv[1], newline='', encoding='ascii') as src:
            reader = csv.DictReader(src)
            check([tuple(int(row[k], 0) for k in ('tick', 'address', 'value')) for row in reader])
    except (OSError, ValueError, KeyError) as exc:
        sys.exit(str(exc))
    print('PASS: seven ordered, cycle-spaced SID register writes')
