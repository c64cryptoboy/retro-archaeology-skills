import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from compare_animation import compare


# An indicator's three coloured lamps change without the housing or its black
# foot moving.  The opposite view is independently transcribed in display order.
def indicator(colors):
    return bytes([255, *colors, 255, 255, 255, 0, 255, 255])


A, B, C = map(indicator, [(1, 2, 3), (2, 3, 1), (3, 1, 2)])
X, Y, Z = map(indicator, [(3, 2, 1), (1, 3, 2), (2, 1, 3)])


class CompareTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def export(self, name, schedule, loop=None, hz=(9, 2), size=(5, 2)):
        from fractions import Fraction
        path = self.root / name / 'manifest.json'
        path.parent.mkdir()
        frames = []
        for i, (plane, hold) in enumerate(schedule):
            filename = f'{i}.idx'
            (path.parent / filename).write_bytes(plane)
            d = Fraction(hold * hz[1], hz[0])
            frames.append(dict(hold=hold, indices=filename, sha256=hashlib.sha256(plane).hexdigest(),
                               seconds=[d.numerator, d.denominator]))
        m = dict(format='c64-animation-export-v1', transparent=255, size=size, frames=frames,
                 origin=[0, 0], movie_repeat=False, clock=dict(hz_num=hz[0], hz_den=hz[1]),
                 source_loop=loop or [0, len(frames)])
        path.write_text(json.dumps(m))
        return path

    def test_registered_clock_and_phase(self):
        left = self.export('a', [(C, 50), (A, 4), (B, 2), (C, 6)], [1, 4])
        right = self.export('b', [(Z, 6), (X, 3), (X, 5), (Y, 4), (Z, 6), (A, 1)], [0, 5], (9, 1))
        self.assertEqual(compare(left, right)['status'], 'different')
        r = compare(left, right, reflect_x=True)
        self.assertEqual(r['loop_seconds'], '8/3')
        self.assertEqual(r['right_phase_seconds'], {'identity': [], 'reflect_x': ['2/3']})
        self.assertEqual(compare(right, left, reflect_x=True)['right_phase_seconds']['reflect_x'], ['2'])

    def test_silhouette_trap_and_controls(self):
        self.assertEqual(len({tuple(c != 255 for c in p) for p in (A, B, C, X, Y, Z)}), 1)
        left = self.export('a', [(A, 4), (B, 2), (C, 6)])
        for name, schedule in [('colour', [(X, 4), (Y, 2), (X, 6)]),
                               ('reverse', [(Z, 6), (Y, 2), (X, 4)]),
                               ('timing', [(X, 4), (Y, 3), (Z, 5)])]:
            right = self.export(name, schedule)
            self.assertEqual(compare(left, right, reflect_x=True)['status'], 'different', name)

    def test_ties_and_large_hold(self):
        red, blue = indicator([1, 3, 1]), indicator([2, 1, 2])
        n = 10**18
        p = self.export('twice', [(red, n), (blue, n)] * 2, hz=(1, 1))
        r = compare(p, p, reflect_x=True)['right_phase_seconds']
        self.assertEqual(r, {mode: ['0', str(2*n)] for mode in ('identity', 'reflect_x')})
        p = self.export('steady', [(red, n)])
        self.assertEqual(compare(p, p, reflect_x=True)['right_phase_seconds'],
                         {'identity': 'any', 'reflect_x': 'any'})

    def test_not_comparable_vs_different(self):
        p = self.export('a', [(A, 1)])
        q = self.export('long', [(A, 2)])
        self.assertEqual(compare(p, q)['reason'], 'declared loop durations differ')
        q = self.export('shape', [(A, 1)], size=(2, 5))
        self.assertEqual(compare(p, q)['status'], 'not_comparable')
        original = json.loads(p.read_text())
        for key, value in [('clock', None), ('source_loop', None), ('source_loop', [0, 2]), ('size', None)]:
            q.write_text(json.dumps({**original, key: value}))
            self.assertEqual(compare(p, q)['status'], 'not_comparable')
        (p.parent / '0.idx').write_bytes(B)
        self.assertIn('digest', compare(p, p)['reason'])


if __name__ == '__main__':
    unittest.main()
