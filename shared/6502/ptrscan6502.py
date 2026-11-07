#!/usr/bin/env python3
"""Find consecutive little-endian pointer-table candidates in a PRG.

Candidates are evidence only: tables can resemble data, and data can resemble tables.
"""
import argparse
from analysis6502 import load_prg, read_json, dump


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('prg'); p.add_argument('--min-run', type=int, default=3)
    p.add_argument('--cfg-json', help='cfg6502 --json output; ranks pointers to its decoded instructions')
    args = p.parse_args(); base, mem = load_prg(args.prg); end = base + len(mem)
    code = set()
    if args.cfg_json:
        code = {x['pc'] for x in read_json(args.cfg_json)['instructions']}
    candidates = []
    # Test every alignment; overlap is intentionally retained for human review.
    for start in range(len(mem) - args.min_run * 2 + 1):
        values = []
        while start + (len(values) + 1) * 2 <= len(mem):
            i = start + len(values) * 2
            value = mem[i] | mem[i + 1] << 8
            if not base <= value < end: break
            values.append(value)
        if len(values) >= args.min_run:
            hits = sum(value in code for value in values)
            candidates.append({'address': base + start, 'count': len(values), 'targets': values,
                               'codeTargetCount': hits,
                               'confidence': 'high' if code and hits == len(values) else 'candidate'})
    # Keep maximal runs only; shorter same-alignment suffixes add no evidence.
    maximal = [x for x in candidates if not any(y['address'] < x['address'] and
               y['address'] + y['count'] * 2 >= x['address'] + x['count'] * 2 for y in candidates)]
    dump({'loadAddress': base, 'candidates': maximal,
          'warning': 'Do not classify a region as a table solely from this scan.'})
if __name__ == '__main__': main()
