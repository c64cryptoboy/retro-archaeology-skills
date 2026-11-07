# Tool reference

Run commands from the skill directory containing `SKILL.md` so bundled imports resolve predictably. All tools use Python's standard library.

## `make_region_manifest6502.py`

Wrap one raw binary:

```bash
python3 scripts/make_region_manifest6502.py INPUT OUTPUT_DIR \
  --id REGION-ID [--base-address 0xADDR] \
  [--kind cpu-memory] [--cpu-profile 6502-nmos] \
  [--known-mask MASK]
```

Copies the bytes/mask into `OUTPUT_DIR` and writes validated `regions.json`.

## Snapshot adapters

```bash
python3 scripts/extract_applewin_snapshot.py STATE.aws.yaml OUTPUT_DIR
python3 scripts/extract_vice_snapshot.py STATE.vsf OUTPUT_DIR
python3 scripts/extract_retro_nestopia_snapshot.py STATE.sav GAME.nes OUTPUT_DIR
```

Inspect and validate emitted regions before scanning.

## `anchor_scan6502.py`

```bash
python3 scripts/anchor_scan6502.py LEFT/regions.json RIGHT/regions.json OUT.json \
  [--window-sizes 5,6,8] [--min-unique-mnemonics 4] \
  [--max-occurrences 64] [--max-pairs 4096] \
  [--max-reported-clusters 500]
```

Produces exact literal/relational anchor counts and relational clusters. It does not extend or classify routines.

## `exact_anchor_controls6502.py`

```bash
python3 scripts/exact_anchor_controls6502.py LEFT/regions.json RIGHT/regions.json OUT.json \
  [--instruction-count 8] [--shuffle-trials 20] \
  [--token-shuffle-trials 20] [--random-trials 10]
```

Controls are deterministic by trial seed. They preserve selected low-level properties while destroying sequence relationships.

## `reuse_align6502.py`

```bash
python3 scripts/reuse_align6502.py LEFT/regions.json RIGHT/regions.json OUT.json \
  [--markdown OUT.md] [--seed-instruction-count 8] \
  [--probable-min-paired 16] [--max-seed-clusters 500] \
  [--max-reported-matches 100]
```

Produces:

- exact anchor/cluster counts;
- boundary-corrected affine extensions;
- per-column evidence;
- deduplicated matches and provisional classes;
- chains;
- unique probable-routine coverage.

`max-reported-matches` limits retained detailed match objects. Ensure it is high enough for whole-comparison accounting when using a lock.

## `calibrate_reuse6502.py`

```bash
python3 scripts/calibrate_reuse6502.py \
  KNOWN.json ANCHOR_CONTROLS.json CALIBRATION.json \
  --unrelated CONTROL.json [--unrelated CONTROL2.json ...] \
  --sensitivity SENSITIVITY.json [--sensitivity ...] \
  [--markdown CALIBRATION.md] [--lock LOCK.json]
```

The gate requires:

- zero accepted anchors in generated controls;
- zero probable routines in unrelated controls;
- the common eight-instruction idiom below probable;
- at least one known-positive comparison with three probable routines.

`--lock` is written only after a passing gate. It records core tool hashes and a relative hash-pinned source calibration.

## `run_locked_reuse6502.py`

```bash
python3 scripts/run_locked_reuse6502.py LOCK.json \
  LEFT/regions.json RIGHT/regions.json OUT.json [--markdown OUT.md]
```

It refuses to run when:

- the lock format/pre-target declaration is absent;
- a core tool hash changed;
- the calibration hash changed;
- runtime report configuration differs from the lock.

It adds whole-pair evidence classification to the ordinary alignment report.

## `candidate_signature6502.py`

```bash
python3 scripts/candidate_signature6502.py \
  REFERENCE.bin 0xOFFSET INSTRUCTION_COUNT TARGETS... \
  [--max-insertions N] [--output OUT.json]
```

This is post-hoc supporting evidence. It matches the complete portable shape as an ordered subsequence, retaining immediate values and permitting only target-side insertions.

## `render_alignment6502.py`

```bash
python3 scripts/render_alignment6502.py REPORT.json \
  [--match MATCH-ID] [--left-label LEFT] [--right-label RIGHT] \
  [--format text|markdown] [--show-relation] \
  [--pair-differences] [--output PATH]
```

Without `--match`, selects the match with the longest supporting run. Default presentation separates unlike replacement hunks into non-overlapping one-sided rows.

## Library modules

- `region_manifest.py`: manifest construction/validation and hashing.
- `dis6502.py`: bundled official NMOS opcode/operand formatter used by the scanner.

## Tests

```bash
python3 -m unittest discover -s scripts/tests -v
python3 -m py_compile scripts/*.py scripts/tests/*.py
```

The public suite is synthetic and requires no commercial data. Named-title fixture checks and calibration reports are maintained separately, not silently skipped as part of the portable acceptance gate.
