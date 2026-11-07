---
name: c64-basic-v2-rnd-analysis
description: Query, explain, and reproduce the exact stock C64 BASIC V2 RND graph, negative-FAC seed mapping, canonical ranks, cycles, basins, and literal reachability. Use for exact RND seeds, periods, fixed points, and component statistics.
compatibility: Python 3.10+ for compact queries; external pinned C64 ROMs for ROM-backed checks; GCC and a POSIX little-endian host for C validation and runners. Retain repository shared support and the sibling ROM-reference skill.
---

# C64 BASIC V2 RND analysis

Use the deterministic tools in `analysis/` to answer exact seed and graph questions without reconstructing the arithmetic or rerunning billions of states.  Compact data, references, tests, and query tools are bundled; ROM binaries and per-state metadata are not.

## Start with a compact query

From this skill directory:

```bash
cd analysis
python3 -B rnd_query.py rank '7e 2a d3 ab c6'
python3 -B rnd_query.py fac-to-seed '9f f1 ea b4 2a'
python3 -B rnd_query.py components
python3 -B rnd_query.py verify-results
```

The fixed-point state has canonical rank **1,708,815,729**.  The supplied negative FAC maps directly to those same five state bytes.  `components` prints canonical cycle, transient, median-depth, maximum-depth, and basin counts; transient medians exclude cycle nodes.  These commands need only Python's standard library and bundled data, not an emulator, ROMs, or full metadata.

FAC is BASIC's floating-point accumulator representation.  FAC arguments above contain an exponent and restored normalized mantissa; the negative sign is understood separately.  RNDX is the retained five-byte generator state, not its printed decimal approximation.

For all 64 negative-FAC preimages of that fixed point:

```bash
python3 -B rnd_query.py preimages '7e 2a d3 ab c6'
```

## Choose the relevant reference

- [Results](analysis/FINAL_REPORT.md): graph inventory, statistics, useful seeds, and a complete small orbit.
- [Seed reference](analysis/SEED_REFERENCE.md): canonical-domain derivation, negative-FAC image and inverse, shell maxima, expression-only proof, integer clock seeds, and `RND(0)`.
- [Reproduction](analysis/REPRODUCE.md): requirements, commands, bounded tests, and the explicit exhaustive-run gate.
- [Validation](analysis/VALIDATION.md): exact transition contracts, differential evidence, metadata layout, restart recovery, and negative controls.
- [Sources](analysis/SOURCES.md): prior work, historical design evidence, attribution, and unresolved ROM-derived-code provenance.
- [External data](analysis/LOCAL_ARTIFACTS.md): metadata size, identity, and verification limits.

Read the relevant proof before making an impossibility claim.  Read all of the reproduction guide before rebuilding, validating against ROMs, or launching a fresh exhaustive run.  A seed query does not authorize a production run.

## Scope and reporting guardrails

1. The canonical closed subset `C` contains **2,936,012,800** states.  The all-valid-negative-FAC image `S` contains **10,745,675,776** distinct states.  `C ⊂ S`, `T(S) ⊆ C`, and `T(C) ⊆ C`; do not replace containment with `T(S)=C`.
2. **547,608,330,240** normalized nonzero negative FAC encodings map into `S`.  Weighting those inputs differs from counting each distinct output state once.
3. State identity includes all five RNDX bytes at `$008B-$008F`.  Canonical rank is a bijective enumeration, not the raw four mantissa bytes.  `S` uses a separate dense 64-bit rank.
4. Positive arguments advance once regardless of magnitude.  Negative arguments replace state through byte reversal, exponent injection, normalization, and rounding.  Zero samples CIA1 hardware and is outside both deterministic graphs.
5. Power-on state `80 4f c7 52 58` belongs to neither `C` nor `S`, has no valid negative-FAC preimage, and enters `C` after one positive advance.
6. The transition is many-to-one, has ramps, and is not a textbook integer LCG.  Never use host floating point as an exact transition or decimal-parser oracle.  The ROM transition assumes normal BASIC arithmetic workspace, including `$0068=0`.
7. FAC, decimal-literal, and expression reachability differ.  A failed literal search is not an impossibility proof.  Detect repeats using exact five-byte equality, not formatted BASIC output.
8. Both populations have the same 15 components, one cycle per component; all 15 cycle lengths happen to differ.  A basin includes its cycle and feeders.
9. Over `S`, maxima remain `mu=58,681`, `lambda=58,078`, and `mu+lambda=116,759`.  `RND(-4.33901453)` is a practical maximizing seed, not the only FAC/state representation across `S`.  `RND(-1)` is a simpler maximum-period seed.  Neither is cryptographically suitable.

Report the population, weighting, cycle inclusion, five-byte state, rank, and ROM identity.  `mu` counts steps to the cycle; `lambda` is its length; `mu+lambda` counts unique internal states before repetition.

## Optional data and validation

Per-state classification requires an external **11,744,051,200-byte (10.9375-GiB)** `metadata.bin` plus its matching completed-run files:

```bash
python3 -B rnd_query.py classify '7e 2a d3 ab c6' --run-dir /path/to/completed-run
```

`C64_RND_RUN_DIR` selects that run; `C64_RND_SHELL_DIR` selects alternate shell aggregates.  If data is missing, report unavailable classification rather than launching production.  The compact expanded-population table remains available at `analysis/scratch/negative-shell-production/final-table.txt`.

ROM-free query tests, from `analysis/`:

```bash
unset C64_RND_RUN_DIR C64_RND_SHELL_DIR
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest -v test_rnd_query
sha256sum -c compact-result-sha256.txt
```

The classification test retains its existing explicit metadata gate.  Full report and transition tests additionally require external pinned ROMs, configured through `C64_ROM_DIR`; consult the reproduction guide.  Missing ROMs are a prerequisite failure, not a reason to alter test expectations or skip rules.

Fresh exhaustive runs need explicit approval, matching ROM hashes, validated restart behavior, a native little-endian filesystem, and at least 15 GiB free disk space (25 GiB preferred).  Recorded canonical and shell runtimes were about 2 hours 22 minutes and 33 minutes, respectively; performance is host-dependent.  Use `run_full_histogram.py` for canonical production, not direct C invocation.

## Provenance

ROM binaries are external.  The bundled `analysis/generated_rnd_cycle.c` and `analysis/scratch/generated_fin.c` are mechanically ROM-derived and retain **unresolved provenance/licensing status pending owner decision**.  Inclusion is not clearance or a new license grant.  Preserve their [attribution and uncertainty notices](analysis/SOURCES.md), the sibling [ROM sources](../c64-rom-reference/references/SOURCES.md), and the repository [notices](../../THIRD_PARTY_NOTICES.md).
