#!/usr/bin/env python3
"""Dependency-boundary tests for the independently finishable capability."""

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / 'tools'
sys.path.insert(0, str(TOOLS))

import cpu6502  # noqa: E402
import dataflow6502  # noqa: E402
import equivalence  # noqa: E402
import isa6502  # noqa: E402
import routine_runner  # noqa: E402


class ReductionDependencyBoundaryTests(unittest.TestCase):
    def test_neutral_runtime_modules_are_owned_by_reduction(self):
        for module in (cpu6502, dataflow6502, equivalence, isa6502,
                       routine_runner):
            with self.subTest(module=module.__name__):
                expected = (ROOT.parents[1] / 'shared/6502'
                            if module in (cpu6502, isa6502) else TOOLS)
                self.assertEqual(Path(module.__file__).resolve(),
                                 (expected / Path(module.__file__).name).resolve())

    def test_runtime_and_field_scripts_have_no_metamorphic_import_path(self):
        paths = tuple(TOOLS.glob('*.py')) + tuple(
            (ROOT / 'field_tests').glob('*/*.py')
        )
        forbidden = (
            "from metamorphic_rewriter import",
            "import metamorphic_rewriter",
            "/obfuscation/tools",
            "'obfuscation' / 'tools'",
            '"obfuscation" / "tools"',
            "'dead_test' / 'metamorphic'",
            '"dead_test" / "metamorphic"',
        )
        for path in paths:
            text = path.read_text()
            for marker in forbidden:
                with self.subTest(path=str(path), marker=marker):
                    self.assertNotIn(marker, text)


if __name__ == '__main__':
    unittest.main()
