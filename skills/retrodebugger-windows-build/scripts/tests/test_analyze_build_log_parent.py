"""Independent parent controls: whitespace must not bypass echo rejection."""
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(os.environ.get("BUILDLOG_ANALYZER", Path(__file__).resolve().parents[1] / "analyze_build_log.py"))
SPEC = importlib.util.spec_from_file_location("parent_analyzer", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ParentDiagnosticControls(unittest.TestCase):
    def test_indentation_and_project_prefix_cannot_bypass_echo_rejection(self):
        for prefix in ("", " ", "  ", "\t", "1>", "1> ", " 12>  "):
            for command in ("echo", "Write-Host", "Write-Output"):
                for severity in ("error C2440", "warning C4996"):
                    line = prefix + command + " source.cpp(10): " + severity + ": example"
                    with self.subTest(line=line):
                        self.assertIsNone(MODULE.DIAGNOSTIC.match(line))
                        self.assertFalse(MODULE.is_error(line))

    def test_powershell_failure_records_preserve_wrapper_diagnostics(self):
        records = (
            "    + CategoryInfo : NotSpecified: (:) [Write-Error], WriteErrorException",
            "System.Management.Automation.RuntimeException: Native build failed with exit 1",
        )
        for record in records:
            with self.subTest(record=record):
                self.assertTrue(MODULE.is_error(record))
                for prefix in ("echo ", "  Write-Host ", "note: ", "+ "):
                    self.assertFalse(MODULE.is_error(prefix + record))
        self.assertFalse(MODULE.is_error("+ CategoryInfo : example mentions Write-Error"))
        self.assertFalse(MODULE.is_error("System.Management.Automation.RuntimeException: example succeeded"))

    def test_independent_oracle_warning_option_and_note_controls(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "build.log"
            path.write_text(
                "a.cpp(1,2): note: expected error : example\n"
                "a.cpp(1,2): note: prior warning : unused [-Wunused-variable]\n"
                "status: error : none\n"
                "Literal [-Wformat] mentioned here\n"
                "a.cpp(2,3): warning : text mentions error: token [-W#pragma-messages]\n"
                "a.cpp(2,3): warning : text mentions error: token [-W#pragma-messages]\n"
                "=== Build successful ===\n", encoding="utf-8")
            result = MODULE.analyze(path, [])
            self.assertEqual(0, result["exit_code"])
            self.assertEqual([], result["errors"])
            self.assertEqual({"-W#pragma-messages": 2}, result["warning_counts"])


if __name__ == "__main__":
    unittest.main()
