#!/usr/bin/env python3
"""Verify and run a frozen 6502 reuse configuration without retuning it."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import reuse_align6502 as align


class LockedRunError(ValueError):
    pass


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_lock(lock_path: Path) -> dict[str, Any]:
    lock = json.loads(lock_path.read_text())
    if lock.get("format") != "6502-reuse-locked-investigation-configuration":
        raise LockedRunError("not a locked 6502 reuse configuration")
    if not lock.get("createdBeforeTargetComparison"):
        raise LockedRunError("configuration lacks pre-target lock declaration")
    tool_dir = Path(__file__).resolve().parent
    mismatches = []
    for name, expected in lock.get("toolSha256", {}).items():
        path = tool_dir / name
        actual = digest(path) if path.is_file() else None
        if actual != expected:
            mismatches.append({"tool": name, "expected": expected, "actual": actual})
    if mismatches:
        raise LockedRunError(f"locked tool hash mismatch: {mismatches}")
    calibration = lock.get("sourceCalibration")
    if calibration:
        source = Path(calibration["path"])
        if not source.is_absolute():
            source = lock_path.parent / source
        if not source.is_file() or digest(source) != calibration["sha256"]:
            raise LockedRunError("source calibration hash mismatch")
    return lock


def union_size(intervals: list[tuple[int, int]]) -> int:
    if not intervals:
        return 0
    total = 0
    start, end = sorted(intervals)[0]
    for next_start, next_end in sorted(intervals)[1:]:
        if next_start <= end:
            end = max(end, next_end)
        else:
            total += end - start
            start, end = next_start, next_end
    return total + end - start


def overall_evidence(report: dict[str, Any], lock: dict[str, Any]) -> dict[str, Any]:
    probable = []
    candidates = []
    for comparison in report["comparisons"]:
        for match in comparison["matches"]:
            item = {"comparison": comparison, "match": match}
            if match["classification"] == "probable-shared-routine":
                probable.append(item)
            elif match["classification"] == "candidate-similarity":
                candidates.append(item)

    left_by_region: dict[str, list[tuple[int, int]]] = {}
    right_by_region: dict[str, list[tuple[int, int]]] = {}
    supporting = 0
    for item in probable:
        comparison, match = item["comparison"], item["match"]
        left_by_region.setdefault(comparison["leftRegion"], []).append(
            (match["leftStart"], match["leftEndExclusive"])
        )
        right_by_region.setdefault(comparison["rightRegion"], []).append(
            (match["rightStart"], match["rightEndExclusive"])
        )
        supporting += match["metrics"]["supportingPairs"]
    unique_left = sum(union_size(intervals) for intervals in left_by_region.values())
    unique_right = sum(union_size(intervals) for intervals in right_by_region.values())

    interpretation = lock["comparisonInterpretation"]
    strong = interpretation["strongSharedCodeLineage"]
    if (
        len(probable) >= strong["minimumProbableSharedRoutines"]
        and unique_left >= strong["minimumUniqueBytesEachSide"]
        and unique_right >= strong["minimumUniqueBytesEachSide"]
        and supporting >= strong["minimumSupportingInstructionPairs"]
    ):
        classification = "strong-shared-code-lineage"
    elif len(probable) >= interpretation["limitedSharedRoutineEvidence"]["minimumProbableSharedRoutines"]:
        classification = "limited-shared-routine-evidence"
    elif len(candidates) >= interpretation["candidateOnly"]["minimumCandidateSimilarities"]:
        classification = "candidate-only"
    else:
        classification = "no-detected-reuse-under-locked-configuration"

    return {
        "classification": classification,
        "probableSharedRoutines": len(probable),
        "candidateSimilarities": len(candidates),
        "uniqueLeftBytes": unique_left,
        "uniqueRightBytes": unique_right,
        "supportingInstructionPairs": supporting,
        "cautions": [
            "Similarity does not establish copying direction, authorship, or legal provenance.",
            "A null result is bounded by captured/resident bytes, supported opcodes, normalization, and edit thresholds.",
            "Counts use reported deduplicated matches; per-region aggregate fields remain available in the full report.",
        ],
    }


def run_locked(
    lock_path: Path,
    left_manifest: Path,
    right_manifest: Path,
) -> dict[str, Any]:
    lock = verify_lock(lock_path)
    config = lock["analysisConfiguration"]
    probable = config["classificationThresholds"]["probableSharedRoutine"]
    report = align.analyze_manifests(
        left_manifest,
        right_manifest,
        seed_instruction_count=config["seedInstructionCount"],
        min_unique_mnemonics=config["minUniqueMnemonics"],
        max_occurrences=config["maxOccurrencesPerRegion"],
        max_pairs=config["maxPairsPerFingerprint"],
        max_seed_clusters=config["maxSeedClusters"],
        max_instructions=config["maxInstructionsPerExtension"],
        max_bytes=config["maxBytesPerExtension"],
        max_reported_matches=100,
        probable_min_paired=probable["minimumPairedInstructions"],
    )
    if report["configuration"] != config:
        raise LockedRunError("runtime report configuration differs from locked configuration")
    report["lockedRun"] = {
        "lockPath": str(lock_path),
        "lockSha256": digest(lock_path),
        "verifiedToolSha256": lock["toolSha256"],
        "primaryConfiguration": True,
    }
    report["overallEvidence"] = overall_evidence(report, lock)
    return report


def render_markdown(report: dict[str, Any]) -> str:
    evidence = report["overallEvidence"]
    prefix = [
        "# Locked 6502 code-reuse investigation",
        "",
        f"**Primary classification:** `{evidence['classification']}`",
        "",
        f"- Probable shared routines: **{evidence['probableSharedRoutines']}**",
        f"- Candidate similarities: **{evidence['candidateSimilarities']}**",
        f"- Unique covered bytes: left **{evidence['uniqueLeftBytes']}**, right **{evidence['uniqueRightBytes']}**",
        f"- Supporting instruction pairs: **{evidence['supportingInstructionPairs']}**",
        f"- Lock SHA-256: `{report['lockedRun']['lockSha256']}`",
        "",
        "> This primary result was produced with settings and analysis-tool hashes frozen before the unknown comparison.",
        "",
    ]
    body = align.render_markdown(report).splitlines()
    if body and body[0].startswith("# "):
        body = body[1:]
    return "\n".join(prefix + body) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("lock", type=Path)
    parser.add_argument("left_manifest", type=Path)
    parser.add_argument("right_manifest", type=Path)
    parser.add_argument("output_json", type=Path)
    parser.add_argument("--markdown", type=Path)
    args = parser.parse_args()

    report = run_locked(args.lock, args.left_manifest, args.right_manifest)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(f"wrote {args.output_json}")
    if args.markdown:
        args.markdown.parent.mkdir(parents=True, exist_ok=True)
        args.markdown.write_text(render_markdown(report))
        print(f"wrote {args.markdown}")
    evidence = report["overallEvidence"]
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
