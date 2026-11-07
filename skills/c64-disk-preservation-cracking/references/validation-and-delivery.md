# Dynamic observations, raw tracks, validation and notes

> Read [SKILL.md](../SKILL.md) first. This is the detailed procedure for the routed phase, not an instruction to expand every task. Commands and inline file paths below are relative to the **skill directory**, unless explicitly stated otherwise; Markdown links resolve from this reference.

## Phase 11 -- Use a debugger dynamically

Prefer experiments over prolonged speculation.

Useful operations include:

- break on C64 execution,
- break on C64 memory read/write,
- inspect C64 registers,
- inspect CIA2 IEC state,
- capture C64 memory before/after load,
- inspect drive RAM,
- break on drive execution from RAM,
- break on drive VIA accesses,
- inspect drive registers,
- record drive head/track behavior when available,
- compare memory at successive loader stages.

High-value breakpoint ideas:

- first execution in uploaded drive RAM,
- first write to drive VIA #2,
- C64 code immediately after disk authentication returns,
- write to a suspected protection-result flag,
- execution of a suspected decryptor,
- first execution in newly decoded C64 memory.

Do not leave broad breakpoints active if they create so much noise that causal relationships become unclear.

## Phase 12 — Inspect raw track information when needed

Sector-level analysis is insufficient for many protections.

When available, inspect:

- raw GCR track bytes,
- track length,
- half-track content,
- sync runs,
- duplicate headers,
- unusual density,
- repeated reads,
- bytes outside standard sectors.

The bundled [G64 readers](g64-readers.md) have narrow, documented coverage.  No general D64/G64/NIB analysis suite is bundled.  When selecting an external tool for broader structural evidence, establish which of these operations it actually supports:

- reading D64/G64/NIB metadata,
- listing represented tracks/half tracks,
- reporting track lengths,
- identifying standard GCR headers,
- flagging duplicate sector IDs,
- flagging unusual sync runs,
- comparing multiple captures of the same track,
- detecting likely non-standard encoding,
- exporting raw track bytes.

Use only supported operations, and report missing capabilities.  Never infer magnetic layout solely from C64 memory.

## Phase 13 — Validate the crack

A preservation crack is complete only after meaningful validation.

Test:

- cold boot,
- reset/restart if relevant,
- all initial loads,
- representative gameplay/program use,
- later disk accesses,
- level/area transitions,
- multi-load content,
- save/load if applicable,
- multiple emulator runs,
- at least one clean startup from the derived image.

If possible, compare behavior against the preserved original.

Watch for:

- delayed crashes,
- corrupted graphics,
- subtly wrong data,
- missing levels,
- bad decompression,
- checksum failures,
- drive hangs,
- protection checks that trigger only occasionally.

## Phase 14 — Produce preservation notes

Document the result.

Recommended notes:

```text
Title:
Publisher:
Year:
Disk side:
Original media/image:
Original image hash:
Derived image hash:

Protection observed:
Image-format limitations:
C64 protection routines:
1541 uploaded code:
1541 protection routines:
Tracks/sectors/regions involved:
Authentication result path:
Runtime decryption:
Patch location(s):
Original bytes:
Replacement bytes:
Reason for patch:

Validation performed:
Known limitations:
```

Keep observations separate from assumptions.

If the crack depends on emulator behavior, record emulator and drive-model versions.

