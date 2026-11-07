# State, systems, remnants and gameplay-purpose hypotheses

> Read [SKILL.md](../SKILL.md) first. This is the detailed procedure for the routed phase, not an instruction to expand every task. Commands and inline file paths below are relative to the **skill directory**, unless explicitly stated otherwise; Markdown links resolve from this reference.

### 5. Build state and update models

Inventory persistent and transient state, then build both:

- **write map:** every material mutation;
- **read map:** every decision, calculation, and display consuming it.

Cover initialization, normal play, exceptional paths, level/room transitions, death, restart, save, and restore.

Reconstruct exact update order across input, action, movement, events, AI, combat, hazards, theft, timers, scoring, death/win checks, rendering, and sound. Account for command turns, frames, interrupts, animation callbacks, and hidden repeated updates.

When the effort needs more than a few runtime cases, build the deterministic semantic core before the matrix: hash-gate subjects; discover symbols/state structurally rather than assuming shared addresses; encode legal setups; calculate resource/memory budgets where patches can move boundaries; and emit machine-readable observations, declared difference budgets, and evidence hashes. Keep emulator, debugger, and manual-operation adapters thin. Batch independent cases only after one end-to-end case proves transport and completion oracles.

### 6. Audit every applicable system and boundary

Use the detailed checklist. Cover every entity, item, weapon, resource, vehicle, room/level, puzzle, hazard, difficulty, score source, ending, and persistence path—not representative examples only.

Prove boundaries: zero/one/maximum, overflow/underflow, exact inequalities, empty/full inventory, alive/dead/removed, first/repeat/final use, one-shot events, and save/restore around mutations.

Maintain an unusual-design queue while auditing: isolated or transient rooms, random transports, asymmetric links, long detours, unusually placed objects, apparently redundant handlers, conspicuous quantities or thresholds, underused resources, themed set pieces, and mechanics with no role in the provisional route. Do not postpone these automatically to presentation cleanup.

Inventory every RNG callsite and derive generator state, call order, mapping, rerolls, bias, and exact probability where possible. Prefer calculation or finite simulation over broad sampling.

### 7. Perform the unfinished-feature/remnant pass

Maintain a dedicated ledger. Search for:

- initialized resources or fields with no consumer/decrement/transfer;
- writes without readers, readers without reachable writers, and discarded calculations;
- incomplete paired operations and state transitions;
- coherent rooms/events/entities/messages/assets with no incoming path or dispatcher;
- fallback handlers made unreachable by earlier interception;
- loaded parser/action distinctions collapsed by execution;
- manual, HELP, demo, UI, or data promises with no integrated mechanic;
- old-version/deleted/debug fragments that corroborate a removed design.

Triangulate evidence across code, data, map placement, documentation, and lifecycle. Distinguish confirmed partial implementation, probable remnant, documented-but-absent behavior, coherent simplification, ordinary bug, and unsupported speculation. Record plausible-looking cases disproved as unfinished.

### 7a. Perform a gameplay-purpose hypothesis pass before final route synthesis

Review every item in the unusual-design queue after the mechanical systems and topology are known. This is structured abductive analysis, not license to tell an unsupported design story.

For each feature:

1. State the exact implemented behavior independently of purpose.
2. Ask what player problem it could solve: progression gate, alternate route, shortcut, escape, recovery, resource sink, tutorial, pacing break, risk/reward choice, replayability, clue delivery, worldbuilding, or deliberate trap.
3. Search legal states outside the provisional winning route, especially boundary states: overloaded or empty inventory, low/high health, exhausted resources, enemies alive or displaced, failed prerequisites, alternate direction of approach, repeated use, hard mode, and recovery after a mistake.
4. Compose it with neighboring systems rather than evaluating it alone. Check map distance and reachability, AI pursuit/parking, item placement, resource thresholds, RNG outcomes, event ordering, scoring, persistence, and later crossings. Use bounded state search or graph analysis when a useful interaction may be several steps away.
5. Apply a counterfactual: if the feature were removed, relocated, deterministic, or replaced by an ordinary connection, which legal player situations, recoveries, or strategic choices would disappear?
6. Derive exact cost and risk for plausible uses, including travel steps, forced attacks/updates, success probability, retry loop, landing/failure states, and whether a simpler strategy dominates it.
7. Seek corroboration from manual/help text, room and object names, nearby rewards/hazards, old versions, messages, and balanced/asymmetric placement. Treat these as evidence of gameplay function, not automatic proof of authorial intent.
8. Record disconfirming evidence and assign one disposition: strong gameplay function, plausible/tentative function, atmosphere/pacing only, remnant/defect, or unresolved with the smallest next check.

A feature may have multiple functions, and a dangerous or dominated option may still be deliberate. Do not require every oddity to have a hidden strategic purpose. The gate is satisfied by a reasoned, evidence-labeled disposition—not by forced certainty.

Create a provisional route early when useful for exposing dependencies, but do not publish or call it final until this pass has fed viable alternatives, traps, and recovery paths into the mechanics and presenter ledgers. If later play or analysis reveals a new interaction, reopen affected purpose hypotheses, route state, and presenter dispositions; iteration is expected, but every revision must be revalidated.

