#!/usr/bin/env python3
"""Find verified short decimal literal spellings for maximum-total FAC preimages."""
from __future__ import annotations

import subprocess
from fractions import Fraction
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from negative_seed_image import SeedState, seed_preimages
from rnd_paths import ROM_DIR

EXE = HERE / "scratch/generated_fin"
SEEDS = [
    bytes.fromhex("76 57 66 2a 0c"),
    bytes.fromhex("7a 57 66 2a 0c"),
    bytes.fromhex("7c 57 66 2a 0c"),
    bytes.fromhex("7e 57 66 2a 0c"),
]


def fac_fraction(exponent: int, mantissa: int) -> Fraction:
    power = exponent - 160
    return Fraction(mantissa << power, 1) if power >= 0 else Fraction(mantissa, 1 << -power)


def floor_log10(value: Fraction) -> int:
    # Bit/digit-length estimate followed by exact rational adjustment.
    estimate = len(str(value.numerator)) - len(str(value.denominator))
    def ge_power(k: int) -> bool:
        return value >= (Fraction(10 ** k, 1) if k >= 0 else Fraction(1, 10 ** -k))
    while not ge_power(estimate):
        estimate -= 1
    while ge_power(estimate + 1):
        estimate += 1
    return estimate


class Fin:
    def __init__(self) -> None:
        self.process = subprocess.Popen(
            [str(EXE), str(ROM_DIR / "basic.bin"), str(ROM_DIR / "kernal.bin")],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1,
        )
        assert self.process.stdin and self.process.stdout

    def parse(self, text: str) -> bytes | None:
        assert self.process.stdin and self.process.stdout
        self.process.stdin.write(text + "\n")
        self.process.stdin.flush()
        line = self.process.stdout.readline()
        if not line:
            raise RuntimeError("generated FIN parser terminated")
        field = line.rstrip().split("\t")[-1]
        try:
            raw = bytes.fromhex(field)
        except ValueError:
            return None
        return raw[:5] if len(raw) >= 5 else None

    def close(self) -> None:
        assert self.process.stdin
        self.process.stdin.close()
        if self.process.wait() != 0:
            raise RuntimeError("generated FIN parser failed")


def find_literal(fin: Fin, target: bytes, value: Fraction, max_digits: int = 14) -> str | None:
    decimal_exponent = floor_log10(value)
    for digits in range(1, max_digits + 1):
        shift = digits - 1 - decimal_exponent
        scaled = value * (10 ** shift) if shift >= 0 else value / (10 ** -shift)
        center = scaled.numerator // scaled.denominator
        for significand in range(max(1, center - 8), center + 10):
            text_digits = str(significand)
            if len(text_digits) != digits:
                continue
            # -.D E(k+1) avoids dependence on decimal-point placement.
            text = f"-.{text_digits}E{decimal_exponent + 1}"
            if fin.parse(text) == target:
                return text
    return None


def main() -> None:
    fin = Fin()
    try:
        total = 0
        for seed_bytes in SEEDS:
            seed = SeedState.from_bytes(seed_bytes)
            preimages = seed_preimages(seed)
            print(f"seed {seed_bytes.hex(' ')} preimages {len(preimages)}")
            for fac in preimages:
                literal = find_literal(fin, fac.bytes, fac_fraction(fac.exponent, fac.mantissa))
                print(f"{fac.bytes.hex(' ')}\t{literal or 'UNFOUND'}")
                total += 1
        print(f"total {total}")
    finally:
        fin.close()


if __name__ == "__main__":
    main()
