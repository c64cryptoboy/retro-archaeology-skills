# Reduction catalog

## Established deterministic rules

Implementation: `tools/reduction_rules6502.py` (relative to the skill directory).

### Zero-page operand narrowing

An existing absolute operand `$00xx` becomes its zero-page encoding when the same mnemonic supports it, saving one byte and often one cycle. Absolute-X/Y forms narrow only when the corresponding index is known and cannot wrap past `$00FF`; zero-page indexed addressing wraps while absolute indexed addressing does not.

This local rule does not allocate or relocate variables. Global zero-page placement requires platform reservations, complete reference/address-taken evidence, lifetime and asynchronous-use analysis, and weighted whole-program savings.

### Known-carry immediate adjustment

When binary arithmetic is established, `CLC; ADC #k` with incoming C=1 or `SEC; SBC #k` with incoming C=0 becomes the arithmetic instruction with immediate `k-1`, saving one byte and two cycles. Capability policy assumes D=0 at program entry. If complete reachable-code inspection finds no instruction or external status-loading convention that sets decimal mode, propagate D=0 as a program-wide invariant; individual ADC/SBC sites need no nearby CLD or separate semantic proof. The 2A03 is always treated as decimal-disabled. If the program does set/import D, use local D-state flow, reviewed binary-only consumer evidence, or prove equivalence under both D states over the contracted domain. The established local reducer consumes the resulting D=0 fact and refuses `k=$00` (carry boundary) and `k=$80` (overflow-sign boundary) so A/N/V/Z/C remain exact.

### Known-state redundancy

Remove a flag setter when the incoming flag already has its target value. Remove an immediate LDA/LDX/LDY only when the incoming register, N, and Z exactly match the load result.

Precondition source: declared entry facts plus conservative forward propagation. Unknown facts refuse the rule.

### Duplicate flag setter

Collapse adjacent identical CLC/SEC/CLD/SED/CLI/SEI/CLV operations. The first operation remains; final flags are exact and two nominal cycles are removed.

### Exact transfer round trip

- `TAX; TXA` → `TAX`
- `TAY; TYA` → `TAY`
- `TXA; TAX` → `TXA`
- `TYA; TAY` → `TYA`

The second transfer restores a value already equal to the destination and reproduces the same N/Z, so final architectural state is exact while one byte/two cycles are removed.

### Dead-source load/transfer fusion

Examples:

- `LDA #v; TAX` → `LDX #v` when A is dead afterward;
- `LDX addr; TXA` → `LDA addr` when X is dead afterward;
- corresponding Y forms and compatible zp/abs/indexed modes.

The fused load uses the same effective address and produces the same transferred value and final N/Z. Indexed forms retain the same page-cross condition. The original load destination must be dead.

## Established LLM-assisted case evidence

### Domain/liveness rewrite

A nibble-rotation routine can sometimes be reduced under a one-hot input domain A in `{1,2,4,8}` and dead Y. Prove those facts at every caller; a domain-specific implementation is not a generic arbitrary-A rule.

### Carry reuse

For carry reasoning, a preceding `CMP #20` can establish the carry consumed by `SBC #19`, avoiding a separate SEC. Promote analogous cases only when forward facts establish the required carry on every incoming path and final flags satisfy liveness/contract requirements.

### Outlining accounting

Outlining two repeated 19-byte sequences into two JSRs plus one helper/RTS would save 12 code bytes before any additional layout costs, but add 12 cycles per execution. Always include call/return and branch/layout costs. Never outline or loop repeated code merely because it looks unrolled; preserve possible timing intent.

### Loop induction reversal

Treat two cases separately. The implemented deterministic tier recognizes a single linear `LDX/LDY #start … INX/INY; CPX/CPY #terminal; BNE` loop with 1..255 fixed iterations whose index is unused by the body. It loads the modulo trip count, substitutes DEX/DEY, deletes the compare, and repairs BNE. It requires complete/private loop flow, no body index touch, dead exit index/C, unobserved loop-back N/C and changed initial Z, and no asynchronous counter observer. It saves two bytes and nominally two cycles per iteration, refuses cycle-exact policy, remains pathwise faster under interrupt policy, and never constructs a loop from unrolled code. Indexed loops remain semantic because their index values matter. The scanner reports same-set reverse-order options separately from compactor candidates; `semantic_loop6502.py` materializes local bytes only after an explicit all-true semantic contract. Independent ordinary-RAM constant stores illustrate final-state rather than ordered-trace equivalence; reversing their order still requires explicit alias and observation contracts. Local savings do not establish whole-image integration.

If the index addresses memory or affects computation, reversal is semantic rather than a local control rewrite. The scanner now emits analysis-only options for canonical one-based decrement+BNE and bounded zero-based decrement+BPL forms, including body/index-use addresses, current-layout replacement previews, liveness gates, and semantic obligations; these options are intentionally absent from compactor rules. Disjoint ordinary-RAM stores may preserve final state despite reversing ordered writes, but overlap/aliasing, recurrence, early exit, screen/raster visibility, SID or other device-register ordering, SMC, interrupts, and concurrent observers can make it invalid. The LLM must choose and validate an exact or specification-equivalence contract; “same addresses eventually” is insufficient for I/O.

A related same-order opportunity occurs when a loop pre-decrements its index, performs indexed work, then uses `TXA`/`TYA` only to refresh N/Z for `BNE`:

```asm
        LDX #count
loop:   DEX
        LDA source,X
        STA dest,X
        TXA
        BNE loop
```

For `count` in 1..255, it may become:

```asm
        LDX #count
loop:   LDA source-1,X
        STA dest-1,X
        DEX
        BNE loop
```

The body still reaches `source+count-1` through `source` and `dest+count-1` through `dest` in the same order. The tail decrement now supplies the same N/Z tested by the branch, removing the transfer and saving one byte plus nominally two cycles per iteration. Apply the same reasoning to Y. This is a review pattern, not yet an implemented rule: every body observation of the index must be adjusted or excluded; N/Z entering the body must be overwritten before use; the final A changed by deleting `TXA`/`TYA` must be dead; operand underflow, aliases, I/O, SMC/code-as-data, asynchronous observers, relocated branch timing, and all references need the usual proofs. Absolute indexed reads need special timing review: biasing a page-aligned base such as `$C000` to `$BFFF` preserves effective addresses but changes page-cross penalties. A zero-based `DEX/DEY; BPL` alternative avoids address bias only for at most 128 elements: its initial and continuing nonterminal values must remain in `$00-$7F`. It is invalid for a 129..255-element countdown; use one-based `BNE` instead.

## Established read-only CFG candidate detection

The Stage-2 scanner reports but does not apply:

- private `JSR target; RTS` tail-call signatures under an explicit conventional stack/return contract;
- known never-taken branch and branch-to-own-fallthrough deletion candidates;
- known-flag short-jump selection: `JMP target` → a guaranteed-taken `BEQ/BNE`, `BCS/BCC`, `BMI/BPL`, or `BVS/BVC`, saving one byte when final displacement is −128..127; taken branch is 3 cycles like absolute JMP on the same page but 4 cycles across a page, so interrupt policy rejects page crossing.

All remain provisional until complete entries/references, code-as-data/SMC exclusions, final layout, and shifted references are established.

## Established guarded packed-region transformations

For a contiguous region whose every byte is established documented code, the Stage-3 compactor applies the scanned and guarded lowering families after explicit complete-reference, no-code-as-data, either no-SMC or exhaustive declared-SMC-field, and return-stack assertions. It regenerates final relative and internal direct JSR/JMP operands, emits entry/address/provenance/reference ledgers, preserves NOPs/unrolling, and refuses rel8 or interrupt page-cross regressions. This region-only result does not itself repair the surrounding image. Strict whole-image integration V2 can shift one non-tail suffix and repair declared callers, vectors, abs16/split/rel8 pointers, and declared SMC writers while protecting hash-guarded mixed/opaque ranges and fixed anchors. Indirect flow, banking aliases, and compaction through mixed data remain unresolved. Multiple one-region V2 stages may compose only through exact current-output hash chaining; this is not a relaxed multi-region manifest.

## Established idempotence reduction

Adjacent exact duplicates are removable when the modeled state transformer satisfies `f(f(s)) = f(s)` and the operation has no memory/I/O effect. Supported families include immediate AND/ORA, immediate loads/compares, TSX/TXS, flag setters, and transfers. NOP remains deliberately preserved; repeated memory reads/stores are excluded because volatility, I/O, or external observation can make repetition significant.

## Established target-aware liveness lowering

The scanner now emits live/available A/X/Y sets. For an equality branch immediately after a matched load and compare to `$FF` or `1`, it can replace the two-byte compare with one-byte INX/INY or DEX/DEY. It may lower an A-based load into an available X/Y register when the original A result, chosen index register, and changed C are dead on every successor path. N/Z remain exact; load addressing mode, dynamic page behavior, bytes, and cycles must match. The compactor applies the selected lowering and regenerates its final branch.

A private matching load followed by `CMP/CPX/CPY #0` and BEQ/BNE can delete the two-byte compare when the load already established the same register N/Z and compare-only C is dead on every successor. The retained branch is repaired after packing. This currently covers only matching LDA/CMP, LDX/CPX, and LDY/CPY; other N/Z producers are not supported.

Private `LDA value; AND #mask; BEQ/BNE` bit tests support masks `$01`, `$40`, and `$80`: use LSR plus BCC/BCS, ASL plus BPL/BMI, or the load's existing N plus BPL/BMI. Per-mask changed A/C/N/Z resources must be dead. The rules save one/two bytes and regenerate the final branch. Separately, `CMP/CPX/CPY #0` always establishes C=1, so private BCS becomes JMP and BCC plus compare deletes when N/Z/C are dead.

The scanner also reports equal-cost simple direct/immediate load→direct store live ranges that can be rehomed among A/X/Y. These zero-byte options are not credited as reductions or applied alone; they are future composition choices when another optimization needs to borrow the original register.

One bounded composition handles a two-path value selection. For a private equality diamond of the form “load A default; `CPX/CPY #0`; BEQ/BNE shared store; load A alternate; shared STA,” both selected values and the store may move to the other dead index register. TXA/TYA then replaces the two-byte zero compare, saving one byte at equal cycles on both paths. The rule requires matching supported modes/cycles, no external entry/join into the diamond or store, the replacement register dead on entry, and A/replacement-register/C dead after the store. It preserves selected memory, N/Z, the compared index, and branch behavior; it is not general register allocation.

## Deterministic transformations requiring implementation

- broader constant conditional-branch deletion/folding with final-address repair;
- jump-to-next/fallthrough elimination;
- carry-aware ADC/SBC rewrites beyond the established exact binary/immediate subset, requiring explicit C/V/D liveness;
- redundant compare/load/transfer sequences;
- branch threading/inversion and short-branch relaxation;
- common-tail merging and profitable outlining;
- single-call inlining with source retirement and branch-range repair;
- direct RMW replacement for load/modify/store sequences under A/flag/memory-bus policy;
- pointer-copy elimination when a stable zero-page pointer can be consumed directly.

Each requires positive/negative fixtures, exact flag effects, byte/cycle ledger, refusal tests, and final integration evidence before being labeled supported.

A replacement's extra register or flag clobber is not itself a rejection reason. Use CFG-wide liveness to prove that each changed value is unobserved until overwritten. If it is still live but has a small simple def-use interval, attempt local live-range rehoming: for example, `LDA #0` … `STA $D020` can become `LDY #0` … `STY $D020` while A is borrowed, provided Y is dead/available throughout and all flag/addressing/timing effects remain compatible. This enables destructive bit tests/shifts, compare-via-INX/DEX/LSR forms, EOR-based comparisons, opposite-direction rotates, and temporary index-register use. A/X/Y are asymmetric, so accumulator-only arithmetic, X/Y indexing, mode availability, joins, calls, and interrupts can refuse a rename.

## LLM-assisted semantic families

- domain-restricted arithmetic/state-machine implementations;
- narrow 16-bit/enumerated state to bytes when the complete value domain permits it;
- array-of-structs to struct-of-arrays or byte-indexed/page-aware data layouts;
- split 16-bit pointer tables into low/high arrays when scaled indexing disappears;
- global/static/zero-page calling state replacing software-stack parameters only when recursion, reentrancy, callbacks, and IRQ/NMI overlap are excluded;
- bit-7/bit-6 boolean representation using memory shifts and BIT/N/V tests after converting every producer and consumer;
- specialized application routines replacing generic linked runtime/library facilities;
- alternate search, random, parser, rendering, or data-structure algorithms;
- table-to-formula conversion, or formula/switch/arithmetic-to-table conversion only when complete code+data cost shrinks;
- procedural generation of exact data;
- grammar/dictionary encoding of repeated domain records;
- specification-equivalent replacement where downstream invariants—not exact bytes—are the true contract.

Measure complete cost: generator/decoder code, parameters, workspace, startup and runtime cycles, storage, and integration. Validate exact output when exact content matters; otherwise validate consumer-specific invariants and whole-program behavior.

## Excluded by default

- rolling unrolled code into loops;
- deleting NOPs/padding;
- transformations inside cycle-exact islands;
- cycle-increasing interrupt rewrites;
- changing I/O order or count;
- exploiting undocumented opcodes without a separately selected CPU policy;
- relocating through unresolved entries, pointers, code-as-data, or self-modification;
- BIT instruction-skipping/overlapping streams, RTS jump-table tricks, inline argument streams, or stack-temporary substitutions without a bespoke control/stack/code-data contract;
- RMW operations on ROM or mapped I/O without a platform-specific bus-conflict/write-side-effect proof;
- speed-for-space lookup tables unless whole-image accounting proves a net byte reduction.
