#!/usr/bin/env python3

import random
import unittest

from canonical_seed_domain import (
    CATEGORY_COUNTS,
    CATEGORY_OFFSETS,
    DOMAIN_SIZE,
    CanonicalState,
    category_count,
    contributions,
    rank,
    reversed_mantissa_count,
    unrank,
)


class CanonicalSeedDomainTests(unittest.TestCase):
    def test_exact_size_and_partition(self) -> None:
        self.assertEqual(DOMAIN_SIZE, 0xAF000000)
        self.assertEqual(sum(CATEGORY_COUNTS), DOMAIN_SIZE)
        self.assertEqual(CATEGORY_OFFSETS[0], 0)
        for shifts in range(24):
            self.assertEqual(
                CATEGORY_OFFSETS[shifts] + CATEGORY_COUNTS[shifts],
                CATEGORY_OFFSETS[shifts + 1],
            )

    def test_contributions_are_formula_image(self) -> None:
        for shifts in range(25):
            expected = tuple(sorted({
                ((exponent << shifts) + 0x80) >> 8
                for exponent in range(0x7F, 0x99)
            }))
            self.assertEqual(contributions(shifts), expected)
            expected_count = reversed_mantissa_count(shifts) * len(expected)
            if shifts == 0:
                expected_count = reversed_mantissa_count(0) * 129 // 128
            self.assertEqual(category_count(shifts), expected_count)

    def test_every_category_boundary_round_trips(self) -> None:
        probes = {0, DOMAIN_SIZE - 1}
        for offset, count in zip(CATEGORY_OFFSETS, CATEGORY_COUNTS):
            probes.update((offset, offset + count - 1))
        for index in sorted(probes):
            self.assertEqual(rank(unrank(index)), index)

    def test_one_million_deterministic_random_round_trips(self) -> None:
        generator = random.Random(0x6502C64)
        for _ in range(1_000_000):
            index = generator.randrange(DOMAIN_SIZE)
            self.assertEqual(rank(unrank(index)), index)

    def test_special_rounded_one_state(self) -> None:
        state = CanonicalState(0x81, 0x80000000)
        self.assertEqual(unrank(rank(state)), state)

    def test_rejects_noncanonical_examples(self) -> None:
        for state in (
            CanonicalState(0x67, 0x80000000),
            CanonicalState(0x82, 0x80000000),
            CanonicalState(0x80, 0x80000001),
        ):
            with self.assertRaises(ValueError):
                rank(state)


if __name__ == "__main__":
    unittest.main()
