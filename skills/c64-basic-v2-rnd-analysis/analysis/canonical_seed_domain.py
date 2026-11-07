#!/usr/bin/env python3
"""Rank the closed canonical post-shuffle C64 BASIC V2 RND state domain.

The positive advance computes an intermediate FAC in [roughly 0.35, 11879546],
so its exponent is $7F..$98.  The ROM then reverses its four mantissa bytes,
places the intermediate exponent in the guard byte, forces exponent $80,
normalizes, rounds, and stores RNDX.  This module ranks every distinct state
that this shuffle/normalization format can represent for that exponent range.
"""

from __future__ import annotations

from dataclasses import dataclass

MIN_INTERMEDIATE_EXPONENT = 0x7F
MAX_INTERMEDIATE_EXPONENT = 0x98


def contributions(shifts: int) -> tuple[int, ...]:
    return tuple(sorted({
        ((exponent << shifts) + 0x80) >> 8
        for exponent in range(MIN_INTERMEDIATE_EXPONENT, MAX_INTERMEDIATE_EXPONENT + 1)
    }))


def reversed_mantissa_count(shifts: int) -> int:
    if not 0 <= shifts <= 24:
        raise ValueError("shifts must be in 0..24")
    return 1 << (30 - shifts) if shifts < 24 else 128


def category_count(shifts: int) -> int:
    count = reversed_mantissa_count(shifts)
    if shifts == 0:
        # k={0,1}.  Each 128-value bit-7 run and its successor endpoint
        # form a 129-value output run.
        return count + count // 128
    return count * len(contributions(shifts))

CATEGORY_COUNTS = tuple(category_count(shifts) for shifts in range(25))
CATEGORY_OFFSETS = tuple(sum(CATEGORY_COUNTS[:shifts]) for shifts in range(25))
DOMAIN_SIZE = sum(CATEGORY_COUNTS)
assert DOMAIN_SIZE == 0xAF000000


@dataclass(frozen=True)
class CanonicalState:
    exponent: int
    mantissa: int  # unpacked positive mantissa

    @property
    def bytes(self) -> bytes:
        return bytes((self.exponent, (self.mantissa >> 24) & 0x7F)) + (
            self.mantissa & 0xFFFFFF
        ).to_bytes(3, "big")


def _expand_reversed_index(index: int, shifts: int) -> int:
    high_bit = 31 - shifts
    if shifts == 24:
        if not 0 <= index < 128:
            raise ValueError("reversed index outside shift-24 category")
        return 0x80 | index
    if not 0 <= index < 1 << (high_bit - 1):
        raise ValueError("reversed index outside category")
    low = index & 0x7F
    upper = index >> 7
    return (1 << high_bit) | (upper << 8) | 0x80 | low


def _compress_reversed(value: int, shifts: int) -> int:
    high_bit = 31 - shifts
    if value.bit_length() != high_bit + 1 or not value & 0x80:
        raise ValueError("reversed mantissa violates category invariants")
    if shifts == 24:
        return value & 0x7F
    return ((value & ((1 << high_bit) - 1)) >> 8) << 7 | (value & 0x7F)


def unrank(index: int) -> CanonicalState:
    if not 0 <= index < DOMAIN_SIZE:
        raise ValueError("canonical state index outside domain")
    shifts = next(
        s for s in range(24, -1, -1)
        if index >= CATEGORY_OFFSETS[s]
    )
    local = index - CATEGORY_OFFSETS[shifts]
    if shifts == 0:
        block, within = divmod(local, 129)
        value = 0x80000080 + (block << 8) + within
        if value == 1 << 32:
            return CanonicalState(0x81, 0x80000000)
        return CanonicalState(0x80, value)

    allowed = contributions(shifts)
    reversed_index, contribution_index = divmod(local, len(allowed))
    reversed_mantissa = _expand_reversed_index(reversed_index, shifts)
    mantissa = (reversed_mantissa << shifts) + allowed[contribution_index]
    if not 0x80000000 <= mantissa < 1 << 32:
        raise AssertionError("normal category unexpectedly overflowed")
    return CanonicalState(0x80 - shifts, mantissa)


def rank(state: CanonicalState) -> int:
    if state.exponent == 0x81 and state.mantissa == 0x80000000:
        return CATEGORY_OFFSETS[0] + CATEGORY_COUNTS[0] - 1
    shifts = 0x80 - state.exponent
    if not 0 <= shifts <= 24 or not 0x80000000 <= state.mantissa < 1 << 32:
        raise ValueError("state outside canonical exponent/mantissa range")
    if shifts == 0:
        low = state.mantissa & 0xFF
        upper = state.mantissa >> 8
        if low >= 0x80:
            block = upper - 0x800000
            within = low - 0x80
        elif low == 0 and upper > 0x800000:
            block = upper - 0x800001
            within = 128
        else:
            raise ValueError("state outside shift-0 output runs")
        local = block * 129 + within
    else:
        mask = (1 << shifts) - 1
        contribution = state.mantissa & mask
        allowed = contributions(shifts)
        try:
            contribution_index = allowed.index(contribution)
        except ValueError as error:
            raise ValueError("state has an impossible rounded exponent contribution") from error
        reversed_mantissa = state.mantissa >> shifts
        reversed_index = _compress_reversed(reversed_mantissa, shifts)
        local = reversed_index * len(allowed) + contribution_index
    if not 0 <= local < CATEGORY_COUNTS[shifts]:
        raise ValueError("state outside canonical category")
    return CATEGORY_OFFSETS[shifts] + local


def main() -> int:
    print(f"canonical state-domain size: {DOMAIN_SIZE:,} (${DOMAIN_SIZE:08x})")
    print("shifts exponent contributions states offset")
    for shifts in range(25):
        print(
            f"{shifts:>6} ${0x80-shifts:02x} {len(contributions(shifts)):>13} "
            f"{CATEGORY_COUNTS[shifts]:>12,} {CATEGORY_OFFSETS[shifts]:>12,}"
        )
    probes = {0, 1, DOMAIN_SIZE - 1}
    probes.update(CATEGORY_OFFSETS)
    probes.update(offset + count - 1 for offset, count in zip(CATEGORY_OFFSETS, CATEGORY_COUNTS))
    for index in sorted(probes):
        assert rank(unrank(index)) == index
    print(f"boundary round trips passed ({len(probes)} indices)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
