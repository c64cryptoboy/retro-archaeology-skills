# Find a gate from its printed bar

Use the full ledger to find where an original attack was written, or ask for one bar to see which gates enter it already held.  This optional Python 3 companion reads the engraver's **existing, matching** `gates.csv` and `plan.json`.  It writes CSV to standard output, needs only the standard library, and never reads MIDI or runs an engraver.

From the folder containing the companion, set `F` to the notation package's authored fixture.  For example, if installed beside `midi_score.py`:

```sh
F=fixture
python3 -B bar_locator.py "$F/engraved/gates.csv" "$F/plan.json" > editor-ledger.csv
python3 -B bar_locator.py "$F/engraved/gates.csv" "$F/plan.json" --bar 2
python3 -B check_bar_locator.py "$F"
```

Choose a **new** filename for redirected output, never an input.  Open that CSV in a spreadsheet or text editor.

- The full ledger has one row per source gate, in original order.  `source_gate` is the one-based **data record** in that gates CSV (header excluded), assigned before filtering or sorting.  It identifies the same gate in every view of that file; do not use it across reordered or regenerated inputs.  All original columns, including the absolute SMF ticks, key, wheel evidence, and printed mark, follow the addresses.
- `start_bar:start_offset_32nds` names the written attack; bars start at 1, and offsets count 32nds from 0.  `end_bar:end_offset_32nds` is the **exclusive stop in the last occupied bar**.  An exact barline stop is written as the preceding bar at its full length, including at the end of the score.  The lengths come directly from `bars_32nds`, not from a presumed meter.
- In a bar query, `[from_offset_32nds, until_offset_32nds)` is just the part on that page of the ledger.  The full gate addresses and performance ticks remain unchanged.  `carry-in` means a tie from an earlier bar, not another attack.  A gate ending at the left edge is absent; a gate starting there is an attack.  Results are ordered by local offset, then source record; a silent bar returns just the header.
- Written positions are editorial grid units.  `start_tick` and `end_tick` are absolute note-event positions in the **performance** SMF, not ticks of a quantized score MIDI, seconds, or evidence of acoustic onset or decay.  The locator neither snaps them again nor derives new pitches or times.

### What to expect in the authored two-bar study

| Bar 2 offsets (stop excluded) | Source gate | Track, MIDI key | Role | Absolute performance ticks (stop excluded) |
|---|---:|---|---|---|
| 0 to 8 | 3 | Reed, 67 | carry-in from bar 1, offset 24 | 1441 to 2401 |
| 4 to 16 | 6 | Low, 53 | attack | 2160 to 2880 |
| 12 to 20 | 4 | Reed, 69 | attack | 2640 to 3120 |

The first two Reed gates in bar 1 are both middle C.  Record 1 stops at offset 8, and record 2 attacks there; they are not tied.  The separate irregular-bar check counts lengths 3, 5, and 2 by hand.  A drone spanning all three bars ends at bar 3, offset 2, with no fictitious fourth bar.  Moving its release to bar 2, offset 5, removes it from the third-bar query entirely.
