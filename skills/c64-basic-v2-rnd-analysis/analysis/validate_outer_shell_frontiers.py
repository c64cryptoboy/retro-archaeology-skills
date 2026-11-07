#!/usr/bin/env python3
"""Replay outer-shell frontier evidence through the independent 6502 emulator."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from throwaway_rom_cycle import RNDX, advance, make_cpu


def negative_fac_to_seed_rom(cpu, fac: bytes) -> bytes:
    cpu.inject_bytes(0x0061, fac)
    cpu.memory[0x0066] = 0xFF
    cpu.init_cpu(0xE0D3)
    cpu.exit_on_empty_stack = True
    for _ in range(100_000):
        if not cpu.runcpu():
            return bytes(cpu.memory[RNDX:RNDX + 5])
    raise RuntimeError("negative seed path exceeded instruction limit")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("predecessor_csv", type=Path)
    parser.add_argument("summary_json", type=Path)
    args = parser.parse_args()

    cpu = make_cpu()
    transition_count = 0
    with args.predecessor_csv.open(newline="") as source:
        for row in csv.DictReader(source):
            start = bytes.fromhex(row["predecessor_state"])
            expected = bytes.fromhex(row["target_state"])
            cpu.inject_bytes(RNDX, start)
            actual = advance(cpu)
            if actual != expected:
                raise AssertionError(
                    f"{start.hex()}: {actual.hex()} != {expected.hex()}"
                )
            transition_count += 1

    result = json.loads(args.summary_json.read_text())
    mapping_count = 0
    for item in result["outerPredecessors"]:
        expected = bytes.fromhex(item["predecessorState"])
        for text in item["negativeFacPreimages"]:
            actual = negative_fac_to_seed_rom(cpu, bytes.fromhex(text))
            if actual != expected:
                raise AssertionError(
                    f"FAC {text}: {actual.hex()} != {expected.hex()}"
                )
            mapping_count += 1
    if transition_count != result["numericPredecessorCandidates"]:
        raise AssertionError("numeric predecessor count disagrees with summary")
    if mapping_count != result["outerNegativeFacMappings"]:
        raise AssertionError("negative-FAC mapping count disagrees with summary")
    print(
        f"validated {transition_count} predecessor transitions and "
        f"{mapping_count} negative-FAC mappings against the pinned ROM"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
