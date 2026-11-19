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

### What “identical” covers in a sparse reference

Before treating a byte comparison as a known positive, ask *whose address set was counted*.  At a fixed bank and stage, let `R` be the reference’s known addresses and `B` the candidate’s known addresses.  Report four disjoint counts: equal and different bytes in `R ∩ B`, missing `R − B`, and extra `B − R`.  Missing is not different, and extra is not a mismatch at a reference address.  If the intersection is empty, there are no compared bytes.  Do not turn an empty reference into a positive control.

Example: the reference knows `$4000=A9`, `$4001=01`, and `$4004=60`.  A candidate PRG loads `A9 01 DE AD 60` at `$4000`.  The counts `(equal, different, missing, extra)` are `(3,0,0,2)`: every known reference byte matches, but the two intervening bytes were never specified.  Truncating the PRG before `$4004` gives `(2,0,1,2)`; changing only `$4001` to `00` in the full candidate gives `(2,1,0,2)`.  Even `(3,0,0,0)` would establish equality only for the declared bytes and mapping, not file identity, reachability, or shared authorship.

Basis: [c64-re-tools `compareBuild` and `mergedPrograms`](https://github.com/henols/c64-re-tools/blob/2339d4aea09141af178263e7796fe875154c83d4/src/compare.ts).  Its segment check enumerates reference addresses; a true result does not assert absence of other candidate bytes.  Its merged reference uses the *last loaded byte* on overlap.  Use that rule only for a documented single load stage, not for mutually exclusive banks or an unknown load order.

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

The optional `capture.cpu` records the clock, A, X, Y, SP, PC, and status from the first 15 payload bytes of exactly one CPU module: [`MAINCPU` 1.4](https://github.com/VICE-Team/svn-mirror/blob/6ab477a19dc3c98742a6f1d923183fc4e4e1e7e0/vice/src/mainc64cpu.c#L883-L904) or [`MAINC64CPU` 1.5](https://github.com/VICE-Team/svn-mirror/blob/babcf716dcd7e8484dbe9ce9795bfb33e0a884ff/vice/src/mainc64cpu.c#L903-L924).  If neither name occurs, more than one module bears either name, the name/version pair is unsupported, or the prefix is short, `capture.cpu` is null.  This does not prevent extraction from an otherwise valid snapshot.  The adapter does not interpret the rest of the CPU payload.

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
- bank-bounded scan regions covering all physical PRG bytes once, plus the complete flat PRG file, disabled by default;
- current mirrored/banked CPU-visible reconstruction, disabled by default;
- a known-byte mask for the current view.

Use the scan regions for automatic matching.  Each region is one physical 8 KiB page, or consecutive pages witnessed together in one readable, consecutive CPU mapping in the snapshot.  Add a match's region offset to `source.prgOffset` for its flat PRG offset or to `source.fileOffset` for its iNES offset.  This partition can miss code spanning nonconsecutive physical pages or adjacencies in another mapper state; audit those separately.  The current CPU view is not independent evidence.  Re-extract older manifests that enabled the flat PRG by default.

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
