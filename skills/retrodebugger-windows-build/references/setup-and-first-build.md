# Scope, checkout, toolchain and first build

> Read [SKILL.md](../SKILL.md) first. This is the detailed procedure for the routed phase, not an instruction to expand every task. Commands and inline file paths below are relative to the **skill directory**, unless explicitly stated otherwise; Markdown links resolve from this reference.

## 1. Establish scope

Ask or confirm:

- contributor build versus release packaging;
- `x64` versus `ARM64`;
- `Debug` versus `Release`;
- `MSVC` versus `ClangCL`;
- CUDA enabled or intentionally skipped;
- whether dependency repositories may be patched;
- whether fixes are local-only, fork-backed, or intended for later upstream review.

Do not silently downgrade a requested Debug build to Release merely because Release libraries already exist.

## 2. Inspect current build contracts

Before installing or changing anything, read:

- RetroDebugger's current `README.md` and `build-windows.ps1`;
- its Windows workflow under `.github/workflows/`;
- the release script, if release behavior matters;
- MTEngineSDL's `README.md` and the dependency/child scripts actually invoked by the current driver (their locations change);
- project `RuntimeLibrary`, `LibraryPath`, `AdditionalDependencies`, and toolset settings.

Revalidate these contracts on every new application/engine revision. A moving `MTENGINE_REF` is not a reproducible pin; record both resolved commits. SDL/build-system migrations can invalidate earlier paths, cached-library assumptions, and repair patches. Inspect whether upstream already contains each fix; never blindly replay a historical build branch.

Compare documented support with actual CI coverage. Clang Release CI does not validate MSVC Debug. Check active upstream branches: a dependency's development branch may already contain a broader replacement for a defect on its default branch, but do not switch branches without checking application compatibility.

## 3. Create and record the checkout manifest

A typical layout is:

```text
C:\develop\retrodebugger-work\
├── RetroDebugger\
├── MTEngineSDL\
└── uSockets\
```

Record for every repository:

```bat
git remote -v
git branch --show-current
git rev-parse HEAD
git status --short
```

Configure a contributor fork as `origin` and the author's repository as `upstream`. Preserve original revisions before repairs. Use Windows Git when evaluating Windows checkouts; a Linux Git process can report thousands of CRLF-only modifications. If cross-environment inspection is unavoidable, verify `core.autocrlf` before interpreting status.

Never commit generated libraries, build trees, logs, PDBs, executables, smoke profiles, or line-ending-only rewrites.

## 4. Verify the native toolchain

From a fresh Visual Studio developer shell, capture:

```bat
where cl
cl
where msbuild
msbuild -version
cmake --version
git --version
```

Also record installed MSVC toolset and Windows SDK versions when relevant. A script saying “v143” is not proof of the exact compiler selected; inspect its toolset override and any manual `PATH` manipulation.

Install only missing components required by the agreed matrix. For an MSVC build this normally means Desktop development with C++, MSBuild, CMake tools, Git, a Windows SDK, and the requested MSVC toolset.

## 5. Run the first build without source edits

From RetroDebugger's root, use the repository's current command.  In a Visual Studio developer PowerShell, a representative x64 MSVC Debug build without CUDA is:

```powershell
& .\build-windows.ps1 -Platform x64 -Configuration Debug -Compiler MSVC -SkipCuda *> ..\build-msvc-x64-debug.log
```

The `*>` all-streams redirection is PowerShell syntax, not `cmd.exe` syntax.  Confirm the selected revision's parameters and any script-execution policy requirements before running it; do not silently change machine-wide policy.

Do not run a clean unless needed; it destroys useful incremental evidence. For the first reproduction, avoid environment-variable workarounds. Wait for the prompt to return before inspecting or editing shared source.

Analyze the transcript from the skill directory:

```bash
python3 scripts/analyze_build_log.py /path/to/build-msvc-x64-debug.log
```

The helper exits 0 for a success marker without a substantive error, 1 when it finds a substantive error (even if a later false success marker exists), and 2 when the transcript is incomplete or indeterminate. Exit 0 alone is not acceptance: inspect `warning_counts` for CRT/linker conflicts and apply the gates below.
