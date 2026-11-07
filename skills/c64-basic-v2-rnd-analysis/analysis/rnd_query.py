#!/usr/bin/env python3
"""Query exact C64 BASIC V2 RND state/seed results without host floats."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import struct
from collections import defaultdict
from pathlib import Path

import canonical_seed_domain as domain
import negative_seed_image as negative

HERE = Path(__file__).resolve().parent
from rnd_paths import RUN_DIR as DEFAULT_RUN_DIR
CHECKPOINT_FORMAT = "<QIIQQQQII254IQ"
CHECKPOINT_MAGIC = 0x324B4348444E5252
CHECKPOINT_VERSION = 2
CHECKSUM_SALT = 0xC64B451C6502F00D
MASK64 = (1 << 64) - 1
REQUIRED_COMPACT_OUTPUTS = frozenset({
    "checkpoint.bin", "cycle-components.csv", "hist-lambda.csv",
    "hist-mu.csv", "hist-total.csv", "summary.json",
})


def parse_bytes(text: str, length: int = 5) -> bytes:
    compact = text.replace("$", "").replace(",", " ").replace(":", " ")
    try:
        value = bytes.fromhex("".join(compact.split()))
    except ValueError as error:
        raise argparse.ArgumentTypeError(str(error)) from error
    if len(value) != length:
        raise argparse.ArgumentTypeError(f"expected {length} bytes, got {len(value)}")
    return value


def state_from_bytes(data: bytes) -> domain.CanonicalState:
    seed = negative.SeedState.from_bytes(data)
    return domain.CanonicalState(seed.exponent, seed.mantissa)


def format_bytes(data: bytes) -> str:
    return data.hex(" ")


def rol64(value: int, count: int) -> int:
    return ((value << count) | (value >> (64 - count))) & MASK64


def read_checkpoint(run_dir: Path) -> tuple[dict[str, int], list[int]]:
    path = run_dir / "checkpoint.bin"
    raw = path.read_bytes()
    expected_size = struct.calcsize(CHECKPOINT_FORMAT)
    if len(raw) != expected_size:
        raise ValueError(f"checkpoint size is {len(raw)}, expected {expected_size}: {path}")
    values = struct.unpack(CHECKPOINT_FORMAT, raw)
    magic, version, size = values[:3]
    next_scan, classified, sequence, complete = values[3:7]
    class_count, reserved = values[7:9]
    all_lengths = list(values[9:9 + 254])
    stored_checksum = values[-1]
    checksum = (magic ^ version ^ size ^ next_scan ^ classified ^ sequence
                ^ complete ^ class_count ^ CHECKSUM_SALT) & MASK64
    for length in all_lengths:
        checksum = rol64(checksum, 7) ^ length
    if (magic != CHECKPOINT_MAGIC or version != CHECKPOINT_VERSION
            or size != domain.DOMAIN_SIZE or reserved != 0
            or not 0 <= class_count <= 254 or checksum != stored_checksum):
        raise ValueError(f"invalid or incompatible checkpoint: {path}")
    lengths = all_lengths[:class_count]
    if any(length == 0 for length in lengths):
        raise ValueError(f"checkpoint contains a zero cycle length: {path}")
    return {
        "nextScan": next_scan,
        "classifiedStates": classified,
        "checkpointSequence": sequence,
        "complete": complete,
        "cycleLengthClasses": class_count,
    }, lengths


def classify(seed_bytes: bytes, run_dir: Path) -> dict[str, int]:
    checkpoint, lengths = read_checkpoint(run_dir)
    if not checkpoint["complete"]:
        raise ValueError(f"classification is incomplete: {run_dir}")
    rank = domain.rank(state_from_bytes(seed_bytes))
    metadata = run_dir / "metadata.bin"
    expected_size = domain.DOMAIN_SIZE * 4
    if metadata.stat().st_size != expected_size:
        raise ValueError(f"metadata size is not {expected_size}: {metadata}")
    with metadata.open("rb") as stream:
        stream.seek(rank * 4)
        raw = stream.read(4)
    if len(raw) != 4:
        raise ValueError(f"short metadata read at rank {rank:,}")
    packed = struct.unpack("<I", raw)[0]
    cycle_class, mu = packed >> 24, packed & 0xFFFFFF
    if not 1 <= cycle_class <= len(lengths):
        raise ValueError(f"invalid metadata class {cycle_class} at rank {rank:,}")
    lam = lengths[cycle_class - 1]
    return {"rank": rank, "mu": mu, "lambda": lam, "total": mu + lam}


def component_rows(path: Path) -> list[dict[str, int]]:
    grouped: dict[int, list[tuple[int, int]]] = defaultdict(list)
    with path.open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            grouped[int(row["lambda"])].append((int(row["mu"]), int(row["count"])))
    output = []
    for number, length in enumerate(sorted(grouped), 1):
        rows = sorted(grouped[length])
        cycle = sum(count for mu, count in rows if mu == 0)
        transient = sum(count for mu, count in rows if mu > 0)
        target, cumulative, median = (transient + 1) // 2, 0, 0
        for mu, count in rows:
            if mu == 0:
                continue
            cumulative += count
            if cumulative >= target:
                median = mu
                break
        maximum = max((mu for mu, count in rows if mu > 0 and count), default=0)
        if cycle != length:
            raise ValueError(f"lambda {length}: expected {length} cycle nodes, found {cycle}")
        output.append({"loop": number, "lambda": length, "transient": transient,
                       "medianMu": median, "maxMu": maximum, "basin": cycle + transient})
    return output


def digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def command_domain(_: argparse.Namespace) -> None:
    print(f"canonical states: {domain.DOMAIN_SIZE:,} (${domain.DOMAIN_SIZE:08x})")


def command_rank(args: argparse.Namespace) -> None:
    print(domain.rank(state_from_bytes(args.seed)))


def command_unrank(args: argparse.Namespace) -> None:
    print(format_bytes(domain.unrank(args.rank).bytes))


def command_fac_to_seed(args: argparse.Namespace) -> None:
    fac = negative.NegativeFac(args.fac[0], int.from_bytes(args.fac[1:], "big"))
    print(format_bytes(negative.fac_to_seed(fac).bytes))


def command_preimages(args: argparse.Namespace) -> None:
    seed = negative.SeedState.from_bytes(args.seed)
    values = negative.seed_preimages(seed)
    print(f"preimages: {len(values)}")
    for value in values:
        print(format_bytes(value.bytes))


def command_classify(args: argparse.Namespace) -> None:
    result = classify(args.seed, args.run_dir)
    print(json.dumps(result, indent=2))


def command_components(args: argparse.Namespace) -> None:
    rows = component_rows(args.component_depth)
    print("loop  lambda  transient_states  median_mu  max_mu  basin_states")
    for row in rows:
        print(f"{row['loop']:>4} {row['lambda']:>7} {row['transient']:>17} "
              f"{row['medianMu']:>10} {row['maxMu']:>7} {row['basin']:>13}")


def command_verify(args: argparse.Namespace) -> None:
    manifest = args.run_dir / "final-output-sha256.txt"
    entries: dict[str, str] = {}
    for line in manifest.read_text(encoding="utf-8").splitlines():
        expected, name = line.split(maxsplit=1)
        if name in entries:
            raise ValueError(f"duplicate compact output in manifest: {name}")
        if name not in REQUIRED_COMPACT_OUTPUTS:
            raise ValueError(f"unexpected compact output in manifest: {name}")
        entries[name] = expected
    missing = REQUIRED_COMPACT_OUTPUTS - entries.keys()
    if missing:
        raise ValueError(f"missing required compact outputs: {', '.join(sorted(missing))}")
    for name, expected in entries.items():
        path = args.run_dir / name
        actual = digest(path)
        if actual != expected:
            raise ValueError(f"hash mismatch for {path}: {actual} != {expected}")
        print(f"OK {name} {actual}")
    checkpoint, _ = read_checkpoint(args.run_dir)
    if not checkpoint["complete"] or checkpoint["classifiedStates"] != domain.DOMAIN_SIZE:
        raise ValueError("checkpoint does not describe a complete domain")
    print(f"verified {len(entries)} compact outputs and complete checkpoint")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    item = sub.add_parser("domain", help="show the canonical domain size")
    item.set_defaults(function=command_domain)
    item = sub.add_parser("rank", help="convert canonical five-byte RNDX to rank")
    item.add_argument("seed", type=parse_bytes)
    item.set_defaults(function=command_rank)
    item = sub.add_parser("unrank", help="convert canonical rank to five-byte RNDX")
    item.add_argument("rank", type=lambda value: int(value, 0))
    item.set_defaults(function=command_unrank)
    item = sub.add_parser("fac-to-seed", help="map normalized negative FAC bytes to RNDX")
    item.add_argument("fac", type=parse_bytes,
                      help="five bytes: exponent plus restored 32-bit mantissa")
    item.set_defaults(function=command_fac_to_seed)
    item = sub.add_parser("preimages", help="list all valid negative-FAC preimages")
    item.add_argument("seed", type=parse_bytes)
    item.set_defaults(function=command_preimages)
    item = sub.add_parser("classify", help="read rank/mu/lambda from completed metadata")
    item.add_argument("seed", type=parse_bytes)
    item.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    item.set_defaults(function=command_classify)
    item = sub.add_parser("components", help="summarize exact component/depth aggregate")
    item.add_argument("--component-depth", type=Path,
                      default=DEFAULT_RUN_DIR / "component-depth.csv")
    item.set_defaults(function=command_components)
    item = sub.add_parser("verify-results", help="verify retained compact output hashes")
    item.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    item.set_defaults(function=command_verify)

    args = parser.parse_args()
    try:
        args.function(args)
    except (OSError, ValueError, IndexError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
