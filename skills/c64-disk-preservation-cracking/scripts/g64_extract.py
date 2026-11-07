#!/usr/bin/env python3
"""Read standard 1541 sectors from a G64 and list/extract directory files.

Decoding does not modify the input.  Extraction refuses output paths that
resolve to the input or identify the same existing file, including hardlinks.
This pre-write check is not race-proof; output writes are not atomic.
It decodes GCR header/data blocks, verifies checksums, follows the directory
chain, and extracts a selected file by its recorded track/sector chain.
It does not emulate a drive or handle arbitrary copy-protection formats whose
sectors are not standard Commodore blocks.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


GCR_TO_NIBBLE = {
    0x0A: 0x0, 0x0B: 0x1, 0x12: 0x2, 0x13: 0x3,
    0x0E: 0x4, 0x0F: 0x5, 0x16: 0x6, 0x17: 0x7,
    0x09: 0x8, 0x19: 0x9, 0x1A: 0xA, 0x1B: 0xB,
    0x0D: 0xC, 0x1D: 0xD, 0x1E: 0xE, 0x15: 0xF,
}

FILE_TYPES = {
    0: "DEL", 1: "SEQ", 2: "PRG", 3: "USR",
    4: "REL", 5: "CBM", 6: "DIR",
}


@dataclass(frozen=True)
class DecodedSector:
    track: int
    sector: int
    data: bytes
    physical_slot: int
    header_bit: int
    data_bit: int
    header_checksum_valid: bool
    data_checksum_valid: bool
    disk_id_hex: str


class G64Error(ValueError):
    pass


def xor_bytes(values: Iterable[int]) -> int:
    value = 0
    for item in values:
        value ^= item
    return value


def petscii_name(raw: bytes) -> str:
    # Normal 1541 names are padded with $A0. Some intentionally odd directory
    # entries switch to zero padding after the visible name.
    raw = raw.rstrip(b"\xA0\x00")
    result = []
    for value in raw:
        if value == 0xA0:
            result.append(" ")
        elif 0x20 <= value <= 0x7E:
            result.append(chr(value))
        elif 0xC1 <= value <= 0xDA:
            result.append(chr(value - 0x80))
        else:
            result.append(f"\\x{value:02x}")
    return "".join(result).rstrip()


def bytes_to_bits(data: bytes) -> list[int]:
    return [((value >> shift) & 1) for value in data for shift in range(7, -1, -1)]


def decode_gcr(bits: list[int], start: int, byte_count: int) -> bytes | None:
    output = bytearray()
    bit_count = len(bits)
    for nibble_index in range(byte_count * 2):
        encoded = 0
        nibble_start = start + nibble_index * 5
        for offset in range(5):
            encoded = (encoded << 1) | bits[(nibble_start + offset) % bit_count]
        nibble = GCR_TO_NIBBLE.get(encoded)
        if nibble is None:
            return None
        if nibble_index & 1:
            output[-1] |= nibble
        else:
            output.append(nibble << 4)
    return bytes(output)


def find_sync_ends(bits: list[int], minimum_ones: int = 10) -> list[tuple[int, int]]:
    runs: list[tuple[int, int]] = []
    index = 0
    while index < len(bits):
        if bits[index] == 0:
            index += 1
            continue
        end = index
        while end < len(bits) and bits[end] == 1:
            end += 1
        if end - index >= minimum_ones:
            runs.append((index, end))
        index = end
    return runs


def decode_track(track_bytes: bytes, physical_slot: int) -> list[DecodedSector]:
    bits = bytes_to_bits(track_bytes)
    if not bits or 0 not in bits:
        return []
    # Start at a zero so a sync run split by the stored track boundary is whole.
    pivot = bits.index(0)
    ring = bits[pivot:] + bits[:pivot]
    blocks: list[tuple[int, str, bytes | None]] = []
    for sync_start, sync_end in find_sync_ends(ring):
        sync_start = (sync_start + pivot) % len(bits)
        header = decode_gcr(ring, sync_end, 8)
        if header is not None and header[0] == 0x08:
            blocks.append((sync_start, "header", header))
            continue
        # Only marker + payload + checksum are essential; trailer GCR is unused.
        data = decode_gcr(ring, sync_end, 258)
        if data is not None and data[0] == 0x07:
            blocks.append((sync_start, "data", data))
        else:
            # Unknown sync blocks must break association, not be skipped.
            blocks.append((sync_start, "unknown", None))

    sectors: list[DecodedSector] = []
    if len(blocks) < 2:
        return sectors
    for index, (header_bit, kind, header) in enumerate(blocks):
        if kind != "header":
            continue
        data_bit, next_kind, encoded_data = blocks[(index + 1) % len(blocks)]
        if next_kind != "data":
            continue
        assert header is not None and encoded_data is not None
        sector_number = header[2]
        track_number = header[3]
        payload = encoded_data[1:257]
        sectors.append(DecodedSector(
            track=track_number,
            sector=sector_number,
            data=payload,
            physical_slot=physical_slot,
            header_bit=header_bit,
            data_bit=data_bit,
            header_checksum_valid=(header[1] == xor_bytes(header[2:6])),
            data_checksum_valid=(encoded_data[257] == xor_bytes(payload)),
            disk_id_hex=header[4:6].hex(),
        ))
    return sectors


def sector_evidence(sector: DecodedSector) -> dict:
    return {
        "physicalSlot": sector.physical_slot,
        "headerBit": sector.header_bit,
        "dataBit": sector.data_bit,
        "headerChecksumValid": sector.header_checksum_valid,
        "dataChecksumValid": sector.data_checksum_valid,
        "diskIdHex": sector.disk_id_hex,
        "payloadSha256": hashlib.sha256(sector.data).hexdigest(),
    }


def read_g64(path: Path) -> tuple[dict[tuple[int, int], DecodedSector], dict]:
    image = path.read_bytes()
    if len(image) < 12 or image[:8] != b"GCR-1541":
        raise G64Error("not a GCR-1541 G64 image")
    version = image[8]
    slot_count = image[9]
    max_track_size = int.from_bytes(image[10:12], "little")
    if version != 0:
        raise G64Error(f"unsupported G64 version {version}")
    table_end = 12 + slot_count * 8
    if table_end > len(image):
        raise G64Error("truncated G64 track/speed tables")

    offsets = [
        int.from_bytes(image[12 + slot * 4:16 + slot * 4], "little")
        for slot in range(slot_count)
    ]
    speed_base = 12 + slot_count * 4
    speeds = [
        int.from_bytes(image[speed_base + slot * 4:speed_base + slot * 4 + 4], "little")
        for slot in range(slot_count)
    ]

    sector_map: dict[tuple[int, int], DecodedSector] = {}
    candidates: dict[tuple[int, int], list[DecodedSector]] = {}
    slots: list[dict] = []
    for slot, offset in enumerate(offsets):
        if offset == 0:
            continue
        if offset < table_end:
            raise G64Error(f"track slot {slot} overlaps G64 header/track/speed tables")
        if offset + 2 > len(image):
            raise G64Error(f"track slot {slot} points outside image")
        length = int.from_bytes(image[offset:offset + 2], "little")
        if length > max_track_size or offset + 2 + length > len(image):
            raise G64Error(f"invalid track length {length} in slot {slot}")
        decoded = decode_track(image[offset + 2:offset + 2 + length], slot)
        slots.append({
            "slot": slot,
            "nominalTrack": slot // 2 + 1,
            "halfTrack": bool(slot & 1),
            "offset": offset,
            "length": length,
            "speed": speeds[slot],
            "decodedSectors": len(decoded),
        })
        for sector in decoded:
            key = (sector.track, sector.sector)
            candidates.setdefault(key, []).append(sector)
            existing = sector_map.get(key)
            if existing is not None:
                if existing.header_checksum_valid and existing.data_checksum_valid:
                    continue
            sector_map[key] = sector

    # Keep the existing selection policy: first checksum-valid candidate, or
    # last candidate if none is valid.  Describe the final selection, not a
    # provisional winner that a later candidate may replace.
    duplicates: list[dict] = []
    for key, copies in candidates.items():
        selected = sector_map[key]
        for duplicate in copies:
            if duplicate is selected:
                continue
            identical = selected.data == duplicate.data
            duplicates.append({
                "track": key[0],
                "sector": key[1],
                "keptSlot": selected.physical_slot,
                "duplicateSlot": duplicate.physical_slot,
                "selected": sector_evidence(selected),
                "duplicate": sector_evidence(duplicate),
                "payloadRelation": "identical" if identical else "different",
                "conflictingValidPayloads": (
                    not identical and selected.header_checksum_valid
                    and selected.data_checksum_valid and duplicate.header_checksum_valid
                    and duplicate.data_checksum_valid
                ),
            })

    metadata = {
        "path": str(path),
        "size": len(image),
        "sha256": hashlib.sha256(image).hexdigest(),
        "version": version,
        "trackSlots": slot_count,
        "maxTrackSize": max_track_size,
        "decodedSectorCount": len(sector_map),
        "slots": slots,
        "duplicates": duplicates,
    }
    return sector_map, metadata


def require_sector(sectors: dict[tuple[int, int], DecodedSector], track: int, sector: int) -> DecodedSector:
    result = sectors.get((track, sector))
    if result is None:
        raise G64Error(f"missing standard sector T{track}/S{sector}")
    if not result.header_checksum_valid:
        raise G64Error(f"invalid header checksum at T{track}/S{sector}")
    if not result.data_checksum_valid:
        raise G64Error(f"invalid data checksum at T{track}/S{sector}")
    return result


def read_directory(sectors: dict[tuple[int, int], DecodedSector]) -> tuple[dict, list[dict]]:
    bam = require_sector(sectors, 18, 0).data
    disk = {
        "name": petscii_name(bam[0x90:0xA0]),
        "id": petscii_name(bam[0xA2:0xA4]),
        "dosType": petscii_name(bam[0xA5:0xA7]),
        "firstDirectoryTrack": bam[0],
        "firstDirectorySector": bam[1],
    }
    track, sector = bam[0], bam[1]
    seen: set[tuple[int, int]] = set()
    directory_chain: list[str] = []
    entries: list[dict] = []
    while track:
        key = (track, sector)
        if key in seen:
            raise G64Error(f"directory chain loop at T{track}/S{sector}")
        seen.add(key)
        data = require_sector(sectors, track, sector).data
        directory_chain.append(f"{track}/{sector}")
        next_track, next_sector = data[0], data[1]
        for slot in range(8):
            raw = data[2 + slot * 32:2 + (slot + 1) * 32]
            file_type = raw[0]
            if file_type == 0:
                continue
            entries.append({
                "index": len(entries),
                "directoryTrack": track,
                "directorySector": sector,
                "slot": slot,
                "rawType": file_type,
                "type": FILE_TYPES.get(file_type & 0x07, f"TYPE{file_type & 0x07}"),
                "closed": bool(file_type & 0x80),
                "locked": bool(file_type & 0x40),
                "name": petscii_name(raw[3:19]),
                "nameHex": raw[3:19].hex(),
                "startTrack": raw[1],
                "startSector": raw[2],
                "reportedBlocks": int.from_bytes(raw[28:30], "little"),
                "rawHex": raw.hex(),
            })
        track, sector = next_track, next_sector
    disk["directoryChain"] = directory_chain
    return disk, entries


def extract_chain(
    sectors: dict[tuple[int, int], DecodedSector], start_track: int, start_sector: int
) -> tuple[bytes, list[dict]]:
    output = bytearray()
    chain: list[dict] = []
    seen: set[tuple[int, int]] = set()
    track, sector = start_track, start_sector
    while track:
        key = (track, sector)
        if key in seen:
            raise G64Error(f"file chain loop at T{track}/S{sector}")
        seen.add(key)
        decoded = require_sector(sectors, track, sector)
        data = decoded.data
        next_track, next_sector = data[0], data[1]
        if next_track == 0:
            byte_count = max(0, next_sector - 1)
            output.extend(data[2:2 + byte_count])
        else:
            byte_count = 254
            output.extend(data[2:])
        chain.append({
            "track": track,
            "sector": sector,
            "nextTrack": next_track,
            "nextSector": next_sector,
            "payloadBytes": byte_count,
            "physicalSlot": decoded.physical_slot,
            "headerBit": decoded.header_bit,
            "dataBit": decoded.data_bit,
        })
        track, sector = next_track, next_sector
    return bytes(output), chain


def ensure_distinct_output(image: Path, output: Path) -> None:
    """Reject stable path/inode aliases, not concurrent filesystem changes.

    Resolve symlinks (including parent directories) and relative spellings;
    samefile also catches hardlinks.  Missing output files are allowed.
    Other resolution/stat errors propagate rather than bypassing the check.
    """
    if output.resolve() == image.resolve():
        raise G64Error("output path identifies the input image")
    try:
        same_file = output.samefile(image)
    except FileNotFoundError:
        same_file = False
    if same_file:
        raise G64Error("output path identifies the input image")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("--extract", metavar="NAME", help="extract the first exact directory-name match")
    parser.add_argument("--output", type=Path, help="output path for --extract")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    sectors, metadata = read_g64(args.image)
    disk, entries = read_directory(sectors)
    result: dict = {"image": metadata, "disk": disk, "entries": entries}

    if args.extract is not None:
        matches = [entry for entry in entries if entry["name"] == args.extract]
        if not matches:
            raise SystemExit(f"no directory entry named {args.extract!r}")
        entry = matches[0]
        payload, chain = extract_chain(sectors, entry["startTrack"], entry["startSector"])
        output = args.output or Path(f"{args.extract}.prg")
        ensure_distinct_output(args.image, output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(payload)
        load_address = int.from_bytes(payload[:2], "little") if len(payload) >= 2 else None
        result["extraction"] = {
            "entry": entry,
            "output": str(output),
            "byteCount": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
            "loadAddress": load_address,
            "chain": chain,
        }

    if args.json:
        print(json.dumps(result, indent=2))
        return

    print(f'0 "{disk["name"]}" {disk["id"]} {disk["dosType"]}')
    for entry in entries:
        marker = " " if entry["closed"] else "*"
        lock = "<" if entry["locked"] else ""
        print(
            f'{entry["reportedBlocks"]:5d} "{entry["name"]}" '
            f'{marker}{entry["type"]}{lock} T{entry["startTrack"]}/S{entry["startSector"]}'
        )
    if "extraction" in result:
        extraction = result["extraction"]
        load_address = extraction["loadAddress"]
        load_display = f"${load_address:04X}" if load_address is not None else "unavailable"
        print(
            f'wrote {extraction["output"]}: {extraction["byteCount"]} bytes, '
            f'load={load_display}, SHA-256 {extraction["sha256"]}'
        )
        print("chain: " + " -> ".join(
            f'T{item["track"]}/S{item["sector"]}' for item in extraction["chain"]
        ))


if __name__ == "__main__":
    main()
