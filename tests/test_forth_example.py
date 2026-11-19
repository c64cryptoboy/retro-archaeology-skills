"""Run the Forth skill's portable teaching example in the repository gate."""
from pathlib import Path
import subprocess
import sys
import unittest


class ForthExampleTests(unittest.TestCase):
    def test_standalone_contract(self):
        example = (Path(__file__).resolve().parents[1] / 'skills' /
                   '6502-forth-reversing' / 'check_example.py')
        subprocess.run([sys.executable, '-I', '-B', str(example)], check=True)
