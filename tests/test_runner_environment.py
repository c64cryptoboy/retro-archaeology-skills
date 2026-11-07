"""Exercise the real runner with isolated miniature suites and caller environments."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

RUNNER = Path(__file__).resolve().with_name('run.py')
CLEARED = ('PYTHONPATH', 'C64_ROM_DIR', 'C64_RND_PROJECT',
           'C64_RND_RUN_DIR', 'C64_RND_SHELL_DIR')


class RunnerEnvironmentTests(unittest.TestCase):
    def invoke(self, supplied_root, *, reject=False):
        with tempfile.TemporaryDirectory(prefix='toolkit space ') as directory:
            root = Path(directory)
            tests = root / 'tests'
            tests.mkdir()
            shutil.copyfile(RUNNER, tests / 'run.py')
            probe = '''import os
from pathlib import Path
import unittest

class Probe(unittest.TestCase):
    def test_environment(self):
        self.assertEqual(Path(os.environ['PUBLIC_TOOLKIT_ROOT']), Path(__file__).resolve().parents[1])
        self.assertEqual(os.environ['PYTHONDONTWRITEBYTECODE'], '1')
        self.assertEqual(os.environ['PYTHONUTF8'], '1')
        for name in CLEARED:
            self.assertNotIn(name, os.environ)
        if REJECT:
            self.fail('intentional child-suite rejection')
'''
            (tests / 'test_probe.py').write_text('CLEARED = ' + repr(CLEARED) + '\nREJECT = ' + repr(reject) + '\n' + probe)
            env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
            for name in CLEARED:
                env[name] = str(root / 'unrelated')
            if supplied_root is None:
                env.pop('PUBLIC_TOOLKIT_ROOT', None)
            else:
                env['PUBLIC_TOOLKIT_ROOT'] = str(root / supplied_root)
            return subprocess.run([sys.executable, '-B', str(tests / 'run.py')],
                                  cwd=root, env=env, text=True, capture_output=True, timeout=15)

    def test_unset_caller_root_uses_own_checkout(self):
        result = self.invoke(None)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('Passed 1 test suites.', result.stdout)

    def test_stale_caller_root_is_overridden(self):
        result = self.invoke('wrong toolkit')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('Passed 1 test suites.', result.stdout)

    def test_child_failure_is_not_hidden(self):
        result = self.invoke(None, reject=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('intentional child-suite rejection', result.stderr)
        self.assertNotIn('Passed 1 test suites.', result.stdout)


if __name__ == '__main__':
    unittest.main()
