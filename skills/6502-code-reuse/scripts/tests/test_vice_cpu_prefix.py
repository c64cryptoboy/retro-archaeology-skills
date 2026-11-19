"""Optional C64 CPU metadata must not determine which RAM bytes are extracted."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from extract_vice_snapshot import parse_snapshot


# Hand-authored wire bytes, not packed by the decoder or a VICE test kit.
PREFIX = bytes.fromhex("08 17 26 35 44 53 62 71 9a bc de f0 34 12 a5")
RAM = bytes(range(256)) * 256


def module(name, major, minor, payload):
    size = (22 + len(payload)).to_bytes(4, "little")
    return name.encode("ascii").ljust(16, b"\0") + bytes((major, minor)) + size + payload


def snapshot(*cpus):
    header = b"VICE Snapshot File\x1a\x01\x01" + b"C64".ljust(16, b"\0")
    return header + b"".join(cpus) + module("C64MEM", 0, 1, b"\x37\x2f\0\0" + RAM)


class ViceCpuPrefixTest(unittest.TestCase):
    def test_known_prefixes(self):
        expected = {"clock": 0x7162534435261708, "a": 0x9a, "x": 0xbc, "y": 0xde,
                    "sp": 0xf0, "pc": 0x1234, "p": 0xa5}
        for name, minor in (("MAINCPU", 4), ("MAINC64CPU", 5)):
            with self.subTest(name=name):
                parsed = parse_snapshot(snapshot(module(name, 1, minor, PREFIX)))
                self.assertEqual(parsed["cpu"], expected)
                self.assertEqual(parsed["ram"], RAM)

    def test_ram_survives_unusable_cpu(self):
        old = module("MAINCPU", 1, 4, PREFIX)
        new = module("MAINC64CPU", 1, 5, PREFIX)
        crossed = module("MAINC64CPU", 1, 4, PREFIX)
        cases = {
            "missing": (), "old name, new minor": (module("MAINCPU", 1, 5, PREFIX),),
            "new name, old minor": (crossed,), "wrong major": (module("MAINC64CPU", 2, 5, PREFIX),),
            "short prefix": (module("MAINC64CPU", 1, 5, PREFIX[:-1]),),
            "duplicate old": (old, old), "duplicate new": (new, new), "both names": (old, new),
            "supported and unsupported": (old, crossed),
        }
        for label, cpus in cases.items():
            with self.subTest(case=label):
                parsed = parse_snapshot(snapshot(*cpus))
                self.assertIsNone(parsed["cpu"])
                self.assertEqual(parsed["ram"], RAM)
