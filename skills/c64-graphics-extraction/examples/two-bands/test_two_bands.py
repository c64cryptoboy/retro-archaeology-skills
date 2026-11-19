import unittest

from fixture import BACKGROUND, PLACEMENT, layers
from two_bands import replay


class TwoBands(unittest.TestCase):
    def test_shapes_and_gap(self):
        plane = replay(BACKGROUND, *layers(), **PLACEMENT)
        self.assertEqual(len(plane), 64000)
        self.assertEqual(plane[:320 * 100].count(7), 264)
        self.assertEqual(plane[320 * 100:].count(2), 208)
        self.assertEqual(plane.count(0), 64000 - 264 - 208)
        self.assertFalse(any(plane[320 * 56:320 * 130]))

    def test_wrong_order_and_cut(self):
        upper, lower = layers()
        with self.assertRaisesRegex(ValueError, "fit wholly"):
            replay(BACKGROUND, lower, upper, **PLACEMENT)
        with self.assertRaisesRegex(ValueError, "fit wholly"):
            replay(BACKGROUND, upper, lower, **dict(PLACEMENT, first_lower_row=45))
