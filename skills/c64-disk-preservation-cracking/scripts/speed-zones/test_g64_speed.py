"""Independent synthetic file layout and expected spans, not writer round trips."""
import unittest

from g64_speed import describe_slot


# One slot, max length 5, track at 20, packed map at 27.  Arbitrary GCR bytes.
PREFIX = bytes.fromhex("47 43 52 2d 31 35 34 31 00 01 05 00 "
                       "14 00 00 00 1b 00 00 00 05 00 11 22 33 44 55")


class SpeedTests(unittest.TestCase):
    def test_field_order_and_final_padding(self):
        # 00|01|10|11, 11|xx|xx|xx.  The last run spans two map bytes.
        for last in (0xe4, 0xff):
            with self.subTest(last=last):
                result = describe_slot(PREFIX + bytes([0x1b, last]), 0)
                self.assertEqual(result["kind"], "packed")
                self.assertEqual(result["runs"], [[0, 1, 0], [1, 2, 1],
                                                  [2, 3, 2], [3, 5, 3]])

    def test_truncated_map(self):
        with self.assertRaisesRegex(ValueError, "truncated speed map at 27: need 2 bytes, have 1"):
            describe_slot(PREFIX + b"\x1b", 0)

    def test_constant_zone_zero_is_not_a_missing_map(self):
        result = describe_slot(PREFIX[:16] + bytes(4) + PREFIX[20:], 0)
        self.assertEqual((result["kind"], result["runs"]), ("constant", [[0, 5, 0]]))


if __name__ == "__main__":
    unittest.main()
