# Validated end-to-end workflow

Run commands from the skill directory containing `SKILL.md`, and use absolute corpus/output paths.

## Phase 0: pre-register the investigation

Before inspecting the target comparison, write down:

- target pair and capture versions;
- known-positive pair;
- unrelated-real-program controls;
- primary seed length and thresholds;
- required sensitivity variants;
- whole-comparison interpretation gates;
- expected limitations (resident RAM, banks, CPU profile, unknown masks).

The bundled defaults reproduce the validated primary model:

- seed k=8;
- candidate: at least 8 paired instructions and 70% support;
- probable: at least 16 paired, 80% support, 8 relational-exact pairs, seed frequency product at most 16;
- strong whole-pair evidence: at least 3 probable routines, 48 supporting pairs, and 256 unique bytes per side.

If the new corpus differs materially, calibrate alternatives before the target rather than after it.

## Phase 1: preserve and extract

Hash every source artifact:

```bash
sha256sum SOURCE_FILES...
```

### Raw binary

```bash
python3 scripts/make_region_manifest6502.py capture.bin extracted-left \
  --id left-main --base-address 0x0000
```

Omit `--base-address` when file offsets do not correspond to a stable CPU address. Add `--known-mask mask.bin` when some bytes are unknown.

### AppleWin

```bash
python3 scripts/extract_applewin_snapshot.py state.aws.yaml extracted-apple
```

### VICE

```bash
python3 scripts/extract_vice_snapshot.py state.vsf extracted-c64
```

### Retro Debugger/Nestopia plus matching iNES ROM

```bash
python3 scripts/extract_retro_nestopia_snapshot.py state.sav game.nes extracted-nes
```

Validate that each output `regions.json` identifies the intended physical regions. Do not enable a mirrored/current CPU view when its physical RAM/PRG sources are already enabled.

## Phase 2: known-positive anchors and primary alignment

Optional anchor smoke report:

```bash
python3 scripts/anchor_scan6502.py \
  KNOWN_LEFT/regions.json KNOWN_RIGHT/regions.json known-anchors.json \
  --window-sizes 5,6,8
```

Primary extended report:

```bash
python3 scripts/reuse_align6502.py \
  KNOWN_LEFT/regions.json KNOWN_RIGHT/regions.json known-primary.json \
  --seed-instruction-count 8 --probable-min-paired 16 \
  --markdown known-primary.md
```

Manually inspect several top matches before trusting aggregate counts. Confirm coherent boundaries, operations, and relocation—not merely plausible decoded data.

## Phase 3: controls

Deterministic anchor controls:

```bash
python3 scripts/exact_anchor_controls6502.py \
  KNOWN_LEFT/regions.json KNOWN_RIGHT/regions.json anchor-controls.json \
  --instruction-count 8 \
  --shuffle-trials 20 --token-shuffle-trials 20 --random-trials 10
```

Run at least one unrelated-real-program pair through `reuse_align6502.py` with the primary settings:

```bash
python3 scripts/reuse_align6502.py \
  UNRELATED_LEFT/regions.json UNRELATED_RIGHT/regions.json unrelated.json \
  --seed-instruction-count 8 --probable-min-paired 16 \
  --markdown unrelated.md
```

Do not label an unrelated title as proven negative. It is a control whose expected relationship is weaker.

## Phase 4: known-positive sensitivity

```bash
python3 scripts/reuse_align6502.py KNOWN_LEFT/regions.json KNOWN_RIGHT/regions.json \
  known-k6.json --seed-instruction-count 6 --probable-min-paired 16

python3 scripts/reuse_align6502.py KNOWN_LEFT/regions.json KNOWN_RIGHT/regions.json \
  known-k10.json --seed-instruction-count 10 --probable-min-paired 16

python3 scripts/reuse_align6502.py KNOWN_LEFT/regions.json KNOWN_RIGHT/regions.json \
  known-min12.json --seed-instruction-count 8 --probable-min-paired 12

python3 scripts/reuse_align6502.py KNOWN_LEFT/regions.json KNOWN_RIGHT/regions.json \
  known-min20.json --seed-instruction-count 8 --probable-min-paired 20
```

Expect gradual, explainable changes. A known positive that disappears under every small perturbation is not a robust calibration.

## Phase 5: calibrate and freeze

```bash
python3 scripts/calibrate_reuse6502.py \
  known-primary.json anchor-controls.json calibration.json \
  --unrelated unrelated.json \
  --sensitivity known-k6.json \
  --sensitivity known-k10.json \
  --sensitivity known-min12.json \
  --sensitivity known-min20.json \
  --markdown calibration.md \
  --lock locked-target-config.json
```

Calibration exits unsuccessfully if the gate fails. The lock contains hashes of the core analysis tools and the calibration artifact. Do not edit the locked scripts or calibration after this point. If a necessary fix changes a core tool, create a new calibration and versioned lock before running the target.

## Phase 6: authoritative target run

```bash
python3 scripts/run_locked_reuse6502.py \
  locked-target-config.json TARGET_LEFT/regions.json TARGET_RIGHT/regions.json \
  target-primary.json --markdown target-primary.md
```

Preserve the primary output and lock hash. Do not replace it with a later, more favorable sensitivity result.

## Phase 7: target sensitivity

Repeat k=6, k=10, minimum 12, and minimum 20 using `reuse_align6502.py`, and label each filename/report as sensitivity evidence.

Compare:

- candidates gained/lost;
- probable routines gained/lost;
- whether the same families recur;
- unique coverage;
- whether one isolated lead drives the change.

## Phase 8: family audit

Group primary and sensitivity reports by:

- seed fingerprint;
- overlapping starts;
- shared enclosing routine;
- cloned target banks;
- repeated arithmetic structure.

For each family, save a concise evidence record:

- representative locations and bank/address mapping;
- exact alignment metrics;
- static caller/consumer evidence;
- runtime evidence if obtained;
- semantic operand mapping;
- candidate-selected frequency result if run;
- verdict and confidence;
- unresolved questions.

Use small CFG/disassembly/runtime experiments rather than broad unexplained memory poking.

## Phase 9: candidate-specific frequency (optional)

For a selected reference shape:

```bash
python3 scripts/candidate_signature6502.py \
  reference.bin 0xOFFSET INSTRUCTION_COUNT target1.bin target2.bin \
  --max-insertions N --output candidate-frequency.json
```

Run the same shape against the curated unrelated corpus. State prominently that this is post-hoc specificity evidence, not a calibrated chance probability.

## Phase 10: presentation

```bash
python3 scripts/render_alignment6502.py target-primary.json \
  --match M0001 --left-label "LEFT" --right-label "RIGHT" \
  --format text --output match.txt
```

Present the locked aggregate first, then family-level manual findings. Preserve the distinction between a persuasive individual skeleton and broad whole-game reuse.
