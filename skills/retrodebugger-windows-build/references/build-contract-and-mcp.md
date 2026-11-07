# Build rules and MCP roster regression gate

> Read [SKILL.md](../SKILL.md) first. This is the detailed procedure for the routed phase, not an instruction to expand every task. Commands and inline file paths below are relative to the **skill directory**, unless explicitly stated otherwise; Markdown links resolve from this reference.

# RetroDebugger native Windows builds

Build and test on **native Windows**, not through WSL or a Linux container. An agent may inspect shared files elsewhere, but every compiler, linker, dependency, and runtime acceptance command must execute in Windows.

Read [`references/troubleshooting.md`](../references/troubleshooting.md) when a build fails or emits CRT/linker warnings. Use [`scripts/analyze_build_log.py`](../scripts/analyze_build_log.py) to summarize preserved transcripts without overlooking early failures.

## Core rules

1. Freeze exact revisions, remotes, configuration, architecture, compiler, and optional features before building.
2. Keep RetroDebugger, MTEngineSDL, and uSockets as adjacent checkouts when the active build script requires that layout.
3. Use a fresh Developer Command Prompt/PowerShell for Visual Studio; do not carry ad hoc `LIB`, `LibraryPath`, `INCLUDE`, or `PATH` experiments into acceptance runs.
4. Preserve the complete transcript for every material attempt.
5. Never edit source while a build is active.
6. Diagnose the first substantive error, not trailing wrapper output.
7. Match every static dependency's architecture, configuration, toolset, CRT, and material feature defines.
8. Do not install or enable Clang, CUDA, or another toolchain silently. Confirm scope first.
9. Do not treat successful linking as runtime acceptance.
10. Keep build-enablement commits separate from unrelated bug fixes and never open or submit a pull request without explicit approval.
11. Make surgical patches in the surrounding code's style: preserve indentation, braces, naming, idioms, line endings, and encodings unless the fix requires otherwise. No unrelated refactoring, cleanup, renaming, reformatting, or dependency upgrades. If a broader change is necessary, explain why and obtain approval first.
12. For upstream RetroDebugger issues and PRs, suggest fixes in RetroDebugger or its maintained dependencies, not in external proxies or clients. Those can provide reproduction context; propose client-side changes only when explicitly requested.

### MCP tool roster regression gate

When a RetroDebugger PR adds, removes, or renames an MCP tool, inspect `CMCPServer::RegisterDebuggerTools()` and **both** connected and after-reconnect `tools/list` checks in `src/Tests/CTestMCPBridge.cpp`. Update any hard-coded expected counts and assert the new tool is present (or the removed tool absent) at both checkpoints; keep the disconnected bridge-local roster expectation separate. Run the focused `MCPBridge` test on a build containing the change before treating the PR as tested. A new tool can work while this unrelated-looking bridge suite fails solely because its old count remains.

Check current CI workflows rather than inferring tests from green builds: in the 2026-09-26 workflows macOS runs `tests/run_test.sh --skip-build` in both logging configurations, but Windows/Linux build and stage without the application suite. Inspect the actual macOS suite results on both legs; Windows/Linux success alone cannot establish `MCPBridge` passed. Do not pin a particular tool count in this skill—it changes with the roster.
