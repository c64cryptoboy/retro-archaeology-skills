#!/usr/bin/env python3
"""Render the exact C64 BASIC V2 RND histograms as a standalone SVG.

No third-party Python packages are required. The three panels deliberately use
log scales where needed so both billion-state basins and tiny dud basins remain
visible without pretending their populations are comparable.
"""
from __future__ import annotations

import argparse
import csv
import html
import math
from pathlib import Path

WIDTH, HEIGHT = 1600, 1200
COLORS = ("#5cc8ff", "#ffca5c", "#ff6b8a", "#8bd17c", "#b39ddb")


def read_histogram(path: Path) -> list[tuple[int, int]]:
    with path.open(newline="", encoding="utf-8") as stream:
        return [(int(row["value"]), int(row["count"])) for row in csv.DictReader(stream)]


def esc(text: object) -> str:
    return html.escape(str(text))


def text(x: float, y: float, value: object, size: int = 18, anchor: str = "start",
         color: str = "#e8edf2", weight: str = "normal") -> str:
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-family="system-ui, sans-serif" '
            f'font-size="{size}" text-anchor="{anchor}" fill="{color}" '
            f'font-weight="{weight}">{esc(value)}</text>')


def line(x1: float, y1: float, x2: float, y2: float, color: str = "#52606d",
         width: float = 1, dash: str = "") -> str:
    extra = f' stroke-dasharray="{dash}"' if dash else ""
    return (f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            f'stroke="{color}" stroke-width="{width}"{extra}/>')


def cycle_panel(parts: list[str], rows: list[tuple[int, int]], population: int) -> None:
    x, y, w, h = 70, 170, 700, 440
    parts.append(text(x, y - 45, "A. Basin population by eventual cycle length", 25, weight="bold"))
    parts.append(text(x, y - 17, "Logarithmic population scale—tiny cycles remain visible", 16, color="#aab7c4"))
    label_w, right_w = 95, 145
    plot_x, plot_w = x + label_w, w - label_w - right_w
    row_h = h / len(rows)
    maximum_log = math.log10(max(count for _, count in rows))
    for tick in range(0, 10):
        value = 10 ** tick
        if value > population:
            break
        tx = plot_x + math.log10(value) / maximum_log * plot_w
        parts.append(line(tx, y, tx, y + h, "#34414d"))
        parts.append(text(tx, y + h + 23, f"10^{tick}", 13, "middle", "#9aa8b5"))
    for index, (length, count) in enumerate(rows):
        cy = y + index * row_h + row_h * .72
        bar_y = y + index * row_h + 4
        bar_w = max(1.5, math.log10(max(count, 1)) / maximum_log * plot_w)
        color = COLORS[index % len(COLORS)]
        parts.append(text(plot_x - 12, cy, f"{length:,}", 15, "end"))
        parts.append(f'<rect x="{plot_x:.1f}" y="{bar_y:.1f}" width="{bar_w:.1f}" '
                     f'height="{max(5,row_h-8):.1f}" rx="3" fill="{color}"/>')
        parts.append(text(plot_x + plot_w + 10, cy,
                          f"{count:,}  ({count*100/population:.6g}%)", 14))
    parts.append(text(plot_x + plot_w / 2, y + h + 50, "canonical starting states", 16, "middle"))
    parts.append(text(x - 5, y + h / 2, "λ", 24, "middle", "#ffca5c", "bold"))


def survival_panel(parts: list[str], rows: list[tuple[int, int]], population: int) -> None:
    x, y, w, h = 850, 170, 680, 440
    parts.append(text(x, y - 45, "B. Chance of at least this many distinct outputs", 25, weight="bold"))
    parts.append(text(x, y - 17, "Survival curve for μ + λ; logarithmic percentage axis", 16, color="#aab7c4"))
    max_value = rows[-1][0]
    counts = dict(rows)
    suffix = [0] * (max_value + 2)
    for value in range(max_value, -1, -1):
        suffix[value] = suffix[value + 1] + counts.get(value, 0)
    plot_x, plot_y, plot_w, plot_h = x + 72, y, w - 90, h
    for pct in (100, 10, 1, .1, .01, .001, .0001, .00001):
        py = plot_y + (-math.log10(pct / 100) / 7) * plot_h
        parts.append(line(plot_x, py, plot_x + plot_w, py, "#34414d"))
        parts.append(text(plot_x - 10, py + 5, f"{pct:g}%", 13, "end", "#9aa8b5"))
    points = []
    for pixel in range(int(plot_w) + 1):
        value = round(pixel / plot_w * max_value)
        pct = max(suffix[value] * 100 / population, 1e-7)
        py = plot_y + min(7, -math.log10(pct / 100)) / 7 * plot_h
        points.append(f"{plot_x+pixel:.1f},{py:.1f}")
    parts.append(f'<polyline points="{" ".join(points)}" fill="none" stroke="#5cc8ff" stroke-width="3"/>')
    for value in (0, 40_000, 80_000, 100_000, max_value):
        px = plot_x + value / max_value * plot_w
        parts.append(line(px, plot_y, px, plot_y + plot_h, "#34414d"))
        parts.append(text(px, plot_y + plot_h + 24, f"{value:,}", 13, "middle", "#9aa8b5"))
    annotations = ((100_000, "8.318% ≥100k"), (110_000, "0.7355% ≥110k"),
                   (115_000, "0.01971% ≥115k"), (116_759, "one maximum"))
    for value, label in annotations:
        px = plot_x + value / max_value * plot_w
        pct = max(suffix[value] * 100 / population, 1e-7)
        py = plot_y + min(7, -math.log10(pct / 100)) / 7 * plot_h
        parts.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="5" fill="#ffca5c"/>')
        parts.append(text(px - 8, py - 10, label, 13, "end", "#ffdc89"))
    parts.append(text(plot_x + plot_w / 2, plot_y + plot_h + 52, "μ + λ", 17, "middle"))


def total_panel(parts: list[str], rows: list[tuple[int, int]]) -> None:
    x, y, w, h = 70, 730, 1460, 360
    parts.append(text(x, y - 45, "C. Distribution of on-ramp plus cycle length", 25, weight="bold"))
    parts.append(text(x, y - 17, "2,000-step bins; logarithmic counts reveal both dense and rare lengths", 16, color="#aab7c4"))
    max_value = rows[-1][0]
    bin_width = 2000
    bins = [0] * (max_value // bin_width + 1)
    for value, count in rows:
        bins[value // bin_width] += count
    max_log = math.log10(max(bins))
    plot_x, plot_y, plot_w, plot_h = x + 70, y, w - 90, h
    for exponent in range(0, 10):
        if 10 ** exponent > max(bins):
            break
        py = plot_y + plot_h - exponent / max_log * plot_h
        parts.append(line(plot_x, py, plot_x + plot_w, py, "#34414d"))
        parts.append(text(plot_x - 10, py + 5, f"10^{exponent}", 13, "end", "#9aa8b5"))
    bw = plot_w / len(bins)
    for index, count in enumerate(bins):
        if not count:
            continue
        bh = math.log10(count) / max_log * plot_h if count > 1 else 2
        parts.append(f'<rect x="{plot_x+index*bw:.2f}" y="{plot_y+plot_h-bh:.2f}" '
                     f'width="{max(.8,bw-.4):.2f}" height="{bh:.2f}" fill="#8bd17c"/>')
    for value in (0, 20_000, 40_000, 60_000, 80_000, 100_000, max_value):
        px = plot_x + value / max_value * plot_w
        parts.append(line(px, plot_y, px, plot_y + plot_h, "#34414d"))
        parts.append(text(px, plot_y + plot_h + 24, f"{value:,}", 13, "middle", "#9aa8b5"))
    parts.append(text(plot_x + plot_w / 2, plot_y + plot_h + 53, "distinct states before repetition (μ + λ)", 17, "middle"))


def render(directory: Path) -> str:
    cycle = read_histogram(directory / "hist-lambda.csv")
    total = read_histogram(directory / "hist-total.csv")
    population = sum(count for _, count in total)
    if sum(count for _, count in cycle) != population:
        raise ValueError("histogram populations disagree")
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">',
             '<rect width="100%" height="100%" fill="#101820"/>',
             text(WIDTH / 2, 50, "C64 BASIC V2 RND: all 2,936,012,800 canonical states", 31, "middle", weight="bold"),
             text(WIDTH / 2, 82, "Exact full-domain functional-graph census • starting-state weighted", 18, "middle", "#aab7c4")]
    cycle_panel(parts, cycle, population)
    survival_panel(parts, total, population)
    total_panel(parts, total)
    parts.append(text(WIDTH / 2, 1170, "μ = on-ramp length; λ = eventual cycle length. Log scales are labeled explicitly.", 17, "middle", "#aab7c4"))
    parts.append("</svg>\n")
    return "\n".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_directory", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.write_text(render(args.run_directory), encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
