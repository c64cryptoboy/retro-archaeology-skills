#!/usr/bin/env python3
"""Scan raw binaries for a full 6502 instruction-shape signature.

The reference is decoded at an exact file offset. Targets are decoded from every
byte offset. A match preserves all reference instruction shapes and literal
immediates in order while permitting a bounded number of target-only inserted
instructions. This is a candidate-specific frequency aid, not a reuse claim:
it does not prove code boundaries, execution, or relational operand identity.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Sequence

from anchor_scan6502 import Instruction, decode_window, instruction_json, shape_tokens


def parse_int(value: str) -> int:
    return int(value, 0)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def is_subsequence(reference: Sequence[object], target: Sequence[object]) -> bool:
    position = 0
    for token in target:
        if position < len(reference) and token == reference[position]:
            position += 1
    return position == len(reference)


def find_matches(
    data: bytes,
    reference_shape: Sequence[object],
    *,
    maximum_insertions: int,
) -> list[dict[str, object]]:
    count = len(reference_shape)
    matches: list[dict[str, object]] = []
    for start in range(len(data)):
        for insertions in range(maximum_insertions + 1):
            instructions = decode_window(
                data, start, count + insertions, base_address=None
            )
            if instructions is None:
                continue
            target_shape = shape_tokens(instructions)
            # Anchor both ends so trailing/prefix instructions are not counted as
            # arbitrary insertions around an otherwise unrelated inner match.
            if target_shape[0] != reference_shape[0] or target_shape[-1] != reference_shape[-1]:
                continue
            if not is_subsequence(reference_shape, target_shape):
                continue
            matches.append(
                {
                    "startOffset": start,
                    "endOffsetExclusive": instructions[-1].offset + instructions[-1].length,
                    "insertedInstructions": insertions,
                    "instructions": [instruction_json(item) for item in instructions],
                }
            )
            break
    return matches


def build_report(
    reference_path: Path,
    reference_offset: int,
    instruction_count: int,
    target_paths: Sequence[Path],
    maximum_insertions: int,
) -> dict[str, object]:
    reference_data = reference_path.read_bytes()
    reference = decode_window(
        reference_data, reference_offset, instruction_count, base_address=None
    )
    if reference is None:
        raise ValueError("reference does not decode as the requested official-opcode window")
    reference_shape = shape_tokens(reference)
    targets = []
    for path in target_paths:
        data = path.read_bytes()
        matches = find_matches(
            data, reference_shape, maximum_insertions=maximum_insertions
        )
        targets.append(
            {
                "path": str(path),
                "size": len(data),
                "sha256": sha256(data),
                "matchCount": len(matches),
                "matches": matches,
            }
        )
    return {
        "format": "6502-candidate-shape-signature-scan",
        "version": 1,
        "method": {
            "allByteOffsets": True,
            "officialOpcodesOnly": True,
            "view": "portable-shape",
            "immediateOperandsRetained": True,
            "maximumTargetOnlyInsertedInstructions": maximum_insertions,
            "anchoredAtFirstAndLastReferenceShape": True,
            "caution": "Shape-subsequence hits are an upper-bound frequency aid, not confirmed code or reuse evidence.",
        },
        "reference": {
            "path": str(reference_path),
            "size": len(reference_data),
            "sha256": sha256(reference_data),
            "startOffset": reference_offset,
            "endOffsetExclusive": reference[-1].offset + reference[-1].length,
            "instructionCount": instruction_count,
            "instructions": [instruction_json(item) for item in reference],
            "shape": [token.text() for token in reference_shape],
        },
        "targets": targets,
        "aggregate": {
            "targetFiles": len(targets),
            "targetBytes": sum(item["size"] for item in targets),
            "matches": sum(item["matchCount"] for item in targets),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference", type=Path, help="raw reference binary")
    parser.add_argument("reference_offset", type=parse_int, help="reference file offset")
    parser.add_argument("instruction_count", type=int)
    parser.add_argument("targets", nargs="+", type=Path)
    parser.add_argument("--max-insertions", type=int, default=0)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.instruction_count < 1:
        parser.error("instruction_count must be positive")
    if args.max_insertions < 0:
        parser.error("--max-insertions cannot be negative")
    try:
        report = build_report(
            args.reference,
            args.reference_offset,
            args.instruction_count,
            args.targets,
            args.max_insertions,
        )
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    text = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
        print(f"wrote {args.output}")
    else:
        print(text, end="")
    print(
        f"targets={report['aggregate']['targetFiles']} "
        f"bytes={report['aggregate']['targetBytes']} "
        f"matches={report['aggregate']['matches']}",
        file=sys.stderr if not args.output else sys.stdout,
    )


if __name__ == "__main__":
    main()
