"""Export one Glass Steps loop from its executed SID gate rows, not a note table.

Optional: ChiptuneSAK and mido. This is a fixture-specific example, not a general
SID transcriber. The source has one simple voice and a known 60-field NTSC loop.
"""
import argparse
from math import log2
from pathlib import Path

from chiptunesak import SID
from mido import Message, MetaMessage, MidiFile, MidiTrack


def export_one_loop(path):
    sid = SID()
    sid.set_options(sid_in_filename=str(Path(__file__).with_name('glass-steps.sid')),
                    seconds=1.1, subtune=0, create_gate_off_notes=False,
                    assert_gate_on_new_note=False, always_include_freq=True, verbose=False)
    rows = sid.capture().rows
    if [r.play_call_num for r in rows[:61]] != list(range(61)):
        raise ValueError('expected 60 VBI calls plus the loop seam')
    # Choose 30 fields per written quarter; the time conversion, not this choice
    # of notation, determines actual seconds. A 6567R8 field = 263 * 65 cycles.
    midi = MidiFile(type=0, ticks_per_beat=960)
    track = MidiTrack()
    midi.tracks.append(track)
    track.append(MetaMessage('set_tempo', tempo=round(30 * 263 * 65 * 1000000 / 1022727)))
    track.append(Message('program_change', program=81))  # GM saw lead, not SID emulation
    active, last = None, 0
    for row in rows[:60]:
        channel = row.chips[0].channels[0]
        if channel.gate_on is None:
            continue  # unchanged, not a rest
        tick = 32 * row.play_call_num
        if channel.gate_on and active is None and channel.freq:
            # Map the actual 16-bit frequency word, not the arrangement's note list.
            hz = channel.freq * 1022727 / 2**24
            active = round(69 + 12 * log2(hz / 440))
            msg = Message('note_on', note=active, velocity=96)
        elif not channel.gate_on and active is not None:
            msg = Message('note_off', note=active, velocity=0)
            active = None
        else:
            raise ValueError('unexpected gate transition in the known example')
        track.append(msg.copy(time=tick - last))
        last = tick
    if active is not None:
        raise ValueError('expected a release before the loop end')
    track.append(MetaMessage('end_of_track', time=60 * 32 - last))
    with Path(path).open('xb') as f:
        midi.save(file=f)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('output', help='a NEW .mid file')
    export_one_loop(ap.parse_args().output)
