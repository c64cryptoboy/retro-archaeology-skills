# Timing SID writes when a CIA timer changes pace

Timestamp play calls at entry, not at `call number × nominal timer period`.  Even with an unchanged timer latch, stopped counting adds time between interrupts, and dispatch latency can move an entry without moving the interrupt.

**Align the logs.**  Observe the running player rather than calling it at a rate you choose.  Record the machine clock in cycles per second and use one cycle counter for timer events, play-entry opcode fetches, and SID bus writes.  For each call `i`, keep its entry cycle `E[i]` and its writes in execution order, including repeated writes to the same register.  Attribute writes by call context through return; a write between two entries need not belong to the earlier call.  Keep initialization and unrelated writers separate.  If a separate log has only `(call, write order)`, verify the same run or deterministic replay, first-call anchor, and one-to-one call sequence, including calls with no writes.  Join on call number for entry timing and order only; without a bus cycle or measured within-call offset, the write's exact time is unknown.

**Diagnose a long gap.**  For an interrupt-driven player, pair each timer IRQ assertion `A[i]` with the entry it actually dispatched.  Do not force a pairing for missed or shared IRQs; a polling player may dispatch on underflow without any IRQ assertion.  Compare assertion gaps with the counting period, latch/reload changes, and observed stop/resume intervals.  Then compute latency `L[i] = E[i] − A[i]`: the entry gap is the assertion gap **plus the change in latency**, not plus the whole latency.  For a call that writes, the first write is later by its measured offset `W[i] − E[i]`; it need not be a gate change or an audible attack.

**Worked example.**  [Synthetic cycle log](example.csv), invented 1 MHz clock, 800 counting cycles per period, resume without reload.  From call 1 to call 2:

| Event | Cycles apart | Explanation |
|---|---:|---|
| IRQ assertion | `2944 − 2000 = 944` | 800 counting + `2264 − 2120 = 144` stopped |
| Play entry | `2962 − 2028 = 934` | Latency falls from 28 to 18: `944 + (18 − 28)` |
| First SID write | `2994 − 2044 = 950` | Write offset rises from 16 to 32: `934 + (32 − 16)` |

The first writes are therefore 0.950 ms apart, not 0.800 ms.  The log alone says nothing about audible onset.  For that, measure rendered PCM against a stated onset criterion and time resolution, with the sample origin aligned to the run.

**Decision rule.**  Choose the event the tick represents and the window you will report.  For a complete one-event-per-tick sequence with observed cycles `T[i]`, use an exact uniform clock only if a single period `P` satisfies `T[i] = T[0] + i × P` at every tick in that window.  Otherwise use measured cycle differences divided by the machine clock; where evidence is missing, mark timing unknown.  A uniform IRQ clock does not certify uniform entries or writes.  An average rate can summarize a window, not timestamp its individual events.
