#!/usr/bin/env python3
"""Summarize exact aggregate output from full_rnd_histogram.

Uses only the Python standard library. Statistics are weighted equally by
canonical starting states unless a field explicitly says otherwise.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path


def read_histogram(path: Path) -> list[tuple[int, int]]:
    with path.open(newline="", encoding="utf-8") as stream:
        rows = [(int(row["value"]), int(row["count"])) for row in csv.DictReader(stream)]
    if not rows or rows != sorted(rows):
        raise ValueError(f"invalid or unsorted histogram: {path}")
    return rows


def quantile(rows: list[tuple[int, int]], population: int, fraction: float) -> int:
    target = math.ceil(population * fraction)
    cumulative = 0
    for value, count in rows:
        cumulative += count
        if cumulative >= target:
            return value
    raise AssertionError("quantile exceeds histogram population")


def histogram_statistics(rows: list[tuple[int, int]], population: int) -> dict[str, object]:
    total = sum(count for _, count in rows)
    if total != population:
        raise ValueError(f"histogram sums to {total:,}, expected {population:,}")
    return {
        "populatedBins": len(rows),
        "minimum": rows[0][0],
        "maximum": rows[-1][0],
        "startWeightedMean": sum(value * count for value, count in rows) / population,
        "startWeightedQuantiles": {
            str(percent): quantile(rows, population, percent / 100)
            for percent in (1, 10, 25, 50, 75, 90, 95, 99, 99.9)
        },
    }


def count_at_least(rows: list[tuple[int, int]], threshold: int) -> int:
    return sum(count for value, count in rows if value >= threshold)


def count_below(rows: list[tuple[int, int]], threshold: int) -> int:
    return sum(count for value, count in rows if value < threshold)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def analyze(directory: Path) -> dict[str, object]:
    summary_path = directory / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    population = int(summary["domainSize"])
    if not summary["complete"] or summary["classifiedStates"] != population:
        raise ValueError("run is not marked complete over the whole domain")

    histograms = {
        name: read_histogram(directory / f"hist-{name}.csv")
        for name in ("mu", "lambda", "total")
    }
    stats = {
        name: histogram_statistics(rows, population)
        for name, rows in histograms.items()
    }

    components = []
    component_total = 0
    with (directory / "cycle-components.csv").open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            length = int(row["lambda"])
            cycle_nodes = int(row["cycle_nodes"])
            count = int(row["component_count"])
            if cycle_nodes % length or cycle_nodes // length != count:
                raise ValueError(f"invalid component row for lambda={length}")
            basin = dict(histograms["lambda"])[length]
            component_total += count
            components.append({
                "lambda": length,
                "cycleNodes": cycle_nodes,
                "componentCount": count,
                "basinStartingStates": basin,
                "basinPercent": basin * 100 / population,
            })

    total_thresholds = (58_078, 80_000, 90_000, 100_000, 105_000,
                        110_000, 115_000, 116_000, 116_500, 116_700,
                        116_750, 116_759)
    lambda_thresholds = (10, 100, 500, 725, 1_000, 3_000, 8_000, 58_078)
    files = [summary_path, directory / "checkpoint.bin", directory / "cycle-components.csv"]
    files.extend(directory / f"hist-{name}.csv" for name in ("mu", "lambda", "total"))

    return {
        "schema": "c64-basic-rnd-final-statistics-v1",
        "weighting": "Each canonical starting state has equal weight.",
        "domainSize": population,
        "run": summary,
        "histograms": stats,
        "cycleComponents": components,
        "distinctComponents": component_total,
        "totalLengthAtLeast": [
            {
                "threshold": threshold,
                "states": (count := count_at_least(histograms["total"], threshold)),
                "percent": count * 100 / population,
            }
            for threshold in total_thresholds
        ],
        "cycleLengthBelow": [
            {
                "threshold": threshold,
                "states": (count := count_below(histograms["lambda"], threshold)),
                "percent": count * 100 / population,
            }
            for threshold in lambda_thresholds
        ],
        "sha256": {path.name: sha256(path) for path in files},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_directory", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = analyze(args.run_directory)
    text = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
