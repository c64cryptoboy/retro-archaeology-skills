#!/usr/bin/env python3
"""Render a small exact functional-graph example to DOT and standalone SVG."""
from __future__ import annotations

import argparse
import html
import json
import math
from pathlib import Path


def dot_quote(value: str) -> str:
    return '"' + value.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n') + '"'


def render_dot(data: dict[str, object]) -> str:
    nodes = data["nodes"]
    mu = int(data["mu"])
    lines = [
        "digraph c64_rnd_example {",
        "  graph [rankdir=LR, bgcolor=\"#101820\", fontcolor=white, label=\"C64 BASIC V2 RND: μ=5, λ=7\", labelloc=t, fontsize=24];",
        "  node [shape=box, style=\"rounded,filled\", fontname=\"Courier New\", fontsize=12, fontcolor=\"#101820\"];",
        "  edge [color=\"#d7e3ec\", fontcolor=white, fontsize=11];",
    ]
    for node in nodes:
        index = int(node["index"])
        color = "#ffca5c" if index >= mu else "#5cc8ff"
        label = f'x{index}\\n{node["stateBytes"]}\\n≈ {node["valueApprox"]}'
        lines.append(f"  x{index} [fillcolor={dot_quote(color)}, label={dot_quote(label)}];")
    for index in range(len(nodes) - 1):
        lines.append(f"  x{index} -> x{index + 1};")
    lines.append(f'  x{data["repeatFrom"]} -> x{data["repeatTo"]} [label=" repeats", color="#ff6b8a", penwidth=2];')
    lines.extend(["  { rank=same; x5; x6; x7; x8; x9; x10; x11; }", "}"])
    return "\n".join(lines) + "\n"


def svg_text(x: float, y: float, value: str, size: int = 16, anchor: str = "middle",
             color: str = "#101820", weight: str = "normal") -> str:
    return (f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}" '
            f'font-family="monospace" font-size="{size}" font-weight="{weight}" '
            f'fill="{color}">{html.escape(value)}</text>')


def render_svg(data: dict[str, object]) -> str:
    width, height = 1500, 850
    nodes = data["nodes"]
    positions: dict[int, tuple[float, float]] = {}
    for index in range(int(data["mu"])):
        positions[index] = (95 + index * 170, 425)
    center_x, center_y, radius = 1170, 425, 220
    cycle_indices = list(range(int(data["mu"]), len(nodes)))
    for place, index in enumerate(cycle_indices):
        angle = math.pi + place * 2 * math.pi / len(cycle_indices)
        positions[index] = (center_x + radius * math.cos(angle), center_y + radius * math.sin(angle))

    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
             '<defs><marker id="arrow" markerWidth="10" markerHeight="8" refX="9" refY="4" orient="auto"><path d="M0,0 L10,4 L0,8 z" fill="#d7e3ec"/></marker></defs>',
             '<rect width="100%" height="100%" fill="#101820"/>',
             svg_text(width/2, 42, "C64 BASIC V2 RND — a complete μ=5, λ=7 example", 27, color="#f3f6f8", weight="bold"),
             svg_text(width/2, 73, f'Seed with {data["seedExpression"]}; the arrow from x11 returns exactly to x5', 17, color="#aab7c4")]

    def edge(a: int, b: int, curved: bool = False) -> None:
        x1, y1 = positions[a]; x2, y2 = positions[b]
        dx, dy = x2 - x1, y2 - y1
        length = math.hypot(dx, dy); ux, uy = dx / length, dy / length
        start = (x1 + ux * 76, y1 + uy * 46); end = (x2 - ux * 82, y2 - uy * 49)
        if curved:
            control = (center_x + 30, center_y + radius + 120)
            parts.append(f'<path d="M {start[0]:.1f},{start[1]:.1f} Q {control[0]:.1f},{control[1]:.1f} {end[0]:.1f},{end[1]:.1f}" fill="none" stroke="#ff6b8a" stroke-width="3" marker-end="url(#arrow)"/>')
        else:
            parts.append(f'<line x1="{start[0]:.1f}" y1="{start[1]:.1f}" x2="{end[0]:.1f}" y2="{end[1]:.1f}" stroke="#d7e3ec" stroke-width="2" marker-end="url(#arrow)"/>')

    for index in range(len(nodes)-1): edge(index, index+1)
    edge(int(data["repeatFrom"]), int(data["repeatTo"]), True)
    parts.append(svg_text(995, 735, "repeat to x5", 15, color="#ff8ca3", weight="bold"))
    parts.append(svg_text(460, 325, "on-ramp: 5 transitions", 18, color="#5cc8ff", weight="bold"))
    parts.append(svg_text(center_x, 120, "cycle: 7 states", 18, color="#ffca5c", weight="bold"))

    for node in nodes:
        index = int(node["index"]); x, y = positions[index]
        fill = "#ffca5c" if index >= int(data["mu"]) else "#5cc8ff"
        parts.append(f'<rect x="{x-82:.1f}" y="{y-47:.1f}" width="164" height="94" rx="12" fill="{fill}" stroke="#f3f6f8" stroke-width="1.5"/>')
        parts.append(svg_text(x, y-20, f"x{index}", 16, weight="bold"))
        parts.append(svg_text(x, y+3, str(node["stateBytes"]), 13))
        parts.append(svg_text(x, y+27, "≈ " + str(node["valueApprox"]), 12))
    parts.append(svg_text(width/2, 815, "Blue nodes feed the cycle; gold nodes repeat forever. Byte labels are the five-byte RNDX state.", 16, color="#aab7c4"))
    parts.append("</svg>\n")
    return "\n".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output_prefix", type=Path)
    args = parser.parse_args()
    data = json.loads(args.input.read_text(encoding="utf-8"))
    dot = args.output_prefix.with_suffix(".dot")
    svg = args.output_prefix.with_suffix(".svg")
    dot.write_text(render_dot(data), encoding="utf-8")
    svg.write_text(render_svg(data), encoding="utf-8")
    print(dot)
    print(svg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
