"""One authored, data-only C64 bitmap example.  This is not an emulator."""

import unittest


# Fixture coordinates and bytes are literal observations, not derived by the decoder.
PRG = bytearray(b"\x00\xe0") + bytearray(8000)
PRG[0x02AD] = 0x8D
# Explicit fixture assumption: the whole payload was placed in underlying RAM unchanged.
LOAD = int.from_bytes(PRG[:2], "little")
RAM = dict(enumerate(PRG[2:], LOAD))
RAM[0xC455] = 0xA4
COLOR = {0x055: 0x0E}  # Separate 4-bit store, indexed by the matrix counter.


def locate(x, y, cia_pins, d018):
    """Ordinary, unscrolled bitmap coordinates in single-dot units."""
    bank = ((~cia_pins) & 3) << 14
    cell = (y // 8) * 40 + x // 8
    bitmap = bank + ((d018 & 8) << 10)
    matrix = bank + ((d018 >> 4) << 10)
    return bitmap + cell * 8 + y % 8, matrix + cell, cell


def eight_dots(data, matrix, color, background, d016):
    # D011 is fixed at $3B in this fixture (bitmap enabled, ECM clear).
    if d016 & 0x10:
        ink = (background, matrix >> 4, matrix & 15, color)
        return tuple(ink[(data >> shift) & 3] for shift in (6, 4, 2, 0) for _ in range(2))
    return tuple((matrix >> 4 if data & (1 << bit) else matrix & 15) for bit in range(7, -1, -1))


class BitmapExample(unittest.TestCase):
    def test_three_address_spaces(self):
        addr, matrix, cell = locate(40, 19, 0, 0x18)
        self.assertEqual((addr, matrix, cell), (0xE2AB, 0xC455, 0x55))
        self.assertEqual((LOAD, addr - LOAD + 2), (0xE000, 0x02AD))
        self.assertEqual((RAM[addr], RAM[matrix], COLOR[cell]), (0x8D, 0xA4, 14))
        # Omitting the header or indexing the bitmap as linear scanlines loses the mark.
        self.assertEqual((PRG[addr - LOAD], PRG[2 + 40 * 19 + 5]), (0, 0))

    def test_same_byte_two_modes(self):
        addr, matrix, cell = locate(40, 19, 0, 0x18)
        inputs = (RAM[addr], RAM[matrix], COLOR[cell], 6)
        self.assertEqual(eight_dots(*inputs, 0x18), (4, 4, 6, 6, 14, 14, 10, 10))
        self.assertEqual(eight_dots(*inputs, 0x08), (10, 4, 4, 4, 10, 10, 4, 10))

    def test_same_file_different_vic_bank(self):
        addr, _, _ = locate(40, 19, 2, 0x18)
        self.assertEqual(addr, 0x62AB)
        self.assertNotIn(addr, RAM)  # No evidence there; do not substitute E2AB or zero.


if __name__ == "__main__":
    unittest.main()
