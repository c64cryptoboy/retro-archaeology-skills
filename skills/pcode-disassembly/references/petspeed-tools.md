# PETSpeed decoder

From the skill directory:

```sh
python3 -X utf8 scripts/petspeed/petspeed.py PROGRAM.WOW \
  --map PROGRAM.W --source PROGRAM.bas \
  --text-output NEW-listing.txt --json-output NEW-report.json
python3 -X utf8 -m unittest discover -s scripts/petspeed -q
```

Only `petspeed.py` and its adjacent `petspeed_profile.json` are needed. Python 3.10+ standard library only. Tests use synthetic bytes and require no commercial software, emulator or network access.

`--source` requires the matching raw SEQ `.W` map. Supplied BASIC is annotation, not recovered or authenticated source. Preserve duplicate source anchors and the opaque map footer instead of inventing meaning. Output files must be fresh.

Unknown runtime fingerprints, lengths/selectors, truncated instructions and invalid boundaries refuse. The profile includes compact families, 122 explicit primary entries and eight secondary selectors. These counts are structural knowledge, not independently executed language-feature coverage.

Opcode `$AB` is the one-byte `ZERO_ARG` primitive: `$6C/$6D := 0`, integer tag `$B6 := 1`, no inline operand, normal p-code fallthrough. The pinned runtime's dispatch word `$087C` selects `$1408`; its handler tails to the shared `$0926` cursor increment without another operand fetch. This does not clear all ARG payload bytes or write FAC. Admission remains limited to runtime `[$0826,$2800)` SHA-256 `cee17449b6e9700af4642546477c06dbb42413888fa5e594ebded33014c5dbaf`. Static handler evidence and synthetic grammar/refusal tests are not target-execution or whole-program equivalence evidence.

ON-table and function-definition grammars validate every encoded control destination. Keep function descriptors, body entries, skip targets and source-line operands distinct. Complete declared-main-p-code decoding does not establish reachability, full compiler-language support or interpreted/compiled equivalence.

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

No opcode grammar, runtime fingerprint, or public image admission changes.  Decoded-record callers must establish this native-handler and literal-producer contract, valid numeric representations, binary arithmetic, stock BASIC mapping, valid VM/stack/heap state, benign interrupts, and nonaliasing conventional workspace.  Joins, calls, unknown effects, and region boundaries still discard literal facts.  Synthetic tests and retained-development-object static replay are not native execution, an independent holdout, or executable stock-BASIC equivalence.

## Extending coverage

Follow [compiler-assisted discovery](compiler-assisted-discovery.md). Establish runtime handler behavior and exact operand lengths before extending the profile. Freeze the core/profile before a fresh holdout and distinguish same-image regressions from independent validation.

Consult the appropriate C64 PETSpeed manual for edition-specific restrictions before preparing input. Preserve a compiler-neutral baseline and explicit compiler-specific deltas. Do not execute broad preimage programs merely because compilation or decoding succeeded.

Pinned-media preparation, capture, private-fixture regression and native-runtime discovery helpers are not dependencies of the portable decoder. Keep those project-specific adapters and their compiler/runtime/media evidence in your own analysis project, outside the distributable skill.
