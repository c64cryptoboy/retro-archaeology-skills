#!/usr/bin/env python3
"""Summarize how the all-valid-negative-FAC one-step shell changes max mu.

Inputs are the retained-metadata frontier extraction and exact positive inverse
candidate CSV. This script algebraically filters candidates to noncanonical
states in the negative-seed image. It does not evaluate RND transitions.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

from canonical_seed_domain import CanonicalState, rank, unrank
from negative_seed_image import SeedState, seed_preimages


def is_canonical(seed: SeedState) -> bool:
    try:
        rank(CanonicalState(seed.exponent, seed.mantissa))
    except ValueError:
        return False
    return True


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as source:
        return list(csv.DictReader(source))


def analyze(frontier_path: Path, predecessor_path: Path) -> dict[str, object]:
    frontier = read_csv(frontier_path)
    predecessors = read_csv(predecessor_path)
    if not frontier:
        raise ValueError("empty canonical frontier input")

    canonical_by_lambda: dict[int, list[dict[str, str]]] = defaultdict(list)
    for row in frontier:
        canonical_by_lambda[int(row["lambda"])].append(row)

    outer_by_lambda_mu: dict[int, dict[int, list[dict[str, object]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    seen: set[tuple[int, str]] = set()
    numeric_predecessors = 0
    negative_fac_mappings = 0
    for row in predecessors:
        numeric_predecessors += 1
        key = (int(row["rank"]), row["predecessor_state"].lower())
        if key in seen:
            raise ValueError(f"duplicate target/predecessor pair: {key}")
        seen.add(key)
        seed = SeedState.from_bytes(bytes.fromhex(row["predecessor_state"]))
        fac_preimages = seed_preimages(seed)
        if not fac_preimages or is_canonical(seed):
            continue
        item: dict[str, object] = {
            "targetRank": int(row["rank"]),
            "targetState": row["target_state"].lower(),
            "targetMu": int(row["mu"]),
            "predecessorState": row["predecessor_state"].lower(),
            "negativeFacPreimages": [value.bytes.hex() for value in fac_preimages],
        }
        outer_by_lambda_mu[int(row["lambda"])][int(row["mu"])].append(item)
        negative_fac_mappings += len(fac_preimages)

    components = []
    for lambda_value in sorted(canonical_by_lambda):
        rows = canonical_by_lambda[lambda_value]
        maxima = {int(row["component_max_mu"]) for row in rows}
        if len(maxima) != 1:
            raise ValueError(f"inconsistent maximum for lambda {lambda_value}")
        canonical_max = maxima.pop()
        canonical_max_rows = [row for row in rows if int(row["mu"]) == canonical_max]
        if not canonical_max_rows:
            raise ValueError(f"missing maximum layer for lambda {lambda_value}")

        extending = outer_by_lambda_mu[lambda_value].get(canonical_max, [])
        if extending:
            expanded_max = canonical_max + 1
            maximizing_outer = extending
            maximizing_canonical: list[dict[str, str]] = []
        else:
            expanded_max = canonical_max
            maximizing_outer = outer_by_lambda_mu[lambda_value].get(canonical_max - 1, [])
            maximizing_canonical = canonical_max_rows

        canonical_fac_count = 0
        canonical_states = []
        for row in maximizing_canonical:
            state = unrank(int(row["rank"]))
            seed = SeedState(state.exponent, state.mantissa)
            preimages = seed_preimages(seed)
            canonical_fac_count += len(preimages)
            canonical_states.append({
                "rank": int(row["rank"]),
                "state": state.bytes.hex(),
                "negativeFacPreimages": [value.bytes.hex() for value in preimages],
            })
        outer_fac_count = sum(
            len(item["negativeFacPreimages"]) for item in maximizing_outer
        )
        components.append({
            "lambda": lambda_value,
            "canonicalMaxMu": canonical_max,
            "canonicalMaxStateCount": len(canonical_max_rows),
            "expandedMaxMu": expanded_max,
            "expandedMaxStateCount": len(canonical_states) + len(maximizing_outer),
            "expandedMaxNegativeFacCount": canonical_fac_count + outer_fac_count,
            "maximizingCanonicalStates": canonical_states,
            "maximizingOuterStates": maximizing_outer,
        })

    global_canonical_max = max(item["canonicalMaxMu"] for item in components)
    global_expanded_max = max(item["expandedMaxMu"] for item in components)
    global_components = [
        item["lambda"] for item in components
        if item["expandedMaxMu"] == global_expanded_max
    ]
    all_outer_predecessors = [
        {"lambda": lambda_value, **item}
        for lambda_value in sorted(outer_by_lambda_mu)
        for mu in sorted(outer_by_lambda_mu[lambda_value])
        for item in outer_by_lambda_mu[lambda_value][mu]
    ]
    return {
        "schema": "c64-basic-rnd-negative-shell-frontiers-v1",
        "scope": "All distinct immediate states from valid normalized negative FAC encodings, union the closed canonical positive-advance domain.",
        "numericPredecessorCandidates": numeric_predecessors,
        "outerNegativeImagePredecessorStates": sum(
            len(items) for by_mu in outer_by_lambda_mu.values() for items in by_mu.values()
        ),
        "outerNegativeFacMappings": negative_fac_mappings,
        "outerPredecessors": all_outer_predecessors,
        "globalCanonicalMaxMu": global_canonical_max,
        "globalExpandedMaxMu": global_expanded_max,
        "globalExpandedMaxComponents": global_components,
        "components": components,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("frontier_csv", type=Path)
    parser.add_argument("predecessor_csv", type=Path)
    parser.add_argument("output_json", type=Path)
    parser.add_argument("--output-csv", type=Path)
    args = parser.parse_args()
    result = analyze(args.frontier_csv, args.predecessor_csv)
    args.output_json.write_text(json.dumps(result, indent=2) + "\n")
    if args.output_csv:
        with args.output_csv.open("w", newline="") as destination:
            writer = csv.writer(destination, lineterminator="\n")
            writer.writerow((
                "lambda", "canonical_max_mu", "canonical_max_states",
                "expanded_max_mu", "expanded_max_states",
                "expanded_max_negative_fac_inputs",
            ))
            for item in result["components"]:
                writer.writerow((
                    item["lambda"], item["canonicalMaxMu"],
                    item["canonicalMaxStateCount"], item["expandedMaxMu"],
                    item["expandedMaxStateCount"],
                    item["expandedMaxNegativeFacCount"],
                ))
    print(
        f"canonical max mu: {result['globalCanonicalMaxMu']}; "
        f"negative-shell max mu: {result['globalExpandedMaxMu']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
