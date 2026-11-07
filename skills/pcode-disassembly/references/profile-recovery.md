# Intake, VM architecture, tracing, profiles and decoding

> Read [SKILL.md](../SKILL.md) first. This is the detailed procedure for the routed phase, not an instruction to expand every task. Commands and inline file paths below are relative to the **skill directory**, unless explicitly stated otherwise; Markdown links resolve from this reference.

## Workflow

### 1. Preserve and scope

1. Hash every source, PRG, disk, snapshot, and runtime input.
2. Record whether source is original, reconstructed, or approximate.
3. Choose whether the capability is standalone or internal before general architecture work. On protected compiler media, use the disk-preservation skill to audit BAM reservations, file chains and error metadata before staging inputs; do not normalize or validate away protection.
4. Record whether this effort is compiler-assisted or explicitly compiler-free. Only the latter requires a pre-oracle plan/freeze before consulting a compiler, manual, opcode table or third-party disassembler. Follow explicit authorization changes prospectively; preserve historical frozen results.
5. State that one source/binary pair covers only the features it exercises.

Use the `6502-disassembly` skill for native-runtime code/data classification and CFG analysis. Use `6502-commenting` only after runtime structure is established. Use `c64-rom-reference` for exact BASIC/KERNAL calls or ROM addresses.

### 2. Identify the VM architecture

Establish with static evidence:

- host entry and interpreter entry;
- p-code instruction pointer and central fetch;
- dispatch classes, thresholds, tables, and handler extent;
- operand-fetch/update conventions;
- call, return, branch, and indirect-control mechanisms;
- value stack/FAC and variable/descriptor representations;
- runtime, p-code, DATA, descriptor, and mutable-state boundaries.

Try the generic structural candidate scan first:

```sh
python3 scripts/blitz/discover_dispatch6502.py program.prg
```

A candidate only establishes a 6502 dispatcher shape. It does not establish that the program is BLITZ, table extent, instruction lengths, or semantics.

### 3. Gather bounded runtime evidence

When static behavior is ambiguous:

- instrument the single central p-code fetch, not every handler;
- log pre-increment p-code address and opcode;
- preserve and restore displaced instructions exactly;
- use RAM-only reversible patches;
- declare every memory override in trace metadata;
- compare logged bytes against the preserved PRG;
- reject instrumentation that touches live VM zero-page state without proof.

Never take a C64 snapshot while the debugger is paused; the host can deadlock. Preserve trace bytes before attempting snapshots.

### 4. Author an external profile

Keep static VM contract data in external profiles (algorithmic, ABI-specific adapters remain explicit code):

- image hash and layout;
- direct-handler and startup table locations;
- exact opcodes;
- compact opcode families and masks;
- operand grammar;
- control class;
- confidence and limitations.

Use stable neutral names such as `OP_1D` until semantics are supported. Do not infer unknown instruction length merely because a later byte looks plausible.

Evidence levels:

- `confirmed`: handler/runtime behavior plus independent source or trace correspondence;
- `confirmed-structure`: encoding/boundary is established but higher semantics may be generic;
- `strong`: multiple consistent clues without the full confirmation standard;
- `unknown`: retain/refuse explicitly.

### 5. Decode conservatively

BLITZ commands (PETSpeed uses the separate CLI in its [tool guide](../references/petspeed-tools.md)):

```sh
cd scripts/blitz
python3 -m unittest -v
python3 blitz_pcode.py --profile profile.json info program.prg
python3 blitz_pcode.py --profile profile.json one program.prg 0x2000
python3 blitz_pcode.py --profile profile.json recursive program.prg \
  --entry 0x2000 --start 0x2000 --end 0x4000 \
  --json-output out.json --text-output out.txt
python3 blitz_pcode.py --profile profile.json validate-trace \
  program.prg trace.json --json-output validation.json
python3 annotate_listing.py out.json annotations.json annotated.txt
```

Use `--allow-hash-mismatch` only for deliberate compatibility research. It bypasses provenance refusal, not actual incompatibility.

The deterministic gate must check:

- truncation and unknown-length refusal;
- boundary overlaps;
- branch/call target validity;
- variable-length ON/string forms;
- exact byte coverage by configured region;
- trace address/opcode and transition consistency;
- byte-identical repeated output.

### 6. Correlate semantics

Sample source correspondence across startup, arithmetic/comparisons, branches, calls, strings, variables, arrays, loops, DATA/READ, input/output, file channels, and unusual/protection paths. Confirm stack order and handler side effects before naming operations.

Keep these distinct:

- encoded static targets;
- targets conservatively inferred from structured constructs such as FOR/NEXT;
- runtime-managed or truly indirect edges.

