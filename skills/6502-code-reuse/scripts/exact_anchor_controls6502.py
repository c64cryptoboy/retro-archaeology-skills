#!/usr/bin/env python3
"""Run deterministic byte-shuffle and random controls for exact anchors."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
import random
from typing import Any

import anchor_scan6502 as anchor


def summarize_against(
    data: bytes,
    right_index,
    *,
    instruction_count: int,
    min_unique_mnemonics: int,
    max_occurrences: int,
    max_pairs: int,
) -> dict[str, Any]:
    windows, scan = anchor.scan_region(
        data,
        instruction_count,
        base_address=0,
        known_mask=None,
        min_unique_mnemonics=min_unique_mnemonics,
    )
    summary = anchor.view_summary(
        anchor.index_view(windows, "relational"),
        right_index,
        max_occurrences=max_occurrences,
        max_pairs=max_pairs,
    )
    return {"scan": scan, "relational": summary}


def token_shuffle_index(
    windows,
    *,
    seed: int,
):
    """Shuffle token order within every candidate window, preserving vocabulary."""
    rng = random.Random(0x1A570000 + seed)
    result = defaultdict(list)
    for window in windows:
        original = window.relational
        shuffled = list(original)
        rng.shuffle(shuffled)
        if len(shuffled) > 1 and tuple(shuffled) == original:
            shuffled = shuffled[1:] + shuffled[:1]
        result[tuple(shuffled)].append(None)
    return dict(result)


def run_controls(
    left_manifest: Path,
    right_manifest: Path,
    *,
    instruction_count: int,
    shuffle_trials: int,
    random_trials: int,
    token_shuffle_trials: int,
    min_unique_mnemonics: int,
    max_occurrences: int,
    max_pairs: int,
) -> dict[str, Any]:
    _, left_regions = anchor.load_regions(left_manifest)
    _, right_regions = anchor.load_regions(right_manifest)
    comparisons = []
    for left in left_regions:
        for right in right_regions:
            right_windows, right_scan = anchor.scan_region(
                right["data"],
                instruction_count,
                base_address=right["metadata"].get("baseAddress"),
                known_mask=right["knownMask"],
                min_unique_mnemonics=min_unique_mnemonics,
            )
            right_index = anchor.index_view(right_windows, "relational")
            trials = []
            left_windows, left_scan = anchor.scan_region(
                left["data"],
                instruction_count,
                base_address=left["metadata"].get("baseAddress"),
                known_mask=left["knownMask"],
                min_unique_mnemonics=min_unique_mnemonics,
            )
            for seed in range(shuffle_trials):
                shuffled = bytearray(left["data"])
                random.Random(seed).shuffle(shuffled)
                trials.append(
                    {
                        "kind": "left-byte-shuffle",
                        "seed": seed,
                        **summarize_against(
                            bytes(shuffled),
                            right_index,
                            instruction_count=instruction_count,
                            min_unique_mnemonics=min_unique_mnemonics,
                            max_occurrences=max_occurrences,
                            max_pairs=max_pairs,
                        ),
                    }
                )
            for seed in range(token_shuffle_trials):
                summary = anchor.view_summary(
                    token_shuffle_index(left_windows, seed=seed),
                    right_index,
                    max_occurrences=max_occurrences,
                    max_pairs=max_pairs,
                )
                trials.append(
                    {
                        "kind": "left-window-token-order-shuffle",
                        "seed": seed,
                        "scan": left_scan,
                        "relational": summary,
                    }
                )
            for seed in range(random_trials):
                random_data = random.Random(0x650200 + seed).randbytes(len(left["data"]))
                trials.append(
                    {
                        "kind": "random-same-size-as-left",
                        "seed": seed,
                        **summarize_against(
                            random_data,
                            right_index,
                            instruction_count=instruction_count,
                            min_unique_mnemonics=min_unique_mnemonics,
                            max_occurrences=max_occurrences,
                            max_pairs=max_pairs,
                        ),
                    }
                )
            comparisons.append(
                {
                    "leftRegion": left["metadata"]["id"],
                    "rightRegion": right["metadata"]["id"],
                    "rightScan": right_scan,
                    "trials": trials,
                }
            )
    return {
        "format": "6502-exact-anchor-controls",
        "version": 1,
        "configuration": {
            "instructionCount": instruction_count,
            "shuffleTrials": shuffle_trials,
            "randomTrials": random_trials,
            "tokenShuffleTrials": token_shuffle_trials,
            "minUniqueMnemonics": min_unique_mnemonics,
            "maxOccurrencesPerRegion": max_occurrences,
            "maxPairsPerFingerprint": max_pairs,
        },
        "comparisons": comparisons,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("left_manifest", type=Path)
    parser.add_argument("right_manifest", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--instruction-count", type=int, default=8)
    parser.add_argument("--shuffle-trials", type=int, default=10)
    parser.add_argument("--random-trials", type=int, default=5)
    parser.add_argument("--token-shuffle-trials", type=int, default=10)
    parser.add_argument("--min-unique-mnemonics", type=int, default=4)
    parser.add_argument("--max-occurrences", type=int, default=64)
    parser.add_argument("--max-pairs", type=int, default=4096)
    args = parser.parse_args()

    report = run_controls(
        args.left_manifest,
        args.right_manifest,
        instruction_count=args.instruction_count,
        shuffle_trials=args.shuffle_trials,
        random_trials=args.random_trials,
        token_shuffle_trials=args.token_shuffle_trials,
        min_unique_mnemonics=args.min_unique_mnemonics,
        max_occurrences=args.max_occurrences,
        max_pairs=args.max_pairs,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(f"wrote {args.output}")
    for comparison in report["comparisons"]:
        counts = [trial["relational"]["acceptedAnchorPairs"] for trial in comparison["trials"]]
        print(
            f"{comparison['leftRegion']} vs {comparison['rightRegion']}: "
            f"control anchor pairs min={min(counts)} max={max(counts)}"
        )


if __name__ == "__main__":
    main()
