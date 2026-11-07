# Machine context, entries, CFG and data

> Read [SKILL.md](../SKILL.md) first. This is the detailed procedure for the routed phase, not an instruction to expand every task. Commands and inline file paths below are relative to the **skill directory**, unless explicitly stated otherwise; Markdown links resolve from this reference.

## Workflow

### 1. Establish the machine context

Before substantial analysis, determine as much of the following as possible:

- machine/platform,
- CPU variant,
- load/storage address versus execution address, including any known move stages,
- initial PC or known entry point,
- relevant ROM mappings,
- interrupt vectors,
- zero-page conventions,
- important hardware registers,
- whether code may bank memory in or out.

For Commodore 64 programs, first capture a raw 64 KiB CPU-memory snapshot where feasible and run `c64-state-report.py`; it provides an explicit record of the snapshot's `$0001`, vectors, BASIC pointers, and sampled VIC state. Confirm its I/O-dependent fields with Retro Debugger when necessary.

For Commodore 64 programs, account for:

- CPU memory configuration through `$0001`,
- KERNAL/BASIC/I/O banking,
- VIC-II state when display behavior matters,
- IRQ/NMI vectors,
- hardware register accesses.

Do not assume the entire CPU address space is static RAM.

### 2. Identify initial entry points

Start from known execution locations such as:

- loader entry point,
- SYS target,
- reset vector,
- IRQ/NMI vectors,
- BASIC hooks,
- observed PC values,
- known calls from already analyzed code.

Run `cfg6502.py` with each strongly established entry point (and `--json` when downstream tools/reports are needed). Create functions or labels for strongly established entry points using Retro Debugger facilities when available.

If the tool supports temporary labels, use neutral names such as:

    sub_8A37
    loc_A421
    data_B200

Do not assign semantic names prematurely.

### 3. Recursively trace reachable code

For each confirmed entry point:

1. Decode instructions along reachable control-flow paths.
2. Follow conditional branches.
3. Follow JSR targets.
4. Follow unconditional JMP targets.
5. Record fall-through paths.
6. Stop when execution reaches:
   - an already analyzed instruction,
   - RTS,
   - RTI,
   - an unconditional transfer,
   - invalid or contradictory decoding,
   - or bytes already established as data.

Add newly discovered targets to the analysis worklist.  If a target's bytes are supplied or replaced by a memory move, resolve the [move and runtime image](memory-moves-and-relocation.md) before following that edge.  Keep the loaded-image CFG and each relevant runtime-stage CFG distinct; a static file address is not sufficient evidence for the bytes present at execution.

As each confirmed block is traversed, account for every instruction's role in control flow, state/memory effects, pointer or arithmetic transformations, ROM/hardware access, and block inputs/outputs. Mark an instruction `mechanically understood, context pending` when its effect is clear but its purpose is not; record genuinely unexplained effects as worklist items rather than stepping past them.

Prefer recursive traversal to blind linear sweep. Use `cfg6502.py` as the initial static worklist, but add entry points it cannot discover (interrupts, decoded code, banked code, and resolved indirect destinations) explicitly and rerun it.

### 4. Build and maintain cross-references

For every significant address, track references from:

- JSR,
- JMP,
- conditional branches,
- absolute loads and stores,
- zero-page accesses when their role becomes known,
- pointer tables,
- indirect jumps,
- indirect-indexed and indexed-indirect addressing when a base pointer can be identified.

When Retro Debugger can expose xrefs, query and use them. Use the `dataXrefs` produced by `cfg6502.py` as a static supplement, then run `ptrscan6502.py --cfg-json cfg.json` to investigate candidate address tables.

When it cannot, infer them from disassembly and memory searches.

Cross-references are evidence. Use them to revisit classifications and routine boundaries.

### 5. Identify routine boundaries

A function generally begins at a callable entry point, but do not assume every labeled branch target is a separate function.

Look for:

- JSR targets,
- shared tails,
- multiple legitimate entry points,
- tail calls,
- trampolines,
- dispatch stubs,
- inline data following JSR,
- nonstandard return mechanisms.

6502 code frequently violates modern compiler assumptions about function structure.

### 6. Classify non-code regions

After reachable code has been identified, investigate gaps.

Look for:

- PETSCII or ASCII strings,
- screen-code strings,
- pointer tables,
- jump tables,
- address pairs,
- lookup tables,
- numeric constants,
- sprite data,
- character bitmaps,
- tile/map data,
- compressed data,
- encrypted or obfuscated data,
- inline parameters associated with nearby code.

Run `data-classify6502.py` on the PRG only after excluding CFG-confirmed code, and use its output to prioritize inspection of gaps. Do not classify an unexplored region as data solely because no direct code reference has yet been found.

