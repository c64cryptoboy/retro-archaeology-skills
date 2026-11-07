# Simulation, runtime evidence, confidence and presentation

> Read [SKILL.md](../SKILL.md) first. This is the detailed procedure for the routed phase, not an instruction to expand every task. Commands and inline file paths below are relative to the **skill directory**, unless explicitly stated otherwise; Markdown links resolve from this reference.

### 11. Use simulation for difficult routines

When static inspection leaves uncertainty, write a small temporary Python program to reproduce the relevant algorithm.

This is encouraged for routines such as:

- PRNGs,
- checksums,
- encoders/decoders,
- bit manipulation,
- unusual arithmetic,
- lookup-driven transformations,
- coordinate calculations,
- state machines,
- procedural generation.

Keep simulations narrowly scoped.

Model the actual 6502 behavior, including where relevant:

- 8-bit wraparound,
- 16-bit wraparound,
- carry,
- borrow semantics,
- shifts and rotates,
- signed versus unsigned interpretation.

For example, when analyzing a PRNG:

1. Translate the routine faithfully.
2. Generate a sequence from known seeds.
3. Compare against values observed in Retro Debugger if possible.
4. Determine period or obvious repetition where useful.
5. Test hypotheses about output ranges or bias.
6. Use the results to improve comments.

Do not replace evidence from the real program with an unverified Python model.

The simulation should be checked against at least one known or observed case whenever practical.

### 12. Use runtime experiments when useful

When Retro Debugger is available, prefer an experiment over prolonged guessing.

Examples:

- breakpoint on routine entry,
- record A/X/Y across calls,
- watch a suspected variable,
- change a value and observe behavior,
- inspect table indexes,
- observe PRNG state transitions,
- capture memory before and after a routine.

Use dynamic observations to validate comments.

### 13. Add routine summaries

Once a routine is reasonably understood, add a concise summary near its entry point.

Example:

    ; Choose monster type for a newly spawned encounter.
    ;
    ; Uses dungeon level to select a weighted encounter table,
    ; obtains an 8-bit random value, then returns the matching
    ; monster ID in A.

Routine summaries should describe behavior, not implementation trivia.

## Instruction-level commenting

When asked to comment most assembly lines, use judgment.

Comment an individual instruction when the reader benefits from knowing:

- what a memory location means,
- what an immediate constant represents,
- why carry is being set or cleared,
- what condition a branch represents,
- what hardware effect occurs,
- what larger calculation the instruction participates in.

For sequences whose purpose is obvious once described, use one comment for the block rather than repeating commentary on every line.

For example:

    LDA screen_ptr
    CLC
    ADC #$28
    STA screen_ptr
    BCC no_carry
    INC screen_ptr+1       ; Advance screen pointer by 40 bytes
no_carry:

is preferable to five comments that simply restate the instructions.

## Confidence

When interpretation is uncertain, say so.

Useful language includes:

    ; Likely index into encounter table.

or:

    ; Appears to fold the RNG state to 5 bits.

Do not erase uncertainty merely to make the disassembly look finished.

As evidence improves, replace tentative comments with definitive ones.

## Naming

Prefer names based on purpose:

    generate_random_byte
    choose_monster
    print_status_line
    current_room
    encounter_table

Avoid names that assert more than is known.

A routine initially named:

    sub_A820

may become:

    update_rng_state

and later:

    xorshift_rng

only when evidence supports each refinement.

## Relationship to the disassembly skill

This skill focuses on understanding and documenting code already believed to be executable.

If substantial uncertainty exists about:

- code versus data,
- routine boundaries,
- entry points,
- indirect control flow,
- runtime-decrypted code,
- or cross-reference discovery,

use the `6502-disassembly` skill first or alongside this one.

Do not attempt to solve structural disassembly problems merely by adding comments to questionable assembly.

