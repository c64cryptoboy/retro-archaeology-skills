#!/usr/bin/env python3

from __future__ import annotations

import collections
import csv
import json
import mmap
import os
import struct
import subprocess
import tempfile
import unittest
from pathlib import Path

import run_full_histogram

HERE = Path(__file__).resolve().parent


def synthetic_next(value: int, size: int = 1024) -> int:
    if value == 0:
        return 1
    if value == 1:
        return 2
    if value == 2:
        return 0
    if value < size // 2:
        return value // 2
    if value == size // 2:
        return value + 1
    if value == size // 2 + 1:
        return value - 1
    return size // 2 + (value - size // 2) // 2


def oracle_histograms(size: int = 1024) -> dict[str, dict[int, int]]:
    mus, lambdas = [], []
    for start in range(size):
        seen: dict[int, int] = {}
        current = start
        while current not in seen:
            seen[current] = len(seen)
            current = synthetic_next(current, size)
        mu = seen[current]
        mus.append(mu)
        lambdas.append(len(seen) - mu)
    return {
        "mu": dict(collections.Counter(mus)),
        "lambda": dict(collections.Counter(lambdas)),
        "total": dict(collections.Counter(a + b for a, b in zip(mus, lambdas))),
    }


def read_histogram(path: Path) -> dict[int, int]:
    with path.open() as source:
        return {
            int(row["value"]): int(row["count"])
            for row in csv.DictReader(source)
        }


class FullRunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.build = tempfile.TemporaryDirectory(prefix="rnd-full-test-build-")
        cls.binary = Path(cls.build.name) / "full-rnd-synthetic"
        subprocess.run(
            [
                "gcc", "-std=gnu11", "-O2", "-Wall", "-Wextra", "-Werror",
                "-DFULL_RUNNER_SYNTHETIC", "-DFULL_RUNNER_DOMAIN_SIZE=1024",
                str(HERE / "full_rnd_histogram.c"), "-o", str(cls.binary),
            ],
            check=True,
        )
        cls.oracle = oracle_histograms()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.build.cleanup()

    def invoke(self, workdir: Path, mode: str, *options: str,
               expected: int = 0) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            [str(self.binary), "ignored", "ignored", str(workdir), f"--{mode}",
             "--sparse", *options],
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, expected, result.stderr)
        return result

    def assert_complete_matches_oracle(self, workdir: Path) -> None:
        for name, expected in self.oracle.items():
            self.assertEqual(read_histogram(workdir / f"hist-{name}.csv"), expected)
        self.assertEqual(
            (workdir / "cycle-components.csv").read_text(),
            "lambda,cycle_nodes,component_count\n2,2,1\n3,3,1\n",
        )
        summary = json.loads((workdir / "summary.json").read_text())
        self.assertTrue(summary["complete"])
        self.assertEqual(summary["classifiedStates"], 1024)
        self.assertEqual(summary["metadataBytes"], 4096)

    def test_complete_run_matches_independent_oracle(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rnd-full-complete-") as parent:
            workdir = Path(parent) / "run"
            self.invoke(workdir, "create", "--checkpoint-every=333")
            self.assert_complete_matches_oracle(workdir)

    def test_graceful_stop_and_resume(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rnd-full-resume-") as parent:
            workdir = Path(parent) / "run"
            self.invoke(workdir, "create", "--checkpoint-every=50",
                        "--stop-after-scans=123", expected=3)
            self.invoke(workdir, "resume", "--checkpoint-every=200")
            self.assert_complete_matches_oracle(workdir)

    def test_abrupt_path_marker_recovery(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rnd-full-abort-") as parent:
            workdir = Path(parent) / "run"
            self.invoke(workdir, "create", "--abort-after-transitions=2", expected=99)
            result = self.invoke(workdir, "resume", "--checkpoint-every=200")
            self.assertIn("cleared_markers=2", result.stderr)
            self.assert_complete_matches_oracle(workdir)

    def test_partial_cycle_commit_recovery(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rnd-full-cycle-") as parent:
            workdir = Path(parent) / "run"
            self.invoke(workdir, "create", "--checkpoint-every=1",
                        "--stop-after-scans=1", expected=3)
            with (workdir / "metadata.bin").open("r+b") as metadata_file:
                metadata = mmap.mmap(metadata_file.fileno(), 0)
                metadata[4:8] = struct.pack("<I", 0xFF000002)
                metadata[8:12] = struct.pack("<I", 0xFF000003)
                metadata.flush()
                metadata.close()
            result = self.invoke(workdir, "resume", "--checkpoint-every=200")
            self.assertIn("cycle_repair components=1 cycle_nodes=3", result.stderr)
            self.assert_complete_matches_oracle(workdir)

    def test_checkpoint_corruption_is_refused(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rnd-full-checkpoint-") as parent:
            workdir = Path(parent) / "run"
            self.invoke(workdir, "create", "--stop-after-scans=1", expected=3)
            checkpoint = workdir / "checkpoint.bin"
            data = bytearray(checkpoint.read_bytes())
            data[-1] ^= 1
            checkpoint.write_bytes(data)
            result = subprocess.run(
                [str(self.binary), "x", "x", str(workdir), "--resume", "--sparse"],
                text=True, capture_output=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("invalid or incompatible checkpoint", result.stderr)

    def test_rom_hash_checker_refuses_modified_rom(self) -> None:
        valid = run_full_histogram.ROM_DIR / 'basic.bin'
        self.assertEqual(
            run_full_histogram.checked_rom(valid, run_full_histogram.BASIC_SHA256),
            run_full_histogram.BASIC_SHA256,
        )
        with tempfile.TemporaryDirectory(prefix="rnd-rom-check-") as directory:
            bad = Path(directory) / "bad.bin"
            data = bytearray(valid.read_bytes())
            data[0] ^= 1
            bad.write_bytes(data)
            with self.assertRaises(SystemExit):
                run_full_histogram.checked_rom(bad, run_full_histogram.BASIC_SHA256)


if __name__ == "__main__":
    unittest.main()
