# Select a PSID song before init

Use `song_selection.py` when you need the song number, init accumulator, and initial interrupt source without loading the tune.  It reads only the fixed PSID header and does not call a player.  It is independent of the stricter `sidfile.py` reader/writer.

```sh
python3 -B song_selection.py input.sid            # use the header default
python3 -B song_selection.py input.sid --song 33  # explicit 1-based selection
```

```python
from song_selection import select_song

with open("input.sid", "rb") as stream:
    result = select_song(stream, song=33)  # omit song to use startSong
print(result["default"], result["selected"])
```

Both interfaces return the default and selected records (JSON on stdout for the CLI).  Each record contains the 1-based `song`, `init_a` (song minus one), `speed_bit_index` (zero-based, counted from the least significant bit), `speed_bit` (0 or 1), and `initial_source`.  A selected bit value of 0 means VBI; 1 means CIA 1 Timer A.  This is the header's initial setup, not a measurement of calls per second or a prediction of timer reprogramming.

| Fixed PSID header | Speed-bit index for songs above 32 |
|---|---|
| v1 (no flags word) | Repeat: `(song - 1) % 32`. |
| v2 through v4, PlaySID-specific flag set | Repeat as for v1.  This is bit 1 of the big-endian flags at `+76` hex, for features specific to Amiga PlaySID; bit 0 (MUS) is not this flag. |
| v2 through v4, PlaySID-specific flag clear | Keep using bit 31. |

For songs 1 through 32, all three use bit `song - 1`.  Song 33 distinguishes which bit is indexed (0 or 31), but it only distinguishes the resulting IRQ source if those two bits have different values.  A speed word of all ones cannot test the scheduling difference, however many songs the file contains.  Song 256 uses bit 31 in either case, with init A set to 255, not 31.

The helper checks magic, supported version, fixed offset, complete header, and song/default/request bounds.  It raises `ValueError` for invalid or unsupported selections; the CLI reports errors on stderr.  RSID (reserved speed field), PSID v5, and unknown versions are refused.  A header alone suffices: success says nothing about the payload, player, other flags, compatibility, or whether the file is playable.  Unselected speed bits are not validated.

Source: [HVSC SID File Format Description](https://www.hvsc.c64.org/download/C64Music/DOCUMENTS/SID_file_format.txt), 2026-10-09, fields `version`, `dataOffset`, `initAddress`, `songs`, `startSong`, `speed`, and `flags` bit 1.
