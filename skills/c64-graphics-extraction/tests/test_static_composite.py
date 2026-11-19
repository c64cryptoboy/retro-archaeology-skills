"""Original synthetic decoded planes; no capture, ROM, or emulator required."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from static_composite import static_composite


def layer(slot, x, y, *, width=24, height=21, behind=False, enabled=True):
    return {'slot': slot, 'width': width, 'height': height,
            'expanded_pixels': bytearray([255]) * (width * height),
            'metadata': {'x': x, 'y': y, 'enabled': enabled,
                         'priority': 'behind_background' if behind else 'in_front'}}


class StaticCompositeTests(unittest.TestCase):
    def setUp(self):
        self.bg = {'pixels': bytes([6]) * 64000, 'priority': bytearray(8000)}

    def test_sprite_arbitration_precedes_foreground(self):
        # At y=1, mark x=7 and x=9 foreground.  Background color stays 6 everywhere.
        self.bg['priority'][40:42] = b'\x01\x40'
        a, b = layer(2, 17, 9, behind=True), layer(6, 17, 9)
        a['expanded_pixels'][:5] = bytes([0, 0, 255, 255, 4])
        b['expanded_pixels'][:5] = bytes([2, 2, 2, 255, 2])
        disabled = layer(0, 17, 9, enabled=False)
        disabled['expanded_pixels'][:5] = bytes([1]) * 5
        expected = bytearray(self.bg['pixels'])
        # Hidden winner, opaque black, transparent winner lets b through, hole, winner.
        expected[327:332] = bytes([6, 0, 2, 6, 4])
        for sprites in ([a, b, disabled], [disabled, b, a]):
            with self.subTest(order=[s['slot'] for s in sprites]):
                self.assertEqual(static_composite(self.bg, sprites, offset_x=-10, offset_y=-8), expected)
        self.assertEqual(self.bg['pixels'], bytes([6]) * 64000)

    def test_clips_expanded_planes_at_both_corners(self):
        # Upper-left plane ends in a 2 x 2 expanded dot; only its last copy survives.
        ul = layer(5, 0, 0, width=48, height=42)
        for row in (40, 41):
            ul['expanded_pixels'][row*48 + 46:row*48 + 48] = b'\x03\x03'
        # Lower-right starts at (318,199) after registration, with a doubled black dot.
        lr = layer(7, 365, 240, width=48, height=42)
        for row in (0, 1):
            lr['expanded_pixels'][row*48:row*48 + 4] = b'\0\0\x04\x04'
        expected = bytearray(self.bg['pixels'])
        expected[0], expected[-2:] = 3, b'\0\0'
        self.assertEqual(static_composite(self.bg, [ul, lr], offset_x=-47, offset_y=-41), expected)

    def test_no_coordinate_wrap(self):
        for x, y in ((511, 0), (0, 255)):
            s = layer(1, x, y)
            s['expanded_pixels'][0] = 2
            self.assertEqual(static_composite(self.bg, [s], offset_x=1, offset_y=1), self.bg['pixels'])

    def test_no_silent_registration_or_ambiguous_slots(self):
        with self.assertRaises(TypeError):
            static_composite(self.bg, [])
        for dx, dy in ((0.5, 0), (0, False)):
            with self.assertRaisesRegex(ValueError, 'integers'):
                static_composite(self.bg, [], offset_x=dx, offset_y=dy)
        s = layer(3, 0, 0)
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            static_composite(self.bg, [s, s], offset_x=0, offset_y=0)
        self.assertEqual(static_composite(self.bg, [], offset_x=0, offset_y=0), self.bg['pixels'])


if __name__ == '__main__':
    unittest.main()
