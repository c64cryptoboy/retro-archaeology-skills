---
name: 6502-disassembly
description: Systematically reverse-engineer 6502 machine code using Retro Debugger and other available analysis tools. Use when identifying code versus data, discovering routines and entry points, building cross-references, tracing control flow, identifying tables and embedded data, resolving indirect behavior, tracking startup memory moves and runtime relocation, or progressively turning an unknown 6502 binary into a structured disassembly.
---

# 6502 Disassembly

Turn an unknown or partially understood binary into an **evidence-backed code/data map and control-flow worklist**, not just assembly text. Use `6502-commenting` after structure is established. For hosted bytecode use `pcode-disassembly`; decoding VM operands as native instructions is not a substitute.

## Start here

Record the input identity/hash, CPU variant, container/load address, runtime mapping, known entry points and requested analysis boundary. Preserve originals. If these are unknown, establish them before interpreting addresses; do not silently assume stock C64 RAM or a particular 6502 opcode set.

Prefer static inspection first where it can settle the question. Use a focused, authorized runtime capture when banking, indirect control, decoding, hardware or missing state prevents a sound conclusion. A trace proves observed execution, not all possible paths. Retro Debugger is optional; equivalent captures/breakpoints are acceptable and offline tools require no emulator connection.

## Read the reference for the phase you are entering

Do not load every file for a narrow question. Read the required phase **before** taking its actions; references are procedure, not optional background when their trigger applies.

| Trigger | Read | Produce/check before continuing |
|---|---|---|
| First use of the tools, or uncertain classification/evidence conventions | [Foundations and tools](references/foundations-and-tools.md) | Tool input/working-directory contract; provisional code/data labels |
| New binary/entry point; building CFG, xrefs, routines or data map | [Structure and data](references/structure-and-data.md) | Machine context, entry set, blocks/edges, referenced data and explicit gaps |
| Startup copies, memory moves, relocation fixups, or overlays | [Memory moves and runtime relocation](references/memory-moves-and-relocation.md) | Source/destination stage map, exact copy semantics, recovered runtime bytes, and evidenced handoff |
| Indirect jumps, self-modification, runtime decoding or ambiguous execution | [Dynamic code and traces](references/dynamic-code-and-traces.md) | Pointer writers/targets, comparable captures or bounded transform/trace evidence |
| Distinguishing a supplied stream interpretation from pointer data or origin claims | [Regional evidence pilot](scripts/region-evidence/README.md) and [worksheet](scripts/region-evidence/WORKSHEET.md) | Byte-pinned consumer assumptions, conditional boundary checks, and explicit unknown authorship |
| Separating Forth dictionary links, threaded cells, inline operands, and native handlers | [Source-backed FIG-Forth example](references/forth-source-example.md) | Source-derived relationships and explicit binary/platform applicability limits; not a universal recognizer |
| Naming, closing a region or handing work off | [Completion and handoff](references/completion-and-handoff.md) | Reviewed names, byte coverage and unresolved worklist |

For exact C64/1541 ROM calls, workspace or banking, also read the relevant `c64-rom-reference` table. Do not infer the behavior of a ROM call from its label alone.

## Invariants that remain in force throughout

- **No blind linear sweep.** Follow evidenced entries and control flow; nearby bytes may be strings, tables, inline JSR parameters or encoded data. Numeric address occurrences alone are weak evidence.
- **Classifications are provisional:** confirmed/probable code, confirmed/probable data, unknown; also explicitly record unused/padding and excluded ranges. Revise them when new evidence contradicts them.
- **Account for every byte in scope.** Every confirmed reachable instruction must belong to a mechanically understood block/routine or an explicit open item. A block comment can account for many instructions; no opcode-by-opcode paraphrase is required.
- **Keep mechanics separate from purpose.** “Mechanically understood, context pending” is valid; unsupported semantic names are not. Record facts, inferences and hypotheses separately.
- **Do not assume modern function boundaries.** Multiple entries, shared tails, tail calls, inline parameters, patched operands and nonstandard returns require evidence.
- **Unknown flow stays open.** Add indirect, interrupt, decoded and banked entries when established; absence from a static CFG does not make a region dead or free.
- **Separate storage from execution.** Track copied/relocated bytes by address, mapping, and stage.  Rebuild destination analysis from the appropriate runtime image; do not follow stale file bytes or assume every copied region is code.
- **Model actual state.** Decoder simulation needs material registers, flags, RAM and stop bounds. Unsupported opcodes, missing state or a limit stop are incomplete evidence, not permission to extrapolate.
- **C64 CPU and VIC views differ.** `$0001` controls CPU ROM/I/O banking; `$D000-$DFFF` is not always I/O. Screen/character memory and IRQ/NMI/workspace conventions need current mapping evidence.

## Minimal tool path

Bundled helpers live in [../../shared/6502/](../../shared/6502/). Retain repository layout. From this skill directory:

```bash
python3 ../../shared/6502/cfg6502.py file.prg --entry 0xADDR --json
```

Replace `0xADDR` with an evidenced entry; save CFG JSON for pointer scans and reports. This is a static candidate/worklist generator, not proof of reachability. [Foundations and tools](references/foundations-and-tools.md) routes pointer scans, data classification, indirect-flow inventory, bounded decoding, traces, write diffs, C64-state reports and final reports; do not run them all by default.

## Deliverable and stop gate

Retain input hashes/mapping, entries, code/data/unknown ranges, block effects and calling assumptions, xrefs, evidence references, meaningful labels and a prioritized open worklist. Revisit classifications after new callers or runtime forms emerge.

A region is complete only within its declared evidence boundary: bytes accounted for, confirmed reachable instructions explained or explicitly open, data/indirect/mutable behavior addressed, and residual uncertainty reported. If required bytes, mapping, legal runtime state or CPU semantics are unavailable, stop at that boundary. Rendering all bytes as assembly is **not** completion.
