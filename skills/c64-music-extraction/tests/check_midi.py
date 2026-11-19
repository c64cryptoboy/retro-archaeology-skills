"""Reopen the gate-timed Glass Steps MIDI; oracle does not use the extractor."""
import sys

from mido import MidiFile


def check_midi(path):
    mf = MidiFile(path)
    if mf.type != 0 or mf.ticks_per_beat != 960:
        raise ValueError('expected single-track 960 PPQ example')
    tick, events, tempos = 0, [], []
    for msg in mf.tracks[0]:
        tick += msg.time
        if msg.type == 'note_on' and msg.velocity:
            events.append((tick, 'on', msg.note))
        elif msg.type in ('note_off', 'note_on'):
            events.append((tick, 'off', msg.note))
        elif msg.type == 'set_tempo':
            tempos.append((tick, msg.tempo))
    expected = []
    for i, key in enumerate([67, 70, 65, 74]):
        expected.extend([(i * 480, 'on', key), (i * 480 + 352, 'off', key)])
    if events != expected or tick != 1920 or not tempos or len(tempos) != 1 or tempos[0][0] != 0:
        raise ValueError('pitch, edge, tempo count, or final-rest mismatch')
    if abs(mf.length - 60 * 17095 / 1022727) > 0.000001:
        raise ValueError('loop elapsed-time mismatch')
    print(f'4 keys, 8 edges, 128-tick final rest, {mf.length:.6f} s: OK')


if __name__ == '__main__':
    check_midi(sys.argv[1])
