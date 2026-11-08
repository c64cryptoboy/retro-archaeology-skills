"""Synthetic output-safety tests; no commercial images or external packages."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from disk_image_output import MAX_INPUT_BYTES, extract_image


class OutputTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "synthetic.img"
        self.source.write_bytes(b"synthetic input")
        self.output = self.root / "extracted"

    @staticmethod
    def reader(data):
        return {"format": "synthetic", "issues": []}, {"files/entry-000/payload.bin": data[:4]}

    def test_extract_hashes_and_source_nonmutation(self):
        before = self.source.read_bytes()
        result = extract_image(self.reader, self.source, self.output)
        self.assertEqual(self.source.read_bytes(), before)
        self.assertEqual((self.output / "files/entry-000/payload.bin").read_bytes(), b"synt")
        self.assertEqual(result["input"]["sha256"], hashlib.sha256(before).hexdigest())
        self.assertEqual(result["artifacts"]["files/entry-000/payload.bin"]["sha256"], hashlib.sha256(b"synt").hexdigest())
        self.assertEqual(json.loads((self.output / "manifest.json").read_text()), result)
        self.assertNotIn(str(self.root), (self.output / "manifest.json").read_text())

    def test_deterministic_output(self):
        extract_image(self.reader, self.source, self.output)
        other = self.root / "other"
        extract_image(self.reader, self.source, other)
        self.assertEqual((self.output / "manifest.json").read_bytes(), (other / "manifest.json").read_bytes())

    def test_expected_hash(self):
        digest = hashlib.sha256(self.source.read_bytes()).hexdigest().upper()
        extract_image(self.reader, self.source, self.output, expected_sha256=digest)

    def test_bad_hash_and_mismatch_create_no_output(self):
        for digest in ("bad", "0" * 64):
            with self.subTest(digest=digest), self.assertRaises(ValueError):
                extract_image(self.reader, self.source, self.output, expected_sha256=digest)
            self.assertFalse(self.output.exists())

    def test_nonregular_input_refused(self):
        with self.assertRaisesRegex(ValueError, "regular file"):
            extract_image(self.reader, self.root, self.output)
        self.assertFalse(self.output.exists())

    @unittest.skipUnless(hasattr(os, "mkfifo"), "FIFO probe requires POSIX")
    def test_fifo_input_refused_without_waiting_for_writer(self):
        fifo = self.root / "pipe"
        os.mkfifo(fifo)
        code = "import sys; sys.path.insert(0, sys.argv[1]); from disk_image_output import extract_image; extract_image(lambda data: ({}, {}), sys.argv[2], sys.argv[3])"
        tools = Path(__file__).resolve().parents[1] / "tools"
        result = subprocess.run([sys.executable, "-B", "-c", code, str(tools), str(fifo), str(self.output)], capture_output=True, text=True, timeout=5)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Input must be a regular file", result.stderr)
        self.assertFalse(self.output.exists())

    def test_oversized_input_refused(self):
        with self.source.open("wb") as handle:
            handle.truncate(MAX_INPUT_BYTES + 1)
        with self.assertRaisesRegex(ValueError, "safety limit"):
            extract_image(self.reader, self.source, self.output)
        self.assertFalse(self.output.exists())

    def test_existing_directory_and_file_refused(self):
        for target in (self.root, self.source):
            with self.subTest(target=target), self.assertRaises(FileExistsError):
                extract_image(self.reader, self.source, target)
        self.assertEqual(self.source.read_bytes(), b"synthetic input")

    def test_missing_parent_refused(self):
        with self.assertRaises(ValueError):
            extract_image(self.reader, self.source, self.root / "absent" / "output")
        self.assertFalse((self.root / "absent").exists())

    def test_symlink_destination_refused(self):
        self.output.symlink_to(self.root / "absent", target_is_directory=True)
        with self.assertRaises(ValueError):
            extract_image(self.reader, self.source, self.output)
        self.assertFalse((self.root / "absent").exists())

    def test_symlink_parent_refused(self):
        alias = self.root / "alias"
        alias.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(ValueError):
            extract_image(self.reader, self.source, alias / "output")
        self.assertFalse((self.root / "output").exists())

    def test_existing_output_symlink_file_not_followed(self):
        self.output.mkdir()
        victim = self.root / "victim"
        victim.write_bytes(b"untouched")
        (self.output / "manifest.json").symlink_to(victim)
        with self.assertRaises(FileExistsError):
            extract_image(self.reader, self.source, self.output)
        self.assertEqual(victim.read_bytes(), b"untouched")

    def test_unsafe_artifact_paths_create_no_output(self):
        for name in ("../escape", "/absolute", "a/../escape", "a\\escape", "a//b", "a/./b", "a:b", "a\x00b", "CON", "aux.txt", "a.", "manifest.json", "MANIFEST.JSON/x"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                extract_image(lambda _: ({}, {name: b"x"}), self.source, self.output)
            self.assertFalse(self.output.exists())

    def test_path_collisions_create_no_output(self):
        for artifacts in ({"a": b"x", "A": b"y"}, {"a": b"x", "a/b": b"y"}, {"a/b": b"x", "a": b"y"}, {"Files/a": b"x", "files/b": b"y"}):
            with self.subTest(artifacts=artifacts), self.assertRaises(ValueError):
                extract_image(lambda _: ({}, artifacts), self.source, self.output)
            self.assertFalse(self.output.exists())

    def test_parse_failure_creates_no_output(self):
        def broken(data):
            raise ValueError("Unsupported format")
        with self.assertRaisesRegex(ValueError, "Unsupported format"):
            extract_image(broken, self.source, self.output)
        self.assertFalse(self.output.exists())

    def test_bad_manifest_creates_no_output(self):
        with self.assertRaises(TypeError):
            extract_image(lambda _: ({"bad": object()}, {}), self.source, self.output)
        self.assertFalse(self.output.exists())

    def test_optimized_python_keeps_safety_checks(self):
        tools = Path(__file__).resolve().parents[1] / "tools"
        code = """
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from disk_image_output import extract_image
try:
    extract_image(lambda data: ({}, {'../escape': b'x'}), sys.argv[2], sys.argv[3])
except ValueError:
    sys.exit(0)
sys.exit(7)
"""
        result = subprocess.run([sys.executable, "-B", "-O", "-c", code, str(tools), str(self.source), str(self.output)], capture_output=True, text=True, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main()
