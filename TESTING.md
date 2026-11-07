# Testing and prerequisites

Run commands from the repository root with Python 3.10 or newer.  Use `python3` if that is your interpreter's name.  The Python tools generally use the standard library; no agent harness or live emulator is needed for these offline tests.

## Small ROM-free checks

```sh
python -B -m unittest discover -s tests -v
python -B -m unittest discover -s shared/6502/tests -v
python -B -m unittest discover -s skills/6502-code-reuse/scripts/tests -v
python -B -m unittest discover -s skills/6502-disassembly/scripts/region-evidence/tests -v
python -B -m unittest discover -s skills/6502-size-reduction/tests -v
```

These are a **subset**, not an alternative claim that all bundled tests passed.  The repository checks cover layout, relative Markdown file links, machine-path markers, and selected shared-tool behavior.  Skill-local suites exercise synthetic examples and rejection boundaries.

Additional disk and p-code tests live beside their scripts.  Discover one test directory at a time; several modules have short import names and are intentionally isolated by the full runner.

## Full bundled test runner

```sh
python -B tests/run.py
```

This discovers every directory containing `test_*.py`, runs each in an isolated subprocess, and stops on failure.  It does not select an easier acceptance suite when prerequisites are missing.

Before running it, supply:

1. **GCC** and a POSIX/little-endian environment for the RND C-backed tests.
2. The exact **BASIC V2** and **KERNAL revision 3** images identified in the [ROM manifest](skills/c64-rom-reference/references/rom-manifest.md), named `basic.bin` and `kernal.bin`, in `skills/c64-rom-reference/assets/roms/`.  Use only images you are authorized to supply.  The downloader documented by [c64-rom-reference](skills/c64-rom-reference/SKILL.md) is optional, explicit, and never invoked by the test runner.

For Windows acquisition, the [VICE/ROM acquisition handoff](IMPORTING-VICE-ROMS.md) identifies a verified VICE archive and maps its BASIC, KERNAL, and 1541 ROM files to the local asset directory with size/hash checks. Installing Windows VICE alone does not satisfy the GCC/POSIX test prerequisites.

No ROM images are bundled.  Without the required images, the ROM-dependent tests **fail**, rather than silently being skipped or downloading inputs.  Keep local ROM files out of a redistributed copy.

For reproducibility, `tests/run.py` clears `PYTHONPATH`, `C64_ROM_DIR`, `C64_RND_PROJECT`, `C64_RND_RUN_DIR`, and `C64_RND_SHELL_DIR` in its subprocesses.  Setting one of those environment variables does not provision inputs for this runner.  Individual tools can use the configuration described in their own documentation.

The existing RND tests that depend on large graph metadata explicitly skip when it is absent.  Report those skips.  The compact data and bounded tests do not substitute for rerunning the exhaustive graph calculation, and the full test runner does not launch that calculation.

## Evidence boundaries

- Synthetic fixtures test the supplied implementation and documented negative controls, not every historical title, disk, or compiler revision.
- CPU-helper equivalence checks apply to the tested inputs and stated machine model.  They do not establish cycle-accurate C64/1541 behavior, banking correctness, or preservation fidelity on real hardware.
- Hash checks establish input/output identity relative to a manifest, not independent truth of the associated scientific result.
- Keep test logs and analysis outputs outside a copy intended for redistribution.  Use `-B` to avoid bytecode caches, and record interpreter/compiler versions when reporting results.
