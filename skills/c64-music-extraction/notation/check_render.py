"""Verify the actual engraver's note gates against a separately prepared grid oracle."""
import argparse
import csv
from fractions import Fraction
from pathlib import Path
import mido


def verify(rendered, expected_csv, units):
    with open(expected_csv, newline='') as f:
        expected = sorted(tuple(int(r[k]) for k in ('staff','start_32nd','end_32nd','key'))
                          for r in csv.DictReader(f))
    m = mido.MidiFile(rendered)
    actual = []
    ends = []
    staff = 0
    for tr in m.tracks:
        tick = 0
        starts = {}
        notes = []
        for msg in tr:
            tick += msg.time
            if msg.type not in ('note_on', 'note_off'):
                continue
            pos = Fraction(8*tick, m.ticks_per_beat)
            if pos.denominator != 1:
                raise ValueError(f'non-grid rendered tick {tick}')
            pos = int(pos)
            key = (msg.channel, msg.note)
            if msg.type == 'note_on' and msg.velocity:
                if key in starts:
                    raise ValueError('rendered gate overlaps itself')
                starts[key] = pos
            else:
                notes.append((starts.pop(key), pos, msg.note))
        if starts:
            raise ValueError('missing rendered release')
        if notes:
            staff += 1
            actual.extend((staff, a,b,k) for a,b,k in notes)
        ends.append(Fraction(8*tick, m.ticks_per_beat))
    actual.sort()
    for e,a in zip(expected, actual):
        if a != e:
            raise ValueError(f'gate mismatch (staff, start, end, key): expected {e}, rendered {a}')
    if len(actual) != len(expected) or set(ends) != {units}:
        raise ValueError(f'wrong gate count ({len(actual)}) or end units ({ends})')
    repeats = sum(a[0]==b[0] and a[2]==b[1] and a[3]==b[3] for a,b in zip(actual,actual[1:]))
    print(f'PASS: {len(actual)} rendered gates across {staff} staves, {repeats} adjacent same-key reattacks, all tracks end at unit {units}')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('engraver_midi', type=Path)
    p.add_argument('expected_csv', type=Path)
    p.add_argument('end_32nd', type=int)
    a=p.parse_args()
    verify(a.engraver_midi, a.expected_csv, a.end_32nd)
