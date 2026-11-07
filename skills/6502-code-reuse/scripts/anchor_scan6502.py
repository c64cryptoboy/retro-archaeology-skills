#!/usr/bin/env python3
"""Find exact normalized 6502 instruction-window anchors in generic regions.

This is the Stage 2 exact-anchor scanner. It deliberately does not perform
local extension or make a reuse claim; those belong to later stages.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Sequence

from region_manifest import sha256, validate_manifest

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
from dis6502 import fmt as format_operand  # noqa: E402
from dis6502 import ops as COMMON_OFFICIAL_OPS  # noqa: E402

BRANCHES = {"BPL", "BMI", "BVC", "BVS", "BCC", "BCS", "BNE", "BEQ"}
TERMINATORS = {"BRK", "RTI", "RTS", "JMP"}
CONTROL_ABSOLUTE = {"JSR", "JMP"}
PORTABLE_MODES = {
    "zp": "mem",
    "abs": "mem",
    "zpx": "mem_x",
    "abx": "mem_x",
    "zpy": "mem_y",
    "aby": "mem_y",
}


class ScanError(ValueError):
    pass


@dataclass(frozen=True)
class Instruction:
    offset: int
    address: int | None
    opcode: int
    mnemonic: str
    mode: str
    operand: int | None
    raw: bytes

    @property
    def length(self) -> int:
        return len(self.raw)


@dataclass(frozen=True)
class Token:
    mnemonic: str
    mode: str
    operand: str | int | None

    def text(self) -> str:
        if self.operand is None:
            return f"{self.mnemonic}:{self.mode}"
        return f"{self.mnemonic}:{self.mode}:{self.operand}"


@dataclass(frozen=True)
class Window:
    start: int
    end: int
    instructions: tuple[Instruction, ...]
    literal: tuple[Token, ...]
    relational: tuple[Token, ...]
    shape: tuple[Token, ...]


@dataclass(frozen=True)
class Anchor:
    left: Window
    right: Window
    fingerprint: tuple[Token, ...]
    left_frequency: int
    right_frequency: int

    @property
    def delta(self) -> int:
        return self.right.start - self.left.start


@dataclass
class Cluster:
    delta: int
    left_start: int
    left_end: int
    right_start: int
    right_end: int
    anchors: list[Anchor]

    @property
    def span(self) -> int:
        return min(self.left_end - self.left_start, self.right_end - self.right_start)


def _operand(raw: bytes) -> int | None:
    if len(raw) == 2:
        return raw[1]
    if len(raw) == 3:
        return raw[1] | raw[2] << 8
    return None


def decode_window(
    data: bytes,
    start: int,
    count: int,
    *,
    base_address: int | None,
    known_mask: bytes | None = None,
) -> tuple[Instruction, ...] | None:
    offset = start
    instructions: list[Instruction] = []
    for index in range(count):
        if offset >= len(data):
            return None
        description = COMMON_OFFICIAL_OPS.get(data[offset])
        if description is None:
            return None
        mnemonic, mode, length = description
        end = offset + length
        if end > len(data):
            return None
        if known_mask is not None and any(value == 0 for value in known_mask[offset:end]):
            return None
        # A linear candidate cannot cross an unconditional return/transfer.
        if index < count - 1 and mnemonic in TERMINATORS:
            return None
        raw = data[offset:end]
        instructions.append(
            Instruction(
                offset=offset,
                address=(base_address + offset) & 0xFFFF
                if base_address is not None
                else None,
                opcode=raw[0],
                mnemonic=mnemonic,
                mode=mode,
                operand=_operand(raw),
                raw=raw,
            )
        )
        offset = end
    return tuple(instructions)


def literal_tokens(instructions: Sequence[Instruction]) -> tuple[Token, ...]:
    return tuple(Token(i.mnemonic, i.mode, i.operand) for i in instructions)


def _branch_relationship(
    instruction: Instruction, instruction_offsets: dict[int, int]
) -> str:
    assert instruction.operand is not None
    displacement = instruction.operand - 256 if instruction.operand >= 128 else instruction.operand
    target = instruction.offset + 2 + displacement
    if target in instruction_offsets:
        return f"I{instruction_offsets[target]}"
    return "back" if displacement < 0 else "forward"


def relational_tokens(instructions: Sequence[Instruction]) -> tuple[Token, ...]:
    memory_names: dict[tuple[str, int], str] = {}
    control_names: dict[int, str] = {}
    instruction_offsets = {instruction.offset: i for i, instruction in enumerate(instructions)}
    result: list[Token] = []

    for instruction in instructions:
        mode = PORTABLE_MODES.get(instruction.mode, instruction.mode)
        operand: str | int | None = None
        if instruction.mode == "imm":
            operand = instruction.operand
        elif instruction.mode == "rel":
            operand = _branch_relationship(instruction, instruction_offsets)
        elif instruction.mnemonic in CONTROL_ABSOLUTE and instruction.mode == "abs":
            assert instruction.operand is not None
            operand = control_names.setdefault(
                instruction.operand, f"C{len(control_names)}"
            )
        elif instruction.operand is not None:
            key = (mode, instruction.operand)
            operand = memory_names.setdefault(key, f"M{len(memory_names)}")
        result.append(Token(instruction.mnemonic, mode, operand))
    return tuple(result)


def shape_tokens(instructions: Sequence[Instruction]) -> tuple[Token, ...]:
    result: list[Token] = []
    for instruction in instructions:
        mode = PORTABLE_MODES.get(instruction.mode, instruction.mode)
        operand: str | int | None = None
        if instruction.mode == "imm":
            operand = instruction.operand
        elif instruction.mode == "rel":
            assert instruction.operand is not None
            displacement = instruction.operand - 256 if instruction.operand >= 128 else instruction.operand
            operand = "back" if displacement < 0 else "forward"
        result.append(Token(instruction.mnemonic, mode, operand))
    return tuple(result)


def qualifying(window: Window, min_unique_mnemonics: int) -> bool:
    mnemonics = [instruction.mnemonic for instruction in window.instructions]
    if "BRK" in mnemonics:
        return False
    return len(set(mnemonics)) >= min_unique_mnemonics


def scan_region(
    data: bytes,
    count: int,
    *,
    base_address: int | None,
    known_mask: bytes | None,
    min_unique_mnemonics: int,
) -> tuple[list[Window], dict[str, int]]:
    windows: list[Window] = []
    decoded = 0
    for start in range(len(data)):
        instructions = decode_window(
            data,
            start,
            count,
            base_address=base_address,
            known_mask=known_mask,
        )
        if instructions is None:
            continue
        decoded += 1
        window = Window(
            start=start,
            end=instructions[-1].offset + instructions[-1].length,
            instructions=instructions,
            literal=literal_tokens(instructions),
            relational=relational_tokens(instructions),
            shape=shape_tokens(instructions),
        )
        if qualifying(window, min_unique_mnemonics):
            windows.append(window)
    return windows, {"decodedWindows": decoded, "qualifyingWindows": len(windows)}


def index_view(windows: Sequence[Window], view: str) -> dict[tuple[Token, ...], list[Window]]:
    result: dict[tuple[Token, ...], list[Window]] = defaultdict(list)
    for window in windows:
        result[getattr(window, view)].append(window)
    return dict(result)


def view_summary(
    left_index: dict[tuple[Token, ...], list[Window]],
    right_index: dict[tuple[Token, ...], list[Window]],
    *,
    max_occurrences: int,
    max_pairs: int,
) -> dict[str, int]:
    common = left_index.keys() & right_index.keys()
    accepted = []
    skipped = []
    for fingerprint in common:
        left_count = len(left_index[fingerprint])
        right_count = len(right_index[fingerprint])
        if (
            left_count > max_occurrences
            or right_count > max_occurrences
            or left_count * right_count > max_pairs
        ):
            skipped.append(fingerprint)
        else:
            accepted.append(fingerprint)
    return {
        "leftUniqueFingerprints": len(left_index),
        "rightUniqueFingerprints": len(right_index),
        "commonFingerprints": len(common),
        "acceptedFingerprints": len(accepted),
        "skippedRepetitiveFingerprints": len(skipped),
        "acceptedAnchorPairs": sum(
            len(left_index[fingerprint]) * len(right_index[fingerprint])
            for fingerprint in accepted
        ),
    }


def relational_anchors(
    left_index: dict[tuple[Token, ...], list[Window]],
    right_index: dict[tuple[Token, ...], list[Window]],
    *,
    max_occurrences: int,
    max_pairs: int,
) -> list[Anchor]:
    anchors: list[Anchor] = []
    for fingerprint in left_index.keys() & right_index.keys():
        left_windows = left_index[fingerprint]
        right_windows = right_index[fingerprint]
        if (
            len(left_windows) > max_occurrences
            or len(right_windows) > max_occurrences
            or len(left_windows) * len(right_windows) > max_pairs
        ):
            continue
        for left in left_windows:
            for right in right_windows:
                anchors.append(
                    Anchor(
                        left,
                        right,
                        fingerprint,
                        len(left_windows),
                        len(right_windows),
                    )
                )
    return anchors


def cluster_anchors(anchors: Sequence[Anchor]) -> list[Cluster]:
    """Collapse overlapping anchors along one exact byte-offset diagonal."""
    by_delta: dict[int, list[Anchor]] = defaultdict(list)
    for anchor in anchors:
        by_delta[anchor.delta].append(anchor)

    clusters: list[Cluster] = []
    for delta, diagonal in by_delta.items():
        diagonal.sort(key=lambda anchor: (anchor.left.start, anchor.right.start))
        current: Cluster | None = None
        for anchor in diagonal:
            if (
                current is not None
                and anchor.left.start <= current.left_end
                and anchor.right.start <= current.right_end
            ):
                current.left_end = max(current.left_end, anchor.left.end)
                current.right_end = max(current.right_end, anchor.right.end)
                current.anchors.append(anchor)
            else:
                if current is not None:
                    clusters.append(current)
                current = Cluster(
                    delta=delta,
                    left_start=anchor.left.start,
                    left_end=anchor.left.end,
                    right_start=anchor.right.start,
                    right_end=anchor.right.end,
                    anchors=[anchor],
                )
        if current is not None:
            clusters.append(current)

    return sorted(
        clusters,
        key=lambda cluster: (-cluster.span, -len(cluster.anchors), cluster.left_start, cluster.right_start),
    )


def fingerprint_digest(tokens: Sequence[Token]) -> str:
    encoded = "\n".join(token.text() for token in tokens).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]


def instruction_json(instruction: Instruction) -> dict[str, Any]:
    pc = instruction.address if instruction.address is not None else instruction.offset
    return {
        "offset": instruction.offset,
        "address": instruction.address,
        "bytes": instruction.raw.hex(),
        "mnemonic": instruction.mnemonic,
        "mode": instruction.mode,
        "operand": instruction.operand,
        "text": f"{instruction.mnemonic} {format_operand(instruction.mode, instruction.raw, pc)}".rstrip(),
    }


def window_json(window: Window) -> dict[str, Any]:
    return {
        "startOffset": window.start,
        "endOffsetExclusive": window.end,
        "instructions": [instruction_json(i) for i in window.instructions],
        "views": {
            "literal": [token.text() for token in window.literal],
            "relational": [token.text() for token in window.relational],
            "shape": [token.text() for token in window.shape],
        },
    }


def cluster_json(cluster: Cluster) -> dict[str, Any]:
    example = min(
        cluster.anchors,
        key=lambda anchor: (
            anchor.left_frequency * anchor.right_frequency,
            anchor.left.start,
            anchor.right.start,
        ),
    )
    return {
        "delta": cluster.delta,
        "leftStart": cluster.left_start,
        "leftEndExclusive": cluster.left_end,
        "rightStart": cluster.right_start,
        "rightEndExclusive": cluster.right_end,
        "minimumByteSpan": cluster.span,
        "overlappingAnchorCount": len(cluster.anchors),
        "example": {
            "fingerprint": fingerprint_digest(example.fingerprint),
            "leftFrequency": example.left_frequency,
            "rightFrequency": example.right_frequency,
            "left": window_json(example.left),
            "right": window_json(example.right),
        },
    }


def load_regions(manifest_path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    manifest = json.loads(manifest_path.read_text())
    validate_manifest(manifest, manifest_path.parent)
    loaded = []
    for region in manifest["regions"]:
        if not region["scanByDefault"]:
            continue
        data = (manifest_path.parent / region["path"]).read_bytes()
        mask = None
        if "knownMask" in region:
            mask = (manifest_path.parent / region["knownMask"]["path"]).read_bytes()
        loaded.append({"metadata": region, "data": data, "knownMask": mask})
    return manifest, loaded


def scan_manifests(
    left_manifest_path: Path,
    right_manifest_path: Path,
    *,
    window_sizes: Sequence[int],
    min_unique_mnemonics: int,
    max_occurrences: int,
    max_pairs: int,
    max_reported_clusters: int,
) -> dict[str, Any]:
    left_manifest, left_regions = load_regions(left_manifest_path)
    right_manifest, right_regions = load_regions(right_manifest_path)
    if not left_regions or not right_regions:
        raise ScanError("both manifests need at least one scanByDefault region")

    cache: dict[tuple[str, int, str], tuple[list[Window], dict[str, int]]] = {}

    def cached(side: str, region: dict[str, Any], count: int):
        region_id = region["metadata"]["id"]
        key = (side, count, region_id)
        if key not in cache:
            cache[key] = scan_region(
                region["data"],
                count,
                base_address=region["metadata"].get("baseAddress"),
                known_mask=region["knownMask"],
                min_unique_mnemonics=min_unique_mnemonics,
            )
        return cache[key]

    comparisons = []
    for left_region in left_regions:
        for right_region in right_regions:
            per_size = []
            for count in window_sizes:
                left_windows, left_stats = cached("left", left_region, count)
                right_windows, right_stats = cached("right", right_region, count)
                indexes = {}
                summaries = {}
                for view in ("literal", "relational", "shape"):
                    left_index = index_view(left_windows, view)
                    right_index = index_view(right_windows, view)
                    indexes[view] = (left_index, right_index)
                    summaries[view] = view_summary(
                        left_index,
                        right_index,
                        max_occurrences=max_occurrences,
                        max_pairs=max_pairs,
                    )
                anchors = relational_anchors(
                    *indexes["relational"],
                    max_occurrences=max_occurrences,
                    max_pairs=max_pairs,
                )
                clusters = cluster_anchors(anchors)
                per_size.append(
                    {
                        "instructionCount": count,
                        "leftScan": left_stats,
                        "rightScan": right_stats,
                        "views": summaries,
                        "relationalClusters": {
                            "count": len(clusters),
                            "reported": min(len(clusters), max_reported_clusters),
                            "items": [
                                cluster_json(cluster)
                                for cluster in clusters[:max_reported_clusters]
                            ],
                        },
                    }
                )
            comparisons.append(
                {
                    "leftRegion": left_region["metadata"]["id"],
                    "rightRegion": right_region["metadata"]["id"],
                    "windowSizes": per_size,
                }
            )

    return {
        "format": "6502-exact-anchor-report",
        "version": 1,
        "decoderProfile": "shared official NMOS 6502 subset",
        "left": {
            "manifest": str(left_manifest_path),
            "manifestSha256": sha256(left_manifest_path.read_bytes()),
            "artifact": left_manifest["artifact"],
        },
        "right": {
            "manifest": str(right_manifest_path),
            "manifestSha256": sha256(right_manifest_path.read_bytes()),
            "artifact": right_manifest["artifact"],
        },
        "configuration": {
            "windowSizes": list(window_sizes),
            "minUniqueMnemonics": min_unique_mnemonics,
            "maxOccurrencesPerRegion": max_occurrences,
            "maxPairsPerFingerprint": max_pairs,
            "maxReportedClustersPerSize": max_reported_clusters,
            "immediateOperandsRetained": True,
            "earlyTerminatorsRejected": sorted(TERMINATORS),
            "allOffsetStartsAreCandidateBoundaries": True,
        },
        "comparisons": comparisons,
    }


def parse_window_sizes(value: str) -> list[int]:
    try:
        result = sorted({int(item) for item in value.split(",")})
    except ValueError as exc:
        raise argparse.ArgumentTypeError("window sizes must be comma-separated integers") from exc
    if not result or result[0] < 2:
        raise argparse.ArgumentTypeError("window sizes must all be >= 2")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("left_manifest", type=Path)
    parser.add_argument("right_manifest", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--window-sizes", type=parse_window_sizes, default=[5, 6, 8])
    parser.add_argument("--min-unique-mnemonics", type=int, default=4)
    parser.add_argument("--max-occurrences", type=int, default=64)
    parser.add_argument("--max-pairs", type=int, default=4096)
    parser.add_argument("--max-reported-clusters", type=int, default=500)
    args = parser.parse_args()

    report = scan_manifests(
        args.left_manifest,
        args.right_manifest,
        window_sizes=args.window_sizes,
        min_unique_mnemonics=args.min_unique_mnemonics,
        max_occurrences=args.max_occurrences,
        max_pairs=args.max_pairs,
        max_reported_clusters=args.max_reported_clusters,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(f"wrote {args.output}")
    for comparison in report["comparisons"]:
        print(f"{comparison['leftRegion']} vs {comparison['rightRegion']}")
        for result in comparison["windowSizes"]:
            relational = result["views"]["relational"]
            print(
                f"  k={result['instructionCount']}: "
                f"anchors={relational['acceptedAnchorPairs']}, "
                f"clusters={result['relationalClusters']['count']}"
            )


if __name__ == "__main__":
    main()
