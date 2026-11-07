#!/usr/bin/env python3
"""Regenerate, compile, and differentially validate generated RND C blocks."""

from __future__ import annotations

import argparse
import os
import random
import statistics
import subprocess
import tempfile
import time
from pathlib import Path

import generate_specialized_rnd_c as generator
import throwaway_rom_cycle as oracle

HERE = Path(__file__).resolve().parent
ROMS = (oracle.BASIC_PATH, oracle.KERNAL_PATH)
FNV_OFFSET = 1469598103934665603
FNV_PRIME = 1099511628211
MASK64 = (1 << 64) - 1


def run(command: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, check=True, text=True, **kwargs)


def stream_digest(start: bytes, transitions: int) -> str:
    cpu = oracle.make_cpu()
    cpu.inject_bytes(oracle.RNDX, start)
    cpu.memory[0x68] = 0
    current = start
    digest = FNV_OFFSET
    for index in range(transitions + 1):
        for value in current:
            digest = ((digest ^ value) * FNV_PRIME) & MASK64
        if index < transitions:
            current = oracle.advance(cpu)
    return f"digest through x[{transitions}]: {digest:016x}"


def generated_digest(executable: Path, start: bytes, transitions: int) -> str:
    environment = {**os.environ, "RND_START": start.hex()}
    result = run(
        [str(executable), *(str(path) for path in ROMS), f"--digest={transitions}"],
        env=environment,
        capture_output=True,
    )
    return result.stdout.splitlines()[-1]


def validate_random_starts(executable: Path, cases: int) -> None:
    rng = random.Random(0x6502E0BE)
    starts = [
        bytes.fromhex(text)
        for text in (
            "0000000000", "0100000000", "017fffffff",
            "8000000000", "807fffffff", "804fc75258",
        )
    ]
    while len(starts) < cases:
        starts.append(bytes((
            rng.randrange(1, 0x81),
            rng.randrange(0x80),
            rng.randrange(256),
            rng.randrange(256),
            rng.randrange(256),
        )))
    counts = (1, 2, 3, 10, 30, 100)
    for index, start in enumerate(starts[:cases]):
        transitions = counts[index % len(counts)]
        expected = stream_digest(start, transitions)
        actual = generated_digest(executable, start, transitions)
        if actual != expected:
            raise AssertionError(
                f"start {start.hex()} through {transitions}: {actual!r} != {expected!r}"
            )


def benchmark(executable: Path) -> None:
    command = [str(executable), *(str(path) for path in ROMS), "--steps=1000000"]
    durations = []
    for _ in range(7):
        began = time.perf_counter()
        run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        durations.append(time.perf_counter() - began)
    median = statistics.median(durations)
    print(f"generated median: {median:.6f}s; {1_000_000 / median:,.0f} transitions/s")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--random-cases", type=int, default=32)
    parser.add_argument("--benchmark", action="store_true")
    parser.add_argument("--sanitize", action="store_true")
    args = parser.parse_args()

    basic = generator.checked(ROMS[0], generator.BASIC_SHA256)
    kernal = generator.checked(ROMS[1], generator.KERNAL_SHA256)
    memory = generator.make_memory(basic, kernal)
    generated = generator.generate(memory, generator.collect_cfg(memory))
    retained = (HERE / "generated_rnd_cycle.c").read_text()
    if generated != retained:
        raise AssertionError("retained generated_rnd_cycle.c is stale")

    with tempfile.TemporaryDirectory(prefix="rnd-generated-") as temporary:
        executable = Path(temporary) / "generated-rnd"
        command = [
            "gcc", "-O3", "-std=c11", "-Wall", "-Wextra", "-Werror",
            "-o", str(executable), str(HERE / "generated_rnd_cycle.c"),
        ]
        run(command)
        vector = run(
            [str(executable), *(str(path) for path in ROMS), "--vectors-only"],
            capture_output=True,
        ).stdout
        if "7e 3e 04 7e 4e" not in vector or "7c 40 18 c8 69" not in vector:
            raise AssertionError("generated vector output is incomplete")
        seen = run(
            [str(executable), *(str(path) for path in ROMS), "--seen"],
            capture_output=True,
        ).stdout
        for expected in (
            "first repeated index: 69871",
            "first seen index (mu): 11793",
            "cycle (lambda): 58078",
        ):
            if expected not in seen:
                raise AssertionError(f"missing generated result: {expected}")
        validate_random_starts(executable, args.random_cases)

        batch_executable = Path(temporary) / "batch-rnd"
        run([
            "gcc", "-O3", "-std=c11", "-Wall", "-Wextra", "-Werror",
            "-o", str(batch_executable), str(HERE / "batch_rnd_graph.c"),
        ])
        starts_file = Path(temporary) / "starts.txt"
        starts_file.write_text("804fc75258\n7e3e047e4e\n7f2277b9e3\n802ac973a3\n804fc75258\n")
        batch = run(
            [str(batch_executable), *(str(path) for path in ROMS), str(starts_file)],
            capture_output=True,
        )
        for expected in (
            "804fc75258,11793,58078",
            "7e3e047e4e,11792,58078",
            "7f2277b9e3,0,58078",
            "802ac973a3,1,58078",
        ):
            if expected not in batch.stdout:
                raise AssertionError(f"missing batch result: {expected}")
        if "unique_states=69871 transitions=69871" not in batch.stderr:
            raise AssertionError("batch graph did not reuse the classified component")

        if args.sanitize:
            sanitized = Path(temporary) / "generated-rnd-sanitized"
            run([
                "gcc", "-O1", "-g", "-std=c11", "-Wall", "-Wextra", "-Werror",
                "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
                "-o", str(sanitized), str(HERE / "generated_rnd_cycle.c"),
            ])
            run([str(sanitized), *(str(path) for path in ROMS), "--seen"],
                stdout=subprocess.DEVNULL)
            sanitized_batch = Path(temporary) / "batch-rnd-sanitized"
            run([
                "gcc", "-O1", "-g", "-std=c11", "-Wall", "-Wextra", "-Werror",
                "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
                "-o", str(sanitized_batch), str(HERE / "batch_rnd_graph.c"),
            ])
            run([str(sanitized_batch), *(str(path) for path in ROMS), str(starts_file)],
                stdout=subprocess.DEVNULL)
        if args.benchmark:
            benchmark(executable)

    print(f"generated C validation passed ({args.random_cases} starting states)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
