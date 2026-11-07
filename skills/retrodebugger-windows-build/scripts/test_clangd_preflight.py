#!/usr/bin/env python3
"""Offline additive tests only; no C++ compilation or payload execution."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

from clangd_preflight import capture, classify, run

ROOT = Path(__file__).resolve().parent
OK = {'exit_code': 0, 'timed_out': False, 'launch_error': None}
PREFIX = 'I[00:00:00.000] Compile command from CDB is: explicit\n'
CLEAN = PREFIX + 'I[00:00:00.000] All checks completed, 0 errors\n'
BAD = PREFIX + ('E[00:00:00.000] [init_conversion_failed] Line 9: Cannot initialize a parameter\n'
                'I[00:00:00.000] All checks completed, 1 errors\n')


class PreflightTests(unittest.TestCase):
    def test_clean_completion(self):
        self.assertEqual(classify(CLEAN, OK)['status'], 'clean')

    def test_type_error(self):
        result = classify(BAD, {**OK, 'exit_code': 3})
        self.assertEqual(result['status'], 'findings')
        self.assertEqual(len(result['diagnostics']), 1)

    def test_missing_header_not_a_pass_or_source_finding(self):
        text = BAD.replace('init_conversion_failed', 'pp_file_not_found')
        self.assertEqual(classify(text, {**OK, 'exit_code': 3})['status'], 'unavailable')

    def test_empty_or_partial_not_clean(self):
        for text in ('', PREFIX, BAD.replace('All checks completed', 'Interrupted')):
            self.assertFalse(classify(text, OK)['coverage_available'])

    def test_fallback_not_clean(self):
        self.assertEqual(classify(CLEAN + 'Generic fallback command', OK)['status'], 'unavailable')

    def test_abnormal_exit_not_clean(self):
        self.assertEqual(classify(CLEAN, {**OK, 'exit_code': 7})['status'], 'unavailable')

    def test_tool_errors_not_clean(self):
        self.assertEqual(classify(CLEAN + 'E[00:00:00.000] IncludeCleaner: failure\n', OK)['status'], 'unavailable')

    def test_mismatched_count_not_clean(self):
        self.assertEqual(classify(BAD, OK)['status'], 'unavailable')

    def test_real_process_timeout_failure_and_launch_failure(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            base = Path(directory)
            timed = capture([sys.executable, '-B', '-c', 'print("started", flush=True)\nwhile True: pass'],
                            directory, dict(os.environ), base / 'timeout.log', 0.2)
            self.assertTrue(timed['timed_out'])
            self.assertEqual(timed['exit_code'], -9)
            self.assertIn('started', (base / 'timeout.log').read_text())
            failed = capture([sys.executable, '-B', '-c', 'print("failed"); raise SystemExit(7)'],
                             directory, dict(os.environ), base / 'failed.log', 2)
            self.assertEqual(failed['exit_code'], 7)
            missing = capture(['/nonexistent/clangd'], directory, dict(os.environ), base / 'missing.log', 2)
            self.assertIsNotNone(missing['launch_error'])
            for result in (timed, failed, missing):
                self.assertEqual(classify('', result)['status'], 'unavailable')

    def test_synthetic_feature_failure_with_and_without_type_diagnostic(self):
        # Public synthetic equivalents; original full-TU evidence tests remain
        # unchanged in the private effort.  No private source/log is required.
        feature = ('E[00:00:00.000] tweak: ExtractFunction ==> FAIL: '
                   'Cannot extract break/continue without corresponding loop/switch statement.\n')
        diagnostic = ('E[00:00:00.000] [init_conversion_failed] Line 36: '
                      'cannot initialize a parameter of type uint16_t\n')
        for expected in (0, 1):
            log = (PREFIX + feature + (diagnostic if expected else '') +
                   f'I[00:00:00.000] All checks completed, {expected + 1} errors\n')
            classified = classify(log, {**OK, 'exit_code': 3})
            self.assertEqual(classified['status'], 'unavailable')
            self.assertEqual(classified['reasons'], ['non_diagnostic_tool_errors'])
            self.assertEqual(len(classified['diagnostics']), expected)
            self.assertIn('ExtractFunction ==> FAIL', '\n'.join(classified['tool_error_lines']))

    def test_timeout_bounds(self):
        for value in (0, -1, 121, float('nan'), float('inf')):
            with self.assertRaises(ValueError):
                run('unused', 'unused', 'unused', timeout=value)

    def test_no_entry_or_duplicate_refused_before_launch(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            base = Path(directory)
            source = base / 'x.cpp'
            source.write_text('int x;\n')
            entry = dict(directory=directory, file=str(source), arguments=['/usr/bin/clang++', str(source)])
            for entries in ([], [entry, entry]):
                (base / 'compile_commands.json').write_text(json.dumps(entries))
                with self.assertRaises(ValueError):
                    run(source, base, base / 'never-created')
                self.assertFalse((base / 'never-created').exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
