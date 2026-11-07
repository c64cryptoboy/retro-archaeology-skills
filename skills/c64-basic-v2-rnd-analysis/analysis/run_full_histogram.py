#!/usr/bin/env python3
"""Hash-check ROMs and launch the restartable full RND histogram runner."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
from rnd_paths import ROM_DIR
DEFAULT_BASIC = ROM_DIR / "basic.bin"
DEFAULT_KERNAL = ROM_DIR / "kernal.bin"
BASIC_SHA256 = "89878cea0a268734696de11c4bae593eaaa506465d2029d619c0e0cbccdfa62d"
KERNAL_SHA256 = "83c60d47047d7beab8e5b7bf6f67f80daa088b7a6a27de0d7e016f6484042721"
DOMAIN_SIZE = 0xAF000000
METADATA_BYTES = DOMAIN_SIZE * 4
MINIMUM_EXTRA_FREE = 2 * 1024**3


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def checked_rom(path: Path, expected: str) -> str:
    actual = digest(path)
    size = path.stat().st_size
    if size != 8192 or actual != expected:
        raise SystemExit(
            f"refusing unexpected ROM {path}: size={size}, sha256={actual}"
        )
    return actual


def atomic_json(path: Path, value: object, exclusive: bool) -> None:
    temporary = path.with_name(path.name + f".tmp.{os.getpid()}")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    descriptor = os.open(temporary, flags, 0o644)
    try:
        with os.fdopen(descriptor, "w") as output:
            json.dump(value, output, indent=2, sort_keys=True)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        if exclusive and path.exists():
            raise FileExistsError(path)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("workdir", type=Path)
    parser.add_argument("mode", choices=("create", "resume"))
    parser.add_argument("--basic", type=Path, default=DEFAULT_BASIC)
    parser.add_argument("--kernal", type=Path, default=DEFAULT_KERNAL)
    parser.add_argument("--binary", type=Path, default=HERE / "full_rnd_histogram")
    parser.add_argument("--checkpoint-every", type=int, default=100_000_000)
    parser.add_argument("--stop-after-scans", type=int)
    parser.add_argument("--sparse", action="store_true",
                        help="testing only: do not reserve metadata blocks up front")
    args = parser.parse_args()

    if args.checkpoint_every <= 0:
        parser.error("--checkpoint-every must be positive")
    if args.stop_after_scans is not None and args.stop_after_scans <= 0:
        parser.error("--stop-after-scans must be positive")
    binary = args.binary.resolve()
    if not binary.is_file() or not os.access(binary, os.X_OK):
        raise SystemExit(f"runner is absent or not executable: {binary}")
    basic_hash = checked_rom(args.basic, BASIC_SHA256)
    kernal_hash = checked_rom(args.kernal, KERNAL_SHA256)

    workdir = args.workdir.resolve()
    parent = workdir.parent
    if not parent.is_dir():
        raise SystemExit(f"workdir parent does not exist: {parent}")
    if args.mode == "create":
        if workdir.exists():
            raise SystemExit(f"create refuses existing workdir: {workdir}")
        free = shutil.disk_usage(parent).free
        required = METADATA_BYTES + MINIMUM_EXTRA_FREE
        if not args.sparse and free < required:
            raise SystemExit(
                f"insufficient free space: need at least {required:,}, have {free:,}"
            )
    elif not workdir.is_dir():
        raise SystemExit(f"resume requires existing workdir: {workdir}")

    initial_manifest_path = workdir.with_name(workdir.name + "-launch.json")
    current = {
        "schema": "c64-basic-rnd-full-launch-v1",
        "createdUtc": datetime.now(timezone.utc).isoformat(),
        "workdir": str(workdir),
        "mode": args.mode,
        "domainSize": DOMAIN_SIZE,
        "metadataBytes": METADATA_BYTES,
        "basicPath": str(args.basic.resolve()),
        "basicSha256": basic_hash,
        "kernalPath": str(args.kernal.resolve()),
        "kernalSha256": kernal_hash,
        "runnerPath": str(binary),
        "runnerSha256": digest(binary),
        "checkpointEvery": args.checkpoint_every,
        "stopAfterScans": args.stop_after_scans,
        "sparse": args.sparse,
        "pushPerformed": False,
    }
    if args.mode == "resume":
        if not initial_manifest_path.exists():
            raise SystemExit(f"resume requires initial launch manifest: {initial_manifest_path}")
        previous = json.loads(initial_manifest_path.read_text())
        for key in ("domainSize", "metadataBytes", "basicSha256", "kernalSha256", "runnerSha256"):
            if previous.get(key) != current[key]:
                raise SystemExit(f"resume manifest mismatch for {key}")
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        manifest_path = workdir.with_name(workdir.name + f"-resume-{stamp}-{os.getpid()}.json")
    else:
        manifest_path = initial_manifest_path
    atomic_json(manifest_path, current, exclusive=True)

    command = [
        str(binary), str(args.basic.resolve()), str(args.kernal.resolve()),
        str(workdir), "--create" if args.mode == "create" else "--resume",
        f"--checkpoint-every={args.checkpoint_every}",
    ]
    if args.stop_after_scans is not None:
        command.append(f"--stop-after-scans={args.stop_after_scans}")
    if args.sparse:
        command.append("--sparse")
    print("validated launch:", " ".join(command), flush=True)
    os.execv(command[0], command)
    raise AssertionError("execv returned")


if __name__ == "__main__":
    raise SystemExit(main())
