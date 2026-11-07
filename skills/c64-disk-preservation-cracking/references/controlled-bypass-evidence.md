# Controlled bypass evidence

Use this procedure when resolving a protection-learning question, choosing a preservation patch, or validating a new carrier.  It complements [loader analysis](loader-and-authentication.md), [patching and transforms](patching-and-transforms.md), and [validation](validation-and-delivery.md); it does not require a new trial for a question already answered.  Keep specimen identities, copyrighted bytes, and title-specific patch recipes in the private effort record.

## Select discriminating targets, not just more titles

Choose a small batch with different mechanisms and a useful next observation: for example, a physical-layout test, a returned decode key, and a repeated-read comparison.  Database labels are selection leads, not proof of the exact edition's protection.  Pin the specimen and inspect its actual consumer before assigning a family or causal explanation.  Stop a lane when its scoped question is answered or its finite budget ends; an analyzed protection, a candidate patch, and a validated bypass are different outcomes.

## Close an understanding-only question

Declare the question and stop condition before expanding the investigation.  Keep a compact evidence card:

- exact specimen identity, represented side or component, and [capture ancestry](media-and-baseline.md#capture-ancestry-and-observation-boundary);
- source bytes and mappings qualified by CPU, load stage, address space, and transformation;
- producer, result shape, transfer or storage, relevant consumer, and failure path;
- observed facts, static derivations, conditional assumptions, and unresolved dependencies;
- the smallest discriminating observation, if one is still needed and safely available;
- the admitted conclusion, excluded claims, and finite stopping decision.

A complete static explanation can close its question without creating a derivative.  An incomplete chain can close as a bounded negative finding, but not as a proved mechanism.  Do not invent a key, repair missing records, or start unrelated tooling just to manufacture a playable artifact.  A new runtime trial is needed only for the execution-dependent claim it would resolve.

## Inspect rejection before testing it

Trace the failure path before deliberately provoking rejection.  It can upload destructive drive code, overwrite raw tracks, wipe host RAM, or reset while the drive continues independently.  A C64 reset does not cancel or prove completion of a drive job.

Use disposable copies, establish an independent write-protection barrier before testing a destructive path, and stop before the failure-mode upload or first destructive operation.  A normal DOS write-protect software check may be bypassed by custom job dispatch; hardware or emulator enforcement is a separate claim requiring evidence.  If safe containment or the required pre-failure stop is unavailable, keep the result static and do not execute that path.  Do not test protection by damaging the preservation master.

## Separate transport, decision, and required state

Build a short dataflow chain:

```text
represented disk behavior -> received bytes/status -> predicate or key
                         -> required initialization/decode effects -> continuation
```

A custom-record checksum can be transport integrity rather than authentication.  Forcing it may accept corrupted data instead of removing a protection dependency.  Preserve strict checksum, truncation, and missing-record refusals until the consumer justifies another interpretation.

The result may be a byte, a decoding table, a pointer, or the drive's ability to accept another command.  Data delivery and a later readiness gate can be separate phases; an unchanged self-modifying operand can leave a receiver spinning without returning a failure code.  Trace the consumer before labeling a transport table or a liveness gate as authentication, and do not infer an actual host failure from the static spin alone.

A branch change alone is insufficient when the result also seeds decoding or controls later transforms.  Identify every relevant result consumer, the authentic success value, overwritten operands, and explicit controller initialization.  When skipping a measurement, distinguish observed sufficiency for a declared load path from unobserved equality of drive registers, head position, or timing.

Patch in the correct representation.  A changed decoded opcode may require compensating encoded-byte changes: in a cumulative-XOR transform, one input change can propagate through the remaining stream.  Decode the entire affected range independently, check that only the intended plaintext changes, and retain checksum effects separately.  Do not write plaintext opcodes directly into encoded media.

Same-length instruction replacement does not mean NOP equivalence.  Derive and, where relevant, observe its accumulator, flags, memory accesses, and later consumers.  A replacement that reads a failure label as data can trigger a read watch without executing the failure routine.

## Track the lifetime and full state of a result

Qualify an address by CPU and stage.  A later upload can replace transport code with authentication code at the same drive address; a later host module can likewise reuse an address with a different contract.  Record which source bytes populate each stage, including any upload tail not backed by recovered bytes.

For a delayed consumer, record the producer, storage location, intervening calls or loads, and required invariants.  A PHA and later PLA show intended storage, not proof that unknown callees preserve SP, the saved byte, or relevant code.  Establish those invariants from code or coherent observations; otherwise keep the equality conditional.

A replay or counterfactual needs the state relevant to its claimed outcome, not just the apparent key: registers and flags, CPU-port and memory mapping, input bytes, overwritten operands, lookup tables, stack pointer, and relevant stack contents.  PLA can supply a decode seed, and outstanding JSR return addresses can become input or accumulate across loops.  Verify source/destination bounds and traversal order.  Equal transformed bytes or the same final accumulator do not establish whole-state equivalence; a later consumer can still distinguish the arms.

Do not replace a measured controller quantity with a similar-looking representation statistic.  Counted sync-pulse width, non-sync byte-ready interval, and stored bit-run length are different observations.  Regional timing patches and environmental inputs such as write protection may feed transport configuration rather than a simple rejection branch.  Preserve or explain those dependencies instead of changing the environment to force a result.

## Interpret checkpoints in execution context

- Distinguish native CPU PCs from bytecode addresses.  For a hosted VM, combine the interpreter fetch, VM base/index or instruction pointer, current opcode, and virtual state.  A data-address read alone does not establish VM execution.
- A shared clear, reset, or transfer helper can serve both ordinary initialization and rejection.  Identify its caller, selected destination, and phase before classifying a stop.
- Record whether the captured predicate is the one that rejected.  An earlier passing iteration plus a later failure-entry stop does not identify the final failing iteration.
- Compare repeated-read buffers using their actual bounds and iteration order.  Exclude adjacent result slots from the buffers.  A first-difference index may be a downstream key, not a Boolean; unequal buffers in an emulator do not by themselves prove physical weak-bit behavior.
- A PRG's load address does not guarantee a linear file-offset map.  A bootstrap can overwrite the KERNAL load pointer, relocate itself, or copy already-modified operands.  Capture the actual stage before applying static address assumptions.

For payload comparisons, distinguish CPU-visible ROM from underlying RAM.  Pause for a coherent capture, use a supported physical-RAM view or a carefully bounded mapping change, restore the original mapping before execution, and record the range and mapping.  Compare complete defined spans with hashes and byte equality, not just a familiar instruction prefix.

## Construct honest paired carriers

Keep the high-fidelity master and build an unpatched control and a minimally changed candidate from the same justified sector interpretation.  Retain an inventory of accepted sectors, duplicate observations, missing slots, error metadata, and the sectors required by identified loading paths.

Physical track placement is not a logical sector ID.  Do not rename a repeated logical header to fill a missing track.  Equal duplicates may support one payload choice; conflicting duplicates require a consumer-supported interpretation or an explicit unresolved gap.  If the target container needs fixed-size slots, mark placeholders and errors honestly -- zero-filled storage is not recovered data.  Required-sector coverage does not prove that every later game path is covered.  Preserve unrelated sectors and filesystem metadata rather than silently repairing them.

Conflicting occurrences can be jointly required protocol inputs, not competing versions from which to choose a winner.  Before collapsing them, trace initialization, each sample's update, the first-stop predicate, and the exit into the consumer.  Preserve the alternatives and their coordinates.  Test repeated samples, reversed order, and first acceptance: cumulative XOR parity is not equivalent to having seen each variant once.  State the admitted input domain; an aggregate match need not identify the complete expected payload outside it.

Retain phase-sensitive state and unchanged context, including self-modified exit opcodes and instructions spanning reconstructed/original boundaries.  Producing the expected page does not alone prove that the original exit transfers into it.  A one-slot-per-ID carrier cannot preserve a required multi-occurrence protocol merely by choosing a valid payload; any adaptation needs a justified transformation and its own scoped validation.  Finite sequence replay does not establish physical selection probabilities, fairness, or eventual completion.

Separate payload changes from error-table changes, and enumerate the exact differences between control and candidate.  After a raw-bit edit, measure the resulting circular representation: a changed run can merge with an adjacent bit or cross the storage boundary, so the number of edited bits need not equal the change in measured gap length.  Stored bit counts are not automatically hardware byte-ready counts.

## Accept only the observed scope

Use comparable starting conditions and record material differences, including extra resets, drive state, instrumentation, and process generations.  An unexplained pause or failed setup is not an observed authentication rejection.  A clean control rejection strengthens causality; an imperfect negative control must not be described as a clean one or erase independently sufficient positive evidence.

A strong bounded initial-load claim combines:

1. Exact master and candidate provenance, with justified changes.
2. The relevant decision and required success effects, with their evidence strength stated.
3. Natural execution from the derived carrier through loading and initialization, rather than a forced PC jump or a restored post-authentication snapshot.
4. Matching defined payload spans and an unchanged final integrity check where available.
5. The expected title or application entry, with the observed screen interpreted correctly.

A title can be sufficient for this scope; it does not establish gameplay, later disk access, saves, other editions, or physical-drive equivalence.  Each carrier needs its own clean-start evidence.  Keep multiple carriers of one title distinct from multiple cracked titles, preserve failed attempts, and stop once the declared claim is supported.  Follow [checkpointing and recovery](checkpointing-and-recovery.md) when an interruption makes the execution history uncertain.
