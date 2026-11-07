#!/usr/bin/env python3

import importlib.util
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "analyze_build_log.py"
SPEC = importlib.util.spec_from_file_location("analyze_build_log", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class AnalyzeBuildLogTests(unittest.TestCase):
    def analyze_text(self, text: str):
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "build.log"
            log.write_text(text, encoding="utf-8")
            return MODULE.analyze(log, [])

    def test_success_with_missing_dependency_pdb_warnings(self):
        result = self.analyze_text(
            "=== Building uSockets (x64 Debug MSVC) ===\n"
            "Building mbedTLS libs (Debug)\n"
            "SDL2.lib(foo.obj) : warning LNK4099: PDB not found\n"
            "=== Build successful ===\n"
        )
        self.assertEqual("successful", result["status"])
        self.assertEqual(0, result["exit_code"])
        self.assertEqual({"LNK4099": 1}, result["warning_counts"])
        self.assertEqual(
            [
                {"name": "uSockets", "configuration": "Debug"},
                {"name": "mbedTLS", "configuration": "Debug"},
            ],
            result["dependencies"],
        )

    def test_first_compile_error_wins_over_trailing_failure_noise(self):
        result = self.analyze_text(
            "source.cpp(10): error C2440: cannot convert\n"
            "build-windows.ps1 : RetroDebugger build failed\n"
        )
        self.assertEqual("failed", result["status"])
        self.assertEqual(1, result["exit_code"])
        self.assertEqual(1, result["first_error"]["line"])
        self.assertIn("C2440", result["first_error"]["text"])

    def test_error_invalidates_success_marker(self):
        result = self.analyze_text("CMake Error: generation failed\n=== Build successful ===\n")
        self.assertEqual("failed", result["status"])
        self.assertEqual(1, result["exit_code"])

    def test_missing_success_marker_is_indeterminate(self):
        result = self.analyze_text("compilation still running\n")
        self.assertEqual("indeterminate", result["status"])
        self.assertEqual(2, result["exit_code"])

    def test_utf16_transcript(self):
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "build.log"
            log.write_text("=== Build successful ===\n", encoding="utf-16")
            result = MODULE.analyze(log, [])
        self.assertEqual("successful", result["status"])


if __name__ == "__main__":
    unittest.main()
