# Night Watch: two eyes, one changing glyph

The owl blinks without changing a single screen code or color.  Both yellow eye cells contain code `1`.  When the VIC-II draws either cell, it fetches the same eight bytes from character RAM.  Change those bytes once and both eyes close together.

Load `night-watch.prg` on a stock NTSC C64 and enter `RUN`.  The 16 by 24 pixel owl sits near the center of the blue screen.  Reset to exit.  The 278-byte PRG contains its own art; it does not copy any character ROM.  To rebuild from `night-watch.s` with cc65 tools:

```sh
ca65 night-watch.s -o owl.o && ld65 -t none owl.o -o night-watch.prg
```

**What to inspect.**  The matrix starts at `$4400`.  The eye cells at `$45F3` and `$45F4` stay `01`, and the corresponding color RAM nibbles stay `7`.  The character set starts at `$4800`, so code `1` uses `$4808` through `$480F`, one byte per row, most significant bit on the left:

| Pose | Eight glyph rows (hex) | NTSC fields |
| --- | --- | ---: |
| Eyes open | `3C 7E E7 C3 C3 E7 7E 3C` | 32 |
| Eyes closed | `00 00 00 C3 66 3C 00 00` | 8 |

`patch` copies the rows after the visible area has been drawn.  `hold` counts raster-line-256 edges, not CPU delay loops.  In an offline MOS6567R8 run, fields 1 through 32 showed open eyes, fields 33 through 40 showed closed eyes, and field 41 returned to open.  At 65 cycles per line, 263 lines per field, and 1,022,730 cycles per second, the blink repeats about every 0.669 seconds.

**Extraction lesson.**  Decode the background separately with each pose's captured character RAM.  Keeping the first charset while decoding the closed pose produced 72 wrong pixels, 36 in each eye, even with the correct matrix, VIC registers, and color RAM.  This example uses ordinary high-resolution character mode throughout: no sprites, bitmap, or raster split.
