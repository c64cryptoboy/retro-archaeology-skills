"""Wrap the linked Two Hops image.  Usage: python pack.py INPUT.bin NEW.sid"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from sidfile import Tune, write_psid

if __name__ == '__main__':
    source, output = map(Path, sys.argv[1:])
    tune = Tune(source.read_bytes(), 0x1000, 0x1000, 0x1003, 'NTSC', 'vbi',
                '8580', 'Two Hops', 'Original example', '2026', prefix=False)
    wire = write_psid(tune, dirty_pages=(0x24, 0x74))
    with output.open('xb') as f:
        f.write(wire)
