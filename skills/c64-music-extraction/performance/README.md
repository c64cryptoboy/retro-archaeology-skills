# Performance MIDI from a voice ledger

Use this writer when an extractor can tell you **which attacks and releases occurred**, and where the sounding pitch moved between them.  It preserves those decisions as notes and channel pitch bends.  It does not open SID files, infer notes from a frequency trace, or guess a tempo from call counts.

**Play the original example:** [Lantern Relay](examples/lantern-relay.mid), a four-second miniature in two voices.  The treble C bends upward without a second strike; the bass bends downward underneath it.  At 0.750 seconds the treble really does strike C again.  A single optional hi-hat punctuates the opening.  After the final C releases at 3.500 seconds, the file keeps half a second of rest.  The [authored ledger](examples/lantern-relay.json) is synthetic, not a recovered tune.

### Use

For an **editable SID MIDI**, use Type 1: a conductor track holds the tempo, and each supplied physical voice gets its own named track and independent MIDI channel.  Voices stay separate even when silent or playing in unison.  From this directory, with Python 3 and no extra dependencies:

```sh
python3 performance_midi.py --type 1 examples/lantern-relay.json editable.mid
python3 -B -m unittest discover -s tests -v
```

Or import the same writer and pass a decoded dictionary and an output path:

```python
import json
from pathlib import Path
from performance_midi import write_performance_midi

ledger = json.loads(Path('examples/lantern-relay.json').read_text())
write_performance_midi(ledger, 'editable.mid', smf_type=1)
```

For legacy single-track Type 0, omit `--type 1` or call `write_performance_midi(ledger, path)` as before.  This is the format of the bundled MIDI fixture, not the editable master.

### Supply the evidence, not just the notes

- Use **absolute integer microseconds from one origin** for every `start_us`, `end_us`, and curve `us`.  When the source clock varies, convert each measured absolute position, not a count times the average interval.  Record the clock, origin, observation granularity, note-boundary evidence, and any editorial decisions alongside the ledger.
- `voices` is a list of monophonic voices.  Each has its own human-numbered `channel` (1 through 16, except 10) and a time-ordered `notes` list.  A note is a half-open interval `[start_us, end_us)`; adjacent intervals with the same `key` explicitly request a reattack.  Intervals on one channel cannot overlap.  `key` is an integer MIDI note (0 through 127); `velocity` is optional (1 through 127, default 80).
- For a hardware transcription, supply every physical voice in ledger order.  Set `name` to a nonblank string identifying the chip and local voice, for example `{"name": "SID 2 voice 1", "channel": 4, "notes": []}` for a silent voice.  Type 1 writes the supplied name as UTF-8; if omitted, the label is `Channel N`.  A channel number alone does not establish hardware identity.
- Each note requires a `curve` with a point at its start.  A point has `us` and **one** of `pitch` (absolute fractional MIDI note) or `hz` (positive frequency, 12-tone equal temperament with A4 = 440 Hz).  Each value is **held until the next point or release**, not interpolated.  Add points for evidenced slides or vibrato; an unchanged held pitch needs no repeated points.  A bend is relative to the explicit key, including at onset.  An out-of-range bend is rejected, never made into a new note.
- `bend_range` is the integer semitone range in either direction (1 through 127).  At tick zero, each pitched channel selects pitch-bend sensitivity RPN 0, writes the semitones and zero cents, and deselects the RPN.  Bends use the 14-bit wheel; center is 8192, and the positive limit is one unit short of full scale.  A player must honor the RPN for nondefault ranges to sound right.  No program, chip instrument, or synthesizer configuration is imposed.
- Optional `noise` is a separate, time-ordered list of nonoverlapping spans.  Each writes `noise:on` and `noise:off` SMF text markers, which alone are silent.  Add `gm_key` (35 through 81) **only** to request an audition surrogate on General MIDI percussion channel 10.  In Type 1 the markers and any GM notes go on a separately labeled noise track, never in place of a physical voice track.  A GM hi-hat or snare is not oscillator noise; a player may ignore its note-off or lack a GM kit.
- Top-level `end_us` is the end-of-track boundary, including trailing rest.  Every note/noise span must have its own end by then; the writer does not invent releases.  The optional ledger `title` is for the reader.  Extractor provenance and annotations can stay in the ledger or a sidecar; they are not exported as music.

### Timing and limits

Both formats keep the same elapsed timeline, including the final rest on every track, with a constant 500,000 µs/quarter and 1,000 ticks/quarter.  The tempo is a time ruler, not inferred meter.  Each absolute time is rounded to the nearest 500 µs tick (ties up), so rounding does not accumulate.  A gap shorter than one tick can disappear.  A note/noise duration that collapses, or a pitch update indistinguishable in ticks from its predecessor or release, is rejected.  At a shared tick on one voice the order is old note-off, new initial bend, new note-on.  Curves never emit note attacks after the initial point.  Use separate voices for simultaneous independent bends; there are at most 15 pitched channels.

### Compare what a listener will actually play

Render the delivered MIDI file through a named synth and sound bank, not just a sine-wave model of its input ledger.  Record the MIDI hash, bank, and synth settings; check that a large bend actually spans the requested interval in the audio.  Keep an unmodified render of the source chip.  Estimate one time offset from transitions across the piece, then leave it fixed.  Choose steady one-voice and two-voice windows before examining their spectra, and repeat the comparison at a deliberately wrong offset.  Count an obscured second pitch as inconclusive rather than moving the window or accepting its octave.  Report timing, pitch, and timbre separately: close pitches do not make two instruments sound alike.

This is a MIDI performance approximation, not SID/TED emulation, audio validation, notation, ADSR, PWM, filter, or waveform recovery.  Final silence means no active MIDI keys or noise spans until end-of-track, not zero PCM on a synth with release or reverb tails.  The tests read back actual MIDI bytes using a separate test parser and an independently scored tick ledger.  A missing held pitch fails even when every note onset and release is intact.
