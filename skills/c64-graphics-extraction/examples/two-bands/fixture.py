"""Authored blank-screen example; no ROM or emulator needed."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # bundled graphics core
from extract import State, decode
from images import png
from two_bands import replay

BACKGROUND = {"pixels": bytes(64000), "priority": bytes(8000)}
# Register x, y, screen pointer byte, and individual color, in display order.
TUPLES = ((168, 85, 0x28, 7), (168, 180, 0x29, 2))
PLACEMENT = dict(first_lower_row=100, offset_x=-24, offset_y=-50)


def layers():
    patterns = Path(__file__).with_name("shapes.bin").read_bytes()
    if len(patterns) != 128:
        raise ValueError("expected two aligned sprite blocks")
    ram = bytearray(65536)
    ram[0x0a00:0x0a80] = patterns
    vic = bytearray(64)
    vic[0x15], vic[0x18] = 1, 0x14  # only slot 0 enabled; screen at $0400
    result = []
    for x, y, pointer, color in TUPLES:
        vic[0], vic[1], ram[0x07f8], vic[0x27] = x, y, pointer, color
        scene = decode(State(bytes(ram), bytes(vic), 3), only="sprites", slots=[0])
        result.append(scene["sprites"][0])
    return result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="new output directory")
    args = parser.parse_args()
    plane = replay(BACKGROUND, *layers(), **PLACEMENT)
    args.output.mkdir(exist_ok=False)
    png(args.output / "replay.png", 320, 200, plane)
