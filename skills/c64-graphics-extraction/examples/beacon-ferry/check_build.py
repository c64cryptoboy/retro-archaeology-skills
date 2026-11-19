#!/usr/bin/env python3
"""Rebuild the example from a freshly exported sprite, using Python and cc65."""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent.parent


def main():
    with tempfile.TemporaryDirectory() as temp:
        work = Path(temp)
        for args in ([sys.executable, '-B', SKILL / 'example.py', 'donor'],
                     [sys.executable, '-B', SKILL / 'extract.py', 'donor/capture.json',
                      'assets', '--only', 'sprites', '--slots', '0']):
            subprocess.run(args, cwd=work, check=True)
        shutil.copyfile(HERE / 'ferry.s', work / 'ferry.s')
        subprocess.run(['ca65', 'ferry.s', '-o', 'ferry.o'], cwd=work, check=True)
        subprocess.run(['ld65', '-t', 'none', 'ferry.o', '-o', 'new.prg'], cwd=work, check=True)
        result = (work / 'new.prg').read_bytes()
        asset = (work / 'assets/slot0.bin').read_bytes()
        address = int.from_bytes(result[:2], 'little')
        off = 2 + 0x0980 - address
        if len(asset) != 64 or result[off:off+64] != asset or result != (HERE / 'beacon-ferry.prg').read_bytes():
            raise SystemExit('Rebuild or relocated asset differs')
        print(f'{len(result)}-byte PRG reproduced; 64 sprite bytes at $0980')


if __name__ == '__main__':
    main()
