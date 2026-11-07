#!/usr/bin/env python3
"""Tests for the generic byte-region contract and AppleWin/VICE adapters."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(TOOLS))

import extract_applewin_snapshot as applewin  # noqa: E402
import extract_retro_nestopia_snapshot as nestopia  # noqa: E402
import extract_vice_snapshot as vice  # noqa: E402
import region_manifest  # noqa: E402


def synthetic_applewin(*, second_offset: str = "0040") -> bytes:
    first_row = bytes(range(64)).hex().upper()
    second_row = bytes(range(64, 72)).hex().upper()
    return (
        "---\r\n"
        "File_hdr:\r\n"
        "  Tag: AppleWin Save State\r\n"
        "  Version: 2\r\n"
        "\r\n"
        "Unit:\r\n"
        "  Type: Apple2\r\n"
        "  Version: 9\r\n"
        "  State:\r\n"
        "    Model: Enhanced Apple//e\r\n"
        "    CPU:\r\n"
        "      Type: 65C02\r\n"
        "      A: 0x01\r\n"
        "      X: 0x02\r\n"
        "      Y: 0x03\r\n"
        "      P: 0x24\r\n"
        "      S: 0xF0\r\n"
        "      PC: 0x3456\r\n"
        "    Main Memory:\r\n"
        f"      0000: {first_row}\r\n"
        f"      {second_offset}: {second_row}\r\n"
        "\r\n"
        "Unit:\r\n"
        "  Type: Auxiliary Slot\r\n"
        "  Version: 2\r\n"
        "  State:\r\n"
        "    Card: Extended 80 Column\r\n"
        "    State:\r\n"
        "      Auxiliary Memory Bank00:\r\n"
        "        0400: 0102030405060708\r\n"
        "\r\n"
        "Unit:\r\n"
        "  Type: Slots\r\n"
        "  Version: 1\r\n"
        "  State:\r\n"
        "    6:\r\n"
        "      Track Image:\r\n"
        "        0000: DEADBEEF00000000\r\n"
    ).encode("ascii")


class SyntheticAppleWinTest(unittest.TestCase):
    def test_extracts_duplicate_unit_memory_maps_without_yaml_dependency(self) -> None:
        parsed = applewin.parse_snapshot(synthetic_applewin())
        self.assertEqual(parsed["fileVersion"], 2)
        self.assertEqual(parsed["machine"]["model"], "Enhanced Apple//e")
        self.assertEqual(parsed["cpu"]["type"], "65C02")
        self.assertEqual(parsed["cpu"]["pc"], 0x3456)

        regions = parsed["regions"]
        self.assertEqual([region.region_id for region in regions], [
            "applewin-main-memory",
            "applewin-auxiliary-memory-bank00",
        ])
        self.assertEqual(regions[0].data, bytes(range(72)))
        self.assertEqual(regions[0].base_address, 0)
        self.assertEqual(regions[1].data, bytes(range(1, 9)))
        self.assertEqual(regions[1].base_address, 0x400)
        self.assertEqual(len(parsed["ignoredHexBlocks"]), 1)
        self.assertIn("Track Image", parsed["ignoredHexBlocks"][0]["yamlPath"])

    def test_rejects_noncontiguous_memory_rows(self) -> None:
        with self.assertRaisesRegex(applewin.SnapshotError, "non-contiguous"):
            applewin.parse_snapshot(synthetic_applewin(second_offset="0048"))

    def test_writes_self_validating_generic_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "state.aws.yaml"
            output = root / "out"
            source.write_bytes(synthetic_applewin())
            manifest = applewin.extract_to_directory(source, output)
            region_manifest.validate_manifest(manifest, output)
            reloaded = json.loads((output / "regions.json").read_text())
            region_manifest.validate_manifest(reloaded, output)
            self.assertEqual(reloaded["regions"][0]["cpuProfile"], "65c02")


class ManifestValidationTest(unittest.TestCase):
    def test_validates_optional_same_size_known_mask(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            data = b"ABCD"
            mask = b"\xFF\xFF\x00\x00"
            (output / "region.bin").write_bytes(data)
            (output / "known.mask").write_bytes(mask)
            region = region_manifest.region_record(
                region_id="masked-region",
                path="region.bin",
                data=data,
                kind="cpu-memory",
                source={"container": "synthetic"},
                known_mask_path="known.mask",
                known_mask=mask,
            )
            manifest = region_manifest.build_manifest(
                artifact={
                    "path": "synthetic",
                    "format": "synthetic",
                    "size": 0,
                    "sha256": region_manifest.sha256(b""),
                },
                regions=[region],
            )
            region_manifest.validate_manifest(manifest, output)

    def test_rejects_duplicate_region_ids(self) -> None:
        data = b"test"
        region = region_manifest.region_record(
            region_id="test-region",
            path="one.bin",
            data=data,
            kind="cpu-memory",
            source={"container": "synthetic"},
        )
        duplicate = dict(region)
        duplicate["path"] = "two.bin"
        with self.assertRaisesRegex(region_manifest.ManifestError, "duplicate region id"):
            region_manifest.build_manifest(
                artifact={
                    "path": "synthetic",
                    "format": "synthetic",
                    "size": 0,
                    "sha256": region_manifest.sha256(b""),
                },
                regions=[region, duplicate],
            )


if __name__ == "__main__":
    unittest.main()
