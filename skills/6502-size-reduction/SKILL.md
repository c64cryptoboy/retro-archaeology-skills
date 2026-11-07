---
name: 6502-size-reduction
description: Reduce 6502/6510/2A03 machine-code size using deterministic peephole/dataflow rules and LLM-assisted semantic redesign. Use when compacting routines or complete programs, exploiting known register/flag state or liveness, identifying smaller algorithms/representations, preserving deliberate loop unrolling, enforcing interrupt no-slower policy, or refusing cycle-exact raster/audio/loader code.
compatibility: Python 3.10+; optional Retro Debugger for live C64 validation.
---

# 6502 Code-Size Reduction

Use this skill to reduce native 6502-family code bytes under an explicit semantic and timing contract.

This is a **portable LLM-assisted capability** with standalone deterministic tools. Run commands from this skill directory and retain the repository's shared support directory. Give stable signature-based work to deterministic rules; use LLM reasoning for semantics, domains, representation choices, artifact mapping, and image-specific integration. Promote a semantic pattern into a rule only after it recurs and has checkable preconditions and negative tests.

## Mandatory first steps

1. Preserve the original and record size, SHA-256, CPU variant, container, runtime mapping, and entries.
2. Create effort `TODO.md`, `DONE.md`, and `NOTES.md`; for substantial work copy [assets/EFFORT_PLAN_TEMPLATE.md](assets/EFFORT_PLAN_TEMPLATE.md).
3. Explicitly classify timing as `ordinary`, `interrupt`, or `cycle-exact`.
4. Identify visible unrolling, NOP/padding, balanced paths, hardware I/O, raster/audio timing, fast-loader/device loops, interrupt/NMI/DMA observation, and self-modification.
5. For unknown code, load `6502-disassembly`; for semantic routine analysis, load `6502-commenting`. For C64 work, use an emulator or hardware workflow appropriate to the target and use `c64-rom-reference` when applicable.

## Non-negotiable policy

- **Do not roll visibly unrolled loops back into loops by default.** Assume the author paid bytes for an important cycle reason.
- **Interrupt handlers:** accept byte reductions only when every affected path is proven cycle-neutral or faster under the declared model.
- **Cycle-exact code:** refuse automatic transformation. Preserve advanced raster code, Apple II cycle-exact sound, 1541 fast loaders, balanced I/O paths, and suspicious timing padding as opaque islands unless the user supplies a new exact timing specification.
- Preserve NOPs by default.
- Never infer that code is timing-insensitive merely because it is not an interrupt.
- Treat zero page as a platform-owned scarce register file: reserve OS/runtime/special bytes, prove every reference and address-taken use, and account for mainline/IRQ/NMI lifetime overlap before relocating state into it.
- Assume D=0 at program entry. If complete reachable-code inspection finds no decimal-mode setter/import, propagate D=0 throughout the program rather than demanding a local CLD at every ADC/SBC.
- Never claim whole-program equivalence from a peephole rule or bounded tests.
- Do not reject a smaller sequence merely because it clobbers another register or flag. Treat N/V/Z/C, and D under the decimal-policy contract, as locally available condition resources whenever CFG liveness proves no path reads the old value before overwrite. I is hardware-observable through interrupt acceptance and requires a separate asynchronous-interrupt contract even when ordinary CFG liveness marks it dead. First accept direct dead clobbers through CFG-wide liveness. If the clobbered register carries a simple local live range, consider rehoming that value into an available A/X/Y register whose old value is dead across the interval and whose producer/consumers have equivalent addressing modes. Recompute flags, cycles, liveness, and paths after renaming; refuse when joins, calls, indexing, or accumulator-only operations make the reassignment ambiguous.

Read [timing policy](references/timing-policy.md) **before selecting any transformation**. Also read [workflow](references/workflow.md) before a new reduction effort. A tool's `--assert-*` option records your obligation; it does not discover or prove that obligation for you.

## AI/tool responsibility boundary

### Deterministic rules own

- exact opcode signatures;
- forward known-state and backward liveness checks;
- byte/cycle deltas;
- expected-byte/hash guards;
- provenance ledgers and fresh output;
- refusal when a rule's mechanical preconditions fail.

### The LLM owns

- function/input/output/caller understanding;
- deciding whether entry facts, dead values, and timing policies are true;
- recognizing alternate algorithms, formulas, generators, grammars, or domain restrictions;
- judging whether code/data representation can change under exact or specification equivalence;
- image-specific placement, reference repair, and verification design.

Convert consequential LLM conclusions into guards, contracts, cases, or explicit retained assumptions.

## Support ownership

The deterministic tools and tests live in `tools/` and `tests/`. Identical neutral CPU/opcode support is canonical in `../../shared/6502/`, loaded through small Python import adapters that require no filesystem symlinks. No metamorphic tools or private effort files are required. Read [references/support-provenance.md](references/support-provenance.md) for provenance and retained third-party licensing.

## Workflow

1. **Map:** establish exact code/data boundaries, all entries/references, I/O, stack, banking, SMC, timing islands, and available/reclaimable bytes.
2. **Classify timing:** ordinary, interrupt no-slower, or cycle-exact refusal.
3. **Inventory candidates:** deterministic signatures first; then semantic/domain opportunities.
4. **Protect intent:** mark unrolled loops, padding, balanced paths, and opaque timing regions before selecting reductions.
5. **Apply locally:** use the smallest established rule or a focused bespoke rewrite. Maintain exact byte/cycle/RAM/stack effects.
6. **Integrate:** compact/repack at final addresses and repair every evidenced branch, call, pointer, vector, table, or SMC field.
7. **Verify:** static guards, local differential execution, connected final-address execution, whole-image changed-byte audit, and emulator/hardware checks as applicable.
8. **Report:** original/final sizes and hashes, bytes saved, cycle effects by path, transformed/preserved regions, contracts, failures, and limitations.

See [references/workflow.md](references/workflow.md) and [references/reduction-catalog.md](references/reduction-catalog.md).

## Select the smallest applicable tool

Read [tool map](references/tool-map.md) and the chosen section of [tool selection/examples](references/tool-selection-examples.md) **before running a tool**. All detailed command flags, supported rules and refusal limits are retained there; do not load/run all stages for one local question.

| Proven input / goal | Route | Boundary |
|---|---|---|
| Read-only candidate survey | `tools/scan_reductions6502.py` | Candidates are not approved replacements; recheck entries, liveness and final timing. |
| One documented straight-line block | `tools/reduce6502.py` | No interior entries or code-as-data; no surrounding layout repair. |
| Contiguous all-code region to pack | `tools/compact6502.py` | Must establish complete coverage/incoming-reference obligations; mixed/opaque regions stay outside. SMC (self-modifying code) requires explicit supported field declarations. |
| Integration into the actual image | `tools/integrate_whole6502.py` plus [V2 contract](references/whole-image-integration-v2.md) | Read V2 before writing a manifest. Hash-guard/classify shifted suffixes and declare all callers, pointers, anchors and SMC writers. Multi-stage input must be the exact prior output. |
| Algorithm/domain rewrite or loop-order change | [Reduction catalog](references/reduction-catalog.md) | Explicit equivalence domain, alias/order/observer obligations; not an automatic peephole promotion. |

Do not paper over an unsupported boundary with assertion flags. A region-only result does not prove repaired external references or whole-image equivalence; verification must use final addresses and connected code/data.

## Semantic reduction

The LLM may replace a routine or representation with something smaller when it recognizes stronger meaning than syntax exposes. First distinguish:

- **Exact equivalence:** outputs/state/effects must match for every declared input.
- **Domain equivalence:** a smaller implementation is valid only for evidenced caller inputs or dead outputs.
- **Specification equivalence:** outputs may differ but consumer-visible invariants must hold.

Account for code, constants, workspace, startup/runtime cycles, caching/materialization, I/O order, interrupts, banking, and reference repair. A clever formula that needs a larger runtime scaffold is not a size win.

For counted indexed loops, also check whether a pre-decrement and later `TXA`/`TYA` used only to refresh branch flags can become one tail `DEX`/`DEY`, with indexed base operands biased by one to preserve effective addresses. This is not merely instruction deletion: prove every index and flag use, final accumulator liveness, indexed page-cross timing, and final-layout branch timing. Prefer one-based `DEX/DEY; BNE` for counts through 255; `DEX/DEY; BPL` is valid only when every continuing countdown value stays in `$00-$7F`, limiting the usual zero-based form to at most 128 elements. See the loop-induction section of the reduction catalog.

## Completion criteria

A result is ready for its bounded claim when:

- identity/mapping and selected boundaries are exact;
- timing classification and protected timing islands are explicit;
- no deliberate unrolling was rolled up without separate authorization;
- every deterministic rule's mechanical proof is ledgered;
- every semantic rewrite has an explicit domain/specification contract;
- final placement and references are repaired and audited;
- required differential/connected/live checks pass;
- bytes saved and cycle/RAM/stack effects are reported separately;
- scripts and evidence reproduce the final artifact.
