#!/usr/bin/env python3
"""Targeted search over normalized negative decimal literals -.D (1..73 digits)."""
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from rnd_paths import ROM_DIR
EXE = HERE / "scratch/generated_fin"
BASIC = ROM_DIR / 'basic.bin'
KERNAL = ROM_DIR / 'kernal.bin'
TARGET = bytes.fromhex("80 81 23 45 00")

p = subprocess.Popen([str(EXE), str(BASIC), str(KERNAL)], stdin=subprocess.PIPE,
                     stdout=subprocess.PIPE, text=True, bufsize=1)
assert p.stdin and p.stdout

def parse(digits: str) -> bytes:
    text = "-." + digits
    p.stdin.write(text + "\n")
    p.stdin.flush()
    line = p.stdout.readline()
    if not line:
        raise RuntimeError("parser accelerator terminated")
    return bytes.fromhex(line.rstrip().split("\t")[-1])[:5]

# A target-sized 39-digit accumulator begins near 5.04e38, above the
# approximately 1.7e38 FAC maximum. FIN accumulates all digits before applying
# the decimal-point/exponent scale, so target-equivalent literals with 39 or
# more significant digits take the ROM overflow path.
for n in range(1, 39):
    lo, hi = 10 ** (n - 1), 10 ** n - 1
    while lo < hi:
        mid = (lo + hi) // 2
        value = parse(str(mid))
        if value < TARGET:
            lo = mid + 1
        else:
            hi = mid
    probes = range(max(10 ** (n - 1), lo - 2), min(10 ** n, lo + 3))
    found = [(d, parse(str(d))) for d in probes]
    for d, value in found:
        if value == TARGET:
            print(f"reachable with {n} digits: -.{d}")
            p.terminate()
            raise SystemExit(0)
    below = max((item for item in found if item[1] < TARGET), default=None,
                key=lambda item: item[1])
    above = min((item for item in found if item[1] > TARGET), default=None,
                key=lambda item: item[1])
    print(n, below and (below[0], below[1].hex()), above and (above[0], above[1].hex()))
p.stdin.close()
if p.wait() != 0:
    raise SystemExit(p.returncode)
print("not reachable with 1..38 significant digits; target-equivalent 39+ digit accumulators overflow before scaling")
