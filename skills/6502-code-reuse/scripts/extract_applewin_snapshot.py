#!/usr/bin/env python3
"""Extract CPU-memory byte regions from an AppleWin YAML save state.

AppleWin's file intentionally repeats YAML keys such as ``Unit``.  This parser
therefore follows the simple indentation/hex-row format that AppleWin writes
instead of using a generic YAML loader that could discard duplicate units.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import re
from pathlib import Path
from typing import Any

from region_manifest import (
    artifact_record,
    build_manifest,
    region_record,
    write_manifest,
)

HEADING = re.compile(r"^(?P<indent> *)(?P<key>[^:#][^:]*):\s*(?:#.*)?$")
HEX_ROW = re.compile(
    r"^(?P<indent> +)(?P<offset>[0-9A-Fa-f]{4}):\s*"
    r"(?P<data>[0-9A-Fa-f]+)\s*(?:#.*)?$"
)
SCALAR = re.compile(
    r"^(?P<indent> *)(?P<key>[^:#][^:]*):\s*(?P<value>.+?)\s*$"
)


class SnapshotError(ValueError):
    pass


@dataclass(eq=False)
class Node:
    key: str
    indent: int
    line: int
    parent: "Node | None"
    sibling_index: int
    scalars: dict[str, str] = field(default_factory=dict)
    rows: list[tuple[int, int, bytes]] = field(default_factory=list)

    def ancestors(self) -> list["Node"]:
        result: list[Node] = []
        node: Node | None = self
        while node is not None:
            result.append(node)
            node = node.parent
        result.reverse()
        return result

    def yaml_path(self) -> str:
        parts = []
        for node in self.ancestors():
            if node.key == "Unit" or node.sibling_index:
                parts.append(f"{node.key}[{node.sibling_index}]")
            else:
                parts.append(node.key)
        return "/".join(parts)


@dataclass(frozen=True)
class ExtractedRegion:
    region_id: str
    filename: str
    data: bytes
    base_address: int
    source: dict[str, Any]


def _strip_comment(value: str) -> str:
    # Scalar values needed here are numeric/simple words and do not contain '#'.
    return value.split("#", 1)[0].strip().strip('"')


def _parse_int(value: str, field_name: str) -> int:
    try:
        return int(_strip_comment(value), 0)
    except ValueError as exc:
        raise SnapshotError(f"{field_name} is not an integer: {value!r}") from exc


def _is_cpu_memory_node(node: Node) -> bool:
    key = node.key
    return (
        key == "Main Memory"
        or key == "Auxiliary Memory"
        or re.fullmatch(r"Auxiliary Memory Bank[0-9A-Fa-f]*", key) is not None
        or re.fullmatch(r"Memory Bank[0-9A-Fa-f]*", key) is not None
    )


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "region"


def _parse_nodes(text: str) -> list[Node]:
    nodes: list[Node] = []
    stack: list[Node] = []
    sibling_counts: dict[tuple[int | None, str], int] = {}

    for line_number, line in enumerate(text.splitlines(), 1):
        row_match = HEX_ROW.match(line)
        if row_match:
            indent = len(row_match.group("indent"))
            if not stack or stack[-1].indent >= indent:
                raise SnapshotError(f"hex row at line {line_number} has no parent map")
            hex_data = row_match.group("data")
            if len(hex_data) % 2:
                raise SnapshotError(f"hex row at line {line_number} has odd length")
            stack[-1].rows.append(
                (
                    line_number,
                    int(row_match.group("offset"), 16),
                    bytes.fromhex(hex_data),
                )
            )
            continue

        heading_match = HEADING.match(line)
        if heading_match:
            indent = len(heading_match.group("indent"))
            key = heading_match.group("key").strip()
            while stack and stack[-1].indent >= indent:
                stack.pop()
            parent = stack[-1] if stack else None
            count_key = (id(parent) if parent is not None else None, key)
            sibling_index = sibling_counts.get(count_key, 0)
            sibling_counts[count_key] = sibling_index + 1
            node = Node(key, indent, line_number, parent, sibling_index)
            nodes.append(node)
            stack.append(node)
            continue

        scalar_match = SCALAR.match(line)
        if scalar_match:
            indent = len(scalar_match.group("indent"))
            while stack and stack[-1].indent >= indent:
                stack.pop()
            if stack:
                stack[-1].scalars[scalar_match.group("key").strip()] = _strip_comment(
                    scalar_match.group("value")
                )

    return nodes


def _extract_block(node: Node) -> tuple[bytes, int, int]:
    if not node.rows:
        raise SnapshotError(f"{node.yaml_path()} has no hex rows")
    output = bytearray()
    expected = node.rows[0][1]
    first_offset = expected
    for line_number, offset, chunk in node.rows:
        if not chunk:
            raise SnapshotError(f"empty hex row at line {line_number}")
        if offset != expected:
            raise SnapshotError(
                f"{node.yaml_path()} is non-contiguous at line {line_number}: "
                f"expected {expected:04X}, got {offset:04X}"
            )
        output.extend(chunk)
        expected += len(chunk)
    return bytes(output), first_offset, expected


def _find_apple_unit(nodes: list[Node]) -> Node:
    units = [node for node in nodes if node.key == "Unit"]
    for unit in units:
        if unit.scalars.get("Type") == "Apple2":
            return unit
    raise SnapshotError("missing Unit with Type: Apple2")


def _is_descendant(node: Node, ancestor: Node) -> bool:
    parent: Node | None = node
    while parent is not None:
        if parent is ancestor:
            return True
        parent = parent.parent
    return False


def parse_snapshot(data: bytes) -> dict[str, Any]:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise SnapshotError("AppleWin state is not UTF-8 text") from exc

    nodes = _parse_nodes(text)
    file_headers = [node for node in nodes if node.key == "File_hdr" and node.parent is None]
    if len(file_headers) != 1:
        raise SnapshotError("expected exactly one root File_hdr")
    file_header = file_headers[0]
    if file_header.scalars.get("Tag") != "AppleWin Save State":
        raise SnapshotError("File_hdr Tag is not AppleWin Save State")
    file_version = _parse_int(file_header.scalars.get("Version", ""), "File_hdr.Version")

    apple_unit = _find_apple_unit(nodes)
    state_nodes = [
        node
        for node in nodes
        if node.key == "State" and node.parent is apple_unit
    ]
    if len(state_nodes) != 1:
        raise SnapshotError("Apple2 Unit must contain exactly one State map")
    apple_state = state_nodes[0]
    cpu_nodes = [
        node
        for node in nodes
        if node.key == "CPU" and _is_descendant(node, apple_state)
    ]
    if len(cpu_nodes) != 1:
        raise SnapshotError("Apple2 state must contain exactly one CPU map")
    cpu_node = cpu_nodes[0]

    cpu: dict[str, Any] = {"type": cpu_node.scalars.get("Type")}
    for source_key, output_key in (
        ("A", "a"),
        ("X", "x"),
        ("Y", "y"),
        ("P", "p"),
        ("S", "sp"),
        ("PC", "pc"),
        ("Cumulative Cycles", "cumulativeCycles"),
    ):
        if source_key in cpu_node.scalars:
            cpu[output_key] = _parse_int(
                cpu_node.scalars[source_key], f"CPU.{source_key}"
            )

    memory_nodes = [node for node in nodes if node.rows and _is_cpu_memory_node(node)]
    if not memory_nodes:
        raise SnapshotError("snapshot contains no recognized CPU-memory hex maps")

    slug_counts: dict[str, int] = {}
    regions: list[ExtractedRegion] = []
    for node in memory_nodes:
        region_data, start, end = _extract_block(node)
        basic_slug = _slug(node.key)
        occurrence = slug_counts.get(basic_slug, 0)
        slug_counts[basic_slug] = occurrence + 1
        suffix = "" if occurrence == 0 else f"-{occurrence}"
        region_id = f"applewin-{basic_slug}{suffix}"
        regions.append(
            ExtractedRegion(
                region_id=region_id,
                filename=f"{region_id}.bin",
                data=region_data,
                base_address=start,
                source={
                    "container": "applewin-yaml-hex-map",
                    "yamlPath": node.yaml_path(),
                    "headingLine": node.line,
                    "firstDataLine": node.rows[0][0],
                    "lastDataLine": node.rows[-1][0],
                    "offsetStart": start,
                    "offsetEndExclusive": end,
                    "rowCount": len(node.rows),
                },
            )
        )

    ignored_blocks = []
    for node in nodes:
        if node.rows and node not in memory_nodes:
            block_data, start, end = _extract_block(node)
            ignored_blocks.append(
                {
                    "yamlPath": node.yaml_path(),
                    "headingLine": node.line,
                    "size": len(block_data),
                    "offsetStart": start,
                    "offsetEndExclusive": end,
                    "reason": "hex blob is not a recognized CPU-memory map",
                }
            )

    return {
        "format": "applewin-yaml-save-state",
        "fileVersion": file_version,
        "machine": {
            "model": apple_state.scalars.get("Model"),
            "unitVersion": _parse_int(apple_unit.scalars.get("Version", ""), "Unit.Version"),
        },
        "cpu": cpu,
        "regions": regions,
        "ignoredHexBlocks": ignored_blocks,
    }


def extract_to_directory(snapshot_path: Path, output_dir: Path) -> dict[str, Any]:
    source_data = snapshot_path.read_bytes()
    parsed = parse_snapshot(source_data)
    output_dir.mkdir(parents=True, exist_ok=True)

    cpu_type = parsed["cpu"].get("type")
    cpu_profile = "65c02" if cpu_type == "65C02" else None
    region_entries = []
    for extracted in parsed["regions"]:
        output_path = output_dir / extracted.filename
        output_path.write_bytes(extracted.data)
        region_entries.append(
            region_record(
                region_id=extracted.region_id,
                path=extracted.filename,
                data=extracted.data,
                kind="cpu-memory",
                source=extracted.source,
                base_address=extracted.base_address,
                cpu_profile=cpu_profile,
            )
        )

    capture = {
        "formatVersion": parsed["fileVersion"],
        "machine": parsed["machine"],
        "cpu": parsed["cpu"],
        "ignoredHexBlocks": parsed["ignoredHexBlocks"],
    }
    manifest = build_manifest(
        artifact=artifact_record(snapshot_path, source_data, parsed["format"]),
        regions=region_entries,
        capture=capture,
    )
    write_manifest(output_dir / "regions.json", manifest)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()

    manifest = extract_to_directory(args.snapshot, args.output_dir)
    for region in manifest["regions"]:
        print(
            f"wrote {args.output_dir / region['path']} "
            f"({region['size']} bytes, SHA-256 {region['sha256']})"
        )
    print(f"wrote {args.output_dir / 'regions.json'}")


if __name__ == "__main__":
    main()
