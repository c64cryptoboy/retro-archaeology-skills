#!/usr/bin/env python3

import hashlib
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location(
    "download_roms", SCRIPTS / "download-roms.py"
)
download = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(download)

from rom_manifest import ROMS, Rom, RomPart  # noqa: E402


class Response:
    status = 200

    def __init__(self, data):
        self.data = data

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, amount):
        return self.data[:amount]


def fixture_rom(data=b"ROM!"):
    checksum = hashlib.sha256(data).hexdigest()
    return Rom(
        "test.bin", 0x8000, len(data), checksum, "test-revision",
        (RomPart("http://example.invalid/test.bin", len(data), checksum),),
    )


class DownloadRomTests(unittest.TestCase):
    def test_manifest_has_complete_pinned_source_metadata(self):
        self.assertEqual(set(ROMS), {"basic", "kernal", "chargen", "dos1541"})
        for name, rom in ROMS.items():
            with self.subTest(name=name):
                self.assertEqual(len(rom.sha256), 64)
                self.assertTrue(rom.parts)
                self.assertEqual(sum(part.size for part in rom.parts), rom.size)
                self.assertTrue(all(
                    part.url.startswith("http://www.zimmers.net/")
                    and len(part.sha256) == 64
                    for part in rom.parts
                ))
        self.assertEqual(len(ROMS["dos1541"].parts), 2)

    def test_installs_verified_bytes_atomically(self):
        data = b"ROM!"
        rom = fixture_rom(data)
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            result = download.install_one(
                "test", rom, output, replace_invalid=False, timeout=1,
                opener=lambda _request, timeout: Response(data),
            )
            self.assertIn("installed", result)
            self.assertEqual((output / rom.filename).read_bytes(), data)
            self.assertEqual(list(output.glob("*.tmp")), [])

    def test_keeps_valid_existing_file_without_network(self):
        data = b"ROM!"
        rom = fixture_rom(data)
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            (output / rom.filename).write_bytes(data)

            def unexpected(*_args, **_kwargs):
                raise AssertionError("network should not be used")

            result = download.install_one(
                "test", rom, output, replace_invalid=False, timeout=1,
                opener=unexpected,
            )
            self.assertIn("already valid", result)

    def test_invalid_existing_file_requires_explicit_replacement(self):
        good = b"ROM!"
        rom = fixture_rom(good)
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            destination = output / rom.filename
            destination.write_bytes(b"bad!")
            with self.assertRaisesRegex(download.DownloadError, "--replace-invalid"):
                download.install_one(
                    "test", rom, output, replace_invalid=False, timeout=1,
                    opener=lambda _request, timeout: Response(good),
                )
            self.assertEqual(destination.read_bytes(), b"bad!")
            download.install_one(
                "test", rom, output, replace_invalid=True, timeout=1,
                opener=lambda _request, timeout: Response(good),
            )
            self.assertEqual(destination.read_bytes(), good)

    def test_rejects_html_size_and_hash_mismatches_without_output(self):
        rom = fixture_rom(b"ROM!")
        cases = (b"<html>blocked</html>", b"bad", b"NOPE")
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            for data in cases:
                with self.subTest(data=data):
                    with self.assertRaises(download.DownloadError):
                        download.install_one(
                            "test", rom, output, replace_invalid=False, timeout=1,
                            opener=lambda _request, timeout, value=data: Response(value),
                        )
                    self.assertFalse((output / rom.filename).exists())


if __name__ == "__main__":
    unittest.main()
