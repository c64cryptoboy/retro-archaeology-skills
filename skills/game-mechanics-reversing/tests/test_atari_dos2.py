"""Synthetic ATR fixtures only; no third-party programs or token modules."""

import json
from pathlib import Path
import struct
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from atari_dos2 import read_image


class AtrFixture:
    """Small DOS 2.0 fixture builder with independently settable raw trailers."""

    def __init__(self, sectors=720):
        self.body = bytearray(sectors * 128)
        self.body[359 * 128] = 2
        struct.pack_into("<H", self.body, 359 * 128 + 1, 707)
        for number in range(4, 720):
            if not 360 <= number <= 368:
                self.set_free(number, True)

    def set_free(self, number, free):
        offset = 359 * 128 + 10 + number // 8
        mask = 0x80 >> (number % 8)
        if free:
            self.body[offset] |= mask
        else:
            self.body[offset] &= ~mask

    def entry(self, slot=0, first=4, count=1, name=b"TEST    BIN", flags=0x42):
        if len(name) != 11:
            raise ValueError("Fixture names must have exactly 11 bytes")
        offset = 360 * 128 + slot * 16
        self.body[offset:offset + 16] = struct.pack("<BHH", flags, count, first) + name
        return self

    def block(self, number, payload=b"DATA", *, next_sector=0, file_id=0,
              slack_byte=0xa5, used=None):
        if len(payload) > 125:
            raise ValueError("Fixture payload exceeds sector capacity")
        raw = (payload + bytes([slack_byte]) * (125 - len(payload))
               + bytes([(file_id << 2) | (next_sector >> 8), next_sector & 255,
                        len(payload) if used is None else used]))
        self.body[(number - 1) * 128:number * 128] = raw
        if number < 720:
            self.set_free(number, False)
        return self

    def image(self):
        bitmap = self.body[359 * 128 + 10:359 * 128 + 100]
        free = sum(bin(byte).count("1") for byte in bitmap)
        struct.pack_into("<H", self.body, 359 * 128 + 3, free)
        paragraphs = len(self.body) // 16
        return struct.pack("<HHHH8x", 0x296, paragraphs & 65535, 128, paragraphs >> 16) + bytes(self.body)


def codes(entry):
    return {issue["code"] for issue in entry["issues"]}


class AtariDos2Tests(unittest.TestCase):
    def test_good_payload_slack_trailers_and_metadata(self):
        fixture = AtrFixture().entry(count=2).block(4, b"A" * 125, next_sector=300)
        fixture.block(300, b"\x00END\xff", slack_byte=0xcc)
        image = fixture.image()
        before = bytes(image)
        manifest, artifacts = read_image(image)
        entry = manifest["entries"][0]
        self.assertEqual(manifest["status"], "ok")
        self.assertEqual(entry["status"], "ok")
        self.assertEqual(len(manifest["entries"]), 64)
        self.assertEqual(artifacts[entry["paths"]["payload"]], b"A" * 125 + b"\x00END\xff")
        self.assertEqual(artifacts[entry["paths"]["slack"]], b"\xcc" * 120)
        self.assertEqual(artifacts[entry["paths"]["trailers"]], b"\x01\x2c\x7d\x00\x00\x05")
        self.assertEqual(artifacts[entry["paths"]["allocated"]],
                         fixture.body[3 * 128:4 * 128] + fixture.body[299 * 128:300 * 128])
        self.assertEqual(entry["chain"][1]["payload_offset"], 125)
        self.assertEqual(entry["chain"][1]["slack_offset"], 0)
        self.assertEqual(entry["chain"][1]["allocated_offset"], 128)
        self.assertTrue(entry["chain_terminated"])
        self.assertEqual(bytes.fromhex(entry["raw_entry_hex"]), fixture.body[360 * 128:360 * 128 + 16])
        self.assertEqual(artifacts["metadata/atr-header.bin"], image[:16])
        self.assertEqual(artifacts["metadata/vtoc.bin"], fixture.body[359 * 128:360 * 128])
        self.assertEqual(artifacts["metadata/directory.bin"], fixture.body[360 * 128:368 * 128])
        self.assertEqual(image, before)
        self.assertEqual((manifest, artifacts), read_image(image))
        json.dumps(manifest)

    def test_short_nonfinal_sector_is_supported(self):
        fixture = AtrFixture().entry(count=2).block(4, b"ABC", next_sector=719)
        fixture.block(719, b"", slack_byte=0x77)
        manifest, artifacts = read_image(fixture.image())
        entry = manifest["entries"][0]
        self.assertEqual(entry["issues"], [])
        self.assertEqual(artifacts[entry["paths"]["payload"]], b"ABC")
        self.assertEqual(artifacts[entry["paths"]["slack"]], b"\xa5" * 122 + b"\x77" * 125)

    def test_malformed_headers_and_geometry(self):
        image = AtrFixture().image()
        cases = [(b"", "header"), (image[:15], "header"),
                 (b"xx" + image[2:], "magic"),
                 (image[:4] + b"\x00\x01" + image[6:], "density"),
                 (image[:-1], "declared size"), (image + b"x", "declared size"),
                 (image[:6] + b"\x01\x00" + image[8:], "declared size")]
        body = image[16:] + bytes(16)
        cases.append((struct.pack("<HHHH8x", 0x296, len(body) // 16, 128, 0) + body,
                      "whole number"))
        body = image[16:-128]
        cases.append((struct.pack("<HHHH8x", 0x296, len(body) // 16, 128, 0) + body,
                      "at least 720"))
        for bad, message in cases:
            with self.subTest(message=message, size=len(bad)):
                with self.assertRaisesRegex(ValueError, message):
                    read_image(bad)

    def test_unsupported_vtoc_profiles(self):
        for version, count in [(1, 707), (2, 1010), (2, 1011), (2, 0)]:
            fixture = AtrFixture(1040)
            fixture.body[359 * 128] = version
            struct.pack_into("<H", fixture.body, 359 * 128 + 1, count)
            with self.subTest(version=version, count=count):
                with self.assertRaisesRegex(ValueError, "Unsupported VTOC"):
                    read_image(fixture.image())

    def test_ambiguous_vtoc2_is_not_guessed(self):
        fixture = AtrFixture(1040)
        fixture.body[1023 * 128 + 84] = 1
        with self.assertRaisesRegex(ValueError, "sector 1024"):
            read_image(fixture.image())

    def test_larger_container_preserves_all_extra_sectors(self):
        fixture = AtrFixture(1040).entry().block(4)
        fixture.body[1036 * 128 + 35] = 2
        manifest, artifacts = read_image(fixture.image())
        extra = manifest["outside_allocation_map"]
        self.assertEqual(manifest["status"], "ok")
        self.assertEqual(extra["sector_count"], 321)
        self.assertEqual(extra["nonzero_sectors"], [1037])
        self.assertEqual(artifacts[extra["path"]], fixture.body[719 * 128:])

    def test_sector_800_is_never_a_valid_dos2_chain(self):
        for start_outside in [True, False]:
            fixture = AtrFixture(1040).entry(first=800 if start_outside else 4,
                                             count=1 if start_outside else 2)
            if not start_outside:
                fixture.block(4, b"A" * 125, next_sector=800)
            fixture.block(800, b"OUTSIDE")
            with self.subTest(start_outside=start_outside):
                manifest, artifacts = read_image(fixture.image())
                entry = manifest["entries"][0]
                self.assertIn("link_out_of_map", codes(entry))
                self.assertIn("sector_count_mismatch", codes(entry))
                self.assertEqual(entry["status"], "issues")
                self.assertFalse(entry["chain_terminated"])
                self.assertNotIn("payload", entry["paths"])
                self.assertEqual(entry["observed_sectors"], 0 if start_outside else 1)
                self.assertEqual(artifacts[entry["paths"]["observed_payload"]],
                                 b"" if start_outside else b"A" * 125)
                extra = artifacts["evidence/outside-allocation-map.bin"]
                self.assertEqual(extra[80 * 128:81 * 128], fixture.body[799 * 128:800 * 128])

    def test_link_out_of_bounds_and_sector_720_boundary(self):
        for number in [720, 721, 1023, 65535]:
            with self.subTest(number=number):
                manifest, _ = read_image(AtrFixture().entry(first=number).image())
                entry = manifest["entries"][0]
                self.assertIn("link_out_of_map", codes(entry))
                self.assertEqual("link_out_of_bounds" in codes(entry), number > 720)
                self.assertEqual(entry["observed_sectors"], 0)

    def test_reserved_sector_links(self):
        for number in [1, 3, 360, 361, 368]:
            with self.subTest(number=number):
                manifest, _ = read_image(AtrFixture().entry(first=number).image())
                self.assertIn("reserved_sector_link", codes(manifest["entries"][0]))

    def test_loop_keeps_each_observed_sector_once(self):
        fixture = AtrFixture().entry(count=2).block(4, next_sector=5).block(5, next_sector=4)
        manifest, artifacts = read_image(fixture.image())
        entry = manifest["entries"][0]
        self.assertIn("chain_loop", codes(entry))
        self.assertEqual([item["sector"] for item in entry["chain"]], [4, 5])
        self.assertEqual(len(artifacts[entry["paths"]["allocated"]]), 256)
        self.assertFalse(entry["chain_terminated"])
        self.assertNotIn("payload", entry["paths"])

    def test_directory_count_mismatch_and_missing_start(self):
        for first in [0, 4]:
            with self.subTest(first=first):
                fixture = AtrFixture().entry(first=first, count=2).block(4)
                manifest, _ = read_image(fixture.image())
                entry = manifest["entries"][0]
                self.assertIn("sector_count_mismatch", codes(entry))
                self.assertNotIn("payload", entry["paths"])

    def test_invalid_used_count_preserves_raw_without_guessing_payload(self):
        fixture = AtrFixture().entry(count=2).block(4, b"GOOD", next_sector=5)
        fixture.block(5, b"BAD", used=126, next_sector=6).block(6, b"NOT FOLLOWED")
        manifest, artifacts = read_image(fixture.image())
        entry = manifest["entries"][0]
        self.assertIn("invalid_used_count", codes(entry))
        self.assertEqual(entry["observed_sectors"], 2)
        self.assertEqual(artifacts[entry["paths"]["observed_payload"]], b"GOOD")
        self.assertEqual(artifacts[entry["paths"]["allocated"]], fixture.body[3 * 128:5 * 128])
        self.assertEqual(len(artifacts[entry["paths"]["trailers"]]), 6)
        self.assertIsNone(entry["chain"][1]["payload_offset"])
        self.assertFalse(entry["chain_terminated"])
        self.assertNotIn("payload", entry["paths"])
        self.assertEqual(manifest["allocated_unowned"], [6])

    def test_wrong_file_id_is_reported(self):
        manifest, artifacts = read_image(AtrFixture().entry().block(4, file_id=3).image())
        entry = manifest["entries"][0]
        self.assertIn("wrong_file_id", codes(entry))
        self.assertEqual(artifacts[entry["paths"]["observed_payload"]], b"DATA")
        self.assertNotIn("payload", entry["paths"])

    def test_cross_links_flag_every_claimant(self):
        fixture = AtrFixture().entry().entry(slot=1, name=b"OTHER   BIN").block(4)
        manifest, artifacts = read_image(fixture.image())
        for slot, other in [(0, "entry-001"), (1, "entry-000")]:
            entry = manifest["entries"][slot]
            self.assertIn("cross_link", codes(entry))
            self.assertNotIn("payload", entry["paths"])
            self.assertEqual(artifacts[entry["paths"]["observed_payload"]], b"DATA")
            cross = [item for item in entry["issues"] if item["code"] == "cross_link"]
            self.assertEqual(cross[0]["other_entries"], [other])
        self.assertIn("wrong_file_id", codes(manifest["entries"][1]))

    def test_duplicate_case_colliding_and_unsafe_names_use_slots(self):
        names = [b"SAME    BIN", b"SAME    BIN", b"same    bin", b"../\\    BIN", b"\xffNAME   BIN"]
        fixture = AtrFixture()
        for slot, name in enumerate(names):
            fixture.entry(slot=slot, first=4 + slot, name=name).block(4 + slot, bytes([slot]), file_id=slot)
        manifest, artifacts = read_image(fixture.image())
        for slot, name in enumerate(names):
            entry = manifest["entries"][slot]
            self.assertEqual(entry["status"], "ok")
            self.assertEqual(entry["name_raw_hex"], name.hex())
            self.assertEqual(entry["paths"]["payload"], f"files/entry-{slot:03d}/payload.bin")
            self.assertEqual(artifacts[entry["paths"]["payload"]], bytes([slot]))
        for path in artifacts:
            self.assertNotIn("..", path.split("/"))
            self.assertNotIn("\\", path)
            self.assertFalse(path.startswith("/"))

    def test_bitmap_issues_and_unowned_evidence(self):
        fixture = AtrFixture().entry().block(4).block(7, b"UNOWNED")
        fixture.set_free(4, True)
        fixture.set_free(360, True)
        image = bytearray(fixture.image())
        struct.pack_into("<H", image, 16 + 359 * 128 + 3, 0)
        manifest, artifacts = read_image(bytes(image))
        self.assertIn("chain_sector_marked_free", codes(manifest["entries"][0]))
        self.assertEqual(codes(manifest), {"free_count_mismatch", "reserved_sectors_marked_free", "allocated_unowned"})
        self.assertEqual(manifest["allocated_unowned"], [7])
        self.assertEqual(artifacts["evidence/allocated-unowned.bin"], fixture.body[6 * 128:7 * 128])

    def test_deleted_entries_are_metadata_only(self):
        fixture = AtrFixture().entry(flags=0x82).block(4)
        manifest, artifacts = read_image(fixture.image())
        entry = manifest["entries"][0]
        self.assertTrue(entry["deleted"])
        self.assertEqual(entry["status"], "not_extracted")
        self.assertFalse(any(path.startswith("files/") for path in artifacts))

    def test_open_and_after_end_entries_are_observations_only(self):
        for slot, flags, issue in [(0, 0x43, "open_for_output"), (1, 0x42, "active_after_directory_end")]:
            with self.subTest(issue=issue):
                fixture = AtrFixture().entry(slot=slot, flags=flags).block(4, file_id=slot)
                manifest, _ = read_image(fixture.image())
                entry = manifest["entries"][slot]
                self.assertIn(issue, codes(entry))
                self.assertNotIn("payload", entry["paths"])

    def test_unsupported_directory_variants(self):
        for flags in [0x03, 0x40, 0x46]:
            with self.subTest(flags=flags):
                with self.assertRaisesRegex(ValueError, "Unsupported directory flags"):
                    read_image(AtrFixture().entry(flags=flags).image())


if __name__ == "__main__":
    unittest.main()
