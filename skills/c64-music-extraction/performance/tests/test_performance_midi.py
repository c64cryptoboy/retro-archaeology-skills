import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
from performance_midi import write_performance_midi
from read_performance_smf import parse_smf


# Independently scored in SMF ticks.  Each span has one attack, one release,
# and an ordered list of held wheel settings (absolute tick, 14-bit value).
SCORE = {
    1: [(0, 1500, 72, [(0,8192), (500,10240), (1250,8192)]),
        (1500, 2000, 72, [(1500,8192)]),
        (2250, 3500, 76, [(2250,8192), (3000,7168)]),
        (4000, 5000, 74, [(4000,8192)]),
        (5000, 7000, 72, [(5000,8192), (5500,12288), (6000,10240), (6500,8192)])],
    2: [(0, 2000, 57, [(0,8192), (1000,6144), (1750,8192)]),
        (2000, 3500, 53, [(2000,8192)]), (4000, 4800, 55, [(4000,8192)]),
        (5000, 7000, 60, [(5000,8192)])]}


def assert_song(case, data):
    division, events = parse_smf(data)
    case.assertEqual(division, 1000)
    case.assertEqual([e for e in events if e[1] == 'meta'], [
        (0, 'meta', 0x51, bytes.fromhex('07 a1 20')),
        (250, 'meta', 6, b'noise:on'), (375, 'meta', 6, b'noise:off'),
        (3750, 'meta', 6, b'noise:on'), (3875, 'meta', 6, b'noise:off'),
        (8000, 'meta', 47, b'')])
    case.assertEqual(events[-1], (8000, 'meta', 47, b''))
    midi = [e for e in events if e[1] != 'meta']
    case.assertEqual({e[2] for e in midi}, {1, 2, 10})
    case.assertEqual([e for e in midi if e[2] == 10], [
        (250, 'on', 10, 42, 80), (375, 'off', 10, 42, 0)])
    for ch, notes in SCORE.items():
        expected = [(0, 'cc', ch, cc, val) for cc, val in
                    [(101,0), (100,0), (6,2), (38,0), (101,127), (100,127)]]
        for start, end, key, contour in notes:
            expected += [(start, 'bend', ch, contour[0][1]), (start, 'on', ch, key, 80)]
            expected.extend((t, 'bend', ch, val) for t, val in contour[1:])
            expected.append((end, 'off', ch, key, 0))
        case.assertEqual([e for e in midi if e[2] == ch], expected)


class PerformanceTests(unittest.TestCase):
    def setUp(self):
        self.ledger = json.loads((HERE.parent/'examples/lantern-relay.json').read_text())
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name)/'song.mid'

    def render(self):
        write_performance_midi(self.ledger, self.path)
        return self.path.read_bytes()

    def test_score(self):
        assert_song(self, self.render())

    def test_missing_held_pitch_fails_score_even_with_same_attacks(self):
        del self.ledger['voices'][0]['notes'][0]['curve'][1]
        data = self.render()
        with self.assertRaises(AssertionError):
            assert_song(self, data)

    def test_raw_range_and_rails(self):
        self.ledger['bend_range'] = 4
        self.ledger['voices'][0]['notes'][0]['curve'][1]['pitch'] = 76
        self.ledger['voices'][1]['notes'][0]['curve'][1]['pitch'] = 53
        _, events = parse_smf(self.render())
        self.assertIn((0, 'cc', 1, 6, 4), events)
        self.assertIn((0, 'cc', 2, 6, 4), events)
        self.assertIn((500, 'bend', 1, 16383), events)
        self.assertIn((1000, 'bend', 2, 0), events)

    def test_reject_ambiguous_bends_or_lost_transitions(self):
        for channel in [1, 10]:
            self.ledger['voices'][1]['channel'] = channel
            with self.assertRaisesRegex(ValueError, 'own channel'):
                self.render()
        self.ledger['voices'][1]['channel'] = 2
        curve = self.ledger['voices'][0]['notes'][0]['curve']
        curve[1]['us'] = 200
        with self.assertRaisesRegex(ValueError, 'distinct ticks'):
            self.render()
        curve[1]['us'], curve[1]['pitch'] = 250000, 75
        with self.assertRaisesRegex(ValueError, 'outside bend range'):
            self.render()
        self.assertFalse(self.path.exists())

    def test_absolute_rounding_not_rounded_durations(self):
        note = self.ledger['voices'][0]['notes'][0]
        note.update(start_us=249, end_us=1250, curve=[{'us':249,'pitch':72}, {'us':749,'pitch':73}])
        _, events = parse_smf(self.render())
        self.assertIn((0, 'on', 1, 72, 80), events)
        self.assertIn((1, 'bend', 1, 12288), events)
        self.assertIn((3, 'off', 1, 72, 0), events)


if __name__ == '__main__':
    unittest.main()
