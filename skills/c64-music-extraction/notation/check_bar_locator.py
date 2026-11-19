"""Check the locator against hand-counted rows.  Argument: notation/fixture directory."""
import argparse
import csv
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from bar_locator import locate


check = TestCase()


def records(gates, plan, bar=None):
    result = StringIO()
    locate(gates, plan, result, bar)
    return list(csv.DictReader(StringIO(result.getvalue())))


def columns(rows, names):
    return [tuple(row[k] for k in names.split()) for row in rows]


def addresses(rows):
    return [tuple(map(int, item)) for item in columns(rows,
            'source_gate start_bar start_offset_32nds end_bar end_offset_32nds start_tick end_tick')]


def segments(rows):
    return [(int(i), kind, int(lo), int(hi)) for i, kind, lo, hi in columns(rows,
            'source_gate kind from_offset_32nds until_offset_32nds')]


def authored(fixture):
    gates, plan = fixture/'engraved'/'gates.csv', fixture/'plan.json'
    full = records(gates, plan)
    check.assertEqual(addresses(full), [
        (1, 1, 0, 1, 8, 0, 480), (2, 1, 8, 1, 16, 480, 960),
        (3, 1, 24, 2, 8, 1441, 2401), (4, 2, 12, 2, 20, 2640, 3120),
        (5, 1, 4, 1, 20, 240, 1200), (6, 2, 4, 2, 16, 2160, 2880)])
    check.assertEqual(columns(full[:2], 'track key'), [('Reed', '60'), ('Reed', '60')])
    second = records(gates, plan, 2)
    check.assertEqual(segments(second), [(3, 'carry-in', 0, 8), (6, 'attack', 4, 16), (4, 'attack', 12, 20)])
    with gates.open(encoding='utf-8', newline='') as f:
        source = list(csv.DictReader(f))
    for row in full + second:
        original = source[int(row['source_gate']) - 1]
        check.assertEqual({k: row[k] for k in original}, original)


def irregular(folder):
    gates, plan = folder/'gates.csv', folder/'plan.json'
    plan.write_text('{"bars_32nds": [3, 5, 2]}')  # bar starts: 0, 3, 8; final edge: 10
    header = 'track,key,start_tick,end_tick,start_32nd,end_32nd\n'
    gates.write_text(header + 'Pulse,60,11,30,1,3\nPulse,60,30,79,3,8\nDrone,48,22,101,2,10\n')
    check.assertEqual(addresses(records(gates, plan)), [
        (1, 1, 1, 1, 3, 11, 30), (2, 2, 0, 2, 5, 30, 79), (3, 1, 2, 3, 2, 22, 101)])
    check.assertEqual(segments(records(gates, plan, 1)), [(1, 'attack', 1, 3), (3, 'attack', 2, 3)])
    check.assertEqual(segments(records(gates, plan, 2)), [(2, 'attack', 0, 5), (3, 'carry-in', 0, 5)])
    check.assertEqual(segments(records(gates, plan, 3)), [(3, 'carry-in', 0, 2)])
    for bar in [0, 4]:
        with check.assertRaisesRegex(ValueError, 'bar must be'):
            records(gates, plan, bar)
    # Change just the drone's endpoints to finish exactly at bar 3's left edge.
    gates.write_text(header + 'Drone,48,22,79,2,8\n')
    check.assertEqual(records(gates, plan, 3), [])
    for invalid in ['2,11', '3,3', '-1,3']:
        gates.write_text(header + f'Drone,48,22,101,{invalid}\n')
        with check.assertRaisesRegex(ValueError, 'gate 1: invalid'):
            records(gates, plan)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('fixture', type=Path)
    authored(p.parse_args().fixture)
    with TemporaryDirectory() as temp:
        irregular(Path(temp))
    print('PASS: authored addresses and source identity; unequal bars, reattacks, carries, final edge, and refusals')
