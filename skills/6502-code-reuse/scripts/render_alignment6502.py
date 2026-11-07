#!/usr/bin/env python3
"""Render a reuse-align6502 match as presentation-ready side-by-side text."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable


def instruction_parts(instruction: dict[str, Any] | None) -> tuple[str, str, str]:
    if instruction is None:
        return "", "", ""
    address = instruction.get("address")
    if address is None:
        address = instruction.get("offset")
    address_text = "" if address is None else f"${address:04X}"
    mnemonic = instruction.get("mnemonic", "")
    text = instruction.get("text", "")
    operand = text[len(mnemonic) :].strip() if text.startswith(mnemonic) else text
    return address_text, mnemonic, operand


def all_matches(document: dict[str, Any]) -> Iterable[tuple[dict[str, Any], dict[str, Any]]]:
    for comparison in document.get("comparisons", []):
        for match in comparison.get("matches", []):
            yield comparison, match


def select_match(
    document: dict[str, Any], match_id: str | None = None
) -> tuple[dict[str, Any], dict[str, Any]]:
    candidates = list(all_matches(document))
    if match_id is not None:
        candidates = [item for item in candidates if item[1].get("id") == match_id]
        if not candidates:
            raise ValueError(f"match not found: {match_id}")
        if len(candidates) > 1:
            raise ValueError(f"match ID is ambiguous across comparisons: {match_id}")
        return candidates[0]
    if not candidates:
        raise ValueError("alignment document contains no matches")
    return max(
        candidates,
        key=lambda item: (
            item[1].get("metrics", {}).get("longestSupportingRun", 0),
            item[1].get("metrics", {}).get("pairedInstructions", 0),
            max(
                item[1].get("leftEndExclusive", 0) - item[1].get("leftStart", 0),
                item[1].get("rightEndExclusive", 0) - item[1].get("rightStart", 0),
            ),
        ),
    )


def presentation_rows(
    columns: list[dict[str, Any]], pair_differences: bool = False
) -> list[tuple[tuple[str, str, str], tuple[str, str, str], str]]:
    """Convert alignment columns to rows without implying false replacement pairs.

    The affine aligner retains negatively scored ``different`` pairs because they
    can bridge two supporting runs. For presentation, a contiguous change hunk is
    clearer when each side is shown independently. Existing gap columns join the
    same hunk so inserted/deleted instructions remain contiguous.
    """
    blank = ("", "", "")
    rows = []
    index = 0
    while index < len(columns):
        column = columns[index]
        relation = column.get("relation", "")
        if pair_differences or relation not in {"different", "gap-left", "gap-right"}:
            rows.append(
                (
                    instruction_parts(column.get("left")),
                    instruction_parts(column.get("right")),
                    relation,
                )
            )
            index += 1
            continue

        hunk = []
        while index < len(columns) and columns[index].get("relation", "") in {
            "different",
            "gap-left",
            "gap-right",
        }:
            hunk.append(columns[index])
            index += 1

        left = [instruction_parts(item.get("left")) for item in hunk if item.get("left")]
        right = [instruction_parts(item.get("right")) for item in hunk if item.get("right")]
        first = hunk[0]
        if first.get("left") is None and first.get("right") is not None:
            side_order = ("right", "left")
        elif first.get("right") is None and first.get("left") is not None:
            side_order = ("left", "right")
        else:
            # For a pure replacement, show target/right additions before the
            # source/left instructions they replace.
            side_order = ("right", "left")
        for side_name in side_order:
            items = right if side_name == "right" else left
            for item in items:
                rows.append(
                    (blank, item, "right-only")
                    if side_name == "right"
                    else (item, blank, "left-only")
                )
    return rows


def render_table(
    match: dict[str, Any],
    left_label: str,
    right_label: str,
    show_relation: bool = False,
    pair_differences: bool = False,
) -> str:
    rows = presentation_rows(match.get("columns", []), pair_differences)

    address_width = 7
    mnemonic_width = 8
    operand_width = max(
        [len(left_label) - address_width - mnemonic_width - 2, 18]
        + [len(side[2]) for row in rows for side in row[:2]]
    )
    side_width = address_width + 1 + mnemonic_width + 1 + operand_width

    def side(address: str, mnemonic: str, operand: str) -> str:
        if not (address or mnemonic or operand):
            return " " * side_width
        return f"{address:<{address_width}} {mnemonic:<{mnemonic_width}} {operand:<{operand_width}}"

    separator = " | "
    lines = [
        f"{left_label:<{side_width}}{separator}{right_label:<{side_width}}",
        f"{'Address':<{address_width}} {'Operator':<{mnemonic_width}} {'Operand':<{operand_width}}"
        f"{separator}{'Address':<{address_width}} {'Operator':<{mnemonic_width}} {'Operand':<{operand_width}}",
        f"{'-' * side_width}{separator}{'-' * side_width}",
    ]
    for left, right, relation in rows:
        line = f"{side(*left)}{separator}{side(*right)}"
        if show_relation:
            line += f" | {relation}"
        lines.append(line.rstrip())
    return "\n".join(lines) + "\n"


def markdown_document(
    source: Path,
    comparison: dict[str, Any],
    match: dict[str, Any],
    left_label: str,
    right_label: str,
    show_relation: bool,
    pair_differences: bool,
) -> str:
    metrics = match.get("metrics", {})
    left_bytes = match["leftEndExclusive"] - match["leftStart"]
    right_bytes = match["rightEndExclusive"] - match["rightStart"]
    table = render_table(
        match, left_label, right_label, show_relation, pair_differences
    ).rstrip()
    return (
        f"# Side-by-side 6502 alignment: {match.get('id', 'unknown')}\n\n"
        f"- Source: `{source}`\n"
        f"- Regions: `{comparison.get('leftRegion')}` vs `{comparison.get('rightRegion')}`\n"
        f"- Classification: `{match.get('classification')}`\n"
        f"- Instructions: {metrics.get('pairedInstructions')} paired; "
        f"longest supporting run {metrics.get('longestSupportingRun')}\n"
        f"- Span: {left_bytes} bytes left, {right_bytes} bytes right\n"
        f"- Relations: {metrics.get('relationalExact', 0)} relational-exact, "
        f"{metrics.get('shapeExact', 0)} shape-exact, "
        f"{metrics.get('compatibleChangedOperand', 0)} changed operand, "
        f"{metrics.get('gaps', 0)} gaps\n\n"
        "A blank instruction cell represents an insertion/deletion on the other side. "
        "Unlike instructions are shown as separate one-sided replacement rows.\n\n"
        f"```text\n{table}\n```\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("alignment", type=Path, help="reuse_align6502 JSON output")
    parser.add_argument("--match", help="match ID; defaults to longest supporting run")
    parser.add_argument("--left-label", default="LEFT")
    parser.add_argument("--right-label", default="RIGHT")
    parser.add_argument("--format", choices=("text", "markdown"), default="text")
    parser.add_argument("--show-relation", action="store_true")
    parser.add_argument(
        "--pair-differences",
        action="store_true",
        help="show unlike instructions paired as retained by the raw affine alignment",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    document = json.loads(args.alignment.read_text())
    comparison, match = select_match(document, args.match)
    if args.format == "markdown":
        rendered = markdown_document(
            args.alignment,
            comparison,
            match,
            args.left_label,
            args.right_label,
            args.show_relation,
            args.pair_differences,
        )
    else:
        rendered = render_table(
            match,
            args.left_label,
            args.right_label,
            args.show_relation,
            args.pair_differences,
        )

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered)
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
