# Importing Retro Archaeology Skills

**Handoff for the importing AI:** make these skills usable in the current harness, preserving the repository's supporting files and the user's existing configuration. The README points here so an agent examining the repository can find the setup details. This file is not an executable installer or a promise that every harness auto-loads arbitrary Markdown.

The workflows are harness- and model-agnostic. They require an agent capable of reading the instructions; running helpers additionally requires suitable tools and permissions. Different agents may produce different analysis, so keep the skills' evidence checks and stated limits.

## 1. Locate the repository and choose skills

- Resolve the actual repository root from this file's location. Keep the complete checkout in a stable, agent-readable folder, including `skills/` and `shared/6502/`. Do not copy just the `SKILL.md` files or flatten supporting directories.
- Read the [skill catalogue](README.md#skills) and the selected `skills/<name>/SKILL.md` entrypoints. Import the collection or a user-selected subset; preserve the repository even when registering only a subset, because some skills share helpers or references.
- Start with **6502-disassembly** for native code, or **pcode-disassembly** when a compiled-BASIC runtime is suspected. Other skills are task-specific; do not load every reference into context unnecessarily.

## 2. Adapt to this harness

1. Inspect the harness's documented skill-discovery mechanism. There is no universal installation folder or configuration syntax, and these skills do not require a particular provider or model.
2. Register the selected skill directories, or expose the intact repository through the harness's supported resource mechanism. Preserve existing skills/settings; get approval before replacing a conflicting installation or changing settings outside the requested import.
3. If there is no native skill registry, explicitly read the appropriate `SKILL.md` before the task and follow its relative references. This is still useful instruction-based use, not native registry integration.
4. Perform any documented reload/restart needed for discovery. Do not claim a skill is loaded merely because files were copied or a configuration file was edited.
5. Confirm that the agent can open entrypoints, follow references, and access helper scripts. If shell execution is unavailable, state that the workflows are readable but helper execution is unverified.

Keep machine-specific setup records, harness state, and test outputs outside the distributable repository. Do not add a private configuration or local absolute path to shared skill documents.

## 3. Provision only needed prerequisites

- **Reading and most offline tools:** no package installation step; Python 3.10+ for Python scripts. Most scripts use the standard library. Use the actual available interpreter (`python`, `python3`, or `py -3`) rather than assuming a launcher name.
- **VICE or ROM-backed work:** follow [IMPORTING-VICE-ROMS.md](IMPORTING-VICE-ROMS.md) for official acquisition sources, exact BASIC/KERNAL/1541 ROM mapping, paths, and identity checks. Its worked example uses Windows VICE; that does not make skill import Windows-specific. Obtain inputs only when needed and authorized. ROM images are not bundled.
- **Live debugging:** configure an appropriate emulator or real-machine workflow and any agent/debugger bridge separately. Installing VICE does not itself expose emulator controls to the harness.  The optional [RetroDebugger MCP guide](skills/retrodebugger-windows-build/references/mcp-getting-started.md) covers choosing a binary, connecting a compatible client, and checking readiness without the author's private proxy.  Importing skills or building the debugger does not establish an MCP connection; offline work and other suitable debuggers remain supported.
- **C-backed RND tests/reproduction:** GCC and a suitable POSIX/little-endian environment are required. Per-state RND classification also needs external metadata, about 10.94 GiB for the canonical file. Neither full graph reproduction nor exhaustive research validation is an import check.

Use [TESTING.md](TESTING.md) for the exact test prerequisites and environment-variable behavior. Missing required inputs must not be concealed by weakening tests or silently changing skip rules. Keep downloaded ROMs/emulators and private captures out of redistributed copies; `.gitignore` alone does not protect a folder or ZIP export.

## 4. Check a small example

Run from the repository root. These commands use only Python and synthetic/retained data, not a live emulator or ROM images. Use `-B` to avoid bytecode caches.

Create a synthetic PRG containing `LDA #$01`, `STA $D020`, and `RTS` at `$1000`. The first command refuses to overwrite an existing `tiny-example.prg`; if it already exists, preserve it and use a fresh scratch filename in all three commands instead.

```sh
python -B -c "open('tiny-example.prg', 'xb').write(bytes.fromhex('00 10 a9 01 8d 20 d0 60'))"
python -B shared/6502/dis6502.py tiny-example.prg 0x1000 3
python -B shared/6502/cfg6502.py tiny-example.prg --entry 0x1000
```

Expect three instructions at `$1000`, `$1002`, and `$1005`. The two-byte load header is not an instruction. Linear formatting does not prove that bytes are executable, and `$D020` is the C64 border-color register only under the appropriate I/O mapping. This validates basic tool routing, not hardware behavior. Keep the scratch PRG local, outside any redistributed copy.

For a compact RND query that needs no ROM, compiler, or large metadata:

```sh
python -B skills/c64-basic-v2-rnd-analysis/analysis/rnd_query.py domain
python -B skills/c64-basic-v2-rnd-analysis/analysis/rnd_query.py verify-results
```

The canonical domain contains **2,936,012,800 states**. Hash verification checks the compact result files; it does not rerun or independently prove the historical graph computation.

Finally, run the small repository checks:

```sh
python -B -m unittest discover -s tests -v
```

This is a ROM-free subset, not a claim that all tests passed. The full unchanged runner and its additional prerequisites are documented in [TESTING.md](TESTING.md). Do not launch it without its required inputs or start the exhaustive graph calculation as part of importing skills.

## 5. Report readiness and start the task

Leave a short local setup report stating:

- The repository location and selected skills.
- The actual discovery/registration method, and whether any reload is still needed.
- Checks run, their results, and anything unavailable or untested.
- Remaining ROM, compiler, metadata, or debugger-integration requirements.

Then ask for or use the user's actual investigation goal and authorized inputs. Keep originals read-only and derived outputs separate. These skills support evidence-driven analysis; passing a helper test does not establish cycle-accurate machine behavior, universal format support, or identical results across agents.
