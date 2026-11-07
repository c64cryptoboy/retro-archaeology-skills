import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from calibrate_reuse6502 import build_lock
from make_region_manifest6502 import create_manifest
from reuse_align6502 import analyze_manifests
from run_locked_reuse6502 import run_locked


LEFT = bytes.fromhex(
    "a510 290f 8511 a612 e8 8612 c908 d0f3 "
    "a000 b120 8513 c8 b120 8514 a513 18 6514 8515 60"
)
RIGHT = bytes.fromhex(
    "ad0040 290f 8d0140 ae0240 e8 8e0240 c908 d0f0 "
    "a000 b150 8d0340 c8 b150 8d0440 ad0340 18 6d0440 8d0540 60"
)


class EndToEndSyntheticTest(unittest.TestCase):
    def test_raw_manifests_find_probable_relocated_routine(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            left_raw = root / "left.bin"
            right_raw = root / "right.bin"
            left_raw.write_bytes(LEFT)
            right_raw.write_bytes(RIGHT)
            create_manifest(left_raw, root / "left", "left-main", base_address=0x2000)
            create_manifest(right_raw, root / "right", "right-main", base_address=0x8000)
            report = analyze_manifests(
                root / "left/regions.json",
                root / "right/regions.json",
                seed_instruction_count=8,
                max_seed_clusters=50,
                max_reported_matches=20,
            )
            aggregate = report["comparisons"][0]["aggregate"]
            self.assertGreaterEqual(aggregate["probableSharedRoutines"], 1)
            self.assertGreaterEqual(aggregate["uniqueLeftBytes"], len(LEFT) - 1)
            match = report["comparisons"][0]["matches"][0]
            self.assertGreaterEqual(match["metrics"]["relationalExact"], 16)
            self.assertEqual(match["metrics"]["different"], 0)

            tool_hashes = {
                name: hashlib.sha256((SCRIPTS / name).read_bytes()).hexdigest()
                for name in (
                    "anchor_scan6502.py",
                    "reuse_align6502.py",
                    "exact_anchor_controls6502.py",
                    "region_manifest.py",
                )
            }
            calibration = {
                "stage3GatePassed": True,
                "lockedConfiguration": {
                    "version": 1,
                    "decoderProfile": "shared official NMOS 6502 subset",
                    "analysisConfiguration": report["configuration"],
                    "comparisonInterpretation": {
                        "strongSharedCodeLineage": {
                            "minimumProbableSharedRoutines": 3,
                            "minimumUniqueBytesEachSide": 256,
                            "minimumSupportingInstructionPairs": 48,
                        },
                        "limitedSharedRoutineEvidence": {
                            "minimumProbableSharedRoutines": 1
                        },
                        "candidateOnly": {
                            "minimumCandidateSimilarities": 1,
                            "maximumProbableSharedRoutines": 0,
                        },
                    },
                    "toolSha256": tool_hashes,
                },
            }
            calibration_path = root / "calibration.json"
            lock_path = root / "lock.json"
            calibration_path.write_text(json.dumps(calibration))
            lock = build_lock(calibration, calibration_path, lock_path)
            lock_path.write_text(json.dumps(lock))
            locked_report = run_locked(
                lock_path,
                root / "left/regions.json",
                root / "right/regions.json",
            )
            self.assertEqual(
                locked_report["overallEvidence"]["classification"],
                "limited-shared-routine-evidence",
            )


if __name__ == "__main__":
    unittest.main()
