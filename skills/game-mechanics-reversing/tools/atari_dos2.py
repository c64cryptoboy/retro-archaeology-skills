#!/usr/bin/env python3
"""Extract raw DOS 2.0 files without executing or decoding their contents.

Scope: 16-byte ATR header, 128-byte sectors, at least 720 physical sectors,
VTOC code 2, and initial allocation count 707.  File allocation ends at 719.
Larger containers are allowed, but a nonzero sector 1024 is conservatively
rejected as ambiguous VTOC2 evidence.  DOS 2.5, other densities, deleted-file
recovery, and BASIC decoding are not supported.

Manifest: ``entries`` retains all 64 directory slots, raw names/entries, flags,
chain order, byte boundaries, and generic issue codes.  ``allocated.bin`` holds
observed in-map chain sectors, including trailers.  ``observed-payload.bin``
and ``slack.bin`` concatenate only sectors with valid used-byte counts, stopping
before an invalid count.  Their per-sector offsets are recorded in ``chain``.
``trailers.bin`` includes every observed sector's three trailer bytes.
``payload.bin`` is emitted only for an issue-free entry, after cross-link checks.
Neither observed bytes nor an issue-free chain imply valid application content.
Global ``issues`` concern allocation metadata; per-entry issues concern files.
Extra physical sectors and unowned allocated sectors are separate raw evidence,
never assigned to a repaired file.  Names are display metadata, never paths.

Format references (facts, not copied implementation): Joseph H. Allen's
atari-tools, revision 835d5a6fc1258921949fe92400adb789c398b9c3:
https://github.com/jhallen/atari-tools/blob/835d5a6fc1258921949fe92400adb789c398b9c3/readme.md
https://github.com/jhallen/atari-tools/blob/835d5a6fc1258921949fe92400adb789c398b9c3/atr.c
The referenced atr.c bears Copyright (C) 2011 Joseph H. Allen and GPL-1.0-or-later
terms.  No upstream code or token tables are bundled or executed here.
"""

import struct


SECTOR_SIZE = 128
LAST_ALLOCATED_SECTOR = 719
RESERVED_SECTORS = frozenset((0, 1, 2, 3, *range(360, 369)))


def read_image(data: bytes) -> tuple[dict, dict[str, bytes]]:
    """Return a JSON-safe manifest and slot-named artifacts; never write files.

    Raise ValueError for malformed ATR geometry or an unsupported filesystem
    profile.  Report damaged supported-profile chains in the manifest instead.
    """
    if len(data) < 16:
        raise ValueError("ATR header is shorter than 16 bytes")
    magic, low, sector_size, high = struct.unpack_from("<HHHH", data)
    if magic != 0x0296:
        raise ValueError("Invalid ATR magic")
    if sector_size != SECTOR_SIZE:
        raise ValueError("Unsupported ATR density: sector size must be 128 bytes")
    declared_bytes = (low | (high << 16)) * 16
    if declared_bytes != len(data) - 16:
        raise ValueError("ATR declared size does not match the physical payload")
    if declared_bytes % SECTOR_SIZE:
        raise ValueError("ATR payload is not a whole number of 128-byte sectors")
    physical_sectors = declared_bytes // SECTOR_SIZE
    if physical_sectors < 720:
        raise ValueError("DOS 2.0 requires at least 720 physical sectors")

    def sector(number):
        offset = 16 + (number - 1) * SECTOR_SIZE
        return data[offset:offset + SECTOR_SIZE]

    vtoc = sector(360)
    initial_free, current_free = struct.unpack_from("<HH", vtoc, 1)
    if vtoc[0] != 2 or initial_free != 707:
        raise ValueError("Unsupported VTOC profile: require DOS 2.0 code 2 and count 707")
    if physical_sectors >= 1024 and any(sector(1024)):
        raise ValueError("Unsupported nonzero sector 1024: possible DOS 2.5/VTOC2")

    def is_free(number):
        return bool(vtoc[10 + number // 8] & (0x80 >> (number % 8)))

    artifacts = {
        "metadata/atr-header.bin": data[:16],
        "metadata/boot.bin": data[16:16 + 3 * SECTOR_SIZE],
        "metadata/vtoc.bin": vtoc,
        "metadata/directory.bin": data[16 + 360 * SECTOR_SIZE:16 + 368 * SECTOR_SIZE],
        "evidence/outside-allocation-map.bin": data[16 + 719 * SECTOR_SIZE:],
    }
    entries = []
    owners = {}
    directory_ended = False
    for slot in range(64):
        directory_sector = 361 + slot // 8
        directory_offset = (slot % 8) * 16
        raw = sector(directory_sector)[directory_offset:directory_offset + 16]
        flags = raw[0]
        declared_sectors, first_sector = struct.unpack_from("<HH", raw, 1)
        name = raw[5:13].decode("ascii", "backslashreplace").rstrip(" ")
        extension = raw[13:16].decode("ascii", "backslashreplace").rstrip(" ")
        active = bool(flags & 0x40) and not bool(flags & 0x80)
        # Enhanced-density entries can have bit 0 set without the in-use bit.
        if not flags & 0x80 and ((flags & 1 and not flags & 0x40)
                                or (active and (not flags & 2 or flags & 0x1c))):
            raise ValueError(f"Unsupported directory flags 0x{flags:02x} in slot {slot}")
        entry = {
            "id": f"entry-{slot:03d}", "slot": slot,
            "directory_sector": directory_sector, "directory_offset": directory_offset,
            "atr_entry_offset": 16 + (directory_sector - 1) * SECTOR_SIZE + directory_offset,
            "raw_entry_hex": raw.hex(), "name_raw_hex": raw[5:16].hex(),
            "name": name + ("." + extension if extension else ""),
            "flags": flags, "active": active, "deleted": bool(flags & 0x80),
            "locked": bool(flags & 0x20), "open_for_output": bool(flags & 1),
            "dos2": bool(flags & 2), "declared_sectors": declared_sectors,
            "first_sector": first_sector, "issues": [],
        }
        entries.append(entry)
        if not flags & 0xc0:
            directory_ended = True
        if not active:
            continue
        issues = entry["issues"]
        if directory_ended:
            issues.append({"code": "active_after_directory_end"})
        if flags & 1:
            issues.append({"code": "open_for_output"})
        chain, raw_chunks, payload, slack, trailers = [], [], [], [], []
        payload_size = slack_size = 0
        seen = set()
        number = first_sector
        terminated = number == 0
        while number:
            outside_image = not 1 <= number <= physical_sectors
            outside_map = number > LAST_ALLOCATED_SECTOR
            if outside_image:
                issues.append({"code": "link_out_of_bounds", "sector": number})
            if outside_map:
                issues.append({"code": "link_out_of_map", "sector": number})
            if outside_image or outside_map:
                break
            if number in RESERVED_SECTORS:
                issues.append({"code": "reserved_sector_link", "sector": number})
                break
            if number in seen:
                issues.append({"code": "chain_loop", "sector": number})
                break
            seen.add(number)
            owners.setdefault(number, []).append(slot)
            block = sector(number)
            used = block[127]
            file_id = block[125] >> 2
            next_sector = ((block[125] & 3) << 8) | block[126]
            valid_used = used <= 125
            chain.append({
                "sector": number, "atr_offset": 16 + (number - 1) * SECTOR_SIZE,
                "allocated_offset": len(raw_chunks) * SECTOR_SIZE,
                "payload_offset": payload_size if valid_used else None,
                "slack_offset": slack_size if valid_used else None,
                "used_bytes": used, "used_bytes_valid": valid_used,
                "slack_bytes": 125 - used if valid_used else None,
                "trailer_hex": block[125:].hex(), "file_id": file_id,
                "next_sector": next_sector,
            })
            raw_chunks.append(block)
            trailers.append(block[125:])
            if file_id != slot:
                issues.append({"code": "wrong_file_id", "sector": number, "file_id": file_id})
            if is_free(number):
                issues.append({"code": "chain_sector_marked_free", "sector": number})
            if not valid_used:
                issues.append({"code": "invalid_used_count", "sector": number, "used_bytes": used})
                break
            # Short nonfinal sectors are allowed; the trailer defines each boundary.
            payload.append(block[:used])
            slack.append(block[used:125])
            payload_size += used
            slack_size += 125 - used
            number = next_sector
            terminated = number == 0
        if len(chain) != declared_sectors:
            issues.append({"code": "sector_count_mismatch", "declared": declared_sectors,
                           "observed": len(chain)})
        prefix = f"files/{entry['id']}"
        paths = {"allocated": f"{prefix}/allocated.bin",
                 "observed_payload": f"{prefix}/observed-payload.bin",
                 "slack": f"{prefix}/slack.bin", "trailers": f"{prefix}/trailers.bin"}
        artifacts[paths["allocated"]] = b"".join(raw_chunks)
        artifacts[paths["observed_payload"]] = b"".join(payload)
        artifacts[paths["slack"]] = b"".join(slack)
        artifacts[paths["trailers"]] = b"".join(trailers)
        entry.update(chain=chain, chain_terminated=terminated,
                     observed_sectors=len(chain), observed_payload_bytes=payload_size,
                     observed_slack_bytes=slack_size, paths=paths)

    # Mark every claimant, not just whichever directory entry was visited last.
    for number, slots in owners.items():
        if len(slots) > 1:
            for slot in slots:
                entries[slot]["issues"].append({
                    "code": "cross_link", "sector": number,
                    "other_entries": [entries[other]["id"] for other in slots if other != slot],
                })
    for entry in entries:
        if not entry["active"]:
            entry["status"] = "not_extracted"
            continue
        entry["status"] = "issues" if entry["issues"] else "ok"
        if not entry["issues"]:
            path = f"files/{entry['id']}/payload.bin"
            entry["paths"]["payload"] = path
            artifacts[path] = artifacts[entry["paths"]["observed_payload"]]

    issues = []
    bitmap_free = sum(is_free(number) for number in range(720))
    if bitmap_free != current_free:
        issues.append({"code": "free_count_mismatch", "declared": current_free,
                       "observed": bitmap_free})
    reserved_free = sorted(number for number in RESERVED_SECTORS if is_free(number))
    if reserved_free:
        issues.append({"code": "reserved_sectors_marked_free", "sectors": reserved_free})
    unowned = [number for number in range(4, 720)
               if number not in RESERVED_SECTORS and number not in owners and not is_free(number)]
    if unowned:
        issues.append({"code": "allocated_unowned", "sectors": unowned})
        artifacts["evidence/allocated-unowned.bin"] = b"".join(sector(number) for number in unowned)
    manifest = {
        "format": "atari-dos2.0-128", "schema_version": 1,
        "header_hex": data[:16].hex(), "declared_payload_bytes": declared_bytes,
        "sector_size": SECTOR_SIZE, "physical_sectors": physical_sectors,
        "allocation_last_sector": LAST_ALLOCATED_SECTOR,
        "vtoc": {"code": vtoc[0], "initial_free": initial_free,
                 "current_free": current_free, "bitmap_free": bitmap_free},
        "outside_allocation_map": {
            "first_sector": 720, "sector_count": physical_sectors - 719,
            "path": "evidence/outside-allocation-map.bin",
            "nonzero_sectors": [number for number in range(720, physical_sectors + 1)
                                if any(sector(number))],
        },
        "allocated_unowned": unowned, "entries": entries, "issues": issues,
        "status": "issues" if issues or any(entry["issues"] for entry in entries) else "ok",
    }
    return manifest, artifacts


if __name__ == "__main__":
    from disk_image_output import run_cli

    raise SystemExit(run_cli(read_image, description="Extract raw 128-byte ATR DOS 2.0 files"))
