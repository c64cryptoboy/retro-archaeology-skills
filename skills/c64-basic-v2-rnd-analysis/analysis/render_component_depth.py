#!/usr/bin/env python3
"""Render an aggregate whole-graph atlas from exact component/depth counts.

Each of the 15 functional-graph components is a column. Vertical position is
on-ramp depth (mu), and brightness is log population normalized independently
within that component. This is an aggregate atlas, not a literal node layout.
"""
from __future__ import annotations

import argparse
import csv
import html
import math
from pathlib import Path

WIDTH, HEIGHT = 1700, 1120
PALETTE = ((92, 200, 255), (255, 202, 92), (255, 107, 138), (139, 209, 124), (179, 157, 219))


def txt(x: float, y: float, value: object, size: int = 16, anchor: str = "middle",
        color: str = "#e8edf2", weight: str = "normal") -> str:
    return (f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}" '
            f'font-family="system-ui, sans-serif" font-size="{size}" '
            f'font-weight="{weight}" fill="{color}">{html.escape(str(value))}</text>')


def blend(rgb: tuple[int, int, int], amount: float) -> str:
    base = (23, 34, 44)
    values = tuple(round(base[i] + (rgb[i] - base[i]) * amount) for i in range(3))
    return "#" + "".join(f"{value:02x}" for value in values)


def render(depth_path: Path, component_path: Path, bin_width: int) -> str:
    basin: dict[int, int] = {}
    population = 0
    with component_path.open(newline="", encoding="utf-8") as stream:
        component_rows = list(csv.DictReader(stream))
    with depth_path.open(newline="", encoding="utf-8") as stream:
        raw = [(int(row["lambda"]), int(row["mu"]), int(row["count"])) for row in csv.DictReader(stream)]
    for length, _, count in raw:
        basin[length] = basin.get(length, 0) + count
        population += count
    lengths = sorted(basin)
    if len(lengths) != len(component_rows):
        raise ValueError("component and depth files disagree")
    max_mu = max(mu for _, mu, _ in raw)
    bins = max_mu // bin_width + 1
    aggregate: dict[int, list[int]] = {length: [0] * bins for length in lengths}
    for length, mu, count in raw:
        aggregate[length][mu // bin_width] += count

    left, top, plot_w, plot_h = 105, 170, 1530, 760
    column_w = plot_w / len(lengths)
    row_h = plot_h / bins
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">',
             '<rect width="100%" height="100%" fill="#101820"/>',
             txt(WIDTH/2, 48, "C64 BASIC V2 RND — aggregate atlas of the entire functional graph", 29, weight="bold"),
             txt(WIDTH/2, 80, f"{population:,} canonical states • 15 components • depth bins of {bin_width:,}", 18, color="#aab7c4"),
             txt(WIDTH/2, 108, "Each column is one complete component; brightness is log-scaled within that column", 16, color="#aab7c4")]

    for depth in range(0, max_mu + 1, 10_000):
        py = top + plot_h - depth / (bins * bin_width) * plot_h
        parts.append(f'<line x1="{left}" y1="{py:.1f}" x2="{left+plot_w}" y2="{py:.1f}" stroke="#34414d"/>')
        parts.append(txt(left-12, py+5, f"{depth:,}", 13, "end", "#9aa8b5"))
    for column, length in enumerate(lengths):
        values = aggregate[length]
        maximum = max(values)
        denominator = math.log10(maximum + 1)
        rgb = PALETTE[column % len(PALETTE)]
        x = left + column * column_w
        for index, count in enumerate(values):
            intensity = math.log10(count + 1) / denominator if count else 0
            y = top + plot_h - (index + 1) * row_h
            parts.append(f'<rect x="{x+1:.2f}" y="{y:.2f}" width="{column_w-2:.2f}" height="{max(1,row_h+.1):.2f}" fill="{blend(rgb,intensity)}"/>')
        parts.append(f'<rect x="{x+1:.2f}" y="{top:.2f}" width="{column_w-2:.2f}" height="{plot_h:.2f}" fill="none" stroke="#52606d"/>')
        parts.append(txt(x+column_w/2, top+plot_h+25, f"{length:,}", 13))
        share = basin[length] * 100 / population
        label = f"{share:.3g}%" if share >= .001 else f"{share:.2e}%"
        parts.append(txt(x+column_w/2, top-15, label, 12, color="#d3dce4"))
    parts.append(f'<text x="30" y="{top+plot_h/2:.1f}" transform="rotate(-90 30 {top+plot_h/2:.1f})" text-anchor="middle" font-family="system-ui, sans-serif" font-size="17" font-weight="bold" fill="#5cc8ff">on-ramp depth μ →</text>')
    parts.append(txt(left+plot_w/2, top+plot_h+58, "eventual cycle length λ", 17, color="#ffca5c", weight="bold"))
    parts.append(txt(WIDTH/2, 1020, "How to read it: a bright cell means many starts in that component have that depth.", 17, color="#d3dce4"))
    parts.append(txt(WIDTH/2, 1048, "Column brightness is normalized separately so tiny components are visible; percentages above columns preserve absolute scale.", 15, color="#aab7c4"))
    parts.append(txt(WIDTH/2, 1076, "This preserves exact component/depth counts but intentionally does not draw 2.94 billion individual nodes or edges.", 15, color="#aab7c4"))
    parts.append("</svg>\n")
    return "\n".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("component_depth_csv", type=Path)
    parser.add_argument("cycle_components_csv", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--bin-width", type=int, default=500)
    args = parser.parse_args()
    if args.bin_width <= 0:
        parser.error("--bin-width must be positive")
    args.output.write_text(render(args.component_depth_csv, args.cycle_components_csv, args.bin_width), encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
