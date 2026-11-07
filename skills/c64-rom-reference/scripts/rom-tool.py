#!/usr/bin/env python3
"""Verify installed C64/1541 ROM assets and convert ROM addresses to offsets."""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
from pathlib import Path

from rom_manifest import ROMS, Rom


ROOT = Path(__file__).resolve().parents[1]
ROM_DIR = Path(os.environ.get("C64_ROM_DIR", ROOT / "assets" / "roms"))


def parse_number(value: str) -> int:
    value = value.strip().lower().replace("_", "")
    if value.startswith("$"):
        return int(value[1:], 16)
    return int(value, 0)


def get_rom(name: str) -> Rom:
    try:
        return ROMS[name]
    except KeyError as error:
        raise ValueError(f"unknown ROM {name!r}; choose: {', '.join(ROMS)}") from error


def verify(args: argparse.Namespace) -> int:
    failures = 0
    for name, rom in ROMS.items():
        path = ROM_DIR / rom.filename
        if not path.is_file():
            suffix = " (allowed)" if args.allow_missing else ""
            print(f"{name}: MISSING {path}{suffix}")
            failures += not args.allow_missing
            continue
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        valid = len(data) == rom.size and digest == rom.sha256
        status = "OK" if valid else "MISMATCH"
        print(
            f"{name}: {status}; revision={rom.revision}; size={len(data)} "
            f"(expected {rom.size}); sha256={digest}"
        )
        failures += not valid
    return int(failures > 0)


def offset(args: argparse.Namespace) -> int:
    rom = get_rom(args.rom)
    address = parse_number(args.address)
    if not rom.base <= address < rom.base + rom.size:
        raise ValueError(
            f"{args.rom} maps ${rom.base:04X}-${rom.base + rom.size - 1:04X}; "
            f"${address:04X} is outside it"
        )
    print(f"{args.rom} ${address:04X} -> file offset 0x{address - rom.base:04x}")
    return 0


def address(args: argparse.Namespace) -> int:
    rom = get_rom(args.rom)
    file_offset = parse_number(args.file_offset)
    if not 0 <= file_offset < rom.size:
        raise ValueError(
            f"{args.rom} size is 0x{rom.size:x}; offset 0x{file_offset:x} is outside it"
        )
    print(f"{args.rom} file offset 0x{file_offset:04x} -> ${rom.base + file_offset:04X}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    verify_parser = subparsers.add_parser(
        "verify", help="validate installed ROM sizes and SHA-256 hashes"
    )
    verify_parser.add_argument(
        "--allow-missing", action="store_true",
        help="succeed when files are absent, but still reject installed mismatches",
    )
    verify_parser.set_defaults(handler=verify)
    for command, argument, help_text, handler in (
        ("offset", "address", "convert CPU address to zero-based ROM file offset", offset),
        ("address", "file_offset", "convert zero-based ROM file offset to CPU address", address),
    ):
        command_parser = subparsers.add_parser(command, help=help_text)
        command_parser.add_argument("rom", choices=ROMS)
        command_parser.add_argument(argument)
        command_parser.set_defaults(handler=handler)
    args = parser.parse_args()
    try:
        return args.handler(args)
    except ValueError as error:
        parser.error(str(error))


if __name__ == "__main__":
    sys.exit(main())
