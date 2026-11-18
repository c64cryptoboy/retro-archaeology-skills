"""A physical file seam alone is not an executable PRG sequence."""

import json
import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from anchor_scan6502 import load_regions
from extract_retro_nestopia_snapshot import extract_to_directory, physical_prg_ranges, PRG_PAGE_SIZE
from reuse_align6502 import analyze_manifests
from reuse_fixture import manifest
from test_end_to_end_synthetic import LEFT


def chunk(tag, body):
    return tag + struct.pack("<I", len(body)) + body


def capture(root, mapper, pages, bank_count, start):
    prg = bytearray(b"\x02" * (16384 * bank_count))
    prg[start:start + len(LEFT)] = LEFT
    header = b"NES\x1a" + bytes([bank_count, 0, (mapper << 4) | 4]) + bytes(9)
    rom = root / "synthetic.nes"
    rom.write_bytes(header + bytes(512) + prg)
    info = chunk(b"NFO\0", struct.pack("<II", zlib.crc32(prg), 0))
    cpu = chunk(b"CPU\0", chunk(b"REG\0", bytes(7)) + chunk(b"RAM\0", bytes(2049)))
    mapping = chunk(b"ACC\0", b"\x01") + chunk(b"BNK\0", b"".join(struct.pack("<BH", 0, i) for i in pages))
    image = chunk(b"IMG\0", chunk(b"MPR\0", chunk(b"PRG\0", mapping)))
    state = root / "state.bin"
    state.write_bytes(chunk(b"NST\x1a", info + cpu + image))
    return extract_to_directory(state, rom, root / "out"), prg


class PrgScanTest(unittest.TestCase):
    def test_auto_scan_requires_a_contiguous_mapping_for_a_seam(self):
        for name, mapper, pages, count, start, expected in (
            ("switchable seam", 2, [0, 1, 6, 7], 4, 0x3ff0, 0),
            ("intact bank", 2, [0, 1, 6, 7], 4, 0x4800, 1),
            ("mapped seam", 0, [0, 1, 2, 3], 2, 0x3ff0, 1),
        ):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                records, prg = capture(root, mapper, pages, count, start)
                out = root / "out"
                extracted = out / "regions.json"
                self.assertEqual((out / "nes-prg-rom.bin").read_bytes(), prg)
                physical = [r for r in records["regions"] if r["kind"] == "cpu-program-rom" and r["scanByDefault"]]
                recovered = bytearray()
                for r in physical:
                    self.assertEqual(r["source"]["prgOffset"], len(recovered))
                    self.assertEqual(r["source"]["fileOffset"], 16 + 512 + len(recovered))
                    recovered.extend((out / r["path"]).read_bytes())
                self.assertEqual(recovered, prg)
                reference = manifest(root, "reference", LEFT)
                comparisons = analyze_manifests(reference, extracted)["comparisons"]
                hits = [(c["rightRegion"], m["rightStart"]) for c in comparisons for m in c["matches"]
                        if m["classification"] == "probable-shared-routine"]
                self.assertEqual(len(hits), expected)
                for region_id, offset in hits:
                    record = next(r for r in physical if r["id"] == region_id)
                    self.assertEqual(record["source"]["prgOffset"] + offset, start)
                if not expected:
                    # Reject old default-enabled flat manifests, not just new adapter output.
                    next(r for r in records["regions"] if r["id"] == "ines-prg-rom")["scanByDefault"] = True
                    extracted.write_text(json.dumps(records))
                    with self.assertRaisesRegex(ValueError, "re-extract"):
                        load_regions(extracted)

    def test_mirrored_page_cannot_stitch_two_cpu_runs(self):
        page = PRG_PAGE_SIZE
        segments = [{"cpuStart": i*page, "cpuEndExclusive": (i+1)*page,
                     "known": True, "source": "prg-rom", "sourceOffset": bank*page}
                    for i, bank in enumerate((0, 1, 1, 2))]
        self.assertEqual(list(physical_prg_ranges(3*page, segments)), [(0, 2*page), (2*page, 3*page)])
