#!/usr/bin/env python3
"""Extract physical C64 RAM from a VICE snapshot file.

The parser follows VICE's module framing rather than searching for byte
patterns. It currently supports C64/C64SC snapshots with a C64MEM module.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

from region_manifest import (
    artifact_record,
    build_manifest,
    region_record,
    write_manifest,
)

SNAPSHOT_MAGIC = b"VICE Snapshot File\x1a"
VERSION_MAGIC = b"VICE Version\x1a"
MODULE_HEADER_SIZE = 22
C64_RAM_SIZE = 65536


class SnapshotError(ValueError):
    pass


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def padded_ascii(raw: bytes, field: str) -> str:
    value = raw.split(b"\0", 1)[0]
    try:
        return value.decode("ascii")
    except UnicodeDecodeError as exc:
        raise SnapshotError(f"{field} is not ASCII") from exc


def u32le(data: bytes, offset: int) -> int:
    if offset + 4 > len(data):
        raise SnapshotError(f"truncated little-endian DWORD at file offset {offset}")
    return struct.unpack_from("<I", data, offset)[0]


def parse_snapshot(data: bytes) -> dict:
    minimum_header = 19 + 2 + 16
    if len(data) < minimum_header or data[:19] != SNAPSHOT_MAGIC:
        raise SnapshotError("not a VICE snapshot (magic mismatch)")

    file_major, file_minor = data[19], data[20]
    machine = padded_ascii(data[21:37], "machine name")
    position = 37
    vice_version = None
    vice_revision = None

    if data[position:position + 13] == VERSION_MAGIC:
        if position + 21 > len(data):
            raise SnapshotError("truncated VICE version header")
        version_bytes = list(data[position + 13:position + 17])
        vice_version = version_bytes
        vice_revision = u32le(data, position + 17)
        position += 21

    modules = []
    by_name = {}
    while position < len(data):
        if position + MODULE_HEADER_SIZE > len(data):
            raise SnapshotError(f"truncated module header at file offset {position}")
        name = padded_ascii(data[position:position + 16], "module name")
        major = data[position + 16]
        minor = data[position + 17]
        size = u32le(data, position + 18)
        if size < MODULE_HEADER_SIZE:
            raise SnapshotError(f"module {name!r} has invalid size {size}")
        end = position + size
        if end > len(data):
            raise SnapshotError(
                f"module {name!r} extends past EOF: end={end}, file={len(data)}"
            )
        module = {
            "name": name,
            "major": major,
            "minor": minor,
            "offset": position,
            "size": size,
            "payloadOffset": position + MODULE_HEADER_SIZE,
            "payloadSize": size - MODULE_HEADER_SIZE,
            "endOffsetExclusive": end,
        }
        modules.append(module)
        by_name.setdefault(name, []).append(module)
        position = end

    if position != len(data):
        raise SnapshotError("module traversal did not end at EOF")

    if machine not in {"C64", "C64SC"}:
        raise SnapshotError(f"snapshot machine is {machine!r}, not C64/C64SC")
    if len(by_name.get("C64MEM", [])) != 1:
        raise SnapshotError("snapshot must contain exactly one C64MEM module")

    mem_module = by_name["C64MEM"][0]
    payload = mem_module["payloadOffset"]
    required = 4 + C64_RAM_SIZE
    if mem_module["payloadSize"] < required:
        raise SnapshotError(
            f"C64MEM payload is {mem_module['payloadSize']} bytes; need at least {required}"
        )

    cpu_port_data = data[payload]
    cpu_port_direction = data[payload + 1]
    exrom = data[payload + 2]
    game = data[payload + 3]
    ram_offset = payload + 4
    ram = data[ram_offset:ram_offset + C64_RAM_SIZE]

    cpu = None
    main_modules = by_name.get("MAINCPU", [])
    if len(main_modules) == 1:
        main = main_modules[0]
        p = main["payloadOffset"]
        # VICE 3.9 MAINCPU v1.4 writes an eight-byte CLOCK, then A/X/Y/SP,
        # little-endian PC, and P. Leave other versions un-interpreted.
        if (main["major"], main["minor"]) == (1, 4) and main["payloadSize"] >= 15:
            clock = struct.unpack_from("<Q", data, p)[0]
            cpu = {
                "clock": clock,
                "a": data[p + 8],
                "x": data[p + 9],
                "y": data[p + 10],
                "sp": data[p + 11],
                "pc": struct.unpack_from("<H", data, p + 12)[0],
                "p": data[p + 14],
            }

    return {
        "format": "vice-snapshot",
        "fileVersion": {"major": file_major, "minor": file_minor},
        "machine": machine,
        "viceVersionBytes": vice_version,
        "viceRevision": vice_revision,
        "modules": modules,
        "c64Memory": {
            "moduleVersion": {
                "major": mem_module["major"],
                "minor": mem_module["minor"],
            },
            "cpuPortData": cpu_port_data,
            "cpuPortDirection": cpu_port_direction,
            "exrom": exrom,
            "game": game,
            "ramFileOffset": ram_offset,
            "ramSize": len(ram),
            "ramSha256": sha256(ram),
        },
        "cpu": cpu,
        "ram": ram,
    }


def extract_to_directory(snapshot_path: Path, output_dir: Path) -> dict:
    source = snapshot_path.read_bytes()
    parsed = parse_snapshot(source)
    ram = parsed["ram"]

    output_dir.mkdir(parents=True, exist_ok=True)
    ram_path = output_dir / "c64-physical-ram.bin"
    metadata_path = output_dir / "metadata.json"
    ram_path.write_bytes(ram)

    metadata = {key: value for key, value in parsed.items() if key != "ram"}
    metadata["source"] = {
        "path": str(snapshot_path),
        "size": len(source),
        "sha256": sha256(source),
    }
    metadata["outputs"] = {
        "physicalRam": {
            "path": ram_path.name,
            "size": len(ram),
            "sha256": sha256(ram),
            "addressRange": {"start": 0, "endExclusive": 65536},
            "meaning": "physical C64 RAM beneath any currently mapped ROM or I/O",
        }
    }
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n")

    memory = parsed["c64Memory"]
    region = region_record(
        region_id="vice-c64-physical-ram",
        path=ram_path.name,
        data=ram,
        kind="cpu-memory",
        base_address=0,
        cpu_profile="6502-nmos",
        source={
            "container": "vice-snapshot-module",
            "module": "C64MEM",
            "moduleVersion": memory["moduleVersion"],
            "fileOffset": memory["ramFileOffset"],
            "endOffsetExclusive": memory["ramFileOffset"] + len(ram),
            "meaning": "physical C64 RAM beneath any currently mapped ROM or I/O",
        },
    )
    manifest = build_manifest(
        artifact=artifact_record(snapshot_path, source, parsed["format"]),
        regions=[region],
        capture={
            "fileVersion": parsed["fileVersion"],
            "machine": parsed["machine"],
            "viceVersionBytes": parsed["viceVersionBytes"],
            "viceRevision": parsed["viceRevision"],
            "cpu": parsed["cpu"],
            "cpuPort": {
                "data": memory["cpuPortData"],
                "direction": memory["cpuPortDirection"],
                "exrom": memory["exrom"],
                "game": memory["game"],
            },
        },
    )
    write_manifest(output_dir / "regions.json", manifest)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()

    manifest = extract_to_directory(args.snapshot, args.output_dir)
    region = manifest["regions"][0]
    print(
        f"wrote {args.output_dir / region['path']} "
        f"({region['size']} bytes, SHA-256 {region['sha256']})"
    )
    print(f"wrote {args.output_dir / 'metadata.json'}")
    print(f"wrote {args.output_dir / 'regions.json'}")


if __name__ == "__main__":
    main()
