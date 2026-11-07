#!/usr/bin/env python3
"""Exact model of the C64 BASIC V2 RND(negative) FAC-to-RNDX mapping.

This models the already evaluated negative FAC at the $E0D3 branch. It does not
model decimal literal parsing or expression evaluation into FAC.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass


@dataclass(frozen=True)
class NegativeFac:
    exponent: int
    mantissa: int  # Unpacked FAC mantissa; bit 31 must be one.

    def __post_init__(self) -> None:
        if not 1 <= self.exponent <= 0xFF:
            raise ValueError("nonzero FAC exponent must be in 1..255")
        if not 0x80000000 <= self.mantissa <= 0xFFFFFFFF:
            raise ValueError("normalized FAC mantissa must have bit 31 set")

    @property
    def bytes(self) -> bytes:
        # For a negative packed BASIC float, the packed sign bit and restored
        # implicit mantissa bit are both one, so these five bytes have the same
        # numeric byte values as exponent + unpacked mantissa.
        return bytes((self.exponent,)) + self.mantissa.to_bytes(4, "big")


@dataclass(frozen=True)
class SeedState:
    exponent: int
    mantissa: int  # Unpacked positive mantissa; bit 31 is implicit when stored.

    def __post_init__(self) -> None:
        if not 1 <= self.exponent <= 0xFF:
            raise ValueError("seed exponent must be in 1..255")
        if not 0x80000000 <= self.mantissa <= 0xFFFFFFFF:
            raise ValueError("normalized seed mantissa must have bit 31 set")

    @property
    def bytes(self) -> bytes:
        return bytes((self.exponent, (self.mantissa >> 24) & 0x7F)) + (
            self.mantissa & 0xFFFFFF
        ).to_bytes(3, "big")

    @classmethod
    def from_bytes(cls, data: bytes) -> "SeedState":
        if len(data) != 5:
            raise ValueError("seed must contain five bytes")
        if data[0] == 0:
            raise ValueError("zero seed encoding is outside this nonzero model")
        if data[1] & 0x80:
            raise ValueError("RNDX seed must be positive (stored sign bit clear)")
        mantissa = int.from_bytes(bytes((data[1] | 0x80,)) + data[2:], "big")
        return cls(data[0], mantissa)


def reverse_bytes32(value: int) -> int:
    return int.from_bytes(value.to_bytes(4, "big")[::-1], "big")


def exponent_contribution(exponent: int, shifts: int) -> int:
    """Rounded integer added after reversing and normalizing the mantissa."""
    return ((exponent << shifts) + 0x80) >> 8


def fac_to_seed(value: NegativeFac) -> SeedState:
    reversed_mantissa = reverse_bytes32(value.mantissa)
    shifts = 32 - reversed_mantissa.bit_length()
    if not 0 <= shifts <= 24:
        raise AssertionError("restored input mantissa bit limits normalization to 24 shifts")

    wide = ((reversed_mantissa << 8) | value.exponent) << shifts
    mantissa = wide >> 8
    if wide & 0x80:  # BC1B/ASL $70 rounds upward when guard bit 7 is set.
        mantissa += 1

    output_exponent = 0x80 - shifts
    if mantissa == 1 << 32:
        # B96F overflows the significand; B938 increments the exponent and
        # rotates the carry into a normalized $80000000 mantissa.
        mantissa = 0x80000000
        output_exponent += 1
    return SeedState(output_exponent, mantissa)


def mantissa_count_for_shifts(shifts: int) -> int:
    if not 0 <= shifts <= 24:
        raise ValueError("normalization shifts must be in 0..24")
    # Reversed input mantissas have bit 7 set. For shifts 0..23, their top
    # one bit is independently fixed; at shift 24 it is that same bit 7.
    return 1 << (30 - shifts) if shifts < 24 else 128


def image_count_for_shifts(shifts: int) -> int:
    inputs = mantissa_count_for_shifts(shifts)
    if shifts <= 6:
        # Exponents realize every k in 0..2^s. Consecutive allowed R values
        # have one shared endpoint; bit-7 runs contain 128 consecutive values.
        return inputs * (1 << shifts) + inputs // 128
    if shifts == 7:
        # Exponents realize k=1..128, with no overlap between adjacent R.
        return inputs * 128
    # For s>=8, k=E*2^(s-8), E=1..255; all pairs are distinct.
    return inputs * 255


IMAGE_CATEGORY_COUNTS = tuple(image_count_for_shifts(shifts) for shifts in range(25))
IMAGE_CATEGORY_OFFSETS = tuple(sum(IMAGE_CATEGORY_COUNTS[:shifts]) for shifts in range(25))
IMAGE_SIZE = sum(IMAGE_CATEGORY_COUNTS)
assert IMAGE_SIZE == 10_745_675_776


def _expand_reversed_index(index: int, shifts: int) -> int:
    high_bit = 31 - shifts
    limit = mantissa_count_for_shifts(shifts)
    if not 0 <= index < limit:
        raise ValueError("reversed-mantissa index outside category")
    if shifts == 24:
        return 0x80 | index
    return (1 << high_bit) | ((index >> 7) << 8) | 0x80 | (index & 0x7F)


def _compress_reversed(value: int, shifts: int) -> int:
    high_bit = 31 - shifts
    if value.bit_length() != high_bit + 1 or not value & 0x80:
        raise ValueError("reversed mantissa violates category invariants")
    if shifts == 24:
        result = value & 0x7F
    else:
        result = ((value & ((1 << high_bit) - 1)) >> 8) << 7 | (value & 0x7F)
    if result >= mantissa_count_for_shifts(shifts):
        raise ValueError("compressed reversed mantissa outside category")
    return result


def image_unrank(index: int) -> SeedState:
    """Map a dense 64-bit index to one distinct all-valid-negative-FAC seed."""
    if not 0 <= index < IMAGE_SIZE:
        raise ValueError("negative seed-image index outside domain")
    shifts = next(
        value for value in range(24, -1, -1)
        if index >= IMAGE_CATEGORY_OFFSETS[value]
    )
    local = index - IMAGE_CATEGORY_OFFSETS[shifts]
    scale = 1 << shifts
    if shifts <= 6:
        run_size = 128 * scale + 1
        run, within = divmod(local, run_size)
        high_bit = 31 - shifts
        reversed_first = (1 << high_bit) | (run << 8) | 0x80
        wide_mantissa = reversed_first * scale + within
    elif shifts == 7:
        reversed_index, contribution_index = divmod(local, 128)
        reversed_mantissa = _expand_reversed_index(reversed_index, shifts)
        wide_mantissa = reversed_mantissa * scale + contribution_index + 1
    else:
        reversed_index, contribution_index = divmod(local, 255)
        reversed_mantissa = _expand_reversed_index(reversed_index, shifts)
        wide_mantissa = reversed_mantissa * scale + (contribution_index + 1) * (1 << (shifts - 8))
    exponent = 0x80 - shifts
    if wide_mantissa == 1 << 32:
        exponent += 1
        mantissa = 0x80000000
    else:
        mantissa = wide_mantissa
    return SeedState(exponent, mantissa)


def image_rank(seed: SeedState) -> int:
    """Return the dense image index, rejecting states outside the exact image."""
    candidates: list[tuple[int, int]] = []
    ordinary_shifts = 0x80 - seed.exponent
    if 0 <= ordinary_shifts <= 24:
        candidates.append((ordinary_shifts, seed.mantissa))
    overflow_shifts = 0x81 - seed.exponent
    if seed.mantissa == 0x80000000 and 0 <= overflow_shifts <= 7:
        candidates.append((overflow_shifts, 1 << 32))

    for shifts, wide_mantissa in candidates:
        scale = 1 << shifts
        try:
            if shifts <= 6:
                high_bit = 31 - shifts
                base = ((1 << high_bit) | 0x80) * scale
                delta = wide_mantissa - base
                if delta < 0:
                    continue
                run, within = divmod(delta, 256 * scale)
                if run >= mantissa_count_for_shifts(shifts) // 128 or within > 128 * scale:
                    continue
                local = run * (128 * scale + 1) + within
            elif shifts == 7:
                quotient, remainder = divmod(wide_mantissa, scale)
                if remainder:
                    reversed_mantissa = quotient
                    contribution = remainder
                else:
                    reversed_mantissa = quotient - 1
                    contribution = scale
                reversed_index = _compress_reversed(reversed_mantissa, shifts)
                if not 1 <= contribution <= 128:
                    continue
                local = reversed_index * 128 + contribution - 1
            else:
                reversed_mantissa, contribution = divmod(wide_mantissa, scale)
                step = 1 << (shifts - 8)
                if not contribution or contribution % step:
                    continue
                exponent = contribution // step
                if not 1 <= exponent <= 255:
                    continue
                reversed_index = _compress_reversed(reversed_mantissa, shifts)
                local = reversed_index * 255 + exponent - 1
        except ValueError:
            continue
        if local < IMAGE_CATEGORY_COUNTS[shifts]:
            result = IMAGE_CATEGORY_OFFSETS[shifts] + local
            if image_unrank(result) == seed:
                return result
    raise ValueError("state outside the all-valid-negative-FAC seed image")


def image_summary() -> dict[str, object]:
    rows = []
    for shifts in range(25):
        rows.append({
            "shifts": shifts,
            "seedExponentNormally": 0x80 - shifts,
            "inputMantissas": mantissa_count_for_shifts(shifts),
            "uniqueSeeds": image_count_for_shifts(shifts),
        })
    total = IMAGE_SIZE
    return {
        "validNegativeFacInputs": 255 * (1 << 31),
        "uniqueReachableSeedStates": total,
        "rows": rows,
    }


def seed_preimages(seed: SeedState) -> list[NegativeFac]:
    """Return every valid negative FAC that maps to one seed state."""
    answers: set[NegativeFac] = set()
    for shifts in range(25):
        ordinary = seed.exponent == 0x80 - shifts
        rounded_overflow = (
            shifts <= 7
            and seed.exponent == 0x81 - shifts
            and seed.mantissa == 0x80000000
        )
        if not ordinary and not rounded_overflow:
            continue
        target = (1 << 32) if rounded_overflow and not ordinary else seed.mantissa
        scale = 1 << shifts
        for exponent in range(1, 256):
            contribution = exponent_contribution(exponent, shifts)
            difference = target - contribution
            if difference < 0 or difference % scale:
                continue
            reversed_mantissa = difference // scale
            if not 0 < reversed_mantissa < 1 << 32:
                continue
            if 32 - reversed_mantissa.bit_length() != shifts:
                continue
            if not reversed_mantissa & 0x80:
                continue
            mantissa = reverse_bytes32(reversed_mantissa)
            if mantissa < 0x80000000:
                continue
            candidate = NegativeFac(exponent, mantissa)
            if fac_to_seed(candidate) == seed:
                answers.add(candidate)
    return sorted(answers, key=lambda item: (item.exponent, item.mantissa))


def parse_hex_bytes(text: str, length: int) -> bytes:
    compact = text.replace("$", "").replace(",", " ").replace(":", " ")
    parts = compact.split()
    try:
        data = bytes.fromhex("".join(parts))
    except ValueError as error:
        raise argparse.ArgumentTypeError(str(error)) from error
    if len(data) != length:
        raise argparse.ArgumentTypeError(f"expected {length} bytes, got {len(data)}")
    return data


def print_summary() -> None:
    summary = image_summary()
    print(f"valid negative FAC encodings: {summary['validNegativeFacInputs']:,}")
    print(f"unique reachable RNDX states: {summary['uniqueReachableSeedStates']:,}")
    print("shifts seed_exp input_mantissas unique_seeds")
    for row in summary["rows"]:
        print(
            f"{row['shifts']:>6} ${row['seedExponentNormally']:02x} "
            f"{row['inputMantissas']:>16,} {row['uniqueSeeds']:>12,}"
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--fac", type=lambda text: parse_hex_bytes(text, 5),
                       help="negative packed/FAC bytes: exponent plus mantissa")
    group.add_argument("--seed", type=lambda text: parse_hex_bytes(text, 5),
                       help="positive packed RNDX bytes to invert")
    args = parser.parse_args()
    if args.fac is not None:
        value = NegativeFac(args.fac[0], int.from_bytes(args.fac[1:], "big"))
        result = fac_to_seed(value)
        print(f"negative FAC: {value.bytes.hex(' ')}")
        print(f"RNDX seed:    {result.bytes.hex(' ')}")
    elif args.seed is not None:
        seed = SeedState.from_bytes(args.seed)
        preimages = seed_preimages(seed)
        print(f"RNDX seed: {seed.bytes.hex(' ')}")
        print(f"valid negative FAC preimages: {len(preimages)}")
        for value in preimages:
            print(value.bytes.hex(" "))
    else:
        print_summary()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
