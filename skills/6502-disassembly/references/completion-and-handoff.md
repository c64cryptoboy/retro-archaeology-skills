# Naming, worklists and completion

> Read [SKILL.md](../SKILL.md) first. This is the detailed procedure for the routed phase, not an instruction to expand every task. Commands and inline file paths below are relative to the **skill directory**, unless explicitly stated otherwise; Markdown links resolve from this reference.

### 11. Assign semantic names incrementally

Begin with neutral names.

Replace them with semantic names only when evidence supports a role.

For example:

    sub_A430
        ↓
    scan_keyboard
        ↓
    scan_keyboard_and_update_repeat_state

Prefer precise descriptive names over speculative broad names.

Do the same for data:

    byte_B100
        ↓
    current_room
        ↓
    current_room_index

### 12. Iterate to convergence

After analyzing a meaningful region:

- revisit unknown areas,
- revisit unresolved xrefs,
- revisit indirect control flow,
- revisit suspicious data/code boundaries,
- revisit routines whose callers are now better understood,
- revisit temporary names,
- look for newly exposed entry points.

Reverse engineering is iterative.

New knowledge about one routine often changes the interpretation of another.

## Worklist discipline

For substantial analysis, maintain an explicit conceptual worklist containing items such as:

- unexplored function,
- unresolved branch target,
- unresolved indirect jump,
- unidentified table,
- unexplained memory write,
- suspected self-modifying instruction,
- suspected encoded region,
- unresolved memory move, relocation fixup, or overlay lifetime,
- unknown hardware access.

Prefer completing or intentionally deferring worklist items rather than wandering opportunistically through the binary. At meaningful handoff points, run `disassembly-report.py` from the CFG JSON and a reviewed notes JSON to preserve confirmed facts, hypotheses, and the remaining worklist.

## C64-specific cautions

On a Commodore 64:

- ROM and RAM may occupy the same CPU addresses depending on `$0001`.
- VIC-II memory visibility differs from CPU memory visibility.
- `$D000-$DFFF` may represent I/O, character ROM, or RAM.
- programs often replace KERNAL IRQ handling,
- zero-page locations may be repurposed,
- screen memory is not necessarily `$0400`,
- character data is not necessarily the ROM character set,
- disk loaders and protection systems may relocate or decode executable code.

Inspect machine state rather than assuming default BASIC configuration.

## Completion criteria

A region is reasonably analyzed when:

- every byte in the declared region has a code/data/unused/excluded/unknown classification;
- reachable code is identified and every confirmed reachable instruction is accounted for within a mechanically understood block or explicit open item;
- major routine entry points are labeled,
- callers and callees are known where practical,
- obvious data structures are classified,
- indirect flow has been investigated,
- suspected self-modifying or decoded code has been handled,
- relevant memory moves have source/destination stage maps, recovered runtime bytes, evidenced entries, and explicit fixup or overlap assumptions;
- remaining unknown areas are explicitly identified,
- semantic names reflect evidence rather than guesswork.

Do not claim the entire binary is understood merely because every byte can be rendered as assembly.

