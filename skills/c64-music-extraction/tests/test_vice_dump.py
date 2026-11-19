import sys
import unittest
from pathlib import Path

EXAMPLE = Path(__file__).resolve().parents[1] / 'vice-dump'
sys.path.insert(0, str(EXAMPLE))
from dump_to_csv import decode
from verify_probe import check


class ViceDump(unittest.TestCase):
    def test_real_probe_and_wrong_spacing(self):
        lines = (EXAMPLE / 'program.dump').read_text().splitlines()
        events = list(decode(lines))
        check(events)
        i, a, v = events[5]
        self.assertEqual((i - events[4][0], a, v), (325, 0xd404, 0x21))
        events[5] = (i - 256, a, v)
        with self.assertRaises(ValueError):
            check(events)

    def test_equal_tick_and_unsupported_offset(self):
        self.assertEqual(list(decode(['91 4 3', '0 4 3'])), [(0, 0xd404, 3)] * 2)
        for bad in ('1 25 0', '-1 0 0', '2147483648 0 0', '1 0 256'):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                list(decode([bad]))
