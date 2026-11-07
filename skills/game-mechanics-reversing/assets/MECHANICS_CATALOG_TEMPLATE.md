# [Game] mechanics catalog and coverage matrix

## Scope

- **Edition/configuration:**
- **Evidence boundary:**
- **Known exclusions:**
- **Status vocabulary:** covered / not applicable / excluded / open

## Evidence vocabulary

- **Confirmed:** Direct source/code/data proof or controlled runtime confirmation
- **Strong:** Multiple consistent evidence sources; one material ambiguity remains
- **Tentative:** Plausible interpretation needing a discriminating check
- **Unresolved:** Competing explanations remain

## Early source-unit accountability

Use `SOURCE_ACCOUNTABILITY_LEDGER_TEMPLATE.md` or link an equivalent line index/annotated disassembly. Complete the mechanical pass before treating the thematic catalog as mature.

| Layer | In-scope units/bytes | Understood | Context pending | Data/unreachable/excluded | Open | Ledger/annotated evidence |
|---|---:|---:|---:|---:|---:|---|
| Interpreted lines/statements | | | | | | |
| Confirmed reachable native instructions | | | | | | |
| Other byte regions | | | | | | |

Every context-pending/open unit needs a revisit entry with the missing context and smallest next check.

## Mechanics catalog

Use one row per independently useful claim. Split claims when preconditions, editions, or evidence differ.

| ID | System | Claim | Preconditions/trigger | Ordered visible + hidden effects | Evidence | Confidence | Behavior class | Discoverability | Strategy/recovery consequence | Status/open check |
|---|---|---|---|---|---|---|---|---|---|---|
| M-001 | | | | | | | | | | |

Behavior classes: documented intended; undocumented coherent; emergent; likely defect; exploit; vestigial/unreachable; uncertain.

Discoverability: documented; signposted; normally inferable; experiment-only; source/debugger-only; unreachable.

## Unusual-design and gameplay-purpose ledger

Populate the queue during system analysis and disposition it before final walkthrough synthesis. Gameplay function is an evidence-backed interpretation; authorial intent remains a separate claim.

| ID/feature | Why queued | Exact implemented behavior | Legal boundary/noncanonical states | Interacting systems and map distance | Plausible gameplay function(s) | Counterfactual if absent/ordinary | Exact cost/risk/probability/recovery | Supporting evidence | Disconfirming evidence | Purpose disposition/confidence | Intent evidence | Route/presenter impact | Open check |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| P-001 | | | | | | | | | | strong / tentative / atmosphere / remnant-defect / unresolved | documented / unsupported | | |

## Action/update ledger

| Action/input | Context | Accepted/committed? | Resource consumption point | Player effect | AI/physics/time updates | Hazard/attack exposure | RNG calls | Messages | Evidence |
|---|---|---:|---|---|---|---|---|---|---|
| | | | | | | | | | |

## Adversarial command-context matrix

Use for text adventures and other stateful command interfaces. Add rows for expected success and for absent, remote, stored, exhausted, repeated, blocked, and stale/restored contexts; mark nonapplicable axes explicitly.

| Command | Required actor/object/state | Context variant | Expected invariant | Accepted? | Resource/state changed before validation? | Time/AI/hazard cost | Visible result | Hidden result | Classification | Evidence/status |
|---|---|---|---|---:|---|---|---|---|---|---|
| | | carried / stored / room / remote / absent | | | | | | | | |
| | | full / one / zero / negative resource | | | | | | | | |
| | | initial / repeated / opposite / stale state | | | | | | | | |

## State write/read map

| State value | Meaning | Initialization | Writers | Consumers | Save/restore treatment | Derived/UI treatment | Open questions |
|---|---|---|---|---|---|---|---|
| | | | | | | | |

## Entity/item/system matrix

| ID/name | Generic behavior | Special cases | Cross-system interactions | Difficulty/mode differences | Death/removal/persistence | Alternatives | Failure/recovery | Evidence/status |
|---|---|---|---|---|---|---|---|---|
| | | | | | | | | |

## Randomness matrix

| Callsite/event | RNG state/seed | Call timing/order | Mapping/rerolls | Exact probability/distribution | Dependencies | Static derivation | Runtime cross-check | Status |
|---|---|---|---|---|---|---|---|---|
| | | | | | | | | |

## Unfinished-feature and remnant ledger

Do not equate every bug or unused symbol with an unfinished feature. Record corroborating code/data/map/documentation pieces and the missing connection.

| Feature/remnant | Existing pieces | Missing/disconnected piece | Evidence | Classification | Confidence | Player impact | Restoration scope/risk | Disposition/open check |
|---|---|---|---|---|---|---|---|---|
| | | | | confirmed partial / probable remnant / documented absent / coherent simplification / not unfinished | | | | |

## Irreversibility and recovery matrix

| Trigger | Required preparation | Irreversible/delayed effect | Player warning | Failure class | Recovery/retry | Safe demonstration | Evidence |
|---|---|---|---|---|---|---|---|
| | | | | | | | |

## Documentation concordance

| Source/claim | Implemented behavior | Classification | Player can infer actual cause? | Strategic danger/value | Evidence |
|---|---|---|---|---|---|
| | | | | | |

## Implementation-aware gameplay tips (when player guidance is in scope)

Keep tips distinct from patch recommendations and identify exploitation level.

| Tip | Category | Edition | Preconditions/exact input | Actionable result | Hidden cost/risk | Evidence | Repaired-edition difference |
|---|---|---|---|---|---|---|---|
| | practical tactic / useful quirk / overt exploit / implementation trap | | | | | | |

## Patch-decision ledger (when fixes are characterized)

List the complete current set within the stated audit boundary. Do not present selected examples as exhaustive.

| Candidate | Tier | Shipped behavior/evidence | Competing intent interpretations | Proposed behavior/options | Player/route/balance impact | Save/data/compatibility/code impact | Discriminating check | Acceptance tests | User disposition |
|---|---|---|---|---|---|---|---|---|---|
| | conservative / intent-dependent / expanded-restored / discussion | | | | | | | | accepted / rejected / pending |

Use effort-appropriate labels; B1/B2/B3 shorthand is optional. Keep uncertain coherent behavior and documentation-only issues in the separate discussion queue until explicitly classified.

## Coverage closure

| Audit surface | Inventory source | Total/applicable | Covered | N/A | Excluded | Open | Evidence/index |
|---|---|---:|---:|---:|---:|---:|---|
| Interpreted source lines/statements | | | | | | | |
| Reachable native instructions/blocks | | | | | | | |
| In-scope byte-region classification | | | | | | | |
| Source context-revisit queue | | | | | | | |
| Inputs/actions | | | | | | | |
| Material state writers/readers | | | | | | | |
| Update/scheduler paths | | | | | | | |
| RNG callsites | | | | | | | |
| Entities/NPCs/enemies | | | | | | | |
| Items/weapons/resources | | | | | | | |
| Unfinished features/remnants | | | | | | | |
| Unusual-design/gameplay-purpose dispositions | | | | | | | |
| Implementation-aware tips | | | | | | | |
| Rooms/levels/maps/events | | | | | | | |
| Modes/difficulties | | | | | | | |
| Scoring/progression/endings | | | | | | | |
| Death/restart/continue | | | | | | | |
| Save/restore/persistence | | | | | | | |
| Messages/help/manual claims | | | | | | | |
| Dynamic/indirect/overlaid code | | | | | | | |

## Residual unknowns

For each open item, state why current evidence is insufficient and the smallest discriminating experiment or analysis step.
