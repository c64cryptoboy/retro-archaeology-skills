# Delayed checks, patch strategies and transforms

> Read [SKILL.md](../SKILL.md) first. This is the detailed procedure for the routed phase, not an instruction to expand every task. Commands and inline file paths below are relative to the **skill directory**, unless explicitly stated otherwise; Markdown links resolve from this reference.

## Phase 7 — Search for delayed or repeated checks

Do not stop after bypassing the first boot-time test.

Commercial software may:

- repeat protection during later loads,
- check again between levels,
- load keys required by later data,
- verify drive code remains resident,
- intentionally crash much later after failed authentication,
- use several checks that verify one another.

After identifying one protection path:

- search its callers,
- search references to its result flag,
- search for repeated reads of the same unusual track,
- search for other uploaded drive programs,
- audit ordinary `OPEN`, `LOAD`, `INPUT#`, `GET#`, and command-channel operations,
- resolve dynamically constructed filenames against raw directory bytes,
- inspect obscure one-block files and content-length/suffix sentinels,
- observe all later disk accesses during representative execution.

A later protection layer may be ordinary filesystem I/O rather than another physical-disk probe.

A preservation crack should remove the dependency, not merely postpone failure.

## Phase 8 — Choose the least invasive preservation strategy

Choose based on what the protection actually does.

### Strategy A — Patch only the pass/fail decision

Best when:

- the protection supplies no data needed later,
- the test is isolated,
- success and failure paths are well understood.

Patch the smallest possible decision point.

Preserve all unrelated loader behavior.

### Strategy B — Replace returned authentication state

Best when:

- drive code returns a status/key byte,
- downstream code expects a fixed success value,
- the physical signature itself is otherwise irrelevant.

Prefer returning the authentic success state rather than deleting broad sections of logic.

### Strategy C — Preserve useful loader but remove physical dependency

Best when:

- the custom loader is also the fastloader,
- replacing it would be invasive,
- only one disk-signature portion is problematic.

Modify the authentication path while retaining data loading.

### Strategy D — Replace custom loading with normalized files/sectors

Use when:

- preservation portability matters more than retaining loader behavior,
- custom track data cannot be reliably represented,
- loader replacement is tractable,
- the software's actual payload can be reconstructed accurately.

This is more invasive. Document it clearly.

### Strategy E — Reconstruct decrypted payload

Use when:

- disk/loader protection exists primarily to decrypt code,
- the stable decrypted form can be captured,
- retaining runtime decryption is unnecessary for preservation.

Verify relocation, initialization state, and later self-modification before saving a static decrypted image.

## Phase 9 — Runtime decryption and transformation

Protection loaders often transform bytes after reading them.

Look for loops involving:

- EOR,
- ADC,
- SBC,
- ROL,
- ROR,
- lookup tables,
- byte permutation,
- address-dependent keys,
- self-modifying operands.

When a deterministic transform is found:

1. identify source bytes,
2. identify destination,
3. determine key/state, including relevant flags, mapping, stack contents, outstanding return addresses, and self-modifying operands,
4. determine loop bounds,
5. reproduce the transform,
6. for execution or runnable-artifact claims, compare output against a coherent runtime capture; otherwise label the reproduction conditional and retain missing inputs,
7. continue disassembly on the decoded form without converting predicted code into an execution claim.

It is acceptable to write a small temporary Python program to reproduce a clearly understood transformation.

No general loader-transform simulator is bundled with this skill.  If using an external bounded 6502 simulator, declare:

- starting PC,
- register state,
- memory input,
- stop condition,
- maximum instruction count,
- changed-memory report,
- optional execution trace.

For a reproduced EOR/decode loop, retain the exact transform, inputs, output bounds, and emitted binary identity.  A bespoke transform script is not evidence of general loader support.

A bounded static reproduction can prove a conditional transformation without a new runtime trial when source bytes, instruction semantics, inputs or explicit parameters, and bounds support that claim.  Do not invent missing inputs, select an unobserved seed merely because it produces plausible code, or call predicted bytes an observed state.  Before relying on the result as actually executed output or as validation of a runnable artifact, check it against an appropriate runtime observation.  See [result lifetime and full state](controlled-bypass-evidence.md#track-the-lifetime-and-full-state-of-a-result).

### Calculate read-time XOR coverage before changing covered code

When code bytes or moving operands contribute to an XOR-derived key, write an inclusion table for each stage.  Record the exact bytes read, their values at the time of each read, any repeated reads, the initial accumulator, intentional mutations, and which downstream bytes or decisions consume the result.  Include self-modifying addresses, copies, aliases, and stage boundaries; a static interval alone may not describe the read sequence.

For a fixed XOR read sequence, the change in its result is the XOR of the changes to the values actually read, including any change to the initial accumulator.  Equal changes cancel only when their contributions have the required multiplicity in that same sequence.  Matching load and store operands do not establish cancellation if the span includes only one of them.  If the intervention changes addresses, iteration count, read order, or writes between reads, derive the changed sequence first rather than applying a fixed-coverage formula blindly.

Use bounded controls that distinguish the explanation: a single covered change, a cancelling covered pair, and a change outside the key's coverage but inside a downstream transformed region.  Compare predicted keys and the available output bytes; never invent an unavailable tail.  Keep these XOR-specific properties separate from other checksum or transformation algorithms.

A replacement can preserve local registers and flags yet change a later key because its instruction bytes are read as data.  Conversely, preserving an aggregate XOR does not prove identical code, cycles, full memory, or later behavior.  Call a code-derived decoder a decoder unless an actual acceptance comparison is established; conditional arithmetic is not execution or runnable-artifact validation.

## Phase 10 — Analyze C64 and 1541 together

When the loader uses both CPUs, maintain a paired model.

For each transfer, record:

```text
C64:
  sender/receiver routine
  source/destination address
  byte count
  protocol state

1541:
  sender/receiver routine
  source/destination address
  byte count
  disk operation causing the transfer
```

This is especially important when:

- one CPU decrypts code for the other,
- key material crosses the IEC bus,
- drive code is uploaded in stages,
- later drive routines overwrite earlier ones,
- the same memory buffer contains code at one time and disk data at another.

Use timestamps/breakpoint order when necessary.

