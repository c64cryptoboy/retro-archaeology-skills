---
name: c64-rom-reference
description: Reference and verify hash-pinned stock C64 BASIC, KERNAL, character-generator, and 1541 DOS ROMs while analyzing C64 or 1541 6502 code. Use when resolving ROM calls, RAM workspace, C64 I/O registers, ROM offsets, revision-specific symbols, or stock 1541 DOS behavior.
---

# C64 ROM Reference

Use this skill as a revision-pinned local reference for C64 and 1541 analysis. It provides pinned ROM identities, local verification/acquisition tools, and concise symbol/workspace references; verify actual asset availability rather than assuming a package contains the bytes. Read the source and licensing-uncertainty notices; ROM binaries are not relicensed under the repository MIT license. A label or ROM convention is **not** proof of a program's behavior; confirm local control flow, data flow, banking, and runtime evidence.

## Official Microsoft BASIC source

Microsoft publishes the historical **Microsoft BASIC for 6502 Version 1.1** source under the MIT License:

- https://github.com/microsoft/BASIC-M6502

Use it as the preferred official source for Microsoft BASIC lineage, algorithms, original symbols, and comments. It includes the floating-point package and RND ancestor used by supported 6502 targets, including PET-oriented conditional code.

Do not mistake it for an exact source tree/build of the stock C64 BASIC V2 ROM, and do not call it the source of Commodore's separate KERNAL implementation. C64 BASIC V2 has later lineage and stores part of its BASIC implementation physically in the KERNAL ROM address range. Continue to verify claims against the pinned C64 ROM bytes and C64-specific control flow.

## ROM assets

**ROM images are not bundled.**  Supply lawfully obtained files with the names below in `assets/roms/`, or set `C64_ROM_DIR` to your own ROM directory.  Their source URLs, revisions, sizes, and expected SHA-256 values are listed in [the ROM manifest](references/rom-manifest.md).  Verify supplied assets before analysis.  No download occurs during verification or ordinary tool use.

If you explicitly choose network acquisition, run the downloader yourself from the skill directory after reviewing [source and licensing notes](references/SOURCES.md):

```bash
python3 scripts/download-roms.py
python3 scripts/rom-tool.py verify
```

The downloader verifies every source part and final image before an atomic install. Existing valid files are retained; invalid files refuse replacement unless `--replace-invalid` is supplied. Set `C64_ROM_DIR` or pass downloader `--output-dir` to use an external location.

Expected local filenames:

| ROM | CPU address range | Local file |
|---|---:|---|
| C64 BASIC V2 | `$A000-$BFFF` | `assets/roms/basic.bin` |
| C64 KERNAL revision 3 | `$E000-$FFFF` | `assets/roms/kernal.bin` |
| C64 character generator | `$D000-$DFFF` when character ROM is mapped | `assets/roms/chargen.bin` |
| 1541 DOS | `$C000-$FFFF` | `assets/roms/dos1541.bin` |

Run the helper before relying on an asset or converting addresses:

```bash
python3 scripts/rom-tool.py verify
python3 scripts/rom-tool.py offset kernal '$FFD2'
python3 scripts/rom-tool.py address dos1541 0x3fea
```

`offset` converts a CPU address to a zero-based file offset; `address` performs the inverse. Both reject addresses/offsets outside the selected image.

## Choose the relevant reference

Load only the files relevant to the question, **before interpreting the corresponding address/call**. First choose C64 versus drive CPU and establish mapping; do not read every symbol table for one call. If a local image fails verification, retain its actual hash/revision and stop applying this profile's internal symbols until compatibility is established:

- [BASIC ROM symbols (`$A000-$BFFF`)](references/basic-symbols.md) — BASIC parser, statements, variables, strings, floating-point internals, and official Microsoft source provenance. Its functional continuation at `$E000-$E39F` is intentionally in the KERNAL reference.
- [KERNAL ROM symbols (`$E000-$FFFF`)](references/kernal-symbols.md) — documented jump-table calls, screen editor, IRQ, IEC, tape, and system internals.
- [C64 BASIC/KERNAL RAM workspace](references/c64-rom-workspace.md) — zero page, pages 2/3, BASIC/KERNAL vectors, keyboard, screen editor, and cassette-buffer conventions.
- [C64 I/O symbols](references/c64-io-symbols.md) — 6510 banking, VIC-II, SID, color RAM, CIA, and expansion I/O.
- [1541 symbols and memory map](references/1541-symbols.md) — 1541 RAM, buffers, VIAs, DOS conventions, and ROM layout.
- [Construction sources and licensing status](references/SOURCES.md) — pinned citations, retained notices and explicit uncertainty where upstream reuse terms are unclear.

## Workflow

1. **Establish the CPU and mapping.** Distinguish C64 CPU code from drive CPU code. On C64, inspect `$0001` before treating `$A000-$BFFF`, `$D000-$DFFF`, or `$E000-$FFFF` as the corresponding ROM/I/O. On a 1541, identify the actual DOS ROM revision if internal addresses matter.
2. **Verify the local asset.** Run `rom-tool.py verify`; record a different ROM's revision/hash rather than applying this skill's internal labels to it.
3. **Resolve the narrowest relevant reference.** Prefer documented KERNAL jump-table entries over internal-address labels. For BASIC and 1541 internals, inspect required workspace and calling state.
4. **Use local evidence.** A ROM call or conventional RAM address is evidence, not a complete explanation. Track inputs, outputs, callers, banking, and overwritten vectors/workspace.
5. **Escalate appropriately.** Use the local ROM/reference for static understanding; use bounded simulation only with explicit modeled hooks; use a suitable debugger for hardware, timing, banking, or live-device validation.

## Interpretation rules

- Do not infer cassette activity solely from `$033C-$03FB`.
- Do not infer the visible screen from `$0288`; derive it from VIC/CIA state.
- Do not interpret `$D000-$DFFF` as I/O without checking banking.
- Do not assume an uploaded 1541 buffer is sector data or stock DOS code.
- Treat ROM-internal names as revision-specific and less stable than public KERNAL APIs.
