#!/usr/bin/env python3
"""Shared schema helpers for platform-neutral extracted byte regions."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Sequence

SCHEMA_VERSION = 1
REGION_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")


class ManifestError(ValueError):
    pass


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def artifact_record(path: Path, data: bytes, format_name: str) -> dict[str, Any]:
    return {
        "path": str(path),
        "format": format_name,
        "size": len(data),
        "sha256": sha256(data),
    }


def region_record(
    *,
    region_id: str,
    path: str,
    data: bytes,
    kind: str,
    source: dict[str, Any],
    base_address: int | None = None,
    cpu_profile: str | None = None,
    scan_by_default: bool = True,
    known_mask_path: str | None = None,
    known_mask: bytes | None = None,
) -> dict[str, Any]:
    region: dict[str, Any] = {
        "id": region_id,
        "path": path,
        "kind": kind,
        "size": len(data),
        "sha256": sha256(data),
        "scanByDefault": scan_by_default,
        "source": source,
    }
    if base_address is not None:
        region["baseAddress"] = base_address
    if cpu_profile is not None:
        region["cpuProfile"] = cpu_profile
    if (known_mask_path is None) != (known_mask is None):
        raise ManifestError("known_mask_path and known_mask must be supplied together")
    if known_mask is not None and known_mask_path is not None:
        if len(known_mask) != len(data):
            raise ManifestError("known mask size must equal region size")
        region["knownMask"] = {
            "path": known_mask_path,
            "sha256": sha256(known_mask),
            "meaning": "zero byte is unknown; nonzero byte is known",
        }
    return region


def build_manifest(
    *,
    artifact: dict[str, Any],
    regions: Sequence[dict[str, Any]],
    capture: dict[str, Any] | None = None,
) -> dict[str, Any]:
    manifest: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "artifact": artifact,
        "regions": list(regions),
    }
    if capture is not None:
        manifest["capture"] = capture
    validate_manifest(manifest)
    return manifest


def _require_int(value: Any, field: str, *, minimum: int = 0) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise ManifestError(f"{field} must be an integer >= {minimum}")
    return value


def validate_manifest(manifest: dict[str, Any], output_dir: Path | None = None) -> None:
    if not isinstance(manifest, dict):
        raise ManifestError("manifest must be an object")
    if manifest.get("schemaVersion") != SCHEMA_VERSION:
        raise ManifestError(f"unsupported schemaVersion {manifest.get('schemaVersion')!r}")

    artifact = manifest.get("artifact")
    if not isinstance(artifact, dict):
        raise ManifestError("artifact must be an object")
    for field in ("path", "format", "sha256"):
        if not isinstance(artifact.get(field), str) or not artifact[field]:
            raise ManifestError(f"artifact.{field} must be a nonempty string")
    _require_int(artifact.get("size"), "artifact.size")
    if not SHA256.fullmatch(artifact["sha256"]):
        raise ManifestError("artifact.sha256 must be lowercase SHA-256")

    regions = manifest.get("regions")
    if not isinstance(regions, list) or not regions:
        raise ManifestError("regions must be a nonempty array")
    ids: set[str] = set()
    paths: set[str] = set()
    for index, region in enumerate(regions):
        prefix = f"regions[{index}]"
        if not isinstance(region, dict):
            raise ManifestError(f"{prefix} must be an object")
        region_id = region.get("id")
        if not isinstance(region_id, str) or not REGION_ID.fullmatch(region_id):
            raise ManifestError(f"{prefix}.id is not a stable lowercase slug")
        if region_id in ids:
            raise ManifestError(f"duplicate region id {region_id!r}")
        ids.add(region_id)

        relative_path = region.get("path")
        if (
            not isinstance(relative_path, str)
            or not relative_path
            or Path(relative_path).is_absolute()
            or ".." in Path(relative_path).parts
        ):
            raise ManifestError(f"{prefix}.path must be a contained relative path")
        if relative_path in paths:
            raise ManifestError(f"duplicate region path {relative_path!r}")
        paths.add(relative_path)

        size = _require_int(region.get("size"), f"{prefix}.size", minimum=1)
        digest = region.get("sha256")
        if not isinstance(digest, str) or not SHA256.fullmatch(digest):
            raise ManifestError(f"{prefix}.sha256 must be lowercase SHA-256")
        if not isinstance(region.get("kind"), str) or not region["kind"]:
            raise ManifestError(f"{prefix}.kind must be a nonempty string")
        if not isinstance(region.get("scanByDefault"), bool):
            raise ManifestError(f"{prefix}.scanByDefault must be boolean")
        if not isinstance(region.get("source"), dict) or not region["source"]:
            raise ManifestError(f"{prefix}.source must be a nonempty object")
        if "baseAddress" in region:
            _require_int(region["baseAddress"], f"{prefix}.baseAddress")
        if "cpuProfile" in region and (
            not isinstance(region["cpuProfile"], str) or not region["cpuProfile"]
        ):
            raise ManifestError(f"{prefix}.cpuProfile must be a nonempty string")
        known_mask = region.get("knownMask")
        if known_mask is not None:
            if not isinstance(known_mask, dict):
                raise ManifestError(f"{prefix}.knownMask must be an object")
            mask_path = known_mask.get("path")
            if (
                not isinstance(mask_path, str)
                or not mask_path
                or Path(mask_path).is_absolute()
                or ".." in Path(mask_path).parts
            ):
                raise ManifestError(f"{prefix}.knownMask.path must be contained and relative")
            mask_digest = known_mask.get("sha256")
            if not isinstance(mask_digest, str) or not SHA256.fullmatch(mask_digest):
                raise ManifestError(f"{prefix}.knownMask.sha256 must be lowercase SHA-256")
            if not isinstance(known_mask.get("meaning"), str) or not known_mask["meaning"]:
                raise ManifestError(f"{prefix}.knownMask.meaning must be nonempty")

        if output_dir is not None:
            file_path = output_dir / relative_path
            if not file_path.is_file():
                raise ManifestError(f"missing region file {file_path}")
            data = file_path.read_bytes()
            if len(data) != size:
                raise ManifestError(
                    f"{region_id}: manifest size {size} != file size {len(data)}"
                )
            if sha256(data) != digest:
                raise ManifestError(f"{region_id}: SHA-256 mismatch")
            if known_mask is not None:
                mask_file = output_dir / known_mask["path"]
                if not mask_file.is_file():
                    raise ManifestError(f"missing known-mask file {mask_file}")
                mask_data = mask_file.read_bytes()
                if len(mask_data) != size:
                    raise ManifestError(f"{region_id}: known-mask size mismatch")
                if sha256(mask_data) != known_mask["sha256"]:
                    raise ManifestError(f"{region_id}: known-mask SHA-256 mismatch")


def write_manifest(path: Path, manifest: dict[str, Any]) -> None:
    validate_manifest(manifest, path.parent)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
