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
- Multidimensional arrays should be explicitly `DIM`ensioned; one-dimensional arrays may default to 11 elements. BLITZ creates a reserved internal `z*%` array, so account for it when mapping descriptors.
- Integer `FOR` variables are a BLITZ-only source technique and change loop representation/overhead; do not infer stock BASIC legality from compiled behavior.
- The STOP key is disabled after compiled `RUN`, `LOAD`, and `CLR` unless special REM directives alter it; `CONT` is unsupported. Treat debugger interruption/restart behavior separately from program semantics.
- Forced extensions prefixed by `::` may be passed to the built-in BASIC interpreter, creating a hybrid native/p-code/BASIC path that needs explicit tracing.

Compiler artifacts can be structural evidence:

- Option 1 conventionally emits `c/<name>` plus `z/<name>`; the cross-reference maps compiled runtime program-counter values back to source lines.
- Temporary `p/<name>` and `d/<name>` files reportedly hold pure p-code and DATA before being scratched. Preserve them when legitimately available: they can establish boundaries independently of a final-image heuristic.
- The documented final layout is runtime routines, DATA, p-code, then the variable table. Treat this as a lead and verify exact addresses per binary/revision.
- A reported compile error does not prove the final file is unusable or complete: first-pass erroneous lines may be omitted while compilation continues. Retain the full compiler transcript and verify source-line coverage.
- Multi-file options differ in runtime inclusion, variable-table sharing, chaining, and overlay behavior. Record the exact option and disk topology before comparing layouts.

### Bounded numeric leaf-FN reading

The symbolic reader can label one straight-line numeric leaf declaration, its retained scalar formal, and its deferred normal-return expression.  The function name remains synthetic (`FN F_<descriptor>`), not recovered source syntax.  This is a structural reading aid, not executable or equivalent BASIC.

Admission requires the selected BLITZ or Austro profile, complete seven-byte scalar records, distinct aligned function/formal storage, one declaration per descriptor, a valid body/skip interval, no alternate body entry, and exactly one numeric result.  Only formal loads, numeric constants, negation, addition, subtraction, and multiplication are accepted.  Other variable reads, calls, recursion, arrays, unknown effects, malformed descriptors, and joins retain the opaque declaration/return path.

The declaration skips its embedded body.  A normal call stores the argument in the five-byte numeric formal, with the runtime's conversion/rounding, and normal return restores the saved formal bytes.  Error cleanup is not established.  Calls remain descriptor-indirect, at their original evaluation sites, with conservative state invalidation; a lexical declaration is not proof of the reaching runtime binding.  No call is inlined or promoted to purity.

Austro retains its own family/profile identity and partial `VM_AUSTRO_MULTIPLY` operation.  Shared FN structure does not establish shared arithmetic, I/O, error, or whole-runtime semantics.  Authored fixtures and known-object offline replays do not establish unseen holdout generalization or target execution.

