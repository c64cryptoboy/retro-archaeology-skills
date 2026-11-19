"""Locate existing engraved gates on the supplied written grid; emit CSV to stdout."""
import argparse
from bisect import bisect_right
import csv
from itertools import accumulate
import json
from pathlib import Path
import sys


ADDRESS = ['source_gate', 'start_bar', 'start_offset_32nds', 'end_bar', 'end_offset_32nds']
VIEW = ['bar', 'kind', 'from_offset_32nds', 'until_offset_32nds']


def locate(gates, plan, out, bar=None):
    bars = json.loads(plan.read_text(encoding='utf-8'))['bars_32nds']
    if not isinstance(bars, list) or not bars or any(type(n) is not int or n < 1 for n in bars):
        raise ValueError('bars_32nds must be a nonempty list of positive integers')
    edges = [0, *accumulate(bars)]
    if bar is not None and not 1 <= bar <= len(bars):
        raise ValueError(f'bar must be 1 through {len(bars)}')

    rows = []
    with gates.open(encoding='utf-8', newline='') as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames or []
        required = {'track', 'key', 'start_tick', 'end_tick', 'start_32nd', 'end_32nd'}
        if not required.issubset(fields) or (set(ADDRESS + VIEW) & set(fields)):
            raise ValueError('expected engraver gates.csv columns (not a locator output)')
        for gate, row in enumerate(reader, 1):
            a, b = int(row['start_32nd']), int(row['end_32nd'])
            if not 0 <= a < b <= edges[-1] or not 0 <= int(row['start_tick']) < int(row['end_tick']):
                raise ValueError(f'gate {gate}: invalid written or performance interval')
            # Locate the last occupied unit, then report its exclusive right edge.
            first, last = bisect_right(edges, a), bisect_right(edges, b - 1)
            row.update(source_gate=gate, start_bar=first, start_offset_32nds=a-edges[first-1],
                       end_bar=last, end_offset_32nds=b-edges[last-1])
            if bar is not None:
                if not first <= bar <= last:
                    continue
                lo, hi = edges[bar-1], edges[bar]
                row.update(bar=bar, kind='carry-in' if a < lo else 'attack',
                           from_offset_32nds=max(a, lo)-lo, until_offset_32nds=min(b, hi)-lo)
            rows.append(row)
    if bar is not None:
        rows.sort(key=lambda r: r['from_offset_32nds'])  # source order breaks ties
    writer = csv.DictWriter(out, (VIEW if bar is not None else []) + ADDRESS + fields, lineterminator='\n')
    writer.writeheader()
    writer.writerows(rows)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('gates', type=Path)
    p.add_argument('plan', type=Path)
    p.add_argument('--bar', type=int, help='one-based bar; include tied carry-ins as well as attacks')
    args = p.parse_args()
    try:
        locate(args.gates, args.plan, sys.stdout, args.bar)
    except (OSError, ValueError, KeyError) as exc:
        p.exit(2, f'{p.prog}: {exc}\n')
