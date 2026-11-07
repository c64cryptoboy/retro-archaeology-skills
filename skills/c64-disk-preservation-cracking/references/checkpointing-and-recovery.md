# Checkpointing and recovery

Keep a small, durable record so an interrupted investigation can resume without repeating an operation whose outcome is unknown.  This is a recovery procedure, not a provider-restriction workaround or a promise of automatic continuation.  It requires no particular harness, model, emulator, or background scheduler.

## One ledger, bounded attempts

Use the effort's existing state file or task ledger, rather than creating a second competing queue.  Keep the current state first and preserve prior attempts in linked evidence.  Give independently completable experiments stable task IDs and each execution a distinct attempt ID.  Reuse an existing controller when present; do not create recurring loops merely to detect silence.

For each active task, record:

- The authorized question, smallest useful observation, competing predictions, completion condition, and finite time or work budget.
- Status: pending, running, interrupted, blocked, completed, or cancelled.  Record a user hold and its release conditions separately; a background wake cannot override it.
- Last verified result and its evidence path/hash, not just the last intended action.  Distinguish an original baseline, a candidate, and a controlled comparison.
- Relevant input identities: immutable master, disposable working copy, derivative, executable/ROM revision, and address space or memory mapping.
- Before-state and expected after-state for the next consequential action: mounted media, emulator session/generation if available, run/pause and warp state, owned breakpoints, and data that a restart would discard.
- The in-flight action, attempt ID, outcome (verified success, verified failure, or unknown), and the next safe recovery step.  Link the result receipt before advancing the task.

A compact entry can be a table row plus a linked evidence record:

| Task | Attempt | Status | Last verified result | In flight / outcome | Next safe step |
|---|---|---|---|---|---|
| candidate-cold-load | 2 | interrupted | Clean baseline; working-image hash recorded | LOAD issued; completion unknown | Inspect current session and planned stop before sending input |

Record checkpoints before consequential operations, such as loading, patching, disk writes, reset, or process restart, and after their verified results.  Do not checkpoint every register read.  The ledger does not need a duplicate of every tool response: keep large captures and logs separately, with links and identities.  Update the current-state file atomically when practical; preserve the last good record if a write fails.

## Make execution bounds real

Writing a deadline in the ledger does not enforce it while a model turn is delayed or unavailable.  Before resuming a consequential experiment, pre-arm a verified stop and, where supported, an independently enforced cycle, instruction, or time limit.  Check whether a tool's timeout actually stops execution or only stops waiting for a response.  If independent enforcement is unavailable, report that limitation and choose a safe checkpoint or smaller observation; do not run a destructive path that depends on timely agent intervention.

Distinguish load time, emulated progress, agent-held breakpoint dwell, and observation time.  Finding a machine at a planned stop after a long response gap does not reveal when it arrived or prove continuous execution during the gap.  Preserve a missed observation deadline as a procedural deviation, not a timeout failure or an automatically extended budget.  Close the attempt at its recorded scope; any further forward observation needs its own explicit purpose and bound, not an implicit replay or another arm.

## Detect and classify interruptions honestly

A rejected model request may stop an agent turn without undoing earlier tool calls.  An emulator or background worker may continue.  Conversely, a successful transport response is not proof that a requested operation succeeded: inspect returned error text, completion status, and the required observed state before queuing the next action.

Keep separate categories for provider rejection, tool or transport failure, emulator crash or jam, ordinary breakpoint/pause, user cancellation or hold, and an interruption of unknown cause.  A stopped counter or unfinished ledger entry alone does not identify the cause.  Verify counter progress only over a meaningful bounded observation interval; do not turn repeated polling into an unbounded diagnostic loop.

Provider-error capture belongs at the harness/provider boundary when that boundary exposes the event.  The skill cannot observe a backend rejection that never reaches it.  Record a timestamp, task/attempt association if known, error class, source (harness, tool, or user report), and request/event ID when actually available.  Do not invent an ID or a task-level cause.  Never copy credentials, access tokens, or unnecessary sensitive prompt content into the ledger.

Maintain distinct counts for directly observed provider rejections, user-reported occurrences, and unknown interruptions.  Deduplicate repeated delivery of the same event where identity permits.  Missing instrumentation means the total is unknown, not zero; silence does not increment a rejection count.  A user-reported warning can be useful evidence without proving the exact rejected request or classification rationale.

## Resume protocol

1. **Honor authority and holds.**  Read the current task, user hold, and release conditions before acting.  A cancellation stops work; a provider rejection is not permission to evade a restriction.  Clarify legitimate scope or seek support when necessary.  Do not automatically rephrase prompts, change providers or access tiers, or disguise intent to route around a refusal.
2. **Reconcile work already started.**  Inspect outstanding workers, tool receipts, and the emulator's actual state.  Do not infer rollback from a rejected model turn, lost connection, or timeout.  An unknown-outcome disk write, input injection, restart, or load must not be blindly replayed.
3. **Establish the session.**  Check platform registration, responsiveness, current process/session generation when exposed, media, CPU/address space, and owned stops.  Distinguish a legitimate pause from a crash.  A newly spawned process is not evidence that the emulator is ready; a reset or restart invalidates old RAM, breakpoints, and continuation assumptions.
4. **Recover through a supported route.**  If restart is justified, preserve useful evidence first and use an authorized, bounded recovery mechanism.  Do not open a second client against a single-owner endpoint or kill unrelated processes.  Record which state was lost, the restart attempt, and whether its outcome is known.  After a restart timeout, query state instead of immediately issuing another restart.
5. **Re-establish input prerequisites.**  At a BASIC command boundary, require a successful idle/READY wait and the expected visible prompt before queuing commands.  BASIC input-idle alone does not prove direct-mode READY.  For a custom loader or game, use its own verified prompt/checkpoint.  If any setup gate fails, stop the sequence without sending later input.
6. **Create the next attempt deliberately.**  Continue from an observed safe checkpoint, or start a new controlled trial with preserved prior evidence.  Give a retry a reason and a finite bound; do not retry solely because no result was seen.  Keep instrumentation recovery, protection experiments, and validation of a derivative separate.

## Evidence and completion

Retain failed and interrupted attempts, including setup mistakes.  Do not call a candidate a failure if it never validly executed, or call a stalled emulator an observed authentication result.  Record static hypotheses, observed predicates, preserved success effects, and runtime outcomes at their actual strength.

A title screen can establish a bounded bypass when the complete relevant single-load/authentication path and required initialization are evidenced.  Keep that claim separate from whole-game coverage, and investigate relevant later loads, delayed checks, transitions, or save behavior proportionately.  A different carrier, such as a reconstructed D64, needs its own stated validation; success on a patched G64 does not automatically validate the D64.

Before reporting completion, reconcile the ledger with saved evidence and remaining tasks.  A delayed worker or workflow event neither reopens completed work nor completes an unfinished objective.  Report what passed, what remains uncertain, any hold or required owner action, and the next safe step.  No automatic prompt-retry or backend-error-counting feature is implied by this document.
