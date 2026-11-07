# Preservation contract and two-computer model

> Read [SKILL.md](../SKILL.md) first. This is the detailed procedure for the routed phase, not an instruction to expand every task. Commands and inline file paths below are relative to the **skill directory**, unless explicitly stated otherwise; Markdown links resolve from this reference.

# C64 Disk Preservation Cracking

Use this skill when reverse-engineering copy protection in Commodore 64 **disk-based** software for legitimate preservation, research, interoperability, repair, or archival use.

The target environment is a C64 running software from a Commodore 1541-compatible disk drive.  Use a debugger with the C64 and drive facilities needed for the chosen observations; no particular debugger or agent harness is required.

This skill covers:

- C64-side loaders and protection checks,
- 1541-side uploaded machine code,
- IEC communication between the C64 and drive,
- custom disk formats,
- GCR-level and track-level protection concepts,
- runtime decryption associated with disk loaders,
- protection checks occurring during boot or later gameplay,
- creation of a minimally modified runnable preservation copy.

This skill does **not** cover:

- cassette/tape protection,
- cartridge protection,
- modern DRM,
- network authentication,
- license-server circumvention,
- redistribution of copyrighted software.

The purpose is preservation and understanding of historical C64 disk software.

## Core principles

### Preserve before modifying

Before changing code or disk data:

1. Preserve the best available original disk image.
2. Record its hash.
3. Keep it immutable.
4. Perform all experiments on copies.
5. If multiple image formats are available, retain the highest-fidelity capture.

Do not make the only surviving archival copy a cracked or normalized image.

A protection-stripped D64 is useful for execution and study, but it is **not a substitute for a preservation-quality representation of the original disk**.

### Distinguish two goals

Treat these as separate deliverables.

**Preservation master:** an image intended to retain the original disk's physical or logical behavior as faithfully as practical.

**Runnable preservation copy:** a derived copy whose protection has been neutralized or whose loader has been adapted so the software runs reliably in an emulator or from replacement media.

When practical, keep both.

### Prefer minimal intervention

When creating a runnable preservation copy, prefer the smallest change that makes the software independent of the failing or unrepresentable protection.

Good outcomes include:

- bypassing one authentication test,
- replacing a protection result with the expected success result,
- removing a dependence on an unrepresentable disk feature,
- adapting a loader while leaving game/program code unchanged.

Avoid rewriting large portions of the program merely because a smaller patch is harder to discover.

### Preserve original behavior

The cracked preservation copy should behave like the original after authentication.

Verify:

- loading,
- title screens,
- menus,
- gameplay/program startup,
- later disk loads,
- save/load behavior if applicable,
- multi-disk transitions,
- delayed protection checks.

A successful boot alone does not prove the protection has been fully neutralized.

### Separate fact from hypothesis

Label conclusions as:

- observed,
- strongly inferred,
- tentative.

Do not declare a protection mechanism identified merely because it resembles a known family.

## Understand the two computers

A disk-based C64 program may contain code executing on **two separate 6502-family processors**:

1. the C64's 6510,
2. the 1541 drive's 6502.

The 1541 is an intelligent peripheral with its own ROM, RAM, VIA hardware, disk controller behavior, and executable RAM.

Custom loaders frequently upload code into the 1541 and execute it there.

Therefore:

> Never assume all relevant protection logic is visible in C64 RAM.

When behavior cannot be explained from C64-side code, investigate the drive.

Use the project's 1541 symbol/memory reference when analyzing drive code.

