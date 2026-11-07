#!/usr/bin/env python3
"""Regression checks for Stage 3 calibration and the frozen configuration."""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(TOOLS))

import calibrate_reuse6502 as calibration  # noqa: E402
import run_locked_reuse6502 as locked_run  # noqa: E402


class CalibrationTest(unittest.TestCase):
    def test_common_idiom_remains_candidate_only(self) -> None:
        result = calibration.common_idiom_control()
        self.assertEqual(result["classification"], "candidate-similarity")
        self.assertEqual(result["metrics"]["pairedInstructions"], 8)

    def test_generic_lock_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            calibration_path = root / "calibration.json"
            lock_path = root / "lock.json"
            report = {
                "stage3GatePassed": True,
                "lockedConfiguration": {
                    "version": 1,
                    "analysisConfiguration": {},
                    "comparisonInterpretation": {},
                    "toolSha256": {},
                },
            }
            calibration_path.write_text(json.dumps(report))
            lock = calibration.build_lock(report, calibration_path, lock_path)
            lock_path.write_text(json.dumps(lock))
            self.assertTrue(lock["createdBeforeTargetComparison"])
            self.assertEqual(
                lock["format"], "6502-reuse-locked-investigation-configuration"
            )
            self.assertEqual(locked_run.verify_lock(lock_path), lock)


if __name__ == "__main__":
    unittest.main()
