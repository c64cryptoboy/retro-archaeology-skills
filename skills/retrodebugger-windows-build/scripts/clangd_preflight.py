#!/usr/bin/env python3
"""One explicit clangd --check, never a build or an acceptance substitute.

Default full mode includes token-level editor tests.  Opt-in translation-unit
mode omits them; it still parses, indexes, and checks inlay/semantic features.
Exit 0: selected mode completed, no reported errors; 1: completed with findings;
2: coverage unavailable (including missing context, timeout, or tool failure).
Inputs are trusted local source and a reviewed, explicit compilation database.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import time


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def kill_and_reap(proc):
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass  # The child may have exited between wait and cleanup.
    return proc.wait(timeout=5)


def capture(argv, cwd, env, log, timeout):
    """Bound a process group; retain raw output, even on timeout or failure."""
    started = time.monotonic()
    result = {"argv": argv, "timeout_seconds": timeout, "exit_code": None,
              "timed_out": False, "launch_error": None}
    with Path(log).open("xb") as stream:
        try:
            proc = subprocess.Popen(argv, cwd=cwd, env=env, stdout=stream,
                                    stderr=subprocess.STDOUT, start_new_session=True)
            try:
                result["exit_code"] = proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                result["timed_out"] = True
                result["exit_code"] = kill_and_reap(proc)
            except BaseException:
                kill_and_reap(proc)
                raise
        except OSError as exc:
            result["launch_error"] = str(exc)
    result["elapsed_seconds"] = round(time.monotonic() - started, 3)
    return result


def classify(log, process):
    """Fail closed on incomplete checks, context errors, and unknown tool errors."""
    errors = re.findall(r"^E\[[^\]]+\] (.*)$", log, re.M)
    diagnostics = [line for line in errors if re.match(r"\[[^\]]+\] Line \d+:", line)]
    completed = re.findall(r"All checks completed, (\d+) errors", log)
    reasons = []
    if process["launch_error"]:
        reasons.append("launch_failure")
    if process["timed_out"]:
        reasons.append("timeout")
    if len(completed) != 1:
        reasons.append("missing_or_ambiguous_completion")
    if "Compile command from CDB is:" not in log or "Generic fallback command" in log:
        reasons.append("explicit_compile_command_not_confirmed")
    context_codes = ("pp_file_not_found", "pp_hash_error", "fatal_too_many_errors",
                     "drv_", "err_drv_", "module_not_found", "module_file_not_found")
    if any(any(code in line for code in context_codes) for line in diagnostics):
        reasons.append("context_or_parse_blocker")
    if len(errors) != len(diagnostics):
        reasons.append("non_diagnostic_tool_errors")
    count = int(completed[0]) if len(completed) == 1 else None
    if process["exit_code"] not in (0, 3):
        reasons.append("abnormal_exit")
    if count is not None and (count != len(errors) or
                              (count == 0) != (process["exit_code"] == 0)):
        reasons.append("inconsistent_completion")
    status = "unavailable" if reasons else ("findings" if count else "clean")
    return {"status": status, "coverage_available": not reasons,
            "reasons": reasons, "reported_errors": count, "diagnostics": diagnostics,
            "tool_error_lines": errors}


def classify_mode(log, process, mode="full"):
    """Apply the unchanged classifier, then enforce the explicit scope evidence."""
    if mode not in ("full", "translation-unit"):
        raise ValueError("mode must be full or translation-unit")
    result = classify(log, process)
    if mode == "translation-unit":
        phases = ("Building AST...", "Indexing AST...", "Building inlay hints",
                  "Building semantic highlighting")
        if not all(re.search(r"^I\[[^\]]+\] " + re.escape(phase) + r"$", log, re.M)
                   for phase in phases):
            result["reasons"].append("translation_unit_phases_not_confirmed")
        if "Testing features at each token" in log:
            result["reasons"].append("unexpected_token_feature_testing")
        if result["reasons"]:
            result.update(status="unavailable", coverage_available=False)
    result.update(check_mode=mode, native_acceptance=False,
                  omitted_checks=["token-level editor features"] if mode == "translation-unit" else [])
    return result


def run(source, database, output, clangd="/usr/bin/clangd", timeout=60, mode="full"):
    if mode not in ("full", "translation-unit"):
        raise ValueError("mode must be full or translation-unit")
    if not math.isfinite(timeout) or not 0 < timeout <= 120:
        raise ValueError("timeout must be finite, > 0, and <= 120 seconds")
    executable = shutil.which(clangd)
    if executable is None:
        raise ValueError(f"clangd executable not found: {clangd}")
    clangd = str(Path(executable).resolve())
    source, database, output = map(lambda p: Path(p).resolve(), (source, database, output))
    db_file = database / "compile_commands.json"
    entries = json.loads(db_file.read_text())
    matches = [entry for entry in entries
               if (Path(entry["directory"]) / entry["file"]).resolve() == source]
    if len(matches) != 1 or not matches[0].get("arguments"):
        raise ValueError("require exactly one explicit arguments entry for the unchanged source")
    output.mkdir(parents=True, exist_ok=False)
    before = {"source_sha256": sha256(source), "database_sha256": sha256(db_file)}
    (output / "compile-command.json").write_text(json.dumps(matches[0], indent=2) + "\n")
    env = dict(os.environ)
    for key in ("CPATH", "CPLUS_INCLUDE_PATH", "C_INCLUDE_PATH", "OBJC_INCLUDE_PATH",
                "CLANGD_FLAGS", "SDKROOT"):
        env.pop(key, None)
    for key, subdir in (("HOME", "home"), ("XDG_CONFIG_HOME", "config"),
                        ("XDG_CACHE_HOME", "cache"), ("TMPDIR", "tmp")):
        (output / subdir).mkdir()
        env[key] = str(output / subdir)
    argv = [clangd, "--check=" + str(source), "--compile-commands-dir=" + str(database),
            "--enable-config=false", "--background-index=false", "--clang-tidy=false",
            "--pch-storage=memory", "--query-driver=", "-j=1", "--log=info"]
    if mode == "translation-unit":
        argv.append("--check-locations=false")
    process = capture(argv, str(output), env, output / "clangd.log", timeout)
    log = (output / "clangd.log").read_text(errors="replace")
    result = classify_mode(log, process, mode)
    after = {"source_sha256": sha256(source), "database_sha256": sha256(db_file)}
    if before != after:
        result.update(status="unavailable", coverage_available=False)
        result["reasons"].append("input_changed_during_check")
    result.update(process=process, source=str(source), database=str(db_file),
                  before=before, after=after, log_sha256=sha256(output / "clangd.log"),
                  clangd_realpath=str(Path(clangd).resolve()),
                  clangd_sha256=sha256(clangd) if Path(clangd).is_file() else None,
                  scope="Only the named source under the recorded analysis flags; no native acceptance.")
    (output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True)
    parser.add_argument("--database", required=True)
    parser.add_argument("--output", required=True, help="fresh evidence directory, never overwritten")
    parser.add_argument("--clangd", default="/usr/bin/clangd")
    parser.add_argument("--timeout", type=float, default=60)
    parser.add_argument("--mode", choices=("full", "translation-unit"), default="full",
                        help="full (default), or explicit translation-unit scope without token-level editor tests")
    args = parser.parse_args()
    try:
        result = run(args.source, args.database, args.output, args.clangd, args.timeout, args.mode)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"status": "unavailable", "coverage_available": False,
                          "check_mode": args.mode, "error": str(exc)}))
        return 2
    print(json.dumps({k: result[k] for k in ("status", "reported_errors", "reasons",
                                            "check_mode", "omitted_checks", "native_acceptance")}))
    return {"clean": 0, "findings": 1, "unavailable": 2}[result["status"]]


if __name__ == "__main__":
    raise SystemExit(main())
