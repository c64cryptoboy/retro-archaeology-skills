# Performance MIDI to reading score

Use `midi_score.py` when you have timed note gates **and evidence for a written grid**.  Keep the input SMF as the performance master.  The outputs are editable LilyPond source and a gate ledger; the optional engraver produces a PDF and a deliberately simplified MIDI of what was printed.  Do not substitute that MIDI for the input.

## Run the authored example

From this folder, with Python 3 and `mido==1.3.3`:

```sh
python midi_score.py fixture/performance.mid fixture/plan.json out
lilypond -dno-point-and-click -o out/score out/score.ly
python check_render.py out/score.midi fixture/expected.csv 64
python check_fixture.py
```

`check_fixture.py` uses a system LilyPond or the isolated PyPI `lilypond==2.24.3` binary wheel.  For example, create a temporary venv and install `mido==1.3.3 lilypond==2.24.3` there.  No engraver is needed to emit `.ly`.  The included two-bar `fixture/` was authored for this test, including its hand-written gate oracle.  `fixture/make_example.py` recreates its SMF.  Its off-grid held note survives a barline as one attack, its two adjacent middle Cs remain two attacks, and the second staff starts and finishes with rests.  The negative shortens only the first C and replaces the missing duration with silence.  Both scores compile; only the correct one matches the expected releases.

## Credit the selected subtune

Look up the exact collection path and **one-based song number** before printing credits.  In HVSC STIL, a numbered section’s `TITLE` and `ARTIST` may identify a covered recording; they do not establish the C64 arranger or transcriber.  Keep the SID header’s file-level author separate from STIL’s subtune `NAME` and `AUTHOR`.  If the selected song has no specific credit, use the file title and song number.  Do not borrow the next song’s title, or silently label a catalog identification as verified authorship.

## Supply an evidence-backed plan

- `anchors`: ordered `[absolute SMF tick, written 32nd-note index]` pairs, from `[0,0]` through the loop end, including final silence.  Two knots suffice for a uniform tempo/grid.  Use additional knots at documented clock changes or deviations you intend to normalize.  Between knots, snap **both endpoints** to the nearest integer unit, allowing only `tolerance_ticks` of performance error.  Collapsed or overlapping notes are refused.  This is not a tempo, key, or meter detector.
- `quarter_bpm` is the editorial quarter-note tempo, either a decimal string or an exact rational string.  `bars_32nds` partitions the full written duration into explicit measure lengths; no source time or key signature is inferred.  `title`, `subtitle`, optional `legend`, and optional `page_turn_after` (one-based bars) control presentation.  Printed spelling uses sharps.  Match the score tempo to a recurring pulse, not automatically to an SMF's transport quarter.
- `voices` lists note-bearing SMF track names in top-to-bottom staff order, exactly once each.  Supply `track`, `label`, `short`, and optionally `clef` (`treble`, `treble_8`, or `bass`).  A single noise lane may use `drum: "sn"` with GM key 38 as an explicit unpitched proxy.  Reattacks stay distinct; a single held gate split across notation values or bars is tied.  Gaps, including leading and trailing silence, become rests.
- `mark_wheel_span` optionally marks a gate with `*` if its maximum minus minimum wheel value reaches the supplied raw 14-bit unit threshold.  Derive this from the input bend range, and supply your own legend.  Start, extrema, and in-gate write count are recorded in `gates.csv`.  The exact contour, stationary detuning, expression, patches, and synthesis belong to the input MIDI, not the printed note.  Repeated marks are not new notes.
- Before choosing a straight grid, test the shortest group against the written score or tracker row boundaries.  Three evenly spaced attacks inside a beat can still total one correct beat after a bad snap: nearest straight sixteenths turn those thirds into a short, long, short pattern.  Compare the interior attacks and releases, not just the note count and barline.  Keep the performance MIDI unchanged and mark any unresolved tuplet for the editor.
- Scope: synchronous, PPQ-timed MIDI, with explicitly paired note gates, one channel per note track, distinct names, and no polyphony within a track.  Use separate tracks for simultaneous voices.  This is gate-duration notation, not pedal/acoustic sustain transcription, chords, tuplets, automatic voice separation, or unrestricted DAW import.  Tempo changes and controllers are not automatically interpreted as source notation.

## Locate a written note without engraving again

The [bar locator](bar-locator.md) looks up one printed bar in the existing gate ledger.  It keeps original performance MIDI ticks and identifies notes carried in from the preceding bar instead of listing them as new attacks.  It uses the actual bar lengths, including pickups and short bars.

## Optional independent importer

With [ChiptuneSAK](https://github.com/c64cryptoboy/ChiptuneSAK) importable in your environment, append `--check-chirp` to `midi_score.py` or `check_fixture.py`.  It invokes `MIDI().to_chirp(..., keyswitch=False, polyphony=True)` without quantization, and compares every track's pitch, start tick, and end tick to the primary reader.  The adapter uses normal Python discovery and has no machine-specific path.  ChiptuneSAK is MIT-licensed, copyright David Youd and contributors; no ChiptuneSAK code is bundled.  Its MIDI → Chirp → MChirp → LilyPond example is useful for ordinary metered scores.  This exporter uses the explicit clock, silent tail, noise proxy, and bend policy instead of accepting guessed metadata or flattening the performance.
