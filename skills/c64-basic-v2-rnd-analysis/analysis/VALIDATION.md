# Transition and graph validation

This reference records the established oracle contracts and validation evidence.  It does not claim these historical campaigns were rerun for this package.  Current commands, resource gates, and optional prerequisites are in `REPRODUCE.md`.

## Power-on orbit and independent checks

### Result

With the initial `RNDX` state at index zero defined as:

```text
80 4f c7 52 58
```

and one transition defined as a call to the stock ROM routine at `$E0BE` under the normal BASIC floating-point invariant `$0068=0`:

- **on-ramp length (`mu`): 11,793**
- **cycle length (`lambda`): 58,078**
- first repeated-state index: **69,871**
- cycle-entry/repeated state: **`7f 22 77 b9 e3`**

Thus state `x[11793]` equals `x[69871]`.  The preceding state is:

```text
x[11792] = 80 2a c9 73 a3
```

State equality compared all five bytes at `$008B-$008F`.

### Transition-vector checks

The supplied vectors matched the pinned ROM runner:

```text
x[0] = 80 4f c7 52 58
x[1] = 7e 3e 04 7e 4e
x[2] = 7c 40 18 c8 69
x[3] = 80 53 e7 04 89
x[4] = 80 0e 04 0b 97
```

Four actual immediate-mode `X=RND(1)` calls in an emulator produced `x[1]` through `x[4]` exactly.

### Independent checks

1.  The compiled ROM interpreter used Brent cycle detection and reported:

   ```text
   mu=11793, lambda=58078
   ```

2.  The same compiled interpreter used a separate exact hash-table first-repeat pass and reported:

   ```text
   first repeated index=69871
   first seen index=11793
   lambda=58078
   ```

3.  The independently implemented Python 6502 emulator retained every five-byte state in a dictionary.  It also reported:

   ```text
   first repeated index=69871
   first seen index=11793
   lambda=58078
   repeated state=7f 22 77 b9 e3
   ```

4.  The compiled and Python interpreters agreed at transition 10,000:

   ```text
   x[10000] = 7d 57 d3 86 4d
   ```

The Python complete-orbit pass evaluated 69,871 transitions in 122.256 seconds (571.5 transitions/second).  The compiled interpreter's Brent pass evaluated 147,199 counted transitions and 193,925,466 interpreted 6502 instructions.

A five-run benchmark of the optimized C interpreter measured approximately:

- 317,576 sequential `$E0BE` transitions/second over one million calls;
- 261,208 transitions/second including exact hash-table work in the 69,871-state first-repeat experiment;
- 0.267 seconds median for that complete first-repeat experiment.

`throwaway_rom_cycle.c` interprets the original verified ROM instructions.  It is independent of the mechanically generated transition described below.

## Arithmetic workspace contract

### Valid-environment caveat

The ROM multiply path reads arithmetic temporary `$0068` without first writing it during this entry path.  A normal reset has `$0068=0`, and it remained zero through repeated transitions.  Twenty tests with randomized non-ROM RAM and `$0068` forced to zero reproduced the first two supplied vectors; arbitrary `$0068` values did not.

Therefore this result describes `$E0BE` under its normal BASIC floating-point calling invariant, matching actual `RND(1)` behavior.  It does not claim that `$008B-$008F` alone determines the result when the surrounding BASIC arithmetic workspace is deliberately corrupted.

## Generated transition and differential evidence

### Implementation

`generate_specialized_rnd_c.py`:

1. verifies the pinned 8 KiB BASIC and KERNAL ROM hashes;
2. recursively follows the control flow reachable from `$E0BE`;
3. follows both outcomes of conditional branches, direct `JSR` targets and returns, and direct `JMP` targets;
4. emits 365 direct C instruction blocks;
5. preserves 8-bit registers, flags, carry/borrow, zero-page wrapping, the hardware stack, indirect data addressing, and fixed-width overflow;
6. uses no host floating-point operations;
7. refuses the unresolved indirect BASIC error-dispatch jump at `$A437` if reached.

Normal generated execution moves directly between C labels.  It does not fetch and decode a 6502 opcode for every instruction.  Dynamic `RTS` destinations are checked through a generated return-PC dispatch.

`batch_rnd_graph.c` includes the generated transition and classifies multiple starts with one exact shared hash table.  Every newly discovered state is transitioned once, then assigned:

- distance to its cycle (`mu` for that state);
- cycle length (`lambda`).

A later starting point that reaches a classified state reuses the existing result.  If a path closes on itself, its cycle nodes receive distance zero and its prefix is classified in reverse.

### Confirmed reset-seed result

Generated C reproduces the original result exactly:

```text
start                80 4f c7 52 58
mu                   11,793
lambda               58,078
first repeated index 69,871
cycle-entry state    7f 22 77 b9 e3
```

It also reproduces the supplied first transitions and the state at index 10,000.

### Differential evidence

- Generated output is deterministically regenerated and compared byte-for-byte with the retained generated file.
- The supplied first two vectors match.
- Generated Brent and generated exact first-seen-table passes both report `mu=11,793`, `lambda=58,078`.
- FNV-1a digests over every five-byte state matched the opcode interpreter through indices:
  - 0, 1, 2, 3, 4;
  - 100;
  - 10,000;
  - 69,871;
  - 1,000,000.
- The digest through `x[1,000,000]` is `fb9e8c35a3be4c77`.
- 128 deterministic candidate-valid starting encodings matched the independent Python ROM emulator over randomized lengths from 1 through 100 transitions.
- The complete generated first-seen run passes AddressSanitizer and UndefinedBehaviorSanitizer.
- The batch classifier also passes sanitizer validation.
- Clang 18.1.3 at `-O3` reproduces the exact reset-seed result for both the generated transition and batch classifier; GCC 13.3.0 is the primary measured compiler.

The differential sample used “candidate-valid” to mean zero or a positive packed value with exponent `$01-$80` and a clear stored sign bit.  This sampled population is not the canonical-domain proof.

## Batch classifier and limits

### Shared-cache checks

A batch containing the reset seed, its successor, the cycle entry, the cycle-entry predecessor, and a duplicate reset seed produced:

```text
state,mu,lambda
804fc75258,11793,58078
7e3e047e4e,11792,58078
7f2277b9e3,0,58078
802ac973a3,1,58078
804fc75258,11793,58078
```

Only 69,871 unique transitions were evaluated for all five rows together.

A separate 12-start deterministic test classified 206,238 unique states, and every batch answer matched an independent generated Brent run from that start.

### Calling contract and limitations

- `$0068` is forced to zero before unrelated batch transitions, matching the normal BASIC arithmetic invariant.
- State equality compares all five `$008B-$008F` bytes.
- The generated code handles the recursively discovered direct CFG, including alternate arithmetic branches.  It deliberately refuses the indirect BASIC error dispatcher rather than pretending an overflowing/invalid state returned normally.
- The generator does not itself prove that every valid `RNDX` encoding follows only these successful-return paths.
- The batch graph table is an in-memory experimental table with a configurable power-of-two capacity and a 70% load refusal.  Use the direct-indexed full runner, not this batch table, for an exhaustive run.
- This remains a 6502-semantic translation.  It does not express the generator as a proved higher-level integer recurrence.

## Full-runner storage

### Disk and memory design

The full runner uses one direct-indexed 32-bit metadata word per canonical state:

```text
$00000000  unvisited
$FFxxxxxx  active path marker; low 24 bits are path index + 1
$CCxxxxxx  classified; CC=cycle-length class 1..254, low 24 bits are mu
```

For 2,936,012,800 states:

```text
metadata.bin = 11,744,051,200 bytes exactly
             = 10.9375 GiB
```

No successor table, edge list, per-state CSV, or second metadata copy is created.  Successors are computed on demand from the validated generated-ROM C.

Other persistent files are small:

- checkpoint: approximately 1.1 KiB;
- three aggregate histogram CSVs: projected around 1.7 MiB from the 1% result, subject to full-domain maxima;
- cycle-component inventory, summary JSON, launch manifests, hashes, and logs: ordinarily a few MiB or less;
- atomic output temporaries: approximately one additional copy of each small aggregate while replacing it.

Run-specific estimate:

- expected allocated disk: approximately **10.94 GiB plus small outputs**;
- minimum practical reservation: **15 GiB**;
- conservative operational reservation: **25 GiB**.

The launcher requires metadata size plus 2 GiB free before creation.  Resume recovery additionally uses a 367,001,600-byte (350-MiB) cycle-repair bitmap.  Current-path ranks are 32-bit values with a checked 24-bit path-index bound.

## Full-runner algorithm and refusal tests

### Guarded compact limits

The 4-byte layout is lossless while:

- there are no more than 254 distinct cycle lengths;
- `mu` and an active path index fit in 24 bits.

The 1% pilot observed 13 cycle lengths and `maxMu=58,676`.  The real sequential validation observed 12 cycle classes and `maxMu=58,175` after only 101,100 scan ranks.  These are evidence, not assumptions: every packing operation checks its range, and the runner refuses rather than truncating or wrapping if either bound is exceeded.

Cycle length itself remains a full 32-bit value in the checkpoint's class table.  Multiple distinct cycles may share one length class.

### Exact algorithm

For each canonical rank in ascending order:

1.  Skip it if already classified.
2.  Otherwise follow exact generated-ROM successors, marking the current path.
3.  Stop at a classified state or a repeated current-path state.
4.  For a new cycle, register its full 32-bit length durably before using its compact class code.
5.  Classify the complete cycle and unwind the ramp.
6.  Add each newly classified state exactly once to `mu`, `lambda`, and `mu+lambda` histograms.
7.  Count `mu=0` nodes by lambda; exact component count for a length is `cycle_nodes/lambda`.

At successful completion every domain state is classified exactly once, so each histogram must sum to 2,936,012,800.

### Checkpoints and recovery

- Metadata is `MAP_SHARED` and explicitly `msync`ed at checkpoints.
- Histogram, component, summary, and checkpoint files are written through temporary files, `fsync`, and atomic rename.
- SIGINT/SIGTERM set a stop flag; the runner finishes the active path and writes a consistent checkpoint.
- An initial checkpoint is written before the first transition.
- Resume scans metadata as the authority, rebuilds aggregate histograms, and clears interrupted path markers.
- A temporary bitmap visits each already committed cycle once and rewrites its complete cycle metadata.  This repairs interruption during a multi-node cycle commit.
- New cycle-class meanings are atomically checkpointed before metadata uses them.
- Checkpoints carry magic, version, domain, cycle-class table, and checksum; incompatible or corrupted checkpoints are refused.
- Metadata locking refuses concurrent writers.

The summary's `logicalTransitions` equals classified states.  `transitionsThisProcess` can be larger on resume because cycle-repair validation deliberately reevaluates complete cycles.

### Synthetic exact validation

A compile-time 1,024-node synthetic graph has:

- one cycle of length 3;
- one cycle of length 2;
- trees of known depths feeding each cycle.

The following all matched an independent Python all-state oracle byte-for-byte for the three histograms and component inventory:

1. uninterrupted complete run;
2. graceful stop after 123 scans and resume;
3. deliberate `_exit(99)` with active path markers and resume;
4. deliberately simulated partial three-node cycle commit and resume.

Additional refusal test:

- a one-byte-corrupted checkpoint was rejected.

### Compiler and sanitizer validation

- GCC 13.3.0 `-O3 -Wall -Wextra -Werror`: passed;
- Clang 18.1.3 `-O3 -Wall -Wextra -Werror`: passed;
- GCC AddressSanitizer plus UndefinedBehaviorSanitizer on the complete synthetic graph: passed;
- GCC and Clang synthetic aggregate outputs matched;
- 17 focused Python tests passed, including the independent synthetic oracle, restart cases, checkpoint corruption, ROM hash refusal, canonical rank tests, and prior negative-seed tests.

## Sampling and rejected approximations

The deterministic 1% pilot classified 29,360,128 distinct starts and visited 356,723,817 graph states.  Its 13 observed cycle lengths omitted the fixed point and three-cycle; sample histograms were not a complete component inventory.  Canonical means for mu, lambda, and total differed from the pilot by approximately 1.26, 3.28, and 2.02, respectively.  The total median was 71,870 in both.

An ideal full-precision multiply or naively truncated 40-bit product disagreed with the ROM because multiplication and aligned addition preserve byte-level guard behavior.  The rejected `direct_rnd_model.c` is not bundled or accepted as an oracle.  All accepted graph runs use exact generated ROM instruction semantics, not that approximation.
