# Shared offline 6502 helpers

These standard-library Python tools are shared dependencies of the analysis skills.  Keep this directory intact; its scripts import adjacent `analysis6502.py` and `dis6502.py`.  No installation, emulator connection, or agent harness is required.

Reuse and reduction import canonical modules here through small Python adapters, so those packages do not require filesystem symlinks.  Keep the repository layout intact.  The CPU implementation derives from ChiptuneSAK; preserve its in-file attribution and [MIT notice](CHIPTUNESAK_LICENSE.txt).

See [the disassembly workflow](../../skills/6502-disassembly/SKILL.md) for commands and evidence limits.  Most tools accept `--help`; the linear formatter supports it and uses `dis6502.py INPUT.prg [START] [COUNT]`.

The formatter stops at the end of supplied bytes.  An incomplete instruction shows only its available bytes and an `INCOMPLETE` marker, never a zero-filled operand or an invented `BRK`.  Its `fmt()` helper raises `ValueError` for missing operand bytes.  Both formatter and CFG reject a PRG whose linear load range extends past `$FFFF`; an exclusive end of `$10000` is valid.  Relative targets and CFG successors wrap as 16-bit CPU addresses, but missing instruction bytes are not fetched by wrapping around the image.  This does not model a wrapping loader, memory banking, or runtime execution.

Run the additive bounds controls with `python -B -m unittest discover -s tests -p 'test_disassembly_bounds.py' -v` from this directory.

`cfg6502.py` follows official NMOS opcodes from declared entries, records direct control/data references, and exposes unknown/truncated/indirect stops.  It does not resolve banking, automatically classify all bytes, or guarantee nonoverlapping instruction boundaries.  Treat the linear formatter and all-offset candidate scanners as inspection aids, never as proof of executable structure.

`decode-loop6502.py` is a bounded model of selected decoder-loop instructions, not a complete CPU emulator.  Its instruction-fetch guard prevents absent bytes in zero-filled backing RAM from being reported as an observed `BRK`:

- By default, only the PRG load range is admitted for execution.  This is a compatibility policy, not proof that every loaded byte is code.
- Repeated `--exec-range START:END` options **replace** that default with the union of the supplied half-open ranges (`END` is exclusive, up to `0x10000`).  They do not map memory or supply bytes.  To retain the original load range and add a destination, declare both.
- Every instruction byte must also have been supplied by the PRG or `--set ADDRESS=BYTE`.  `--set` alone does not grant executable status.  The full current instruction length is checked before decoding, tracing, or execution, including after JMP, taken branches, and fallthrough.
- Fetch stops use `outside_executable_ranges`, `unknown_instruction_byte`, or `instruction_fetch_outside_memory`, rather than `brk`.  `fetchStop` records the attempted PC, first rejected byte, offset, instruction length if the opcode was admitted, and preceding instruction (or `null` at entry).  Its `supplied` flag distinguishes a supplied but excluded byte from missing memory; `value` is the current simulated byte only when supplied, otherwise `null` (never an invented zero).  `executableRanges` records the admission policy.  A rejected fetch is not added to the trace or `instructionsExecuted`.  Legacy terminal and unsupported-opcode counting remains unchanged; a zero instruction budget reports zero attempts.
- Known, admitted `$00` still stops as `brk`; it is a simulator sentinel, not execution of interrupt/vector semantics.  Existing JSON keys remain, with `fetchStop` and `executableRanges` added.  Callers relying on implicit zero-filled code or complete JSON equality must update.
- In-place opcode and operand self-modification remains supported: fetches use current simulated memory and recheck the current length.  Stores do **not** make previously unsupplied bytes eligible for instruction fetch, even inside a declared executable range.  A generated destination must already be fully supplied and explicitly admitted if outside the default range; otherwise stop and capture its bytes for a separate run.

For example, if a three-byte PRG loaded at `$1000` jumps to `$2000`, an explicitly supplied external BRK is admitted with:

```sh
python decode-loop6502.py jump.prg --exec-range 0x1000:0x1003 --exec-range 0x2000:0x2001 --set 0x2000=0
```

This guard is an instruction-fetch evidence boundary, **not** RAM banking, automatic code classification, or dataflow taint analysis.  Data reads still use the original flat, zero-filled RAM model, and stores still update it; callers must supply all material input data and registers.  A supplied byte that is later overwritten is not independently proven correct by this guard.  This guard does not extend supported CPU instructions, decimal behavior, or hardware semantics.

Run the synthetic tests with `python -B -m unittest discover -s tests -p 'test_decode_loop6502.py' -v` from this directory.

`trace6502.py` summarizes supplied PC samples; it does not capture them.  Other scripts compare supplied images, inspect candidate data/pointers, and render analyst-maintained evidence.

Preserve input images and write derived evidence separately.  Hardware- or timing-dependent conclusions require a suitable emulator or physical-machine experiment.
