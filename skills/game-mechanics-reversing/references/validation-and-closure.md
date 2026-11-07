# Lifecycle, runtime oracles, coverage and presentation gates

> Read [SKILL.md](../SKILL.md) first. This is the detailed procedure for the routed phase, not an instruction to expand every task. Commands and inline file paths below are relative to the **skill directory**, unless explicitly stated otherwise; Markdown links resolve from this reference.

### 8. Audit lifecycle, reachability, documentation, and recovery

Trace cold boot, new game, transitions, death/continue, warm restart, save/restore, disk/tape swaps, and post-ending state.

Prove reachable, transient, unreachable, irreversible, missable, softlocked, and delayed-failure states. For each dangerous action record avoidance, warning, consequence, recovery, checkpoint strategy, and whether recovery advances hazards.

Compare manual, reference card, HELP, tutorial, demo, UI, and promotional claims with implementation and realistic player discoverability.

### 9. Validate only what needs runtime evidence

Use runtime for ambiguous integration, stale state, timing/hardware, dynamic code, media exchange, player-visible presentation, or a targeted challenge to static interpretation—not merely because emulation is available. Match evidence depth to the claim: for a game using ordinary documented filesystem calls, application-level file contents, closure/replacement behavior, restore behavior, and surfaced errors are normally sufficient. Audit allocation maps, sector chains, controller state, or firmware internals only when the game or deliverable makes them material, including when a known platform/firmware defect applies to the exact standard API path being used.

Before each experiment record:

1. claim, edition/environment, and why static evidence is insufficient;
2. legal state provenance and parser/control reachability;
3. target routine/branch and one controlled difference where practical;
4. semantic completion oracle (prompt plus parsed result, target state/write, breakpoint, or bounded terminal condition), never a generic READY wait when the program may autostart or own input;
5. expected observation, disconfirming observation, watched state/output, and justified repetitions;
6. instrumentation, tool/media limitations, contamination risks, evidence path, and cleanup.

After execution, classify malformed, partial, mistimed, unreachable, stale-state, or tool-contaminated runs as excluded rather than forcing an interpretation. Prefer focused watches, traces, breakpoints, before/after comparisons, raw-state captures, and bounded simulators. If debugger or emulator infrastructure becomes unstable, quarantine that investigation, preserve the failure separately, and use a validated fallback such as offline analysis or manual emulator operation; never report tool failure as game behavior.

One coordinator owns a shared live emulator and canonical files. Parallel work should use independent static evidence surfaces.

### 10. Close coverage explicitly

Before claiming completeness, account for:

- every in-scope source unit and byte region as understood, context-pending, data, unreachable, excluded, or explicitly open;
- every input/dispatch branch and applicable adversarial context;
- material state writers/readers and scheduler paths;
- RNG callsites;
- entities, items, resources, rooms/events, modes, and difficulties;
- progression, score, endings, death/restart, and persistence;
- unfinished/remnant candidates;
- messages and documentation claims;
- unresolved dynamic, indirect, banked, or overlaid code.

Mark each surface covered, not applicable, excluded, or open. Name residual uncertainty and the smallest next discriminating check.

### 11. Produce scope-specific decisions and guidance

If fixes are in scope, use [`references/repair-triage.md`](../references/repair-triage.md). Maintain conservative, intent-dependent, expanded/restored, and discussion categories with explicit per-candidate user disposition. New findings never inherit prior approval.

If player guidance is in scope, use [`references/player-guidance-and-presentation.md`](../references/player-guidance-and-presentation.md). Produce edition-specific practical tactics, useful quirks, overt exploits, and implementation traps separately from bugs.

If a walkthrough or presentation is in scope, complete the gameplay-purpose hypothesis pass and presenter ledger before finalizing the route. Assign every applicable finding DO, ALT, SHOW, SAY, or SKIP, including unusual features whose plausible use belongs only in an alternate or recovery note. Reopen and revalidate the route whenever new mechanics or purpose interactions change logistics, probabilities, prerequisites, or strategic interpretation.

## Stop rather than overclaim

Report an open boundary when artifacts do not correspond, code/data or VM boundaries remain unresolved, dynamic modules are missing, hardware timing is material but unavailable, RNG call order is unknown, or intent lacks evidence.

## Completion gate

A substantial audit is complete only when scope and editions are explicit; every in-scope source unit/byte region is accounted for or explicitly open; implementation structure, actions, adversarial contexts, state/update order, systems, boundaries, randomness, lifecycle, persistence, reachability, failures/recovery, unfinished features, documentation, and discoverability are covered within the named boundary; unusual-design items have evidence-labeled gameplay-purpose dispositions; scoped repair/tips/presentation ledgers are complete; and remaining unknowns are explicit.

Do not call the work complete merely because the game can be finished or every byte has been rendered as code.
