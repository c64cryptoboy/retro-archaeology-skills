#!/usr/bin/env python3
"""Summarize a RetroDebugger Windows build transcript without hiding early errors."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

SUCCESS_MARKER = "=== Build successful ==="
# Require a diagnostic-shaped line, not quoted commands or source/caret excerpts.
DIAGNOSTIC = re.compile(
    r"^(?!\s*(?:\d+>)?\s*(?:\+\s*)?(?:echo|Write-Host|Write-Output)\b)\s*(?:\d+>)?\s*(?:"
    r"(?:(?:[A-Z]:)?[^:\"<>|]*\(\d+(?:,\d+)?\)|(?:[A-Z]:)?[^:\"<>|]+:\d+(?::\d+)?|"
    r"(?:[A-Z]:)?[^:\"<>|]*\.(?:lib|obj|vcxproj|csproj|targets|props)(?:\([^\"<>|]*\))?|"
    r"(?:clang(?:-cl|\+\+)?|cl|link|lld-link|ld(?:\.lld)?|msbuild)(?:\.exe)?)\s*:\s*"
    r")?(?P<severity>fatal\s+error|error|warning)\s*"
    r"(?P<code>[A-Z]+\d{4,5})?\s*:\s*(?P<message>.+?)\s*$",
    re.IGNORECASE,
)
PROJECT_PREFIX = re.compile(r"^\s*\d+>\s*")
ECHO_COMMAND = re.compile(r"^\s*(?:\+\s*)?(?:echo|Write-Host|Write-Output)\b", re.IGNORECASE)
ERROR_PATTERNS = (
    re.compile(r"^\s*(?:\d+>)?\s*CMake Error(?:\s|:)", re.IGNORECASE),
    re.compile(r"^\s*(?:[^\"<>|]*\.ps1\s*:\s*)?(?:[\w.-]+\s+)?build failed\b", re.IGNORECASE),
    re.compile(r"^\s*Write-Error\s*:", re.IGNORECASE),
    re.compile(r"^\s*\+\s*CategoryInfo\s*:.*\[Write-Error\],\s*WriteErrorException\s*$", re.IGNORECASE),
    re.compile(r"^\s*System\.Management\.Automation\.RuntimeException:\s*(?:[\w.-]+\s+)?build failed\b", re.IGNORECASE),
)
CLANG_WARNING = re.compile(r"\[(-W[^\]\s,]+)\](?:\s+\[[^\]]+\])?\s*$")
DEPENDENCY_BUILD = re.compile(r"Building\s+(.+?)\s+(?:libs\s+)?\((Debug|Release|RelWithDebInfo|MinSizeRel)\)")
DEPENDENCY_HEADING = re.compile(
    r"=== Building\s+(.+?)\s+\((?:x64|ARM64)\s+(Debug|Release|RelWithDebInfo|MinSizeRel)\s+(?:MSVC|Clang)\)\s+==="
)


def decode_transcript(path: Path) -> tuple[str, str | None]:
    data = path.read_bytes()
    sample = data[:4096]
    units = len(sample) // 2
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        encoding = "utf-16"
    elif data.startswith(b"\xef\xbb\xbf"):
        encoding = "utf-8-sig"
    # Accept ASCII-dominant UTF-16LE without a BOM; sparse embedded NULs
    # in UTF-8 are not enough to select that encoding.
    elif len(data) % 2 == 0 and units and sample[1::2].count(0) > units / 2 and sample[::2].count(0) < units / 10:
        encoding = "utf-16-le"
    else:
        encoding = "utf-8"
    try:
        return data.decode(encoding), None
    except UnicodeDecodeError as error:
        # Retain complete diagnostics, but never certify a damaged transcript.
        return data.decode(encoding, errors="replace"), str(error)


def read_transcript(path: Path) -> str:
    return decode_transcript(path)[0]


def classification_line(line: str) -> str | None:
    normalized = PROJECT_PREFIX.sub("", line, count=1)
    return None if ECHO_COMMAND.match(normalized) else normalized


def is_error(line: str) -> bool:
    line = classification_line(line)
    if line is None:
        return False
    diagnostic = DIAGNOSTIC.match(line)
    return bool(diagnostic and diagnostic.group("severity").lower() != "warning") or any(
        pattern.search(line) for pattern in ERROR_PATTERNS
    )


def artifact_record(path: Path) -> dict[str, Any]:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return {"path": str(path), "size": path.stat().st_size, "sha256": digest.hexdigest()}


def analyze(log_path: Path, artifact_paths: list[Path]) -> dict[str, Any]:
    text, decoding_error = decode_transcript(log_path)
    lines = text.splitlines()
    errors = [{"line": number, "text": line.strip()} for number, line in enumerate(lines, 1) if is_error(line)]

    warning_counts: dict[str, int] = {}
    for line in lines:
        normalized = classification_line(line)
        diagnostic = DIAGNOSTIC.match(normalized) if normalized is not None else None
        if diagnostic and diagnostic.group("severity").lower() == "warning":
            code = diagnostic.group("code")
            option = CLANG_WARNING.search(diagnostic.group("message"))
            key = code.upper() if code else option.group(1) if option else "uncoded"
            warning_counts[key] = warning_counts.get(key, 0) + 1

    dependencies: list[dict[str, str]] = []
    seen_dependencies: set[tuple[str, str]] = set()
    for line in lines:
        match = DEPENDENCY_BUILD.search(line) or DEPENDENCY_HEADING.search(line)
        if match:
            key = (match.group(1).strip(), match.group(2))
            if key not in seen_dependencies:
                seen_dependencies.add(key)
                dependencies.append({"name": key[0], "configuration": key[1]})

    has_success_marker = any(line.strip() == SUCCESS_MARKER for line in lines)
    if errors:
        status = "failed"
        exit_code = 1
    elif decoding_error:
        status = "indeterminate"
        exit_code = 2
    elif has_success_marker:
        status = "successful"
        exit_code = 0
    else:
        status = "indeterminate"
        exit_code = 2

    artifacts = []
    missing_artifacts = []
    for path in artifact_paths:
        if path.is_file():
            artifacts.append(artifact_record(path))
        else:
            missing_artifacts.append(str(path))
    if missing_artifacts and exit_code == 0:
        status = "failed"
        exit_code = 1

    return {
        "log": str(log_path),
        "status": status,
        "exit_code": exit_code,
        "success_marker": has_success_marker,
        **({"decoding_error": decoding_error} if decoding_error else {}),
        "error_count": len(errors),
        "first_error": errors[0] if errors else None,
        "errors": errors,
        "warning_counts": dict(sorted(warning_counts.items())),
        "dependencies": dependencies,
        "artifacts": artifacts,
        "missing_artifacts": missing_artifacts,
    }


def print_text(result: dict[str, Any]) -> None:
    print(f"status: {result['status']}")
    print(f"success marker: {'yes' if result['success_marker'] else 'no'}")
    print(f"errors: {result['error_count']}")
    if result.get("decoding_error"):
        print(f"transcript decoding error: {result['decoding_error']}")
    if result["first_error"]:
        first = result["first_error"]
        print(f"first error: line {first['line']}: {first['text']}")
    if result["warning_counts"]:
        rendered = ", ".join(f"{code}={count}" for code, count in result["warning_counts"].items())
        print(f"warnings: {rendered}")
    if result["dependencies"]:
        rendered = ", ".join(f"{item['name']} [{item['configuration']}]" for item in result["dependencies"])
        print(f"dependency builds: {rendered}")
    for artifact in result["artifacts"]:
        print(f"artifact: {artifact['path']} ({artifact['size']} bytes, sha256 {artifact['sha256']})")
    for path in result["missing_artifacts"]:
        print(f"missing artifact: {path}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", type=Path, help="PowerShell/MSBuild transcript")
    parser.add_argument("--artifact", action="append", default=[], type=Path, help="artifact to size and hash")
    parser.add_argument("--json", action="store_true", help="emit JSON")
    args = parser.parse_args()

    if not args.log.is_file():
        parser.error(f"log file not found: {args.log}")
    result = analyze(args.log, args.artifact)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print_text(result)
    return int(result["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
