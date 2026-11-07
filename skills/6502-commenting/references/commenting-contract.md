# Commenting objectives and style

> Read [SKILL.md](../SKILL.md) first. This is the detailed procedure for the routed phase, not an instruction to expand every task. Commands and inline file paths below are relative to the **skill directory**, unless explicitly stated otherwise; Markdown links resolve from this reference.

# 6502 Code Commenting

Use this skill to turn structurally correct 6502 disassembly into understandable documented code.

Assume that another analysis pass has substantially established code versus data boundaries.

The goal is not to translate each opcode into English.

The goal is to explain what the program is doing.

## Primary objective

For each routine, progressively determine:

- what inputs it consumes,
- what outputs it produces,
- what state it modifies,
- what registers it preserves or destroys,
- what significant memory locations mean,
- what loops accomplish,
- what branches represent logically,
- what algorithm or game/program behavior is being implemented.

Add comments and labels that capture this meaning.

For a declared complete routine/region, account for every confirmed reachable instruction even when only one block-level comment is needed for several obvious opcodes. If an instruction's effect or reason does not fit the current routine model, retain an explicit unresolved note instead of leaving it silently uncommented. “Accounted for” does not mean mechanically paraphrasing every opcode.

## Commenting philosophy

Prefer semantic comments:

    LDA $42
    BEQ no_monster       ; Skip combat when room contains no monster

over mechanical comments:

    LDA $42              ; Load address $42 into accumulator
    BEQ no_monster       ; Branch if equal

The reader already knows 6502 assembly.

Comments should explain information that is not obvious from the opcode itself.

### Useful comments include

- purpose of hardware registers,
- meaning of variables,
- interpretation of flags,
- reason for unusual arithmetic,
- loop purpose,
- table semantics,
- state transitions,
- computed values,
- invariants,
- side effects,
- algorithmic intent,
- correspondence to visible program behavior.

### Avoid redundant comments

Do not routinely write comments such as:

    INX             ; Increment X
    DEX             ; Decrement X
    CLC             ; Clear carry
    RTS             ; Return

unless the operation has a meaningful contextual role worth explaining.

For example:

    CLC             ; Add movement delta without previous carry

can be useful.

