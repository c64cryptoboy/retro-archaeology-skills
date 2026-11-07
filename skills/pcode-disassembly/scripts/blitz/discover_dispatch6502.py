#!/usr/bin/env python3
"""Find candidate 6502 split low/high-byte indexed dispatch sequences in a PRG.

This is a structural heuristic, not a VM detector or semantic opcode recovery tool.
It recognizes the common sequence CMP #min; BCC; LDA lowTable,X; STA ptr;
LDA highTable,X; STA ptr+1; JMP (ptr).
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def load_prg(path: Path) -> tuple[int, bytes, str]:
    raw = path.read_bytes()
    if len(raw) < 3:
        raise ValueError("PRG too short")
    return int.from_bytes(raw[:2], "little"), raw[2:], hashlib.sha256(raw).hexdigest()


def u16(data: bytes, offset: int) -> int:
    return data[offset] | data[offset + 1] << 8


def discover(load: int, data: bytes) -> list[dict]:
    results = []
    # c9 nn / 90 rr / bd ll ll / 85 zp / bd hh hh / 85 zp+1 / 6c zp 00
    for offset in range(0, len(data) - 17 + 1):
        chunk = data[offset : offset + 17]
        if not (
            chunk[0] == 0xC9
            and chunk[2] == 0x90
            and chunk[4] == 0xBD
            and chunk[7] == 0x85
            and chunk[9] == 0xBD
            and chunk[12] == 0x85
            and chunk[14] == 0x6C
        ):
            continue
        pointer = chunk[8]
        if chunk[13] != (pointer + 1) & 0xFF or u16(chunk, 15) != pointer:
            continue
        address = load + offset
        relative = chunk[3] - 256 if chunk[3] & 0x80 else chunk[3]
        results.append(
            {
                "address": address,
                "minimumDirectOpcode": chunk[1],
                "belowMinimumTarget": (address + 4 + relative) & 0xFFFF,
                "lowTable": u16(chunk, 5),
                "highTable": u16(chunk, 10),
                "dispatchPointerZeroPage": pointer,
                "indirectJump": pointer,
                "bytes": chunk.hex(" "),
                "confidence": "structural-candidate",
                "limitations": "Does not establish table extent, instruction boundaries, VM state, or opcode semantics.",
            }
        )
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prg", type=Path)
    parser.add_argument("--json-output", type=Path)
    args = parser.parse_args()
    load, data, digest = load_prg(args.prg)
    result = {
        "schema": "6502-split-dispatch-candidates-v1",
        "image": {
            "path": str(args.prg),
            "loadAddress": load,
            "endExclusive": load + len(data),
            "sha256": digest,
        },
        "candidates": discover(load, data),
    }
    text = json.dumps(result, indent=2) + "\n"
    if args.json_output:
        args.json_output.write_text(text)
    else:
        print(text, end="")


if __name__ == "__main__":
    main()
