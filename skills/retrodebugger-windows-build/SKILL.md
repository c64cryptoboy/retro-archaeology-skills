---
name: retrodebugger-windows-build
description: Establish, diagnose, repair, and validate reproducible native Windows contributor builds of RetroDebugger and its sibling MTEngineSDL/uSockets dependencies. Use for Visual Studio/MSVC or ClangCL setup, Debug/Release configuration, CRT and linker failures, dependency orchestration, build-log evidence, symbol verification, clean-profile smoke tests, and keeping build repairs isolated from unrelated pull requests. Also use when changing RetroDebugger MCP tool registrations to check bridge tool-list tests and cross-platform CI coverage before a PR, or preparing an owner-run Git commit/push handoff after scoped validation.
license: MIT
compatibility: Native Windows source builds require Visual Studio with C++, CMake, Git, and a Windows SDK; the portable log analyzer requires Python 3.10+ standard library; optional clangd preflight requires a POSIX host and clangd; MCP use requires a compatible client and debugger binary.
---

# RetroDebugger native Windows builds

Use a suitable [official prebuilt release](https://github.com/slajerek/RetroDebugger/releases) when it provides the capabilities you need.  A source build is optional: use it for unreleased features, source changes, or a configuration unavailable in the release.  Building does not connect an agent to the debugger; follow [MCP setup and readiness](references/mcp-getting-started.md) separately.  The archaeology skills also support offline analysis and other appropriate debuggers.

When a Windows source build is needed, produce a reproducible contributor build and separately evidenced runtime acceptance. Execute compiler/linker/dependency and runtime acceptance commands on **native Windows**, not WSL or a Linux container. An agent can inspect shared sources/logs elsewhere. The bundled Python log analyzer is portable; no particular agent harness is required.

## Route by phase, before acting

| Trigger | Read | Gate / output |
|---|---|---|
| Choose a release, or connect an agent through MCP | [MCP setup and readiness](references/mcp-getting-started.md) | Choose a supported binary/transport; verify the actual tool roster and responsive emulator |
| Any new build or change in scope | [Build contract](references/build-contract-and-mcp.md) and [Setup/first build](references/setup-and-first-build.md) | Exact revision/toolchain/configuration manifest; inspect current upstream scripts before launching |
| Optional source diagnostics before a native build | [Bounded clangd preflight](references/clangd-preflight.md) | Reviewed explicit compile context; findings or unavailable coverage, never Windows acceptance |
| Compiler/linker/wrapper failure or CRT warnings | [Troubleshooting](references/troubleshooting.md) and diagnosis in [Validation/delivery](references/validation-and-delivery.md) | First substantive error, narrow source-backed hypothesis, smallest repair |
| Linking succeeds, EXE changes, clean-profile smoke or patch delivery | [Validation/delivery](references/validation-and-delivery.md) | Artifact/log hashes, CRT/PE checks, isolated-profile runtime evidence and focused patch state |
| Add/remove/rename an MCP tool | [MCP roster regression gate](references/build-contract-and-mcp.md#mcp-tool-roster-regression-gate) | Connected and after-reconnect tool-list tests; disconnected roster separate; actual CI suite results |
| Prepare a contributor commit/push handoff | [Owner-run Git handoff](references/validation-and-delivery.md#10-owner-run-git-handoff) | Reuse the established owner workflow; task-scoped script, one exact invocation, guarded changes, and no agent-side publication |

Load only the applicable phases. For a log-only question, do not install a toolchain, rebuild or launch the GUI merely because the full workflow includes those steps.

Before expanding a feature into new tracking, synchronization, or stronger guarantees, explain the implementation, runtime-cost, and validation consequences to the user and obtain their scope choice.  Offer a narrow existing-behavior PR and a separate exploratory PR when appropriate; do not discover the cost through an unapproved build/test campaign.  Keep prerequisite diagnosis bounded: preserve the original failure, distinguish inherited defects from new regressions, and return to the requested feature when a repair stops converging.  Do not weaken tests or expand the agreed scope to obtain a passing result.

## Invariants and common traps

- Pin application, engine and dependency revisions/remotes, architecture, Debug/Release, compiler/toolset, CRT and optional features. Match all static dependencies; a moving `MTENGINE_REF` or “v143” label is not an exact resolved build identity.
- Read the current README/build scripts/workflows and project settings. Historical commands and fixes are examples, not guaranteed contracts for a new revision. Keep adjacent checkouts where the current driver requires them.
- Use a fresh Visual Studio developer shell; no accidental LIB/INCLUDE/PATH experiments in acceptance. Do not silently change Debug to Release or install Clang/CUDA/another toolchain.
- Preserve every material transcript; never edit source during an active build. Diagnose the first real error, not the final wrapper message. Avoid unnecessary clean rebuilds that destroy incremental evidence.
- Do not suppress CRT warnings to claim success. Resolve configuration/architecture/runtime mismatches; check generated flags/projects and, after CRT repair, final PE imports. An incremental relink does not erase earlier compile warnings.
- Successful linking is not runtime acceptance. Require expected EXE/PDB and distinguish dependency-symbol limitations; repeat smoke when the EXE hash changes.
- Profile isolation must be **observed**, not assumed from environment variables. `LOCALAPPDATA` alone may not redirect Windows shell-folder APIs. Verify the revision supports its chosen override (such as `MT_SETTINGS_DIR`) and confirm actual `pathToSettings`; never rename/delete the user's normal profile as a shortcut.
- A legacy LogConsole helper can trigger a .NET prompt independently of the native GUI. Treat it as an unresolved observation; isolate only with permission and restore/verify the helper. Helper-disabled smoke is qualified evidence, not a product fix.
- Preserve surrounding style, encodings and line endings; no unrelated cleanup/refactors/upgrades. Use Windows Git for Windows checkout status, or account for CRLF configuration before interpreting apparent mass changes.
- Keep build-enablement repairs separate from unrelated bug commits. No generated outputs/logs/PDBs in commits; no push or PR without explicit approval. Upstream fixes belong in RetroDebugger/maintained dependencies, not client proxies unless that work is explicitly requested.
- Tool-registration changes require both connected and reconnect roster checks in `CTestMCPBridge.cpp`; a new tool can work while stale hard-coded counts break the suite. Inspect current CI jobs rather than treating green build jobs as test execution.

## Smallest useful tool

From this skill directory, analyze a preserved transcript:

```bash
python3 scripts/analyze_build_log.py BUILD.log
```

Exit 0 means a standalone success-marker line with no detected substantive error and all requested artifacts present; 1 means a detected error, even with a later marker, or a requested artifact missing from an otherwise successful log; 2 means incomplete/indeterminate.  `warning_counts` retains coded keys such as `C4996` and `LNK4099`, adds Clang option keys such as `-Wunused-variable`, and uses `uncoded` for recognized warnings without either.  Counts are transcript occurrences, not unique defects.  Inspect the original evidence before acceptance.  [Validation/delivery](references/validation-and-delivery.md) includes supported diagnostic/encoding forms, artifact hashing, optional JSON reporting, and native smoke commands.

## Deliverable and stop gate

Report exact revisions/configuration, command/log hash, artifact paths/sizes/hashes, warnings and first-failure/fix evidence, actual smoke observations/profile location, local/fork/PR state and remaining gaps. If native Windows is unavailable, deliver analysis/staged commands as **not yet executed**, with expected evidence and the next contingent action; do not label static review as runtime validation.

Stop after the requested build/repair/acceptance question is answered. Do not turn a missing dependency, optional feature, or unresolved runtime observation into an unbounded build matrix or unrelated product investigation.
