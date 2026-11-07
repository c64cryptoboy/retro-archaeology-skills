# Player guidance and presentation from mechanics evidence

Read this when producing gameplay tips, walkthroughs, articles, presenter notes, or video plans.

## Pre-route gameplay-purpose gate

Before finalizing tips or a walkthrough, review the mechanics catalog's unusual-design queue. For every isolated, random, asymmetric, conspicuously placed, redundant-looking, or provisionally unused feature, record:

- exact behavior, separate from inferred purpose;
- legal boundary states in which it may become valuable or dangerous;
- interactions with topology, AI, resources, thresholds, RNG, persistence, and nearby content;
- plausible gameplay functions and counterfactual-removal result;
- exact cost, probability, failure, retry, and recovery of any proposed use;
- supporting and disconfirming evidence;
- a confidence-labeled purpose disposition, with authorial intent left unclaimed unless documented.

Use graph/state search when the interaction is several transitions away or depends on propagated state. A provisional route is an analysis tool and may precede this gate; a final player-facing route may not silently bypass it.

## Implementation-aware gameplay tips

Tips are a separate deliverable from bug and patch lists. Derive them from proven implementation behavior even when no defect exists, and identify the edition.

Organize tips by exploitation level:

1. **Strong practical tactics** — exact thresholds, efficient resource values, storage/scoring rules, hidden action costs, guaranteed strategies, and recovery behavior.
2. **Useful shipped quirks** — coherent or low-impact implementation details that provide leverage.
3. **Overt/extreme exploits** — state corruption, underflow, duplication, remote control, sequence breaks, or prerequisite bypasses, clearly unsuitable for ordinary play unless requested.
4. **Implementation traps** — premature resource consumption, misleading feedback, irreversible ordering, unwinnable actions, and unsafe status/menu operations.

Each tip should give:

- edition and prerequisites;
- exact input or compact decision table when useful;
- actionable result;
- hidden update cost, risk, or recovery;
- repaired-edition difference.

Prefer concise “do X before Y” guidance over duplicating the full proof. Do not call leverage intended merely because it is useful, and do not place severe exploits in a clean route merely because they work.

## Presenter-discovery ledger

Before finalizing a chronological presentation, copy or adapt `../assets/PRESENTER_DISCOVERY_LEDGER_TEMPLATE.md`. Intake includes every applicable mechanics finding and every unusual-design purpose disposition, even when the canonical route does not use it. Each receives one disposition:

- **DO** — use in the canonical run;
- **ALT** — document as an alternate strategy or solution;
- **SHOW** — demonstrate from a disposable checkpoint or separate recording;
- **SAY** — narrate without risking or bloating the run;
- **SKIP** — omit with a recorded reason.

A concise walkthrough may omit demonstrations, but the ledger must account for them. Keep a scenic route or checkpoint plan for worthwhile findings that do not belong in the main run.

## Route-step contract

For each material step include, when relevant:

- required state, inventory, equipment, health/resources, score, and trustworthy derived values;
- exact action and hidden update cost;
- immediate and delayed hazards;
- irreversible changes and future-route effects;
- alternate, failure result, retry, and recovery;
- later crossings or cleanup created by the step;
- original-versus-repaired behavior;
- what the audience sees versus what narration must explain.

Delay final route synthesis until command, state, scheduler, irreversibility, unfinished-feature, and gameplay-purpose-hypothesis coverage is substantially complete. Preliminary routes are encouraged when they expose missing dependencies. When later analysis or play reveals a new interaction, reopen affected purpose hypotheses and presenter dispositions, then revalidate route state, logistics, probabilities, prerequisites, recovery, and narration.
