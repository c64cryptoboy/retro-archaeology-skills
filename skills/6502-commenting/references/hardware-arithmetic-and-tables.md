# Hardware, arithmetic, loops and table semantics

> Read [SKILL.md](../SKILL.md) first. This is the detailed procedure for the routed phase, not an instruction to expand every task. Commands and inline file paths below are relative to the **skill directory**, unless explicitly stated otherwise; Markdown links resolve from this reference.

### 6. Decode hardware accesses

On known platforms such as the Commodore 64, recognize documented hardware locations and comment their semantic purpose.

For example:

    LDA #$00
    STA $D020       ; Border = black
    STA $D021       ; Background = black

When hardware behavior depends on individual bits, explain those bits where useful.

Do not merely repeat the symbolic register name if the operation's purpose can be inferred.

### 7. Explain arithmetic

6502 code often implements higher-level arithmetic using several instructions.

Recognize constructs such as:

- 16-bit increment/decrement,
- 16-bit addition/subtraction,
- multiplication by powers of two,
- division by shifts,
- modulo operations,
- comparisons,
- signed comparisons,
- fixed-point arithmetic,
- BCD operations,
- range mapping,
- coordinate calculations.

Comment the higher-level operation.

For example:

    ASL
    ASL
    CLC
    ADC original

may represent multiplication by 5.

Verify rather than assume.

### 8. Explain loops

For each loop, determine:

- induction variable,
- bounds,
- direction,
- termination condition,
- memory traversed,
- cumulative state,
- side effects.

Prefer:

    ; Scan all 40 characters in the current screen row.

over repeatedly describing INX and CPX.

### 9. Explain branches semantically

When possible, convert processor-condition meaning into program meaning.

Prefer:

    BEQ player_dead

with:

    ; HP reached zero

rather than:

    ; Branch if zero flag set

Trace backwards far enough to determine what established the flag.

Remember that many 6502 instructions modify N and Z implicitly.

### 10. Analyze tables together with their consumers

When code indexes a table, inspect the table.

Determine:

- element width,
- number of entries,
- signed versus unsigned interpretation,
- whether entries are pointers,
- indexing formula,
- relationship between multiple parallel tables.

Document both the table and the consuming code.

