#!/usr/bin/env python3
"""Regression checks for Stage 3 calibration and the frozen configuration."""

from __future__ import annotations

from copy import deepcopy
import subprocess
import json
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))

import calibrate_reuse6502 as calibration  # noqa: E402
import run_locked_reuse6502 as locked_run  # noqa: E402


from reuse_fixture import complete_calibration, manifest, routine, save


class CalibrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        temporary = tempfile.TemporaryDirectory()
        cls.addClassCleanup(temporary.cleanup)
        cls.root = Path(temporary.name)
        cls.report, cls.args = complete_calibration(cls.root)

    def test_common_idiom_remains_candidate_only(self) -> None:
        result = calibration.common_idiom_control()
        self.assertEqual(result["classification"], "candidate-similarity")
        self.assertEqual(result["metrics"]["pairedInstructions"], 8)

    def test_generic_lock_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            calibration_path = root / "calibration.json"
            lock_path = root / "lock.json"
            report = self.report
            self.assertTrue(report["stage3GatePassed"], report["gateFailures"])
            calibration_path.write_text(json.dumps(report))
            lock = calibration.build_lock(report, calibration_path, lock_path)
            lock_path.write_text(json.dumps(lock))
            self.assertTrue(lock["createdBeforeTargetComparison"])
            self.assertEqual(
                lock["format"], "6502-reuse-locked-investigation-configuration"
            )
            self.assertEqual(locked_run.verify_lock(lock_path), lock)

    def assert_refused(self, report, reason):
        self.assertFalse(report["stage3GatePassed"])
        self.assertIn(reason, "; ".join(report["gateFailures"]))
        with self.assertRaisesRegex(ValueError, "did not pass"):
            calibration.build_lock(report, self.root / "unused.json", self.root / "unused.lock")

    def test_each_required_control_and_sensitivity(self):
        known, controls_path, unrelated, variants = self.args
        for kind in calibration.CONTROL_KINDS:
            controls = json.loads(controls_path.read_text())
            for pair in controls["comparisons"]:
                pair["trials"] = [t for t in pair["trials"] if t["kind"] != kind]
            with self.subTest(kind=kind):
                path = save(self.root / "missing-kind.json", controls)
                self.assert_refused(calibration.calibrate(known, path, unrelated, variants), kind)
        for variant in variants:
            with self.subTest(variant=variant.name):
                others = [v for v in variants if v != variant]
                self.assert_refused(calibration.calibrate(known, controls_path, unrelated, others), "sensitivity")
        self.assert_refused(calibration.calibrate(known, controls_path, [], variants), "missing unrelated")
        self.assert_refused(calibration.calibrate(known, controls_path, [known], variants), "contains probable")
        self.assert_refused(calibration.calibrate(known, controls_path, [variants[0]], variants), "primary settings")
        variant = json.loads(variants[0].read_text())
        variant["right"] = json.loads(unrelated[0].read_text())["right"]
        other_pair = save(self.root / "other-pair.json", variant)
        self.assert_refused(calibration.calibrate(known, controls_path, unrelated, [other_pair, *variants[1:]]),
                            "sensitivity")

    def test_incomplete_cli_writes_exploratory_report_not_lock(self):
        out, lock = self.root / "incomplete.json", self.root / "incomplete.lock"
        command = [sys.executable, TOOLS / "calibrate_reuse6502.py", *self.args[:2], out, "--lock", lock]
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing unrelated", result.stderr)
        self.assertFalse(json.loads(out.read_text())["stage3GatePassed"])
        self.assertFalse(lock.exists())

    def test_verify_requires_evidence_tool_set_and_bound_configuration(self):
        source = save(self.root / "source.json", self.report)
        path = self.root / "verify.lock"
        original = calibration.build_lock(self.report, source, path)
        for changed in (
            {"sourceCalibration": {}}, {"toolSha256": {}}, {"analysisConfiguration": {}},
            {"version": 1}, {"sourceCalibration": {"path": source.name, "sha256": "0"*64}},
        ):
            with self.subTest(field=next(iter(changed))):
                save(path, {**original, **changed})
                with self.assertRaises(locked_run.LockedRunError):
                    locked_run.verify_lock(path)

        # A matching digest and a pass flag cannot rescue an incomplete report.
        bad = deepcopy(self.report)
        bad["knownPositive"]["sensitivityRuns"] = []
        save(source, bad)
        original["sourceCalibration"]["sha256"] = locked_run.digest(source)
        save(path, original)
        with self.assertRaisesRegex(ValueError, "did not pass"):
            locked_run.verify_lock(path)

    def test_strong_counts_full_matches_not_locations_or_common_prefixes(self):
        lock = self.report["lockedConfiguration"]
        primary = json.loads(self.args[0].read_text())
        strong = locked_run.overall_evidence(primary, lock)
        self.assertEqual(strong["distinctProbableFamilies"], 3)
        self.assertEqual(strong["classification"], "strong-shared-code-lineage")
        copies = manifest(self.root, "copies", b"\x02".join([routine(0)] * 3))
        report = calibration.align.analyze_manifests(copies, copies, max_seed_clusters=50)
        limited = locked_run.overall_evidence(report, lock)
        self.assertGreaterEqual(limited["probableSharedRoutines"], 3)
        self.assertGreaterEqual(limited["uniqueLeftBytes"], 256)
        self.assertEqual(limited["distinctProbableFamilies"], 1)
        self.assertEqual(limited["classification"], "limited-shared-routine-evidence")
        self.assertLess(limited["familyRepresentativeTotals"]["uniqueLeftBytes"], 256)


if __name__ == "__main__":
    unittest.main()
