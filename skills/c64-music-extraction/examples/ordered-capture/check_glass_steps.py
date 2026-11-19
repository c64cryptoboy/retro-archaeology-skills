"""Opt-in check.  Pass the c64-music-extraction skill directory as the only argument."""
import sys
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory

from chiptunesak_capture import capture, _capture_reviewed


def check(skill):
    sys.path.insert(0, str(skill))
    from trace_states import interpret

    source = skill / 'examples/glass-steps.sid'
    good, count = capture(source)
    assert count == 119
    # From the supplied assembly and its four pitches, not the importer's note rows.
    init = [(a, 0) for a in range(0xd418, 0xd3ff, -1)] + [(0xd405, 8), (0xd406, 163), (0xd418, 15)]
    def signature(rows):
        return [(r.phase, r.call, r.order, r.address, r.value) for r in rows]

    expected = [('init', -1, i, a, v) for i, (a, v) in enumerate(init)]
    for call in range(count):
        if call % 15 == 0:
            word = (6430, 7647, 5729, 9635)[call // 15 % 4]
            stores = [(0xd400, word & 255), (0xd401, word >> 8), (0xd404, 0x21)]
        elif call % 15 == 11:
            stores = [(0xd404, 0x20)]
        else:
            stores = []
        expected.extend(('play', call, i, a, v) for i, (a, v) in enumerate(stores))
    assert signature(good) == expected

    def decode(rows):
        return interpret('sid', ((r.tick, r.address, r.value) for r in rows),
                         clock_hz=1022727, tick_hz='1022727/17095', end_tick=count)['intervals']

    states = decode(good)
    edges = [(s['start_tick'], e['voice'], e['gate']) for s in states for e in s['gate_edges']]
    assert edges == [(start + delta, 1, on) for start in range(0, count, 15)
                     for delta, on in ((0, True), (11, False))]
    assert states[-1]['end_tick'] == count

    # Move the actual gate store before the two pitch stores.  Same addresses, values,
    # length, and end-of-call latches; a snapshot-only checker would accept it.
    wire = source.read_bytes()
    pitch = bytes.fromhex('bd 62 10 8d 00 d4 bd 66 10 8d 01 d4')
    gate = bytes.fromhex('a9 21 8d 04 d4')
    assert wire.count(pitch + gate) == 1
    wrong = wire.replace(pitch + gate, gate + pitch)
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / 'gate-too-early.sid'
        path.write_bytes(wrong)
        bad, n = _capture_reviewed(path, sha256(wrong).hexdigest())
    assert n == count and signature(bad) != expected
    changed = decode(bad)
    assert [(s['start_tick'], s['voices']) for s in changed] == [(s['start_tick'], s['voices']) for s in states]
    assert [states[0]['gate_edges'][0]['write_index'], changed[0]['gate_edges'][0]['write_index']] == [30, 28]
    print('PASS: 60 ordered writes, 16 gate edges; executed early gate rejected despite identical call-end voices.')


if __name__ == '__main__':
    if not __debug__ or len(sys.argv) != 2:
        sys.exit('usage: python -B check_glass_steps.py path/to/c64-music-extraction (without -O)')
    check(Path(sys.argv[1]).resolve())
