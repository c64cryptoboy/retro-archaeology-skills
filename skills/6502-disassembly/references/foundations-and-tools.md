# Foundations and offline tools

> Read [SKILL.md](../SKILL.md) first. This is the detailed procedure for the routed phase, not an instruction to expand every task. Commands and inline file paths below are relative to the **skill directory**, unless explicitly stated otherwise; Markdown links resolve from this reference.

# 6502 Disassembly

Use this skill to turn an unknown or partially understood 6502 binary into a reliable structured disassembly.

The primary goal is not merely to produce assembly syntax. The goal is to determine:

- what bytes are executable code,
- what bytes are data,
- how routines and data reference one another,
- where execution can enter each region,
- what structures exist in data,
- which conclusions are known versus inferred,
- and what remains unresolved.

Prefer evidence gathered from the running program and Retro Debugger over assumptions based only on linear disassembly.

## Supporting tools

The reusable offline helpers are in [../../shared/6502/](../../../shared/6502/), relative to this skill. Keep the repository layout intact. Run the commands below with `python3` from that helper directory, or supply each script's full path. They use only the Python standard library and report candidates and evidence; none substitutes for runtime validation or justifies automatic code/data classification.

Live-debugger steps describe capabilities, not a dependency on a particular agent harness. Use Retro Debugger when available, or equivalent breakpoint, trace and memory-capture facilities. The offline scripts consume files and never connect to an emulator.

- `cfg6502.py file.prg --entry 0xADDR --json` recursively follows static PRG-local control flow and emits xrefs/stops. Run it first after identifying an entry point, and rerun it when new entries are discovered.
- `ptrscan6502.py file.prg --cfg-json cfg.json` ranks consecutive little-endian pointer-table candidates against CFG-confirmed instruction addresses. Use only after a CFG pass.
- `data-classify6502.py file.prg` finds conservative string/repetition/graphics-layout candidates. Use on gaps after known code has been excluded.
- `indirect-flow6502.py file.prg` inventories static `JMP (addr)` sites and candidate direct pointer-byte writers. Confirm listed code/writers with CFG and runtime evidence.
- `decode-loop6502.py file.prg --start 0xADDR ...` boundedly executes common decoder-loop instructions and produces byte changes plus trace. Use for a known deterministic transformation; supply all material initial register/RAM state and treat unsupported-opcode stops as incomplete.
- `trace6502.py samples.jsonl` normalizes debugger-derived PC samples into coverage and observed transitions. Use when static analysis is ambiguous; its input is a capture artifact, not a live debugger controller.
- `code-write-diff.py before.prg after.prg --cfg-json cfg.json --executed-json coverage.json` identifies mutations in known/observed code. Capture comparable images before and after the suspected routine.
- `c64-state-report.py snapshot.bin` summarizes a raw 64 KiB C64 memory snapshot. Use before interpreting C64 vectors/banking/VIC pointers; capture I/O-visible state separately when register values matter.
- `disassembly-report.py cfg.json --notes-json notes.json --output report.md` creates an evidence/worklist handoff. Update the notes JSON with human-confirmed facts and hypotheses rather than presenting tool candidates as facts.

## Core principles

### Do not linearly disassemble unknown memory

Never assume that consecutive bytes following known code are also code.

6502 programs commonly intermix:

- executable instructions,
- strings,
- lookup tables,
- sprite or character data,
- vectors,
- jump tables,
- encoded data,
- inline parameters,
- and unused bytes.

Disassemble outward from known or strongly inferred entry points.

### Treat classification as provisional

Maintain the conceptual states:

- confirmed code,
- probable code,
- confirmed data,
- probable data,
- unknown.

Be willing to revise an earlier classification when new evidence appears.

### Prefer control-flow evidence

Strong evidence that an address contains code includes:

- execution observed there,
- a JSR target,
- a JMP target,
- a branch target,
- an interrupt vector,
- a reset/startup vector,
- a known callback or dispatch vector,
- fall-through from confirmed code.

A numeric occurrence of an address in memory is weaker evidence.

### Separate facts from interpretation

Distinguish:

- directly observed behavior,
- strongly supported inference,
- tentative hypothesis.

Do not present a guessed routine purpose as established fact.

### Require instruction and byte-region accountability

Do not stop after finding the major routines. Within the declared analysis boundary:

- classify every byte range as confirmed/probable code, confirmed/probable data, unused/padding, excluded, or unknown;
- ensure every instruction in confirmed reachable code belongs to a basic block/routine whose mechanical effects, successors, memory accesses, and calling assumptions are understood;
- put every instruction or effect that does not fit the current interpretation on the explicit worklist.

This does not mean paraphrasing every opcode or linearly disassembling data. A block-level explanation such as “advance a 16-bit screen pointer by 40” can account for several obvious instructions. The requirement is that no reachable instruction or loaded region disappears merely because it did not look important on the first pass.

Perform the mechanical accounting early. Semantic purpose may remain context-pending and should be revisited after callers, state, hardware, lifecycle, and data structures are understood.

