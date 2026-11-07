"""Reject command excerpts consistently, and report damaged log encodings."""
import contextlib
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "analyze_build_log.py"
SPEC = importlib.util.spec_from_file_location("wrapper_analyzer", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
SUCCESS = "=== Build successful ===\n"


class WrapperAndEncodingControls(unittest.TestCase):
    def analyze(self, data):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "build.log"
            path.write_bytes(data)
            return MODULE.analyze(path, [])

    def test_echo_rejection_covers_wrappers_and_powershell_excerpts(self):
        for prefix in ("", " ", "\t", "12>", " 12> "):
            for excerpt in ("", "+ "):
                for command in ("echo", "Write-Host", "Write-Output"):
                    for payload in ("build failed", "build-windows.ps1 : Native build failed",
                                    "a.cpp(1): error C2440: example",
                                    "a.cpp(1): warning C4996: example"):
                        line = prefix + excerpt + command + " " + payload
                        with self.subTest(line=line):
                            self.assertFalse(MODULE.is_error(line))
                            self.assertIsNone(MODULE.DIAGNOSTIC.match(line))
                            result = self.analyze((line + "\n" + SUCCESS).encode())
                            self.assertEqual((0, 0, {}), (result["exit_code"], result["error_count"], result["warning_counts"]))

    def test_project_prefix_preserves_real_wrapper_errors_and_raw_evidence(self):
        wrappers = ("build failed", "Native build failed",
                    "build-windows.ps1 : Native build failed", "Write-Error : Native build failed",
                    "+ CategoryInfo : NotSpecified: (:) [Write-Error], WriteErrorException",
                    "System.Management.Automation.RuntimeException: Native build failed with exit 1",
                    "CMake Error at CMakeLists.txt:5 (message): broken")
        for wrapper in wrappers:
            for prefix in ("", "12>", " 12> "):
                line = prefix + wrapper
                with self.subTest(line=line):
                    result = self.analyze((line + "\n" + SUCCESS).encode())
                    self.assertEqual(("failed", 1, 1), (result["status"], result["exit_code"], result["error_count"]))
                    self.assertEqual({"line": 1, "text": line.strip()}, result["first_error"])

    def test_category_records_are_not_blanket_ignored(self):
        genuine = "+ CategoryInfo : NotSpecified: (:) [Write-Error], WriteErrorException"
        self.assertTrue(MODULE.is_error(genuine))
        for prefix in ("+ ", "echo ", "+ Write-Host ", "note: "):
            self.assertFalse(MODULE.is_error(prefix + genuine))

    def damaged(self, text):
        return (text.encode() + b"\xff\n", b"\xef\xbb\xbf" + text.encode() + b"\xff\n",
                b"\xff\xfe" + text.encode("utf-16-le") + b"x",
                b"\xfe\xff" + text.encode("utf-16-be") + b"x")

    def test_damaged_encoding_retains_prior_diagnostics(self):
        for data in self.damaged("a.cpp(1): error : broken\n" + SUCCESS):
            with self.subTest(data=data):
                result = self.analyze(data)
                self.assertEqual(("failed", 1, 1), (result["status"], result["exit_code"], result["error_count"]))
                self.assertEqual(1, result["first_error"]["line"])
                self.assertTrue(result["decoding_error"])

    def test_damaged_encoding_cannot_certify_success(self):
        for data in self.damaged(SUCCESS):
            with self.subTest(data=data):
                result = self.analyze(data)
                self.assertEqual(("indeterminate", 2, 0), (result["status"], result["exit_code"], result["error_count"]))
                self.assertTrue(result["success_marker"])
                self.assertTrue(result["decoding_error"])
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    MODULE.print_text(result)
                self.assertIn("transcript decoding error:", output.getvalue())

    def test_valid_replacement_character_is_not_corruption(self):
        result = self.analyze(("literal U+FFFD: \ufffd\n" + SUCCESS).encode())
        self.assertEqual("successful", result["status"])
        self.assertNotIn("decoding_error", result)

    def test_valid_bom_encodings_keep_unicode_and_success(self):
        text = "工程\\café.cpp(7,2): warning : unused résumé 😀 [-Wunused-variable]\n" + SUCCESS
        for bom, encoding in ((b"", "utf-8"), (b"\xef\xbb\xbf", "utf-8"),
                              (b"\xff\xfe", "utf-16-le"), (b"\xfe\xff", "utf-16-be")):
            with self.subTest(encoding=encoding, bom=bom):
                result = self.analyze(bom + text.encode(encoding))
                self.assertEqual("successful", result["status"])
                self.assertEqual({"-Wunused-variable": 1}, result["warning_counts"])
                self.assertNotIn("decoding_error", result)


if __name__ == "__main__":
    unittest.main()
