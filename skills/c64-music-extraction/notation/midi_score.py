"""Make a reading score from gated monophonic SMF tracks and an explicit grid."""
import argparse
from bisect import bisect_left
import csv
from fractions import Fraction
import json
from pathlib import Path

import mido


def read_lanes(path):
    smf = mido.MidiFile(path)
    if smf.type not in (0, 1) or smf.ticks_per_beat <= 0:
        raise ValueError('expected synchronous PPQ MIDI')
    lanes, ends = {}, []
    for track in smf.tracks:
        tick = wheel = 0
        active = channel = None
        notes = []
        for msg in track:
            tick += msg.time
            if hasattr(msg, 'channel'):
                if channel is not None and msg.channel != channel:
                    raise ValueError('split channels into separate tracks first')
                channel = msg.channel
            if msg.type == 'pitchwheel':
                wheel = msg.pitch
                if active is not None:
                    active['wheels'].append(wheel)
            elif msg.type == 'note_on' and msg.velocity:
                if active is not None:
                    raise ValueError('overlapping gates: separate voices before engraving')
                active = dict(start_tick=tick, key=msg.note, wheels=[wheel])
            elif msg.type in ('note_off', 'note_on'):
                if active is None or active['key'] != msg.note or active['start_tick'] >= tick:
                    raise ValueError('unmatched or zero-length gate')
                active.update(end_tick=tick)
                notes.append(active)
                active = None
        if active is not None:
            raise ValueError('unterminated gate')
        if notes:
            if not track.name or track.name in lanes:
                raise ValueError('note tracks must have unique names')
            lanes[track.name] = notes
        ends.append(tick)
    return lanes, max(ends)


def check_chirp(path, lanes):
    # Optional independent tick-level check; do not accept guessed quantization,
    # key, meter, dropped low notes, or flattened polyphony from any adapter.
    from chiptunesak import MIDI
    song = MIDI().to_chirp(str(path), keyswitch=False, polyphony=True)
    imported = {track.name: [(n.start_time, n.start_time + n.duration, n.note_num)
                             for n in track.notes] for track in song.tracks}
    expected = {name: [(n['start_tick'], n['end_tick'], n['key']) for n in notes]
                for name, notes in lanes.items()}
    if imported != expected:
        raise ValueError('Chirp import disagrees on performance note identity or duration')


def grid_mapper(anchors, end_tick, tolerance):
    ticks, units = zip(*anchors)
    if (anchors[0] != [0, 0] or ticks[-1] != end_tick or len(anchors) < 2 or tolerance < 0
            or any(b <= a for seq in (ticks, units) for a, b in zip(seq, seq[1:]))):
        raise ValueError('expected increasing [SMF tick, 32nd index] knots spanning the performance')

    def snap(tick):
        i = max(1, bisect_left(ticks, tick))
        x, y = ticks[i-1], units[i-1]
        step = Fraction(ticks[i]-x, units[i]-y)
        unit = y + round((tick-x)/step)
        if abs(tick - (x+(unit-y)*step)) > tolerance:
            raise ValueError(f'tick {tick} is not on the supplied grid within {tolerance} ticks')
        return unit
    return snap


def lp_string(value):
    return '"' + value.replace('\\', '\\\\').replace('"', '\\"').replace('\n', ' ') + '"'


def pitch(key):
    name = 'c cis d dis e f fis g gis a ais b'.split()[key % 12]
    marks = key // 12 - 4  # MIDI 60 is c' (middle C).
    return name + ("'" * marks if marks >= 0 else ',' * -marks)


# Whole, dotted, and undotted values down to the minimum written unit.
DUR = [(48,'1.'), (32,'1'), (24,'2.'), (16,'2'), (12,'4.'), (8,'4'),
       (6,'8.'), (4,'8'), (3,'16.'), (2,'16'), (1,'32')]


def bar_tokens(events, start, length):
    end = start + length
    bar = []
    for a, b, symbol, mark in events:
        lo, hi = max(a, start), min(b, end)
        if hi <= lo:
            continue
        if symbol == 'r' and lo == start and hi == end:
            bar.append(f'R1*{length}/32')
            continue
        while lo < hi:
            # Syncopations crossing a beat from a weak subdivision are tied
            # to the next beat; do not rearticulate a held source event.
            span = hi - lo
            off = (lo-start) % 8
            if off and span > 8-off:
                span = 8-off
            units, dur = next(p for p in DUR if p[0] <= span)
            token = symbol + dur
            if lo == a and mark:
                token += '^\\markup \\tiny ' + lp_string(mark)
            lo += units
            if symbol != 'r' and lo < b:
                token += '~'
            bar.append(token)
    return ' '.join(bar)


def engrave(smf, plan, out, chirp=False):
    p = json.loads(Path(plan).read_text())
    lanes, end_tick = read_lanes(smf)
    if chirp:
        check_chirp(smf, lanes)
    specs = p['voices']
    if len(specs) != len(lanes) or {s['track'] for s in specs} != set(lanes):
        raise ValueError('plan must account for every note track exactly once')
    snap = grid_mapper(p['anchors'], end_tick, p['tolerance_ticks'])
    bars = p['bars_32nds']
    if not bars or min(bars) < 1 or sum(bars) != snap(end_tick):
        raise ValueError('bar plan does not cover the loop, including final silence')
    bpm = Fraction(p['quarter_bpm'])
    if bpm <= 0:
        raise ValueError('quarter_bpm must be positive')
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    lines = ['\\version "2.24.0"', '#(set-global-staff-size 16)', '\\header {',
             '  title = ' + lp_string(p['title']), '  subtitle = ' + lp_string(p['subtitle']),
             '  subsubtitle = ' + lp_string(p.get('legend', '')), '  tagline = ##f', '}', '\\paper { indent = 15\\mm short-indent = 9\\mm }',
             '\\score {', '  <<']
    audit = []
    for index, spec in enumerate(specs):
        track = spec['track']
        drum = spec.get('drum')
        clef = spec.get('clef', 'treble')
        if clef not in ('bass','treble','treble_8') or (drum is not None and drum != 'sn'):
            raise ValueError('supported staves: treble, octave treble, bass, or snare proxy')
        staff = 'DrumStaff' if drum else 'Staff'
        lines.extend([f'    \\new {staff} \\with {{',
                      '      instrumentName = ' + lp_string(spec['label']),
                      '      shortInstrumentName = ' + lp_string(spec['short'])])
        if drum:
            lines.extend(['      \\RemoveAllEmptyStaves', '      \\override StaffSymbol.line-count = #1',
                          "      drumStyleTable = #(alist->hash-table '((snare cross #f 0)))"])
        lines.extend(['    } ' + ('\\drummode ' if drum else '') + '{',
                      '      \\omit Staff.TimeSignature'])
        if not drum:
            lines.append('      \\clef ' + lp_string(clef))
        if index == 0:
            tempo = bpm/4
            lines += [f'      \\tempo \\markup {{ "Editorial quarter = {float(bpm):.2f} BPM" }}',
                      f'      \\set Score.tempoWholesPerMinute = #(ly:make-moment {tempo.numerator} {tempo.denominator})']
        events = []
        tail = 0
        for n in lanes[track]:
            a, b = snap(n['start_tick']), snap(n['end_tick'])
            if a < tail or b <= a:
                raise ValueError('quantization collapsed or overlapped a gate')
            if drum and n['key'] != 38:
                raise ValueError('snare proxy requires GM key 38')
            wheels = n['wheels']
            span = max(wheels)-min(wheels)
            threshold = spec.get('mark_wheel_span')
            mark = '*' if threshold is not None and span and span >= threshold else ''
            if a > tail:
                events.append((tail, a, 'r', ''))
            events.append((a, b, drum or pitch(n['key']), mark))
            audit.append(dict(track=track, key=n['key'], start_tick=n['start_tick'], end_tick=n['end_tick'],
                              start_32nd=a, end_32nd=b, wheel_start=wheels[0], wheel_min=min(wheels),
                              wheel_max=max(wheels), wheel_writes_in_gate=len(wheels)-1, printed=mark))
            tail = b
        if tail < sum(bars):
            events.append((tail, sum(bars), 'r', ''))
        start = 0
        for i, length in enumerate(bars):
            if not i or length != bars[i-1]:
                lines.append(f'      \\set Timing.measureLength = #(ly:make-moment {length} 32)')
            lines.append(f'      {bar_tokens(events, start, length)} | % {i+1}')
            if not index and i+1 in p.get('page_turn_after', []):
                lines.append('      \\pageBreak')
            start += length
        lines += ['      \\bar "|."', '    }']
    lines += ['  >>', '  \\layout { }', '  \\midi { }', '}', '']
    (out/'score.ly').write_text('\n'.join(lines), encoding='utf-8')
    with (out/'gates.csv').open('w', newline='') as f:
        writer = csv.DictWriter(f, audit[0].keys(), lineterminator='\n')
        writer.writeheader()
        writer.writerows(audit)
    print(f'{len(audit)} gates, {len(bars)} editorial bars, {sum(bars)} written 32nds' +
          ('; ChiptuneSAK exact tick/gate cross-check passed' if chirp else ''))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('midi', type=Path)
    parser.add_argument('plan', type=Path)
    parser.add_argument('out', type=Path)
    parser.add_argument('--check-chirp', action='store_true')
    args = parser.parse_args()
    engrave(args.midi, args.plan, args.out, args.check_chirp)
