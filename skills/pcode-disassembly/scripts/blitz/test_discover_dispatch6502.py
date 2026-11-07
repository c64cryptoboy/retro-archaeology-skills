import unittest

from discover_dispatch6502 import discover


class DispatchDiscoveryTests(unittest.TestCase):
    def test_finds_split_dispatch(self):
        fixture = bytes.fromhex(
            "ea ea "
            "c9 0e 90 a3 bd 7a 08 85 55 bd 17 08 85 56 6c 55 00 "
            "ea"
        )
        found = discover(0x0E6E, fixture)
        self.assertEqual(len(found), 1)
        candidate = found[0]
        self.assertEqual(candidate["address"], 0x0E70)
        self.assertEqual(candidate["minimumDirectOpcode"], 0x0E)
        self.assertEqual(candidate["lowTable"], 0x087A)
        self.assertEqual(candidate["highTable"], 0x0817)
        self.assertEqual(candidate["dispatchPointerZeroPage"], 0x55)

    def test_rejects_nonconsecutive_pointer(self):
        fixture = bytes.fromhex(
            "c9 0e 90 a3 bd 7a 08 85 55 bd 17 08 85 57 6c 55 00"
        )
        self.assertEqual(discover(0x1000, fixture), [])


if __name__ == "__main__":
    unittest.main()
