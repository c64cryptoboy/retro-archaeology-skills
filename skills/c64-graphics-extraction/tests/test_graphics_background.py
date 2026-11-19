import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from background import decode_background


class Sample:
    """Keep VIC-visible bytes separate so accidental physical RAM reads fail the oracle."""

    def __init__(self):
        self.ram = bytes(65536)
        self.visible = bytearray(65536)
        self.bank = 0x4000
        self.screen = 0x4C00
        self.color = bytearray(1024)
        self.vic = bytearray(64)
        self.vic[0x18] = 0x3B  # Screen $4C00, charset $6800, or bitmap $6000.
        self.vic[0x21:0x25] = bytes([0xF2, 4, 6, 8])

    def fetch(self, address, length):
        return bytes(self.visible[address:address + length])


def row(result, x, y):
    start = 320 * y + x
    return list(result['pixels'][start:start + 8])


class GraphicsBackgroundTests(unittest.TestCase):
    def test_hires_text_stride_color_variants_and_frozen_geometry(self):
        s = Sample()
        s.vic[0x11], s.vic[0x16] = 3, 5  # DEN clear, both scroll offsets nonzero.
        for cell, color in ((0, 0xFD), (39, 13), (40, 7)):
            s.visible[s.screen + cell] = 0x83
            s.color[cell] = color
        glyph = 0x6800 + 8 * 0x83
        s.visible[glyph:glyph + 2] = b'\x81\x40'
        result = decode_background(s)
        self.assertEqual(result['mode'], 'hires-character')
        self.assertIsInstance(result['pixels'], bytes)
        self.assertEqual(len(result['pixels']), 320 * 200)
        self.assertEqual(row(result, 312, 0), [13, 2, 2, 2, 2, 2, 2, 13])
        self.assertEqual(row(result, 0, 8), [7, 2, 2, 2, 2, 2, 2, 7])
        self.assertEqual(row(result, 0, 9), [2, 7, 2, 2, 2, 2, 2, 2])
        variants = [v for v in result['variants'] if v['code'] == 0x83]
        self.assertEqual([v['cells'] for v in variants], [[0, 39], [40]])
        self.assertEqual(variants[1]['pixels'], bytes(row(result, 0, 8) + row(result, 0, 9) + [2] * 48))
        self.assertEqual(result['blocks'], {'screen': (0x4C00, s.fetch(0x4C00, 1000)),
                                            'charset': (0x6800, s.fetch(0x6800, 2048)),
                                            'color': (None, bytes(s.color[:1000]))})
        manifest = json.loads(json.dumps(result['manifest']))
        self.assertEqual((manifest['width'], manifest['height']), (320, 200))
        self.assertEqual((manifest['display_enabled'], manifest['x_scroll'], manifest['y_scroll']), (False, 5, 3))

    def test_one_bit_switch_to_mixed_multicolor_and_hires_text(self):
        s = Sample()
        s.visible[0x6800] = 0x1B  # Pairs 00, 01, 10, 11; individual bits 00011011.
        s.color[:2] = bytes([13, 5])
        before = decode_background(s)
        s.vic[0x16] ^= 0x10
        after = decode_background(s)
        self.assertEqual(after['mode'], 'multicolor-character')
        self.assertEqual(row(before, 0, 0), [2, 2, 2, 13, 13, 2, 13, 13])
        self.assertEqual(row(after, 0, 0), [2, 2, 4, 4, 6, 6, 5, 5])
        self.assertEqual(row(after, 8, 0), [2, 2, 2, 5, 5, 2, 5, 5])
        self.assertEqual([v['cells'] for v in after['variants'][:2]], [[0], [1]])

    def test_ecm_uses_six_bit_code_and_two_bit_background(self):
        s = Sample()
        s.vic[0x11] = 0x50
        s.visible[s.screen:s.screen + 4] = bytes([63, 127, 191, 255])
        s.visible[0x6800 + 511] = 1  # Last row of the last ECM glyph.
        s.color = bytes([11]) * 1000
        result = decode_background(s)
        self.assertEqual(result['mode'], 'extended-color-text')
        self.assertEqual(result['blocks']['charset'], (0x6800, bytes(511) + b'\x01'))
        for cell, bg in enumerate([2, 4, 6, 8]):
            self.assertEqual(row(result, 8 * cell, 7), [bg] * 7 + [11])
        variants = [v for v in result['variants'] if v['code'] == 63]
        self.assertEqual([v['cells'] for v in variants], [[0], [1], [2], [3]])

    def test_bitmap_last_cell_and_one_bit_palette_change(self):
        s = Sample()
        s.vic[0x11] = 0x30
        s.visible[s.screen + 999] = 0xA3
        s.visible[0x6000 + 7999] = 0x1B
        s.color = None
        hires = decode_background(s)
        self.assertEqual(hires['mode'], 'hires-bitmap')
        self.assertEqual(row(hires, 312, 199), [3, 3, 3, 10, 10, 3, 10, 10])
        self.assertEqual(hires['variants'], [])
        self.assertEqual(set(hires['blocks']), {'screen', 'bitmap'})
        self.assertEqual(hires['blocks']['bitmap'], (0x6000, bytes(7999) + b'\x1b'))
        s.color = bytes([0xF9]) * 1000
        s.vic[0x16] ^= 0x10
        multi = decode_background(s)
        self.assertEqual(multi['mode'], 'multicolor-bitmap')
        self.assertEqual(row(multi, 312, 199), [2, 2, 10, 10, 3, 3, 9, 9])
        self.assertEqual(multi['variants'], [])
        self.assertEqual(multi['blocks']['color'], (None, s.color))

    def test_illegal_modes_and_missing_color(self):
        s = Sample()
        for d011, d016 in ((0x40, 0x10), (0x60, 0), (0x60, 0x10)):
            with self.subTest(illegal=(d011, d016)):
                s.vic[0x11], s.vic[0x16] = d011, d016
                with self.assertRaisesRegex(ValueError, 'Illegal'):
                    decode_background(s)
        s.color = None
        for d011, d016 in ((0, 0), (0, 0x10), (0x40, 0), (0x20, 0x10)):
            with self.subTest(missing_color=(d011, d016)):
                s.vic[0x11], s.vic[0x16] = d011, d016
                with self.assertRaisesRegex(ValueError, 'Color RAM'):
                    decode_background(s)

    def test_unknown_vic_data_is_not_replaced_by_physical_ram(self):
        class UnknownCharset(Sample):
            def fetch(self, address, length):
                if address == 0x1000:
                    raise ValueError('unknown character ROM')
                return super().fetch(address, length)

        s = UnknownCharset()
        s.bank, s.screen, s.vic[0x18] = 0, 0x0400, 0x14
        with self.assertRaisesRegex(ValueError, 'unknown character ROM'):
            decode_background(s)


if __name__ == '__main__':
    unittest.main()
