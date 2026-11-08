# Scope, structure, source accountability and actions

> Read [SKILL.md](../SKILL.md) first. This is the detailed procedure for the routed phase, not an instruction to expand every task. Commands and inline file paths below are relative to the **skill directory**, unless explicitly stated otherwise; Markdown links resolve from this reference.

## Workflow

### 1. Freeze scope and provenance

- Preserve/hash original inputs where practical.
- Record title, revision, platform, media, boot path, difficulty, emulator/hardware, patches, and exclusions.
- Name the evidence boundary and outputs being pursued.
- When repair or repackaging is in scope, choose and record the carrier architecture early: preservation-faithful/in-place, normalized/rebuilt, or both. Do not let obsolete protection/layout constraints silently govern a normalized edition, and do not let normalization overwrite the archaeological master.
- Decide whether recurring automation is an internal analysis aid or a standalone capability before substantial implementation; prefer one deterministic core with thin adapters.
- Never modify or redistribute the preserved original; work from copies.

### Cross-port hypothesis pass, when comparison is in scope

Use the divergence prior in [SKILL.md](../SKILL.md) to focus investigation, not to prejudge findings.  Shared authorship does not establish identical algorithms; another porter or reconstruction without original source raises the risk further.  Check each implementation independently against both the other ports and author/manual claims, which may describe a design, prototype, or different revision.

- State the leading hypothesis before comparison: which gameplay algorithm may differ, how a plausible discrepancy would affect play, and what would disconfirm it.  Refine the prediction when code reveals a concrete mechanism; do not leave hypothesis-making to the user.
- Compare semantic paths, not just text: signs, indices, discarded results, initialization, update order, guards, numeric/boolean semantics, RNG/ties, tables, and persistence.  A shared outline or matching routine name is not equivalence.
- Separate algorithm differences from supplied data, trained personalities, difficulty, and runtime behavior.  Preserve intentional adaptations as a possible explanation rather than labeling every difference a bug.
- For adaptive AI, distinguish move evaluation, feature/history recording, and training updates.  A reversed reward sign or inconsistent recorded feature supports a prediction of impaired learning; a training-only defect need not affect play with frozen weights.  Keep intended learning benefit, expected defect harm, and measured playing strength distinct.
- Choose the smallest authorized discriminating check.  Static evidence can establish an algorithm difference; a controlled strength comparison needs matched starting weights, training exposure, opponents, and balanced sides, with tie/RNG policy accounted for.  Do not claim a win rate from a defect alone or launch a tournament merely to express a justified hypothesis.  Record contrary evidence and revise the prior when warranted.

### 2. Establish implementation structure

Identify every gameplay-bearing layer: interpreted source, native code, VM/bytecode, scripts, data tables, overlays, resources, ROM/firmware, interrupts, and device behavior.

Use narrower skills in sequence where applicable:

- `6502-disassembly` for structure and code/data classification;
- `6502-commenting` after structure is known;
- `pcode-disassembly` for supported BLITZ, PETSpeed, BASIC-64 and other hosted p-code VMs;
- `c64-rom-reference` for exact C64/1541 ROM behavior;
- `c64-disk-preservation-cracking` when legitimate protection work gates analysis.

Prove source/binary/data correspondence before integrating claims.

### 3. Complete static source-unit accountability before broad runtime testing

Create or adapt [`assets/SOURCE_ACCOUNTABILITY_LEDGER_TEMPLATE.md`](../assets/SOURCE_ACCOUNTABILITY_LEDGER_TEMPLATE.md) near the start—not after the walkthrough or bug shortlist.

For BASIC/interpreted source, account for every linked/reachable line and materially distinct statement, plus hidden/unlinked/DATA/REM units relevant to the loaded image. Record actual language semantics, reads/writes, calls/fallthrough, ROM/hardware/vector effects, lifecycle behavior, and odd or context-dependent constructs. Resolve syntax according to that interpreter: assignment versus comparison, boolean arithmetic, implicit/default variables and arrays, coercion/precision, and evaluation order. Trace every POKE/PEEK/SYS and ask what happens after STOP, END, error, READY, restart, LOAD, and restore.

For native code, use structural disassembly first: do not interpret data as instructions. Then require every instruction in confirmed reachable code to belong to a mechanically understood block/routine, and classify every in-scope byte range as code, data, unused, excluded, or unknown. A semantically annotated disassembly may be the ledger; unexplained instructions, accesses, entries, and regions must remain explicit worklist items.

The first pass may be mechanical with context pending. Revisit those rows after state, scheduler, lifecycle, protection, data, and documentation models exist. The goal is not to predict subjective “interestingness”; it is to make unusual effects visible early and prevent unexplained source from disappearing from scope.

Before broad emulator testing, derive at least:

- input/parser/dispatcher reachability, including duplicate names and intercepted branches;
- material state variables with their writers, readers, initialization, persistence, and derived-value recomputation;
- update/scheduler order, lifecycle entries, resource/media dependencies, and RNG callsites;
- candidate mechanics, defects, unfinished features, boundaries, unusual-design-purpose questions, and the smallest experiments genuinely requiring runtime evidence.

If packed, generated, banked, self-modifying, or externally loaded code prevents static closure, use one bounded runtime capture to expose the missing code/data, add it to the accountability ledger, and resume static analysis. Do not treat exploratory play as a substitute for recovering the implementation surface.

### 4. Inventory actions and parser/control behavior

Start from input readers and dispatchers, not the walkthrough. Enumerate every command/control, alias, abbreviation, mode, timeout, implicit action, invalid path, and hidden/menu input.

For each action determine:

- validation order and commit point;
- resource consumption and state writes, including writes before refusal;
- time/AI/hazard cost and RNG calls;
- feedback accuracy.

#### Mandatory adversarial command-context pass

For command-driven games, test or prove every applicable action with:

- required object carried, stored, local, remote, hidden, destroyed, stolen, and absent;
- required actor/vehicle/target co-located and separated;
- resource full, one, zero, negative, and reserve item carried/stored/dropped;
- initial, repeated, already-completed, and opposite requested state;
- valid, blocked, invalid, missing, and inappropriate target/direction;
- separation by normal movement, forced transition, and restore;
- first, final, and one-beyond-final use.

Check acceptance, premature consumption, remote mutation/teleportation, container equivalence, idempotence, and physical/state-machine invariants. Generate cases from missing guards as well as existing guards.

