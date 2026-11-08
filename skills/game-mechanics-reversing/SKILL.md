---
name: game-mechanics-reversing
description: Systematically reverse-engineer a game's complete player-visible and hidden mechanics with static-first whole-code accountability across BASIC, native code, bytecode/VMs, scripts, data files, and hardware behavior. Use when auditing commands, controls, state, update order, entities, items, combat, physics, randomness, progression, scoring, persistence, bugs, exploits, unfinished features, unreachable behavior, gameplay-purpose hypotheses for unusual design features, manual claims, cross-port algorithm comparisons, implementation-aware gameplay tips, alternate strategies, recovery paths, or preparing evidence-backed walkthroughs and presenter notes.
---

# Full game-mechanics reversing

Discover and account for mechanics, including hidden systems, boundary behavior and unused/remnant features. **A winning route is not a complete audit.** Scope a narrow question narrowly; for a requested whole-game audit, do not wait for the user to name every hidden mechanic.

## Intake and routing

Record original artifact hashes, title/edition/platform, patches, difficulty, runtime environment, initialization path and exclusions. Never silently combine original/patched editions, warm/cold state, ports or debugger-modified state. Preserve originals; keep title-specific evidence outside reusable skills.

For a substantial audit, read [the audit contract](references/audit-contract.md) and [audit checklist](references/audit-checklist.md), and adapt the [effort plan](assets/EFFORT_PLAN_TEMPLATE.md) and [mechanics catalog](assets/MECHANICS_CATALOG_TEMPLATE.md). Load subsequent references at the phase below, not all at task startup.

| Phase / trigger | Read before that work | Required artifact / gate |
|---|---|---|
| Structure, static accountability, parser/action inventory | [Static discovery](references/static-discovery.md) | [Source accountability ledger](assets/SOURCE_ACCOUNTABILITY_LEDGER_TEMPLATE.md), dispatcher reachability, reads/writes and open questions |
| State/update order, systems/boundaries, RNG, remnants or odd feature purpose | [State, systems and purpose](references/state-systems-and-purpose.md) | State/scheduler model, coverage/remnant ledger and evidence-labeled purpose dispositions |
| Lifecycle, persistence, runtime testing or audit closure | [Validation and closure](references/validation-and-closure.md) | [Runtime experiment ledger](assets/RUNTIME_EXPERIMENT_LEDGER_TEMPLATE.md), semantic oracles, coverage and remaining limits |
| Fixes/restoration actually in scope | [Repair triage](references/repair-triage.md) | Per-candidate user disposition; conservative versus intent-dependent changes |
| Tips, walkthrough, video or presentation | [Player guidance](references/player-guidance-and-presentation.md) plus purpose/closure phases above | [Presenter discovery ledger](assets/PRESENTER_DISCOVERY_LEDGER_TEMPLATE.md), revalidated route/alternatives/recovery |

For read-only extraction from Apple DOS 3.3 `.do` images or Atari DOS 2.0 128-byte-sector ATR images, use the bundled [disk-image readers](references/disk-image-readers.md) before source analysis.  They preserve raw bytes and structural diagnostics, not decoded BASIC or repaired files; keep title-specific images and outputs outside this skill.

Use narrower structure skills before semantics: `6502-disassembly`, then `6502-commenting`; `pcode-disassembly` for hosted VMs; `c64-rom-reference` for exact ROM/hardware contracts; disk preservation when legitimate protection gates access. Optionally hand verified rooms, exits, conditions, and one-way links to a mapping tool or worksheet.  Map drawing does not establish movement semantics.

## Rules that apply even before references are loaded

1. **Static first.** Account for every in-scope source unit and byte region before broad behavioral testing. Early runtime work is limited to a specific blocker/capture, such as exposing unpacked/banked/generated code or proving correspondence; return to static analysis afterward.
2. **Whole-code accountability is mechanical, not line-by-line prose.** Every reachable interpreted statement/native instruction belongs to an understood block or explicit context-pending/open item. Data, unlinked code, unreachable, excluded and unknown regions stay in the ledger.
3. **Actions require adversarial contexts.** Audit aliases/interception, validation/commit order, writes before refusal, resource/time/RNG costs, repeated/boundary use, absent/remote objects and actors, restore and forced movement—not only the canonical route.
4. **Model both writers and readers.** Track initialization, persistence, derived recomputation, scheduler/update order, hardware/interrupts and every RNG callsite. Exact inequalities, overflow and first/final use matter.
5. **Implementation is not intent.** Distinguish documented intended, undocumented coherent, emergent, likely defect, exploit, unfinished/remnant, vestigial/unreachable and uncertain behavior. Defect/remnant labels require corroboration, not aesthetic preference.
6. **Odd features need a purpose pass.** After mechanics/topology are known, examine legal noncanonical states, cross-system interactions, counterfactual removal, costs/risks and disconfirming evidence. Record plausible function separately from documented authorial intent; unresolved is an acceptable disposition.
7. **Runtime is oracle-first.** Before each test declare legal/reachable setup, target path, semantic completion, expected/disconfirming results, contamination risks and retained evidence. READY, timeout, echo or a screen alone does not prove game behavior. Exclude invalid/partial/stale/tool-contaminated runs explicitly.
8. **Stay at the relevant abstraction boundary.** Do not audit firmware/filesystem internals just because the game uses them. Descend only for bypasses, applicable known defects, physical/timing dependencies, material lower-layer error handling, observed corruption or an explicitly in-scope lower-layer deliverable.
9. **Do not expand tests by inertia.** Static proof can settle deterministic complete code/data. Runtime belongs to ambiguous integration, stale state, timing/hardware, RNG or presentation. One coordinator owns a shared emulator; parallel work uses independent static surfaces.
10. **Do not restore fragments automatically.** A missing assignment does not determine intended caps, locality, balance or persistence. New repair findings do not inherit approval. Keep practical player guidance separate from advocacy for patches.
11. **No premature final route.** Feed viable alternate uses, traps and recovery paths into the mechanics/presenter ledgers. Reopen and revalidate affected route state, probabilities and logistics when new interactions emerge.
12. **Supply the working hypothesis.** Do not make the user propose the explanation or stop at “not demonstrated.”  State the leading mechanism-based hypothesis, predicted direction of effect, strongest credible alternative, and smallest discriminating check.  Separate established behavior, expected consequence, and measured outcome.  Intended improvements support an expectation of benefit, not a guarantee; defects that undermine their mechanism support a directional prediction of harm.  Keep checks within the authorized scope.
13. **Expect cross-port divergence.** For 8-bit ports, use the working prior that unintentional differences in gameplay-affecting algorithms are more likely than not, even with the same author.  Different porters, and especially lack of original source, increase that concern.  Test this premise rather than assume algorithmic equivalence from a shared title, design, or author account.  This is a revisable investigation prior, not an established defect or a measured population statistic.  Follow the cross-port pass in [Static discovery](references/static-discovery.md).

## Evidence packet per finding

Record claim; edition/scope; trigger and preconditions; ordered visible/hidden effects; source lines, addresses, table entries or runtime observations; confidence and behavior class; discoverability; strategic consequence; failure/recovery; presentation treatment. For unusual features also record purpose hypotheses, interacting systems and confirming/disconfirming evidence.

When repair/repackaging is in scope, choose preservation-faithful, normalized/rebuilt or both early. Do not let archaeological constraints silently control a normalized edition or overwrite the preservation master.

## Completion and handoff

Close the named boundary with a coverage matrix: source units/bytes; actions/adversarial contexts; state/scheduler; RNG; entities/items/resources/rooms/modes; progression/score/endings; lifecycle/persistence/reachability/recovery; documentation/discoverability; remnants and unusual-purpose dispositions. Mark each covered, not applicable, excluded or open. Scoped repair and presentation ledgers must be complete, with DO/ALT/SHOW/SAY/SKIP dispositions where applicable.

Missing modules, unproved correspondence, unresolved dynamic/indirect code, unavailable material hardware behavior, unknown RNG call order or unsupported intent are explicit stop boundaries. Retain the smallest next check; do not invent certainty. Rendering every byte or finishing the game does not satisfy the audit.
