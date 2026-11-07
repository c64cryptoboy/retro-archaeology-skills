# LLM-assisted reduction workflow

## 1. Intake and identity

Record ownership, original path/hash/size, CPU variant, container/load mapping, entries, output size/base constraints, and timing policy. Preserve the original.

## 2. Map before compacting

Establish code/data/unknown ranges, every known entry and reference, direct/indirect flow, tables, vectors, SMC, banking, I/O, stack conventions, and runtime coverage. A shorter body shifts addresses; local correctness alone does not repair an image.

## 3. Mark protected timing structure

Before searching for savings, mark:

- visibly unrolled loops;
- NOP/padding and equal-cycle paths;
- interrupt/NMI handlers;
- raster/audio/fast-loader/device loops;
- polling and timed I/O sequences.

Preserve cycle-exact regions. For interrupts, establish a pathwise no-slower rule.

## 4. Establish semantic contracts

For each candidate record inputs/domains, outputs, live registers/flags, memory effects, callers, callees, stack behavior, timing, and asynchronous observers. Separate confirmed facts from hypotheses.

## 5. Run deterministic rules

Use the Stage-1 reducer only on an asserted straight-line block with no interior entries. Supply honest terminal liveness and entry facts. Inspect every ledger entry; a tool pass proves only its declared local conditions.

The Stage-2 CFG scanner identifies provisional control-flow candidates but does not restructure loops, change bytes, or patch unknown references. Treat current-layout replacement bytes as previews; compaction must regenerate them at final addresses.

## 6. Search semantically

Ask whether source/domain meaning admits a smaller representation: narrower input domain, dead outputs, alternate algorithm, formula, generator, grammar, shared tail, or table replacement. Convert the insight into a focused guarded script and exact/domain/specification verification contract.

## 7. Integrate at final addresses

The Stage-3 compactor can pack an asserted contiguous all-code region and repair retained relative plus internal direct JSR/JMP control references. Do not use that bounded claim for mixed code/data or surrounding-image integration. A complete image must additionally repair absolute data addresses, external callers, vectors, pointer tables, split low/high fields, computed initialization, and SMC operands under an explicit manifest. Retain old bodies if any reference remains unresolved.

## 8. Verify

1. Static identity/boundary/layout/reference gates.
2. Rule-specific positive and negative tests.
3. Local differential execution across meaningful domains.
4. Connected final-address caller/callee execution.
5. Whole-image changed-byte authorization.
6. Emulator/hardware checks for I/O, interrupts, banking, or timing.

For cycle policy, report original/new cycles per relevant path—not only an average.

## 9. Report and promote

Report bytes before/after/saved, cycles, RAM/stack, intermediate effects, transformed and preserved regions, contracts, cases, failures, and limitations. Freeze reproducible scripts/evidence.

Promote a bespoke reduction into deterministic tooling only when the pattern recurs and stable mechanical preconditions can reject unsafe cases.
