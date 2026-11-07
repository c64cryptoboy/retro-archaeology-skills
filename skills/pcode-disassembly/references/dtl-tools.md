# DTL BASIC / Jetpack 64.4 tools

The deterministic decoder is in [../scripts/dtl/](../scripts/dtl/). Python 3.10+ and the standard library suffice. It does not compile or execute programs and requires no emulator, harness, ROM installation, or private files.

Supply your own legitimately held object and the original `RTL-64` PRG matching the profile. Commercial compiler/runtime bytes are **not** bundled.

```sh
python3 scripts/dtl/dtl.py program.prg --runtime RTL-64.prg \
  --map LN-program.seq --source supplied.bas \
  --json-output decoded.json --text-output decoded.txt
(cd scripts/dtl && python3 -m unittest -v)
```

`--map` and `--source` are optional; `--runtime` is required and hash checked. The default `dtl64_profile.json` fingerprints the supplied 64.4 runtime and object bootstrap. Do not bypass a mismatch to claim support for another revision. Paths in this example are relative to the skill directory.

## Output and evidence contract

- Addresses and exact owned bytes, neutral/semantic mnemonics, operands, confidence and static targets.
- Distinct initialization and main instruction regions, including compiler-appended code after the last source anchor.
- Preserved raw DATA, header/bootstrap, separator, scalar, array-metadata and trailer regions.
- Original scalar names where retained in the object; byte offsets are not variable slot numbers.
- BASIC source above matching LN groups when supplied. This is **source correspondence**, not authenticated recovery of the original source.
- Tokenized BASIC interpreter islands remain visible as such; PRINT and other statements may be executed by the stock BASIC ROM rather than a dedicated p-code handler.
- Every static branch/table/FN target must hit a decoded instruction boundary. Runtime-managed startup, loop, return and SYS edges are classified separately and are not invented as static edges.
- Repeated map offsets are retained. An interior/end map anchor is explicitly reported and never used to guess instruction length.

This is a structural disassembler with source-assisted presentation, **not a general source decompiler, reachability proof or behavioral-equivalence checker**. It does not reconstruct arbitrary expressions into runnable BASIC.

## Supported scope

The default stage-1 **opcode grammar** remains at 79 of 85 nonzero dispatcher entries, with `$4B/$56/$58/$59/$5A/$B4` unknown.  The separately named **`dtl64_profile-omnibus.json`** models 83 of 85, adding descriptor-indirect FN calls (`$B4`), the operand-free RUN-bootstrap transfer (`$58`), counted opaque filename bytes for `$59/$5A`, and colon-terminated SYS argument tails.  Select it explicitly with `--profile scripts/dtl/dtl64_profile-omnibus.json`.  Its remaining unknowns are `$4B/$56`.  Matching handlers/aliases are not automatically equivalent operations.

For `$59/$5A`, the pinned native entry `$B6CE` reads the count at IP+1 and owns `count+2` bytes, including opaque filename data.  Normal continuation advances by that exact width through `$B498`.  Counts 254 and 255 wrap the native byte-width arithmetic and remain refused.  State selects skip, restore, embedded-table setup, or KERNAL LOAD behavior; this is not a pure operation.  The grammar assumes initialized dispatch, binary arithmetic, valid disjoint runtime tables, and normally returning services that preserve the saved width.  For `$5A`, the initialized split tables select `$B6CE`; the handler replaces incoming A/Y, clears carry, and does not use the incoming opcode in X.  This dataflow establishes operand boundaries, not compiler-emitter equivalence among `$59/$5A/$5B`.  There is no claim of external-file support or successful execution.

Known grammar covers literals, typed short/long scalar and array offsets, arithmetic, comparisons, FOR/NEXT, XOR-encoded branches and ON tables, DEF FN definitions/bodies, system/function selectors, directives, standard interpreter islands and the observed empty SYS tail. The omnibus profile also preserves comma-led SYS tails, including empty argument positions. The terminating colon is owned by SYS, but its machine-code callee controls the returned text cursor: a decoded tail does not guarantee that arguments are consumed or execution resumes after it. Colons inside quoted SYS tails and missing delimiters refuse. Some entries have native-handler evidence only; these are not all independently compiled or executed.

Image scope is the complete, standard `$0801` object with embedded scalar/array metadata and the pinned bootstrap/runtime. External VL/VN files, overlays, PROTECTOR modes, another runtime revision and arbitrary BASIC extensions remain unsupported. Full-image code/data classification is not claimed merely because raw non-instruction regions are retained.

The parser refuses unknown opcodes/selectors, truncated operands, unsupported interpreter starts/SYS tails, unrecognized bootstrap/layout, malformed maps and static targets inside operands. Byte-count forms whose native length arithmetic would overflow are conservatively refused; this is a decoder support boundary, **not a newly measured compiler restriction**.

## Important format distinctions

- RTL-64's disk header is `$0801`, but the bootstrap loads its payload at `$A000`.
- Runtime setup changes the fetch opcode and split-table operands. Raw pre-initialization disassembly alone misidentifies the fetch as a store.
- P-code IP `$39/$3A` points to the current opcode. Handlers have explicit advances; there is no universal extra increment.
- Object header offsets are little-endian; scalar/array extended operands and source-map words are big-endian.
- Branch target bytes are XOR encoded with per-image trailer-derived keys. For the accepted identity path in the pinned 64.4 RTL, trailer byte **4** supplies the target-high-byte XOR key and trailer byte **5** supplies the target-low-byte XOR key; the same trailer bytes separately bias the array and scalar pointer words (those pointer biases are **not swapped**). Both active stage-1 and omnibus profiles corrected a previously reversed branch-key pair. A symmetric `$FF,$FF` identity hides the difference; synthetic `$2402`/`$1234` identities and the decoded compiler objects exercise it. This is an operand-key correction, not a compiler-only opcode variant. Other protection/overlay/external-variable modes remain outside scope.
- LN files are SEQ data without a PRG load header. The terminal source anchor is not necessarily the end of compiler-appended p-code.
- Inline BASIC delimiters are contextual and kept separate from the statement text.
- Functions `$18/$19/$1A` are TI/TI$/ST respectively, established from native bridge/workspace behavior—not guessed from table order.

## Validation levels

Bundled synthetic tests cover refusal, layout, endianness, quoting, source maps, signed literals, selectors, and target boundaries without commercial assets.  These include asymmetric accepted-identity branch-target and pointer-bias checks, and `$59/$5A` width, truncation, overflow, target-boundary, default-profile, and identity refusals.  The `$5A` controls exercise every nonwrapping count from 0 through 253 and reject both wrapping counts even with complete payloads.

Reported external development validation, whose objects are not bundled, covers two authored smoke outputs, five supplied source/object examples, ERROR LOCATE, and an authored execution holdout against an earlier frozen profile.  A documentation-filtered, 174-line omnibus compiled with zero errors/warnings and decoded all 1,275 initialization/main bytes as 464 instructions under the omnibus profile; 19 static targets and 175 map anchors validated.  Only REM/DATA had zero-width main-source spans.  This omnibus evidence was compile-only and known-source, not runtime execution, a post-expansion holdout, or source-blind reconstruction.  The current profiles include the documented branch-key correction and are not byte-identical to the earlier freeze.

The omnibus object contains neither `$59` nor `$5A`.  Separate synthetic `$5B`-to-`$59` and `$5B`-to-`$5A` mutations each exercise one 12-byte instruction, not a new compiler-produced example or runtime observation.  Full commercial titles and other revisions are unvalidated.  The manual's CONT/LIST rejection is documentation-based, not established by negative trials.  Print options were off; RUN IDENTITY is a printed-listing heading, not an execution guarantee.
