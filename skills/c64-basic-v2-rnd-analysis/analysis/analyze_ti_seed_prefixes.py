#!/usr/bin/env python3
"""Classify exact C64 BASIC V2 RND(-TI) integer seeds by eventual cycle.

TI=0 is reported separately because RND(-0) takes the RND(0) timer path.
For TI>=1, all integers in the C64 one-day range are represented exactly in
FAC. Counts weight each TI value once, including any seed-map collisions.
"""
from __future__ import annotations

import argparse
import json
import mmap
import struct
from pathlib import Path

import canonical_seed_domain as canonical
from rnd_query import read_checkpoint

HERE = Path(__file__).resolve().parent
from rnd_paths import RUN_DIR as DEFAULT_RUN_DIR
DEFAULT_PREFIXES = (
    60,
    3_600,
    216_000,
    1_000_000,
    5_183_999,
    5_184_000,
)

CONTRIBUTIONS = tuple(canonical.contributions(shifts) for shifts in range(25))
CONTRIBUTION_INDEX = tuple(
    {value: index for index, value in enumerate(values)} for values in CONTRIBUTIONS
)


def reverse_bytes32(value: int) -> int:
    return int.from_bytes(value.to_bytes(4, "big")[::-1], "big")


def integer_fac_to_seed(value: int) -> tuple[int, int]:
    """Return positive packed-seed exponent and unpacked mantissa for RND(-value)."""
    if value <= 0:
        raise ValueError("integer seed must be positive")
    top_bit = value.bit_length() - 1
    exponent = 0x81 + top_bit
    mantissa = value << (31 - top_bit)

    reversed_mantissa = reverse_bytes32(mantissa)
    shifts = 32 - reversed_mantissa.bit_length()
    wide = ((reversed_mantissa << 8) | exponent) << shifts
    output_mantissa = (wide >> 8) + (1 if wide & 0x80 else 0)
    output_exponent = 0x80 - shifts
    if output_mantissa == 1 << 32:
        output_mantissa = 0x80000000
        output_exponent += 1
    return output_exponent, output_mantissa


def canonical_rank(exponent: int, mantissa: int) -> int:
    """Fast exact specialization of canonical.rank for this sequential query."""
    if exponent == 0x81 and mantissa == 0x80000000:
        return canonical.CATEGORY_OFFSETS[0] + canonical.CATEGORY_COUNTS[0] - 1
    shifts = 0x80 - exponent
    if not 0 <= shifts <= 24 or not 0x80000000 <= mantissa < 1 << 32:
        raise ValueError("integer-derived seed is outside canonical exponent/mantissa range")
    if shifts == 0:
        low = mantissa & 0xFF
        upper = mantissa >> 8
        if low >= 0x80:
            block = upper - 0x800000
            within = low - 0x80
        elif low == 0 and upper > 0x800000:
            block = upper - 0x800001
            within = 128
        else:
            raise ValueError("integer-derived seed is outside shift-0 output runs")
        local = block * 129 + within
    else:
        contribution = mantissa & ((1 << shifts) - 1)
        try:
            contribution_index = CONTRIBUTION_INDEX[shifts][contribution]
        except KeyError as error:
            raise ValueError("integer-derived seed has impossible contribution") from error
        reversed_mantissa = mantissa >> shifts
        high_bit = 31 - shifts
        if reversed_mantissa.bit_length() != high_bit + 1 or not reversed_mantissa & 0x80:
            raise ValueError("integer-derived seed violates canonical category")
        if shifts == 24:
            reversed_index = reversed_mantissa & 0x7F
        else:
            reversed_index = (
                ((reversed_mantissa & ((1 << high_bit) - 1)) >> 8) << 7
                | (reversed_mantissa & 0x7F)
            )
        local = reversed_index * len(CONTRIBUTIONS[shifts]) + contribution_index
    if not 0 <= local < canonical.CATEGORY_COUNTS[shifts]:
        raise ValueError("integer-derived seed is outside canonical category")
    return canonical.CATEGORY_OFFSETS[shifts] + local


def classify_prefixes(run_dir: Path, prefixes: tuple[int, ...]) -> dict[str, object]:
    if not prefixes or any(value <= 0 for value in prefixes):
        raise ValueError("prefix limits must be positive")
    prefixes = tuple(sorted(set(prefixes)))
    checkpoint, lengths = read_checkpoint(run_dir)
    if not checkpoint["complete"]:
        raise ValueError("canonical metadata is incomplete")

    metadata_path = run_dir / "metadata.bin"
    expected_size = canonical.DOMAIN_SIZE * 4
    if metadata_path.stat().st_size != expected_size:
        raise ValueError("canonical metadata has the wrong size")

    counts = [0] * len(lengths)
    rows: list[dict[str, object]] = []
    next_prefix_index = 0
    with metadata_path.open("rb") as stream, mmap.mmap(
        stream.fileno(), 0, access=mmap.ACCESS_READ
    ) as mapped:
        for value in range(1, prefixes[-1] + 1):
            exponent, mantissa = integer_fac_to_seed(value)
            rank = canonical_rank(exponent, mantissa)
            entry = struct.unpack_from("<I", mapped, rank * 4)[0]
            cycle_class = entry >> 24
            if not 1 <= cycle_class <= len(lengths):
                raise ValueError(f"invalid metadata class at TI={value}, rank={rank}")
            counts[cycle_class - 1] += 1

            if value == prefixes[next_prefix_index]:
                total = value
                distribution = [
                    {
                        "lambda": lengths[index],
                        "seeds": count,
                        "percent": count * 100.0 / total,
                    }
                    for index, count in sorted(
                        enumerate(counts), key=lambda item: lengths[item[0]]
                    )
                ]
                rows.append({"maxTI": value, "seedCount": total, "distribution": distribution})
                next_prefix_index += 1
                if next_prefix_index == len(prefixes):
                    break

    return {
        "scope": "uniform integer TI values, inclusive range 1..maxTI",
        "tiZero": "excluded: RND(-0) is RND(0), the timer path",
        "allIntegerDerivedSeedsCanonical": True,
        "prefixes": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--prefix", type=int, action="append", dest="prefixes")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    prefixes = tuple(args.prefixes) if args.prefixes else DEFAULT_PREFIXES
    result = classify_prefixes(args.run_dir, prefixes)
    rendered = json.dumps(result, indent=2)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
