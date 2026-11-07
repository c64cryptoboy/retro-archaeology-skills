# Tool map

Run commands from this skill directory. Python 3.10+ and the standard library
suffice. Retain `../../shared/6502/` and the bundled Python import adapters.

## Packed-region compactor

```bash
python3 tools/compact6502.py INPUT.bin OUTPUT.bin \
  --report REPORT.json --base-address 0x8000 --entry 0x8000 \
  --expected-sha256 HASH --timing-policy ordinary \
  --assert-complete-code-region --assert-all-incoming-references-repairable \
  --assert-no-code-as-data --assert-no-self-modifying-code \
  --assert-standard-jsr-rts
```

Requires complete documented-code coverage; packs retained instructions and
repairs internal direct references. Refuses overlapping/incomplete coverage,
rel8 overflow, cycle-exact policy and interrupt page-cross regressions.
Exhaustively declared operand fields can replace the no-SMC assertion; see
`--help`. Surrounding references, banking, writers and data are not automatically
repaired. API: `compaction6502.CompactionConfig`, `compact_code_region`.

## Strict whole-image integration

```bash
python3 tools/integrate_whole6502.py INPUT.bin OUTPUT.bin \
  --manifest MANIFEST.json --report REPORT.json \
  --timing-policy ordinary --cpu-profile nmos6502 --assert-standard-jsr-rts
```

Read [whole-image-integration-v2.md](whole-image-integration-v2.md) first.
Requires identity/hash guards, complete suffix classification and declarations
for all references, fixed anchors and SMC fields/writers. Mixed/opaque suffixes
move byte-for-byte. No padding around fixed anchors or compaction through mixed
data. Sequential stages require exact current-output size/hash chaining.
API: `image_integration6502.WholeImageManifest`, `SequentialIntegrationStage`,
`integrate_whole_image`, `integrate_whole_image_sequence`.

## Read-only CFG candidate scanner

```bash
python3 tools/scan_reductions6502.py INPUT.bin --report SCAN.json \
  --base-address 0x8000 --entry 0x8000 --expected-sha256 HASH \
  --timing-policy ordinary --cpu-profile nmos6502
```

Produces CFG, known-state, register/flag liveness and provisional candidates.
Use repeated `--entry` and declared entry facts where supported. A preview is
not an integrated rewrite. All unknown incoming references, indirect flow,
stack conventions, banking and asynchronous observations remain obligations.
API: `cfg_reduction6502.CFGScanConfig`, `scan_cfg_candidates`.

`semantic_loop6502.py` accepts indexed-traversal reversal only under an explicit
all-true semantic contract covering order, aliases, recurrence/early exits, I/O,
SMC/asynchronous observation and final index/flags. It materializes local bytes,
not shifted whole-image integration or a new automatic compactor rule.

## Straight-line reducer

```bash
python3 tools/reduce6502.py INPUT.bin OUTPUT.bin --report REPORT.json \
  --base-address 0x8000 --expected-sha256 HASH --assert-no-interior-entries \
  --assert-no-code-as-data --timing-policy ordinary --terminal-live A X SP F:N F:Z
```

One asserted straight-line documented-NMOS block; optional terminal RTS/RTI.
No branches/JMP/JSR/BRK, loop rolling, NOP removal or surrounding layout repair.
Known facts repeat `--entry-fact`, e.g. `F:C=0`. Outputs must be fresh.
API: `reduction_rules6502.ReductionConfig`, `reduce_straight_block`.

## Verification support and tests

`dataflow6502`, `routine_runner` and `equivalence` are reduction-owned;
`cpu6502` and `isa6502` resolve to shared neutral support. See
[support-provenance.md](support-provenance.md). No metamorphic tree is needed.

```bash
python3 -m unittest discover -s tests -v
```

The public suite uses synthetic inputs. Named-title field tests and corpus
artifacts are separate, not public dependencies. For unknown images use the
`6502-disassembly` skill/shared CFG helpers; use `6502-commenting` for semantics
and `c64-rom-reference` for exact C64/1541 ROM and I/O context.
