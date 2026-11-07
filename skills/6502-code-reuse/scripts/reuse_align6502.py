#!/usr/bin/env python3
"""Extend, deduplicate, and chain exact 6502 reuse anchors.

Consumes generic byte-region manifests. Exact relational windows seed bounded
local alignments; reported starts remain evidence-backed candidates rather than
asserted function boundaries.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Sequence

import anchor_scan6502 as anchor

PROBABLE_MIN_PAIRED = 16
PROBABLE_MIN_SUPPORT_FRACTION = 0.80
PROBABLE_MIN_RELATIONAL_EXACT = 8
PROBABLE_MAX_SEED_PRODUCT_FREQUENCY = 16
CANDIDATE_MIN_PAIRED = 8
CANDIDATE_MIN_SUPPORT_FRACTION = 0.70


@dataclass(frozen=True)
class AlignmentColumn:
    left_index: int | None
    right_index: int | None
    relation: str
    score: int


@dataclass(frozen=True)
class LocalAlignment:
    score: int
    columns: tuple[AlignmentColumn, ...]


@dataclass
class ExtendedMatch:
    seed_cluster: anchor.Cluster
    seed_anchor: anchor.Anchor
    left_stream: tuple[anchor.Instruction, ...]
    right_stream: tuple[anchor.Instruction, ...]
    left_tokens: tuple[anchor.Token, ...]
    right_tokens: tuple[anchor.Token, ...]
    left_shapes: tuple[anchor.Token, ...]
    right_shapes: tuple[anchor.Token, ...]
    alignment: LocalAlignment
    left_shift: int
    right_shift: int
    metrics: dict[str, Any]
    classification: str

    @property
    def left_start(self) -> int:
        indices = [column.left_index for column in self.alignment.columns if column.left_index is not None]
        return self.left_stream[min(indices)].offset

    @property
    def left_end(self) -> int:
        indices = [column.left_index for column in self.alignment.columns if column.left_index is not None]
        instruction = self.left_stream[max(indices)]
        return instruction.offset + instruction.length

    @property
    def right_start(self) -> int:
        indices = [column.right_index for column in self.alignment.columns if column.right_index is not None]
        return self.right_stream[min(indices)].offset

    @property
    def right_end(self) -> int:
        indices = [column.right_index for column in self.alignment.columns if column.right_index is not None]
        instruction = self.right_stream[max(indices)]
        return instruction.offset + instruction.length


def pair_relation(
    left_relational: anchor.Token,
    right_relational: anchor.Token,
    left_shape: anchor.Token,
    right_shape: anchor.Token,
) -> tuple[str, int]:
    if left_relational == right_relational:
        return "relational-exact", 5
    if left_shape == right_shape:
        return "shape-exact", 3
    if (
        left_shape.mnemonic == right_shape.mnemonic
        and left_shape.mode == right_shape.mode
    ):
        return "compatible-changed-operand", 1
    return "different", -4


def affine_local_align(
    left_relational: Sequence[anchor.Token],
    right_relational: Sequence[anchor.Token],
    left_shape: Sequence[anchor.Token],
    right_shape: Sequence[anchor.Token],
    *,
    gap_open: int = -5,
    gap_extend: int = -1,
) -> LocalAlignment:
    """Smith-Waterman with affine gaps and an inspectable traceback."""
    n, m = len(left_relational), len(right_relational)
    match = [[0] * (m + 1) for _ in range(n + 1)]
    gap_right = [[0] * (m + 1) for _ in range(n + 1)]
    gap_left = [[0] * (m + 1) for _ in range(n + 1)]
    trace_match: list[list[tuple[str, int, int] | None]] = [[None] * (m + 1) for _ in range(n + 1)]
    trace_gap_right: list[list[tuple[str, int, int] | None]] = [[None] * (m + 1) for _ in range(n + 1)]
    trace_gap_left: list[list[tuple[str, int, int] | None]] = [[None] * (m + 1) for _ in range(n + 1)]
    best = (0, "M", 0, 0)

    def update_best(value: int, state: str, i: int, j: int) -> None:
        nonlocal best
        if value > best[0]:
            best = (value, state, i, j)

    for i in range(1, n + 1):
        for j in range(1, m + 1):
            _, relation_score = pair_relation(
                left_relational[i - 1],
                right_relational[j - 1],
                left_shape[i - 1],
                right_shape[j - 1],
            )
            previous = max(
                (
                    (match[i - 1][j - 1], "M"),
                    (gap_right[i - 1][j - 1], "R"),
                    (gap_left[i - 1][j - 1], "L"),
                    (0, "0"),
                ),
                key=lambda item: item[0],
            )
            match[i][j] = previous[0] + relation_score if previous[0] or relation_score > 0 else 0
            if match[i][j] > 0:
                trace_match[i][j] = (previous[1], i - 1, j - 1)

            previous_right = max(
                (
                    (match[i - 1][j] + gap_open, "M"),
                    (gap_right[i - 1][j] + gap_extend, "R"),
                    (gap_left[i - 1][j] + gap_open, "L"),
                    (0, "0"),
                ),
                key=lambda item: item[0],
            )
            gap_right[i][j] = max(0, previous_right[0])
            if gap_right[i][j] > 0:
                trace_gap_right[i][j] = (previous_right[1], i - 1, j)

            previous_left = max(
                (
                    (match[i][j - 1] + gap_open, "M"),
                    (gap_left[i][j - 1] + gap_extend, "L"),
                    (gap_right[i][j - 1] + gap_open, "R"),
                    (0, "0"),
                ),
                key=lambda item: item[0],
            )
            gap_left[i][j] = max(0, previous_left[0])
            if gap_left[i][j] > 0:
                trace_gap_left[i][j] = (previous_left[1], i, j - 1)

            update_best(match[i][j], "M", i, j)
            update_best(gap_right[i][j], "R", i, j)
            update_best(gap_left[i][j], "L", i, j)

    score, state, i, j = best
    columns: list[AlignmentColumn] = []
    while state != "0":
        if state == "M":
            if match[i][j] <= 0 or i == 0 or j == 0:
                break
            relation, relation_score = pair_relation(
                left_relational[i - 1],
                right_relational[j - 1],
                left_shape[i - 1],
                right_shape[j - 1],
            )
            columns.append(AlignmentColumn(i - 1, j - 1, relation, relation_score))
            trace = trace_match[i][j]
        elif state == "R":
            if gap_right[i][j] <= 0 or i == 0:
                break
            trace = trace_gap_right[i][j]
            contribution = gap_extend if trace is not None and trace[0] == "R" else gap_open
            columns.append(AlignmentColumn(i - 1, None, "gap-right", contribution))
        else:
            if gap_left[i][j] <= 0 or j == 0:
                break
            trace = trace_gap_left[i][j]
            contribution = gap_extend if trace is not None and trace[0] == "L" else gap_open
            columns.append(AlignmentColumn(None, j - 1, "gap-left", contribution))
        if trace is None:
            break
        state, i, j = trace
    columns.reverse()
    return LocalAlignment(score, tuple(columns))


def decode_stream(
    data: bytes,
    start: int,
    *,
    base_address: int | None,
    known_mask: bytes | None,
    max_instructions: int,
    max_bytes: int,
) -> tuple[anchor.Instruction, ...]:
    result: list[anchor.Instruction] = []
    offset = start
    while len(result) < max_instructions and offset - start < max_bytes:
        decoded = anchor.decode_window(
            data,
            offset,
            1,
            base_address=base_address,
            known_mask=known_mask,
        )
        if decoded is None:
            break
        instruction = decoded[0]
        result.append(instruction)
        offset += instruction.length
        if instruction.mnemonic in anchor.TERMINATORS:
            break
    return tuple(result)


def stream_candidates(
    data: bytes,
    seed_start: int,
    *,
    base_address: int | None,
    known_mask: bytes | None,
    max_instructions: int,
    max_bytes: int,
) -> list[tuple[int, tuple[anchor.Instruction, ...]]]:
    candidates = []
    for shift in (0, 1, 2):
        start = seed_start - shift
        if start < 0:
            continue
        stream = decode_stream(
            data,
            start,
            base_address=base_address,
            known_mask=known_mask,
            max_instructions=max_instructions,
            max_bytes=max_bytes,
        )
        if not stream:
            continue
        first = stream[0]
        if not (first.offset <= seed_start < first.offset + first.length):
            continue
        candidates.append((shift, stream))
    return candidates


def alignment_metrics(alignment: LocalAlignment) -> dict[str, Any]:
    counts = {
        "relationalExact": 0,
        "shapeExact": 0,
        "compatibleChangedOperand": 0,
        "different": 0,
        "gaps": 0,
    }
    longest_supporting_run = 0
    current_run = 0
    for column in alignment.columns:
        if column.relation == "relational-exact":
            counts["relationalExact"] += 1
            current_run += 1
        elif column.relation == "shape-exact":
            counts["shapeExact"] += 1
            current_run += 1
        elif column.relation == "compatible-changed-operand":
            counts["compatibleChangedOperand"] += 1
            current_run += 1
        elif column.relation == "different":
            counts["different"] += 1
            current_run = 0
        else:
            counts["gaps"] += 1
            current_run = 0
        longest_supporting_run = max(longest_supporting_run, current_run)
    paired = (
        counts["relationalExact"]
        + counts["shapeExact"]
        + counts["compatibleChangedOperand"]
        + counts["different"]
    )
    supporting = (
        counts["relationalExact"]
        + counts["shapeExact"]
        + counts["compatibleChangedOperand"]
    )
    counts.update(
        {
            "score": alignment.score,
            "columns": len(alignment.columns),
            "pairedInstructions": paired,
            "supportingPairs": supporting,
            "supportFraction": supporting / paired if paired else 0.0,
            "longestSupportingRun": longest_supporting_run,
        }
    )
    return counts


def classify(
    metrics: dict[str, Any],
    seed_product_frequency: int,
    *,
    probable_min_paired: int = PROBABLE_MIN_PAIRED,
) -> str:
    paired = metrics["pairedInstructions"]
    support = metrics["supportFraction"]
    if (
        paired >= probable_min_paired
        and support >= PROBABLE_MIN_SUPPORT_FRACTION
        and metrics["relationalExact"] >= PROBABLE_MIN_RELATIONAL_EXACT
        and seed_product_frequency <= PROBABLE_MAX_SEED_PRODUCT_FREQUENCY
    ):
        return "probable-shared-routine"
    if paired >= CANDIDATE_MIN_PAIRED and support >= CANDIDATE_MIN_SUPPORT_FRACTION:
        return "candidate-similarity"
    return "weak-or-generic"


def choose_seed(cluster: anchor.Cluster) -> anchor.Anchor:
    return min(
        cluster.anchors,
        key=lambda item: (
            item.left_frequency * item.right_frequency,
            item.left.start,
            item.right.start,
        ),
    )


def extend_cluster(
    cluster: anchor.Cluster,
    left_region: dict[str, Any],
    right_region: dict[str, Any],
    *,
    max_instructions: int,
    max_bytes: int,
    probable_min_paired: int = PROBABLE_MIN_PAIRED,
) -> ExtendedMatch | None:
    seed = choose_seed(cluster)
    left_candidates = stream_candidates(
        left_region["data"],
        seed.left.start,
        base_address=left_region["metadata"].get("baseAddress"),
        known_mask=left_region["knownMask"],
        max_instructions=max_instructions,
        max_bytes=max_bytes,
    )
    right_candidates = stream_candidates(
        right_region["data"],
        seed.right.start,
        base_address=right_region["metadata"].get("baseAddress"),
        known_mask=right_region["knownMask"],
        max_instructions=max_instructions,
        max_bytes=max_bytes,
    )
    best = None
    for left_shift, left_stream in left_candidates:
        left_relational = anchor.relational_tokens(left_stream)
        left_shapes = anchor.shape_tokens(left_stream)
        for right_shift, right_stream in right_candidates:
            right_relational = anchor.relational_tokens(right_stream)
            right_shapes = anchor.shape_tokens(right_stream)
            alignment = affine_local_align(
                left_relational,
                right_relational,
                left_shapes,
                right_shapes,
            )
            metrics = alignment_metrics(alignment)
            rank = (
                alignment.score,
                metrics["supportingPairs"],
                metrics["relationalExact"],
                -left_shift - right_shift,
            )
            if best is None or rank > best[0]:
                best = (
                    rank,
                    left_shift,
                    right_shift,
                    left_stream,
                    right_stream,
                    left_relational,
                    right_relational,
                    left_shapes,
                    right_shapes,
                    alignment,
                    metrics,
                )
    if best is None or not best[9].columns:
        return None
    (
        _, left_shift, right_shift, left_stream, right_stream,
        left_relational, right_relational, left_shapes, right_shapes,
        alignment, metrics,
    ) = best
    frequency = seed.left_frequency * seed.right_frequency
    return ExtendedMatch(
        cluster,
        seed,
        left_stream,
        right_stream,
        left_relational,
        right_relational,
        left_shapes,
        right_shapes,
        alignment,
        left_shift,
        right_shift,
        metrics,
        classify(metrics, frequency, probable_min_paired=probable_min_paired),
    )


def overlap_fraction(a_start: int, a_end: int, b_start: int, b_end: int) -> float:
    overlap = max(0, min(a_end, b_end) - max(a_start, b_start))
    denominator = min(a_end - a_start, b_end - b_start)
    return overlap / denominator if denominator else 0.0


def deduplicate(matches: Sequence[ExtendedMatch], threshold: float = 0.5) -> list[ExtendedMatch]:
    selected: list[ExtendedMatch] = []
    ranked = sorted(
        matches,
        key=lambda item: (
            -item.alignment.score,
            -item.metrics["supportingPairs"],
            item.left_start,
            item.right_start,
        ),
    )
    for candidate in ranked:
        duplicate = False
        for existing in selected:
            if (
                overlap_fraction(candidate.left_start, candidate.left_end, existing.left_start, existing.left_end) >= threshold
                and overlap_fraction(candidate.right_start, candidate.right_end, existing.right_start, existing.right_end) >= threshold
            ):
                duplicate = True
                break
        if not duplicate:
            selected.append(candidate)
    return selected


def build_chains(matches: Sequence[ExtendedMatch], max_gap: int = 512) -> list[list[ExtendedMatch]]:
    chains: list[list[ExtendedMatch]] = []
    for match in sorted(matches, key=lambda item: (item.left_start, item.right_start)):
        eligible = []
        for chain in chains:
            previous = chain[-1]
            left_gap = match.left_start - previous.left_end
            right_gap = match.right_start - previous.right_end
            if 0 <= left_gap <= max_gap and 0 <= right_gap <= max_gap:
                eligible.append((left_gap + right_gap, chain))
        if eligible:
            min(eligible, key=lambda item: item[0])[1].append(match)
        else:
            chains.append([match])
    return sorted(chains, key=lambda chain: (-sum(item.alignment.score for item in chain), chain[0].left_start))


def instruction_or_none(stream: Sequence[anchor.Instruction], index: int | None) -> dict[str, Any] | None:
    return anchor.instruction_json(stream[index]) if index is not None else None


def match_json(match: ExtendedMatch, match_id: str) -> dict[str, Any]:
    return {
        "id": match_id,
        "classification": match.classification,
        "score": match.alignment.score,
        "leftStart": match.left_start,
        "leftEndExclusive": match.left_end,
        "rightStart": match.right_start,
        "rightEndExclusive": match.right_end,
        "boundaryCorrection": {
            "leftBytesBeforeSeed": match.left_shift,
            "rightBytesBeforeSeed": match.right_shift,
            "applied": bool(match.left_shift or match.right_shift),
        },
        "seed": {
            "leftStart": match.seed_anchor.left.start,
            "rightStart": match.seed_anchor.right.start,
            "instructionCount": len(match.seed_anchor.fingerprint),
            "fingerprint": anchor.fingerprint_digest(match.seed_anchor.fingerprint),
            "leftFrequency": match.seed_anchor.left_frequency,
            "rightFrequency": match.seed_anchor.right_frequency,
            "clusterSpan": match.seed_cluster.span,
            "clusterAnchorCount": len(match.seed_cluster.anchors),
        },
        "metrics": match.metrics,
        "columns": [
            {
                "relation": column.relation,
                "score": column.score,
                "left": instruction_or_none(match.left_stream, column.left_index),
                "right": instruction_or_none(match.right_stream, column.right_index),
            }
            for column in match.alignment.columns
        ],
    }


def interval_union_size(intervals: Sequence[tuple[int, int]]) -> int:
    if not intervals:
        return 0
    result = 0
    start, end = sorted(intervals)[0]
    for next_start, next_end in sorted(intervals)[1:]:
        if next_start <= end:
            end = max(end, next_end)
        else:
            result += end - start
            start, end = next_start, next_end
    return result + end - start


def _display_instruction(value: dict[str, Any] | None) -> str:
    if value is None:
        return "—"
    location = value["address"] if value["address"] is not None else value["offset"]
    return f"${location:04X} {value['bytes']:<6} {value['text']}"


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# 6502 reuse alignment evidence",
        "",
        f"Decoder: `{report['decoderProfile']}`",
        "",
        "> All offsets and inferred boundaries are candidates. This report demonstrates similarity, not copying direction or legal provenance.",
        "",
    ]
    for comparison in report["comparisons"]:
        aggregate = comparison["aggregate"]
        lines.extend(
            [
                f"## `{comparison['leftRegion']}` vs `{comparison['rightRegion']}`",
                "",
                f"- Exact relational anchors: **{comparison['exactAnchors']:,}**",
                f"- Exact overlap clusters: **{comparison['exactClusters']:,}**",
                f"- Deduplicated extensions: **{aggregate['deduplicatedMatches']:,}**",
                f"- Probable shared routines: **{aggregate['probableSharedRoutines']:,}**",
                f"- Unique covered bytes: left **{aggregate['uniqueLeftBytes']:,}**, right **{aggregate['uniqueRightBytes']:,}**",
                f"- Chains: **{len(comparison['chains']):,}**",
                "",
                "| ID | Class | Score | Paired | Relational | Shape | Changed | Gaps | Left | Right | Boundary correction |",
                "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
            ]
        )
        for match in comparison["matches"]:
            metrics = match["metrics"]
            correction = match["boundaryCorrection"]
            lines.append(
                f"| {match['id']} | {match['classification']} | {match['score']} | "
                f"{metrics['pairedInstructions']} | {metrics['relationalExact']} | "
                f"{metrics['shapeExact']} | {metrics['compatibleChangedOperand']} | "
                f"{metrics['gaps']} | `${match['leftStart']:04X}-${match['leftEndExclusive']:04X}` | "
                f"`${match['rightStart']:04X}-${match['rightEndExclusive']:04X}` | "
                f"-{correction['leftBytesBeforeSeed']}/-{correction['rightBytesBeforeSeed']} bytes |"
            )
        lines.append("")
        lines.append("### Top alignment details")
        lines.append("")
        for match in comparison["matches"][:10]:
            lines.extend(
                [
                    f"#### {match['id']} — {match['classification']}",
                    "",
                    "```text",
                ]
            )
            for column in match["columns"]:
                left = column["left"]
                right = column["right"]
                left_text = _display_instruction(left)
                right_text = _display_instruction(right)
                lines.append(f"{left_text:<34} | {right_text:<34} | {column['relation']}")
            lines.extend(["```", ""])
    return "\n".join(lines) + "\n"


def analyze_manifests(
    left_manifest_path: Path,
    right_manifest_path: Path,
    *,
    seed_instruction_count: int = 8,
    min_unique_mnemonics: int = 4,
    max_occurrences: int = 64,
    max_pairs: int = 4096,
    max_seed_clusters: int = 500,
    max_instructions: int = 256,
    max_bytes: int = 512,
    max_reported_matches: int = 100,
    probable_min_paired: int = PROBABLE_MIN_PAIRED,
) -> dict[str, Any]:
    left_manifest, left_regions = anchor.load_regions(left_manifest_path)
    right_manifest, right_regions = anchor.load_regions(right_manifest_path)
    comparisons = []
    for left_region in left_regions:
        for right_region in right_regions:
            left_windows, left_scan = anchor.scan_region(
                left_region["data"],
                seed_instruction_count,
                base_address=left_region["metadata"].get("baseAddress"),
                known_mask=left_region["knownMask"],
                min_unique_mnemonics=min_unique_mnemonics,
            )
            right_windows, right_scan = anchor.scan_region(
                right_region["data"],
                seed_instruction_count,
                base_address=right_region["metadata"].get("baseAddress"),
                known_mask=right_region["knownMask"],
                min_unique_mnemonics=min_unique_mnemonics,
            )
            left_index = anchor.index_view(left_windows, "relational")
            right_index = anchor.index_view(right_windows, "relational")
            exact_anchors = anchor.relational_anchors(
                left_index,
                right_index,
                max_occurrences=max_occurrences,
                max_pairs=max_pairs,
            )
            clusters = anchor.cluster_anchors(exact_anchors)
            extended = []
            for cluster in clusters[:max_seed_clusters]:
                match = extend_cluster(
                    cluster,
                    left_region,
                    right_region,
                    max_instructions=max_instructions,
                    max_bytes=max_bytes,
                    probable_min_paired=probable_min_paired,
                )
                if match is not None:
                    extended.append(match)
            deduplicated = deduplicate(extended)
            chains = build_chains(deduplicated)
            reported = deduplicated[:max_reported_matches]
            serialized = [match_json(match, f"M{index + 1:04d}") for index, match in enumerate(reported)]
            id_by_match = {id(match): f"M{index + 1:04d}" for index, match in enumerate(reported)}
            chain_payloads = []
            for chain in chains:
                reported_members = [match for match in chain if id(match) in id_by_match]
                if not reported_members:
                    continue
                chain_payloads.append(
                    {
                        "members": [id_by_match[id(match)] for match in reported_members],
                        "memberCount": len(reported_members),
                        "score": sum(match.alignment.score for match in reported_members),
                        "leftStart": min(match.left_start for match in reported_members),
                        "leftEndExclusive": max(match.left_end for match in reported_members),
                        "rightStart": min(match.right_start for match in reported_members),
                        "rightEndExclusive": max(match.right_end for match in reported_members),
                    }
                )
            chain_payloads.sort(key=lambda item: (-item["score"], item["leftStart"], item["rightStart"]))
            chain_json = [
                {"id": f"C{index + 1:04d}", **payload}
                for index, payload in enumerate(chain_payloads)
            ]
            probable = [match for match in deduplicated if match.classification == "probable-shared-routine"]
            aggregate = {
                "extendedSeeds": len(extended),
                "deduplicatedMatches": len(deduplicated),
                "reportedMatches": len(reported),
                "probableSharedRoutines": len(probable),
                "candidateSimilarities": sum(match.classification == "candidate-similarity" for match in deduplicated),
                "weakOrGeneric": sum(match.classification == "weak-or-generic" for match in deduplicated),
                "uniqueLeftBytes": interval_union_size([(match.left_start, match.left_end) for match in probable]),
                "uniqueRightBytes": interval_union_size([(match.right_start, match.right_end) for match in probable]),
                "supportingInstructionPairs": sum(match.metrics["supportingPairs"] for match in probable),
                "boundaryCorrectedMatches": sum(bool(match.left_shift or match.right_shift) for match in deduplicated),
                "probableBoundaryCorrectedMatches": sum(
                    bool(match.left_shift or match.right_shift) for match in probable
                ),
                "maximumScore": max((match.alignment.score for match in deduplicated), default=0),
                "minimumProbablePairedInstructions": min(
                    (match.metrics["pairedInstructions"] for match in probable), default=0
                ),
            }
            comparisons.append(
                {
                    "leftRegion": left_region["metadata"]["id"],
                    "rightRegion": right_region["metadata"]["id"],
                    "leftScan": left_scan,
                    "rightScan": right_scan,
                    "exactAnchors": len(exact_anchors),
                    "exactClusters": len(clusters),
                    "aggregate": aggregate,
                    "matches": serialized,
                    "chains": chain_json,
                }
            )
    return {
        "format": "6502-reuse-alignment-report",
        "version": 1,
        "decoderProfile": "shared official NMOS 6502 subset",
        "left": {"manifest": str(left_manifest_path), "artifact": left_manifest["artifact"]},
        "right": {"manifest": str(right_manifest_path), "artifact": right_manifest["artifact"]},
        "configuration": {
            "seedInstructionCount": seed_instruction_count,
            "minUniqueMnemonics": min_unique_mnemonics,
            "maxOccurrencesPerRegion": max_occurrences,
            "maxPairsPerFingerprint": max_pairs,
            "maxSeedClusters": max_seed_clusters,
            "maxInstructionsPerExtension": max_instructions,
            "maxBytesPerExtension": max_bytes,
            "boundaryShiftsTried": [0, -1, -2],
            "pairScores": {
                "relationalExact": 5,
                "shapeExact": 3,
                "compatibleChangedOperand": 1,
                "different": -4,
                "gapOpen": -5,
                "gapExtend": -1,
            },
            "immediateOperandsRetained": True,
            "classificationThresholds": {
                "probableSharedRoutine": {
                    "minimumPairedInstructions": probable_min_paired,
                    "minimumSupportFraction": PROBABLE_MIN_SUPPORT_FRACTION,
                    "minimumRelationalExact": PROBABLE_MIN_RELATIONAL_EXACT,
                    "maximumSeedProductFrequency": PROBABLE_MAX_SEED_PRODUCT_FREQUENCY,
                },
                "candidateSimilarity": {
                    "minimumPairedInstructions": CANDIDATE_MIN_PAIRED,
                    "minimumSupportFraction": CANDIDATE_MIN_SUPPORT_FRACTION,
                },
            },
            "classificationIsProvisional": True,
        },
        "comparisons": comparisons,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("left_manifest", type=Path)
    parser.add_argument("right_manifest", type=Path)
    parser.add_argument("output_json", type=Path)
    parser.add_argument("--markdown", type=Path)
    parser.add_argument("--seed-instruction-count", type=int, default=8)
    parser.add_argument("--probable-min-paired", type=int, default=PROBABLE_MIN_PAIRED)
    parser.add_argument("--max-seed-clusters", type=int, default=500)
    parser.add_argument("--max-reported-matches", type=int, default=100)
    args = parser.parse_args()

    report = analyze_manifests(
        args.left_manifest,
        args.right_manifest,
        seed_instruction_count=args.seed_instruction_count,
        max_seed_clusters=args.max_seed_clusters,
        max_reported_matches=args.max_reported_matches,
        probable_min_paired=args.probable_min_paired,
    )
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(f"wrote {args.output_json}")
    if args.markdown:
        args.markdown.parent.mkdir(parents=True, exist_ok=True)
        args.markdown.write_text(render_markdown(report))
        print(f"wrote {args.markdown}")
    for comparison in report["comparisons"]:
        aggregate = comparison["aggregate"]
        print(
            f"{comparison['leftRegion']} vs {comparison['rightRegion']}: "
            f"anchors={comparison['exactAnchors']}, "
            f"deduplicated={aggregate['deduplicatedMatches']}, "
            f"probable={aggregate['probableSharedRoutines']}"
        )


if __name__ == "__main__":
    main()
