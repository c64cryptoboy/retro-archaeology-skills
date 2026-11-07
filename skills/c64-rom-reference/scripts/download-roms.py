#!/usr/bin/env python3
"""Download and hash-verify the stock ROMs used by c64-rom-reference.

ROM images are not bundled; this downloader acquires pinned revisions only
through explicit user invocation.  Existing valid files are retained.  Existing
invalid files refuse replacement unless --replace-invalid is supplied.
"""

from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from rom_manifest import ROMS, Rom, RomPart


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROM_DIR = Path(os.environ.get("C64_ROM_DIR", ROOT / "assets" / "roms"))
USER_AGENT = "C64-ROM-Reference-Downloader/1"


class DownloadError(RuntimeError):
    pass


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def validate_data(name: str, rom: Rom, data: bytes) -> None:
    if data[:512].lstrip().lower().startswith((b"<!doctype html", b"<html")):
        raise DownloadError(f"{name}: server returned HTML instead of a ROM")
    if len(data) != rom.size:
        raise DownloadError(
            f"{name}: size {len(data)} does not match expected {rom.size}"
        )
    actual = digest(data)
    if actual != rom.sha256:
        raise DownloadError(
            f"{name}: SHA-256 {actual} does not match expected {rom.sha256}"
        )


def existing_valid(path: Path, rom: Rom) -> bool:
    if not path.is_file():
        return False
    data = path.read_bytes()
    return len(data) == rom.size and digest(data) == rom.sha256


def fetch_part(part: RomPart, *, timeout: float, opener=urlopen) -> bytes:
    request = Request(part.url, headers={"User-Agent": USER_AGENT})
    try:
        with opener(request, timeout=timeout) as response:
            status = getattr(response, "status", 200)
            if status != 200:
                raise DownloadError(f"HTTP status {status} from {part.url}")
            data = response.read(part.size + 1)
    except (HTTPError, URLError, OSError) as error:
        raise DownloadError(f"download failed for {part.url}: {error}") from error
    if data[:512].lstrip().lower().startswith((b"<!doctype html", b"<html")):
        raise DownloadError(f"server returned HTML instead of a ROM: {part.url}")
    if len(data) != part.size:
        raise DownloadError(
            f"downloaded size {len(data)} does not match expected {part.size}: {part.url}"
        )
    actual = digest(data)
    if actual != part.sha256:
        raise DownloadError(
            f"downloaded SHA-256 {actual} does not match expected "
            f"{part.sha256}: {part.url}"
        )
    return data


def fetch(rom: Rom, *, timeout: float, opener=urlopen) -> bytes:
    return b"".join(
        fetch_part(part, timeout=timeout, opener=opener) for part in rom.parts
    )


def install_one(
    name: str,
    rom: Rom,
    output_dir: Path,
    *,
    replace_invalid: bool,
    timeout: float,
    opener=urlopen,
) -> str:
    destination = output_dir / rom.filename
    if destination.exists():
        if not destination.is_file():
            raise DownloadError(f"{name}: destination is not a file: {destination}")
        if existing_valid(destination, rom):
            return f"{name}: already valid: {destination}"
        if not replace_invalid:
            raise DownloadError(
                f"{name}: existing file is invalid; inspect it or use "
                f"--replace-invalid: {destination}"
            )

    data = fetch(rom, timeout=timeout, opener=opener)
    validate_data(name, rom, data)
    output_dir.mkdir(parents=True, exist_ok=True)
    temporary_name = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", prefix=f".{rom.filename}.", suffix=".tmp",
            dir=output_dir, delete=False,
        ) as temporary:
            temporary.write(data)
            temporary.flush()
            os.fsync(temporary.fileno())
            temporary_name = Path(temporary.name)
        os.replace(temporary_name, destination)
        temporary_name = None
    finally:
        if temporary_name is not None:
            temporary_name.unlink(missing_ok=True)
    return (
        f"{name}: installed {destination}; size={rom.size}; "
        f"sha256={rom.sha256}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", nargs="*", choices=tuple(ROMS),
                        help="ROM name(s); default installs all pinned ROMs")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_ROM_DIR)
    parser.add_argument("--replace-invalid", action="store_true")
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--delay", type=float, default=0.25,
                        help="seconds between downloads (default: 0.25)")
    args = parser.parse_args()
    if args.timeout <= 0 or args.delay < 0:
        parser.error("--timeout must be positive and --delay must be nonnegative")

    selected = args.rom or list(ROMS)
    failures = []
    for index, name in enumerate(selected):
        try:
            print(install_one(
                name, ROMS[name], args.output_dir,
                replace_invalid=args.replace_invalid, timeout=args.timeout,
            ))
        except DownloadError as error:
            failures.append(str(error))
            print(f"ERROR: {error}")
        if index + 1 < len(selected) and args.delay:
            time.sleep(args.delay)
    if failures:
        print(f"failed to install {len(failures)} of {len(selected)} ROM(s)")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
