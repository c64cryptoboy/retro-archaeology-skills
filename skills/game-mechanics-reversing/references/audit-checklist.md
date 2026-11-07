# Full game-mechanics audit checklist

Use this as a coverage index, not as a claim that every category applies to every game. Mark each item covered, not applicable, excluded, or open, and attach evidence locations.

## 1. Provenance and execution environment

- Exact title, release, revision, region, platform, and difficulty
- Original media/file hashes and working-copy hashes
- Crack, trainer, patch, translation, repair, emulator patch, or save modification
- Boot/load chain, overlays, dynamically loaded modules, and external resources
- Emulator/core/version and hardware-relevant settings
- Cold-boot versus warm-start assumptions
- Source-to-binary correspondence
- Scope exclusions and requested presentation goals
- If repair/repackaging is in scope: preservation-faithful/in-place versus normalized/rebuilt carrier architecture, with the archaeological master kept separate
- If substantial automation is in scope: internal analysis aid versus standalone capability, with one canonical deterministic core rather than duplicated adapters

## 2. Implementation layers

- Interpreted source and tokenization/link structure
- Native CPU code and code/data boundaries
- VM/interpreter and bytecode boundaries
- Scripts, compiled modules, generated code, and plugins
- Maps, tables, object databases, dialogue, and message resources
- Compression, encryption, relocation, self-modification, and overlays
- ROM/firmware calls and shared library behavior
- Interrupts, raster callbacks, DMA/device behavior, and asynchronous state
- Protection/loader behavior that persists into gameplay

## 2a. Early source-unit accountability gate

Complete this before organizing analysis only around mechanics, bugs, or a winning route. Use `../assets/SOURCE_ACCOUNTABILITY_LEDGER_TEMPLATE.md` or an equivalent indexed/annotated source artifact.

### BASIC and other interpreted source

- Every linked/reachable line and every materially distinct colon-separated statement accounted for
- Hidden/unlinked lines, REM, DATA, trailing records, generated code, and external source modules classified
- Actual interpreter grammar and precedence applied—not syntax assumptions imported from another language
- Assignment versus comparison; true/false representation; coercion; signedness; integer/floating precision; evaluation order
- Implicit/default scalar and array creation, undefined values, name-significance rules, and allocation side effects
- Every POKE, PEEK, SYS, vector hook, ROM call, hardware access, memory reservation, and self-modifying source operation resolved or open
- GOTO/GOSUB/ON/fallthrough/RETURN targets and line-entry assumptions
- Cold/warm start, LOAD/chaining, RUN/CLR, STOP/END/error/READY, restart, death, and save/restore consequences
- Computed-but-discarded values, tautologies, impossible conditions, chained-looking expressions, typo-like operators/indexes, and misleading comments/messages
- One status per line/unit: understood; mechanically understood but context pending; unreachable; data; excluded; or open with a next check

### Native code and byte regions

First establish code/data boundaries with the applicable disassembly workflow; never satisfy this gate by linearly disassembling probable data.

- Every in-scope byte range classified as confirmed/probable code, confirmed/probable data, unused/padding, excluded, or unknown
- Every instruction in confirmed reachable code assigned to a mechanically understood basic block/routine
- Inputs, outputs, clobbers, successors, calls, memory effects, ROM/hardware accesses, banking, timing, and self-modification accounted for at block/routine level
- Any instruction or effect that does not fit the current interpretation recorded explicitly as open
- Indirect, interrupt, callback, banked, overlaid, decoded, generated, and self-modified entries represented in the worklist
- Mechanical/context-pending findings revisited after state, scheduling, lifecycle, protection, data, and documentation analysis

This is an accountability requirement, not a demand for redundant comments such as “LDA loads A.” A semantically annotated disassembly can satisfy instruction coverage.

## 2b. Static-first runtime admission gate

Do not begin broad command, boundary, route, or gameplay emulation until the available implementation has been statically surveyed and the following exist:

- indexed accountability for every accessible interpreted unit and confirmed reachable native instruction;
- classification of all in-scope byte/data/resource ranges;
- parser/input/dispatcher reachability map, including duplicate/intercepted/unreachable selections;
- material state read/write/initialization/persistence map;
- update, scheduler, lifecycle, media/resource, and RNG-callsite models;
- mechanics/defect/remnant candidates converted into explicit runtime hypotheses;
- a context-revisit queue for units that are mechanically understood but not yet semantically resolved.

Permitted early runtime work is bounded evidence acquisition: reveal unpacked/generated/banked/overlaid code, capture dynamically loaded resources, prove source/binary correspondence, or resolve one specific blocker. Add the captured surface to the static ledger and return to static analysis before expanding behavioral tests. Exploratory play, broad input fuzzing, and route rehearsal do not satisfy source accountability.

If more than a few experiments will be needed, establish the deterministic semantic test core before running the matrix:

- hash/provenance gate every edition and baseline;
- discover symbols, variables, arrays, and moved structures semantically rather than sharing raw addresses;
- validate fixture legality and parser reachability;
- model memory/resource budgets affected by patch growth;
- emit machine-readable setup, observation, comparison, exclusion, and evidence hashes;
- keep emulator/debugger/manual adapters thin and separately validated.

## 3. Input and action surface

- Keyboard, joystick/gamepad, mouse/paddle, touch, and device inputs
- Commands, verbs, nouns, aliases, abbreviations, and parser precedence
- Menus, inventory, map, pause, help, status, options, and confirmation prompts
- Context-sensitive controls and mode-specific handlers
- Key combinations, held/repeated input, buffering, debouncing, and input latency
- Idle, timeout, attract-mode, and no-input behavior
- Valid, invalid, blocked, cancelled, ineffective, and partial actions
- Commit/consumption point for actions and resources
- Debug, cheat, service, and hidden input paths

For every action ask:

1. What preconditions are tested, and in what order?
2. When does it become a committed action?
3. Which state changes before a failure message?
4. Does time, AI, physics, or a hazard advance?
5. Does it consume an item, charge, ammunition, fuel, money, or opportunity?
6. Does it invoke RNG?
7. Can a hostile or collision act afterward?
8. Does visible feedback accurately describe the result?

Before running any emulator case, complete an oracle-first preflight:

1. Exact claim, edition/environment, and reason runtime evidence is needed
2. Legal-state provenance and proof the requested parser/control path is reachable
3. Target routine/branch and controlled difference
4. Semantic completion condition; command echo, screen appearance, timeout, or generic READY alone is insufficient
5. Expected and disconfirming outputs/state/writes, observation addresses derived from the active edition, and justified repetition count
6. Instrumentation, media/tool limitations, contamination risks, retained evidence path, and cleanup
7. Exclusion criteria for malformed, partial, mistimed, stale-state, unreachable, or tool-contaminated runs

For command-driven and text-adventure interfaces, also complete an adversarial context matrix where applicable:

- Required object carried / in each accessible container / in the room / remote / hidden / destroyed / absent
- Required actor, vehicle, target, facility, and player co-located / separated / separated by forced movement / separated after restore
- Resource full / one / zero / negative, with reserve item carried / stored / dropped / empty
- Requested state before and after repetition: start/stop, open/close, enter/exit, equip/remove, light/extinguish, lock/unlock
- Valid / blocked / invalid / missing target or direction
- First / repeat / final / one-beyond-final use
- Failure then retry, success then retry, and save/restore between linked actions
- Acceptance, update cost, premature consumption, remote mutation/teleportation, and invariant preservation in every tested cell

Generate these cases from both tested guards and conspicuously absent guards; do not wait for player-route needs to expose them.

## 4. Time and scheduling

- Turn definition and accepted-versus-rejected input
- Frame/tick rate and regional timing differences
- Main update loop order
- Interrupt, callback, coroutine, animation, and background schedulers
- Room/level entry and exit ordering
- AI update count and order
- Damage-over-time, poison, suffocation, hunger, temperature, cooldowns
- Spawn/despawn and respawn timers
- Day/night, calendar, fuel, battery, and countdown systems
- Pause, menu, loading, dialogue, cutscene, and inventory time behavior
- Lag, frame skipping, speed dependence, and race conditions
- Multiple updates hidden inside one apparent action

## 5. Player state and resources

- Health, armor, shields, stamina, mana, hunger, status, and caps
- Lives, continues, checkpoints, and respawn state
- Experience, levels, stats, classes, skills, and upgrades
- Inventory capacity, weight, slots, stacks, and derived-value recomputation
- Equipment, weapon tiers, durability, breakage, and repair
- Ammunition, charges, fuel, battery, keys, currency, and consumables
- Storage containers, vehicles, companions, banks, and remote ownership
- Score, bonuses, multipliers, combo state, and high scores
- Temporary buffs/debuffs and cancellation order
- Integer width, signedness, fractional state, overflow, and underflow

## 6. Movement, map, physics, and collision

- Complete map/level graph and conditional transitions
- Coordinates, subpixels, velocity, acceleration, friction, gravity, and caps
- Collision boxes/masks, ordering, one-way surfaces, slopes, and clipping
- Camera, scrolling, wraparound, teleport, doors, ladders, elevators, vehicles
- Entry/exit interception and transient/non-occupiable destinations
- Hidden routes, secret areas, warps, shortcuts, and random exits
- Fall, drowning, crush, out-of-bounds, kill-plane, and rescue behavior
- Weight, inventory, status, or entity-dependent movement
- Physics differences by frame rate, region, character, or difficulty
- Sequence breaks, collision bypasses, and stuck-state recovery

## 7. Entities, AI, and encounters

For every player, enemy, NPC, boss, companion, projectile, and interactive actor:

- Initialization, spawn, placement, activation, and visibility
- State machine and transition conditions
- Movement/pathfinding/target selection
- Perception, aggro, follow, flee, idle, and de-aggro
- Attack selection, hit chance, damage, defense, and status effects
- Collision and invulnerability order
- Health/death/removal/respawn behavior
- Drops, carried items, theft, inventory, and score
- Generic versus entity-specific handling
- Interactions with other entities and background simulation
- Difficulty and progression scaling
- Offscreen, unloaded, invisible, zero-health, or stale-state behavior
- Avoidance, luring, parking, pacifist, stealth, fight, and escape alternatives
- Failed-attempt retry and recovery

## 8. Items, objects, weapons, and interactions

For every object/item:

- Spawn and location rules
- Discovery, visibility, pickup, drop, transfer, storage, theft, and destruction
- Weight/value/score and derived accounting
- Equip/use/read/eat/drink/fire/throw/combine/context actions
- Charges, ammunition, durability, cooldown, and consumption timing
- Generic handler plus explicit special cases
- Valid targets, invalid targets, and side effects on failure
- Use as puzzle solution, combat counter, movement tool, or lure
- Multiple solutions and misleading affordances
- Remote or indirect effects
- Persistence through death, transition, restart, and save/restore
- Missability, duplication, loss, overflow, and softlock potential

## 9. Combat, hazards, and damage

- Initiative and action order
- Accuracy/evasion/block/critical formulas
- Damage rolls, armor/resistance, caps, floors, and overflow
- Weapon/resource validation and consumption order
- Invulnerability frames and multi-hit behavior
- Player and enemy attack frequency
- Escape/run/flee probability and follow-on consequences
- Status infliction, duration, cure, and per-update damage
- Environmental hazards and immunity
- Friendly fire and entity-versus-entity combat
- Death check timing and post-mortem actions
- Noncombat counters and avoidance routes
- Healing formulas, caps, harmful “healing,” rest, and interruption
- Deterministic guarantees versus probabilistic strategies

## 10. Puzzles, dialogue, quests, and one-shot events

- Trigger and precondition order
- First-entry, first-use, and repeat behavior
- Accept/decline/timeout/invalid-response branches
- Required items, knowledge, flags, party members, and state
- Alternate solutions and deceptive solutions
- Dialogue trees, hidden counters, reputation, and relationship state
- Quest start/progress/completion/failure and rewards
- Irreversible choices and ordering dependencies
- Missable clues, rewards, score, and exits
- Rearming/reset behavior
- Failure recovery and delayed unwinnability

## 11. Progression, scoring, difficulty, and endings

- Start-state differences by mode/difficulty/character
- Difficulty effects at every callsite, not just advertised differences
- Level/stage/room unlock predicates
- Score sources, penalties, caps, bonuses, and required totals
- Rank, grade, percentage, completion, and collectible accounting
- Boss/end triggers and ending predicates
- Multiple endings and ending priority
- New-game-plus, loops, credits, and post-ending state
- Hidden completion requirements
- Impossible or mutually exclusive goals
- Whether kills, pacifism, time, continues, or exploits affect outcomes

## 12. Randomness and procedural behavior

- RNG algorithm, state width, seed source, and reset behavior
- Every callsite and call order
- Range conversion, modulo bias, rerolls, and rejection
- Weighted tables and exact probabilities
- Difficulty/state/timing-dependent thresholds
- Random map, spawn, loot, combat, AI, and event behavior
- Deterministic manipulation and replayability
- Save/restore of RNG state
- Dead or duplicate random branches
- Exact enumeration/simulation versus justified sampling

## 13. Lifecycle, death, reset, and persistence

- Cold initialization and uninitialized/default memory assumptions
- New game, restart, warm reset, title return, and mode switch
- Death cleanup, checkpoint restoration, continue, and game over
- Level/room transitions and module reloads
- Save format, checksums, versioning, and serialization extent
- Required state omitted from saves
- Derived values recomputed correctly or incorrectly
- Stale transient state retained after restore
- Password encoding limitations
- High score/configuration/unlock persistence
- Save duplication, rollback, and corruption behavior where in scope
- Original-media/save-media interactions
- Whether the selected emulator/debugger can perform required live media swaps without resetting or lying about attachment success; use a validated manual fallback when it cannot
- Abstraction-boundary decision: ordinary documented filesystem/API use normally needs logical file, close/replace, restore, and surfaced-error validation—not BAM, sector-chain, controller, or firmware auditing
- Lower-layer media internals only when the game bypasses standard APIs, a known defect applies to the exact platform/API path, physical layout/timing matters, lower-layer failures are handled materially, corruption appears, or the filesystem/image itself is an in-scope deliverable

## 14. Interface, feedback, and sensory mechanics

- HUD/status accuracy and refresh timing
- Inventory/stat recomputation caused by display actions
- Hidden state omitted or rounded in UI
- Messages that contradict actual mutations
- Animation lock, cancel windows, and control suppression
- Sound cues with mechanical meaning
- Visibility, darkness, fog, palette, sprite priority, and collision mismatch
- Menus/help/pause that do or do not suspend gameplay
- Accessibility/control options that alter mechanics
- Display mode or hardware timing that changes play

## 15. Documentation and discoverability

- Manual, reference card, box, hint sheet, strategy guide
- In-game help, tutorial, demo, attract mode, dialogue, signs, and item descriptions
- Accurate, incomplete, approximate, misleading, and false claims
- Features documented but absent, or implemented but undocumented
- Advice that is locally useful but globally dangerous
- Causal relationships a normal player can infer
- Mechanics discoverable only through repetition, source, debugger, or unreachable content
- Differences between promotional/demo terminology and final game

## 16. Defects, exploits, emergent behavior, and unreachable content

- Wrong variable/index/table entry or off-by-one
- Sign/width/overflow/underflow and fractional/integer mismatch
- Stale, omitted, duplicated, or incompletely initialized state
- Consume-before-validation and reward-before-failure
- Dead actors that still update, steal, collide, or respawn
- Inventory/weight/score desynchronization
- Sequence breaks and state-machine skips
- Infinite resources, duplication, and remote effects
- Save/restore exploits and inconsistencies
- Parser/control collisions
- Race/timing/frame-rate behavior
- Unreachable rooms, messages, objects, routines, branches, and endings
- Data remnants, disabled features, and transient named states
- Distinction between useful exploit, harmful defect, harmless quirk, and presentation-only archaeology

When bug fixes are being characterized, classify the complete current candidate set—not just prominent examples—into three semantic categories, using effort-appropriate labels:

- **conservative correctness**;
- **intent-dependent repair**;
- **expanded/restored edition**;
- plus a separate **later-discussion / preserve-explain queue**.

For each candidate record evidence, competing intent interpretations, player-visible and hidden effects, route/balance/save/data/compatibility impact, exact acceptance tests, and explicit user disposition. State the audit boundary and do not let decisions on named items silently apply to future findings.

## 16a. Unfinished-feature and remnant audit

- Initialized resource amounts or object fields with no consumer/decrement/transfer
- Write-only state, read-only state, and values computed but never assigned back
- Reachable writers paired only with unreachable readers, and vice versa
- Half-implemented start/stop, enter/exit, open/close, load/fire, refill/consume, equip/use, and save/restore transitions
- Coherent rooms, levels, exits, events, entities, commands, messages, graphics, or audio with no incoming path/dispatcher
- Duplicate/fallback handlers made unreachable by earlier interception
- Loaded parser/action semantic classes whose distinctions are collapsed or ignored
- Manual, HELP, tutorial, demo, UI, or data promises with no integrated mechanic
- Old-version residue, deleted data, debug scaffolding, and neighboring fragments that corroborate removed functionality
- Map placement plus item/resource values that imply a missing connection or range policy
- Explicit separation of confirmed partial implementation, probable remnant, documented-but-absent behavior, coherent simplification, ordinary bug, and unsupported speculation
- Player impact and whether any restoration would be conservative, intent-dependent, or expanded/editorial
- Plausible-looking cases disproved as intentional or representational rather than unfinished

## 16b. Gameplay-purpose hypothesis pass

Complete this before final walkthrough synthesis. Build the intake queue during the mechanics audit rather than trying to remember oddities afterward.

Queue features that are isolated, transient, asymmetric, random, conspicuously placed, unusually costly or generous, apparently redundant, absent from the provisional route, or difficult to explain locally. For each queued feature check:

- exact implemented behavior stated without inferred purpose;
- legal noncanonical and boundary states: overloaded/empty, low/high health, exhausted/full resources, enemies alive/dead/displaced, failed prerequisites, repeated use, alternate approaches, mode/difficulty changes, and recovery states;
- composition with map distance/reachability, AI follow/parking, item placement, resource thresholds, RNG, update order, score, persistence, and later crossings;
- candidate functions: gate, shortcut, alternate route, escape, recovery, resource sink, tutorial, pacing, risk/reward, replayability, clue, atmosphere/worldbuilding, or trap;
- counterfactual removal or relocation: player choices, recoveries, or balance that would disappear;
- exact travel/action cost, forced updates/attacks, success probability, landing/failure outcomes, retries, recovery, and simpler dominating alternatives;
- corroboration from names, messages, nearby content, manual/help, old versions, and structural symmetry/asymmetry;
- supporting and disconfirming evidence;
- disposition: strong function / plausible-tentative function / atmosphere-pacing / remnant-defect / unresolved with smallest next check;
- explicit separation of gameplay-function inference from documented authorial intent.

Use bounded graph or state-space analysis when interaction is not adjacent or state propagates across several steps. Do not force a strategic explanation for every decorative detail, but do not classify a feature as pointless merely because a winning route omits it. Reopen the pass when runtime play or later static work supplies new context.

## 17. Failure and recovery matrix

For every dangerous or irreversible mechanic:

- Preconditions that avoid failure
- Immediate failure result
- Delayed consequence
- Whether the game communicates it
- Retry route and resource cost
- Recovery item/action/location
- Save/checkpoint recovery
- Whether recovery itself advances hazards or AI
- Hard lock, softlock, lost score, lost ending, or merely inefficient state
- Safe separate-checkpoint demonstration plan

## 17a. Implementation-aware gameplay tips

When player guidance is in scope, produce a separate edition-specific tips sheet covering:

- Exact thresholds and compact decision tables
- Efficient resource quantities/durations and hidden action/update costs
- Storage, scoring, theft protection, transport, and remote-counting rules
- Guaranteed strategies, safer alternates, retry, and recovery
- Parser spellings or command order needed to obtain the intended result
- Useful coherent quirks distinct from defects
- Overt/extreme exploits clearly separated from ordinary-play recommendations
- Implementation traps, premature consumption, irreversible ordering, and unwinnable actions
- Original-versus-repaired differences and exploit severity
- Concise actionable wording backed by the mechanics ledger rather than duplicated proof

## 18. Coverage closure

Before closure, verify inventories of:

- Source-unit accountability: every interpreted line/statement and every confirmed reachable native instruction, plus classification of all in-scope byte regions
- Context-revisit queue: every mechanically understood/context-pending or open source unit is resolved or retained with a smallest next check
- Input dispatchers and command/control branches
- State variables and material write/read sites
- Update/scheduler paths
- RNG callsites
- Entity and item IDs/table rows
- Unfinished-feature/remnant ledger, including orphan resources and dead producer/consumer pairs
- Unusual-design queue and evidence-labeled gameplay-purpose dispositions
- Implementation-aware tips sheet when player guidance is in scope
- Rooms, levels, maps, exits, and events
- Modes and difficulty branches
- Scores, deaths, restarts, saves, restores, and endings
- Text/message resources and documentation claims
- Dynamic/indirect/overlaid code still outside static coverage

Record residual uncertainty and the next discriminating experiment. Do not convert an unsearched category into “not applicable.” Confirm that broad runtime testing began only after the static-first admission gate, or document the exact dynamic-code blocker and bounded acquisition used to resolve it.
