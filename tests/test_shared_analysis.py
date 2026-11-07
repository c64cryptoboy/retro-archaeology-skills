"""Synthetic contract and relocated CLI smoke tests for the shared helpers."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

TOOLS = Path(__file__).resolve().parents[1] / 'shared/6502'
sys.path.insert(0, str(TOOLS))
import cfg6502
from dis6502 import ops


class SharedAnalysisTests(unittest.TestCase):
    def test_official_opcode_table(self):
        self.assertEqual(len(ops), 151)
        self.assertEqual(ops[0x20], ('JSR', 'abs', 3))

    def test_branch_edges(self):
        graph = cfg6502.analyze(bytes.fromhex('d0 01 ea 60'), 0x1000, [0x1000], 10)
        self.assertEqual({i['pc'] for i in graph['instructions']}, {0x1000, 0x1002, 0x1003})
        self.assertEqual({e['kind'] for e in graph['edges']}, {'branch', 'fallthrough'})

    def test_unknown_and_truncated_paths_stop(self):
        for data in (b'\x02', b'\x20\x00'):
            graph = cfg6502.analyze(data, 0x1000, [0x1000], 10)
            self.assertEqual(graph['stops'][0]['reason'], 'invalid_or_truncated_opcode')
            self.assertEqual(len(graph['instructions']), 1)

    def test_instruction_bound(self):
        graph = cfg6502.analyze(b'\xea' * 10, 0x1000, [0x1000], 3)
        self.assertTrue(graph['limitReached'])
        self.assertEqual(len(graph['instructions']), 3)

    def test_indirect_jump_remains_unresolved(self):
        graph = cfg6502.analyze(bytes.fromhex('6c 00 20'), 0x1000, [0x1000], 10)
        self.assertEqual(graph['stops'][0]['reason'], 'unresolved_indirect_jump')

    def test_cli_help_from_unrelated_directory(self):
        with tempfile.TemporaryDirectory() as cwd:
            for path in TOOLS.glob('*.py'):
                if path.name in {'dis6502.py', 'analysis6502.py'}:
                    continue
                proc = subprocess.run([sys.executable, str(path), '--help'], cwd=cwd,
                                      capture_output=True, text=True)
                self.assertEqual(proc.returncode, 0, (path.name, proc.stderr))

    def test_formatter_and_trace_cli(self):
        with tempfile.TemporaryDirectory() as name:
            cwd = Path(name)
            (cwd / 'small.prg').write_bytes(bytes.fromhex('00 10 a9 01 60'))
            result = subprocess.run([sys.executable, str(TOOLS/'dis6502.py'), 'small.prg',
                                     '0x1000', '2'], cwd=cwd, capture_output=True, text=True, check=True)
            self.assertIn('LDA', result.stdout)
            self.assertIn('RTS', result.stdout)
            (cwd / 'trace.jsonl').write_text('{"pc":4096}\n{"pc":4098}\n')
            result = subprocess.run([sys.executable, str(TOOLS/'trace6502.py'), 'trace.jsonl'],
                                    cwd=cwd, capture_output=True, text=True, check=True)
            self.assertEqual(json.loads(result.stdout)['executedPcs'], [4096, 4098])


if __name__ == '__main__':
    unittest.main()
