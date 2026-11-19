#!/usr/bin/env python3
"""Convert one continuous VICE 3.10 single-SID dump excerpt to canonical register CSV.

Zero time is the first included write.  Preserve the original dump separately.
The dump cannot attest to its machine, clock, device count, or continuity.
"""
import argparse
import csv
from pathlib import Path
import re
import sys


def decode(lines):
    tick = 0
    seen = False
    for n, line in enumerate(lines, 1):
        if not re.fullmatch(r'[0-9]+ [0-9]+ [0-9]+', line.rstrip('\r\n')):
            raise ValueError(f'line {n}: expected three unsigned decimal fields')
        dt, offset, value = map(int, line.split())
        if dt > 2147483647 or not 0 <= offset <= 24 or value > 255:
            raise ValueError(f'line {n}: outside 32-bit signed delta, SID write register 0..24, or byte range')
        if seen:
            tick += dt
        seen = True
        yield tick, 0xd400 + offset, value
    if not seen:
        raise ValueError('empty excerpt')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('dump', type=Path)
    args = p.parse_args()
    try:
        with args.dump.open(encoding='ascii') as src:
            rows = list(decode(src))  # bounded excerpts; validate before emitting CSV
    except (OSError, ValueError) as exc:
        p.exit(1, f'{p.prog}: {exc}\n')
    writer = csv.writer(sys.stdout, lineterminator='\n')
    writer.writerow(('tick', 'address', 'value'))
    writer.writerows(rows)


if __name__ == '__main__':
    main()
