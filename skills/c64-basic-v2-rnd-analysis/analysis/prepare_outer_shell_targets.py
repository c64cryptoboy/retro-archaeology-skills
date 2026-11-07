#!/usr/bin/env python3
"""Expand canonical frontier ranks into every possible pre-shuffle FAC target."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from canonical_seed_domain import unrank
from negative_seed_image import SeedState, seed_preimages


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("frontier_csv", type=Path)
    parser.add_argument("output_csv", type=Path)
    args = parser.parse_args()

    target_count = 0
    intermediate_count = 0
    with args.frontier_csv.open(newline="") as source, args.output_csv.open(
        "w", newline=""
    ) as destination:
        reader = csv.DictReader(source)
        writer = csv.writer(destination, lineterminator="\n")
        writer.writerow((
            "rank", "lambda", "mu", "component_max_mu", "target_state",
            "intermediate_fac",
        ))
        for row in reader:
            state = unrank(int(row["rank"]))
            target_count += 1
            for value in seed_preimages(SeedState(state.exponent, state.mantissa)):
                if 0x7F <= value.exponent <= 0x98:
                    writer.writerow((
                        row["rank"], row["lambda"], row["mu"],
                        row["component_max_mu"], state.bytes.hex(),
                        value.bytes.hex(),
                    ))
                    intermediate_count += 1
    print(
        f"expanded {target_count} canonical targets into "
        f"{intermediate_count} pre-shuffle FAC targets"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
