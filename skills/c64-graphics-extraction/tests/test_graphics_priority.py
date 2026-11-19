"""Synthetic inputs only.  Run with unittest from any copy of the extractor."""
from hashlib import sha256
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from extract import State, decode, export


class PriorityTests(unittest.TestCase):
    def state(self, d011, d016, entry, ink):
        ram, vic, color = bytearray(65536), bytearray(64), bytearray(1000)
        vic[0x11], vic[0x16], vic[0x18] = d011, d016, 0x18  # $4400 matrix; $6000 patterns
        vic[0x21:0x25] = bytes([0, 1, 2, 6])
        ram[0x4400 + 999], color[999] = entry, ink
        pattern = 999 if d011 & 0x20 else (entry & 63 if d011 & 0x40 else entry)
        ram[0x6000 + pattern * 8 + 7] = 0x1B  # 00 01 10 11, last byte of last scanline
        return State(bytes(ram), bytes(vic), 2, bytes(color))

    def test_all_modes_and_hires_fallback(self):
        for name, d011, d016, entry, ink, packed, indices in [
            ('hires-character', 0, 0, 0xC5, 14, 0x1B, [0,0,0,14,14,0,14,14]),
            ('multicolor-character', 0, 16, 5, 14, 0x0F, [0,0,1,1,2,2,6,6]),
            ('multicolor-character', 0, 16, 5,  6, 0x1B, [0,0,0,6,6,0,6,6]),
            ('extended-color-text', 64, 0, 0xC5, 6, 0x1B, [6]*8),
            ('hires-bitmap', 32, 0, 0x66, 9, 0x1B, [6]*8),
            ('multicolor-bitmap', 32, 16, 0x66, 9, 0x0F, [0,0,6,6,6,6,9,9]),
        ]:
            with self.subTest(mode=name, ink=ink):
                bg = decode(self.state(d011, d016, entry, ink), 'background')['background']
                self.assertEqual(bg['mode'], name)
                self.assertEqual(bg['priority'], bytes(7999) + bytes([packed]))
                self.assertEqual(bg['pixels'][-8:], bytes(indices))

    def test_export_matches_manifest_and_preserves_color_indices(self):
        state = self.state(32, 16, 0x66, 9)
        scene = decode(state, 'background')
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'art'
            export(state, scene, out)
            bg = json.loads((out / 'manifest.json').read_bytes())['background']
            plane = bg['priority']
            data = (out / plane['file']).read_bytes()
            self.assertEqual(data, scene['background']['priority'])
            self.assertEqual((bg['width'], bg['height'], plane['stride_bytes'], plane['length']),
                             (320, 200, 40, 8000))
            self.assertEqual(sha256(data).hexdigest(), plane['sha256'])
            self.assertEqual((out / bg['indices']).read_bytes(), bytes(63992) + bytes([0,0,6,6,6,6,9,9]))
            sprites = Path(tmp) / 'sprites'
            export(state, decode(state, 'sprites', slots=[]), sprites)
            self.assertFalse((sprites / plane['file']).exists())
            self.assertNotIn('background', json.loads((sprites / 'manifest.json').read_bytes()))

    def test_unsupported_combinations_refused(self):
        for d011, d016 in ((64, 16), (96, 0), (96, 16)):
            with self.subTest(bits=(d011, d016)), self.assertRaisesRegex(ValueError, 'Illegal'):
                decode(self.state(d011, d016, 3, 8), 'background')


if __name__ == '__main__':
    unittest.main()
