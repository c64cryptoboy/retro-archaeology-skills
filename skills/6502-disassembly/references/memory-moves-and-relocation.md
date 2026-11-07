# Memory moves and runtime relocation

Startup copies can place executable bytes at addresses where they did not exist in the loaded image.  Recovering that mapping makes control flow and cross-references meaningful; disassembling only the original file can miss the program or decode stale destination bytes.

> Read [SKILL.md](../SKILL.md) first.  Use this procedure when a copy, relocation, or overlay affects the region under analysis, including moves later in execution.  It is an evidence workflow using existing tools, not an automatic mover or packer recognizer.  Stop when the scoped move and its handoff are explained; do not unpack an entire game by default.

## Distinguish the operation

- **Copy/move:** reproduce bytes in another location, possibly with overlap.  This includes code, tables, graphics, or a mixture; a copy alone does not establish executable code.
- **Address relocation/fixups:** change address operands or pointers for a new execution location.  A plain copy need not perform fixups: its payload may already have been assembled for the destination, be position-independent, or retain deliberate references to unmoved code/data.
- **Deobfuscation:** transform the stored representation, such as XOR decoding.  It may also copy the output elsewhere.
- **Decompression:** reconstruct a packed representation, potentially using literals, runs, or back-references.  Copy loops inside a decompressor are not evidence that the whole operation is a plain move.  Size change alone does not identify compression.

Operations can be chained.  Treat copying, decoding, and address patching as distinct stages when their intermediate bytes matter.  For transforms, use [dynamic-code-and-traces.md](dynamic-code-and-traces.md); this procedure does not add general cracked-game decompression support.

## Bounded workflow

1. **Find the writer and its inputs.**  Follow the evidenced startup/loader path.  Look for load/store loops using indexed absolute addresses or zero-page pointers, page loops, patched load/store operands, stack-mediated transfers, or calls to established copy routines.  Trace effective addresses and the values reaching stores.  A constant fill, screen update, or arbitrary store is not automatically a code move.
2. **Derive exact semantics.**  Record source, destination, byte count, copy direction/order, loop exit, and required registers, pointers, flags, and memory mapping.  Resolve page counters, partial final pages, and address/index wraparound.  For a loop that copies before incrementing an initially zero index and stops when that index returns to zero, the count is 256, not zero.  With overlap, reproduce the actual read/write order: later reads can see earlier writes.  Do not substitute a host slice copy or `memmove` assumption.  Check whether the mover overwrites its own instructions or pointers before their last use.
3. **Keep a stage-aware map.**  Record file/container offset when known, source address and bank/read view, destination address and bank/write view, and the stage in which each is valid.  Distinguish CPU-visible ROM/I/O from underlying RAM and later banking changes.  Track ordered moves, overlays, and subsequent patches separately; the same CPU address can denote different bytes at different times.  Preserve originals and identify/hash each derived image or capture.  A relocated PRG header is only an analysis container, not evidence that the original loaded there.
4. **Recover only the needed output.**  Use static reconstruction when the loop, bytes, state, and mapping determine the result.  Otherwise state the uncertainty and take the smallest authorized before/after capture, with a finite stop condition.  Prefer a stop after the last relevant write and before the destination's first execution or mutation.  Watch the writer or handoff if that boundary is unknown.  Capture destination bytes even when a write leaves their values unchanged; a changed-byte diff is not write coverage.  Do not force the PC past initialization and call that the normal execution path.
5. **Resolve the handoff and fixups.**  Establish how execution reaches the destination: direct/indirect jump or call, fall-through, patched vector, interrupt, or stack/return mechanism.  Track address patches independently from the copy.  Do not add the relocation delta to every numeric word: hardware/ROM references and deliberately unmoved data remain at their own addresses.  Relative branches preserve their destinations relative to the block only when both endpoints move together without layout changes.
6. **Analyze the correct runtime image.**  Disassemble at the destination address from the evidenced handoff and other established entries.  Keep source-storage provenance, runtime xrefs, and remaining code/data gaps.  Stored code can be loader data before it becomes executable at the destination.  Do not mark every copied byte as code, discard the loader, or merge incompatible overlay CFGs.  A jump into a destination that the original file did not supply or that a writer has changed is an open runtime-image edge, not permission to follow stale file bytes.
7. **Close the scoped move.**  Check the complete relevant destination span against the predicted output or capture, including count, endpoints, overlap effects, and any fixups.  Record whether this is statically derived, simulated under explicit assumptions, or observed on a particular execution.  Retain unresolved banks, entries, stages, and unsupported semantics as open items.  One successful handoff is not a full-program execution claim.

## Existing helper limits

`decode-loop6502.py` in [the shared helpers](../../../shared/6502/) can simulate supported flat-RAM copy loops with explicit initial state and a conservative instruction bound.  It is not a banked-machine, interrupt, ROM-call, or complete CPU emulator.  Missing data reads can use its zero-initialized backing RAM: supply all material input bytes; a successful stop does not establish their provenance.

Use executable admission to stop at the handoff rather than inadvertently executing the payload.  The helper does not promote newly written, previously unsupplied bytes into instruction-fetch evidence.  An `outside_executable_ranges` stop can be the intended boundary only when its reported PC and preceding control flow establish that the copy finished; an instruction-limit or unsupported-opcode stop is not completion.  A bounded trace can be truncated independently of execution.

Its `--output-prg` writes only the original PRG load span, which can omit a moved destination.  Its `changes` lists value differences, not every write or every output byte.  Reconstruct the complete destination from the known initial memory plus changes, or take an explicit mapped capture, before starting a destination CFG.  Do not broaden executable ranges merely to suppress a refusal.

## Small synthetic example

Assume flat RAM, no interfering interrupts, known source bytes, and this mover at `$0800`:

```asm
        LDY #$00
copy:   LDA $3000,Y
        STA $4000,Y
        INY
        BNE copy
        JMP $4000
```

It copies 256 bytes upward from `$3000` through `$30FF` to `$4000` through `$40FF`, then transfers control to `$4000`.  The ranges do not overlap.  If the stored first four bytes are `20 30 40 60`, the destination begins `JSR $4030; RTS`.  That call already names a runtime destination; it does not need an automatic `$1000` operand adjustment.  The bytes at destination `$4030` still need to be supplied and analyzed.  Source `$3000` and destination `$4000` are distinct provenance/execution coordinates, not interchangeable labels.

## Minimal handoff record

For each relevant stage, retain:

- input/capture identity and known-state assumptions;
- mover entry and evidence for reachability;
- source-to-destination extents, mapping, count, and copy order;
- fixups/transforms, if any, and later overwrite/lifetime constraints;
- output identity, stopping point, and evidenced runtime entries;
- destination CFG/xrefs, classifications, and explicit unresolved items.

Use the effort's existing notes rather than building a new ledger system for one copy loop.
