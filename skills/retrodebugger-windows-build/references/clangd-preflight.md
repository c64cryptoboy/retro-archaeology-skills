# Bounded source preflight without an extension

A direct clangd check can expose source errors before an expensive native build without loading an editor extension into the agent process.  It does not establish Windows build, link, or runtime success.

## Use

From the skill directory, with Python 3.10+, a POSIX host, and an existing clangd executable:

```sh
python3 scripts/clangd_preflight.py --source /path/to/source.cpp --database /path/to/reviewed-cdb --output /path/to/new-evidence --clangd /usr/bin/clangd --timeout 60
python3 -B -m unittest discover -s scripts -p 'test_clangd*.py' -v
```

The compilation database must contain exactly one matching entry with an explicit `arguments` array.  Review its target, definitions, include order, and source identity first.  A hand-built analysis context is not automatically the project's native build command.  Inputs and flags are trusted local material, not sandboxed untrusted content.

The output directory must be new.  The helper saves the command, raw log, input hashes, tool hash, process status, and JSON classification.  It resolves PATH or relative executable names before changing directories, so the launch path and recorded tool identity agree.  It uses private cache/config/temp directories, disables clangd configuration lookup and query-driver execution, bounds the process group to at most 120 seconds, and kills/reaps the child on interruption or a wait failure.  It does not install tools, change the source, generate a global database, invoke a build, or execute target code.

| Exit | Meaning |
|---|---|
| 0 | The selected check mode completed with no reported errors under these flags. |
| 1 | The check completed with source findings. |
| 2 | Coverage unavailable: missing context, fallback command, tool failure, timeout, incomplete log, or changed input. |

Review raw logs and `result.json`, not only the exit code.  An unfamiliar diagnostic format may require classifier maintenance; this is not a universal clangd protocol parser.  Feature-check failures remain tool errors even when usable compiler diagnostics are present.  In particular, `tweak: ExtractFunction ==> FAIL: Cannot extract break/continue without corresponding loop/switch statement.` must not be suppressed to produce a clean result.

## Explicit translation-unit scope

The default `--mode full` remains unchanged: it includes token-level editor-feature checks.  If the goal is source preflight rather than testing those editor features, explicitly select a separate scope:

```sh
python3 scripts/clangd_preflight.py --source /path/to/source.cpp --database /path/to/reviewed-cdb --output /path/to/new-tu-evidence --mode translation-unit
```

This adds clangd's existing `--check-locations=false` control.  It retains parsing, indexing, inlay hints, and semantic highlighting, but omits token-by-token editor-feature tests, including attempted refactorings.  It is **not a diagnostics-only mode**, and a clean result does not clear a failed full check.  There is no automatic retry or fallback between modes.

Both JSON output and the CLI summary identify `check_mode`, `omitted_checks`, and `native_acceptance: false`.  Translation-unit results require observed AST, indexing, inlay-hint, and semantic-highlighting phases and refuse unexpected token testing.  The same diagnostic, missing-context, tool-error, timeout, input-change, and completion rules still apply.  No error lines are suppressed; an unsupported option or unfamiliar log yields unavailable coverage.

The control and scope were source-checked and exercised with clangd 18.1.3.  The option is hidden even from its help listing, so do not assume cross-version compatibility.  Pinned sources: [check phases and control](https://github.com/llvm/llvm-project/blob/llvmorg-18.1.3/clang-tools-extra/clangd/tool/Check.cpp), [ExtractFunction control-flow rejection](https://github.com/llvm/llvm-project/blob/llvmorg-18.1.3/clang-tools-extra/clangd/refactor/tweaks/ExtractFunction.cpp), and [expected-refusal tests](https://github.com/llvm/llvm-project/blob/llvmorg-18.1.3/clang-tools-extra/clangd/unittests/tweaks/ExtractFunctionTests.cpp).  A refused extraction may be valid original C++ whose selection excludes the enclosing loop or switch; it is not itself proof of a broken compilation environment.

## Limits

The helper uses POSIX process-group termination and is not a native Windows runner.  A Linux analysis result does not cover MSVC, the Windows SDK, linking, complete project configurations, or runtime behavior.  Do not broaden an unavailable check into repeated prerequisite repair: preserve the blocker, keep genuine negative controls, and return to the authorized build goal.

Optional history-saving containment in a separate extension is a different concern from correct C++ compile context.  No extension activation or update is implied by this workflow.  Native acceptance still follows [validation and delivery](validation-and-delivery.md).
