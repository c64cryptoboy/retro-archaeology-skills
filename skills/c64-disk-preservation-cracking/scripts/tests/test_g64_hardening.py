"""Independent, synthetic G64 hardening controls.  No target code is executed.

Run against a different reader with G64_READER=/absolute/path/g64_extract.py.
The encoder, XOR, container layout, and expected coordinates are fixture-owned.
"""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

READER = Path(os.environ.get("G64_READER", Path(__file__).resolve().parents[1] / "g64_extract.py"))
spec = importlib.util.spec_from_file_location("g64_hardening_reader", READER)
g = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = g
spec.loader.exec_module(g)

CODES = (10, 11, 18, 19, 14, 15, 22, 23, 9, 25, 26, 27, 13, 29, 30, 21)
PAYLOAD = b"\x01\x08synthetic-only"


def checksum(raw):
    result = 0
    for byte in raw:
        result ^= byte
    return result


def encode(raw):
    return "".join(f"{CODES[nibble]:05b}" for byte in raw for nibble in (byte >> 4, byte & 15))


def record(track=1, sector=0, payload=bytes(range(256)), header_ok=True, data_ok=True, disk_id=b"AB"):
    fields = bytes((sector, track)) + disk_id
    header = bytes((8, checksum(fields) ^ int(not header_ok))) + fields + b"\x0f\x0f"
    body = b"\x07" + payload + bytes((checksum(payload) ^ int(not data_ok),))
    return "1" * 10 + encode(header) + "0" * 16 + "1" * 10 + encode(body)


def track_bytes(*records):
    bits = "0" * 16 + "".join(item + "0" * 16 for item in records)
    bits += "0" * (-len(bits) % 8)
    return bytes(int(bits[i:i + 8], 2) for i in range(0, len(bits), 8))


def container(*tracks):
    position = 12 + 8 * len(tracks)
    offsets, bodies = [], []
    for raw in tracks:
        offsets.append(position.to_bytes(4, "little"))
        body = len(raw).to_bytes(2, "little") + raw
        bodies.append(body)
        position += len(body)
    return (b"GCR-1541" + bytes((0, len(tracks)))
            + max(map(len, tracks), default=0).to_bytes(2, "little")
            + b"".join(offsets) + b"\x03\x00\x00\x00" * len(tracks) + b"".join(bodies))


def directory_sector(next_track, next_sector, name):
    data = bytearray(256)
    data[:2] = bytes((next_track, next_sector))
    data[2:5] = b"\x82\x01\x00"
    data[5:21] = name.encode().ljust(16, b"\xa0")
    data[30:32] = b"\x01\x00"
    return bytes(data)


def filesystem(name="TEST", order=(5, 1)):
    bam = bytearray(256)
    bam[:2] = bytes((18 if order else 0, order[0] if order else 0))
    bam[0x90:0xA0] = b"SYNTHETIC".ljust(16, b"\xa0")
    bam[0xA2:0xA4] = b"AB"
    bam[0xA5:0xA7] = b"2A"
    records = [record(18, 0, bytes(bam))]
    for i, sector in enumerate(order):
        following = (18, order[i + 1]) if i + 1 < len(order) else (0, 255)
        records.append(record(18, sector, directory_sector(*following, name if i == 0 else "SECOND")))
    payload = bytes((0, len(PAYLOAD) + 1)) + PAYLOAD
    records.append(record(1, 0, payload.ljust(256, b"\x00")))
    return container(track_bytes(*records))


class SyntheticFiles(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="g64-hardening-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def read_image(self, raw):
        path = self.root / "fixture.g64"
        path.write_bytes(raw)
        return g.read_g64(path)

    def run_cli(self, source, output=None):
        args = [str(READER), str(source), "--extract", "TEST", "--json"]
        if output is not None:
            args += ["--output", str(output)]
        report = io.StringIO()
        with patch.object(sys, "argv", args), contextlib.redirect_stdout(report):
            g.main()
        return json.loads(report.getvalue())


class OutputIdentityTests(SyntheticFiles):
    def setUp(self):
        super().setUp()
        self.source = self.root / "master.g64"
        self.original = filesystem()
        self.source.write_bytes(self.original)

    def assert_refused(self, output, source=None):
        caught = None
        try:
            self.run_cli(source or self.source, output)
        except g.G64Error as error:
            caught = error
        # This checks the real input bytes, not merely whether a guard was called.
        after = self.source.read_bytes()
        self.assertEqual(hashlib.sha256(after).hexdigest(), hashlib.sha256(self.original).hexdigest(),
                         f"master overwritten: {len(self.original)} -> {len(after)} bytes")
        self.assertIsNotNone(caught, "output/input identity was not refused")
        self.assertIn("output path identifies the input image", str(caught))

    def test_same_path_preserves_input(self):
        self.assert_refused(self.source)

    def test_relative_same_path_preserves_input(self):
        previous = Path.cwd()
        try:
            os.chdir(self.root)
            self.assert_refused(Path("master.g64"))
        finally:
            os.chdir(previous)

    def test_dotdot_alias_preserves_input(self):
        (self.root / "sub").mkdir()
        self.assert_refused(self.root / "sub" / ".." / "master.g64")

    def test_output_symlink_preserves_input(self):
        output = self.root / "alias.prg"
        output.symlink_to(self.source)
        self.assert_refused(output)
        self.assertTrue(output.is_symlink())

    def test_input_symlink_preserves_input(self):
        source = self.root / "source-link.g64"
        source.symlink_to(self.source)
        self.assert_refused(self.source, source)

    def test_parent_symlink_preserves_input(self):
        directory = self.root / "linked"
        directory.symlink_to(self.root, target_is_directory=True)
        self.assert_refused(directory / "master.g64")

    def test_output_hardlink_preserves_input(self):
        output = self.root / "alias.prg"
        os.link(self.source, output)
        self.assert_refused(output)
        self.assertTrue(output.samefile(self.source))

    def test_default_output_alias_preserves_input(self):
        os.link(self.source, self.root / "TEST.prg")
        previous = Path.cwd()
        try:
            os.chdir(self.root)
            self.assert_refused(None)
        finally:
            os.chdir(previous)

    def test_distinct_new_output_and_parent_allowed(self):
        output = self.root / "new" / "derived.prg"
        result = self.run_cli(self.source, output)
        self.assertEqual(output.read_bytes(), PAYLOAD)
        self.assertEqual(self.source.read_bytes(), self.original)
        self.assertEqual(result["extraction"]["byteCount"], len(PAYLOAD))

    def test_distinct_existing_same_basename_allowed(self):
        output = self.root / "other" / self.source.name
        output.parent.mkdir()
        output.write_bytes(b"old derivative")
        self.run_cli(self.source, output)
        self.assertEqual(output.read_bytes(), PAYLOAD)
        self.assertEqual(self.source.read_bytes(), self.original)

    def test_symlink_to_separate_derivative_allowed(self):
        target = self.root / "derivative.prg"
        target.write_bytes(b"old derivative")
        output = self.root / "alias.prg"
        output.symlink_to(target)
        self.run_cli(self.source, output)
        self.assertEqual(target.read_bytes(), PAYLOAD)
        self.assertEqual(self.source.read_bytes(), self.original)

    def test_dangling_symlink_to_separate_derivative_allowed(self):
        target = self.root / "derivative.prg"
        output = self.root / "alias.prg"
        output.symlink_to(target)
        self.run_cli(self.source, output)
        self.assertEqual(target.read_bytes(), PAYLOAD)
        self.assertEqual(self.source.read_bytes(), self.original)

    def test_hardlink_to_separate_derivative_allowed(self):
        target = self.root / "derivative.prg"
        target.write_bytes(b"old derivative")
        output = self.root / "alias.prg"
        os.link(target, output)
        self.run_cli(self.source, output)
        self.assertEqual(target.read_bytes(), PAYLOAD)
        self.assertEqual(self.source.read_bytes(), self.original)


class TableOverlapTests(SyntheticFiles):
    def overlap_image(self, offset):
        raw = bytearray(600)
        raw[:12] = b"GCR-1541\x00\x01\x00\x02"
        raw[12:16] = offset.to_bytes(4, "little")
        raw[16:20] = b"\x03\x00\x00\x00"
        return bytes(raw)

    def test_header_overlap_refused(self):
        with self.assertRaisesRegex(g.G64Error, "overlaps G64 header/track/speed tables"):
            self.read_image(self.overlap_image(8))

    def test_offset_table_overlap_refused(self):
        with self.assertRaisesRegex(g.G64Error, "overlaps G64 header/track/speed tables"):
            self.read_image(self.overlap_image(12))

    def test_speed_table_overlap_refused(self):
        with self.assertRaisesRegex(g.G64Error, "overlaps G64 header/track/speed tables"):
            self.read_image(self.overlap_image(16))

    def test_length_prefix_straddling_boundary_refused(self):
        with self.assertRaisesRegex(g.G64Error, "overlaps G64 header/track/speed tables"):
            self.read_image(self.overlap_image(19))

    def test_exact_table_end_empty_record_allowed(self):
        sectors, metadata = self.read_image(container(b""))
        self.assertEqual(sectors, {})
        self.assertEqual(metadata["slots"][0]["offset"], 20)
        self.assertEqual(metadata["slots"][0]["length"], 0)

    def test_absent_offset_zero_allowed(self):
        sectors, metadata = self.read_image(self.overlap_image(0))
        self.assertEqual((sectors, metadata["slots"]), ({}, []))

    def test_exact_table_end_nonempty_record_allowed(self):
        sectors, metadata = self.read_image(container(track_bytes(record())))
        self.assertEqual(sectors[1, 0].data, bytes(range(256)))
        self.assertEqual(metadata["slots"][0]["offset"], 20)


class DuplicateEvidenceTests(SyntheticFiles):
    def check_duplicates(self, candidates, selected_index, same_slot=False):
        records = [record(payload=payload, header_ok=h, data_ok=d) for payload, h, d in candidates]
        tracks = [track_bytes(*records)] if same_slot else [track_bytes(item) for item in records]
        sectors, meta = self.read_image(container(*tracks))
        selected = sectors[1, 0]
        self.assertEqual(selected.data, candidates[selected_index][0])
        self.assertEqual(selected.physical_slot, 0 if same_slot else selected_index)
        self.assertEqual(selected.header_bit, 16 + 2712 * selected_index if same_slot else 16)
        evidence = meta["duplicates"]
        others = [i for i in range(len(candidates)) if i != selected_index]
        self.assertEqual(len(evidence), len(others))
        for item, duplicate_index in zip(evidence, others):
            with self.subTest(selected=selected_index, duplicate=duplicate_index):
                self.assertEqual(item["keptSlot"], selected.physical_slot)
                self.assertEqual(item["duplicateSlot"], 0 if same_slot else duplicate_index)
                for field, index in (("selected", selected_index), ("duplicate", duplicate_index)):
                    payload, h, d = candidates[index]
                    self.assertEqual(item[field], {
                        "physicalSlot": 0 if same_slot else index,
                        "headerBit": 16 + 2712 * index if same_slot else 16,
                        "dataBit": 122 + 2712 * index if same_slot else 122,
                        "headerChecksumValid": h, "dataChecksumValid": d,
                        "diskIdHex": "4142", "payloadSha256": hashlib.sha256(payload).hexdigest(),
                    })
                a, b = candidates[selected_index], candidates[duplicate_index]
                self.assertEqual(item["payloadRelation"], "identical" if a[0] == b[0] else "different")
                self.assertEqual(item["conflictingValidPayloads"],
                                 all(a[1:]) and all(b[1:]) and a[0] != b[0])
        return sectors, meta

    def test_invalid_then_valid_reports_selected_not_discarded(self):
        self.check_duplicates([(b"A" * 256, False, True), (b"B" * 256, True, True)], 1)

    def test_valid_then_invalid_retains_valid(self):
        self.check_duplicates([(b"A" * 256, True, True), (b"B" * 256, True, False)], 0)

    def test_identical_valid_not_conflicting(self):
        self.check_duplicates([(b"A" * 256, True, True)] * 2, 0)

    def test_conflicting_valid_forward_and_reverse(self):
        for payloads in ((b"A" * 256, b"B" * 256), (b"B" * 256, b"A" * 256)):
            with self.subTest(first=payloads[0][:1]):
                self.check_duplicates([(p, True, True) for p in payloads], 0)

    def test_three_candidates_all_evidence_names_final_selection(self):
        self.check_duplicates([(b"A" * 256, False, True), (b"B" * 256, True, False),
                               (b"C" * 256, True, True)], 2)

    def test_all_invalid_last_retained_and_still_refused(self):
        sectors, _ = self.check_duplicates([(b"A" * 256, False, True),
                                            (b"B" * 256, True, False)], 1)
        with self.assertRaisesRegex(g.G64Error, "invalid data checksum"):
            g.require_sector(sectors, 1, 0)

    def test_same_slot_duplicates_have_distinct_bit_coordinates(self):
        self.check_duplicates([(b"A" * 256, True, True), (b"B" * 256, True, True)], 0, True)

    def test_three_candidates_only_valid_difference_is_conflict(self):
        self.check_duplicates([(b"A" * 256, False, True), (b"B" * 256, True, True),
                               (b"C" * 256, True, True)], 1)


class DirectoryOrderTests(SyntheticFiles):
    def test_nonascending_chain_and_entries_keep_traversal_order(self):
        sectors, _ = self.read_image(filesystem(order=(5, 1)))
        disk, entries = g.read_directory(sectors)
        self.assertEqual(disk["directoryChain"], ["18/5", "18/1"])
        self.assertEqual([(item["name"], item["directorySector"]) for item in entries],
                         [("TEST", 5), ("SECOND", 1)])

    def test_single_sector_directory(self):
        sectors, _ = self.read_image(filesystem(order=(5,)))
        disk, entries = g.read_directory(sectors)
        self.assertEqual(disk["directoryChain"], ["18/5"])
        self.assertEqual(len(entries), 1)

    def test_empty_directory(self):
        sectors, _ = self.read_image(filesystem(order=()))
        disk, entries = g.read_directory(sectors)
        self.assertEqual((disk["directoryChain"], entries), ([], []))

    def test_directory_loop_remains_refused(self):
        sectors, _ = self.read_image(filesystem())
        original = sectors[18, 1]
        sectors[18, 1] = g.DecodedSector(18, 1, b"\x12\x05" + original.data[2:],
                                        original.physical_slot, original.header_bit, original.data_bit,
                                        True, True, original.disk_id_hex)
        with self.assertRaisesRegex(g.G64Error, "directory chain loop at T18/S5"):
            g.read_directory(sectors)


if __name__ == "__main__":
    unittest.main()
