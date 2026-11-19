#!/usr/bin/env python3
"""Write a small original, reproducible frozen capture, not an emulator snapshot."""
import argparse
import json
from pathlib import Path


def make_example(directory):
    out = Path(directory)
    out.mkdir(exist_ok=False)
    ram, vic, color = bytearray(65536), bytearray(64), bytearray(1000)
    # Bank $4000; matrix $6800; custom character patterns $5000.
    vic[0x11], vic[0x16], vic[0x18] = 0x1b, 0x18, 0xa4
    vic[0x21:0x24] = bytes([6, 14, 3])
    ram[0x5008:0x5010] = bytes.fromhex('18 3c 7e ff ff 7e 3c 18')
    for i in range(1000):
        y, x = divmod(i, 40)
        ram[0x6800+i] = int((x+y) % 4 != 0)
        color[i] = (7, 9, 10, 13)[(x//5 + y//5) % 4]
    # Same source interpreted by slot 0 as color pairs, by slot 1 as bits.
    ram[0x6bf8:0x6c00] = bytes([0x80]) * 8
    rows = ['000001000000', '000011110000', '000122221000', '001223322100',
            '012233332210', '122333333221', '012233332210', '001223322100',
            '000122221000', '000011110000', '000001000000']
    for y, row in enumerate(rows, 5):
        ram[0x6000+3*y:0x6003+3*y] = int(row, 4).to_bytes(3, 'big')
    ram[0x603f] = 0xff  # alignment byte, never a visible row
    vic[:4] = bytes([64, 80, 108, 80])
    vic[0x15], vic[0x1c], vic[0x1d] = 3, 1, 2
    vic[0x25:0x29] = bytes([2, 7, 3, 0])
    for name, data in [('ram.bin', ram), ('vic.bin', vic), ('color.bin', color)]:
        (out / name).write_bytes(data)
    spec = {'ram': 'ram.bin', 'vic': 'vic.bin', 'color_ram': 'color.bin', 'cia2_pins': 2}
    (out / 'capture.json').write_text(json.dumps(spec, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('new_directory')
    make_example(parser.parse_args().new_directory)
