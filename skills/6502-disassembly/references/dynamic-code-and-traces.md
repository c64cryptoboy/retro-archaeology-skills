# Indirect flow, mutation and runtime evidence

> Read [SKILL.md](../SKILL.md) first. This is the detailed procedure for the routed phase, not an instruction to expand every task. Commands and inline file paths below are relative to the **skill directory**, unless explicitly stated otherwise; Markdown links resolve from this reference.

### 7. Resolve indirect control flow

Pay special attention to:

    JMP ($xxxx)

and computed dispatch patterns.

Run `indirect-flow6502.py` to enumerate the static sites and candidate direct pointer-byte writers, then determine how the destination pointer is populated.

Trace backwards to identify:

- tables of addresses,
- state-machine dispatch,
- function-pointer variables,
- interrupt vectors,
- patched code,
- self-modifying jump operands.

Where possible, enumerate plausible runtime destinations and add them to the analysis worklist.

### 8. Detect self-modifying code

Look for stores into addresses that are also executable.

Common patterns include modification of:

- immediate operands,
- absolute address operands,
- branch behavior,
- jump targets,
- loop constants.

Capture comparable memory/PRG images before and after the suspected writer, then run `code-write-diff.py` with CFG and/or execution coverage. If code writes into its own instruction stream, annotate the affected instructions and reason about their runtime forms rather than treating the static bytes as authoritative.

### 9. Detect runtime decoding and deobfuscation

For untransformed memory copies, relocation fixups, and overlays, first use [memory moves and runtime relocation](memory-moves-and-relocation.md).  Copying, decoding, and decompressing can occur at startup or later, and can be chained.  A decompressor's internal copy loop does not make the packed payload a plain move; establish its format/algorithm or capture the scoped unpacked output without claiming general unpacker support.

Look for loops that transform memory before execution, especially patterns involving:

- EOR,
- ADC/SBC transformations,
- ROL/ROR,
- table substitution,
- copying encoded bytes to another region,
- modifying a block in place.

A common case is an EOR loop that decodes executable code before jumping into it.

When such a loop is found:

1. Identify source region.
2. Identify destination region if different.
3. Determine exact transform.
4. Determine loop bounds.
5. Determine initial CPU/register state required by the loop.
6. Reconstruct the resulting bytes.
7. Disassemble the reconstructed bytes at their runtime address.
8. Continue normal recursive analysis from newly revealed entry points.

Do not manually transform large regions if automation is appropriate. Run `decode-loop6502.py` with an explicit `--start`, initial A/X/Y/carry values, required `--set ADDRESS=BYTE` RAM values, and a conservative instruction limit. Save its JSON output as evidence, inspect its changed-byte list and trace, then disassemble the changed runtime address range. If it stops at an unsupported opcode, missing state, indirect flow, or instruction limit, do not extrapolate: capture runtime state or extend the tool with a focused tested opcode implementation.

### 10. Examine runtime behavior when static analysis is ambiguous

Use Retro Debugger dynamically when available. Export PC/register samples as JSON Lines and run `trace6502.py` to preserve observed coverage and transitions; use its `executedPcs` output as input to `code-write-diff.py` when investigating mutation.

Useful techniques include:

- execute breakpoints,
- memory-read breakpoints,
- memory-write breakpoints,
- stepping through uncertain code,
- inspecting registers at entry points,
- watching pointer values,
- determining actual indirect JMP destinations,
- determining which branches occur,
- observing code generated or decoded at runtime.

Static analysis and dynamic analysis should reinforce one another.

If dynamic execution disproves a static inference, update the disassembly.

