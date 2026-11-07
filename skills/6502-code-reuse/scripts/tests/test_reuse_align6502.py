#!/usr/bin/env python3
"""Synthetic checks for boundary correction, affine extension, and evidence."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))

import anchor_scan6502 as anchor  # noqa: E402
import reuse_align6502 as align  # noqa: E402


def tokens(data: bytes, count: int):
    instructions = anchor.decode_window(data, 0, count, base_address=0)
    assert instructions is not None
    return anchor.relational_tokens(instructions), anchor.shape_tokens(instructions)


class AffineAlignmentTest(unittest.TestCase):
    def test_tolerates_insertions_and_changed_immediate_but_exposes_them(self) -> None:
        left = bytes.fromhex(
            "A5 10 29 0F 85 11 A6 12 E8 86 12 C9 08 D0 F3 60"
        )
        right = bytes.fromhex(
            "AD 00 40 29 0F 8D 01 40 48 A9 FF 68 AE 02 40 E8 "
            "8E 02 40 C9 09 D0 EC 60"
        )
        left_rel, left_shape = tokens(left, 9)
        right_rel, right_shape = tokens(right, 12)
        result = align.affine_local_align(left_rel, right_rel, left_shape, right_shape)
        metrics = align.alignment_metrics(result)
        self.assertGreaterEqual(metrics["supportingPairs"], 9)
        self.assertEqual(metrics["compatibleChangedOperand"], 1)
        self.assertEqual(metrics["gaps"], 3)
        self.assertEqual(sum(column.score for column in result.columns), result.score)

    def test_short_common_idiom_is_not_probable_routine(self) -> None:
        idiom = bytes.fromhex("48 8A 48 98 48 78 D8 18")
        relational, shape = tokens(idiom, 8)
        result = align.affine_local_align(relational, relational, shape, shape)
        metrics = align.alignment_metrics(result)
        self.assertEqual(metrics["relationalExact"], 8)
        self.assertEqual(align.classify(metrics, 1), "candidate-similarity")

    def test_embedded_common_idiom_does_not_extend_to_probable(self) -> None:
        idiom = bytes.fromhex("48 8A 48 98 48 78 D8 18")
        left_data = b"\x00" * 16 + idiom + b"\x00" * 16
        right_data = b"\x00" * 32 + idiom + b"\x00" * 16
        left_windows, _ = anchor.scan_region(
            left_data, 8, base_address=0, known_mask=None, min_unique_mnemonics=4
        )
        right_windows, _ = anchor.scan_region(
            right_data, 8, base_address=0, known_mask=None, min_unique_mnemonics=4
        )
        seeds = anchor.relational_anchors(
            anchor.index_view(left_windows, "relational"),
            anchor.index_view(right_windows, "relational"),
            max_occurrences=64,
            max_pairs=4096,
        )
        clusters = anchor.cluster_anchors(seeds)
        self.assertEqual(len(clusters), 1)
        left_region = {
            "metadata": {"id": "left", "baseAddress": 0},
            "data": left_data,
            "knownMask": None,
        }
        right_region = {
            "metadata": {"id": "right", "baseAddress": 0},
            "data": right_data,
            "knownMask": None,
        }
        match = align.extend_cluster(
            clusters[0], left_region, right_region, max_instructions=64, max_bytes=128
        )
        assert match is not None
        self.assertEqual(match.classification, "candidate-similarity")
        self.assertLess(match.metrics["pairedInstructions"], align.PROBABLE_MIN_PAIRED)


class BoundaryCorrectionTest(unittest.TestCase):
    def test_recovers_real_boundary_suppressed_by_diversity_filter(self) -> None:
        # Three repeated LDA/EOR/STA groups followed by RTS. At the correct
        # boundary there are only three unique mnemonics; starting one byte
        # late creates a misleading but diverse legal decode.
        routine = bytes.fromhex(
            "AD BE 0D 49 1E 8D BE 0D "
            "AD 3E 0E 49 1E 8D 3E 0E "
            "AD BE 0E 49 1E 8D BE 0E 60"
        )
        left_windows, _ = anchor.scan_region(
            routine,
            8,
            base_address=0,
            known_mask=None,
            min_unique_mnemonics=4,
        )
        right_windows, _ = anchor.scan_region(
            routine,
            8,
            base_address=0x1000,
            known_mask=None,
            min_unique_mnemonics=4,
        )
        anchors = anchor.relational_anchors(
            anchor.index_view(left_windows, "relational"),
            anchor.index_view(right_windows, "relational"),
            max_occurrences=64,
            max_pairs=4096,
        )
        clusters = anchor.cluster_anchors(anchors)
        self.assertTrue(clusters)
        self.assertEqual(align.choose_seed(clusters[0]).left.start, 1)

        region = {
            "metadata": {"id": "synthetic", "baseAddress": 0},
            "data": routine,
            "knownMask": None,
        }
        match = align.extend_cluster(
            clusters[0], region, region, max_instructions=64, max_bytes=128
        )
        assert match is not None
        self.assertEqual(match.left_shift, 1)
        self.assertEqual(match.right_shift, 1)
        self.assertEqual(match.left_start, 0)
        self.assertEqual(match.right_start, 0)
        self.assertEqual(match.metrics["relationalExact"], 10)


if __name__ == "__main__":
    unittest.main()
