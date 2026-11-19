"""Capture ordered, canonical SID stores from the original Glass Steps PSID."""
import argparse
import csv
import hashlib
from pathlib import Path
from typing import NamedTuple


GLASS_STEPS = 'fee100826d90290f166fec6c89cebdff7feaaa4ac31231c996b0aa424786ae2e'


class Write(NamedTuple):
    phase: str
    call: int
    order: int
    emulator_cycle_in_call: int
    tick: int
    address: int
    value: int


def capture(path):
    """Return (ordered Write rows, exclusive play-call count), including init at call -1."""
    return _capture_reviewed(path, GLASS_STEPS)


def _capture_reviewed(path, expected_digest):
    # Private comparison/tests can use a separately reviewed and pinned specimen.
    if hashlib.sha256(Path(path).read_bytes()).hexdigest() != expected_digest:
        raise ValueError('not the reviewed SID file (SHA-256 mismatch)')
    try:
        from chiptunesak.sid import SidImport
    except ImportError as exc:
        raise RuntimeError('optional capture needs the documented ChiptuneSAK environment') from exc

    class Trace(SidImport):
        def __init__(self):
            super().__init__()
            self.rows = []
            self.call = -1
            self.order = 0

        def call_sid_play(self, play_addr):
            self.call = self.play_call_num
            self.order = 0
            return super().call_sid_play(play_addr)

        def track_io_settings(self, loc, val):
            super().track_io_settings(loc, val)  # keep the importer's own history
            cpu = self.cpu_state
            if not cpu.see_io or not 0xd400 <= loc <= 0xd7ff:
                return
            if loc > 0xd418:
                raise ValueError(f'noncanonical SID register or mirror: ${loc:04x}')
            # Official STA, STX, and STY encodings that can address the SID.
            if cpu.last_instruction not in (0x81, 0x8d, 0x91, 0x99, 0x9d, 0x8e, 0x8c):
                raise ValueError(f'not a supported single-store SID instruction at ${loc:04x}')
            self.rows.append(Write('init' if self.call < 0 else 'play', self.call,
                                   self.order, cpu.cpucycles, max(0, self.call), loc, val))
            self.order += 1

    observer = Trace()  # memory, coordinates, and importer state start fresh
    observer.import_sid(str(path), subtune=0, seconds=2, verbose=False)
    return observer.rows, observer.play_call_num


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('sid', type=Path)
    p.add_argument('csv', type=Path, help='new output file for trace_states.py')
    args = p.parse_args()
    rows, count = capture(args.sid)
    with args.csv.open('x', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(Write._fields)
        writer.writerows(rows)
    print(f'{len(rows)} writes; --end-tick {count}')


if __name__ == '__main__':
    main()
