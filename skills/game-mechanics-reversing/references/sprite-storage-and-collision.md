# A sprite sheet is not a collision test

A VIC-II sprite uses 63 pattern bytes, but its pointer selects a **64-byte** block.  A loader can copy from tightly packed source records into aligned blocks at runtime.  Two previews of equal size, or even two correct hardware pointers, do not settle how the loader found its second source record.

Try the [original byte check](../scripts/check_sprite.py).  Start with a 127-byte zero-filled resource and set decimal offsets 0, 63, and 64 to $80, $80, and $40 respectively.  Copy 63 bytes for each of two hires sprites to $2000 and $2040.  Bank $0000 and pointer bytes $80 and $81 select those destinations in **both** interpretations.  Pattern zero has one opaque dot at (0,0).

| Step between source records | Start of second pattern | Opaque dots, relative to second sprite | Overlap at same origin |
|---|---|---|---|
| 63 bytes | 80 40 00 | (0,0), (9,0) | (0,0) |
| 64 bytes | 40 00 00 | (1,0) | none |

Establish the source increment from a loader, table, or observed copy.  Then establish the hardware setup.  With only these two sprites enabled, unexpanded, at the same visible position, stable pointers, and a cleared latch, the two alternatives predict sprite/sprite collision bits $03 versus $00 at $D01E after display.  Reading the register clears its latch.  These are predictions, not a raster capture.  A shielded player might lose no lives under either outcome.  To claim damage, find the game's read or software overlap test and follow the reachable state change.

Sources: [c64-re-tools sprite sheet](https://github.com/henols/c64-re-tools/blob/2339d4aea09141af178263e7796fe875154c83d4/src/graphics.ts#L82-L105) takes the source step as an argument; its [packed-input test](https://github.com/henols/c64-re-tools/blob/2339d4aea09141af178263e7796fe875154c83d4/src/graphics.test.ts#L22-L36) checks width, not the second sprite's dots.  For the hardware contract, see Christian Bauer's [VIC-II description](https://www.cebix.net/VIC-Article.txt), sections 3.8.1 and 3.8.2, and the [C64 I/O reference](../../c64-rom-reference/references/c64-io-symbols.md).
