"""Paired CLI and handoff controls for one fixed-address inline argument."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

TOOLS = Path(__file__).resolve().parents[1] / 'shared/6502'
# JSR $2006; .byte 0; INX; RTS.  The site-specific callee reads $2003,
# then increments the stacked return low byte ($02, so no carry) before RTS.
PRG = bytes.fromhex('00 20  20 06 20  00 e8 60  ad 03 20 ba fe 01 01 60')
SHA = hashlib.sha256(PRG).hexdigest()
SITE = 'Caller listing: $2003 is the literal after JSR $2006.'
CALLEE = 'Callee listing: reads $2003 and increments the stacked return from $2002 to $2003.'


class InlineJsrContractTests(unittest.TestCase):
    def setUp(self):
        work = tempfile.TemporaryDirectory()
        self.addCleanup(work.cleanup)
        self.cwd = Path(work.name)
        (self.cwd / 'demo.prg').write_bytes(PRG)

    def run_tool(self, tool, *args, check=True):
        return subprocess.run([sys.executable, '-B', str(TOOLS / tool), *args], cwd=self.cwd,
                              text=True, capture_output=True, check=check)

    def graph(self, *args):
        return json.loads(self.run_tool('cfg6502.py', 'demo.prg', '--json', *args).stdout)

    def contract(self, sha=SHA, callee='0x2006'):
        return ['--inline-jsr', sha, '0x2000', callee, SITE, CALLEE]

    def report(self, graph):
        (self.cwd / 'cfg.json').write_text(json.dumps(graph))
        self.run_tool('disassembly-report.py', 'cfg.json', '--output', 'report.md')
        return (self.cwd / 'report.md').read_text()

    def test_paired_call_site_and_handoff(self):
        for annotated in (False, True):
            with self.subTest(annotated=annotated):
                graph = self.graph(*(self.contract() if annotated else []))
                ops = {i['pc']: i['mnemonic'] for i in graph['instructions']}
                edges = {(e['kind'], e['to']) for e in graph['edges'] if e['from'] == 0x2000}
                report = self.report(graph)
                if annotated:
                    self.assertEqual(edges, {('call', 0x2006), ('analyst_supplied_continuation', 0x2004)})
                    self.assertNotIn(0x2003, ops)
                    self.assertEqual((ops[0x2004], ops[0x2005]), ('INX', 'RTS'))
                    self.assertFalse(graph['inlineJsr']['codeConflict'])
                    static, supplied = report.split('## Analyst-supplied inline JSR')
                    self.assertIn('`$2000` → `$2006`', static)
                    self.assertNotIn('$2004', static)
                    for detail in (SHA, SITE, CALLEE, 'inline argument $2003 = $00',
                                   'analyst-supplied continuation $2004 (not observed execution)'):
                        self.assertIn(detail, supplied)
                else:
                    self.assertEqual(edges, {('call', 0x2006), ('fallthrough', 0x2003)})
                    self.assertEqual(ops[0x2003], 'BRK')
                    self.assertTrue({0x2004, 0x2005}.isdisjoint(ops))
                    self.assertNotIn('inlineJsr', graph)
                    self.assertNotIn('Analyst-supplied inline JSR', report)

    def test_independent_entry_retains_both_interpretations(self):
        for first, second in [('0x2000', '0x2003'), ('0x2003', '0x2000')]:
            graph = self.graph('--entry', first, '--entry', second, *self.contract())
            self.assertTrue(graph['inlineJsr']['codeConflict'])
            self.assertIn((0x2003, 'BRK'), [(i['pc'], i['mnemonic']) for i in graph['instructions']])
            self.assertIn((0x2000, 0x2004), [(e['from'], e['to']) for e in graph['edges']])
            self.assertIn('Conflict: independent code evidence', self.report(graph))

    def test_reject_stale_hash_and_wrong_target(self):
        for args, message in [(self.contract(sha=hashlib.sha256(PRG[2:]).hexdigest()), 'SHA-256'),
                              (self.contract(callee='0x2005'), 'encoded target')]:
            with self.subTest(message=message):
                result = self.run_tool('cfg6502.py', 'demo.prg', '--json', *args, check=False)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, '')
                self.assertIn('inline JSR conflict', result.stderr)
                self.assertIn(message, result.stderr)
