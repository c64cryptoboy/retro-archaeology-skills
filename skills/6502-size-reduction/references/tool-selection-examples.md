# Reduction tool selection and examples

> Read [SKILL.md](../SKILL.md) and the timing/workflow contracts first. These are phase-specific commands, not a request to run all tools. Commands and inline paths are relative to the **skill directory**; Markdown links are relative to this reference.

## Deterministic tools

### Stage-3 guarded packed-region compactor

```bash
python3 tools/compact6502.py INPUT.bin OUTPUT.bin \
  --report REPORT.json --base-address 0x8000 --entry 0x8000 \
  --expected-sha256 HASH --timing-policy ordinary \
  --assert-complete-code-region --assert-all-incoming-references-repairable \
  --assert-no-code-as-data --assert-no-self-modifying-code \
  --assert-standard-jsr-rts
```

Use only for a contiguous region whose every byte is established documented code. It applies the Stage-2 control candidates plus matching-load redundant compare-to-zero deletion, masked `$01/$40/$80` bit tests, compare-zero unsigned-branch folding, guarded control-only fixed-trip loop reversal, liveness-aware compare-to-`$FF`/`1`, compare-to-`2`, and guarded zero-compare/two-path-register-rehome lowerings plus generalized side-effect-free duplicate-idempotent removal. It packs final addresses, repairs retained relative and internal direct JSR/JMP references, emits entry/address/provenance/repair ledgers, and refuses incomplete coverage, rel8 overflow, cycle-exact policy, or interrupt page-cross regressions. The default excludes SMC; repeated `--declared-smc-field INSTRUCTION:OFFSET:WIDTH` plus `--assert-no-undeclared-self-modifying-code` permits only exhaustively declared one-/two-byte operand fields. Surrounding-image incoming references, data pointers, vectors, indirect flow, mixed code/data, banking, and SMC writers remain outside the region-only output and must not be asserted away without evidence.

### Stage-2 read-only CFG candidate scanner

```bash
python3 tools/scan_reductions6502.py INPUT.bin \
  --report SCAN.json --base-address 0x8000 --entry 0x8000 \
  --expected-sha256 HASH --timing-policy ordinary --cpu-profile nmos6502
```

It recursively decodes documented direct control flow, rejects overlapping control targets, emits blocks/edges/known-state plus live/available A/X/Y evidence, applies the program-entry D=0 policy, and reports private `JSR; RTS` tail calls, known-flag `JMP`→relative-branch opportunities, known dead branches, matching-load redundant `CMP/CPX/CPY #0` deletions, masked single-bit shift/sign tests, compare-zero unsigned BCS/BCC folds, guarded control-only fixed-trip loop reversals, analysis-only indexed-traversal reversal options, equal-cost simple load→store register-rehoming options, compare-to-`$FF`/`1` lowerings through an available X/Y register, and a narrowly guarded two-path A-select rehome composed with `CPX/CPY #0`→TXA/TYA. Every replacement remains provisional until complete entries/references, stack convention, final layout, displacement, and timing are established. Indexed traversal options remain outside automatic compaction; `semantic_loop6502.py` can materialize an exact local option only after an explicit contract covers reversed order, aliasing/overlap, recurrences/exits, I/O, SMC/asynchronous observers, and final index/flag visibility. Whole-image integration remains a separate proof.

### Strict whole-image integration V2

```bash
python3 tools/integrate_whole6502.py \
  INPUT.bin OUTPUT.bin --manifest MANIFEST.json --report REPORT.json \
  --timing-policy ordinary --cpu-profile nmos6502 \
  --assert-standard-jsr-rts
```

Use V2 for one compacted all-code region in a contiguous image. The strict manifest must hash-guard and contiguously classify every shifted suffix byte as code/data/mixed/opaque; declare every caller, vector, abs16/split-low-high/rel8 pointer, fixed anchor, and SMC operand field/writer; and make all completeness assertions explicit. SMC fields may be in the compacted region or wholly inside shifted `code` ranges. It repairs final source/target addresses, emits exact changed-address and authorization ledgers, and refuses gaps, overlaps, unstable provenance, moving fixed anchors, undeclared SMC, and unauthorized prefix changes. It does not compact through mixed code/data or pad around fixed suffix anchors. Each V2 stage still processes one region, but `integrate_whole_image_sequence` can combine multiple stages only when every later manifest hash-guards the exact preceding output and independently passes all V2 audits. Read [references/whole-image-integration-v2.md](../references/whole-image-integration-v2.md) before use. The original tail-only API remains available for compatibility.

### Stage-1 straight-line reducer

The current reusable reducer is:

```bash
python3 tools/reduce6502.py INPUT.bin OUTPUT.bin \
  --report REPORT.json --base-address 0x8000 \
  --expected-sha256 HASH --assert-no-interior-entries \
  --assert-no-code-as-data --timing-policy ordinary --terminal-live A X SP F:N F:Z
```

It accepts only one asserted straight-line documented-NMOS block with no interior entries. It does not repair surrounding layout. Current rules cover zero-page narrowing for existing `$00xx` operands, exact binary known-carry immediate adjustment around ADC/SBC, known-state redundant setters/immediate loads, duplicate flag setters, exact transfer round trips, and dead-source load/transfer fusion. Indexed zero-page narrowing requires a known index proving no wrap.

Read [references/tool-map.md](../references/tool-map.md) before use.

