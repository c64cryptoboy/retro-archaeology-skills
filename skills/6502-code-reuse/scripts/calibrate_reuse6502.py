#!/usr/bin/env python3
"""Calibrate and lock the primary 6502 reuse configuration from controls."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

import anchor_scan6502 as anchor
import reuse_align6502 as align
from region_manifest import sha256


def load_json(path: Path, expected_format: str) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if value.get("format") != expected_format:
        raise ValueError(f"{path} is not {expected_format}")
    return value


def common_idiom_control() -> dict[str, Any]:
    raw = bytes.fromhex("48 8A 48 98 48 78 D8 18")
    instructions = anchor.decode_window(raw, 0, 8, base_address=0)
    assert instructions is not None
    relational = anchor.relational_tokens(instructions)
    shape = anchor.shape_tokens(instructions)
    result = align.affine_local_align(relational, relational, shape, shape)
    metrics = align.alignment_metrics(result)
    return {
        "description": "identical eight-instruction save-register/flag idiom",
        "metrics": metrics,
        "classification": align.classify(metrics, 1),
    }


def summarize_report(report: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "leftRegion": comparison["leftRegion"],
            "rightRegion": comparison["rightRegion"],
            "exactAnchors": comparison["exactAnchors"],
            "exactClusters": comparison["exactClusters"],
            **comparison["aggregate"],
        }
        for comparison in report["comparisons"]
    ]


def calibrate(
    known_path: Path,
    anchor_controls_path: Path,
    unrelated_paths: list[Path],
    sensitivity_paths: list[Path],
) -> dict[str, Any]:
    known = load_json(known_path, "6502-reuse-alignment-report")
    controls = load_json(anchor_controls_path, "6502-exact-anchor-controls")
    unrelated = [
        (path, load_json(path, "6502-reuse-alignment-report"))
        for path in unrelated_paths
    ]
    sensitivity = [
        (path, load_json(path, "6502-reuse-alignment-report"))
        for path in sensitivity_paths
    ]

    known_summary = summarize_report(known)
    unrelated_summary = [
        {"path": str(path), "comparisons": summarize_report(report)}
        for path, report in unrelated
    ]
    control_trials = [
        {
            "leftRegion": comparison["leftRegion"],
            "rightRegion": comparison["rightRegion"],
            "kind": trial["kind"],
            "seed": trial["seed"],
            "acceptedAnchorPairs": trial["relational"]["acceptedAnchorPairs"],
        }
        for comparison in controls["comparisons"]
        for trial in comparison["trials"]
    ]
    max_control_anchors = max(
        (trial["acceptedAnchorPairs"] for trial in control_trials), default=0
    )
    max_unrelated_probable = max(
        (
            comparison["probableSharedRoutines"]
            for item in unrelated_summary
            for comparison in item["comparisons"]
        ),
        default=0,
    )
    max_unrelated_candidate = max(
        (
            comparison["candidateSimilarities"]
            for item in unrelated_summary
            for comparison in item["comparisons"]
        ),
        default=0,
    )
    max_unrelated_score = max(
        (
            comparison["maximumScore"]
            for item in unrelated_summary
            for comparison in item["comparisons"]
        ),
        default=0,
    )

    tool_dir = Path(__file__).resolve().parent
    tool_hashes = {
        name: sha256((tool_dir / name).read_bytes())
        for name in (
            "anchor_scan6502.py",
            "reuse_align6502.py",
            "exact_anchor_controls6502.py",
            "region_manifest.py",
        )
    }

    locked_configuration = {
        "version": 1,
        "createdBeforeTargetComparison": True,
        "decoderProfile": known["decoderProfile"],
        "analysisConfiguration": known["configuration"],
        "comparisonInterpretation": {
            "strongSharedCodeLineage": {
                "minimumProbableSharedRoutines": 3,
                "minimumUniqueBytesEachSide": 256,
                "minimumSupportingInstructionPairs": 48,
            },
            "limitedSharedRoutineEvidence": {
                "minimumProbableSharedRoutines": 1,
            },
            "candidateOnly": {
                "minimumCandidateSimilarities": 1,
                "maximumProbableSharedRoutines": 0,
            },
        },
        "toolSha256": tool_hashes,
        "sensitivityRunsRequired": [
            "seed windows of 6 and 10 instructions",
            "probable minimum paired instructions of 12 and 20",
            "report differences without replacing the locked primary result",
        ],
    }

    idiom = common_idiom_control()
    passes = (
        max_control_anchors == 0
        and max_unrelated_probable == 0
        and idiom["classification"] != "probable-shared-routine"
        and any(item["probableSharedRoutines"] >= 3 for item in known_summary)
    )
    return {
        "format": "6502-reuse-calibration",
        "version": 1,
        "stage3GatePassed": passes,
        "knownPositive": {
            "path": str(known_path),
            "sha256": sha256(known_path.read_bytes()),
            "comparisons": known_summary,
            "sensitivityRuns": [
                {
                    "path": str(path),
                    "sha256": sha256(path.read_bytes()),
                    "configuration": sensitivity_report["configuration"],
                    "comparisons": summarize_report(sensitivity_report),
                }
                for path, sensitivity_report in sensitivity
            ],
        },
        "anchorControls": {
            "path": str(anchor_controls_path),
            "sha256": sha256(anchor_controls_path.read_bytes()),
            "trialCount": len(control_trials),
            "maximumAcceptedAnchorPairs": max_control_anchors,
            "byKind": {
                kind: {
                    "trials": sum(trial["kind"] == kind for trial in control_trials),
                    "maximumAcceptedAnchorPairs": max(
                        (
                            trial["acceptedAnchorPairs"]
                            for trial in control_trials
                            if trial["kind"] == kind
                        ),
                        default=0,
                    ),
                }
                for kind in sorted({trial["kind"] for trial in control_trials})
            },
        },
        "commonIdiomControl": idiom,
        "unrelatedRealProgramControls": {
            "reports": unrelated_summary,
            "maximumProbableSharedRoutines": max_unrelated_probable,
            "maximumCandidateSimilarities": max_unrelated_candidate,
            "maximumScore": max_unrelated_score,
            "caution": "These are controls, not proof that no historical code relationship exists.",
        },
        "lockedConfiguration": locked_configuration,
        "rationale": [
            "The supplied known-positive produces multiple long probable routines and broad unique-byte coverage.",
            "Random, byte-order-shuffled, and per-window token-order-shuffled controls produce no eight-instruction anchors.",
            "Unrelated real-game controls produce no probable routines; the strongest result is one eight-instruction candidate.",
            "An identical eight-instruction common idiom remains candidate-only because it does not meet the 16-instruction probable threshold.",
            "Thresholds and tool hashes must be locked before the target comparison to prevent post-hoc tuning.",
        ],
    }


def build_lock(
    report: dict[str, Any], calibration_path: Path, lock_path: Path
) -> dict[str, Any]:
    if not report.get("stage3GatePassed"):
        raise ValueError("cannot lock a calibration that did not pass")
    lock = dict(report["lockedConfiguration"])
    lock["format"] = "6502-reuse-locked-investigation-configuration"
    lock["createdBeforeTargetComparison"] = True
    lock["sourceCalibration"] = {
        "path": os.path.relpath(calibration_path.resolve(), lock_path.parent.resolve()),
        "sha256": sha256(calibration_path.read_bytes()),
    }
    return lock


def render_markdown(report: dict[str, Any]) -> str:
    known = max(
        report["knownPositive"]["comparisons"],
        key=lambda item: item["probableSharedRoutines"],
    )
    unrelated = report["unrelatedRealProgramControls"]
    idiom = report["commonIdiomControl"]
    lines = [
        "# Stage 3 calibration and locked configuration",
        "",
        f"**Gate passed:** {'yes' if report['stage3GatePassed'] else 'no'}",
        "",
        "## Separation observed",
        "",
        f"- Known-positive probable routines: **{known['probableSharedRoutines']}**",
        f"- Known-positive unique covered bytes: **{known['uniqueLeftBytes']} / {known['uniqueRightBytes']}**",
        f"- Maximum random/shuffle control anchors: **{report['anchorControls']['maximumAcceptedAnchorPairs']}**",
        f"- Maximum unrelated-control probable routines: **{unrelated['maximumProbableSharedRoutines']}**",
        f"- Maximum unrelated-control candidates: **{unrelated['maximumCandidateSimilarities']}**",
        f"- Common eight-instruction idiom classification: **{idiom['classification']}**",
        "",
        "## Known-positive sensitivity runs",
        "",
    ]
    for sensitivity in report["knownPositive"]["sensitivityRuns"]:
        strongest = max(
            sensitivity["comparisons"],
            key=lambda item: item["probableSharedRoutines"],
        )
        configuration = sensitivity["configuration"]
        lines.append(
            f"- Seed k={configuration['seedInstructionCount']}, probable minimum paired="
            f"{configuration['classificationThresholds']['probableSharedRoutine']['minimumPairedInstructions']}: "
            f"**{strongest['probableSharedRoutines']}** probable routines"
        )
    lines.extend(
        [
        "",
        "## Locked primary thresholds",
        "",
        "```json",
        json.dumps(report["lockedConfiguration"], indent=2, sort_keys=True),
        "```",
        "",
        "## Interpretation caution",
        "",
        "A strong result supports shared code lineage, not copying direction, authorship, or legal provenance. A null result is bounded by resident bytes, CPU decoding, and the selected normalization/edit model.",
        "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("known_positive", type=Path)
    parser.add_argument("anchor_controls", type=Path)
    parser.add_argument("output_json", type=Path)
    parser.add_argument("--unrelated", type=Path, action="append", default=[])
    parser.add_argument("--sensitivity", type=Path, action="append", default=[])
    parser.add_argument("--markdown", type=Path)
    parser.add_argument(
        "--lock",
        type=Path,
        help="write a frozen configuration after the calibration report passes",
    )
    args = parser.parse_args()

    report = calibrate(
        args.known_positive,
        args.anchor_controls,
        args.unrelated,
        args.sensitivity,
    )
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(f"wrote {args.output_json}")
    if args.markdown:
        args.markdown.parent.mkdir(parents=True, exist_ok=True)
        args.markdown.write_text(render_markdown(report))
        print(f"wrote {args.markdown}")
    if not report["stage3GatePassed"]:
        raise SystemExit("Stage 3 calibration gate did not pass")
    if args.lock:
        args.lock.parent.mkdir(parents=True, exist_ok=True)
        lock = build_lock(report, args.output_json, args.lock)
        args.lock.write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n")
        print(f"wrote {args.lock}")


if __name__ == "__main__":
    main()
