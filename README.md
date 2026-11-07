# Retro Archaeology Skills

Reusable AI-agent skills for reverse engineering 6502 and Commodore 64 software—code, game mechanics, compiled BASIC, disk formats, and ROMs.

Based on the [CRX 2026 presentation](https://www.youtube.com/watch?v=Sk_Qlxa3ITU).

These skills are a work in progress, but give your agent a substantial head start over starting from scratch.

## Getting started

These skills are **harness- and model-agnostic**: readable workflows with supporting tools, not a plugin tied to one AI product.

Download or clone the whole repository, then ask your agent:

> Read README.md and IMPORTING-SKILLS.md, and incorporate these skills into this harness.

The [import handoff](IMPORTING-SKILLS.md) guides the importing AI through skill discovery, setup, and quick checks. Automatic discovery varies by harness; pointing it at that file works without assuming a particular installation convention. Keep the repository intact so references and shared tools remain available.

The separate [VICE/ROM handoff](IMPORTING-VICE-ROMS.md) covers optional emulator and ROM acquisition.

## Skills

| Skill | What it does |
|---|---|
| [6502-disassembly](skills/6502-disassembly/SKILL.md) | Identifies code and data, and follows 6502 control flow. |
| [6502-commenting](skills/6502-commenting/SKILL.md) | Explains assembly code's purpose, state, and calling conventions. |
| [6502-code-reuse](skills/6502-code-reuse/SKILL.md) | Finds shared or transformed routines while separating similarity from provenance. |
| [6502-size-reduction](skills/6502-size-reduction/SKILL.md) | Finds smaller implementations and checks their behavioral assumptions. |
| [game-mechanics-reversing](skills/game-mechanics-reversing/SKILL.md) | Recovers game rules and state transitions from code and observations. |
| [pcode-disassembly](skills/pcode-disassembly/SKILL.md) | Identifies and decodes supported C64 compiled-BASIC formats. |
| [c64-disk-preservation-cracking](skills/c64-disk-preservation-cracking/SKILL.md) | Preserves disk evidence and analyzes supported formats and copy protection. |
| [c64-rom-reference](skills/c64-rom-reference/SKILL.md) | Provides ROM and hardware references, plus ROM identity checks. |
| [c64-basic-v2-rnd-analysis](skills/c64-basic-v2-rnd-analysis/SKILL.md) | Explores exact C64 BASIC V2 random-number behavior and its limits. |

## Requirements and license

Python tools need Python 3.10+. See [TESTING.md](TESTING.md) for additional prerequisites and checks. ROM images are not bundled.

Original material is [MIT-licensed](LICENSE); third-party and ROM-derived material has the qualifications recorded in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Contributions

This repository is **not accepting pull requests**.
