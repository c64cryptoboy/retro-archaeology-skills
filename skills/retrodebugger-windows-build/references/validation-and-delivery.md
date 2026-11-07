# Diagnosis, artifact acceptance, smoke and patch delivery

> Read [SKILL.md](../SKILL.md) first. This is the detailed procedure for the routed phase, not an instruction to expand every task. Commands and inline file paths below are relative to the **skill directory**, unless explicitly stated otherwise; Markdown links resolve from this reference.

## 6. Diagnose one failure class at a time

For each iteration:

1. preserve and hash the log;
2. identify the first actual compiler/linker/CMake error;
3. form a narrow hypothesis;
4. inspect the defining source/project/script and generated configuration;
5. make the smallest focused repair on a dedicated branch;
6. rerun from a fresh shell when environment changes were tested;
7. confirm the original class disappeared before pursuing the next one.

Common traps include:

- ambiguous conversions accepted by one compiler but rejected by MSVC;
- a C global declared with C++ linkage;
- Release dead stripping hiding an unresolved reference that Debug retains;
- Debug projects explicitly linking `msvcrt.lib` or Release-only archives;
- replacing `LibraryPath` and thereby hiding Windows SDK libraries;
- parent PowerShell scripts forwarding the wrong child parameter;
- CMake projects ignoring `CMAKE_MSVC_RUNTIME_LIBRARY` because CMP0091 was not enabled;
- recursive library searches selecting a stale Release file before Debug;
- native command failures not checked through `$LASTEXITCODE`;
- a build script printing success after packaging stale outputs.

Do not “solve” CRT warnings by suppressing them. Rebuild the named dependency with the matching runtime and verify its generated project or compile flags.

## 7. Validate the final build

Require all of the following:

- an explicit successful build marker;
- no compiler, linker, CMake, or wrapper failure;
- no `LNK2038`, `LNK4098`, or bulk `LNK4217`/`LNK4286` mixed-CRT evidence;
- expected executable and application PDB;
- known dependency-PDB limitations reported honestly.

Distinguish incremental-build evidence from a clean full rebuild: absence of warnings on an incremental relink does not erase earlier compilation warnings. After CRT repairs, inspect the final PE import table as well as the linker log; disappearing unwanted runtime DLL imports provide independent evidence. Repeat runtime smoke when the accepted EXE hash changes.

Hash artifacts on Windows from the **RetroDebugger checkout root**, not this skill directory.  The following paths are relative to that checkout:

```powershell
Get-Item .\platform\Windows\bin\x64\Debug\c64d.exe,
         .\platform\Windows\bin\x64\Debug\c64d.pdb |
  Select-Object FullName, Length, LastWriteTime
Get-FileHash -Algorithm SHA256 .\platform\Windows\bin\x64\Debug\c64d.exe
Get-FileHash -Algorithm SHA256 .\platform\Windows\bin\x64\Debug\c64d.pdb
```

Or have the analyzer record them:

```bash
python3 scripts/analyze_build_log.py BUILD.log \
  --artifact /path/to/c64d.exe --artifact /path/to/c64d.pdb --json
```

### Portable analyzer scope

The analyzer recognizes location-prefixed MSVC and Clang/MSBuild diagnostics, including `error :` and `warning :`, bare diagnostics, selected compiler/linker tool prefixes, and common CMake/PowerShell failure lines.  Diagnostic recognition is line-shaped to avoid treating quoted commands, narrative mentions, or caret/source excerpts as failures.  Optional numeric MSBuild project prefixes are normalized for classification, including wrapper failures, without changing retained evidence.  Echo, `Write-Host`, and `Write-Output` command lines, including PowerShell `+ ` excerpts, are excluded consistently; genuine PowerShell `+ CategoryInfo` errors remain recognized.  The success marker must occupy its own line, apart from surrounding whitespace; an echoed command containing the marker is not acceptance.  `first_error` remains the earliest recognized error in log order.

UTF-8, UTF-8 BOM, and UTF-16 BOM decoding are supported.  The analyzer also recognizes ASCII-dominant BOM-less UTF-16LE by its alternating NUL-byte pattern; this is a bounded heuristic, not general encoding detection.  Damaged encodings retain decodable diagnostic lines and report `decoding_error` in JSON and text output.  That additional JSON field appears only when decoding fails; valid transcripts retain the existing field set.  A recognized error still fails; otherwise, a decoding error makes the result indeterminate, even with a success marker.  Existing CLI options, prior JSON fields, artifact hashing, and exit-code meanings are unchanged.  `warning_counts` now includes Clang `-W...` options and an `uncoded` bucket alongside existing compiler/linker codes.  Warning counts can include repeated diagnostics from the transcript and do not certify warning-free code or runtime acceptance.  Unrecognized diagnostic formats still require raw-log inspection.

## 8. Perform a clean-profile smoke test

First inspect the current settings-path implementation. Redirect only the launched process's settings root; do not rename or delete the contributor's normal profile. **Changing `LOCALAPPDATA` is not sufficient:** Windows shell-folder APIs such as `SHGetFolderPathW` do not use that environment override as the settings contract. Engine revisions supporting `MT_SETTINGS_DIR` explicitly honor that variable. An automated-test fallback folder is separate from the normal profile but is not necessarily fresh.

For a revision verified to support `MT_SETTINGS_DIR`, run the following from `cmd.exe` after adjusting the checkout and profile paths.  The example explicitly changes to the **RetroDebugger checkout root**, because contributor builds resolve resources through their working directory.  Choose a new, unused profile directory:

```bat
cd /d "C:\develop\retrodebugger-work\RetroDebugger" || exit /b 1
set "RD_ORIGINAL_MT_SETTINGS_DIR=%MT_SETTINGS_DIR%"
set "MT_SETTINGS_DIR=C:\develop\retrodebugger-work\smoke-profile-new"
mkdir "%MT_SETTINGS_DIR%"
mkdir "%MT_SETTINGS_DIR%\logs"
start "" /wait "C:\develop\retrodebugger-work\RetroDebugger\platform\Windows\bin\x64\Debug\c64d.exe" --log-dir "%MT_SETTINGS_DIR%\logs"
set "MT_SETTINGS_DIR=%RD_ORIGINAL_MT_SETTINGS_DIR%"
set "RD_ORIGINAL_MT_SETTINGS_DIR="
```

Verify the runtime log's actual `pathToSettings` points to the intended directory before claiming isolated-profile acceptance. Prefer a per-child environment and exception-safe cleanup in scripted runners. If earlier runs used an ineffective override, correct the evidence claims, preserve current settings before further launches, and tell the user; do not silently call those runs clean-profile tests.

Confirm and record:

1. the window appears;
2. no assertion or error dialog appears;
3. basic menus respond;
4. the process closes normally.

Use a new empty smoke directory for a later independent acceptance run rather than assuming an old redirected profile is still clean.

Treat optional-feature prompts as unresolved smoke observations, not automatic evidence that the main executable needs that runtime. Some Windows revisions automatically launch a bundled legacy `LogConsole.exe` targeting CLR 2.0, which triggers Windows' .NET Framework 3.5 prompt while the native GUI continues. Recheck the current startup source and exact helper PE metadata. With permission, a same-EXE test that temporarily hides only the helper and restores/verifies it in `finally` can isolate the cause without installing a Windows feature. Record this qualification; helper-disabled smoke is not a permanent product fix. Do not confuse that prompt with an MCP startup defect.

## 9. Preserve fixes without contaminating other work

Before committing:

- make working-tree status intelligible under the checkout's intended line-ending policy;
- stage explicit paths only;
- run `git diff --cached --check`;
- review every staged hunk for necessity and consistency with surrounding code; reject incidental cleanup or formatting churn;
- use focused commits and separate branches per repository.

Only with explicit user approval, push these branches to contributor-controlled forks as backups without opening pull requests. For unrelated bug work:

1. branch the bug fix from clean upstream;
2. keep only bug-specific commits there;
3. combine it with build fixes on a disposable local integration branch for MSVC Debug testing;
4. submit only the bug branch.

If a bug touches the same project, GoatTracker, or dependency-script files, resolve that overlap explicitly rather than silently including build commits.

## 10. Owner-run Git handoff

For an approved contributor PR handoff, reuse the owner's established commit/push script pattern before asking them to reconstruct it.  Inspect prior scripts and project guidance for the confirmed author identity, fork, shell, and accessible checkout/shared-path convention.  Verify the current target checkout, base, branch, patch, and destination rather than assuming an old task's paths or hashes are still current.  An agent clone with no Git identity configured is not evidence that the owner's identity is unknown.

Native-Windows-only build/runtime rules do not prohibit an established WSL/Bash workflow for Git.  Do not demand a new mapping of the agent's private checkout when a prior owner-accessible workflow can be reused.  Keep owner names, email addresses, fork choices, and local paths in private project guidance; portable skill examples should remain generic.

Prepare a small, task-scoped script for the actual owner shell:

- Verify the intended repository, base, branch, remote destination, exact source changes, and staged paths before mutation.  Keep product changes separate from build-enablement prerequisites.
- Stage explicit paths, inspect the staged diff, and run `git diff --cached --check`.  Preserve the approved author identity and any required coauthor trailer in the actual commit message, not only a PR description.
- Fail clearly on unexpected state.  Retain partial results and logs without credentials; do not reset, delete, force-push, or automatically retry an ambiguous push.
- Syntax-check and, when available, lint without executing mutations.  Deliver one exact invocation, the expected log/result path, and the next evidence-review action.

Preparing a script containing owner-approved commit/push steps does not authorize the agent to execute it, push, or create a PR.  Do not claim unseen execution succeeded, add a publishing framework, or repeat accepted build/runtime qualification merely to prepare this handoff.

## Completion report

Report:

- exact repository revisions and fix branches;
- native environment and build matrix;
- final command and log hash;
- artifact paths, sizes, and hashes;
- warning limitations;
- smoke-test observations;
- local/fork backup state;
- whether any pull request exists (normally no unless separately approved).

A successful report distinguishes confirmed facts from suspected causes and leaves enough evidence for another contributor to reproduce the result.
