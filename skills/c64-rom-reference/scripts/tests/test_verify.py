"""An expected revision must not identify an image with a different digest."""

import argparse
from contextlib import redirect_stdout
from dataclasses import replace
import hashlib
import importlib.util
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location("rom_tool", SCRIPTS / "rom-tool.py")
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)


class VerifyTests(unittest.TestCase):
    def test_revision_requires_a_matching_digest(self):
        good = b"test"
        fixture = replace(tool.ROMS["kernal"], revision="fixture", size=len(good),
                          sha256=hashlib.sha256(good).hexdigest())
        with tempfile.TemporaryDirectory() as directory, patch.object(tool, "ROM_DIR", Path(directory)), \
                patch.object(tool, "ROMS", {"kernal": fixture}):
            for data, code, status, field in ((good, 0, "OK", "revision"),
                                              (b"nope", 1, "MISMATCH", "expected_revision")):
                with self.subTest(status=status):
                    (Path(directory) / fixture.filename).write_bytes(data)
                    output = io.StringIO()
                    with redirect_stdout(output):
                        self.assertEqual(tool.verify(argparse.Namespace(allow_missing=False)), code)
                    self.assertEqual(output.getvalue().strip(),
                                     f"kernal: {status}; {field}=fixture; size=4 (expected 4); "
                                     f"sha256={hashlib.sha256(data).hexdigest()}")
