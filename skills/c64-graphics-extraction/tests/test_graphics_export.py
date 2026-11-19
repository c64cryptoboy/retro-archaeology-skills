import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from example import make_example
from extract import decode, export
from vic_state import State


def read_png(path):
    raw = path.read_bytes()
    assert raw.startswith(b'\x89PNG\r\n\x1a\n')
    p, data = 8, bytearray()
    while p < len(raw):
        n, kind = struct.unpack_from('>I4s', raw, p)
        chunk = raw[p+8:p+8+n]
        assert zlib.crc32(kind+chunk) == struct.unpack_from('>I', raw, p+8+n)[0]
        if kind == b'IHDR':
            w, h, depth, mode, _, _, interlace = struct.unpack('>IIBBBBB', chunk)
            assert (depth, mode, interlace) == (8, 6, 0)
        elif kind == b'IDAT':
            data.extend(chunk)
        p += 12+n
    pixels = zlib.decompress(data)
    stride = 4*w+1
    assert len(pixels) == stride*h and not any(pixels[::stride])
    return w, h, b''.join(pixels[i+1:i+stride] for i in range(0, len(pixels), stride))


class GraphicsExportTests(unittest.TestCase):
    def test_address_sources_and_missing_rom(self):
        ram = bytes([0x15]) * 65536
        regs = bytes(64)
        for bank, pins in [(0, 3), (0x4000, 2), (0x8000, 1), (0xc000, 0)]:
            s = State(ram, regs, pins | 0x60, chargen=bytes([0x83]) * 4096)
            self.assertEqual(s.bank, bank)
            visible = 0x83 if bank in (0, 0x8000) else 0x15
            self.assertEqual(s.fetch(bank+0xfff, 2), bytes([0x15, visible]))
            self.assertEqual(s.fetch(bank+0x1fff, 2), bytes([visible, 0x15]))
        s = State(ram, regs, 3)
        with self.assertRaisesRegex(ValueError, 'chargen'):
            s.fetch(0x1000, 1)
        with self.assertRaisesRegex(ValueError, 'outside'):
            s.fetch(0x3fff, 2)
        for invalid in (True, -1, '3', 256):
            with self.assertRaises(ValueError):
                State(ram, regs, invalid)

    def test_real_cli_outputs_and_reuse(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            make_example(root/'inputs')
            s = State.load(root/'inputs/capture.json')
            cmd = [sys.executable, str(ROOT/'extract.py'), 'inputs/capture.json', 'out', '--sheets', '--prg', '--asm']
            subprocess.run(cmd, cwd=root, capture_output=True, check=True)
            out = root/'out'
            info = json.loads((out/'manifest.json').read_bytes())
            self.assertEqual((info['bank'], info['matrix_address']), (0x4000, 0x6800))
            for name, (addr, size) in {'slot0': (0x6000,64), 'charset': (0x5000,2048), 'screen': (0x6800,1000)}.items():
                data = s.ram[addr:addr+size]
                self.assertEqual((out/f'{name}.bin').read_bytes(), data)
                self.assertEqual((out/f'{name}.prg').read_bytes(), addr.to_bytes(2,'little')+data)
            self.assertEqual((out/'color.bin').read_bytes(), s.color)
            self.assertFalse((out/'color.prg').exists())
            self.assertIn('asset_slot0: .incbin "slot0.bin"', (out/'assets.inc').read_text())
            w, h, sprite = read_png(out/'slot1.png')
            self.assertEqual((w,h), (24,21))
            self.assertEqual(set(sprite[i:i+4] for i in range(0,len(sprite),4)), {bytes(4), bytes([0,0,0,255])})
            self.assertEqual(read_png(out/'slot1-expanded.png')[:2], (48,21))
            w, _, art = read_png(out/'sprites.png')
            entry = info['sheets']['sprites.png'][1]
            pos = entry['y']*w + entry['x']
            crop = b''.join(art[4*(pos+y*w):4*(pos+y*w+24)] for y in range(21))
            self.assertEqual(crop, sprite)
            self.assertEqual(len(info['sheets']['raw-glyph-bits.png']),256)
            self.assertEqual(sum(len(v['cells']) for v in info['background']['variants']),1000)
            self.assertEqual(read_png(out/'screen.png')[:2], (320,200))
            before = (out/'manifest.json').read_bytes()
            self.assertNotEqual(subprocess.run(cmd, cwd=root, capture_output=True).returncode, 0)
            self.assertEqual((out/'manifest.json').read_bytes(), before)

    def test_koala_file_sections_and_mode_refusal(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            regs = bytearray(64)
            regs[0x11], regs[0x16], regs[0x18], regs[0x21] = 0x30, 0x10, 0x18, 0xf3
            ram = bytearray(65536)
            ram[0x4400:0x47e8] = (bytes([0x25, 0x52]) * 500)
            ram[0x6000:0x7f40] = (bytes(range(200)) * 40)
            colors = bytes([0xf1, 0xb7]) * 500
            state = State(bytes(ram), bytes(regs), 2, colors)
            expected = (b'\x00\x60' + bytes(ram[0x6000:0x7f40]) + bytes(ram[0x4400:0x47e8])
                        + bytes([1, 7]) * 500 + b'\x03')
            out = root/'multi'
            meta = export(state, decode(state, 'background'), out, koala=True)
            self.assertEqual((out/'screen.koa').read_bytes(), expected)
            self.assertEqual(meta['background']['koala']['length'], 10003)
            self.assertEqual((out/'color.bin').read_bytes(), colors)
            regs[0x16] = 0
            hires = State(bytes(ram), bytes(regs), 2, colors)
            for mode in ('background', 'sprites'):
                with self.assertRaisesRegex(ValueError, 'multicolor bitmap'):
                    export(hires, decode(hires, mode, []), root/mode, koala=True)
                self.assertFalse((root/mode).exists())

    def test_artstudio_preserves_hires_source_and_refuses_other_modes(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            regs = bytearray(64)
            regs[0x11], regs[0x18] = 0x30, 0x18
            ram = bytearray(65536)
            pattern = b'\x96\x69' * 4000
            matrix = b'\x2a\xa2' * 500
            ram[0x6000:0x7f40], ram[0x4400:0x47e8] = pattern, matrix
            state = State(bytes(ram), bytes(regs), 2)
            meta = export(state, decode(state, 'background'), root/'hi', artstudio=True)
            self.assertEqual((root/'hi'/'screen.art').read_bytes(),
                             b'\x00\x20' + pattern + matrix + bytes(7))
            self.assertEqual(meta['background']['artstudio']['length'], 9009)
            regs[0x16] = 0x10
            state = State(bytes(ram), bytes(regs), 2, bytes(1000))
            for mode in ('background', 'sprites'):
                with self.assertRaisesRegex(ValueError, 'hires bitmap'):
                    export(state, decode(state, mode, []), root/mode, artstudio=True)
                self.assertFalse((root/mode).exists())

    def test_sparse_capture_refuses_unknown_pointer_or_padding(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root/'vic').write_bytes(bytes(64))
            (root/'ptr').write_bytes(bytes([0x80]))
            (root/'pattern').write_bytes(bytes(63))
            spec = {'vic': 'vic', 'cia2_pins': 2, 'ram_segments': [
                {'address': 0x43f8, 'file': 'ptr'}, {'address': 0x6000, 'file': 'pattern'}]}
            p = root/'capture.json'
            p.write_text(json.dumps(spec))
            with self.assertRaisesRegex(ValueError, '603F'):
                decode(State.load(p), 'sprites', [0])
            (root/'pattern').write_bytes(bytes(64))
            s = State.load(p)
            self.assertEqual(decode(s, 'sprites', [0])['sprites'][0]['address'], 0x6000)
            with self.assertRaisesRegex(ValueError, '43F9'):
                decode(s, 'sprites', [1])
            spec['ram_segments'].append({'address': 0x6010, 'file': 'ptr'})
            p.write_text(json.dumps(spec))
            with self.assertRaisesRegex(ValueError, 'overlapping'):
                State.load(p)

    def test_rom_visible_bytes_and_no_ram_prg_for_rom(self):
        with tempfile.TemporaryDirectory() as d:
            ram, regs = bytearray(65536), bytearray(64)
            ram[0x3f8] = 0x40  # sprite at $1000, underneath the VIC char ROM window
            regs[0x15] = 1
            s = State(bytes(ram), bytes(regs), 3, chargen=b'\x80' + bytes(4095))
            result = decode(s, 'sprites', [0])
            out = Path(d)/'export'
            meta = export(s, result, out, prg=True)
            self.assertEqual((out/'slot0.bin').read_bytes(), b'\x80' + bytes(63))
            self.assertEqual((out/'slot0.idx').read_bytes()[:2], bytes([0,255]))
            self.assertEqual(meta['blocks']['slot0']['source_spans'][0]['source'], 'chargen')
            self.assertFalse((out/'slot0.prg').exists())


if __name__ == '__main__':
    unittest.main()
