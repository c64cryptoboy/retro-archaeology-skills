"""Authored two-bar fixture; no game-derived material.  One 32nd = 60 SMF ticks."""
from pathlib import Path
import mido

HERE = Path(__file__).resolve().parent
smf = mido.MidiFile(type=1, ticks_per_beat=480)
meta = smf.add_track('Clock')
meta.append(mido.MetaMessage('set_tempo', tempo=600000))
meta.append(mido.MetaMessage('end_of_track', time=3840))
for channel, name, gates in [
    (0, 'Reed', [(0,480,60), (480,960,60), (1441,2401,67), (2640,3120,69)]),
    (1, 'Low', [(240,1200,48), (2160,2880,53)])]:
    track = smf.add_track(name)
    events = []
    for a,b,k in gates:
        events.extend([(a,mido.Message('note_on', channel=channel, note=k, velocity=90)),
                       (b,mido.Message('note_off', channel=channel, note=k, velocity=0))])
    if channel == 0:
        events.extend([(1800,mido.Message('pitchwheel', channel=0, pitch=4096)),
                       (2300,mido.Message('pitchwheel', channel=0, pitch=0))])
    tick = 0
    for t, msg in sorted(events, key=lambda pair:pair[0]):
        track.append(msg.copy(time=t-tick)); tick=t
    track.append(mido.MetaMessage('end_of_track', time=3840-tick))
smf.save(HERE/'performance.mid')
