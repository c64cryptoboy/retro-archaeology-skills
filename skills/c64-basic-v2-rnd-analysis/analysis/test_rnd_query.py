#!/usr/bin/env python3
from __future__ import annotations

import argparse
import contextlib
import io
import shutil
import tempfile
import unittest
from pathlib import Path

import rnd_query


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
