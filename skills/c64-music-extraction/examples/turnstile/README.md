# Turnstile: let BASIC play the tune

Open [Turnstile](turnstile.sid) in a BASIC-capable RSID player with C64 BASIC and KERNAL ROMs.  Song 1 opens **D4, A4, F4**, and answers **E4, G4, C4**.  Select song 2 to hear the answer first.  Both loop.  Use NTSC timing and one 8580 SID.

The [nine-line listing](turnstile.bas) is the entire player.  Line 20 reads the host's zero-based song number at decimal 780 (`$030C`); only song 2 skips the first three pitch/duration triples.  Each note sets a pitch, opens voice 1's triangle gate, waits in BASIC, and releases the gate.  The zero-duration sentinel rewinds the score.  Nothing calls a native init or play routine, and there is no IRQ player.

The [published SID format](https://www.hvsc.c64.org/download/C64Music/DOCUMENTS/SID_file_format.txt) defines flag bit 1 as BASIC **for RSID**, not for PSID.  Header load, init, play, and speed are zero; the little-endian load prefix after the 124-byte header is `01 08`.  The following linked BASIC lines belong at `$0801` for stock BASIC `RUN`, not `SYS 2049`.

To rebuild from the listing using only Python 3's standard library:

```sh
python3 build.py rebuilt.sid
cmp rebuilt.sid turnstile.sid
```

The original composition, BASIC source, builder, documentation, and generated RSID are [MIT licensed](LICENSE).  No ROMs or third-party tune data are included.
