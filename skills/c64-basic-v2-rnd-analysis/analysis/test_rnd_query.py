#!/usr/bin/env python3
from __future__ import annotations

import argparse
import contextlib
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path

import rnd_query
import turn_schedule


class RndQueryTests(unittest.TestCase):
    def test_fixed_point_rank_round_trip(self) -> None:
        seed = bytes.fromhex("7e 2a d3 ab c6")
        rank = rnd_query.domain.rank(rnd_query.state_from_bytes(seed))
        self.assertEqual(rank, 1_708_815_729)
        self.assertEqual(rnd_query.domain.unrank(rank).bytes, seed)

    @unittest.skipUnless(
        (rnd_query.DEFAULT_RUN_DIR / "metadata.bin").is_file(),
        "external 10.94-GiB metadata absent; set C64_RND_RUN_DIR for this gate",
    )
    def test_fixed_point_classification(self) -> None:
        self.assertEqual(
            rnd_query.classify(bytes.fromhex("7e 2a d3 ab c6"), rnd_query.DEFAULT_RUN_DIR),
            {"rank": 1_708_815_729, "mu": 0, "lambda": 1, "total": 1},
        )

    def test_negative_fac_mapping_and_preimages(self) -> None:
        fac = rnd_query.negative.NegativeFac(0x9F, 0xF1EAB42A)
        seed = rnd_query.negative.fac_to_seed(fac)
        self.assertEqual(seed.bytes, bytes.fromhex("7e 2a d3 ab c6"))
        self.assertEqual(len(rnd_query.negative.seed_preimages(seed)), 64)

    def test_component_summary_excludes_cycle_nodes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "component-depth.csv"
            path.write_text(
                "lambda,mu,count\n"
                "3,0,3\n"
                "3,1,2\n"
                "3,4,1\n"
                "7,0,7\n"
                "7,2,3\n",
                encoding="utf-8",
            )
            self.assertEqual(
                rnd_query.component_rows(path),
                [
                    {"loop": 1, "lambda": 3, "transient": 3,
                     "medianMu": 1, "maxMu": 4, "basin": 6},
                    {"loop": 2, "lambda": 7, "transient": 3,
                     "medianMu": 2, "maxMu": 2, "basin": 10},
                ],
            )

    def test_retained_ti_ranges(self) -> None:
        for first, last, expected in ((1, 60, 43), (61, 3600, 2894), (5184000, 5184000, 1)):
            with self.subTest(first=first, last=last):
                counts = rnd_query.ti_range_counts(first, last)
                self.assertEqual(counts[58078], expected)
                self.assertEqual(sum(counts.values()), last - first + 1)

    def test_unavailable_ti_ranges(self) -> None:
        for first, last, message in ((61, 3599, "not retained"), (60, 3600, "not retained"),
                                     (0, 60, "timer path"), (61, 60, "FIRST <= LAST")):
            with self.subTest(first=first, last=last), self.assertRaisesRegex(ValueError, message):
                rnd_query.ti_range_counts(first, last)


class TurnScheduleTests(unittest.TestCase):
    def test_same_orbit_different_tested_draws(self) -> None:
        orbit = json.loads(turn_schedule.ORBIT.read_text())
        for extra, initial, cycle, discarded, hits in (
            (False, [1, 2, 3, 4], [5, 6, 7, 8, 9, 10, 11], [], [9]),
            (True, [1, 2, 3], [5, 6, 7, 8, 10], [4, 9, 11], []),
        ):
            with self.subTest(extra=extra):
                prefix, loop = turn_schedule.replay(orbit, extra_below_half=extra)
                self.assertEqual([t.tested for t in prefix], initial)
                self.assertEqual([t.tested for t in loop], cycle)
                turns = prefix + loop
                self.assertEqual([t.discarded for t in turns if t.discarded is not None], discarded)
                self.assertEqual([t.tested for t in turns if t.encounter], hits)

    def test_truncated_orbit_is_not_a_turn_frequency(self) -> None:
        orbit = json.loads(turn_schedule.ORBIT.read_text())
        orbit["nodes"].pop()
        with self.assertRaisesRegex(ValueError, "undetermined"):
            turn_schedule.replay(orbit, extra_below_half=True)


class RndResultVerificationTests(unittest.TestCase):
    """Use only bundled compact outputs, never external production metadata."""

    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.run_dir = Path(temporary.name)
        bundled = Path(__file__).resolve().parent / "scratch/full-production"
        for name in (
            "checkpoint.bin", "cycle-components.csv", "hist-lambda.csv",
            "hist-mu.csv", "hist-total.csv", "summary.json", "final-output-sha256.txt",
        ):
            shutil.copyfile(bundled / name, self.run_dir / name)
        self.manifest = self.run_dir / "final-output-sha256.txt"
        self.lines = self.manifest.read_text(encoding="utf-8").splitlines()

    def verify(self) -> str:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            rnd_query.command_verify(argparse.Namespace(run_dir=self.run_dir))
        return output.getvalue()

    def test_bundled_outputs_verify(self) -> None:
        self.assertIn("verified 6 compact outputs and complete checkpoint", self.verify())

    def test_manifest_order_does_not_matter(self) -> None:
        self.manifest.write_text("\n".join(reversed(self.lines)) + "\n", encoding="utf-8")
        self.assertIn("verified 6 compact outputs and complete checkpoint", self.verify())

    def test_empty_manifest_is_rejected(self) -> None:
        self.manifest.write_text("", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "missing required compact outputs"):
            self.verify()

    def test_each_missing_required_output_is_rejected(self) -> None:
        for index, line in enumerate(self.lines):
            with self.subTest(missing=line.split(maxsplit=1)[1]):
                self.manifest.write_text(
                    "\n".join(self.lines[:index] + self.lines[index + 1:]) + "\n",
                    encoding="utf-8",
                )
                with self.assertRaisesRegex(ValueError, "missing required compact outputs"):
                    self.verify()

    def test_duplicate_entry_is_rejected(self) -> None:
        self.manifest.write_text("\n".join(self.lines + [self.lines[0]]) + "\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "duplicate compact output"):
            self.verify()

    def test_unexpected_entry_is_rejected(self) -> None:
        extra = self.lines[0].split()[0] + "  ../checkpoint.bin"
        self.manifest.write_text("\n".join(self.lines + [extra]) + "\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "unexpected compact output"):
            self.verify()

    def test_changed_content_is_rejected(self) -> None:
        with (self.run_dir / "summary.json").open("ab") as stream:
            stream.write(b"\n")
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            self.verify()


if __name__ == "__main__":
    unittest.main()
