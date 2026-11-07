# Scope, non-negotiable rules and evidence contract

> Read [SKILL.md](../SKILL.md) first. This is the detailed procedure for the routed phase, not an instruction to expand every task. Commands and inline file paths below are relative to the **skill directory**, unless explicitly stated otherwise; Markdown links resolve from this reference.

# Full game-mechanics reversing

Use this skill to discover and account for a game's mechanics rather than stopping after a winning route, major routines, or obvious bugs.

## Load only the detail needed

For a substantial whole-game audit, read [`references/audit-checklist.md`](../references/audit-checklist.md) and copy or adapt [`assets/EFFORT_PLAN_TEMPLATE.md`](../assets/EFFORT_PLAN_TEMPLATE.md), [`assets/MECHANICS_CATALOG_TEMPLATE.md`](../assets/MECHANICS_CATALOG_TEMPLATE.md), and—when runtime evidence is needed—[`assets/RUNTIME_EXPERIMENT_LEDGER_TEMPLATE.md`](../assets/RUNTIME_EXPERIMENT_LEDGER_TEMPLATE.md).

When relevant, also read:

- fixes/restoration: [`references/repair-triage.md`](../references/repair-triage.md);
- tips/walkthrough/video: [`references/player-guidance-and-presentation.md`](../references/player-guidance-and-presentation.md) and [`assets/PRESENTER_DISCOVERY_LEDGER_TEMPLATE.md`](../assets/PRESENTER_DISCOVERY_LEDGER_TEMPLATE.md).

For a narrow question, use this orchestration document without loading every reference.

## Non-negotiable rules

1. **A winning route is not a complete mechanics audit.** It proves one sequence, not alternate commands, boundaries, failure states, persistence, unreachable content, or hidden systems.
2. **Do not wait for the user to know what to ask.** Proactively audit the full action surface, adversarial contexts, unfinished features, and cross-system interactions.
3. **Separate editions and environments.** Never silently combine original/patched releases, ports, difficulties, emulator differences, clean boot, warm restart, restored saves, or debugger-modified state.
4. **Separate evidence from intent.** Implementation proves behavior, not authorial purpose.
5. **Do not restore fragments automatically.** A likely missing assignment does not define balance, locality, caps, persistence, or intended presentation.
6. **Keep player guidance separate from patch advocacy.** A useful quirk or exploit may be accurate without being intended or desirable in FIXED.
7. **Account for every in-scope source unit early.** Do not stop after major routines or route-relevant code. Mechanically understand each interpreted line/statement and each instruction in confirmed reachable native code, or put it in an explicit context-revisit worklist. Classify nonexecuted bytes/lines as data, unreachable, excluded, or unknown rather than silently omitting them.
8. **Static mechanics discovery precedes broad emulation testing.** Complete the static accountability pass, parser/dispatcher map, material read/write map, and runtime-hypothesis ledger before launching a broad command, boundary, or gameplay matrix. Early emulation is allowed only for bounded evidence acquisition such as unpacking, exposing overlays/banks/generated code, proving source/binary correspondence, or resolving a specific static blocker; return to static analysis with the captured material before behavioral testing expands.
9. **Every runtime experiment is oracle-first.** Define a legal/reachable setup, target path, semantic completion condition, expected and disconfirming observations, contamination risks, and retained evidence before execution. Tool timeout, READY, screen appearance, or command echo alone is not proof of game behavior.
10. **Test the relevant abstraction boundary.** Do not audit trusted platform, ROM, operating-system, or filesystem internals merely because the game calls them. Descend below the game's API-visible behavior only when it bypasses the standard layer, a known applicable platform-layer defect exists, it depends on physical layout/timing, it handles lower-layer errors materially, corruption is observed, or that lower-layer artifact is itself an in-scope deliverable.
11. **Do not dismiss an odd design feature because the current route does not need it.** Before final walkthrough synthesis, explicitly ask what player problem each unusual, isolated, asymmetric, random, redundant-looking, or conspicuously placed mechanic might solve under noncanonical but legal states. Test cross-system combinations and counterfactual removal. Separate implemented behavior, plausible gameplay function, and documented authorial intent; retain unresolved purpose as an open question rather than inventing one.

## Evidence contract

For each material finding record:

- claim, edition/scope, trigger, preconditions, and ordered visible/hidden effects;
- source lines, routine/address, data entry, trace, watch, or controlled experiment;
- confidence and behavior class;
- player discoverability, strategic consequence, failure/recovery, and presentation treatment;
- for unusual or conspicuously placed features, gameplay-purpose hypotheses, supporting/disconfirming evidence, interacting systems, and intent confidence.

Behavior classes:

- documented intended;
- undocumented but coherent;
- emergent;
- likely defect;
- exploit;
- unfinished/remnant;
- vestigial/unreachable;
- uncertain.

Use “likely defect” or “unfinished” only with evidence such as contradictory documentation, wrong variable/index, missing guard, stale state, dead producer/consumer pair, computed-but-discarded value, initialized-but-unused resource, disconnected coherent content, or violated invariant.

Static proof is sufficient when complete code/data deterministically establishes behavior. Use runtime evidence for ambiguous integration, initialization, timing/hardware, stale state, RNG validation, or player-visible presentation.

