"""Describe the stored speed zones for one slot of a version-0 G64 image."""
import argparse
import json
from pathlib import Path
from struct import unpack_from


def describe_slot(data: bytes, slot: int) -> dict:
    """Return track-relative, half-open byte runs; raise ValueError on refusal."""
    if len(data) < 12 or data[:9] != b"GCR-1541\x00":
        raise ValueError("expected a version-0 GCR-1541 header")
    count = data[9]
    table_end = 12 + 8 * count
    if not 1 <= count <= 84 or table_end > len(data):
        raise ValueError("invalid G64 slot tables")
    if not 0 <= slot < count:
        raise ValueError(f"slot outside image: {slot}")
    track = unpack_from("<I", data, 12 + 4 * slot)[0]
    entry = unpack_from("<I", data, 12 + 4 * (count + slot))[0]
    if not track:
        raise ValueError(f"slot {slot} has no stored track")
    if track < table_end or track + 2 > len(data):
        raise ValueError("invalid track offset")
    size = unpack_from("<H", data, track)[0]
    maximum = unpack_from("<H", data, 10)[0]
    track_end = track + 2 + size
    if not 1 <= size <= maximum or track_end > len(data):
        raise ValueError("invalid track length")

    if entry <= 3:
        kind = "constant"
        runs = [[0, size, entry]]
    else:
        kind = "packed"
        needed = (size + 3) // 4
        if entry < table_end or (entry < track_end and track < entry + needed):
            raise ValueError("speed map overlaps tables or selected track")
        if entry + needed > len(data):
            raise ValueError(f"truncated speed map at {entry}: need {needed} bytes, "
                             f"have {max(0, len(data) - entry)}")
        runs = []
        for i in range(size):
            zone = (data[entry + i // 4] >> (6 - 2 * (i % 4))) & 3
            if runs and runs[-1][2] == zone:
                runs[-1][1] = i + 1
            else:
                runs.append([i, i + 1, zone])
    return {"slot": slot, "track": 1 + slot / 2, "track_bytes": size,
            "track_length_offset": track, "speed_entry": entry,
            "kind": kind, "runs": runs}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("--slot", required=True, type=int,
                        help="zero-based slot (0 = track 1, 1 = 1.5, 70 = 36)")
    args = parser.parse_args()
    try:
        report = describe_slot(args.image.read_bytes(), args.slot)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"refused: {exc}\n")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
