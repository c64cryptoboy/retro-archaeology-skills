#!/usr/bin/env python3
"""Throwaway exact-ROM runner for the C64 BASIC V2 RND advance at $E0BE."""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
from cpu6502 import Cpu6502Emulator

from rnd_paths import ROM_DIR
BASIC_PATH = ROM_DIR / "basic.bin"
KERNAL_PATH = ROM_DIR / "kernal.bin"
BASIC_SHA256 = "89878cea0a268734696de11c4bae593eaaa506465d2029d619c0e0cbccdfa62d"
KERNAL_SHA256 = "83c60d47047d7beab8e5b7bf6f67f80daa088b7a6a27de0d7e016f6484042721"
RNDX = 0x008B
RND_ADVANCE = 0xE0BE
INITIAL = bytes.fromhex("80 4f c7 52 58")
EXPECTED = (
    bytes.fromhex("7e 3e 04 7e 4e"),
    bytes.fromhex("7c 40 18 c8 69"),
)


def checked_rom(path: Path, expected_hash: str) -> bytes:
    data = path.read_bytes()
    actual = hashlib.sha256(data).hexdigest()
    if len(data) != 8192 or actual != expected_hash:
        raise SystemExit(
            f"refusing unexpected ROM {path}: size={len(data)}, sha256={actual}"
        )
    return data


def make_cpu() -> Cpu6502Emulator:
    cpu = Cpu6502Emulator()
    cpu.inject_bytes(0xA000, checked_rom(BASIC_PATH, BASIC_SHA256))
    cpu.inject_bytes(0xE000, checked_rom(KERNAL_PATH, KERNAL_SHA256))
    cpu.inject_bytes(RNDX, INITIAL)
    cpu.clear_memory_usage()
    return cpu


def advance(cpu: Cpu6502Emulator) -> bytes:
    cpu.init_cpu(RND_ADVANCE)
    cpu.exit_on_empty_stack = True
    instructions = 0
    while cpu.runcpu():
        instructions += 1
        if instructions >= 100_000:
            raise RuntimeError("RND advance exceeded instruction limit")
    return bytes(cpu.memory[RNDX:RNDX + 5])


def brent(cpu: Cpu6502Emulator, progress: int = 0) -> tuple[int, int, int]:
    """Find mu/lambda while making one mutable ROM-machine transition per step.

    Brent's first phase only needs the current hare and a saved five-byte state. To
    obtain mu afterward, restart two fresh ROM machines and advance one by lambda.
    """
    power = lam = 1
    tortoise = INITIAL
    hare = advance(cpu)
    transitions = 1
    while tortoise != hare:
        if power == lam:
            tortoise = hare
            power <<= 1
            lam = 0
        hare = advance(cpu)
        transitions += 1
        lam += 1
        if progress and transitions % progress == 0:
            print(f"phase1 transitions={transitions:,} power={power:,} lam={lam:,}", file=sys.stderr)

    tortoise_cpu = make_cpu()
    hare_cpu = make_cpu()
    for _ in range(lam):
        advance(hare_cpu)
    mu = 0
    tortoise = INITIAL
    hare = bytes(hare_cpu.memory[RNDX:RNDX + 5])
    while tortoise != hare:
        tortoise = advance(tortoise_cpu)
        hare = advance(hare_cpu)
        mu += 1
        transitions += 2
        if progress and mu % progress == 0:
            print(f"phase2 mu={mu:,} lambda={lam:,}", file=sys.stderr)
    return mu, lam, transitions


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--vectors-only", action="store_true")
    parser.add_argument("--progress", type=int, default=1_000_000)
    args = parser.parse_args()

    cpu = make_cpu()
    print(f"0: {INITIAL.hex(' ')}")
    for index, expected in enumerate(EXPECTED, 1):
        actual = advance(cpu)
        print(f"{index}: {actual.hex(' ')}")
        if actual != expected:
            raise SystemExit(
                f"vector {index} mismatch: expected {expected.hex(' ')}, got {actual.hex(' ')}"
            )
    print("supplied transition vectors match the pinned ROM")
    if args.vectors_only:
        return 0

    mu, lam, transitions = brent(make_cpu(), args.progress)
    print(f"on-ramp (mu): {mu}")
    print(f"cycle (lambda): {lam}")
    print(f"ROM transitions evaluated: {transitions}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
