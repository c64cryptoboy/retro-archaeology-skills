---
name: c64-disk-preservation-cracking
description: Analyze and neutralize copy protection in legitimately preserved Commodore 64 disk software so aging floppy software can be studied, archived, and made reliably runnable. Use with disk-based C64 software and 1541 drive code when tracing loaders, identifying protection checks, analyzing uploaded drive-resident 6502 code, classifying non-standard disk formats, or producing a minimally modified preservation copy. This skill does not cover tape or cartridge protection. Preserve the original image first, prefer minimal patches, document evidence and changes, and do not publish or redistribute copyrighted software.
---

# C64 Disk Preservation Cracking

Analyze **legitimately preserved disk-based C64/1541 software** and, when requested, create a minimally modified runnable derivative. This does not cover tape/cartridge protection, modern DRM, network authentication, license servers or redistribution of copyrighted software.

Two separate deliverables may be needed: an immutable **preservation master** retaining the best available media fidelity, and a **runnable preservation copy** with a failing/unrepresentable dependency removed. A cracked D64 never replaces the archival master.

## Before doing anything destructive

1. Preserve/hash the original and all higher-fidelity captures; experiment on copies only. Record image type, sides/tracks, error metadata, hardware/emulator and exact scope.
2. Establish whether failure is caused by software, image fidelity, emulation or missing physical behavior. D64 cannot encode many raw/physical features; missing data may be unrecoverable. Do not patch to conceal an unexplained capture failure.
3. Keep C64 **6510** and drive **6502** address spaces separate. Uploaded drive RAM may hold code, a key, or staged data; do not assume all protection is visible in C64 RAM.
4. Do not force “pass” until the exact predicate **and success-only side effects** are known: repair, decoding, vectors, initialization and register state may be required.
5. Preserve unrelated loader/program behavior; prefer the smallest justified intervention. Do not infer a commercial protection family or exact hardware-bit meaning from superficial resemblance.
6. Record observed facts, strong inferences and tentative hypotheses separately. Boot success alone does not establish a complete crack or absence of delayed checks.

## Required reading at each phase

Load only the current phase and applicable references, but do so **before** its actions. A narrow diagnostic need not perform a full preservation project; an end-to-end crack must satisfy all applicable gates.

| When | Read | Required evidence before advancing |
|---|---|---|
| First preservation task or scope/authority ambiguity | [Preservation contract](references/preservation-contract.md) | Master versus derivative, scope and two-computer model |
| Offline G64 sector/file reading or narrow RapidLok-like record inspection/decoding | [Read-only G64 helpers](references/g64-readers.md) | Preserved input, strict standard interpretation, recognition versus explicit-profile record decoding, and limits |
| Before baseline execution, extraction, filesystem edits or choosing a format | [Media and baseline](references/media-and-baseline.md) | Hashes/fidelity, baseline, raw directory/chains/BAM/error-table audit |
| Tracing loading, drive uploads, unusual tracks or the check itself | [Loader and authentication](references/loader-and-authentication.md) | Captured code/mapping, measured behavior, precise pass/fail predicate and success effects |
| Before patching or reconstructing decoded payload | [Patching and transforms](references/patching-and-transforms.md) | Later-check search, selected minimal strategy, transform state/bounds and paired CPU transfers |
| Runtime/raw-track experiments and acceptance of a derived image | [Validation and delivery](references/validation-and-delivery.md) | Controlled observations, cold/later-load/save/restart tests and exact patch ledger |
| Reconnaissance cross-check, hardware clues, final stop decision or citations | [Checklists and sources](references/checklists-and-sources.md) | Coverage of delayed/filesystem checks, limitations and attributed sources |

## Working sequence

1. **Baseline:** preserve originals, identify represented versus missing media behavior, and observe the unmodified image when execution is in scope. Use a known-good original trace if available.
2. **Map:** audit actual directory records, chains, BAM and error metadata, not just rendered names/counts. Follow C64 loading and capture any uploaded 1541 stages before they are overwritten.
3. **Trace the decision:** follow measured disk behavior through returned status/key/flags to the program's decision. Inspect BASIC/native hybrids, rewritten line bodies/links and copied survival stubs.
4. **Check later dependencies:** inspect callers, result consumers, later uploads and ordinary OPEN/LOAD/INPUT#/GET#/command-channel I/O, generated names and sentinels. A second protection layer need not use physical tricks.
5. **Choose and justify a derivative:** patch a decision/result only if it preserves required effects; otherwise retain useful loading, normalize it, or reconstruct a stable payload with explicit initialization/relocation obligations.
6. **Validate and document:** compare the declared lifecycle against the preserved original where possible. Retain original/replacement bytes, ranges, hashes, reason for each change, environment and residual limitations.

## Tool and evidence boundaries

Use `6502-disassembly` for code/data/CFG and runtime decoding; use `6502-commenting` only after structure is established. For C64/1541 hardware, workspace and ROM addresses, consult the [ROM-reference skill](../c64-rom-reference/SKILL.md), especially its [1541 map](../c64-rom-reference/references/1541-symbols.md). Verify CPU/mapping/revision rather than importing C64 meanings into drive RAM.

Use a debugger that provides the needed breakpoints, registers, traces, and memory captures.  Confirm the available backend can inspect the **drive CPU**, not merely the C64. Missing drive/track facilities are an evidence limit, not a reason to invent observations.

Bundled tools provide strict standard-GCR extraction and explicitly scoped RapidLok and later Vorpal record inspection.  They do not provide a general D64/G64/NIB track-analysis suite or a general loader-transform simulator.  Use existing disassembly helpers where their documented opcode/state scope fits, or report the missing capability. Never infer magnetic layout solely from a C64 RAM dump. Keep payload-sector changes separate from error-table changes; controlled derivatives should change one relevant factor and retain both hashes.

For simulation, establish source/destination, exact transformation, key/register/RAM state and loop bounds, then compare against runtime evidence before trusting the output. Unsupported instructions or missing state remain explicit. Scope or permission may prevent a needed experiment; report that gap rather than execute unrelated work.

## Completion gate

A runnable derivative is ready only within its stated validation scope: master preserved; loader and C64/drive responsibilities mapped; check and required effects evidenced; minimal changes audited; delayed checks investigated; cold boot and relevant later loads, transitions, save/load and restart tested; all limits retained. Do not require unrelated loader bytes to be fully reversed once the preservation dependency is established. Do not call a boot-only test whole-program validation, and do not publish proprietary inputs or derived images.
