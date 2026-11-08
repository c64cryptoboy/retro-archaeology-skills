#!/usr/bin/env python3
"""Shared, standard-library CLI and fresh-output handling for disk readers.

Inputs are read only.  Existing output paths and symlinked output ancestors are
refused.  This is not a sandbox against a concurrent process changing paths.
"""

import argparse
import hashlib
import json
from pathlib import Path
import re
import stat
import sys


# Resource bound for these small disk-image formats, not a format-size claim.
MAX_INPUT_BYTES = 16 * 1024 * 1024
_COMPONENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\Z")
_RESERVED = {"CON", "PRN", "AUX", "NUL"} | {
    f"{prefix}{number}" for prefix in ("COM", "LPT") for number in range(1, 10)
}


def _artifact_paths(artifacts):
    """Validate the complete output namespace before creating any directory."""
    paths = {}
    occupied = {"manifest.json": "file"}
    spelling = {}
    for name, data in artifacts.items():
        if not isinstance(name, str) or not isinstance(data, bytes):
            raise ValueError("Artifacts require string paths and bytes values")
        parts = name.split("/")
        if any(
            not _COMPONENT.fullmatch(part)
            or part.endswith(".")
            or part.split(".", 1)[0].upper() in _RESERVED
            for part in parts
        ):
            raise ValueError(f"Unsafe artifact path: {name!r}")
        for end in range(1, len(parts) + 1):
            prefix = "/".join(parts[:end])
            key = prefix.casefold()
            kind = "file" if end == len(parts) else "directory"
            if key in spelling and spelling[key] != prefix:
                raise ValueError(f"Case-colliding artifact path: {name!r}")
            if key in occupied and (kind == "file" or occupied[key] == "file"):
                raise ValueError(f"Conflicting artifact path: {name!r}")
            spelling[key] = prefix
            occupied[key] = kind
        paths[name] = parts
    return paths


def _fresh_destination(output_path):
    output = Path(output_path).absolute()
    for component in reversed((output, *output.parents)):
        if component.is_symlink():
            raise ValueError(f"Symlinked output path is not allowed: {component}")
    if output.exists():
        raise FileExistsError(f"Output must be a new directory: {output}")
    if not output.parent.is_dir():
        raise ValueError(f"Output parent must already be a directory: {output.parent}")
    return output


def extract_image(reader, input_path, output_path, *, expected_sha256=None) -> dict:
    """Parse an image, then write artifacts and a manifest to a new directory.

    The reader returns ``(manifest, artifacts)``.  Structural diagnostics belong
    in the manifest; unsupported container/format errors raise ValueError.
    Partial outputs from an I/O failure are retained, never silently retried.
    """
    source = Path(input_path)
    output = _fresh_destination(output_path)
    if expected_sha256 is not None:
        if not re.fullmatch(r"[0-9a-fA-F]{64}", expected_sha256):
            raise ValueError("Expected SHA-256 must contain exactly 64 hex digits")
        expected_sha256 = expected_sha256.lower()
    source_stat = source.stat()
    if not stat.S_ISREG(source_stat.st_mode):
        raise ValueError(f"Input must be a regular file: {source}")
    if source_stat.st_size > MAX_INPUT_BYTES:
        raise ValueError(f"Input exceeds {MAX_INPUT_BYTES}-byte safety limit")
    with source.open("rb") as handle:
        data = handle.read(MAX_INPUT_BYTES + 1)
    if len(data) > MAX_INPUT_BYTES:
        raise ValueError(f"Input exceeds {MAX_INPUT_BYTES}-byte safety limit")
    digest = hashlib.sha256(data).hexdigest()
    if expected_sha256 is not None and digest != expected_sha256:
        raise ValueError(f"Input SHA-256 mismatch: expected {expected_sha256}, got {digest}")
    manifest, artifacts = reader(data)
    if not isinstance(manifest, dict) or not isinstance(artifacts, dict):
        raise ValueError("Reader must return manifest and artifact dictionaries")
    paths = _artifact_paths(artifacts)
    result = dict(manifest)
    result["input"] = {"name": source.name, "size": len(data), "sha256": digest}
    result["artifacts"] = {
        name: {"size": len(artifacts[name]), "sha256": hashlib.sha256(artifacts[name]).hexdigest()}
        for name in sorted(artifacts)
    }
    serialized = (json.dumps(result, indent=2, ensure_ascii=True, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")
    output.mkdir()
    for name in sorted(paths):
        destination = output.joinpath(*paths[name])
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("xb") as handle:
            handle.write(artifacts[name])
    with (output / "manifest.json").open("xb") as handle:
        handle.write(serialized)
    return result


def run_cli(reader, *, description: str) -> int:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("input", type=Path, help="Read-only disk image")
    parser.add_argument("output", type=Path, help="New output directory; its parent must exist")
    parser.add_argument("--expected-sha256", help="Optional exact input SHA-256")
    args = parser.parse_args()
    try:
        manifest = extract_image(reader, args.input, args.output, expected_sha256=args.expected_sha256)
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(f"Wrote {len(manifest['artifacts'])} artifacts and manifest.json to {args.output}")
    print("Inspect manifest diagnostics before treating extracted files as complete.")
    return 0
