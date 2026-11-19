---
name: c64-graphics-extraction
description: Extract reusable Commodore 64 VIC-II sprites, character sets, and bitmap pictures from frozen stock C64 state, or assemble an evidenced sequence of linked sprites and bitmap updates into a timed animation. Use for native PNGs, contextual glyphs, sheets, reusable binaries, GIFs, and provenance. Distinguish art layers, completed poses, and historical raster frames.
---

# C64 graphics extraction

Use this skill when someone needs the artwork **and the bytes to reuse it**.  A screenshot preserves appearance, but cannot tell you which bytes supplied a sprite or whether an apparently black pixel was transparent.  This workflow reads the VIC-II's memory view and register state, then reports those distinctions explicitly.  It runs offline with Python 3.10 or newer and its standard library.  No agent, emulator, or image library is required for decoding.

## Try it

From this skill directory, run:

```sh
python3 example.py demo-input
python3 extract.py demo-input/capture.json demo-out --sheets --prg --asm
```

Open `demo-out/sprites.png`, then `slot0.png` and `slot1.png`: the two slots read **identical** source bytes but draw different dots.  `slot1-expanded.png` shows its horizontal expansion.  `screen.png` is the background plane; the sprites are intentionally separate.  Compare `slot0.bin` with `slot1.bin`; compare the slot entries in `manifest.json` to see why their previews differ.  Both commands take a new directory and refuse to replace an existing one.

## Capture contract

1. Identify the machine, capture instant, mapper, and physical versus CPU-mapped memory.  This profile is for a **stock, unexpanded C64 VIC-II mapping, without a cartridge**.  Do not treat a CPU-visible dump containing KERNAL ROM or I/O instead of underlying RAM as physical RAM.  A PAL/NTSC choice is not needed for these native asset dimensions; record the actual standard when comparing against a raster or timing a sequence.
2. Capture the physical RAM, VIC register file, **effective** CIA2 port A bank pins, and separate color RAM at the same instant.  If bank pins are inputs, the CIA output latch alone is not the effective value.  Supply the 4 KiB character-generator ROM if a requested VIC fetch crosses its window at `$1000` or `$9000`.  If the capture lacks that evidence, prefer a narrower, supported extraction over guessing.  See the [VIC mapping example](../c64-rom-reference/references/bitmap-beneath-rom.md).
3. For your own dumps, create a UTF-8 `capture.json` such as the following.  Addresses and register values in JSON are decimal integers.  File paths are relative to the descriptor, not the current directory.

```json
{"ram":"physical-64k.bin", "vic":"vic-64.bin", "cia2_pins":2, "color_ram":"colors.bin"}
```

| Field | Required evidence |
|---|---|
| `ram` | Exactly 65,536 bytes of physical RAM, **or** use `ram_segments` instead. |
| `ram_segments` | List of `{"address":24576,"file":"sprite-block.bin"}` objects for raw, nonoverlapping, address-qualified binaries.  Reads of unsupplied RAM refuse, including missing sprite padding.  A PRG's two-byte load header is not payload or proof of placement. |
| `vic` | Exactly 64 VIC register bytes in `$D000` order, not RAM underneath `$D000`. |
| `cia2_pins` | Effective CIA2 port A pins, or their low two bits.  Inversion selects the 16 KiB bank. |
| `color_ram` | 1,000 or 1,024 color RAM bytes in cell order.  Required for text and multicolor bitmap; not used for hires bitmap or sprites.  Only the low nibble supplies color. |
| `chargen` | Optional exact 4,096-byte ROM.  Supply the file explicitly; there is no guessed fallback to RAM or downloaded ROM. |

Use `--only sprites --slots 0 2` if only those pointer and sprite blocks are known, or `--only background` if sprite data is unavailable.  For example, in bank `$4000` with `$D018=$A4`, slot 0's pointer byte belongs at `$6BF8` (decimal 27640).  If that byte is `$80`, provide the full 64-byte block at `$6000` (24576).  Do not zero-fill unrelated memory and call it observed.  Use the example generator for an explicitly synthetic capture.  Never execute unknown input programs to extract their art.

## Import a VICE snapshot

The adapter imports stock, cartridge-free **x64sc snapshot files** (machine `C64SC`, file format 2.0).  It supports VICE **3.9.0.0**, and **3.10.0.0** only with revision field zero and VIC-II model 3 (NTSC MOS6567R8).  Use the emulator's snapshot-file writer, such as the monitor command `dump "game.vsf"`; a frontend's serialized state is not an alternative input contract.  Keep the sibling [6502 code-reuse skill](../6502-code-reuse/SKILL.md) in the repository layout:

```sh
python3 vice_capture.py game.vsf frozen-input
python3 extract.py frozen-input/capture.json art --sheets
```

The adapter writes physical RAM, VIC registers, color RAM, and a descriptor with the source snapshot hash, module versions, and payload offsets.  It derives only the two CIA2 bank pins; if either is an input, supply independently observed `--cia2-pins NUMBER`.  It verifies a stable matching VIC bank.  Add `--chargen FILE` at import if you need an external 4 KiB ROM; the adapter does not extract a bundled ROM.  Other versions, unverified layouts, cartridges, and expanded RAM are refused, not silently treated as stock.  Use a normalized capture instead when its inputs can be established independently.  Only the VICE adapter needs the sibling skill; the decoder and example do not.

## What to inspect and deliver

- **Text:** standard hires, multicolor character (including hires cells selected by color RAM), and extended-background-color text.  `screen.bin` preserves screen codes; `charset.bin` preserves the addressed 2,048-byte charset, or the 512 accessible bytes in extended-color mode.  `color.bin` preserves the 1,000 captured input bytes for the matrix.  Each used glyph/color context has its own PNG and list of cell indices.  With `--sheets`, `glyph-variants.png` shows those appearances, and `raw-glyph-bits.png` inventories the source patterns in black and white, including unused ones.  The latter is not a claim about displayed colors.
- **Bitmap:** standard hires and multicolor bitmap.  `bitmap.bin` contains 8,000 bytes in native cell order, not PNG scanline order.  `screen.bin` supplies the two per-cell color nibbles.  Multicolor additionally needs `color.bin` and `$D021`.  `screen.png` is a 320 × 200 opaque reconstruction of the background content; `background.idx` stores one VIC index per dot.  The display-enable bit, scroll values, and register snapshot are recorded, not applied as crop or border effects.
- **Editable Koala picture:** For a native multicolor bitmap, run `python3 extract.py capture.json art --only background --koala`.  Open `art/screen.koa` in a Koala-compatible editor.  This is the uncompressed 10,003-byte file: `$00 $60`, 8,000 bitmap bytes, 1,000 screen bytes, 1,000 color nibbles stored as bytes, and one background-color byte.  The `$6000` load address is a file convention, not evidence of the original VIC bank.  No pixels are requantized.  The separate raw blocks keep the capture bytes; the editor file does not include sprites, borders, or raster changes.  Hires and text are refused rather than silently converted.  See the [VICE Koala driver](https://github.com/libretro/vice-libretro/blob/76cde0b2cc4e52106618f2cc5d9d1112d9205c89/vice/src/gfxoutputdrv/koaladrv.c).
- **Editable Art Studio picture:** For a native hires bitmap, run `python3 extract.py capture.json art --only background --artstudio` and open `art/screen.art`.  The uncompressed 9,009-byte file uses a $2000 load prefix, the captured 8,000 bitmap bytes, 1,000 original screen bytes, and seven zero trailer bytes as in the [VICE Art Studio writer](https://github.com/libretro/vice-libretro/blob/76cde0b2cc4e52106618f2cc5d9d1112d9205c89/vice/src/gfxoutputdrv/artstudiodrv.c).  Unlike Koala it uses no color RAM or global background byte.  A set bitmap bit selects the high screen nibble, and a clear bit selects the low.  The prefix is an editor convention, not a capture address.  This is an asset export, not a screenshot with sprites or borders.
- **Behind-sprite priority:** `background-priority.bin` is separate from `background.idx` and `screen.png`.  It stores one foreground bit per native dot (320 × 200, packed MSB first, 40 bytes per scanline, no header).  Read `(plane[y * 40 + x // 8] >> (7 - x % 8)) & 1`: `1` denotes foreground in front of a behind sprite; `0` denotes background.  Hires character and bitmap dots use the original pattern bit.  Multicolor bitmap and multicolor character cells use the high bit of each two-bit selector for **both** dots: `00` and `01` are background; `10` and `11` are foreground, even if the colors match.  In multicolor text, cells with color RAM bit 3 clear use hires bits.  Extended-color text also uses hires bits: the upper two screen-code bits choose a background color, not a priority.  The API returns the packed bytes as `scene['background']['priority']`; the export manifest describes the file under `background.priority`.  This is a frozen content classification, not a composited frame or a collision result.  See [Bauer, §§3.7.3 and 3.8.2](https://www.cebix.net/VIC-Article.txt) and the [VICE selector and priority calculation](https://github.com/libretro/vice-libretro/blob/76cde0b2cc4e52106618f2cc5d9d1112d9205c89/vice/src/viciisc/vicii-draw-cycle.c#L160-L198).
- **Sprites:** each selected hardware slot exports `slotN.bin` (63 pattern bytes **and** its original alignment byte), `slotN.png` (24 × 21), and `slotN.idx` (row-major, 255 transparent, 0 opaque black).  Slot enable, mode, nine-bit X, Y, priority, colors, pointer, and expansion are in the manifest.  An expanded PNG is additional, never substituted for the native layer.  A disabled slot's PNG is clear even when its binary is nonblank.  A pointer is not proof of display.  `--sheets` adds `sprites.png`; sheet IDs are hexadecimal, and crop rectangles exclude the labels.
- **Reuse:** exact binaries and their logical VIC addresses, RAM/character-ROM source spans, lengths, hashes, and register evidence are in `manifest.json`.  The RGB palette is illustrative; native indices are authoritative.  `--prg` adds little-endian load headers only for wholly RAM-sourced blocks.  It does not load anything, select a bank, or make overwriting the original address safe.  `--asm` writes ca65 `.incbin` labels in `assets.inc`; choose segment placement yourself, and preserve 64-byte sprite alignment.  These are data, not a runnable program.  Preserve source capture provenance separately.

For a scripted analysis, import `State`, `decode`, and `export` from `extract` with this skill directory on the module search path.  `scene = decode(State.load('capture.json'), only='sprites', slots=[0, 1])` returns the native blocks and index planes without writing files.  The CLI uses that same decoder.

## Preview a static overlap

To see which dots the selected sprites would cover on the decoded background, run the optional [static compositor](static_composite.py) alongside the normal layer export.  For the original demo above:

```sh
python3 static_composite.py demo-input/capture.json demo-preview --offset -16 -32 --slots 1 0
```

Open `demo-preview/preview.png`; `preview.idx` holds 320 × 200 native indices, and `preview.json` records the placement.  The offsets here are illustrative, not a universal VIC origin.  For an observed scene, establish the registration independently: **asset coordinate = sprite register coordinate + offset**.  Supply both offsets and the intended slots explicitly.  The CLI shares the normal decoder and refuses to replace an existing directory.  From Python, call `static_composite(scene['background'], scene['sprites'], offset_x=dx, offset_y=dy)` for the same indices.

At each dot, the first opaque enabled sprite by slot number wins, even if foreground hides it.  Black is opaque; a transparent hole lets the next slot compete.  The preview respects expansion and clips to the decoded background.  It does not simulate borders, scrolling, collision latches, raster changes, or multiplexing.  Keep separate asset layers for reuse, and compare against actual video before claiming this is what the game displayed.

**If one sprite slot appears twice:** identify the field, and record the enable mask, X/Y, pointer, and color before each sprite fetch.  A late snapshot can correctly explain the lower sprite while missing the upper one entirely.  Compare both masks in one unmerged video field; if using an authored test, suppress just the second tuple write and check that only the second shape disappears.  Different captures that show the slot in different positions are not evidence that both positions appeared in one field.  [Replay a slot used twice](examples/two-bands/README.md) shows how to combine two complete appearances when the recorded tuples, clear gap, and common background support the join.

**If a picture changes partway down the screen:** Do not slide a guessed split until it matches the screenshot.  Record the register stores at their raster line and cycle on the identified VIC model, and check which matrix, charset, color RAM, and sprite bytes each band actually fetched.  A store before the first graphics fetch can describe a whole line; a later store may affect only part of it.  If the evidence supports two stable bands and a complete-line boundary, decode each state separately, use the same independent registration, and join the two native planes at `320 * first_lower_content_row`.  Check the transition row separately.  Compare both bands against withheld display pixels, and try the lower colors with the *old* charset as a control.  If the fetch boundary or source bytes are unknown, deliver the proven band and identify the rest as unresolved.  A successful two-band check is not a cycle-level VIC simulator.

If the picture moves but the screen codes and colors do not, capture character RAM for each pose.  [Night Watch: two eyes, one changing glyph](examples/night-watch/README.md) shows how writing eight bytes changes two screen cells at once.  Using a fixed charset misses the blink.

To put an exported sprite into a different game, see [Beacon Ferry: a playable import](examples/beacon-ferry/README.md).  It uses one 64-byte block in two slots and recomputes the pointer for the receiving VIC bank rather than copying the donor pointer.

## Recover and export an animation

A sprite pointer identifies a pattern, not a pose or the frame that comes next.  Trace the game’s pose table and timer, or observe a complete running cycle.  Record which slots draw each character together, their offsets from a common anchor, draw order, facing, and the exact point at which the sequence repeats.  Keep movement across the screen separate from motion within the pose.  A sheet sorted by memory address cannot establish playback order.

For a compressed bitmap, distinguish full redraws, positional **overwrites**, and XOR deltas using an actual decoder write over a nonzero destination.  A write of black is different from no write.  Carry untouched pixels forward, and retain complete storage rows even if verified padding is cropped for display.  Expand double-width logical pixels before applying a common crop and presentation scale.  Time the **completed** poses from the game’s scheduler: a delay byte can count groups of CIA interrupts, not video frames.  Preserve the final hold and loop target.  Quantize cumulative time boundaries only for the viewing format.

If the poses and their holds are still unknown, [recover a loop from displayed fields](references/discover-animation.md) before rendering: remove travel, retain local layer motion, and test the proposed period against the original picture.  Use `python3 animation.py sequence.json movie --gif` for an evidenced schedule, or call `export_animation(sequence_path, output_dir, gif=True)`.  The [animation recipe and schema](references/animation.md) include a runnable example.  Native index planes, copied source blocks, and PNGs require only Python; GIF encoding and decode-back checks require Pillow.  Compare a full loop against a separate code trace or observed capture.  A playable GIF shows what was exported, not that the original game played it that way.  To compare two registered loops without guessing which pose comes first, the [native phase comparison](phase/README.md) tests their full color planes, rational holds, and optional horizontal reflection, reporting every matching phase.

## Validate and stop

Compare one pointer, one boundary pixel, and one known mode/color change before making a visual claim.  Repack a hires sprite's opaque mask MSB first and compare the first 63 bytes; the 64th byte is storage, not a visible row.  Treat sprites as independent layers: priority, hardware coordinates, and expansion are not proof that a dot survived clipping or overlap.  In multicolor bitmap mode, pixel pairs `01` and `10` can have the same color while only `10` covers a behind-background sprite.  Keep the original selectors when determining visibility; neither the RGB picture nor the flattened color indices can distinguish these dots.  For overlapping sprites, find the lowest-numbered opaque slot at the dot **before** testing that slot against background priority.  If foreground hides it, the next sprite does not show through.  A transparent dot in that slot does let the next opaque slot compete.  This is a display-priority rule, not a collision-latch measurement.  A badline, multiplexed sprite, border trick, raster split, FLI display, or mid-frame bank change needs additional timed evidence.  This decoder does not composite a historical frame, discover packed disk assets, invent missing history, or infer animation.  Undocumented background mode combinations are refused.  For the implementation basis, see Christian Bauer's [VIC-II reference](https://www.cebix.net/VIC-Article.txt), especially the video matrix, display modes, and sprites.

Run the original synthetic regression cases with `python3 -B -m unittest discover -s tests -v`.
