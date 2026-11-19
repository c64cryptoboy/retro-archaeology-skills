---
name: 6502-forth-reversing
description: Recover how a 6502 Forth runtime executes words, then turn one evidenced word body into a byte-accounted listing and a readable Forth-style interpretation.  Use for suspected threaded code, native and threaded mixtures, stripped dictionaries, and inline parameters.
---

# Read a 6502 Forth word

Find out **who reads the next byte** before deciding what it means.  The same byte can be a 6502 opcode, an execution token, or a parameter.  This is a guided investigation, not a file-format detector or universal decoder.  Start with one caller, one candidate word, and one path back to the caller.

## 1. Establish the execution contract

Record the input identity, CPU, file-to-memory mapping, and any bank, relocation, or modification needed for the bytes to be visible.  Keep CPU program counter (PC), threaded instruction pointer (IP), and the address identifying the current word separate.  Trace the producer and consumer of each.  Use the following observations to distinguish candidate models:

| Candidate | Evidence to look for on the path into a word |
|---|---|
| Native subroutine threading | The CPU fetches a call or tail jump in the body.  Trace the callee's actual return address, including any adjustment past inline data. |
| Direct threading | A dispatcher reads an address from the thread and transfers native control to that address. |
| Indirect threading | The fetched address identifies a code field; another memory read supplies the native entry. |
| Token threading | The dispatcher translates an encoded ID using a table or tests.  Follow the selected entry: another dispatch layer is possible. |

A plausible disassembly, a vocabulary match, or one `JSR` at an entry is not decisive.  Show the native fetch or dispatch sequence and a caller that uses it.  Mark transitions between models locally rather than assigning one model to the whole image.

For the admitted path, record **fetch** (width, byte order, alignment, and IP advance), **entry** (target resolution, body start, and saved continuation), and **exit** (where the continuation comes from and which engine resumes).  Record the data and return stacks separately: location, cell width, growth, cached top, and hardware-stack use where evidenced.  If the word is a leaf, do not infer the convention for nested words from its return.  Record each primitive's effect on stack, registers, memory, and control flow as far as needed for this reading; distinguish a pushed address from a read through it.

## 2. Give each byte an owner

Start at an evidenced entry, not at a string match.  Use a linked header, caller reference, traced fetch, or independent boundary as a cross-check.  For names, distinguish a spelling present in a verified header or matched source from a conventional primitive gloss or an editorial nickname.  Where headers are absent, keep a stable location label such as `word_<bank>_<offset>`; do not reverse a guessed name into evidence of a dictionary.

Keep a ledger: **location and raw bytes | role and consumer | effect | successor(s) | evidence**.  Distinguish a code field, a word's own parameter area, and inline material in its caller.  For a literal, string, table, or pad, identify the reader, width or length rule, and first byte fetched afterward.  A nested word may consume caller data by changing a saved continuation rather than its current IP.  Do not insert alignment or assume that printable bytes are a string.

For `CREATE … DOES>` children, compare two words from the same defining word.  They may share the same native entry stub and behavior pointer while passing **different parameter addresses** to that behavior.  Follow how the address is used: a child can fetch its private byte and emit it into the assembly buffer without returning either the byte or its address.  Compare the caller’s stack and output before and after; changing one child’s parameter in a disposable copy should not change its sibling.  Distinguish emitting an instruction from executing it.

For each branch, record the tested value and polarity, whether it is popped, the operand bytes, signedness or modular rule, units, exact base, and arithmetic yielding **both** taken and fall-through locations where applicable.  Check these against independently established operation starts and the expected path, not just against the range of the body.  An in-range target can land in a parameter; a genuine operation start can still be the wrong destination.

For a counted loop, first identify where the limit, index, and caller's saved return address live.  Record **when** the index increments and whether the test compares for equality, detects a crossing, or tests an ordering.  Runs that stay far from a boundary may not distinguish these.  For example, try a small positive increment from $7FFE toward $8001 on a 16-bit implementation.  On each path, distinguish reading the caller's inline branch cell from merely skipping over it.  In a disposable copy, changing just that target to another valid instruction can distinguish a real operand from an implicit return to the top of the loop.  Check both stacks on exit.  Do not infer the behavior of `+LOOP` or a zero-trip word from `LOOP` alone.

## 3. Produce two readings and state the limit

1. Deliver the raw ledger first.  Account for every byte in the claimed span exactly once per interpretation and mapping.  Label any unowned interval as unresolved.  Show calls, exits, joins, and side effects in execution order; check stack shapes on both sides of a join.
2. Beside it, give a short Forth-style or plain-language rendering keyed to the ledger.  Mark editorial names and notation.  Introduce `IF` or loop syntax only when the lower-level edges justify it.  Keep opaque calls visible.  A known return boundary does not imply a known stack effect, and a static path does not establish that the word ran.
3. If a token, inline width, dynamic target, or continuation is unknown, state precisely what is missing.  Stop following that edge; do not guess a width or restart at the next familiar byte.  Another independently evidenced entry can still be reported separately.  Unsupported defining words, dynamic execution, and changing mappings are not generic fall-through operations.
4. Test a distinguishing prediction and a plausible wrong reading.  If live execution is separately authorized and needed, observe pre-fetch IP, consumed bytes, resolved native PC, mapping, stack change, and resumed IP.  Otherwise label the result static.  Stop at the scoped word or first concrete blocker; one example does not establish a runtime family.

When matching an unnamed retail word to published source, distinguish the state update from a wrapper that calls it.  Both may store the same new state; inspect which one consumes an incoming bound and which product cell survives.  For example, on eight-bit cells, scaling a state of 255 to three choices by taking the high product gives 2; taking the remainder gives 0.  Across all 256 states the two methods have identical bucket counts.  Use a discriminating input and inspect both the stack result and the caller’s branch, not just a constants match, state trace, or histogram.

See [the synthetic worked example](example.md) for the two readings and a small, offline check.  Keep real specimens, word lists, and traces separate from this public skill.
