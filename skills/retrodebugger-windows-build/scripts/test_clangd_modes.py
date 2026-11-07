"""Additive synthetic scope controls; never replace a failed full-check result."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import clangd_preflight as helper

OK = dict(exit_code=0, timed_out=False, launch_error=None)
PHASES = ('Building AST...', 'Indexing AST...', 'Building inlay hints',
          'Building semantic highlighting')
PREFIX = 'I[00:00:00.000] Compile command from CDB is: explicit\n'
STAGES = ''.join('I[00:00:00.000] ' + phase + '\n' for phase in PHASES)
CLEAN = PREFIX + STAGES + 'I[00:00:00.000] All checks completed, 0 errors\n'
FEATURE = ('E[00:00:00.000] tweak: ExtractFunction ==> FAIL: Cannot extract '
           'break/continue without corresponding loop/switch statement.\n')


class ModeTests(unittest.TestCase):
    def test_explicit_scopes_and_no_native_acceptance(self):
        for mode, omitted in [('full', []), ('translation-unit', ['token-level editor features'])]:
            result = helper.classify_mode(CLEAN, OK, mode)
            self.assertEqual(result['status'], 'clean')
            self.assertEqual(result['check_mode'], mode)
            self.assertEqual(result['omitted_checks'], omitted)
            self.assertFalse(result['native_acceptance'])

    def test_missing_phases_and_unexpected_token_testing_refused(self):
        for phase in PHASES:
            result = helper.classify_mode(CLEAN.replace(phase, 'missing'), OK, 'translation-unit')
            self.assertEqual(result['status'], 'unavailable')
            self.assertIn('translation_unit_phases_not_confirmed', result['reasons'])
        result = helper.classify_mode(CLEAN + 'Testing features at each token\n', OK, 'translation-unit')
        self.assertEqual(result['status'], 'unavailable')
        self.assertIn('unexpected_token_feature_testing', result['reasons'])

    def test_default_classifier_results_preserved(self):
        for log, process in [(CLEAN, OK), ('', OK),
                             (PREFIX + FEATURE + 'I[00:00:00.000] All checks completed, 1 errors\n',
                              {**OK, 'exit_code': 3})]:
            original = helper.classify(log, process)
            actual = helper.classify_mode(log, process)
            self.assertEqual({key: actual[key] for key in original}, original)

    def test_mode_never_suppresses_feature_error_or_context_failure(self):
        cases = [('tweak: ExtractFunction ==> FAIL: refused', 'non_diagnostic_tool_errors'),
                 ('[pp_file_not_found] Line 1: missing header', 'context_or_parse_blocker')]
        for error, reason in cases:
            log = PREFIX + STAGES + f'E[00:00:00.000] {error}\n' + 'I[00:00:00.000] All checks completed, 1 errors\n'
            result = helper.classify_mode(log, {**OK, 'exit_code': 3}, 'translation-unit')
            self.assertEqual(result['status'], 'unavailable')
            self.assertIn(reason, result['reasons'])
            self.assertIn(error, '\n'.join(result['tool_error_lines']))

    def test_real_source_error_stays_findings(self):
        log = (PREFIX + STAGES + 'E[00:00:00.000] [init_conversion_failed] Line 4: wrong type\n'
               'I[00:00:00.000] All checks completed, 1 errors\n')
        result = helper.classify_mode(log, {**OK, 'exit_code': 3}, 'translation-unit')
        self.assertEqual(result['status'], 'findings')
        self.assertEqual(len(result['diagnostics']), 1)

    def test_unsupported_option_timeout_and_incomplete_logs_fail_closed(self):
        for log, process in [('Unknown command line argument --check-locations', {**OK, 'exit_code': 1}),
                             (CLEAN, {**OK, 'timed_out': True}),
                             (PREFIX + STAGES, OK),
                             (CLEAN + 'Generic fallback command\n', OK)]:
            self.assertEqual(helper.classify_mode(log, process, 'translation-unit')['status'], 'unavailable')

    def test_invalid_mode_refused_before_output(self):
        with self.assertRaises(ValueError):
            helper.run('unused', 'unused', 'unused', mode='diagnostics-only')

    def test_flag_is_opt_in_and_cli_discloses_scope(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'x.cpp'
            source.write_text('int x;\n')
            (root / 'compile_commands.json').write_text(json.dumps([dict(
                directory=directory, file=str(source), arguments=['clang++', str(source)])]))
            stub = root / 'stub-clangd'
            # Synthetic output/argument recorder, not a compiler.
            stub.write_text('#!' + sys.executable + '\nimport sys\n' +
                            'print(' + repr(CLEAN) + ')\n' +
                            'print("ARGV=" + repr(sys.argv[1:]))\n')
            stub.chmod(0o755)
            for mode in ('full', 'translation-unit'):
                output = root / mode
                command = [sys.executable, '-B', str(Path(helper.__file__).resolve()),
                           '--source', str(source), '--database', directory, '--output', str(output),
                           '--clangd', str(stub)]
                if mode != 'full':
                    command += ['--mode', mode]
                proc = subprocess.run(command, capture_output=True, text=True, timeout=10)
                self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
                receipt = json.loads(proc.stdout)
                self.assertEqual(receipt['check_mode'], mode)
                self.assertEqual(receipt['omitted_checks'], [] if mode == 'full' else ['token-level editor features'])
                self.assertFalse(receipt['native_acceptance'])
                result = json.loads((output / 'result.json').read_text())
                self.assertEqual('--check-locations=false' in result['process']['argv'], mode != 'full')
                self.assertEqual(result['before'], result['after'])

    def test_no_automatic_fallback_or_second_process(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'x.cpp'
            source.write_text('int x;\n')
            (root / 'compile_commands.json').write_text(json.dumps([dict(
                directory=directory, file=str(source), arguments=['clang++', str(source)])]))
            def failed_capture(argv, cwd, env, log, timeout):
                Path(log).write_text(PREFIX + FEATURE + 'I[00:00:00.000] All checks completed, 1 errors\n')
                return {**OK, 'exit_code': 3, 'argv': argv}
            with patch.object(helper, 'capture', side_effect=failed_capture) as capture:
                result = helper.run(source, root, root / 'out', clangd=sys.executable)
            self.assertEqual(capture.call_count, 1)
            self.assertEqual(result['status'], 'unavailable')
            self.assertEqual(result['check_mode'], 'full')
            self.assertNotIn('--check-locations=false', result['process']['argv'])


if __name__ == '__main__':
    unittest.main()
