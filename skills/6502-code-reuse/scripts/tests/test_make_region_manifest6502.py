import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from make_region_manifest6502 import create_manifest
from region_manifest import validate_manifest


class RawManifestTests(unittest.TestCase):
    def test_wraps_raw_binary_with_address_and_mask(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "capture.bin"
            mask = root / "capture.mask"
            output = root / "out"
            source.write_bytes(bytes.fromhex("a9 01 85 10 60"))
            mask.write_bytes(b"\xff\xff\xff\xff\x00")
            manifest = create_manifest(
                source,
                output,
                "synthetic-main",
                base_address=0x8000,
                known_mask=mask,
            )
            validate_manifest(manifest, output)
            reloaded = json.loads((output / "regions.json").read_text())
            validate_manifest(reloaded, output)
            region = reloaded["regions"][0]
            self.assertEqual(region["baseAddress"], 0x8000)
            self.assertEqual(region["size"], 5)
            self.assertEqual(region["knownMask"]["path"], "synthetic-main.known.mask")

    def test_rejects_empty_region(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "empty.bin"
            source.write_bytes(b"")
            with self.assertRaisesRegex(ValueError, "must not be empty"):
                create_manifest(source, root / "out", "empty-region")


if __name__ == "__main__":
    unittest.main()
