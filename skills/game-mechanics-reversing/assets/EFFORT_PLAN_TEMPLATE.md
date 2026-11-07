# [Game] full mechanics reversing plan

## Capability and scope

- **Capability form:** Internal skill-guided effort / standalone deliverable if separately approved
- **Goal:**
- **Platform/region/revision:**
- **Media/files and hashes:**
- **Runtime/emulator/hardware:**
- **Modes/difficulties covered:**
- **Original, patched, repaired, cracked, or translated edition:**
- **Repair carrier, if applicable:** Preservation-faithful/in-place / normalized-rebuilt / both separately
- **Automation form, if substantial:** Internal deterministic core with thin adapters / standalone capability if separately approved
- **User-requested exclusions:**
- **Presentation outputs:** Mechanics catalog / walkthrough / article / video / other

## Implementation layers

| Layer | Evidence/input | Applicable specialist workflow | Status |
|---|---|---|---|
| Loader/protection | | | |
| Interpreted/high-level source | | | |
| Native code | | | |
| VM/bytecode | | | |
| Data/resources/maps | | | |
| ROM/hardware/asynchronous behavior | | | |

## Required artifacts

Combine small artifacts when appropriate, but preserve these concerns:

- [ ] Provenance and edition record
- [ ] Early source-unit accountability ledger: every interpreted line/statement and confirmed reachable native instruction understood or explicitly open; every in-scope byte region classified
- [ ] Context-revisit queue for mechanically understood but not yet contextualized source units
- [ ] Static-first runtime admission record: parser/dispatcher, state read/write, lifecycle/update, resource/media, RNG, and runtime-hypothesis maps complete before broad emulation
- [ ] Oracle-first [`RUNTIME_EXPERIMENT_LEDGER_TEMPLATE.md`](RUNTIME_EXPERIMENT_LEDGER_TEMPLATE.md) with legality/reachability, target path, completion oracle, expected/disconfirming evidence, contamination, and exclusion criteria
- [ ] Deterministic semantic regression core before any large runtime matrix, when applicable
- [ ] Action/control catalog
- [ ] State model with write/read coverage
- [ ] Update-order/timing model
- [ ] Entity/item/system mechanics catalog
- [ ] RNG/probability accounting
- [ ] Progression/reachability/irreversibility analysis
- [ ] Lifecycle and save/restore analysis
- [ ] Manual/help/discoverability comparison
- [ ] Defect/exploit/emergent/unreachable catalog
- [ ] Unfinished-feature/remnant ledger (orphan resources, dead producer/consumer pairs, disconnected content, documented-but-absent systems)
- [ ] Unusual-design queue and pre-walkthrough gameplay-purpose hypothesis ledger, including cross-system/state/topology analysis and evidence-labeled intent separation
- [ ] Three-category patch-decision ledger plus later-discussion queue, if fixes are characterized
- [ ] Failure and recovery matrix
- [ ] Coverage matrix and explicit open questions
- [ ] Presenter-discovery ledger, if presentation is planned
- [ ] Edition-specific implementation-aware gameplay tips, if player guidance is planned
- [ ] Chronological walkthrough/script, only after ledger intake

## Evidence standards

- Deterministic source/code proof is sufficient when all relevant control flow and state are known.
- Broad emulator testing begins only after the static-first admission gate. Earlier runtime use is bounded to acquiring dynamic/overlaid/generated code or resolving a specific static blocker, followed by renewed static analysis.
- Runtime confirmation is required for ambiguous integration, initialization, stale state, timing/hardware, media behavior, or player-visible claims; every experiment is oracle-first and invalid/contaminated runs are excluded.
- Every probability must derive from exact code/state where possible; avoid broad sampling when calculation or finite enumeration is available.
- Claims about authorial intent remain qualified unless documentary evidence supports them.
- Original and repaired behavior remain separately labeled.

## Work division

- **Coordinator/canonical-file owner:**
- **Live emulator owner (one at a time):**
- **Independent static audits:**
- **Adversarial completeness review:**
- **Contradiction-resolution process:**

## Milestones

1. [ ] Scope/provenance frozen
2. [ ] Implementation structure established
3. [ ] Source-unit accountability pass complete; every unresolved/context-pending unit is on the revisit queue
4. [ ] Parser/dispatcher, inputs, state reads/writes, lifecycle/update order, resources, and RNG statically inventoried
5. [ ] Static-first runtime admission gate passed; runtime hypotheses and oracle-first preflights written
6. [ ] Deterministic semantic harness established before a large matrix, if applicable
7. [ ] Systems, boundaries, adversarial contexts, and unfinished features audited; unusual-design queue populated
8. [ ] Source context-revisit queue resolved or explicitly retained as open; unusual-design items receive gameplay-purpose dispositions before final route synthesis
9. [ ] Runtime ambiguities/integration checks resolved or explicitly open; invalid runs excluded
10. [ ] Coverage gate passed within named boundary; implementation-aware tips produced when in scope
11. [ ] Repair categories, carrier, budget, regression, and promotion gates dispositioned, if applicable
12. [ ] Presenter ledger discharged, including unusual-feature alternates/recoveries and intent labels
13. [ ] Walkthrough/script rehearsed and validated; later discoveries reopen affected hypotheses and route assumptions

## Completion boundary

State exactly what “complete” will mean for this effort and list anything it will not cover.
