#!/usr/bin/env python3
"""Authored, portable build-log fixtures; no native logs or target execution."""

import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(os.environ.get("BUILDLOG_ANALYZER", Path(__file__).resolve().parents[1] / "analyze_build_log.py"))
SPEC = importlib.util.spec_from_file_location("analyzer_under_test", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)
KEYS = {
    "log", "status", "exit_code", "success_marker", "error_count", "first_error",
    "errors", "warning_counts", "dependencies", "artifacts", "missing_artifacts",
}


class BuildLogCandidateTests(unittest.TestCase):
    def analyze_text(self, text, encoding="utf-8"):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "build.log"
            path.write_bytes(text.encode(encoding))
            return MODULE.analyze(path, [])

    def test_msvc_compiler_and_linker_diagnostics(self):
        result = self.analyze_text(
            "1>source.cpp(10,2): warning C4996: deprecated\n"
            "SDL2.lib(foo.obj) : warning LNK4099: PDB not found\n"
            "source.cpp(12): error C2440: cannot convert\n"
            "LINK : fatal error LNK1104: cannot open file\n"
        )
        self.assertEqual({"C4996": 1, "LNK4099": 1}, result["warning_counts"])
        self.assertEqual("failed", result["status"])
        self.assertEqual(2, result["error_count"])
        self.assertEqual(3, result["first_error"]["line"])
        self.assertEqual(KEYS, set(result))

    def test_clang_msbuild_whitespace_colon_error_precedes_wrapper(self):
        result = self.analyze_text(
            "..\\src\\NesWrapper.cpp(1737,54): error : no member named 'cpu'\n"
            "build-windows.ps1 : RetroDebugger build failed\n"
            "=== Build successful ===\n"
        )
        self.assertEqual("failed", result["status"])
        self.assertEqual(1, result["exit_code"])
        self.assertTrue(result["success_marker"])
        self.assertEqual(1, result["first_error"]["line"])
        self.assertIn("NesWrapper.cpp", result["first_error"]["text"])
        self.assertEqual(2, result["error_count"])

    def test_clang_warning_options_and_uncoded_bucket(self):
        result = self.analyze_text(
            "source.cpp(1,2): warning : unused type [-Wunused-local-typedef] [app.vcxproj]\n"
            "2>source.cpp:2:3: warning: unused type [-Wunused-local-typedef]\n"
            "clang-cl: warning : unknown argument\n"
            "source.h(2): warning: no option here\n"
            "LINK : warning LNK4099: symbols missing\n"
            "cl : warning D9002: ignoring option\n"
            "=== Build successful ===\n"
        )
        self.assertEqual({"-Wunused-local-typedef": 2, "uncoded": 2,
                          "LNK4099": 1, "D9002": 1}, result["warning_counts"])
        self.assertEqual("successful", result["status"])

    def test_msbuild_error_and_warning_codes(self):
        result = self.analyze_text(
            "MSBUILD : warning MSB3270: architecture mismatch\n"
            "project.vcxproj(20,5): error MSB3073: command exited with code 1\n"
        )
        self.assertEqual({"MSB3270": 1}, result["warning_counts"])
        self.assertEqual(2, result["first_error"]["line"])

    def test_earliest_error_in_full_log_order(self):
        result = self.analyze_text(
            "src/first.cpp:4:2: error: first failure\n"
            "source.cpp(8,1): fatal error : later failure\n"
            "CMake Error at CMakeLists.txt:40 (message):\n"
            "RetroDebugger build failed\n"
        )
        self.assertEqual(4, result["error_count"])
        self.assertEqual({"line": 1, "text": "src/first.cpp:4:2: error: first failure"},
                         result["first_error"])

    def test_quoted_commands_narrative_and_caret_source_are_not_diagnostics(self):
        result = self.analyze_text(
            'The guide mentions fatal error and error C2440 as examples.\n'
            'A previous build failed, but this is a narrative note.\n'
            'Narrative: warning: this is not compiler output\n'
            'echo "source.cpp(10): error C2440: example"\n'
            'echo source.cpp(10): error C2440: example\n'
            'Write-Host source.cpp(10): warning C4996: example\n'
            'Example: source.cpp(10): error : example\n'
            'PS C:\\work> Write-Error "example"\n'
            '+ Write-Error "fatal error"\n'
            '  42 | printf("error C2440: fatal error");\n'
            '     | ^ warning C4996: example\n'
            '  43 | // source.cpp(10): warning : unused [-Wunused-variable]\n'
        )
        self.assertEqual("indeterminate", result["status"])
        self.assertEqual([], result["errors"])
        self.assertEqual({}, result["warning_counts"])

    def test_echoed_success_is_not_acceptance(self):
        for text in ('Write-Host "=== Build successful ==="\n',
                     'echo === Build successful ===\n',
                     ' 42 | puts("=== Build successful ===");\n',
                     'Note: === Build successful === appears only in documentation\n'):
            with self.subTest(text=text):
                result = self.analyze_text(text)
                self.assertEqual("indeterminate", result["status"])
                self.assertFalse(result["success_marker"])

    def test_exact_success_line_with_whitespace(self):
        result = self.analyze_text("  === Build successful ===  \r\n")
        self.assertEqual("successful", result["status"])
        self.assertEqual(0, result["exit_code"])

    def test_error_invalidates_success(self):
        for error in ("source.cpp(3): error : missing declaration",
                      "clang-cl: error: unknown option",
                      "fatal error: missing header",
                      "CMake Error: generation failed",
                      "Write-Error : RetroDebugger build failed"):
            with self.subTest(error=error):
                result = self.analyze_text(error + "\n=== Build successful ===\n")
                self.assertEqual("failed", result["status"])
                self.assertEqual(1, result["exit_code"])
                self.assertEqual(1, result["first_error"]["line"])

    def test_bom_and_utf8_diagnostic_equivalence(self):
        text = ("source.cpp(1): warning : café [-Wunused-variable]\n"
                "source.cpp(2): error : missing declaration\n"
                "=== Build successful ===\n")
        for encoding in ("utf-8", "utf-8-sig", "utf-16", "utf-16-be", "utf-16-le"):
            with self.subTest(encoding=encoding):
                # utf-16-be is tested with its explicit BOM, as supported before this repair.
                if encoding == "utf-16-be":
                    with tempfile.TemporaryDirectory() as directory:
                        path = Path(directory) / "build.log"
                        path.write_bytes(b"\xfe\xff" + text.encode(encoding))
                        result = MODULE.analyze(path, [])
                else:
                    result = self.analyze_text(text, encoding)
                self.assertEqual("failed", result["status"])
                self.assertEqual(2, result["first_error"]["line"])
                self.assertEqual({"-Wunused-variable": 1}, result["warning_counts"])

    def test_reader_preserves_non_ascii_text(self):
        text = "café / résumé\n"
        for encoding in ("utf-8", "utf-8-sig", "utf-16", "utf-16-le"):
            with self.subTest(encoding=encoding):
                with tempfile.TemporaryDirectory() as directory:
                    path = Path(directory) / "build.log"
                    path.write_bytes(text.encode(encoding))
                    self.assertEqual(text, MODULE.read_transcript(path))

    def test_utf16le_without_bom_is_not_utf8_with_embedded_nuls(self):
        result = self.analyze_text("=== Build successful ===\n", "utf-16-le")
        self.assertEqual("successful", result["status"])
        self.assertEqual(0, result["exit_code"])

    def test_utf8_with_sparse_nul_does_not_become_utf16(self):
        result = self.analyze_text("native stdout\x00 remains UTF-8\n=== Build successful ===\n")
        self.assertEqual("successful", result["status"])

    def test_invalid_utf8_replacement_retains_usable_diagnostic(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "build.log"
            path.write_bytes(b"source.cpp(1): error : bad byte \xff\n")
            result = MODULE.analyze(path, [])
        self.assertEqual("failed", result["status"])
        self.assertIn("\ufffd", result["first_error"]["text"])

    def test_indeterminate_empty_and_warning_only_logs(self):
        for text in ("", "compilation still running\n", "source.cpp(1): warning C4996: deprecated\n"):
            with self.subTest(text=text):
                result = self.analyze_text(text)
                self.assertEqual("indeterminate", result["status"])
                self.assertEqual(2, result["exit_code"])
                self.assertIsNone(result["first_error"])

    def test_artifact_hash_and_missing_artifact_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            log = root / "build.log"
            log.write_text("=== Build successful ===\n", encoding="utf-8")
            artifact = root / "present.pdb"
            artifact.write_bytes(b"authored artifact, not a PDB")
            missing = root / "missing.exe"
            result = MODULE.analyze(log, [artifact, missing])
            self.assertEqual("failed", result["status"])
            self.assertEqual(1, result["exit_code"])
            self.assertEqual([str(missing)], result["missing_artifacts"])
            self.assertEqual([{"path": str(artifact), "size": artifact.stat().st_size,
                               "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest()}], result["artifacts"])
            self.assertIsNone(result["first_error"])
            log.write_text("partial log\n", encoding="utf-8")
            self.assertEqual(2, MODULE.analyze(log, [missing])["exit_code"])

    def test_dependency_deduplication_remains_unchanged(self):
        result = self.analyze_text(
            "=== Building uSockets (x64 Debug MSVC) ===\n"
            "=== Building uSockets (x64 Debug MSVC) ===\n"
            "Building mbedTLS libs (Release)\n=== Build successful ===\n"
        )
        self.assertEqual([{"name": "uSockets", "configuration": "Debug"},
                          {"name": "mbedTLS", "configuration": "Release"}], result["dependencies"])

    def test_print_text_includes_uncoded_and_clang_warning_counts(self):
        result = self.analyze_text("source.cpp(1): warning : ignored [-Wunknown-pragmas]\n"
                                   "warning : no option\n")
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            MODULE.print_text(result)
        self.assertIn("-Wunknown-pragmas=1", output.getvalue())
        self.assertIn("uncoded=1", output.getvalue())

    def test_cli_existing_options_and_exit_codes(self):
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifact = root / "candidate.pdb"
            artifact.write_bytes(b"fixture")
            log = root / "build.log"
            for text, expected in (("=== Build successful ===\n", 0),
                                   ("source.cpp(1): error : failure\n=== Build successful ===\n", 1),
                                   ("still compiling\n", 2)):
                with self.subTest(expected=expected):
                    log.write_text(text, encoding="utf-8")
                    completed = subprocess.run([sys.executable, str(SCRIPT), str(log),
                                                "--artifact", str(artifact), "--json"],
                                               capture_output=True, text=True, env=env, timeout=10)
                    self.assertEqual(expected, completed.returncode)
                    result = json.loads(completed.stdout)
                    self.assertEqual(KEYS, set(result))
                    self.assertEqual(expected, result["exit_code"])
            completed = subprocess.run([sys.executable, str(SCRIPT), str(root / "absent.log")],
                                       capture_output=True, text=True, env=env, timeout=10)
            self.assertEqual(2, completed.returncode)
            self.assertIn("log file not found", completed.stderr)


if __name__ == "__main__":
    unittest.main()
