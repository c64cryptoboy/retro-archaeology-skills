# Reproducing and querying the C64 BASIC V2 `RND()` analysis

This is the operator guide for the bundled portable analysis.  Run these commands from this `analysis/` directory.  Historical plans, chronology, failed trials and large metadata remain separate; they are not package dependencies.  Retained reports describe the original experiments, not a new exhaustive run during packaging.

## Scope and exact result

The classified graph is the closed canonical post-shuffle state domain for repeated positive C64 BASIC V2 `RND()` advances under the normal BASIC arithmetic invariant `$0068=0`.

```text
canonical states:       2,936,012,800  ($AF000000)
functional components:             15
cycle nodes:                    79,440
maximum mu:                     58,681
maximum lambda:                 58,078
maximum mu+lambda:             116,759
```

This denominator is not all five-byte patterns, all positive FAC encodings, all negative inputs, decimal literals, or the `RND(0)` hardware-timer path.  Read `FINAL_REPORT.md` before interpreting the numbers.

## Requirements

For compact queries and post-processing:

- Python 3.10 or newer;
- only the Python standard library.

For the bounded ROM-backed Python smoke tests, also retain the stock C64 BASIC V2
and revision-3 KERNAL ROMs listed below.  These tests do not need a C compiler or
external full metadata.

For the complete test suite, generated-C validation, or runner builds:

- GCC with C11 support on a little-endian system; supplied test/validation helpers explicitly invoke `gcc`;
- a POSIX/Linux-oriented environment for runner paths using `posix_fallocate`, `flock`, and `mmap`; native Windows support is not established;
- the same pinned ROMs.

A fresh exhaustive production run additionally requires approximately 15 GiB free
disk space at minimum (25 GiB is safer), enough time for a multi-hour run, and
explicit operator approval before launching the full sweep.

The retained production run took 8,518.809 seconds on its original host.  Performance is host-dependent.

## ROM installation and identity

ROM binaries are not bundled.  Set `C64_ROM_DIR` to an externally provisioned directory containing the exact `basic.bin` and `kernal.bin` below.  The default directory is the sibling `c64-rom-reference/assets/roms/`; it contains no images until explicitly provisioned.  Read `SOURCES.md` and the repository notices; inclusion of generated C is not clearance or a license grant for ROM material.

```text
basic.bin   size 8192  SHA-256 89878cea0a268734696de11c4bae593eaaa506465d2029d619c0e0cbccdfa62d
kernal.bin  size 8192  SHA-256 83c60d47047d7beab8e5b7bf6f67f80daa088b7a6a27de0d7e016f6484042721
```

Verify before use:

```bash
export C64_ROM_DIR=/path/to/pinned-roms
sha256sum "$C64_ROM_DIR/basic.bin" "$C64_ROM_DIR/kernal.bin"
```

`run_full_histogram.py`, the generator, and ROM-backed tests reject mismatched images.

## Fast path: verify retained results

The default compact-result directory is `scratch/full-production`.  The giant `metadata.bin` is not bundled.  Set `C64_RND_RUN_DIR` (or pass `--run-dir`) to an external completed run for per-state queries.  `C64_RND_SHELL_DIR` selects external shell aggregates.  Check all bundled compact data with `sha256sum -c compact-result-sha256.txt`.

```bash
sha256sum -c reproducibility-sha256.txt
python3 rnd_query.py verify-results
python3 analyze_final_histograms.py scratch/full-production \
  --output /tmp/final-statistics.json
```

`reproducibility-sha256.txt` pins the source, shared support, and test files in this distribution.  The small local import adapters and ROM-directory default are portable packaging support, not changes to the RND algorithms or retained results; the shared implementations are pinned separately in the same manifest.  `compact-result-sha256.txt` independently pins the bundled data.  Neither manifest establishes a fresh exhaustive classification.

`verify-results` requires exactly one manifest entry for each of the six production compact outputs (`checkpoint.bin`, `cycle-components.csv`, `hist-lambda.csv`, `hist-mu.csv`, `hist-total.csv`, and `summary.json`), checks their hashes, and validates the completed checkpoint.  Empty, incomplete, duplicate-entry, and unexpected-entry manifests fail.  It intentionally does not hash the 10.94-GiB metadata file because the historical manifest did not include that hash.  To stream-check every metadata entry, regenerate the component/depth aggregate as described below; the exporter rejects unclassified or invalid entries and verifies the total domain count.

## Common exact queries

All byte arguments are five bytes in big-endian display order.

```bash
# Domain size
python3 rnd_query.py domain

# Canonical RNDX <-> rank
python3 rnd_query.py rank '7e 2a d3 ab c6'
python3 rnd_query.py unrank 1708815729

# Normalized negative FAC -> immediate RNDX seed
# FAC input is exponent plus restored 32-bit mantissa; sign is understood negative.
python3 rnd_query.py fac-to-seed '9f f1 ea b4 2a'

# Every valid normalized negative-FAC preimage of one seed
python3 rnd_query.py preimages '7e 2a d3 ab c6'

# Rank, mu, lambda, and mu+lambda from completed metadata
python3 rnd_query.py classify '7e 2a d3 ab c6'

# Per-component cycle, transient, median-depth, maximum-depth, and basin counts
python3 rnd_query.py components
```

Use `--run-dir PATH` for `classify` and `verify-results` when outputs are elsewhere.  Use `--component-depth PATH` for `components`.

## Sequential integer `RND(-TI)` seeds

The sequential-integer section of `SEED_REFERENCE.md` compares the exact component distribution of the
positive integer clock seeds against the all-valid-negative-FAC state
population.  It reuses the retained canonical metadata and finishes in seconds:

```bash
python3 analyze_ti_seed_prefixes.py \
  --output scratch/ti-seed-prefixes.json
```

Use repeated `--prefix N` options for other inclusive ranges `1..N`.  `TI=0` is
reported separately because `RND(-0)` takes the timer-based `RND(0)` path.  The
defaults include both the conventional final value 5,183,999 and the extra
5,184,000 value exposed for one tick by revision-3 KERNAL `UDTIM`.

## Negative-seed outer-shell frontier analysis

The outer-shell maximum proof in `SEED_REFERENCE.md` determines whether the all-valid-negative-FAC one-step shell changes each component's maximum depth.  It reuses retained metadata and targeted inverse searches; it does not rerun the complete graph.  Set `C64_RND_RUN_DIR` to the matching completed canonical dataset described in `LOCAL_ARTIFACTS.md`, including its external `metadata.bin` and accompanying completed-run files.  The C helpers take this directory as a positional argument; they do not read the environment variable themselves.

```bash
: "${C64_RND_RUN_DIR:?Set this to the matching completed canonical dataset}"
cc -O3 -std=c11 -Wall -Wextra -Werror \
  extract_component_frontiers.c -o extract_component_frontiers
./extract_component_frontiers "$C64_RND_RUN_DIR" \
  scratch/component-frontiers.csv

python3 prepare_outer_shell_targets.py \
  scratch/component-frontiers.csv \
  scratch/component-frontier-intermediates.csv

# The exact ROM-derived generated C is bundled; it can also be regenerated.
cc -O3 -std=c11 -Wall -Wextra -Werror \
  invert_positive_frontiers.c -o invert_positive_frontiers
./invert_positive_frontiers \
  "$C64_ROM_DIR/basic.bin" "$C64_ROM_DIR/kernal.bin" \
  scratch/component-frontier-intermediates.csv \
  > scratch/component-frontier-predecessors.csv

python3 summarize_outer_shell_frontiers.py \
  scratch/component-frontiers.csv \
  scratch/component-frontier-predecessors.csv \
  scratch/outer-shell-frontiers.json \
  --output-csv scratch/outer-shell-frontiers.csv

python3 validate_outer_shell_frontiers.py \
  scratch/component-frontier-predecessors.csv \
  scratch/outer-shell-frontiers.json
```

The first helper streams external full metadata twice but evaluates no transitions.  The inverse helper includes the bundled mechanically ROM-derived generated C; preserve its provenance and licensing-uncertainty notices.

## Complete negative-seed-space statistics

The complete negative-seed statistics in `SEED_REFERENCE.md` expand the population to every distinct state in the all-valid-normalized-negative-FAC image, counting each RNDX state once, and combines its one-step outer shell with the canonical graph.  `RND(0)` and the power-on-only state remain excluded.

The completed run is already retained; do not repeat it merely to print the table:

```bash
cat scratch/negative-shell-production/final-table.txt
sha256sum -c compact-result-sha256.txt
```

A fresh run requires the same pinned ROM and exact generated transition as the canonical runner.  It is restartable and parallel, but evaluates 7,809,662,976 exact outer-state transitions; obtain explicit approval before launching it:

Use the same matching completed canonical dataset for both the C run and the subsequent aggregate analysis:

```bash
: "${C64_RND_RUN_DIR:?Set this to the matching completed canonical dataset}"
cc -O3 -std=c11 -Wall -Wextra -Werror -pthread \
  negative_shell_histogram.c -o negative_shell_histogram

./negative_shell_histogram \
  "$C64_ROM_DIR/basic.bin" "$C64_ROM_DIR/kernal.bin" \
  "$C64_RND_RUN_DIR" scratch/my-shell-run \
  8 1000000 100 0

python3 analyze_negative_seed_space.py \
  "$C64_RND_RUN_DIR/component-depth.csv" \
  scratch/my-shell-run/shell-depth.csv \
  scratch/my-shell-run/summary.json \
  scratch/my-shell-run/final-statistics.json \
  --output-depth-csv scratch/my-shell-run/combined-depth.csv
```

The arguments after the output directory are threads, image states per checkpointable chunk, checkpoint interval in completed chunks, and an optional stop-after-new-chunks limit.  Repeating the same command resumes a compatible checkpoint.  The accepted eight-thread production pass took 1,977.188 seconds after a rejected first attempt was caught by the targeted-frontier cross-check.

## Validation suite

### ROM-free compact query tier

From this directory, the query suite requires no ROMs.  Its existing classification gate reports a skip when external metadata is absent; rejection controls remain active.

```bash
unset C64_RND_RUN_DIR C64_RND_SHELL_DIR
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest -v test_rnd_query
sha256sum -c compact-result-sha256.txt
```

### Bounded ROM-backed smoke tier

With the pinned ROMs and bundled compact data available, the following checks
query behavior, verification rejection controls, aggregate totals, and a few fixed
ROM-parsed literals and transitions.  It neither compiles C nor launches a state
sweep or randomized campaign.  Unsetting the data overrides keeps it on bundled
compact fixtures; the five metadata-dependent tests report explicit skips.

```bash
unset C64_RND_RUN_DIR C64_RND_SHELL_DIR
python3 -B -m unittest -v test_rnd_query test_final_report
```

### Complete suite

With the pinned ROMs, GCC, and the POSIX runner environment available:

```bash
python3 -m unittest -v \
  test_canonical_seed_domain.py \
  test_negative_seed_image.py \
  test_full_rnd_histogram.py \
  test_final_report.py \
  test_rnd_query.py
python3 -m py_compile *.py
```

`test_final_report.py` uses the bundled compact aggregates and visualization example; four tests explicitly skip unless external completed metadata is available through `C64_RND_RUN_DIR`.  The query-classification test has the same explicit gate.  Literal parsing, seed mapping, and the twelve-transition small-orbit check run without that dataset.  `test_negative_seed_image.py` is ROM-backed.  `test_canonical_seed_domain.py` includes one million rank round trips; synthetic full-runner tests use a 1,024-state graph, not production.  This complete suite is intentionally broader than the smoke tier.

Regenerate and differentially test the exact transition oracle (regeneration replaces the generated source, so compare its hash against the package manifest):

```bash
python3 generate_specialized_rnd_c.py
python3 validate_generated_rnd.py --random-cases 128
```

The validator compares generated C with the independent instruction-level Python 6502 execution path.

## Build the standalone runners

Generate the exact transition C from the pinned ROM and compile:

```bash
python3 generate_specialized_rnd_c.py
cc -O3 -std=c11 -Wall -Wextra -Werror \
  generated_rnd_cycle.c -o generated_rnd_cycle
cc -O3 -std=c11 -Wall -Wextra -Werror \
  full_rnd_histogram.c -o full_rnd_histogram
cc -O3 -std=c11 -Wall -Wextra -Werror \
  export_component_depth.c -o export_component_depth
```

Do not substitute `direct_rnd_model.c` for the generated transition.  It is a rejected exploratory approximation and is not an accepted oracle.

## Fresh exhaustive run

Do not run this merely to answer a seed question when completed metadata is available.  A fresh run creates an 11,744,051,200-byte metadata file.

Create:

```bash
python3 run_full_histogram.py scratch/my-full-run create \
  --checkpoint-every 100000000
```

Resume after interruption:

```bash
python3 run_full_histogram.py scratch/my-full-run resume \
  --checkpoint-every 100000000
```

The wrapper verifies ROM and runner hashes, free space, run mode, and launch/resume manifests.  Use a native local filesystem rather than a slow shared/network mount.  Do not use `--sparse` for production.

A complete run emits:

```text
checkpoint.bin
metadata.bin
summary.json
hist-mu.csv
hist-lambda.csv
hist-total.csv
cycle-components.csv
```

## Post-processing and complete metadata validation

```bash
python3 analyze_final_histograms.py scratch/my-full-run \
  --output scratch/my-full-run/final-statistics.json

./export_component_depth scratch/my-full-run \
  scratch/my-full-run/component-depth.csv

python3 rnd_query.py components \
  --component-depth scratch/my-full-run/component-depth.csv

python3 render_histograms.py scratch/my-full-run \
  scratch/my-full-run/rnd-histograms.svg

python3 render_component_depth.py \
  scratch/my-full-run/component-depth.csv \
  scratch/my-full-run/cycle-components.csv \
  scratch/my-full-run/rnd-component-depth.svg
```

`export_component_depth` makes two complete passes over metadata, refuses invalid entries, and checks that aggregate counts equal `$AF000000`.

## Evidence map

- `FINAL_REPORT.md`: statistics, components, useful seeds, and interpretation.
- `SEED_REFERENCE.md`: domain derivation, negative-FAC mapping, shell maxima, literal proof, clock-seed distributions, and timer sampling.
- `VALIDATION.md`: oracle contracts, differential evidence, metadata schema, restart tests, and sampling limitations.
- `SOURCES.md`: lineage, prior work, constant rationale, and unresolved generated-code provenance.
- `LOCAL_ARTIFACTS.md`: external metadata identity and verification limits.

Recorded validation describes the original investigation, not a new exhaustive run for this package.

## Interpretation guardrails

1.  A state is all five `RNDX` bytes `$008B-$008F`.
2.  The canonical key is an enumeration rank; it is not simply `$008C-$008F`.
3.  Positive argument magnitude is irrelevant: every positive argument advances once.
4.  A negative argument replaces state through the byte-reversal/normalization map.
5.  `RND(0)` samples CIA1 timers and is outside the deterministic graph sweep.
6.  The effective transition is many-to-one and has ramps; it is not a textbook integer LCG.
7.  Never use host floating point as an exact transition or decimal-parser oracle.
8.  Distinguish valid negative FAC reachability from one-literal BASIC source reachability.
9.  A functional component contains one directed cycle and all feeder trees in its basin.
10.  Here each observed cycle length identifies one component only because all 15 lengths are distinct and cycle-node divisibility confirmed one cycle per length.
11.  Use exact five-byte equality, not formatted BASIC decimal output, to detect repeats.
12.  Preserve output hashes and denominator definitions with every reported percentage.

## Licensing and redistribution

- ROM binaries are not bundled.  Mechanically ROM-derived `generated_rnd_cycle.c` and `scratch/generated_fin.c` are retained with unresolved provenance/licensing status pending owner decision.  Inclusion is not clearance or a new license grant.  See `SOURCES.md`, the repository notices, and sibling ROM-reference sources.
- Native executables, giant metadata and unrelated commercial software/captures are not included.
- `cpu6502.py` is derived from MIT-licensed ChiptuneSAK work.  Its attribution is in the source header and the license is linked as `CHIPTUNESAK_LICENSE.txt`.
