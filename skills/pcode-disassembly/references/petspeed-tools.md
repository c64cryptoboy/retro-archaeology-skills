# PETSpeed decoder

From the skill directory:

```sh
python3 -X utf8 scripts/petspeed/petspeed.py PROGRAM.WOW \
  --map PROGRAM.W --source PROGRAM.bas \
  --text-output NEW-listing.txt --json-output NEW-report.json
python3 -X utf8 -m unittest discover -s scripts/petspeed -q
```

Keep the `scripts/petspeed/` directory together, including `variant_2267.py` for the alternate runtime. Python 3.10+ standard library only. Tests use synthetic bytes and require no commercial software, emulator or network access.

`--source` requires the matching raw SEQ `.W` map. Supplied BASIC is annotation, not recovered or authenticated source. Preserve duplicate source anchors and the opaque map footer instead of inventing meaning. Output files must be fresh.

Unknown runtime fingerprints, lengths/selectors, truncated instructions and invalid boundaries refuse. The historical base profile includes compact families, 122 explicit primary entries, and eight secondary selectors.  Automatic selection on the exact classic runtime adds four primary entries from `classic_2245.json`; an explicit `--profile` uses the supplied grammar as written. These counts are structural knowledge, not independently executed language-feature coverage.

Opcode `$AB` is the one-byte `ZERO_ARG` primitive: `$6C/$6D := 0`, integer tag `$B6 := 1`, no inline operand, normal p-code fallthrough. The pinned runtime's dispatch word `$087C` selects `$1408`; its handler tails to the shared `$0926` cursor increment without another operand fetch. This does not clear all ARG payload bytes or write FAC.  The symbolic reader contributes the numeric value zero from ARG while retaining a separately known FAC operand; it does not supply either fact to a branch that bypasses the load. That classic profile is pinned to runtime `[$0826,$2800)` SHA-256 `cee17449b6e9700af4642546477c06dbb42413888fa5e594ebded33014c5dbaf`. Static handler evidence and synthetic grammar/refusal tests are not target-execution or whole-program equivalence evidence.

ON-table and function-definition grammars validate every encoded control destination. Keep function descriptors, body entries, skip targets and source-line operands distinct. Complete declared-main-p-code decoding does not establish reachability, full compiler-language support or interpreted/compiled equivalence.

## Reading one independently located routine

If an unknown opcode prevents a whole-program listing, you can still study a **separately evidenced** interval of the classic `JMP $2245` runtime.  Use a decoded call target, map, or equivalent evidence to locate the start.  Do not hunt for a stretch of bytes merely because it decodes.

```sh
python3 scripts/petspeed/petspeed_region.py program.prg --start 0x3000 --stop 0x3010
python3 scripts/petspeed/region_reading.py program.prg --start 0x3000 --stop 0x3010
```

Substitute the actual start and **exclusive** stop.  The first command emits JSON with every instruction and encoded destination; the second puts short BASIC-like statements beside their original bytes.  The reader recognizes selected file I/O, loop setup, guarded string comparisons and substitutions, ordered concatenation, and a conditional descriptor assignment.  Unsupported idioms remain VM rows.  For example, `GET#6, V_2808$, V_2915$` means select channel 6 once, read and store the first character, read and store the second, then restore the channel.  The one- and two-field forms both require the final restore and no known branch into the middle.  Neither implies an atomic read or an EOF check.  A string-element destination alone does not prove a string assignment: the fresh RHS type selects the store path, and assignment assumes successful descriptor maintenance.

The classic whole-object and interval readers share `$C7 CHR_STRING`: one opcode byte, no inline operand, and ordinary fallthrough on success.  With valid numeric FAC, `$1E9E` converts/checks its byte and allocates a one-character string in FAC.  It takes no saved expression-stack operand; allocation can collect and relocate strings or fail.  Decoding the row alone proves neither the incoming type nor successful execution.  A directly selected output file, scalar address load, `PEEK`, `$C7`, string print, and restore can therefore read `PRINT#3, CHR$(PEEK(V_2808));`.  Selection precedes the memory read; the semicolon means no added newline, not that the byte cannot itself be a carriage return.  This reading assumes a valid numeric address and successful allocation and I/O.  An incomplete sequence or a known interior entry stays as separate VM operations.  The alternate runtime's `$C7` comes from its own grammar and handler, not the classic profile.

On that exact classic runtime, `$F1 lo hi` is `LOAD_INTEGER_WORD_ABS`.  The inline word is a little-endian **data address**, not the integer value or a branch target.  On ordinary memory the handler tags FAC as integer, loads the high byte from that address and the low byte from the next, and resumes at `IP+3`.  The row does not establish the memory contents, variable identity, or subscript.

The classic `$EE lo hi` form, `LOAD_INTEGER_WORD_ARG_ABS`, instead sets the integer ARG tag `$B6=1`, and loads the two addressed bytes into `$6C` and `$6D`, respectively.  The address is not a control edge.  With binary arithmetic and stable VM state, the next fetch is at `IP+3`; this is a handler contract, not evidence that a particular site executes.

On that exact classic runtime, `$F4 lo hi` is `STORE_NUMERIC_WORD_ABS`.  The inline word is the little-endian **data address**, not a branch target.  On the ordinary numeric path, the handler stores the high byte first and the low byte second, then fetches at `IP+3`.  A zero FAC tag takes the floating conversion path first; a nonzero tag bypasses conversion, not a type check.  The row does not identify a BASIC variable or array, guarantee conversion succeeds, or predict the effects of overwriting live VM state.

The same interval reader can show a guard that replaces an empty string with a length-one NUL, and an ordered little-endian word expression such as `ASC(V_2808$) + ASC(V_2818$) * 256`.  The guard must compare and store the same slot and skip the entire assignment.  The arithmetic must evaluate the first `ASC` before the second, multiply the second by 256, add the saved first byte, and store the result.  Neither expression predicts I/O status or successful allocation.  Encoded `GOSUB` targets are shown without inferring the matching return.

The interval tool keeps the normal runtime fingerprint, layout, and contextual modifiers.  An internal branch into an operand refuses the interval; an external target inside declared code is labeled *boundary unverified*.  Arbitrary starts are caller-assumed, hidden incoming edges remain possible, and a linear `NEXT` followed by `RETURN` does not establish which path executed.  Neither command runs the input, recovers original names, or changes whether whole-object reconstruction succeeds.

## Alternate runtime and numbered BASIC

The standalone decoder and `scripts/reconstruct/reconstruct.py` select the alternate grammar only for the exact runtime `[$0826,$2800)` SHA-256 `3b13c8c451db362fdd3fafa91832f3484dd9fd3eac0fcff792b82e9484a9131a` and a valid executable layout with `JMP $2267`.  A matching jump or dispatch table alone is not enough.  An explicit standalone `--profile` selects only that profile.

```sh
python3 scripts/reconstruct/reconstruct.py program.prg --text-output annotated.txt \
  --json-output evidence.json --basic-output numbered.bas --prg-output numbered.prg
```

The numbered view adapts [PetspeedDecompy](https://github.com/EgonOlsen71/PetspeedDecompy/tree/3d4360e8b481c2157fccac0458f3556a2d3ea311).  Use it to read statements and follow branches; use the detailed view to check instruction addresses, operands, and unresolved semantics.  Line numbers and aliases are generated; array shapes are inferred, and DATA fields can be regrouped.  The text escapes nonprinting bytes for display.  The optional tokenized PRG preserves the generated token bytes, not the original source or a guarantee of equivalent execution.  Neither input nor output is run.  Compact translation can refuse an object whose instructions all have known lengths; in that case the detailed report remains available without the export options.  See also [related tools and independent checks](compiled-basic-related-tools.md).

The JSON reading view links generated lines to emission addresses, records each encoded destination separately from the line it maps to, and retains each DATA field's address, tag, text bytes, numeric suffix, and the separate footer.  The frontend checks that the compact and detailed instruction boundaries agree (the compact view omits the terminal END marker).  It also refuses direct branches into scalar stores with an unproved incoming value, nonnormalized floating literals, and changes in the number of `RND`, `PEEK`, or `FRE` calls.  Equal counts do not establish evaluation order or reachability.  For the classic `JMP $2245` runtime, the detailed report recovers supported DATA records independently; it does not enable the alternate numbered exporter.

## Semantic clock-reading support

The internal symbolic adapter recognizes an independently decoded `TIME_ARG` record as a numeric clock sample into ARG, preserving FAC.  It uses the existing system-value capture at the original producer site, with the usual stock-BASIC representation warning; the capture is bookkeeping, not a recovered source variable.  Joins, unknown effects, and region boundaries still discard facts.  This does not model the distinct `TIME_STRING_ARG_FAC_TYPE_CLOBBER` form.

This semantic rule does not add a selector, runtime fingerprint, or image-admission path to the public decoder.  A caller supplying decoded records remains responsible for the exact native-handler contract, valid VM state, binary arithmetic, and stock BASIC/KERNAL mapping.  Synthetic semantic tests are not execution or whole-program equivalence evidence.

## Semantic absolute string-descriptor reads

The internal symbolic adapter recognizes an independently decoded `LOAD_STRING_ELEMENT_AT` record as `STRDESC_hhhh$`, an opaque view of an absolute three-byte descriptor slot.  It replaces FAC, preserves ARG, and carries producer provenance and an explicit warning.  The suffix describes the handler's unconditional string output tag, not a recovered BASIC variable, array identity, dimensions, or subscripts.  No descriptor contents or character bytes are read by the lifter, and the expression is not marked as a stable snapshot.

This semantic-only route adds no public opcode, runtime fingerprint, or image admission.  Its caller must establish the exact native contract, binary arithmetic, stable mapping/runtime, a valid stack, benign interrupts, and ordinary nonaliasing descriptor memory; workspace/I/O aliases are outside this simple copy interpretation.  Joins, calls, unknown effects, and region boundaries still discard facts.  No `$EF` tag recovery, character allocation semantics, whole-program typing, or executable BASIC equivalence is implied.

## Semantic literal CHR$ construction

The internal symbolic adapter lifts an independently decoded `CHR_STRING` only when FAC still has a single numeric-literal producer: `ZERO_FAC`, `ONE_FAC`, `CONST_U8_FAC`, `CONST_I16_FAC`, or `CONST_FLOAT_FAC`, with `0 <= value < 256`.  Signed words are not masked to a byte.  Positive fractional floats retain their original argument; the native numeric conversion discards the fractional part before checking the resulting high byte.  Negative, out-of-domain, string, unknown, derived, and unproved-type operands remain unresolved barriers.  This is deliberately not general CHR$ expression support.

The call is represented as `T_hhhh = CHR$(literal)` at its own producer site, even if the result is later overwritten.  This reuses the effectful function path, never a pure substitution or a folded character literal.  It replaces FAC with a stable synthetic result, invalidates ARG and integer scratch, and preserves the explicit saved-value stack.  The normal native result is a tagged string descriptor with length one and a pointer to newly allocated storage containing the checked byte; the temporary represents that string value, not a recovered variable or an exposed descriptor pointer.

The native byte conversion/range check occurs before allocation, which can invoke garbage collection and fail.  The reading representation preserves the evaluation site and carries a heap/error qualification; it does not simulate allocator metadata, relocation, error paths, physical descriptors, or memory-observing equivalence.  The effectful temporary may not be deleted, merged with another call, or moved across a heap-observing operation merely because its argument is constant.

This symbolic rule does not change whole-object grammar, runtime fingerprints, or public image admission.  Decoded-record callers must establish this native-handler and literal-producer contract, valid numeric representations, binary arithmetic, stock BASIC mapping, valid VM/stack/heap state, benign interrupts, and nonaliasing conventional workspace.  Joins, calls, unknown effects, and region boundaries still discard literal facts.  Synthetic tests and retained-development-object static replay are not native execution, an independent holdout, or executable stock-BASIC equivalence.

## Exporting compact BASIC

Check the [boundary between names and word operators](basic-word-boundary.md) in the saved BASIC bytes.  The numbered text alone cannot distinguish `A` followed by the FOR token from `AF` followed by the OR token.

## Extending coverage

Follow [compiler-assisted discovery](compiler-assisted-discovery.md). Establish runtime handler behavior and exact operand lengths before extending the profile. Freeze the core/profile before a fresh holdout and distinguish same-image regressions from independent validation.

Consult the appropriate C64 PETSpeed manual for edition-specific restrictions before preparing input. Preserve a compiler-neutral baseline and explicit compiler-specific deltas. Do not execute broad preimage programs merely because compilation or decoding succeeded.

Pinned-media preparation, capture, private-fixture regression and native-runtime discovery helpers are not dependencies of the portable decoder. Keep those project-specific adapters and their compiler/runtime/media evidence in your own analysis project, outside the distributable skill.
