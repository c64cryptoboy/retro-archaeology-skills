"""Check the published labels, and cross-check their targets if KERNAL is installed."""

import hashlib
import os
from pathlib import Path
import sys
import unittest

SKILL = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SKILL / "scripts"))
from rom_manifest import ROMS

# Public jump slot, internal target in revision 901227-03.
IEC = {
    "TALK": (0xFFB4, 0xED09), "LISTEN": (0xFFB1, 0xED0C),
    "SECND": (0xFF93, 0xEDB9), "TKSA": (0xFF96, 0xEDC7),
    "CIOUT": (0xFFA8, 0xEDDD), "UNTLK": (0xFFAB, 0xEDEF),
    "UNLSN": (0xFFAE, 0xEDFE), "ACPTR": (0xFFA5, 0xEE13),
}


class KernalReferenceTests(unittest.TestCase):
    def test_tables_and_quick_reference(self):
        doc = (SKILL / "references" / "kernal-symbols.md").read_text(encoding="utf-8")
        for name, (slot, target) in IEC.items():
            with self.subTest(name=name):
                self.assertIn(f"| `${slot:04X}` | `{name}` |", doc)
                self.assertIn(f"| `${target:04X}` | `{name}_INTERNAL` |", doc)
                self.assertIn(f"\n${target:04X} {name} internal\n", doc)
        for address, symbol, summary in (
            ("FF48", "IRQ_ENTRY", "hardware IRQ/BRK entry"),
            ("FEBC", "RESTORE_RTI", "restore registers and RTI"),
            ("EA81", "IRQ_EXIT", "IRQ exit"),
        ):
            self.assertIn(f"| `${address}` | `{symbol}` |", doc)
            self.assertIn(f"\n${address} {summary}\n", doc)

    def test_targets_in_supplied_kernal(self):
        rom = ROMS["kernal"]
        path = Path(os.environ.get("C64_ROM_DIR", SKILL / "assets" / "roms")) / rom.filename
        if not path.exists():
            self.skipTest("optional kernal.bin not installed")
        data = path.read_bytes()
        self.assertEqual(len(data), rom.size)
        self.assertEqual(hashlib.sha256(data).hexdigest(), rom.sha256)

        def at(address, size):
            offset = address - rom.base
            return data[offset:offset + size]

        for name, (slot, target) in IEC.items():
            with self.subTest(name=name):
                jump = at(slot, 3)
                self.assertEqual(jump[0], 0x4C)  # JMP absolute
                self.assertEqual(int.from_bytes(jump[1:], "little"), target)

        entry = int.from_bytes(at(0xFFFE, 2), "little")
        self.assertEqual(entry, 0xFF48)
        self.assertEqual(at(entry, 5), bytes.fromhex("48 8A 48 98 48"))  # save A, X, Y
        restore_rti = bytes.fromhex("68 A8 68 AA 68 40")
        self.assertEqual(at(0xFEBC, 6), restore_rti)
        self.assertEqual(at(0xEA81, 6), restore_rti)
        self.assertNotEqual(at(entry, 6), restore_rti)
