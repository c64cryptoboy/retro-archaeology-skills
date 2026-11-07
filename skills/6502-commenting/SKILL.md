---
name: 6502-commenting
description: Analyze already identified 6502 assembly code and add useful semantic comments, labels, and explanations. Use when documenting disassembly, explaining what individual instructions and short sequences accomplish, identifying variables and hardware accesses, or deeply analyzing routines such as PRNGs, arithmetic, state machines, parsers, and algorithms. May write small Python programs to simulate difficult code when that provides stronger evidence than static inspection alone.
---

# 6502 Code Commenting

Explain **what established code does and why**, not each opcode in English. Input is structurally supported disassembly plus its machine context and evidence; output is annotated routines, justified labels/contracts and explicit unknowns. This skill does not require a particular model, harness or debugger.

## Prerequisite gate

Confirm code/data boundaries, entry points and CPU/mapping first. If structure, indirect flow or runtime-decrypted bytes remain uncertain, use `6502-disassembly` first or alongside this skill. Do not make questionable assembly look authoritative by adding polished comments.

Before commenting a routine, inspect its callers, callees, flag dependencies, referenced state/tables and all known entries/exits. Explain every confirmed reachable instruction within a block or retain an explicit unresolved item; “accounted for” does not mean one comment per opcode.

## Read by task

| Task/trigger | Required reference | Result |
|---|---|---|
| First use or deciding what deserves a comment | [Commenting contract](references/commenting-contract.md) | Semantic rather than mechanical style |
| Any routine-level annotation or new semantic name | [Routine analysis](references/routine-analysis.md) | Coverage, caller evidence, inputs/outputs/clobbers and block roles |
| Hardware, arithmetic, loops, flag-based branches or tables | [Hardware, arithmetic and tables](references/hardware-arithmetic-and-tables.md) | Proven widths, bounds, signedness, flag producers and table interpretation |
| Simulation, live experiments, final comments or confidence review | [Validation and presentation](references/validation-and-presentation.md) | Checked model/observations, confidence labels and concise summaries |

Read only applicable references, but read them **before** the corresponding analysis. For C64/1541 internal calls or register meanings, also use `c64-rom-reference` with the actual mapping/revision.

## Rules to keep visible

- Trace where branch flags were established; many instructions change N/Z implicitly. Do not translate `BEQ` into a game condition without proving its producer.
- Derive routine inputs, outputs, preserved/clobbered registers/flags, memory effects and hardware side effects. Include inline parameters and self-modified operands when material.
- Interpret arithmetic using actual widths, wraparound, carry/borrow, signedness and relevant decimal/CPU behavior. A plausible formula is a hypothesis until checked.
- Analyze tables with their consumers: entry count/width, pointer or numeric interpretation, index formula and parallel-table relationships.
- Keep neutral labels until supported. One access is not enough to rename a location `player_hp`; “likely” and “context pending” are useful, honest outcomes.
- Prefer a block comment such as “advance pointer by one 40-column row” over repeating LDA/ADC/STA meanings. Comment individual instructions when constants, flag setup or hardware effects carry nonobvious meaning.
- Simulations are evidence tools, not independent truth. Supply material state, keep tests bounded and check against a known or observed case when practical. Never claim a Python model proves the real program merely because it agrees with itself.
- Use focused runtime observations when they resolve a specific uncertainty; they do not prove unobserved paths. Preserve evidence and identify assumptions/limits.

## Routine summary template

Use only fields established by evidence; mark missing contracts unknown rather than fill them from convention:

```text
Purpose and scope:
Entry points / calling assumptions:
Inputs (registers, flags, memory, hardware):
Outputs and clobbers:
Memory / hardware side effects:
Algorithm / loop / table invariant:
Evidence and confidence:
Unresolved effects or paths:
```

## Small worked example

See the [synthetic pointer-step example](examples/README.md) for a semantic contract, carry-path explanation, and bounded executable check using the shared CPU model.

## Completion

Deliver semantic comments/labels that fit the surrounding assembly style, routine contracts, block-level instruction accountability and a retained uncertainty list. No byte modification is implied by a commenting request. A partial explanation is preferable to an unsupported complete story; if structural evidence breaks down, return to disassembly instead of guessing.
