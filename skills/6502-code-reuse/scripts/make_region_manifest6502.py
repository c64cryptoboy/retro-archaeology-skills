#!/usr/bin/env python3
"""Wrap one raw binary as a validated generic 6502 byte-region manifest."""

from __future__ import annotations

import argparse
from pathlib import Path

from region_manifest import artifact_record, build_manifest, region_record, write_manifest


def parse_int(value: str) -> int:
    return int(value, 0)


def create_manifest(
    source: Path,
    output_dir: Path,
    region_id: str,
    *,
    base_address: int | None = None,
    kind: str = "cpu-memory",
    cpu_profile: str = "6502-nmos",
    known_mask: Path | None = None,
) -> dict:
    data = source.read_bytes()
    if not data:
        raise ValueError("raw region must not be empty")
    output_dir.mkdir(parents=True, exist_ok=True)
    region_name = f"{region_id}.bin"
    (output_dir / region_name).write_bytes(data)

    mask_data = None
    mask_name = None
    if known_mask is not None:
        mask_data = known_mask.read_bytes()
        if len(mask_data) != len(data):
            raise ValueError("known mask must have the same size as the region")
        mask_name = f"{region_id}.known.mask"
        (output_dir / mask_name).write_bytes(mask_data)

    region = region_record(
        region_id=region_id,
        path=region_name,
        data=data,
        kind=kind,
        source={
            "container": "raw-binary",
            "artifactPath": str(source.resolve()),
            "fileOffset": 0,
            "endOffsetExclusive": len(data),
        },
        base_address=base_address,
        cpu_profile=cpu_profile,
        known_mask_path=mask_name,
        known_mask=mask_data,
    )
    manifest = build_manifest(
        artifact=artifact_record(source, data, "raw-binary"),
        regions=[region],
        capture={"adapter": "make_region_manifest6502.py"},
    )
    write_manifest(output_dir / "regions.json", manifest)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--id", required=True, dest="region_id")
    parser.add_argument("--base-address", type=parse_int)
    parser.add_argument("--kind", default="cpu-memory")
    parser.add_argument("--cpu-profile", default="6502-nmos")
    parser.add_argument("--known-mask", type=Path)
    args = parser.parse_args()
    try:
        manifest = create_manifest(
            args.source,
            args.output_dir,
            args.region_id,
            base_address=args.base_address,
            kind=args.kind,
            cpu_profile=args.cpu_profile,
            known_mask=args.known_mask,
        )
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    region = manifest["regions"][0]
    print(
        f"wrote {args.output_dir / 'regions.json'}: "
        f"{region['id']} size={region['size']} sha256={region['sha256']}"
    )


if __name__ == "__main__":
    main()
