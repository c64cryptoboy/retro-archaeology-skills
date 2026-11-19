# BLITZ semantics and compiler artifacts

> Read [SKILL.md](../SKILL.md) first. This is the detailed procedure for the routed phase, not an instruction to expand every task. Commands and inline file paths below are relative to the **skill directory**, unless explicitly stated otherwise; Markdown links resolve from this reference.

### 7. Audit BLITZ-versus-BASIC semantics

For an explicitly compiler-free BLITZ effort, consult historical documentation only after its freeze. In an authorized compiler-assisted effort, consult and cite it directly. Kim Moser's transcription of the Skyles BLITZ documentation, [“Blitz Compiler Docs”](https://www.kmoser.com/bbs/docs-blitz.php) (last-modified 2007-02-02), is useful but explicitly warns of line noise and transcription damage; source licensing is unclear. Cite and summarize it rather than copying substantial text, and validate consequential claims with binaries or microprograms.

Reusable documented leads:

- BLITZ preconverts numeric constants, uses true integer arithmetic where possible, and evaluates expressions as RPN.
- It claims one consistent rounding procedure where stock BASIC can differ between stored values and evaluated arguments. Audit calculated arguments to `PEEK`, `INT`, `POKE`, `WAIT`, `SYS`, and array indexes rather than assuming interpreted/compiled equivalence.
- Differential tests should target chained arithmetic that lands just above/below an integer, byte/address limits, final array indexes, and integer overflow. Record packed values, selected array element or hardware address/value, and exact runtime error—not merely printed decimal text.
- Inventory source constructs first, then use small compiler microprograms to isolate each exercised form. `build_rounding_microtest.py --prg test.prg --listing test.bas.txt` emits one 10,000-iteration test with phase markers; compile the PRG unchanged, retain the compiler input/output hashes and transcript, and require `HASH PASS`, `ARRAY PASS`, `POKE PASS`, and `ALL PASS`. A failure before a marker localizes the class but does not by itself explain the runtime implementation.
- Also run title-specific integrated cases because RPN order, variable typing, runtime conversion, and actual array type can interact. A passing microprogram narrows risk; it does not replace a normal startup/route smoke.
- Multidimensional arrays should be explicitly `DIM`ensioned; one-dimensional arrays may default to 11 elements. BLITZ creates a reserved internal `z*%` array, so account for it when mapping descriptors.  The exact `10 01 DA AA 00 00` allocation is displayed as an internal operation, not a source `DIM`.  It still consumes the upper bound.  [Reblitz64’s emitter](https://github.com/c1570/Reblitz64/blob/4c3f9da453b53fd5cbe898f85a99b1d914efb117/docs/reblitz64.js#L1965-L1988) emits this record separately from named program arrays.
- Integer `FOR` variables are a BLITZ-only source technique and change loop representation/overhead; do not infer stock BASIC legality from compiled behavior.
- The STOP key is disabled after compiled `RUN`, `LOAD`, and `CLR` unless special REM directives alter it; `CONT` is unsupported. Treat debugger interruption/restart behavior separately from program semantics.
- Forced extensions prefixed by `::` may be passed to the built-in BASIC interpreter, creating a hybrid native/p-code/BASIC path that needs explicit tracing.

Compiler artifacts can be structural evidence:

- Option 1 conventionally emits `c/<name>` plus `z/<name>`; the cross-reference maps compiled runtime program-counter values back to source lines.
- Temporary `p/<name>` and `d/<name>` files reportedly hold pure p-code and DATA before being scratched. Preserve them when legitimately available: they can establish boundaries independently of a final-image heuristic.
- The documented final layout is runtime routines, DATA, p-code, then the variable table. Treat this as a lead and verify exact addresses per binary/revision.
- A reported compile error does not prove the final file is unusable or complete: first-pass erroneous lines may be omitted while compilation continues. Retain the full compiler transcript and verify source-line coverage.
- Multi-file options differ in runtime inclusion, variable-table sharing, chaining, and overlay behavior. Record the exact option and disk topology before comparing layouts.

### Literal bytes in annotated listings

The standalone annotator reads inline operands from the instruction bytes.  It displays a known screen control such as `$93` as `{CLEAR}`, but leaves `$5E` as `{PETSCII_$5E}`, not an ASCII caret.  A literal sequence of four bytes `$5C $78 $39 $33` is not the one-byte clear-screen code.  These markers describe the stored bytes, not the glyphs visible in every display mode.

### Retained name bytes

BLITZ and the admitted Austro-Speed decoder use both name bytes to distinguish `Q`, `Q$`, and `Q%`.  Only the second high bit is set for a string; both are set for an integer, including in DIM operands.  When only the first is set, the scalar-table display marks a function slot (`FN Q`), not an integer variable.  These are significant name characters and storage types, not proof of the original identifier spelling or of a reaching FN binding.  FN declarations and calls below still use descriptor identities.

### Selected-file output ending

In the admitted BLITZ and Austro-Speed layouts, `$45` (`PRINT_CHANNEL_EMPTY`) restores the default I/O channels without writing a carriage return.  It enters at the cleanup call, after the newline path.  This matters for forms such as `PRINT#3,;`: the reader keeps the selection and cleanup visible but does not invent an empty record.  Any previous value output remains at its own instruction.  `$3F` (empty print) and `$43` (final value with newline and cleanup) are distinct.  This is normal-path behavior, not proof that the file is open or that the I/O succeeded.

### Current-channel input versus file selection

A partial `REM current-channel INPUT: ...` or `REM current-channel GET: ...` preserves the observed destinations without claiming a keyboard or a file.  `$50` saves the input retry position; it does not select a channel.  `$53` and `$55` test the runtime input state, and `$46` reads the current input device.  Losing track of that state at a call or branch is different from observing `$48` select a file whose number is unknown.  For example, an actual computed selector before GET can still read `GET#<?>, A$`.

### Selected-file input lists

A literal logical-file selector followed immediately by a complete field list can read `INPUT#3, A$, B` or `INPUT#7, U%(Q9), V$(4)`.  The selector retains its own low-level group; the input heading links back to both the number and the selector.  A positive compact file literal and an uninterrupted first/next/final sequence are required.  Scalar destinations use a string scalar load or a numeric scalar descriptor.  An indexed field requires its own compact numeric scalar load or small literal followed by `$A4`, with a uniquely declared, named, rank-one array descriptor.  A missing index is not supplied by the DIM, selector, or previous field.  An alternate decoded entry after the file literal blocks this recovery, even if the destination names look plausible.  The separate `$50` retry form is not part of this sequence.

This is the normal input and destination order, not proof that the file is open, a physical device is attached, or an input succeeds.  The final field has channel cleanup; do not carry its selected file forward.  Zero or computed channels, single-field forms, computed subscript expressions, and flattened multidimensional accesses are outside this rule.  BLITZ and Austro-Speed keep distinct error and end-of-file behavior.

### Two-subscript numeric stores

Two stores that end with the same subscript and value may write different cells.  For ordinary BLITZ `$E4`, a unique preceding numeric rank-two declaration identifies the array; it does not supply the live subscripts.  The reader names both axes when one uninterrupted group builds the first subscript, the second subscript, and the value, in that order.  For example, `U2(3, 4) = 99` and `U2(5, 4) = 99` are distinct even though the final index is 4 in both.  An entry into the middle of the group, a missing producer, or a conflicting descriptor prevents this reading.  Other ranks and Austro-Speed do not inherit this rule.

A separate `$A4` **value read** can recover `V = TA(X, Y)` rather than collapsing it to its final axis `Y`.  The verified interpreter pops the last subscript first, then reads the earlier one when the descriptor says rank two.  Require two uninterrupted ordinary numeric scalar loads, a unique ordinary rank-two declaration, and an immediate numeric scalar assignment.  An alternate entry that bypasses the first producer blocks the reading.  The declaration identifies the array; it need not precede the consumer in address order and does not prove that it ran.  This rule does not apply to an array address used as an input destination.

### Bounded numeric leaf-FN reading

The symbolic reader can label one straight-line numeric leaf declaration, its retained scalar formal, and its deferred normal-return expression.  The function name remains synthetic (`FN F_<descriptor>`), not recovered source syntax.  This is a structural reading aid, not executable or equivalent BASIC.

Admission requires the selected BLITZ or Austro profile, complete seven-byte scalar records, distinct aligned function/formal storage, one declaration per descriptor, a valid body/skip interval, no alternate body entry, and exactly one numeric result.  Only formal loads, numeric constants, negation, addition, subtraction, and multiplication are accepted.  Other variable reads, calls, recursion, arrays, unknown effects, malformed descriptors, and joins retain the opaque declaration/return path.

The declaration skips its embedded body.  A normal call stores the argument in the five-byte numeric formal, with the runtime's conversion/rounding, and normal return restores the saved formal bytes.  Error cleanup is not established.  Calls remain descriptor-indirect, at their original evaluation sites, with conservative state invalidation; a lexical declaration is not proof of the reaching runtime binding.  No call is inlined or promoted to purity.

Austro retains its own family/profile identity and partial `VM_AUSTRO_MULTIPLY` operation.  Shared FN structure does not establish shared arithmetic, I/O, error, or whole-runtime semantics.  Authored fixtures and known-object offline replays do not establish unseen holdout generalization or target execution.

