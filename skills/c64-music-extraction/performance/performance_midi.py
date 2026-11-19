"""Write editable SMF Type 1 or legacy Type 0 from a monophonic voice ledger."""
import argparse
import json
import math
import struct
from pathlib import Path


# Fixed tempo: 500,000 us per quarter at 1000 PPQ gives 500 us per tick.
def _tick(us):
    return (_integer(us, 'time (us)', 0) + 250) // 500


def _integer(value, name, low, high=None):
    if type(value) is not int or value < low or (high is not None and value > high):
        raise ValueError(f'invalid {name}: {value!r}')
    return value


def _vlq(n):
    if not 0 <= n <= 0x0fffffff:
        raise ValueError('delta or length too large for an SMF VLQ')
    out = [n & 127]
    while n > 127:
        n >>= 7
        out.append(128 | (n & 127))
    return bytes(reversed(out))


def _bend(point, key, span):
    if ('hz' in point) == ('pitch' in point):
        raise ValueError('supply exactly one of pitch (absolute MIDI semitones) and hz')
    p = point.get('pitch', point.get('hz'))
    if type(p) not in (float, int) or not math.isfinite(p):
        raise ValueError('pitch must be finite')
    if 'hz' in point:
        if p <= 0:
            raise ValueError('hz must be positive')
        p = 69 + 12 * (math.log2(p) - math.log2(440))
    offset = p - key
    if abs(offset) > span + 1e-12:
        raise ValueError(f'pitch {p:g} outside bend range of key {key}')
    # MIDI center is 8192.  The positive rail is one LSB short of +span.
    return min(16383, max(0, 8192 + round(offset * 8192 / span)))


def _track_chunk(events, end_tick):
    # Stable order preserves off -> initial bend -> on at a shared tick.
    track = bytearray()
    previous = 0
    for tick, msg in sorted(events, key=lambda event: event[0]):
        track.extend(_vlq(tick - previous) + msg)
        previous = tick
    track.extend(_vlq(end_tick - previous) + b'\xff\x2f\x00')
    return struct.pack('>4sI', b'MTrk', len(track)) + track


def write_performance_midi(ledger, path, *, smf_type=0):
    """Use smf_type=1 for one named track per voice; the default preserves Type 0."""
    _integer(smf_type, 'smf_type', 0, 1)
    span = _integer(ledger['bend_range'], 'bend_range', 1, 127)
    end = _integer(ledger['end_us'], 'end_us', 0)
    tracks = []

    def start_track(name):
        if smf_type == 1:
            if not isinstance(name, str) or not name.strip():
                raise ValueError('track name must be a nonempty string')
            label = name.encode('utf-8')
            tracks.append([(0, b'\xff\x03' + _vlq(len(label)) + label)])
        elif not tracks:
            tracks.append([])  # Type 0 reuses this single track for every voice.
        return tracks[-1]

    def emit(us, message):
        events.append((_tick(us), bytes(message)))

    def bounds(note, previous_end):
        a = _integer(note['start_us'], 'start_us', 0, end)
        b = _integer(note['end_us'], 'note end_us', 0, end)
        if a < previous_end or _tick(a) >= _tick(b):
            raise ValueError('unordered, overlapping, or sub-tick note/noise span')
        return a, b

    events = start_track('Conductor')
    emit(0, b'\xff\x51\x03\x07\xa1\x20')  # Set Tempo
    channels = set()
    for voice in ledger['voices']:
        ch = _integer(voice['channel'], 'channel', 1, 16) - 1
        if ch == 9 or ch in channels:
            raise ValueError('each voice needs its own channel other than 10')
        channels.add(ch)
        events = start_track(voice.get('name', f'Channel {ch + 1}'))
        for cc, value in [(101, 0), (100, 0), (6, span), (38, 0), (101, 127), (100, 127)]:
            emit(0, [0xb0 | ch, cc, value])  # select RPN 0, set MSB/LSB, deselect
        previous_end = 0
        for note in voice['notes']:
            a, b = bounds(note, previous_end)
            key = _integer(note['key'], 'key', 0, 127)
            velocity = _integer(note.get('velocity', 80), 'velocity', 1, 127)
            curve = note['curve']
            if not curve or curve[0]['us'] != a:
                raise ValueError('first curve point must be at note start')
            previous_tick = -1
            for i, point in enumerate(curve):
                us = point['us']
                tick = _tick(us)
                if not previous_tick < tick < _tick(b):
                    raise ValueError('curve points need distinct ticks strictly before note end')
                bend = _bend(point, key, span)
                emit(us, [0xe0 | ch, bend & 127, bend >> 7])
                if i == 0:
                    emit(a, [0x90 | ch, key, velocity])
                previous_tick = tick
            emit(b, [0x80 | ch, key, 0])
            previous_end = b

    previous_end = 0
    noise = ledger.get('noise', [])
    if noise:
        events = start_track('Noise markers (optional GM surrogate)')
    for hit in noise:
        a, b = bounds(hit, previous_end)
        for us, label in [(a, b'noise:on'), (b, b'noise:off')]:
            emit(us, b'\xff\x06' + _vlq(len(label)) + label)
        if 'gm_key' in hit:  # explicit audition surrogate, never inferred from pitch
            key = _integer(hit['gm_key'], 'GM percussion key', 35, 81)
            emit(a, [0x99, key, 80])
            emit(b, [0x89, key, 0])
        previous_end = b

    header = struct.pack('>4sIHHH', b'MThd', 6, smf_type, len(tracks), 1000)
    end_tick = _tick(end)
    Path(path).write_bytes(header + b''.join(_track_chunk(t, end_tick) for t in tracks))


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('ledger', type=Path, help='UTF-8 JSON ledger')
    cli.add_argument('midi', type=Path, help='output .mid')
    cli.add_argument('--type', type=int, choices=(0, 1), default=0,
                     help='use 1 for editable voice tracks; default: 0 (legacy single track)')
    args = cli.parse_args()
    try:
        ledger = json.loads(args.ledger.read_text(encoding='utf-8'))
        write_performance_midi(ledger, args.midi, smf_type=args.type)
    except (KeyError, TypeError, ValueError, OSError) as exc:
        cli.exit(2, f'{cli.prog}: {exc}\n')


if __name__ == '__main__':
    main()
