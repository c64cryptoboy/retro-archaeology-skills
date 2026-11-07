# [Game] oracle-first runtime experiment ledger

Create this only after the static-first admission gate identifies behavior that genuinely needs runtime evidence. One row is an experiment contract, not merely a chronology entry.

## Admission context

- **Static accountability artifact:**
- **Parser/dispatcher map:**
- **State read/write and lifecycle/update maps:**
- **Dynamic-code/resource blockers, if any:**
- **Validated emulator/debugger/manual environment:**
- **Known transport, snapshot, media, timing, or completion limitations:**

## Experiment index

| ID | Claim and edition | Why static proof is insufficient | Legal-state provenance | Reachable target path | Controlled difference | Semantic completion oracle | Expected / disconfirming evidence | Status | Evidence |
|---|---|---|---|---|---|---|---|---|---|
| | | | | | | | | planned / valid-pass / valid-fail / excluded / open | |

## Per-experiment contract

### [ID and concise title]

- **Claim, edition, revision, and environment:**
- **Why runtime evidence is required:**
- **Subject and baseline hashes:**
- **Legal-state construction and reread checks:**
- **Parser/control reachability evidence:**
- **Target routine, branch, event, or hardware interaction:**
- **One changed variable/control and comparison subject:**
- **Exact input, timing, and media sequence:**
- **Semantic completion oracle:** Prompt plus parsed result / watched state or write / target breakpoint / bounded terminal condition
- **Observed fields, output, memory ranges, media records, and RNG state:**
- **Expected result:**
- **Disconfirming result:**
- **Justified repetitions/seeds:**
- **Instrumentation and tool limitations:**
- **Contamination risks:** Host keys / stale derived state / illegal fixture / hostile update / warp / media reset / debugger patch / other
- **Exclusion criteria:** Malformed / partial / mistimed / unreachable / stale-state / tool-contaminated / other
- **Cleanup:** Breakpoints, watches, instrumentation, media, warp, and canonical-file restoration
- **Evidence paths and hashes:**
- **Outcome and interpretation:**

## Rules

- Command echo, visible screen change, timeout, or generic READY alone is not semantic completion.
- Never retry timed-out input until screen, queue/buffer, state, and target-path evidence establish that no command was submitted.
- Do not repair an invalid run after the fact and count it as canonical evidence; rerun from a legal baseline.
- Keep excluded runs when useful for chronology, but label them clearly and omit them from behavioral conclusions.
- If infrastructure fails, preserve that failure separately and switch to a validated fallback. Tool behavior is not game behavior.
