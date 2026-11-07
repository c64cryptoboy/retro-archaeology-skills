---
name: 6502-code-reuse
description: Detect, calibrate, audit, and present probable 6502 machine-code reuse across binaries, RAM/ROM dumps, snapshots, and platforms. Use when comparing 6502/6510/2A03 programs for shared implementation lineage, distinguishing broad reuse from common idioms, adapting AppleWin/VICE/Nestopia captures, running relocation-aware anchor and affine-gap alignment, or producing inspectable side-by-side evidence.
compatibility: Python 3.10+; bundled tools use only the standard library.
---

# 6502 Code Reuse

Use this skill to find and explain shared 6502 implementation structure without requiring literal addresses, a complete code map, or Ghidra.

The tools are deterministic evidence generators, not an automatic plagiarism verdict.

## Core rules

1. Preserve original artifacts and record hashes. Work on copies.
2. Keep commercial inputs, snapshots, extracted binaries, and derived reports local unless redistribution rights are explicit.
3. Treat every all-offset decode start as a candidate boundary.
4. Keep immediate operands literal. Do not scrub changed constants into exact matches.
5. Use relational exact matches as discovery anchors; use shape evidence mainly for extension.
6. Calibrate on a known positive and controls before an unknown target whenever possible.
7. Freeze thresholds and tool hashes before the target comparison. Never retune the primary result after seeing it.
8. Label sensitivity runs separately; they do not replace the locked primary run.
9. Collapse overlapping starts and cloned fingerprint families before counting independent evidence.
10. Resolve every conclusion to original bytes, assembly, operands, gaps, frequency, and context.
11. Separate confirmed facts, likely interpretations, and open questions.
12. Do not infer copying direction, authorship, legal provenance, or direct borrowing versus shared ancestry from similarity alone.

If no suitable known-positive/control corpus exists, run the workflow as **exploratory** and do not claim a calibrated whole-comparison classification.

## Workflow

Read [workflow](references/workflow.md) before a new comparison; it owns the command sequence. Load other detail by the next decision, not all at startup:

| Before you… | Read | Check |
|---|---|---|
| Adapt captures or declare mapped regions | [Manifests/adapters](references/manifests-and-adapters.md) | CPU, base/bank identity, unavailable bytes and mutually exclusive mappings |
| Choose token views, thresholds or interpret alignment | [Normalization/scoring](references/normalization-and-scoring.md) | Literal = exact operands; relational = repeated-reference identities; shape = weaker, identities removed. Immediates remain literal. |
| Promote/reject a candidate or write a lineage conclusion | [Evidence/audit](references/evidence-and-audit.md) | Instruction boundaries, operand roles, enclosing algorithm and confusers |
| Invoke a tool or change configuration | [Tool reference](references/tool-reference.md) | Exact arguments, input/output contracts and lock requirements |

If a CPU opcode/profile, capture bank or required byte region is unsupported, record the omission rather than reinterpret it to make a match. An exploratory result is useful; it must not be relabeled calibrated evidence.

### 1. Define and preserve the corpus

Record:

- exact research question;
- source artifact paths, sizes, and SHA-256 hashes;
- machine/CPU variants and capture state;
- expected known positive, unrelated controls, and target pair;
- overlapping banks, mirrors, unknown bytes, and loaded/unloaded-code limitations.

Do not use the target pair to select thresholds.

### 2. Produce generic region manifests

Run commands from this skill's directory (the directory containing `SKILL.md`). For one raw binary:

```bash
python3 scripts/make_region_manifest6502.py INPUT.bin OUTPUT_DIR \
  --id stable-region-id --base-address 0x8000
```

Bundled adapters support AppleWin YAML snapshots, VICE VSF snapshots, and Retro Debugger/Nestopia snapshots plus the matching iNES ROM. Read [references/manifests-and-adapters.md](references/manifests-and-adapters.md) before using them.

Never combine mutually exclusive banks into one invented address space merely to simplify matching.

### 3. Establish the known-positive signal and controls

Run exact anchors, affine extension, shuffle/random controls, unrelated-real-program controls, and required sensitivity variants. Confirm that:

- the known positive has multiple long, coherent, non-overlapping routines;
- controls are materially weaker;
- a short common idiom remains candidate-only;
- sensitivity changes degrade or strengthen evidence visibly rather than flipping one fragile result.

Read [references/normalization-and-scoring.md](references/normalization-and-scoring.md) when interpreting token views, alignment columns, thresholds, or scores.

### 4. Calibrate and write a pre-target lock

Only lock a passing calibration. `calibrate_reuse6502.py --lock` records the analysis configuration, interpretation thresholds, source calibration hash, and current packaged-tool hashes.

The validated defaults are a starting point, not a license to skip controls on a materially different corpus or CPU profile.

### 5. Run the unknown pair once under the lock

Use `run_locked_reuse6502.py`. Preserve the JSON and Markdown output as the authoritative primary result.

Then run the required k=6/k=10 and 12/20-paired-instruction sensitivity variants as separately named artifacts.

### 6. Audit candidates by fingerprint family

Do not treat every report as independent. Group by seed fingerprint, overlapping location, and internal clones.

For each family:

1. verify likely instruction boundaries and executable context;
2. inspect callers, callees, entry contracts, consumers, and enclosing algorithms;
3. map operand identities and determine whether they retain the same semantic roles;
4. distinguish coherent insertions from arbitrary mismatch pairing;
5. check runtime execution when useful and feasible;
6. optionally scan the complete candidate-selected shape against targets and controls;
7. assign a family verdict with explicit confidence and limitations.

Candidate-selected frequency scans are post-hoc specificity evidence, not calibrated false-positive probabilities.

Read [references/evidence-and-audit.md](references/evidence-and-audit.md) before promoting or rejecting a candidate.

### 7. Report inspectable evidence

Include:

- locked primary classification and configuration hash;
- candidate/probable counts, supporting pairs, unique coverage, and chains;
- sensitivity results without replacing primary evidence;
- family-aware manual verdicts;
- control comparison;
- side-by-side original assembly;
- capture/decoder limitations;
- bounded wording such as “no additional persuasive reuse found in these captures under this method,” not proof of absence.

Render a match with:

```bash
python3 scripts/render_alignment6502.py REPORT.json --match M0001 \
  --left-label "LEFT GAME" --right-label "RIGHT GAME" \
  --format markdown --output alignment.md
```

Supporting pairs share rows. Insertions/deletions and negatively scored replacement hunks use blank opposite cells by default. Use `--pair-differences` only to inspect raw affine columns.

## Evidence classes

Use these labels conservatively:

- **probable shared routine**: passes the locked structural threshold; still requires contextual interpretation.
- **likely shared/adapted skeleton**: manual semantics preserve a coherent operation despite bounded edits.
- **weakly suggestive / unresolved**: structural specificity exists, but operation boundaries or data roles do not align well enough.
- **common/coincidental idiom**: ordinary arithmetic, pointer, table, save/restore, or hardware pattern whose enclosing meanings differ.
- **candidate-only / inconclusive**: one or more candidates but no locked probable routines.
- **no detected reuse under the locked configuration**: no candidates meeting the model; not proof of no historical relationship.

Whole-comparison and candidate-level verdicts are separate. One persuasive small routine does not establish broad codebase lineage.

## Bundled tools

- `scripts/make_region_manifest6502.py` — wrap one raw binary in the generic manifest contract.
- `scripts/extract_applewin_snapshot.py` — AppleWin snapshot adapter.
- `scripts/extract_vice_snapshot.py` — VICE VSF physical-RAM adapter.
- `scripts/extract_retro_nestopia_snapshot.py` — Nestopia state/iNES physical-region adapter.
- `scripts/anchor_scan6502.py` — literal/relational/shape exact-window scan.
- `scripts/exact_anchor_controls6502.py` — deterministic byte, token-order, and random controls.
- `scripts/reuse_align6502.py` — boundary correction, affine local extension, deduplication, chaining, and coverage.
- `scripts/calibrate_reuse6502.py` — calibration gate and generic lock creation.
- `scripts/run_locked_reuse6502.py` — verify hashes/configuration and run the authoritative target comparison.
- `scripts/candidate_signature6502.py` — post-hoc complete-shape subsequence frequency scan.
- `scripts/render_alignment6502.py` — presentation-ready side-by-side alignment.

See [references/tool-reference.md](references/tool-reference.md) for exact commands and output interpretation.

## Tests

Run the self-contained/synthetic suite before relying on a modified package:

```bash
python3 -m unittest discover -s scripts/tests -v
python3 -m py_compile scripts/*.py scripts/tests/*.py
```

The bundled suite is synthetic and requires no commercial data.  See the [worked reuse example](references/synthetic-example.md) for a small first run and its evidence limits.

## Validated basis

The public package supplies synthetic normalization, relocation, alignment, control, adapter, lock, and rendering tests. Named-title calibration evidence remains separate from the reusable skill. Thresholds are a starting configuration, not a universal classifier: establish a suitable known-positive and negative-control calibration for each materially different investigation.
