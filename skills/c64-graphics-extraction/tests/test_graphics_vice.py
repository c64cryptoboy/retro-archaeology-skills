"""Synthetic VICE framing and normalization checks; no emulator or ROM required."""
from hashlib import sha256
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from vic_state import State
from vice_capture import normalize


HEADER = (b'VICE Snapshot File\x1a\x02\x00' + b'C64SC'.ljust(16, b'\0')
          + b'VICE Version\x1a')
RAM = bytes(range(256)) * 256
REGS = bytes(range(64))
COLORS = bytes(range(15, -1, -1)) * 64


def framed(name, version, payload):
    return struct.pack('<16sBBI', name.encode(), *version, 22 + len(payload)) + payload


def modules(pra=0xd5, ddra=3, bank=2):
    # Construct the VIC-II writer's fields in order.  Distinct neighbors guard
    # both ends of each extracted array; raster shape is unrelated to the data.
    vic = (b'\x03' + REGS + bytes(19) + bytes(40) * 2 + bytes(1 + 4) + bytes(65 * 8)
           + bytes(4 + 4) + bytes(6 * 4) + bytes(2 + 3 * 4 + 8) + bytes(1 + 4 + 4 + 1)
           + b'\xa3' * 8 + COLORS + b'\xc2' * (8 * 12) + bytes(174)
           + struct.pack('<4I', 42, 320, 200, 320) + bytes(320 * 204))
    return {
        'CIA2': ((2, 5), bytes([pra, 0xff, ddra, 0xff]) + bytes(73)),
        'C64CART': ((0, 1), bytes(1)),
        'VIC-II': ((1, 3), vic),
        'GLUE': ((1, 0), bytes([1, bank, 0])),
        'C64MEMHACKS': ((0, 0), bytes(1)),
        'C64MEM': ((0, 1), b'\x37\x2f\0\0' + RAM + b'\xdb' * 15),
    }


def snapshot(mods=None, version=(3, 9, 0, 0), revision=0):
    if mods is None:
        mods = modules()
    return HEADER + bytes(version) + struct.pack('<I', revision) + b''.join(framed(k, *v) for k, v in mods.items())


class ViceCaptureTest(unittest.TestCase):
    def test_uses_module_bounds_not_search_or_file_offsets(self):
        mods = modules()
        vic_version, vic = mods['VIC-II']
        decoy = framed('VIC-II', vic_version, vic[:1] + bytes([0xee]) * 64 + vic[65:])
        mods = {'UNRELATED': ((0, 1), decoy), **dict(reversed(mods.items()))}
        raw = snapshot(mods)
        spec, blocks = normalize(raw)
        self.assertEqual(blocks, {'ram': RAM, 'vic': REGS, 'color_ram': COLORS})
        self.assertEqual(spec['cia2_pins'] & 3, 1)
        self.assertEqual(spec['provenance']['cia2_pra'], 0xd5)
        self.assertEqual(spec['provenance']['snapshot_sha256'], sha256(raw).hexdigest())
        self.assertNotIn('chargen', spec)

    def test_310_exact_profile_and_unchanged_layout(self):
        version = (3, 10, 0, 0)
        spec, blocks = normalize(snapshot(version=version))
        self.assertEqual(blocks, {'ram': RAM, 'vic': REGS, 'color_ram': COLORS})
        self.assertEqual(spec['provenance']['vice_version'], '3.10.0.0')
        self.assertEqual(spec['provenance']['vic_model'], 3)
        self.assertEqual(spec['cia2_pins'], 1)
        with self.assertRaises(ValueError):
            normalize(snapshot(version=version, revision=1))
        mods = modules()
        rev, vic = mods['VIC-II']
        mods['VIC-II'] = (rev, b'\x04' + vic[1:])
        with self.assertRaisesRegex(ValueError, 'model'):
            normalize(snapshot(mods, version))
        # Insert a byte before colors and drop the last raster byte: same module
        # length and revision, but the raster header is now one byte off.
        mods['VIC-II'] = (rev, vic[:761] + b'\xfe' + vic[761:-1])
        with self.assertRaisesRegex(ValueError, 'raster payload size'):
            normalize(snapshot(mods, version))

    def test_ddr_requires_observation_not_assumed_pullups(self):
        raw = snapshot(modules(pra=0x00, ddra=1, bank=1))
        with self.assertRaisesRegex(ValueError, 'observed'):
            normalize(raw)
        self.assertEqual(normalize(raw, 0x82)[0]['cia2_pins'], 0x82)
        for pins in (-1, 256, 0x83):
            with self.subTest(pins=pins), self.assertRaises(ValueError):
                normalize(raw, pins)

    def test_requires_exact_header_and_each_used_module_once(self):
        raw = snapshot()
        for original, changed in [(b'C64SC', b'C64\0\0'), (b'\x1a\x02\x00', b'\x1a\x02\x01'),
                                  (b'\x03\x09\x00\x00', b'\x03\x0a\x00\x01')]:
            with self.subTest(header=original), self.assertRaises(ValueError):
                normalize(raw.replace(original, changed, 1))
        for name, (version, payload) in modules().items():
            mods = modules()
            del mods[name]
            with self.subTest(missing=name), self.assertRaises(ValueError):
                normalize(snapshot(mods))
            with self.subTest(duplicate=name), self.assertRaises(ValueError):
                normalize(raw + framed(name, version, payload))
            mods[name] = ((version[0], version[1] + 1), payload)
            with self.subTest(version=name), self.assertRaises(ValueError):
                normalize(snapshot(mods))
            mods[name] = (version, payload[:-1])
            with self.subTest(truncated_payload=name), self.assertRaises(ValueError):
                normalize(snapshot(mods))
        with self.assertRaisesRegex(ValueError, 'past EOF'):
            normalize(raw[:-1])

    def test_excludes_nonstock_and_transitional_banks(self):
        mem = modules()['C64MEM'][1]
        for name, payload in [('C64CART', b'\x01'), ('C64MEMHACKS', b'\x01'),
                              ('C64MEM', mem[:2] + b'\x01' + mem[3:]),
                              ('GLUE', b'\x01\x02\x01'), ('GLUE', b'\x01\x03\x00')]:
            mods = modules()
            mods[name] = (mods[name][0], payload)
            with self.subTest(name=name), self.assertRaises(ValueError):
                normalize(snapshot(mods))

    def test_cli_produces_loadable_local_inputs_and_never_reuses_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src, out, rom = root / 'source.vsf', root / 'new', root / 'font'
            src.write_bytes(snapshot(modules(ddra=1)))
            cmd = [sys.executable, '-B', str(ROOT / 'vice_capture.py'), str(src), str(out)]

            def run(*options):
                return subprocess.run(cmd + list(options), capture_output=True, text=True)

            self.assertNotEqual(run().returncode, 0)
            self.assertFalse(out.exists())
            rom.write_bytes(b'not a ROM')
            options = ['--chargen', str(rom), '--cia2-pins', '0xa1']
            self.assertNotEqual(run(*options).returncode, 0)
            self.assertFalse(out.exists())
            rom.write_bytes(b'\xaa\x55' * 2048)
            result = run(*options)
            self.assertEqual(result.returncode, 0, result.stderr)
            state = State.load(out / 'capture.json')
            self.assertEqual((state.ram, state.vic, state.color), (RAM, REGS, COLORS))
            self.assertEqual((state.cia2_pins, state.bank, state.chargen), (0xa1, 0x8000, rom.read_bytes()))
            spec = json.loads((out / 'capture.json').read_text())
            (out / spec['vic']).write_bytes(b'preserve me')
            self.assertNotEqual(run(*options).returncode, 0)
            self.assertEqual((out / spec['vic']).read_bytes(), b'preserve me')


if __name__ == '__main__':
    unittest.main()
