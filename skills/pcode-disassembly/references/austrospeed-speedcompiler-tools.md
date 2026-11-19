# Austro-Speed and INPUT64 Speedcompiler support

These are separately identified attached-runtime variants, not a claim to support
all historical releases or configurations. Commercial media, source fixtures,
whole-image reports and runtime bytes are not bundled.

## Binary-only entry points

From this skill directory:

```sh
python3 scripts/reconstruct/identify.py /path/object.prg
python3 scripts/reconstruct/reconstruct.py /path/object.prg \
  --json-output /new/report.json --text-output /new/listing.txt
```

The frontend accepts no source/map/annotation input and refuses overwriting output.
Identification, layout validity, instruction grammar and semantic reconstruction
are separate gates. Unknown signatures are not proof of uncompiled input.

## Austro-Speed

- Separate family `austrospeed` with explicit runtime fingerprints. The supplied
  AustroSpeed88-style runtime uses `scripts/austrospeed/austrospeed_profile.json`
  and startup table `$1F79`. A separately evidenced older attached runtime retains
  the Austro-Speed identity but selects the byte-compatible BLITZ decoder contract
  and startup table `$1F93`; identity and decoder contract are reported separately.
- Reuses the deterministic BLITZ decoder only after native handler/cursor audit;
  no general claim is made that every Austro-Speed revision is BLITZ-identical.
- Covers init/main p-code, bounded DATA, variables, targets and loaded regions.
- Runtime differences include multiplication, CLR ordering, input and file-I/O
  error handling. This is not an identical-BLITZ-semantics assertion.
- Multiplication lifts as `VM_AUSTRO_MULTIPLY`, not silently as BASIC `*`, because
  the evidenced runtime has an integer-negation defect. A missing array index
  stays `<?>`; reconstruction does not invent the compiler's apparent intent.
  For a one-dimensional GET destination, the DIM rank says how many subscripts
  are needed, not which element is read.  `$A4` selects the array descriptor;
  a separate reaching value supplies the subscript.  A file number consumed by
  `$48` is not that value.  At `$50` (INPUT begin), a retry resumes with the
  following opcode, so do not carry an earlier subscript through that boundary.
- Direct opcode `$58` is operand-free `RETURN_IF_TRUE`; native stack-unwind
  behavior and a post-freeze source reveal independently validate its rendering
  as `IF condition THEN RETURN` for the older runtime. Existing BLITZ limits on
  FN bodies, multidimensional source indices and broader runtime behavior still
  apply. One external source-withheld older-runtime holdout has passed; it does
  not establish support for all Austro-Speed releases.

## INPUT64 Speedcompiler

- Separate family `speedcompiler`, core/profile/tests under
  `scripts/speedcompiler/`.
- Native fetch modifies the low byte of an indirect-JMP operand, selecting an
  interleaved pointer table. This is not the BLITZ split-table VM.
- Decoder models 127 even-byte dispatch entries; odd bytes and the unmodeled
  extension selector `$FE` refuse. Counted/NUL strings, packed floats, targets,
  biased ON counts, initialization, descriptor slots and typed DATA are bounded.
  Static grammar support is not 127 independently executed language features.
- Initial support requires the evidenced attached runtime, default code start,
  ordinary initialization/storage envelope and no external-extension mode.
  Relocated/runtime-less objects and broader revisions are not guessed.
- Whole loaded bytes are partitioned and hashed. Runtime scratch can retain
  source/compiler residue; it is opaque, not an implicit source-recovery channel.
- `scripts/reconstruct/speedcompiler_lift.py` uses distinct integer-stack, lazy
  floating-stack/FAC and three-string-frame contracts, not a shared postfix VM.
- `VM_*` operations preserve integer width, conversions and other runtime-specific
  behavior. Effectful calls get one-time temporaries; joins/unknown effects lose
  facts. These are explanatory names, not guaranteed legal/runnable BASIC.
- The listing uses `POKE address, byte` for an inline immediate byte write and
  for a stack-based byte write with two proved bottom slots.  The latter reads
  the first word as an unsigned address and stores only the second word's low
  byte.  From proved empty depth the bounded proof follows up to three slots
  of literal pushes, single-byte PEEK snapshots, and 16-bit additions.  PEEK
  replaces the top word, addition reduces the top two to one, and POKE is
  admitted only at depth two.  `VM_LOW_BYTE(VM_IADD(T, 4))`, for example,
  stores the low byte of the sum using the earlier sample `T`, not a fresh
  memory read.  Reads can see live VM workspace, not a pristine BASIC memory
  image.  An alternate entry, unknown depth, or unmodeled intervening effect
  kills the proof.  This is the memory effect, not original source syntax;
  `POKE_WORD` is distinct.
- `WAIT address, mask, xorByte` requires exactly three proved integer slots.
  The first supplies a 16-bit address; only the low bytes of the second and
  third participate.  The handler reads the addressed byte at least once,
  repeating while `((byte XOR xorByte) AND mask)` is zero.  This is not one
  `PEEK` or a promise that the wait ends.  Separate `PEEK` instructions that
  produced operands remain one-time samples before the poll.  The listing
  keeps an explicit zero XOR byte without guessing optional source syntax.
- `CLOSE n` names the logical file, not a device or an output selection.  The
  handler passes the low byte of the bottom integer slot to KERNAL CLOSE.
  The reader names `n` only with exactly one proved slot.  Even if it cannot
  name the file, the normal return to dispatch clears integer depth.  This
  does not prove that a device operation succeeded or restore channel facts.
- One counted-name `OPEN` form shows the four values actually passed: logical
  file, device, secondary address, and filename.  On normal return from CLOSE,
  three byte pushes start at empty integer depth.  The admitted path first
  stores a literal in ordinary string storage, reloads that same slot after
  the pushes, and appends a counted literal.  The reader can show their exact
  concatenation if it fits in one byte of length.  A target bypassing the
  reset or a producer, an unmatched store, or an intervening instruction
  blocks this proof.  This does not recover omitted source arguments, infer
  a file mode from a suffix, or establish that a file was opened.
- A signed `INTEGER_COMPARE` returns through `LDY #0` even when it used
  `DEY` to build a true result.  An immediately following `IF_INTEGER_TRUE`
  stores this zero to integer depth before testing the bottom word.  On its
  fall-through, new pushes can therefore prove bottom-slot arguments without
  knowing the predicate.  This rule carries no operand or channel through
  the branch.  A separate entry to the IF, the new push, or its consumer
  breaks this proof; no depth is propagated to branch targets.
- `SYS VM_FLOAT_TO_ADDR16(V_...)` calls the address obtained from the packed
  scalar's **value**, not the address where the scalar is stored.  This is a
  reading annotation, not a BASIC function.  The narrow proof follows a byte
  push (which restores Y to zero), normal WAIT fall-through (which stores Y to
  integer depth), and an uninterrupted scalar load, conversion, and SYS.
  Conversion loads the packed value into FAC, enters stock BASIC at `$BC1D`
  and then `$BC9B`, and pushes fixed-result bytes `$65` (low) and `$64` (high).
  SYS reads the bottom word as an unsigned address, not the last expression
  regardless of depth.  An entry bypassing a required step, or storage outside
  the bounded scalar area, blocks substitution.  No earlier constant is
  forwarded, no target code is interpreted, and all value and channel facts
  are discarded at the call.
- Numeric READ has tag-dependent native depth updates: events are visible, but
  unproved post-state/destination dataflow is dropped. Numeric-looking DATA
  strings keep their encoded string type. Input parsing/retries, file I/O,
  FOR/NEXT and FN reconstruction remain partial or unresolved.

Standalone structural decode:

```sh
python3 scripts/speedcompiler/speedcompiler.py /path/object.prg \
  --json-output /new/decode.json
(cd scripts/speedcompiler && python3 -m unittest -q)
(cd scripts/reconstruct && python3 -m unittest -q)
```

## Evidence boundary

Synthetic parser/state tests need no commercial bytes. Private integration checks
cover successful compilation, exact decoding, target boundaries, binary-only
file-access audits, public-only relocation and separately safe execution. All
omnibus outputs remain compile-only. Instruction coverage is not an accuracy
percentage; known development fixtures cannot be relabeled blind holdouts.
