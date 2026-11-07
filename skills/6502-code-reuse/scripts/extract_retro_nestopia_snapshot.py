#!/usr/bin/env python3
"""Extract NES memory and current PRG mappings from a Retro Debugger/Nestopia save.

Retro Debugger prefixes the standard Nestopia state chunk with an eight-byte
big-endian length and appends debugger/UI state. The iNES ROM is required to
reconstruct the PRG-ROM bytes visible through the mapper at snapshot time.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import zlib
from dataclasses import dataclass
from pathlib import Path

from region_manifest import (
    artifact_record,
    build_manifest,
    region_record,
    write_manifest,
)

ROOT_TAG = b"NST\x1a"
CHUNK_HEADER_SIZE = 8
CPU_RAM_SIZE = 2048
CPU_SPACE_SIZE = 65536
PRG_PAGE_SIZE = 8192


class SnapshotError(ValueError):
    pass


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def tag_text(tag: bytes) -> str:
    return "".join(chr(value) if 32 <= value < 127 else f"\\x{value:02x}" for value in tag)


@dataclass(frozen=True)
class Chunk:
    tag: bytes
    offset: int
    length: int
    payload_offset: int
    end: int

    def summary(self) -> dict:
        return {
            "tag": tag_text(self.tag),
            "offset": self.offset,
            "payloadOffset": self.payload_offset,
            "payloadSize": self.length,
            "endOffsetExclusive": self.end,
        }


def parse_chunk(data: bytes, offset: int, limit: int) -> Chunk:
    if offset + CHUNK_HEADER_SIZE > limit:
        raise SnapshotError(f"truncated Nestopia chunk header at offset {offset}")
    tag = data[offset:offset + 4]
    length = struct.unpack_from("<I", data, offset + 4)[0]
    payload = offset + CHUNK_HEADER_SIZE
    end = payload + length
    if end > limit:
        raise SnapshotError(
            f"chunk {tag_text(tag)!r} at {offset} ends at {end}, past limit {limit}"
        )
    return Chunk(tag, offset, length, payload, end)


def children(data: bytes, parent: Chunk) -> list[Chunk]:
    result = []
    position = parent.payload_offset
    while position < parent.end:
        child = parse_chunk(data, position, parent.end)
        result.append(child)
        position = child.end
    if position != parent.end:
        raise SnapshotError(f"child traversal failed for {tag_text(parent.tag)!r}")
    return result


def one_child(data: bytes, parent: Chunk, tag: bytes, required: bool = True) -> Chunk | None:
    matches = [chunk for chunk in children(data, parent) if chunk.tag == tag]
    if len(matches) > 1:
        raise SnapshotError(
            f"chunk {tag_text(parent.tag)!r} contains duplicate {tag_text(tag)!r} children"
        )
    if not matches:
        if required:
            raise SnapshotError(
                f"chunk {tag_text(parent.tag)!r} lacks {tag_text(tag)!r} child"
            )
        return None
    return matches[0]


def payload(data: bytes, chunk: Chunk) -> bytes:
    return data[chunk.payload_offset:chunk.end]


def uncompress_nestopia(data: bytes, chunk: Chunk, expected_size: int | None = None) -> bytes:
    raw = payload(data, chunk)
    if not raw:
        raise SnapshotError(f"compressed chunk {tag_text(chunk.tag)!r} is empty")
    mode, body = raw[0], raw[1:]
    if mode == 0:
        result = body
    elif mode == 1:
        try:
            result = zlib.decompress(body)
        except zlib.error as exc:
            raise SnapshotError(f"invalid zlib stream in {tag_text(chunk.tag)!r}") from exc
    else:
        raise SnapshotError(
            f"unsupported compression mode {mode} in {tag_text(chunk.tag)!r}"
        )
    if expected_size is not None and len(result) != expected_size:
        raise SnapshotError(
            f"{tag_text(chunk.tag)!r} expands to {len(result)} bytes; expected {expected_size}"
        )
    return result


def parse_bank_chunk(data: bytes, parent: Chunk) -> dict:
    access_chunk = one_child(data, parent, b"ACC\0")
    banks_chunk = one_child(data, parent, b"BNK\0")
    access = list(payload(data, access_chunk))
    bank_data = payload(data, banks_chunk)
    if len(bank_data) % 3:
        raise SnapshotError(f"{tag_text(parent.tag)!r}/BNK length is not divisible by three")
    banks = []
    for offset in range(0, len(bank_data), 3):
        source = bank_data[offset]
        bank = bank_data[offset + 1] | bank_data[offset + 2] << 8
        if source >= len(access):
            raise SnapshotError(
                f"{tag_text(parent.tag)!r} bank refers to absent source {source}"
            )
        banks.append({
            "source": source,
            "bank": bank,
            "readable": bool(access[source] & 1),
            "writable": bool(access[source] & 2),
        })
    return {"access": access, "banks": banks}


def parse_ines(data: bytes) -> dict:
    if len(data) < 16 or data[:4] != b"NES\x1a":
        raise SnapshotError("ROM is not an iNES image")
    if data[7] & 0x0C == 0x08:
        raise SnapshotError("NES 2.0 ROM sizing is not implemented")
    trainer_size = 512 if data[6] & 0x04 else 0
    prg_size = data[4] * 16384
    chr_size = data[5] * 8192
    prg_offset = 16 + trainer_size
    chr_offset = prg_offset + prg_size
    if prg_size == 0 or chr_offset + chr_size > len(data):
        raise SnapshotError("truncated or invalid iNES ROM")
    return {
        "mapper": (data[6] >> 4) | (data[7] & 0xF0),
        "prg": data[prg_offset:prg_offset + prg_size],
        "chr": data[chr_offset:chr_offset + chr_size],
        "prgOffset": prg_offset,
        "trainerSize": trainer_size,
    }


def map_source(
    image: bytearray,
    known: bytearray,
    segments: list[dict],
    address: int,
    page_size: int,
    bank_info: dict,
    sources: dict[int, tuple[str, bytes]],
) -> None:
    source_number = bank_info["source"]
    source = sources.get(source_number)
    segment = {
        "cpuStart": address,
        "cpuEndExclusive": address + page_size,
        "sourceIndex": source_number,
        "bank": bank_info["bank"],
        "readable": bank_info["readable"],
        "writable": bank_info["writable"],
    }
    if source is None:
        segment["known"] = False
        segment["reason"] = "source bytes unavailable"
        segments.append(segment)
        return

    source_name, source_bytes = source
    source_offset = bank_info["bank"] * page_size
    segment["source"] = source_name
    segment["sourceOffset"] = source_offset
    if not bank_info["readable"]:
        segment["known"] = False
        segment["reason"] = "snapshot marks selected source unreadable"
        segments.append(segment)
        return
    if source_offset + page_size > len(source_bytes):
        segment["known"] = False
        segment["reason"] = "selected bank exceeds supplied source"
        segments.append(segment)
        return

    block = source_bytes[source_offset:source_offset + page_size]
    image[address:address + page_size] = block
    known[address:address + page_size] = b"\xff" * page_size
    segment["known"] = True
    segments.append(segment)


def parse_snapshot(snapshot: bytes, rom: bytes) -> dict:
    if snapshot[:4] == ROOT_TAG:
        wrapper = "nestopia-state"
        state_start = 0
        state_size = len(snapshot)
    elif len(snapshot) >= 12 and snapshot[8:12] == ROOT_TAG:
        wrapper = "retrodebugger-nestopia"
        state_start = 8
        state_size = int.from_bytes(snapshot[:8], "big")
        if state_size <= 0 or state_start + state_size > len(snapshot):
            raise SnapshotError("invalid Retro Debugger Nestopia state length")
    else:
        raise SnapshotError("not a recognized Nestopia or Retro Debugger NES state")

    state_end = state_start + state_size
    root = parse_chunk(snapshot, state_start, state_end)
    if root.tag != ROOT_TAG or root.end != state_end:
        raise SnapshotError("Nestopia root chunk does not exactly fill declared state")

    top = children(snapshot, root)
    cpu_chunk = one_child(snapshot, root, b"CPU\0")
    reg_chunk = one_child(snapshot, cpu_chunk, b"REG\0")
    reg = payload(snapshot, reg_chunk)
    if len(reg) != 7:
        raise SnapshotError(f"CPU/REG has {len(reg)} bytes; expected seven")
    cpu = {
        "pc": reg[0] | reg[1] << 8,
        "sp": reg[2],
        "a": reg[3],
        "x": reg[4],
        "y": reg[5],
        "p": reg[6],
    }
    cpu_ram = uncompress_nestopia(
        snapshot, one_child(snapshot, cpu_chunk, b"RAM\0"), CPU_RAM_SIZE
    )

    info_chunk = one_child(snapshot, root, b"NFO\0")
    info = payload(snapshot, info_chunk)
    if len(info) < 8:
        raise SnapshotError("NFO chunk is too short")
    snapshot_prg_crc = struct.unpack_from("<I", info, 0)[0]
    nestopia_frame = struct.unpack_from("<I", info, 4)[0]

    image_chunk = one_child(snapshot, root, b"IMG\0")
    mapper_chunk = one_child(snapshot, image_chunk, b"MPR\0")
    work_chunk = one_child(snapshot, mapper_chunk, b"WRM\0", required=False)
    work_ram = uncompress_nestopia(snapshot, work_chunk) if work_chunk else b""
    prg_map = parse_bank_chunk(snapshot, one_child(snapshot, mapper_chunk, b"PRG\0"))
    work_map_chunk = one_child(snapshot, mapper_chunk, b"WRK\0", required=False)
    work_map = parse_bank_chunk(snapshot, work_map_chunk) if work_map_chunk else None

    ines = parse_ines(rom)
    prg_rom = ines["prg"]
    actual_crc = zlib.crc32(prg_rom) & 0xFFFFFFFF
    if snapshot_prg_crc and snapshot_prg_crc != actual_crc:
        raise SnapshotError(
            f"ROM PRG CRC32 {actual_crc:08x} does not match snapshot {snapshot_prg_crc:08x}"
        )

    cpu_visible = bytearray(CPU_SPACE_SIZE)
    known = bytearray(CPU_SPACE_SIZE)
    segments = []

    for address in range(0, 0x2000, CPU_RAM_SIZE):
        cpu_visible[address:address + CPU_RAM_SIZE] = cpu_ram
        known[address:address + CPU_RAM_SIZE] = b"\xff" * CPU_RAM_SIZE
        segments.append({
            "cpuStart": address,
            "cpuEndExclusive": address + CPU_RAM_SIZE,
            "source": "cpu-internal-ram",
            "sourceOffset": 0,
            "known": True,
            "canonical": address == 0,
        })

    if work_map:
        if len(work_map["banks"]) != 1:
            raise SnapshotError("WRK mapping does not contain exactly one 8 KiB page")
        map_source(
            cpu_visible,
            known,
            segments,
            0x6000,
            PRG_PAGE_SIZE,
            work_map["banks"][0],
            {0: ("work-ram", work_ram), 1: ("prg-rom", prg_rom)},
        )

    if len(prg_map["banks"]) != 4:
        raise SnapshotError("PRG mapping does not contain four 8 KiB pages")
    for index, bank_info in enumerate(prg_map["banks"]):
        map_source(
            cpu_visible,
            known,
            segments,
            0x8000 + index * PRG_PAGE_SIZE,
            PRG_PAGE_SIZE,
            bank_info,
            {0: ("prg-rom", prg_rom), 1: ("work-ram", work_ram)},
        )

    return {
        "metadata": {
            "format": wrapper,
            "stateOffset": state_start,
            "stateSize": state_size,
            "trailingDebuggerDataSize": len(snapshot) - state_end,
            "root": root.summary(),
            "topLevelChunks": [chunk.summary() for chunk in top],
            "cpu": cpu,
            "nestopiaFrame": nestopia_frame,
            "snapshotPrgCrc32": f"{snapshot_prg_crc:08x}",
            "romPrgCrc32": f"{actual_crc:08x}",
            "ines": {
                "mapper": ines["mapper"],
                "prgSize": len(prg_rom),
                "chrSize": len(ines["chr"]),
                "trainerSize": ines["trainerSize"],
            },
            "prgMapping": prg_map,
            "workMapping": work_map,
            "segments": segments,
            "unknownCpuRanges": [
                {
                    "start": 0x2000,
                    "endExclusive": 0x6000,
                    "reason": "NES PPU/APU/I/O/expansion space is not ordinary byte-addressable memory",
                }
            ],
        },
        "cpuRam": cpu_ram,
        "workRam": work_ram,
        "prgRom": prg_rom,
        "cpuVisible": bytes(cpu_visible),
        "knownMask": bytes(known),
    }


def output_info(path: Path, data: bytes, **extra: object) -> dict:
    path.write_bytes(data)
    result = {"path": path.name, "size": len(data), "sha256": sha256(data)}
    result.update(extra)
    return result


def extract_to_directory(
    snapshot_path: Path, rom_path: Path, output_dir: Path
) -> dict:
    snapshot = snapshot_path.read_bytes()
    rom = rom_path.read_bytes()
    result = parse_snapshot(snapshot, rom)
    metadata = result["metadata"]

    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = {}
    outputs["cpuInternalRam"] = output_info(
        output_dir / "nes-cpu-internal-ram.bin",
        result["cpuRam"],
        addressRange={"start": 0, "endExclusive": CPU_RAM_SIZE},
    )
    outputs["workRam"] = output_info(
        output_dir / "nes-work-ram.bin", result["workRam"]
    )
    outputs["prgRom"] = output_info(
        output_dir / "nes-prg-rom.bin", result["prgRom"]
    )
    outputs["cpuVisible"] = output_info(
        output_dir / "nes-cpu-visible.bin",
        result["cpuVisible"],
        addressRange={"start": 0, "endExclusive": CPU_SPACE_SIZE},
        warning="Consult knownByteMask and segments; zero-filled unknown I/O bytes are not memory evidence.",
    )
    outputs["knownByteMask"] = output_info(
        output_dir / "nes-cpu-visible-known-mask.bin",
        result["knownMask"],
        meaning="0xFF means cpu-visible byte is reconstructed; 0x00 means unknown/non-memory.",
    )

    metadata_output = dict(metadata)
    metadata_output["source"] = {
        "snapshot": {
            "path": str(snapshot_path),
            "size": len(snapshot),
            "sha256": sha256(snapshot),
        },
        "rom": {"path": str(rom_path), "size": len(rom), "sha256": sha256(rom)},
    }
    metadata_output["outputs"] = outputs
    metadata_path = output_dir / "metadata.json"
    metadata_path.write_text(json.dumps(metadata_output, indent=2) + "\n")

    regions = [
        region_record(
            region_id="nestopia-cpu-internal-ram",
            path=outputs["cpuInternalRam"]["path"],
            data=result["cpuRam"],
            kind="cpu-memory",
            base_address=0,
            cpu_profile="2a03",
            source={
                "container": "nestopia-state-chunk",
                "chunkPath": "NST/CPU/RAM",
                "meaning": "canonical physical 2 KiB internal CPU RAM",
            },
        )
    ]
    if result["workRam"]:
        regions.append(
            region_record(
                region_id="nestopia-work-ram",
                path=outputs["workRam"]["path"],
                data=result["workRam"],
                kind="cpu-memory",
                base_address=0x6000,
                cpu_profile="2a03",
                source={
                    "container": "nestopia-state-chunk",
                    "chunkPath": "NST/IMG/MPR/WRM",
                    "meaning": "physical cartridge work RAM; mapper visibility is optional capture metadata",
                },
            )
        )
    regions.extend(
        [
            region_record(
                region_id="ines-prg-rom",
                path=outputs["prgRom"]["path"],
                data=result["prgRom"],
                kind="cpu-program-rom",
                cpu_profile="2a03",
                source={
                    "container": "supporting-ines-rom",
                    "artifactPath": str(rom_path),
                    "fileOffset": parse_ines(rom)["prgOffset"],
                    "meaning": "physical PRG ROM bytes in bank order; no single CPU base address",
                },
            ),
            region_record(
                region_id="nestopia-cpu-visible-view",
                path=outputs["cpuVisible"]["path"],
                data=result["cpuVisible"],
                kind="derived-cpu-view",
                base_address=0,
                cpu_profile="2a03",
                scan_by_default=False,
                known_mask_path=outputs["knownByteMask"]["path"],
                known_mask=result["knownMask"],
                source={
                    "container": "derived-from-nestopia-mapper-state",
                    "meaning": "current CPU-visible reconstruction; disabled by default to avoid mirrors/PRG duplication",
                    "segments": metadata["segments"],
                },
            ),
        ]
    )
    capture = {
        **metadata,
        "supportingArtifacts": [
            {
                "path": str(rom_path),
                "format": "ines-rom",
                "size": len(rom),
                "sha256": sha256(rom),
            }
        ],
    }
    manifest = build_manifest(
        artifact=artifact_record(snapshot_path, snapshot, metadata["format"]),
        regions=regions,
        capture=capture,
    )
    write_manifest(output_dir / "regions.json", manifest)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("rom", type=Path, help="matching iNES ROM used to resolve PRG banks")
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()

    manifest = extract_to_directory(args.snapshot, args.rom, args.output_dir)
    metadata = manifest["capture"]
    print(
        f"wrote generic regions and current CPU view; "
        f"PC=${metadata['cpu']['pc']:04X}, mapper={metadata['ines']['mapper']}"
    )
    print(f"wrote {args.output_dir / 'metadata.json'}")
    print(f"wrote {args.output_dir / 'regions.json'}")


if __name__ == "__main__":
    main()
