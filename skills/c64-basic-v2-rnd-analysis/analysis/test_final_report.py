#!/usr/bin/env python3
"""Evidence checks for final-report seed and graph examples."""
from __future__ import annotations

import csv
import json
import mmap
import struct
import unittest
from pathlib import Path

import canonical_seed_domain as domain
import negative_seed_image as negative
import throwaway_rom_cycle as rom
from cpu6502 import FC, FU

HERE = Path(__file__).resolve().parent
from rnd_paths import RUN_DIR as RUN, SHELL_DIR as SHELL_RUN

requires_metadata = unittest.skipUnless(
    (RUN / 'metadata.bin').is_file(),
    'external 10.94-GiB metadata absent; set C64_RND_RUN_DIR for this gate')
SMALL = HERE / "visualization/small-mu5-lambda7.json"
CHRGET = bytes.fromhex("e6 7a d0 02 e6 7b ad 00 08 c9 3a b0 0a c9 20 f0 ef 38 e9 30 38 e9 d0 60")
CHECKPOINT_FORMAT = "<QIIQQQQII254IQ"


def parse_decimal(text: str) -> bytes:
    cpu = rom.make_cpu()
    cpu.inject_bytes(0x0073, CHRGET)
    cpu.inject_bytes(0x0800, text.encode("ascii") + b"\0")
    cpu.memory[0x7A] = 0x00
    cpu.memory[0x7B] = 0x08
    cpu.init_cpu(0xBCF3, newa=ord(text[0]), flags=FU | FC)
    cpu.exit_on_empty_stack = True
    for instructions in range(100_000):
        if not cpu.runcpu():
            return bytes(cpu.memory[0x61:0x67])
    raise AssertionError("BASIC FIN decimal parser did not return")


def checkpoint_lengths() -> list[int]:
    values = struct.unpack(CHECKPOINT_FORMAT, (RUN / "checkpoint.bin").read_bytes())
    count = values[7]
    return list(values[9:9 + count])


def metadata_result(seed: bytes) -> tuple[int, int, int]:
    state = negative.SeedState.from_bytes(seed)
    rank = domain.rank(domain.CanonicalState(state.exponent, state.mantissa))
    with (RUN / "metadata.bin").open("rb") as stream:
        mapping = mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ)
        packed = struct.unpack_from("<I", mapping, rank * 4)[0]
        mapping.close()
    cycle_class, mu = packed >> 24, packed & 0xFFFFFF
    return rank, mu, checkpoint_lengths()[cycle_class - 1]


class FinalReportTests(unittest.TestCase):
    def test_aggregate_totals_and_components(self):
        summary = json.loads((RUN / "summary.json").read_text())
        population = summary["domainSize"]
        self.assertTrue(summary["complete"])
        for name in ("mu", "lambda", "total"):
            with (RUN / f"hist-{name}.csv").open(newline="") as stream:
                self.assertEqual(sum(int(row["count"]) for row in csv.DictReader(stream)), population)
        with (RUN / "cycle-components.csv").open(newline="") as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(len(rows), 15)
        for row in rows:
            self.assertEqual(int(row["cycle_nodes"]), int(row["lambda"]) * int(row["component_count"]))

    def test_complete_negative_shell_histograms(self):
        summary = json.loads((SHELL_RUN / "summary.json").read_text())
        self.assertTrue(summary["complete"])
        self.assertEqual(summary["imageStates"], 10_745_675_776)
        self.assertEqual(summary["canonicalImageStates"], 2_936_012_800)
        self.assertEqual(summary["outerStates"], 7_809_662_976)
        with (SHELL_RUN / "shell-depth.csv").open(newline="") as stream:
            self.assertEqual(
                sum(int(row["count"]) for row in csv.DictReader(stream)),
                summary["outerStates"],
            )
        final = json.loads((SHELL_RUN / "final-statistics.json").read_text())
        self.assertEqual(final["states"], 10_745_675_776)
        self.assertEqual(final["transientStates"], 10_745_596_336)
        self.assertEqual(len(final["components"]), 15)
        longest = final["components"][-1]
        self.assertEqual(
            (longest["lambda"], longest["transientStates"],
             longest["medianMu"], longest["maxMu"]),
            (58_078, 8_836_633_182, 18_602, 58_681),
        )

    @requires_metadata
    def test_unique_canonical_longest_nonrepeating_seed_literal(self):
        fac = parse_decimal("-4.33901453")
        self.assertEqual(fac, bytes.fromhex("83 8a d9 35 00 ff"))
        seed = negative.fac_to_seed(negative.NegativeFac(fac[0], int.from_bytes(fac[1:5], "big"))).bytes
        self.assertEqual(seed, bytes.fromhex("76 57 66 2a 0c"))
        self.assertEqual(metadata_result(seed), (2_900_100_616, 58_681, 58_078))
        with (RUN / "hist-total.csv").open(newline="") as stream:
            totals = {int(row["value"]): int(row["count"]) for row in csv.DictReader(stream)}
        self.assertEqual(totals[116_759], 1)

    @requires_metadata
    def test_negative_shell_does_not_extend_global_maximum(self):
        maximum = bytes.fromhex("76 57 66 2a 0c")
        unavailable_predecessor = bytes.fromhex("6b 44 17 b2 75")
        cpu = rom.make_cpu()
        cpu.inject_bytes(rom.RNDX, unavailable_predecessor)
        self.assertEqual(rom.advance(cpu), maximum)
        self.assertEqual(
            negative.seed_preimages(negative.SeedState.from_bytes(unavailable_predecessor)),
            [],
        )

        target = bytes.fromhex("80 04 d9 84 99")
        outer = (
            (bytes.fromhex("7a 57 66 2a 0c"), 4),
            (bytes.fromhex("7c 57 66 2a 0c"), 16),
            (bytes.fromhex("7e 57 66 2a 0c"), 63),
        )
        for state, preimage_count in outer:
            cpu.inject_bytes(rom.RNDX, state)
            self.assertEqual(rom.advance(cpu), target)
            self.assertEqual(
                len(negative.seed_preimages(negative.SeedState.from_bytes(state))),
                preimage_count,
            )
            with self.assertRaises(ValueError):
                domain.rank(domain.CanonicalState(
                    negative.SeedState.from_bytes(state).exponent,
                    negative.SeedState.from_bytes(state).mantissa,
                ))
        self.assertEqual(metadata_result(target)[1:], (58_680, 58_078))
        maximum_preimages = negative.seed_preimages(
            negative.SeedState.from_bytes(maximum)
        )
        self.assertEqual(len(maximum_preimages), 1)
        self.assertEqual(len(maximum_preimages) + sum(count for _, count in outer), 84)

    def test_two_integer_literals_seed_same_state(self):
        target = bytes.fromhex("80 00 00 00 81")
        for literal, expected_fac in (
            ("-16777217", "99 80 00 00 80 ff"),
            ("-33554434", "9a 80 00 00 80 ff"),
        ):
            fac = parse_decimal(literal)
            self.assertEqual(fac, bytes.fromhex(expected_fac))
            value = negative.NegativeFac(fac[0], int.from_bytes(fac[1:5], "big"))
            self.assertEqual(negative.fac_to_seed(value).bytes, target)

    @requires_metadata
    def test_simple_minus_one_has_maximum_cycle(self):
        fac = parse_decimal("-1")
        self.assertEqual(fac[:5], bytes.fromhex("81 80 00 00 00"))
        seed = negative.fac_to_seed(negative.NegativeFac(fac[0], int.from_bytes(fac[1:5], "big"))).bytes
        self.assertEqual(seed, bytes.fromhex("68 00 81 00 00"))
        self.assertEqual(metadata_result(seed)[1:], (35_736, 58_078))

    @requires_metadata
    def test_small_example_metadata_classification(self):
        data = json.loads(SMALL.read_text())
        seed = bytes.fromhex(data["seedStateBytes"])
        self.assertEqual(metadata_result(seed)[1:], (5, 7))

    def test_small_example_literal_and_orbit(self):
        data = json.loads(SMALL.read_text())
        fac = parse_decimal("-.311306466")
        self.assertEqual(fac, bytes.fromhex("7f 9f 63 8f a5 ff"))
        seed = negative.fac_to_seed(negative.NegativeFac(fac[0], int.from_bytes(fac[1:5], "big"))).bytes
        self.assertEqual(seed, bytes.fromhex(data["seedStateBytes"]))
        cpu = rom.make_cpu()
        cpu.inject_bytes(rom.RNDX, seed)
        actual = [seed]
        for _ in range(12):
            actual.append(rom.advance(cpu))
        expected = [bytes.fromhex(row["stateBytes"]) for row in data["nodes"]]
        expected.append(bytes.fromhex(data["nextRepeatedState"]["stateBytes"]))
        self.assertEqual(actual, expected)
        self.assertEqual(actual[12], actual[5])


if __name__ == "__main__":
    unittest.main()
