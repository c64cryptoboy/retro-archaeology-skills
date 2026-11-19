# Candidate audit and evidence interpretation

## Structural evidence is the beginning

A long alignment establishes shared instruction structure under the model. It does not by itself establish:

- a valid routine boundary;
- execution in the captured game state;
- equal input/output contracts;
- equal data semantics;
- direct copying;
- direction or authorship.

Audit high-value candidates in context before using historical language.

## Family-aware accounting

Group reports before interpreting counts.

One family can generate many reports through:

- overlapping starts in one routine;
- two starts inside one repeated shift loop;
- target routines cloned across switched banks;
- the same fingerprint repeated around related arithmetic;
- sensitivity reports rediscovering the same operation.

Use one representative per family for semantic audit. Record raw report count separately from independent-family count.

## Static audit checklist

For each side:

1. Correct the likely instruction boundary.
2. Identify the containing routine or coherent linear fragment.
3. Search direct JSR/JMP/branch references and jump-table exposure.
4. Trace callers far enough to establish incoming registers/state where practical.
5. Trace continuation far enough to establish outputs/side effects.
6. Inspect referenced tables and their consumers.
7. Determine whether paired references retain the same logical roles.
8. Identify whether the alignment crosses operation/routine boundaries.
9. Check banking/visibility and physical versus CPU addresses.
10. Record unsupported-opcode or inline-data stops.

Before carrying a name or comment across a match, verify its particular operand relationship in the target.  The [annotation-transfer example](annotation-transfer.md) changes only the hardware address, RAM alias, or internal operand, and shows which annotations survive each change.

Use a 6502 disassembly/semantic-commenting workflow for substantial context work; the matcher is not a replacement for reverse engineering.

## Dynamic evidence

Use runtime evidence when it resolves a material uncertainty:

- breakpoint at candidate entry;
- identify actual caller/return address;
- sample inputs and output state;
- confirm switched bank;
- determine whether a suspected dormant routine executes;
- verify table values or indirect targets.

Absence from one bounded run is only “not observed through this state/input,” not proof of dead code.

## Semantic correspondence

Strong candidate-level evidence includes:

- same complete operation in the same order;
- stable one-to-one mapping of source pointers, fields, counters, and outputs;
- coherent insertions with a platform/game purpose;
- matching literal constants that are algorithmically meaningful;
- aligned routine boundaries and compatible callers;
- uncommon full shape across targets and controls.

Evidence against promotion includes:

- match begins/ends inside unrelated operations;
- one paired variable changes semantic role;
- scale factors or algorithms differ;
- ordinary 16-bit add/shift/pointer/table idiom;
- repeated internal occurrences;
- plausible decoded data without control-flow evidence;
- a negatively scored mismatch arbitrarily bridges two generic runs.

## Check for a compiler before claiming programmer-level reuse

A match can come from an emitter template, an optional runtime helper, or the input program.  Compare these separately.  A common helper is evidence about that helper; do not count every call site or every copy as an independent match between application authors.

A worked control is Vic Cortes's [Micro Compiler, preserved and ported by EgonOlsen71](https://github.com/EgonOlsen71/microcompiler/tree/71551d432255f3eda552fa1c1e3b3335a3c11e41).  Here are three questions one can answer by compiling two-line programs with that revision, without running the produced code:

- **Same source construct or shared helper?** Compile `A=4+2*3`, then change only `*` to `/`, each followed by `END`.  At load address `$C000`, the only differing payload byte is at `$C01B`: `CLC` versus `SEC` before the same subroutine call.  The appended helper is identical.  A comparison that ignores flag setup would declare the operations identical; a comparison that counts the helper as application logic would exaggerate shared implementation.  The addition is emitted first: do not infer ordinary BASIC V2 precedence.
- **Relocation or different behavior?** Recompile the multiply example at `$9000`.  Excluding the PRG load header, only the high operand bytes of the entry jump, helper trampoline, and call change.  The absolute variable slots and workspace do not move.  Normalize operands by their *roles*, not by masking every address.
- **Can the original source be identified uniquely?** With `END` fixed, `A=B`, `A=BETA`, and `A=BOX` produce identical files.  Separately, with `A=B` fixed, `END`, `STOP`, and `RETURN` produce identical files.  One form is a plausible reading, not a recovered spelling.  A 16-bit load/store or `RTS` alone is neither a compiler nor an author fingerprint.

For the actual immediate-versus-memory templates and host SAVE differences, see the [native emission probes](../../6502-disassembly/references/microcompiler-emission.md).  For a suspected common compiler, retain a helper-absent control, a second load address, and an unrelated emitter or hand-coded confuser where available.  Without that last comparison, do not claim unique provenance.  The probes above concern one port and one configuration, not every version or every target.

## Candidate-specific frequency scans

`candidate_signature6502.py` scans raw files at every byte offset for a selected complete portable-shape subsequence, retaining immediate values and allowing bounded target-only insertions.

Use it to answer: “How often does this exact post-hoc shape appear in these files?”

Do not describe zero control hits as a p-value or calibrated false-positive probability because:

- the candidate was chosen after seeing the target;
- the corpus is finite and nonrandom;
- shape matching does not prove instruction boundaries or execution;
- a natural idiom can be rare in a modest corpus.

## Verdict vocabulary

### Likely shared/adapted skeleton

Use when a complete coherent operation and operand roles survive, with bounded meaningful edits. State confidence and whether enclosing algorithms diverge.

### Weakly suggestive / unresolved

Use when shape specificity or common domain warrants attention but entry contracts, operation boundaries, constants, or roles do not align sufficiently.

### Common/coincidental idiom

Use for textbook arithmetic, pointer increments, little-endian word reads, table initialization, register saves, or platform conventions whose enclosing meanings differ.

### Dormant/uncalled candidate

A coherent unreferenced routine can preserve lineage, but distinguish static ancestry evidence from observed game behavior.

## Whole-pair wording

Keep the locked automated result and manual family result separate.

Example:

> The locked broad comparison was candidate-only. Manual audit found one likely adapted parser skeleton, but no evidence of substantial codebase-wide reuse in the available captures.

For a null/weak result say:

> No additional persuasive reuse was found in these captures under this decoder and locked model.

Do not say:

> The games share no code.

## Presentation

A report should contain:

- corpus provenance and hashes;
- locked configuration/calibration identity;
- aggregate primary metrics;
- sensitivity table;
- family accounting;
- one side-by-side representative per family;
- semantic reason for each verdict;
- control comparison;
- capture/CPU/banking limitations;
- direction/authorship caveat.

In side-by-side output, do not force unlike instructions onto one row. The bundled renderer expands negatively scored replacement hunks into one-sided rows by default.
