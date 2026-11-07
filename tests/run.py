#!/usr/bin/env python3
"""Run each bundled unittest directory in isolation, without external fixtures."""
import os
from pathlib import Path
import subprocess
import sys


def main():
    root = Path(__file__).resolve().parents[1]
    suites = sorted({p.parent for p in root.rglob('test_*.py')})
    if not suites:
        raise SystemExit('No tests found')
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONUTF8='1')
    # Tests must resolve helpers from this checkout, not an absent or stale caller root.
    env['PUBLIC_TOOLKIT_ROOT'] = str(root)
    # The public gate must not silently borrow private/user-installed fixtures.
    for name in ('PYTHONPATH', 'C64_RND_PROJECT', 'C64_RND_RUN_DIR',
                 'C64_RND_SHELL_DIR', 'C64_ROM_DIR'):
        env.pop(name, None)
    for suite in suites:
        print(f'\n== {suite.relative_to(root)} ==', flush=True)
        subprocess.run([sys.executable, '-X', 'utf8', '-m', 'unittest', 'discover',
                        '-s', str(suite), '-q'], cwd=root, env=env, check=True)
    print(f'\nPassed {len(suites)} test suites.')


if __name__ == '__main__':
    main()
