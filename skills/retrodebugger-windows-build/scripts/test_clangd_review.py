"""Synthetic regressions for process cleanup and executable identity."""
import hashlib
import json
import os
from pathlib import Path
import signal
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

import clangd_preflight as helper


class ReviewGuards(unittest.TestCase):
    def test_interrupt_and_wait_error_kill_and_reap_child(self):
        for failure in (KeyboardInterrupt(), RuntimeError('synthetic wait failure')):
            proc = Mock(pid=12345)
            proc.wait.side_effect = [failure, -9]
            with tempfile.TemporaryDirectory() as directory:
                with patch.object(helper.subprocess, 'Popen', return_value=proc), patch.object(helper.os, 'killpg') as kill:
                    with self.assertRaises(type(failure)):
                        helper.capture(['unused'], directory, {}, Path(directory) / 'log', 1)
                    kill.assert_called_once_with(12345, signal.SIGKILL)
                    self.assertEqual(proc.wait.call_count, 2)

    def test_executable_identity_matches_launched_absolute_path(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'x.cpp'
            source.write_text('int x;\n')
            (root / 'compile_commands.json').write_text(json.dumps([dict(
                directory=directory, file=str(source), arguments=['clang++', str(source)])]))
            executable = root / 'synthetic-clangd'
            # A process/log stub, not a compiler or target.
            executable.write_text('#!' + sys.executable + '\n' +
                'print("I[00:00:00.000] Compile command from CDB is: explicit")\n' +
                'print("I[00:00:00.000] All checks completed, 0 errors")\n')
            executable.chmod(0o755)
            expected = str(executable.resolve())
            for name in (executable.name, os.path.relpath(executable, Path.cwd())):
                with self.subTest(name=name), patch.dict(os.environ, {'PATH': directory}):
                    result = helper.run(source, root, root / ('out-' + str(len(name))), clangd=name)
                    self.assertEqual(result['status'], 'clean')
                    self.assertEqual(result['process']['argv'][0], expected)
                    self.assertEqual(result['clangd_realpath'], expected)
                    self.assertEqual(result['clangd_sha256'], hashlib.sha256(executable.read_bytes()).hexdigest())


if __name__ == '__main__':
    unittest.main()
