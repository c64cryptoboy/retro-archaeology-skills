# Coverage, callers and routine contracts

> Read [SKILL.md](../SKILL.md) first. This is the detailed procedure for the routed phase, not an instruction to expand every task. Commands and inline file paths below are relative to the **skill directory**, unless explicitly stated otherwise; Markdown links resolve from this reference.

## Workflow

### 1. Inventory coverage and unresolved effects

Before polishing comments, enumerate the confirmed blocks/instructions in scope and identify any instruction, entry, exit, memory access, flag dependency, or side effect not explained by the current model. Maintain these as explicit open items and revisit them as callers, tables, and runtime context become clear.

### 2. Understand the routine before heavily commenting it

Inspect:

- callers,
- callees,
- incoming register values,
- outgoing register values,
- referenced memory,
- nearby tables,
- branch structure,
- hardware access.

Do not commit to a semantic explanation based solely on the first few instructions.

### 3. Identify inputs and outputs

For each routine, determine where practical:

Inputs may include:

- A, X, or Y,
- carry or other processor flags,
- zero-page variables,
- global memory,
- hardware state,
- pointer values,
- inline data following JSR,
- self-modified operands.

Outputs may include:

- A, X, or Y,
- carry/zero/negative flags,
- memory modifications,
- hardware changes,
- altered pointers,
- returned status codes.

Add a routine-level comment when enough is known.

Example:

    ; Select a random encounter.
    ;
    ; Input:
    ;   $42 = current dungeon level
    ;
    ; Output:
    ;   A = selected monster index
    ;
    ; Clobbers:
    ;   X
    ;
    ; Uses the encounter-weight table at $A840.

Only state facts supported by analysis.

### 4. Recognize logical blocks

Interpret groups of instructions as operations rather than isolated opcodes.

For example:

    LDA ptr
    CLC
    ADC #$28
    STA ptr
    BCC +
    INC ptr+1
    +

should be understood as something like:

    ; Advance pointer by one 40-column screen row.

The block-level explanation is more valuable than five individual opcode translations.

### 5. Identify memory semantics

When repeated accesses suggest a variable's meaning, assign a semantic name if the environment allows it.

Prefer:

    current_room
    player_hp
    monster_type
    rng_state
    keyboard_index
    screen_ptr

over:

    byte_42
    word_FB
    var_17

Do not rename based on a single weak inference.

If uncertain, preserve the neutral name and comment the hypothesis.

