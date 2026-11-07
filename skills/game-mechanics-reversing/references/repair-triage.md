# Repair triage for game-mechanics audits

Read this when fixes, patches, restored content, or repaired editions are in scope.

## Semantic categories

Classify the complete current candidate set within the named audit boundary. Adapt labels to the effort; B1/B2/B3 terminology is optional.

### Conservative correctness

High-confidence defects whose repair restores a violated invariant, documented operation, completed state transition, prerequisite, or plainly intended output with minimal design change. These are recommendations, not automatic authorization.

### Intent-dependent repair

Behavior is inconsistent, defective, or incomplete, but several plausible corrections exist or the choice changes balance, vocabulary, routes, resources, presentation, timing, or compatibility. Explain alternatives and request a decision.

### Expanded or restored edition

Speculative restoration, new mechanics, substantial redesign, save-format changes, unreachable-content activation, or behavior requiring editorial judgment. Keep this separate from ordinary fixes.

### Discussion / preserve-explain queue

Retain coherent oddities, documentation-only discrepancies, uncertain behavior, and findings not yet classified. Being outside the three categories does not mean approved, rejected, harmless, or permanently preserved.

## Candidate record

For every candidate record:

1. shipped behavior and evidence;
2. category and confidence;
3. plausible intended behavior and competing interpretations;
4. exact player-visible and hidden effects of each option;
5. route, balance, save/resource, data, compatibility, code-space, and timing impact;
6. smallest discriminating experiment where evidence remains ambiguous;
7. before/after acceptance tests;
8. explicit user disposition: accepted, rejected, pending, or discussion.

User approval applies only to explicitly named candidates. New findings never inherit an earlier batch decision.

## Carrier architecture and implementation budget

Before implementing accepted repairs, explicitly choose whether each deliverable is:

- a preservation-faithful/in-place patch constrained by historical layout, loader, timing, and media behavior;
- a normalized/rebuilt edition allowed to remove obsolete startup/protection constraints while preserving gameplay semantics; or
- a separately identified expanded/restored edition.

Do not spend time solving an obsolete in-place constraint for a normalized edition, and never overwrite the preservation master with normalized output. Use a deterministic builder whenever interpreted links, relocation, checksums, tables, or resource names can move. For every candidate build record exact byte growth, new variable/array/string allocations, timing-sensitive path changes, memory/resource ceilings, and a conservative release reserve—not merely the apparent gap to the next address.

## Regression and promotion gate

Convert static findings into acceptance cases before broad emulator testing. Prefer semantic fixtures that rediscover moved symbols and variables independently in each edition, reject illegal or parser-unreachable setups, declare expected and permitted differences, and retain raw evidence. Prove one end-to-end case before batching the matrix.

Keep candidate acceptance separate from canonical promotion. Promotion should atomically preserve the superseded artifact, rebuild deterministically, produce a fresh semantic baseline when layout changed, repin hashes, run focused causal-risk controls plus the mandatory suite required by scope, recheck resource/memory gates, and update current authorities. Manual emulator validation is authoritative when required media or hardware integration is not reliably automatable; document that boundary rather than treating automation as inherently stronger.

## Unfinished features

Do not equate every bug with an unfinished feature. Restoration requires evidence of a partial or disconnected system, such as an unused initialized resource, dead producer/consumer pair, computed-but-discarded result, coherent unreachable content, collapsed semantic class, incomplete state machine, or documented-but-absent mechanic.

Record the existing pieces, missing connection, competing interpretations, and restoration scope. Never complete a fragment automatically merely because a likely assignment or branch can be guessed.

## Edition discipline

Keep original and repaired behavior separately labeled in code, evidence, routes, tips, and presentation. A normalized carrier that preserves original gameplay is not the same artifact as the untouched original medium, and neither is the repaired edition.
