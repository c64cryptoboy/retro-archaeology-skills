"""Synthetic single-snapshot sprite examples; no title or ROM assets required."""

import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sprites import decode_sprites


class SampleState:
    def __init__(self, bank=0xC000, screen=0xC800):
        self.bank = bank
        self.screen = screen
        self.vic = bytearray(64)
        self.ram = bytearray(65536)
        self.color = None

    def fetch(self, address, length):
        return bytes(self.ram[address:address + length])


class SpriteTests(unittest.TestCase):
    def test_hires_black_and_transparent_through_last_row_but_not_pad(self):
        s = SampleState()
        s.ram[0xCBF8] = 0xFF
        block = b'\x81\x40\x01' + bytes(59) + b'\x01\xff'
        s.ram[0xFFC0:] = block
        s.vic[0x15] = 1
        s.vic[0x27] = 0xF0  # Opaque black, not transparency.
        layers = decode_sprites(s)
        self.assertEqual([layer['slot'] for layer in layers], list(range(8)))
        layer = layers[0]
        expected = bytearray([255]) * 504
        for index in (0, 7, 9, 23, 503):
            expected[index] = 0
        self.assertEqual(layer['address'], 0xFFC0)
        self.assertEqual(layer['block'], block)
        self.assertEqual(layer['pixels'], bytes(expected))
        self.assertEqual(layer['expanded_pixels'], bytes(expected))
        self.assertEqual((layer['width'], layer['height']), (24, 21))

    def test_shared_block_keeps_separate_modes_colors_positions_and_enable(self):
        s = SampleState()
        for pointer in (0xCBF9, 0xCBFC, 0xCBFF):
            s.ram[pointer] = 8
        block = b'\x1b' + bytes(62) + b'\xa5'
        s.ram[0xC200:0xC240] = block
        s.vic[0x15] = 0x82  # Enable 1 and 7, but not 4.
        s.vic[0x10] = s.vic[0x1B] = s.vic[0x1C] = s.vic[0x1D] = 0x80
        s.vic[0x17] = 0x12  # Vertical expansion only for slots 1 and 4.
        s.vic[0x02:0x04] = bytes([201, 99])
        s.vic[0x0E:0x10] = bytes([171, 243])
        s.vic[0x25:0x27] = bytes([0xF3, 0xA0])
        s.vic[0x28], s.vic[0x2E] = 0xA5, 0xB7

        mc, hi, off = decode_sprites(s, (7, 1, 4))
        t = b'\xff'
        mc_row = bytes([255, 255, 3, 3, 7, 7, 0, 0]) + t * 16
        hi_row = bytes([255, 255, 255, 5, 5, 255, 5, 5]) + t * 16
        self.assertEqual(mc['pixels'], mc_row + t * 480)
        self.assertEqual(hi['pixels'], hi_row + t * 480)
        self.assertEqual(off['pixels'], t * 504)
        self.assertEqual(mc['expanded_pixels'], t * 4 + b'\x03' * 4 + b'\x07' * 4
                         + b'\x00' * 4 + t * 992)
        self.assertEqual(hi['expanded_pixels'], hi_row * 2 + t * 960)
        self.assertEqual(off['expanded_pixels'], t * 1008)
        for layer, slot, width, height in ((mc, 7, 48, 21), (hi, 1, 24, 42), (off, 4, 24, 42)):
            self.assertEqual((layer['slot'], layer['width'], layer['height']), (slot, width, height))
            self.assertEqual(layer['block'], block)
            self.assertEqual(layer['address'], 0xC200)
            json.dumps(layer['metadata'])
        a, b = mc['metadata'], hi['metadata']
        self.assertEqual((a['mode'], a['x'], a['y'], a['priority']),
                         ('multicolor', 427, 243, 'behind_background'))
        self.assertEqual((b['mode'], b['x'], b['y'], b['priority']), ('hires', 201, 99, 'in_front'))
        self.assertEqual((a['expand_x'], a['expand_y']), (True, False))
        self.assertEqual(a['colors'], {'own': 7, 'shared_0': 3, 'shared_1': 0})
        self.assertTrue(a['enabled'])
        self.assertFalse(off['metadata']['enabled'])

    def test_pointer_follows_screen_and_uses_vic_view_for_pointer_and_block(self):
        s = SampleState(bank=0, screen=0x1400)
        # Synthetic VIC overlay differs from physical RAM at both fetch locations.
        visible = bytearray(s.ram)
        visible[0x17FE], visible[0x1BFE] = 0x42, 0x64
        visible[0x1080], visible[0x1900] = 0x80, 0x40
        s.fetch = lambda address, length: bytes(visible[address:address + length])
        s.vic[0x15] = 0x40
        for screen, ptr_addr, ptr, addr, dot in ((0x1400, 0x17FE, 0x42, 0x1080, 0),
                                                  (0x1800, 0x1BFE, 0x64, 0x1900, 1)):
            with self.subTest(screen=screen):
                s.screen = screen
                layer, = decode_sprites(s, [6])
                meta = layer['metadata']
                self.assertEqual((meta['pointer_address'], meta['pointer_value']), (ptr_addr, ptr))
                self.assertEqual(layer['address'], addr)
                self.assertEqual(meta['provenance']['screen_base'], screen)
                self.assertEqual(layer['pixels'][:2], (b'\x00\xff', b'\xff\x00')[dot])

    def test_unknown_block_not_replaced_by_ram_even_if_disabled(self):
        s = SampleState(bank=0, screen=0x0400)
        s.ram[0x07FA] = 0x40
        fetch = s.fetch

        def missing_rom(address, length):
            if address == 0x1000:
                raise ValueError('unknown character ROM')
            return fetch(address, length)

        s.fetch = missing_rom
        with self.assertRaisesRegex(ValueError, 'unknown character ROM'):
            decode_sprites(s, [2])


if __name__ == '__main__':
    unittest.main()
