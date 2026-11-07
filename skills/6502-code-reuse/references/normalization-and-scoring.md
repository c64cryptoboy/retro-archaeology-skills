# Normalization, alignment, and thresholds

## Decoder scope

The bundled decoder uses the shared official NMOS 6502 opcode table. Unsupported opcodes reject/stop a candidate rather than being assigned another CPU's meaning.

This deliberately permits comparison among common 6502/6510/2A03 code. It can omit real C64 undocumented-opcode routines and 65C02-only code. Record that limitation instead of silently widening the instruction set after viewing a target.

A fixed window cannot cross `BRK`, `RTI`, `RTS`, or unconditional `JMP` before its last instruction. Windows containing `BRK` or fewer than the configured unique mnemonic count are excluded.

## Three views

### Literal

Token = mnemonic + exact addressing mode + exact operand.

Useful for byte-near identity and evidence display. It is too strict for most relocated ports.

### Portable relational

The relational view:

- maps zero-page/absolute storage forms into portable mode families;
- alpha-renames first-seen memory references as `M0`, `M1`, and so on;
- alpha-renames absolute JSR/JMP destinations separately as `C0`, `C1`, and so on;
- preserves repeated-reference identity within the window;
- represents an in-window branch by its target instruction identity;
- otherwise preserves branch direction;
- keeps immediate values literal.

Thus two relocated references can match only when their identity/reuse pattern remains coherent. This is stronger than replacing every address with one generic `ADDR` token.

### Portable shape

The shape view keeps mnemonic, portable addressing family, branch direction, and immediate values, but removes memory/control target identity.

Use shape evidence to continue through edits that introduce references and shift alpha numbering. Do not silently promote a shape-only short match into relational evidence.

## Exact anchors

Primary anchors are equal k=8 relational windows. The tool also records literal evidence. Anchor frequency is measured per region.

Defaults:

- minimum unique mnemonics: 4;
- maximum occurrences per region: 64;
- maximum pairs per fingerprint: 4096;
- maximum seed clusters: 500.

Overlapping anchors on a compatible diagonal are clustered before extension.

## Boundary correction

All-offset scanning can start inside an instruction. Extension tries shifts 0, -1, and -2 independently on each side and chooses the strongest containing decode/alignment. A corrected start is evidence, not proof of a callable routine entry.

## Affine local alignment

Pair scores:

| Relation | Score |
|---|---:|
| relational exact | +5 |
| shape exact | +3 |
| compatible changed operand | +1 |
| materially different | -4 |
| gap open | -5 |
| gap continuation | -1 |

Affine gaps tolerate compact platform edits while making long unrelated jumps expensive. Local alignment finds the strongest bounded region rather than forcing whole streams to correspond.

Every retained column records original instructions, relation, and score.

## Support metrics

A supporting pair is relational-exact, shape-exact, or compatible-changed-operand. A materially different pair is not support. Gaps are explicit.

Important metrics:

- paired instructions;
- supporting pairs and support fraction;
- relational-exact count;
- longest supporting run;
- gap count;
- score;
- left/right spans;
- seed frequency product.

## Validated primary thresholds

Candidate similarity:

- at least 8 paired instructions;
- at least 70% support.

Probable shared routine:

- at least 16 paired instructions;
- at least 80% support;
- at least 8 relational-exact pairs;
- seed frequency product at most 16.

Whole-comparison interpretation:

- strong shared-code lineage: at least 3 probable routines, 48 supporting pairs, and 256 unique bytes per side;
- limited shared-routine evidence: at least 1 probable routine but not the strong gate;
- candidate-only: candidates but no probable routines;
- no detected reuse: no qualifying candidates under the locked configuration.

These thresholds were validated on one research corpus. Recalibrate when CPU profiles, capture types, or expected edit patterns materially differ.

## Sensitivity

Required variants:

- seed k=6;
- seed k=10;
- probable minimum 12 paired instructions;
- probable minimum 20 paired instructions.

A sensitivity result can reveal a lead or demonstrate robustness. It must not replace the frozen k=8/16 primary classification.
