#!/usr/bin/env python3
"""Synthetic checks for exact 6502 anchor discovery."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(TOOLS))

import anchor_scan6502 as scan  # noqa: E402
import exact_anchor_controls6502 as controls  # noqa: E402

LOOP_ZP = bytes.fromhex("A5 10 18 65 11 85 12 A5 12 C9 20 D0 F3")
LOOP_ABS = bytes.fromhex(
    "AD 34 12 18 6D 35 12 8D 36 12 AD 36 12 C9 20 D0 EF"
)


class InstructionViewTest(unittest.TestCase):
    def test_relational_view_matches_relocation_and_width_change(self) -> None:
        left = scan.decode_window(LOOP_ZP, 0, 7, base_address=0x2000)
        right = scan.decode_window(LOOP_ABS, 0, 7, base_address=0x9000)
        assert left is not None and right is not None
        self.assertNotEqual(scan.literal_tokens(left), scan.literal_tokens(right))
        self.assertEqual(scan.relational_tokens(left), scan.relational_tokens(right))

    def test_immediate_values_remain_distinct_in_every_view(self) -> None:
        left = scan.decode_window(bytes.fromhex("A9 08 18 69 01 85 10"), 0, 4, base_address=0)
        right = scan.decode_window(bytes.fromhex("A9 09 18 69 01 85 10"), 0, 4, base_address=0)
        assert left is not None and right is not None
        self.assertNotEqual(scan.relational_tokens(left), scan.relational_tokens(right))
        self.assertNotEqual(scan.shape_tokens(left), scan.shape_tokens(right))

    def test_does_not_decode_through_early_return(self) -> None:
        self.assertIsNone(
            scan.decode_window(bytes.fromhex("A9 01 60 A9 02 85 10"), 0, 4, base_address=0)
        )
        accepted = scan.decode_window(bytes.fromhex("A9 01 85 10 60"), 0, 3, base_address=0)
        self.assertIsNotNone(accepted)

    def test_known_mask_rejects_window_touching_unknown_byte(self) -> None:
        data = bytes.fromhex("A9 01 85 10 60")
        mask = bytearray(b"\xFF" * len(data))
        mask[3] = 0
        self.assertIsNone(
            scan.decode_window(data, 0, 3, base_address=0, known_mask=bytes(mask))
        )


class AnchorClusteringTest(unittest.TestCase):
    def test_overlapping_relocated_windows_collapse_on_diagonal(self) -> None:
        left_windows, _ = scan.scan_region(
            LOOP_ZP,
            5,
            base_address=0,
            known_mask=None,
            min_unique_mnemonics=3,
        )
        right_windows, _ = scan.scan_region(
            LOOP_ABS,
            5,
            base_address=0,
            known_mask=None,
            min_unique_mnemonics=3,
        )
        anchors = scan.relational_anchors(
            scan.index_view(left_windows, "relational"),
            scan.index_view(right_windows, "relational"),
            max_occurrences=64,
            max_pairs=4096,
        )
        self.assertTrue(anchors)
        clusters = scan.cluster_anchors(anchors)
        self.assertLess(len(clusters), len(anchors) + 1)


class ControlGenerationTest(unittest.TestCase):
    def test_token_shuffle_preserves_each_window_vocabulary_but_changes_order(self) -> None:
        windows, _ = scan.scan_region(
            LOOP_ZP,
            6,
            base_address=0,
            known_mask=None,
            min_unique_mnemonics=3,
        )
        self.assertTrue(windows)
        shuffled = controls.token_shuffle_index([windows[0]], seed=0)
        fingerprint = next(iter(shuffled))
        self.assertCountEqual(windows[0].relational, fingerprint)
        self.assertNotEqual(windows[0].relational, fingerprint)


if __name__ == "__main__":
    unittest.main()
