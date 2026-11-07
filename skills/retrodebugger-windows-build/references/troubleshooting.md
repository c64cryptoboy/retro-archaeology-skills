# Windows build troubleshooting

Use this reference after the first failing build has been preserved. Diagnose the earliest substantive error, not the final PowerShell stack trace.

## Failure classes

| Evidence | Likely class | First checks |
|---|---|---|
| `C2xxx` or `C4xxx` | compiler/source | Exact translation unit, toolset, language mode, preceding diagnostic |
| `LNK1104` | library discovery | Does the file exist for this architecture/configuration? Inspect project `LibraryPath`; do not replace inherited SDK paths. |
| `LNK2001`/`LNK2019` | unresolved symbol | Declaration linkage, defining object inclusion, dead stripping differences, required dependency library |
| `LNK2038`/`LNK4098` | incompatible runtime/configuration | `/MTd`, `/MT`, `/MDd`, `/MD`; Debug versus Release archives; explicit CRT libraries |
| `LNK4217`/`LNK4286` in bulk | imported/static CRT mixture | Inspect the named archive's generated project or compile command; rebuild it with the app's CRT. |
| `LNK4099` | dependency PDB unavailable | Usually non-fatal. Record which dependency lacks symbols; do not claim full dependency symbols. |
| `CMake Error` followed by apparent progress | ignored native exit code | Every script invocation must check `$LASTEXITCODE` or throw through a checked wrapper. Reject stale outputs. |
| requested Debug but log says Release | argument/config propagation | Compare parent invocation names with child `param(...)`; inspect output paths and generated project runtime settings. |

## Configuration identity

Treat a native archive as compatible only when these dimensions agree:

- architecture (`x64` versus `ARM64`);
- compiler ABI/toolset;
- configuration (`Debug` versus `Release`);
- CRT (`/MTd` for static Debug, `/MT` for static Release, or the project's chosen dynamic equivalents);
- feature defines that affect public structures or allocation ownership.

A library being found does not make it compatible. Do not fix `LNK1104` by globally replacing `LIB` or `LibraryPath`; that can hide Windows SDK paths and merely move the failure to `version.lib` or another system library. Append a narrow project-level path while retaining `$(LibraryPath)`.

For CMake dependencies that must follow `/MTd` or `/MT`, establish policy `CMP0091` before the relevant targets and pass a concrete `CMAKE_MSVC_RUNTIME_LIBRARY` value. Verify the generated `.vcxproj`; command-line intent is not evidence that the project accepted the setting.

A project that selects `MultiThreadedDebug` (`/MTd`) but explicitly links `msvcrtd.lib` is mixing static and dynamic Debug CRTs. The Release equivalent is `/MT` plus `msvcrt.lib`. If the static runtime is the established application/dependency contract, remove the contradictory explicit import library, not the selected CRT or its warning. Confirm with a native relink and PE imports; if conflicts remain, inspect linked object/archive directives with native `dumpbin /directives` or linker `/VERBOSE:LIB` evidence. Do not assume every cached archive follows its script's intended flags.

## Platform headers, character encoding, and strict diagnostics

These are revision-dependent failure classes, not patches to apply to every checkout:

- **Wrong-platform headers:** adding `#include "SYS_FileSystem.h"` cannot fix a missing Windows declaration if Linux's same-named header wins first. Enumerate duplicate headers and inspect the ordered effective includes, using native `/showIncludes` or preprocessing when necessary. Remove foreign-platform search paths from Windows configurations rather than inventing duplicate declarations. Check every edited configuration; static XML checks do not certify unbuilt architectures.
- **New UTF-8 defaults versus legacy byte literals:** C4828/codepage 65001 may precede misleading C2001 "newline in constant" and syntax cascades. Inspect raw bytes before saving through a Unicode editor. For intentional single-byte character/string data, fixed-width octal escapes can preserve values without disabling UTF-8 globally or expanding characters to multibyte sequences. Verify exact byte reversal and native compilation. Distinguish runtime literals from non-ASCII comments; do not silently transliterate credits or rewrite whole files.
- **C4146 under `/sdl`:** security checks can promote unsigned unary-negation warnings. For an intentional unsigned magnitude, `0U - (unsigned_type)value` can preserve modulo arithmetic, including the signed minimum input, but first verify actual type widths/promotions and test boundary values. Do not replace it with potentially overflowing signed negation or disable security checks globally.
- **Hjson proxy/string ambiguity:** a proxy may expose competing conversions under MSVC. A reviewed repair materializes `Hjson::Value`, checks its type, and then selects its explicit string-reference conversion. Recheck the current API and lifetime before reusing that pattern.

Preserve original line endings and encodings in each focused repair. Keep native compile/link/smoke evidence separate from static arithmetic, XML, hash, or reverse-substitution checks. Revalidate all of these lessons when repository versions change.

## Linkage and optimization traps

A Release build can hide unresolved references by discarding unreachable functions. Debug often retains more code. If a C++ file references a global defined in a `.c` translation unit, declare it at namespace/file scope inside `extern "C"`; a block-local C++ declaration requests a different symbol.

Do not infer that a path is supported merely because another configuration links. Compare the exact CI matrix with the requested local matrix. A project that tests only Clang Release provides no evidence for MSVC Debug.

## PowerShell orchestration

For each native command:

```powershell
& cmake @args
if ($LASTEXITCODE -ne 0) { throw "configure failed" }
```

`$ErrorActionPreference = 'Stop'` does not by itself turn every nonzero native exit into a terminating PowerShell error. A script that continues can package stale libraries and print a false success marker.

Windows PowerShell 5 can also turn ordinary native stderr into `NativeCommandError` under `ErrorActionPreference=Stop`, even for harmless CMake warnings. A narrow wrapper may temporarily use `Continue` around the native child/pipeline, capture `$LASTEXITCODE` immediately, and restore the preference in `finally`. Never use this to ignore the child's real failure.

Before a multi-step mutating script, parse it natively with `[System.Management.Automation.Language.Parser]::ParseFile` and inspect the returned errors; brace counts are not a parser test. Brace variable interpolation before a colon (`${Repo}:`). Check `cl.exe` and MSBuild availability before branch changes or manifest writes; a normal PowerShell window is not a Visual Studio developer shell.

Resumable wrappers should preserve full prior logs/manifests, verify exact reviewed changes, avoid forced branch resets, and reject stale EXE/PDB outputs. Guard narrowly against known generated files without deleting them. A timed-out container Git command on a large Windows share can leave a lock; do not infer absence of Windows Git processes from container process enumeration. Prefer native Windows Git status.

For startup diagnostics, continuously drain both redirected output pipes or leave them unredirected. An unread pipe can block logging and manufacture a GUI stall. Bound automated waits, distinguish the application window from console/error dialogs, preserve partial evidence, and clean up only owned processes. A temporary helper rename must be restored in `finally`, with the original hash checked and a documented recovery path if the shell itself is killed.

Make cache/stamp identity include all material inputs: source revision, script revision, architecture, configuration, compiler, CRT, and feature switches. When selecting files from a multi-configuration CMake tree, constrain the search to the requested configuration rather than taking the first recursive filename match.

## Settings isolation is an observable contract

Do not infer fresh-profile isolation from setting `LOCALAPPDATA`. A native Windows application can use `SHGetFolderPathW` and ignore that override. Inspect the exact revision's supported setting (for example, `MT_SETTINGS_DIR`), create a new directory before launch, and confirm the application's logged resolved path. A dedicated automated-test folder avoids normal workspace writes but may retain state from earlier tests.

If this check was missed, distinguish observed GUI behavior from unproven fresh-profile behavior. Correct draft claims and handoffs, preserve logs/current settings without overwriting the originals, and disclose the mistake. A post-test backup cannot reconstruct the pre-test workspace.

## Clean evidence

A successful acceptance record should include:

- repository URLs, exact revisions, branch names, and dirty/clean state;
- Visual Studio, MSBuild, CMake, Git, compiler, SDK, architecture, configuration, and feature switches;
- exact command and complete transcript hash;
- explicit absence/presence of compiler, linker, CMake, and mixed-CRT errors;
- executable and PDB paths, sizes, and SHA-256 hashes;
- dependency-symbol limitations such as Release-only SDL PDB warnings;
- clean-profile launch observations.

Build success is not runtime success. At minimum confirm window creation, absence of assertion/error dialogs, basic menu response, and clean shutdown.
