# When `$E2AB` is a bitmap byte, even though the CPU reads ROM

A pattern preview can tell you which dots a byte would select.  It cannot tell you that a VIC-II fetched the byte, or what colors reached the screen.  To annotate a candidate bitmap, keep the file offset, the CPU read mapping, and the VIC fetch address on separate lines.

## Follow one byte

Use an authored PRG containing the header `00 E0` and 8,000 data bytes.  All data bytes are zero except `$8D` at **file offset `$02AD`**, counting from zero.  For this example only, stipulate that the payload has already been copied unchanged into physical RAM at `$E000`.  The header is not part of that copy.

| View | Evidence and result |
|---|---|
| File image | `$02AD - 2 = $02AB` into the payload.  The nominal placement is `$E000 + $02AB = $E2AB`.  A load address is not a record of a load. |
| CPU read | On a stock C64 without a cartridge, with effective LORAM, HIRAM, and CHAREN all high, a CPU read at `$E2AB` returns a **KERNAL ROM** byte.  This read does not sample the RAM underneath.  No particular ROM byte value is needed. |
| VIC graphics fetch | CIA2 port A pins 1 and 0 are both driven low (`$DD02 & 3 = 3`, `$DD00 & 3 = 0`), selecting bank `$C000`.  `$D018 = $18` selects a matrix at bank offset `$0400` and a bitmap at offset `$2000`.  In this bank the VIC fetches **RAM**, not KERNAL ROM. |

Take dot `(40, 19)`, relative to the bitmap content, not the border or full raster.  Assume ordinary 40-column, 25-row bitmap display, starting at cell zero, with no splits or sprites.  The cell is `40 × (19 div 8) + (40 div 8) = 85 = $55`.  Within that cell this is row `19 mod 8 = 3`.  A graphics byte holds one row of one cell.  The next byte here is the next row of that cell, not the next group of eight dots to the right:

- Graphics fetch: `$2000 + 8 × $55 + 3 = $22AB` within the VIC bank, hence physical `$E2AB`.  It supplies the stipulated `$8D`.
- Matrix fetch: `$0400 + $55 = $0455` within the bank, hence physical `$C455`.  Stipulate that the byte there is `$A4`.
- Color RAM: nibble `$55` in a **separate store**, accessible to the CPU at `$D855` with I/O mapped.  Stipulate that it holds `$E`.  This is not main RAM at `$D855`, nor an offset to add to `$C000`.

## Predict eight dots, not a frame

With `$D011 = $3B` and `$D016 = $18`, this is multicolor bitmap mode.  Set background register `$D021 = $06`.  Read `$8D` from the most significant pair: `10 00 11 01`.  These are **selectors**, not C64 colors 2, 0, 3, and 1.

| Pair | Source | Color index |
|---|---|---|
| `10` | Matrix low nibble | 4 |
| `00` | `$D021` | 6 |
| `11` | Color RAM nibble | 14 |
| `01` | Matrix high nibble | 10 |

Each pair spans two dots.  The predicted color indices at x = 40 through 47, y = 19 are **`4 4 6 6 14 14 10 10`**.  Change only `$D016` to `$08`: standard bitmap mode uses single bits and just the two matrix nibbles.  The *same bytes at the same addresses* now predict **`10 4 4 4 10 10 4 10`**.  Alternatively, keep multicolor mode and drive CIA2's low pin pair to binary `10`: the graphics fetch moves to `$62AB`.  The fixture supplies no RAM there; the correct result is **unknown**, not black.

For a real annotation, record the provenance of the bytes and the effective bank, mode, and color state for the relevant fetches.  If all you have is the file, label the output **candidate bitmap pattern**, not a captured screen.  Even a matching screenshot proves what was rendered at that instant, not which address supplied it.  A single stopped register sample need not describe earlier raster lines.  None of these views alone establishes a map tile, a collision rule, or a game mechanic.

**Preview reference:** the pinned [c64-re-tools bitmap renderer](https://github.com/henols/c64-re-tools/blob/2339d4aea09141af178263e7796fe875154c83d4/src/graphics.ts#L107-L126) uses cell layout to draw a pattern; that alone does not supply live colors or mode.

**Check:** from the skill root, `python3 -I -B scripts/check_bitmap.py -v` runs the data-only example without a ROM or emulator.  **Hardware reference:** Christian Bauer, [The MOS 6567/6569 video controller (VIC-II) and its application in the Commodore 64](https://www.cebix.net/VIC-Article.txt), sections 2.4.1 and 2.4.2 (two address maps), and 3.7.3.3 and 3.7.3.4 (bitmap addressing and color selection).
