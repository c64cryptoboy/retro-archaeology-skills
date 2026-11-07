#!/usr/bin/env python3
"""Combine canonical and outer-shell depth histograms by eventual cycle."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

from canonical_seed_domain import DOMAIN_SIZE
from negative_seed_image import IMAGE_SIZE

CYCLE_NODES = 79_440
EXPECTED_OUTER = IMAGE_SIZE - DOMAIN_SIZE


def load_depth(path: Path) -> dict[tuple[int, int], int]:
    result: dict[tuple[int, int], int] = defaultdict(int)
    with path.open(newline="") as source:
        for row in csv.DictReader(source):
            key = (int(row["lambda"]), int(row["mu"]))
            count = int(row["count"])
            if count <= 0:
                raise ValueError(f"nonpositive count in {path}: {row}")
            result[key] += count
    return dict(result)


def summarize(combined: dict[tuple[int, int], int],
              shell: dict[tuple[int, int], int]) -> list[dict[str, int]]:
    lengths = sorted({length for length, _ in combined})
    rows = []
    for number, length in enumerate(lengths, 1):
        depths = sorted(
            (mu, count) for (candidate, mu), count in combined.items()
            if candidate == length
        )
        cycle = sum(count for mu, count in depths if mu == 0)
        if cycle != length:
            raise ValueError(f"lambda {length}: {cycle} cycle nodes, expected {length}")
        transient = sum(count for mu, count in depths if mu > 0)
        target = (transient + 1) // 2
        cumulative = 0
        median = 0
        for mu, count in depths:
            if not mu:
                continue
            cumulative += count
            if cumulative >= target:
                median = mu
                break
        maximum = max(mu for mu, count in depths if mu > 0 and count)
        outer = sum(
            count for (candidate, mu), count in shell.items()
            if candidate == length and mu > 0
        )
        rows.append({
            "loop": number,
            "lambda": length,
            "transientStates": transient,
            "outerEntryStates": outer,
            "medianMu": median,
            "maxMu": maximum,
            "basinStates": transient + cycle,
        })
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("canonical_depth_csv", type=Path)
    parser.add_argument("shell_depth_csv", type=Path)
    parser.add_argument("shell_summary_json", type=Path)
    parser.add_argument("output_json", type=Path)
    parser.add_argument("--output-depth-csv", type=Path)
    args = parser.parse_args()

    canonical = load_depth(args.canonical_depth_csv)
    shell = load_depth(args.shell_depth_csv)
    shell_summary = json.loads(args.shell_summary_json.read_text())
    if not shell_summary.get("complete"):
        raise ValueError("refusing incomplete shell summary")
    if sum(canonical.values()) != DOMAIN_SIZE:
        raise ValueError("canonical histogram total mismatch")
    if sum(shell.values()) != EXPECTED_OUTER:
        raise ValueError("outer-shell histogram total mismatch")
    if any(mu == 0 for _, mu in shell):
        raise ValueError("outer-shell histogram unexpectedly contains cycle nodes")

    combined = defaultdict(int, canonical)
    for key, count in shell.items():
        combined[key] += count
    rows = summarize(dict(combined), shell)
    if len(rows) != 15 or sum(row["basinStates"] for row in rows) != IMAGE_SIZE:
        raise ValueError("combined component/domain invariant failed")
    if sum(row["transientStates"] for row in rows) != IMAGE_SIZE - CYCLE_NODES:
        raise ValueError("combined transient total mismatch")

    result = {
        "schema": "c64-basic-rnd-negative-seed-space-statistics-v1",
        "scope": (
            "Each distinct RNDX state in the all-valid-normalized-negative-FAC "
            "image receives equal weight; subsequent positive advances remain "
            "inside this union. RND(0) and the power-on-only entry are excluded."
        ),
        "states": IMAGE_SIZE,
        "canonicalStates": DOMAIN_SIZE,
        "outerEntryStates": EXPECTED_OUTER,
        "cycleNodes": CYCLE_NODES,
        "transientStates": IMAGE_SIZE - CYCLE_NODES,
        "components": rows,
    }
    args.output_json.write_text(json.dumps(result, indent=2) + "\n")

    if args.output_depth_csv:
        with args.output_depth_csv.open("w", newline="") as destination:
            writer = csv.writer(destination, lineterminator="\n")
            writer.writerow(("lambda", "mu", "count"))
            for (length, mu), count in sorted(combined.items()):
                writer.writerow((length, mu, count))

    print("loop  lambda  transient_states  median_mu  max_mu  basin_states")
    for row in rows:
        print(
            f"{row['loop']:>4} {row['lambda']:>7} {row['transientStates']:>17} "
            f"{row['medianMu']:>10} {row['maxMu']:>7} {row['basinStates']:>13}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
