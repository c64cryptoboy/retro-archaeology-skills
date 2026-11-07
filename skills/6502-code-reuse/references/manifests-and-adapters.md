# Generic regions and platform adapters

## Manifest contract

`assets/region-manifest.schema.json` defines manifest version 1. `scripts/region_manifest.py` constructs and validates it.

A manifest contains one source artifact and one or more exact byte regions.

Required region fields:

- `id`: stable lowercase/hyphen identifier;
- `path`, `size`, `sha256`;
- `kind`;
- `scanByDefault`;
- `source`: provenance back to the source artifact.

Optional fields:

- `baseAddress`: CPU address corresponding to byte offset zero;
- `cpuProfile`: decoder hint;
- `knownMask`: same-size file where zero means unknown and nonzero means known.

`capture` may contain registers, banks, mapper state, or machine metadata. The core matcher does not require it.

## Region rules

- Keep mutually exclusive or overlapping banks separate.
- Do not count mirrors/current CPU views independently from their physical sources.
- Do not emit disk buffers, graphics blobs, or device state as CPU memory merely because the container stores them as hexadecimal bytes.
- Never scan a byte marked unknown by the known mask.
- An absent `baseAddress` means offsets are not claimed as CPU addresses.
- Preserve source offsets/module names/YAML paths so extraction can be audited.

## Raw binaries

`scripts/make_region_manifest6502.py` wraps one nonempty binary and optionally copies a known mask. Use separate manifests for two independent artifacts. For a multi-bank artifact, write a small adapter using `region_manifest.py` so all physical regions retain common source provenance.

## AppleWin YAML adapter

`scripts/extract_applewin_snapshot.py` parses the indentation and memory rows directly. AppleWin save states can repeat `Unit` keys, so ordinary YAML object loading can lose data.

The adapter recognizes CPU-memory map names such as:

- main memory;
- auxiliary memory banks;
- language-card memory;
- Saturn-style memory banks.

It inventories but does not emit unrelated hexadecimal blocks such as floppy track images as CPU memory.

Inspect the emitted CPU profile. An AppleWin capture may identify a 65C02 even when the cross-platform matcher intentionally uses only the shared official NMOS subset.

## VICE VSF adapter

`scripts/extract_vice_snapshot.py` structurally parses the VICE snapshot and emits the exact 64 KiB physical RAM payload from `C64MEM`, along with saved CPU-port and cartridge-line metadata.

Important distinction:

- `C64MEM` bytes are physical underlying RAM;
- bytes `$0000/$0001` in that payload are not necessarily the saved 6510 DDR/data registers;
- use emitted metadata for CPU-port state;
- ROM/I/O visibility at capture time does not change the identity of the extracted physical-RAM bytes.

Physical RAM can contain coherent code beneath ROM or I/O. Establish mapping/context during manual audit before claiming that code was CPU-visible or callable.

## Retro Debugger/Nestopia adapter

`scripts/extract_retro_nestopia_snapshot.py` requires both the saved state and the matching iNES ROM. It uses saved mapper state to describe the current CPU view and emits physical regions for ordinary matching:

- canonical 2 KiB CPU internal RAM;
- physical work RAM where supported;
- complete physical PRG ROM;
- current mirrored/banked CPU-visible reconstruction, disabled by default;
- a known-byte mask for the current view.

Prefer the complete physical PRG region over the current CPU view when searching all banks. The current view is useful for runtime address mapping, not independent evidence.

Snapshot and ROM hashes must match the intended capture set. Mapper support is bounded by the adapter implementation; reject unsupported states rather than inventing a mapping.

## Adding an adapter

An adapter may know a container format, but its output must remain generic:

1. parse structurally, with bounds checks;
2. preserve exact region bytes;
3. record artifact and region hashes;
4. emit physical, nonduplicated regions;
5. attach optional addresses and masks only when justified;
6. validate the completed manifest against its output files;
7. add synthetic parser tests without commercial assets.
