"""A common tail must not inherit the rarity of a disconnected entry seed."""

from pathlib import Path
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

from make_region_manifest6502 import create_manifest
from reuse_align6502 import analyze_manifests


def scatter_reduction(*, target: bool, xor: bool = False) -> bytes:
    # Compute a column index in X, clear A, and reduce 48 bytes with ORA/EOR.
    # Scatter the result into that column of 20 successive destination pages.
    entry = bytes.fromhex("d8 18 a5 10 65 11 aa a9 00 85 12 a8")
    hook = bytes.fromhex("48 8a 20 00 a0 68") if target else b""  # save A around a hook
    body = b"".join(bytes((0x45 if xor else 0x05, zp)) for zp in range(0x20, 0x50))
    page = 0x80 if target else 0x40
    stores = b"".join(bytes((0x9d, 0, page + i)) for i in range(20))
    return entry + hook + body + stores + b"\x60"


def compare(root, *, xor, **settings):
    for name, target in (("left", False), ("right", True)):
        raw = root / f"{name}.bin"
        raw.write_bytes(scatter_reduction(target=target, xor=target and xor))
        create_manifest(raw, root / name, name, base_address=0x2000 if target else 0x1000)
    report = analyze_manifests(root / "left/regions.json", root / "right/regions.json", **settings)
    return report["comparisons"][0]


class SeedExtensionTest(unittest.TestCase):
    def test_common_scatter_tail_cannot_borrow_rare_entry_seed(self):
        with tempfile.TemporaryDirectory() as tmp:
            comparison = compare(Path(tmp), xor=True)
        # Only the eight-instruction entry qualifies.  Repeated stores and RTS
        # cannot seed an extension themselves, even though both tails align well.
        self.assertEqual(comparison["exactAnchors"], 1)
        match, = comparison["matches"]
        self.assertEqual(match["classification"], "candidate-similarity")
        self.assertEqual((match["leftStart"], match["rightStart"]), (0, 0))
        self.assertEqual((match["leftEndExclusive"], match["rightEndExclusive"]), (12, 12))
        self.assertEqual(match["metrics"]["relationalExact"], 8)
        self.assertEqual(match["score"], 40)

    def test_relocated_scatter_with_inserted_hook_still_extends(self):
        with tempfile.TemporaryDirectory() as tmp:
            comparison = compare(Path(tmp), xor=False)
        match, = comparison["matches"]
        self.assertEqual(match["classification"], "probable-shared-routine")
        self.assertEqual((match["leftStart"], match["rightStart"]), (0, 0))
        self.assertEqual(match["metrics"]["relationalExact"], 77)
        self.assertEqual(match["metrics"]["gaps"], 4)
        self.assertEqual(match["score"], sum(col["score"] for col in match["columns"]))
        self.assertEqual(match["seed"]["alignedPrefixPairs"], 8)
        self.assertEqual((match["seed"]["leftEndExclusive"], match["seed"]["rightEndExclusive"]), (12, 12))

    def test_truncated_stream_cannot_claim_a_complete_seed(self):
        with tempfile.TemporaryDirectory() as tmp:
            comparison = compare(Path(tmp), xor=True, max_instructions=7)
        self.assertEqual(comparison["exactAnchors"], 1)
        self.assertEqual(comparison["matches"], [])


if __name__ == "__main__":
    unittest.main()
