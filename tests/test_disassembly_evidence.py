"""Offline CLI regressions for instruction bytes, C64 mapping, and NMOS indirect JMP."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

TOOLS = Path(__file__).resolve().parents[1] / 'shared/6502'


class DisassemblyEvidenceTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.cwd = Path(tmp.name)

    def cli(self, script, *args):
        output = subprocess.check_output([sys.executable, '-B', str(TOOLS / script), *args],
                                         cwd=self.cwd, text=True)
        return json.loads(output)

    def test_diff_cfg_spans_and_trace_points(self):
        # LDA #$10; RTS; one data byte.  Change the opcode, operand, and data.
        (self.cwd / 'before.prg').write_bytes(bytes.fromhex('00 20 a9 10 60 00'))
        (self.cwd / 'after.prg').write_bytes(bytes.fromhex('00 20 a2 11 60 01'))
        graph = self.cli('cfg6502.py', 'before.prg', '--entry', '0x2000', '--json')
        (self.cwd / 'cfg.json').write_text(json.dumps(graph))
        (self.cwd / 'trace.json').write_text(json.dumps({'executedPcs': [0x2000]}))
        for option, source, expected in [('--cfg-json', 'cfg.json', [0x2000, 0x2001]),
                                         ('--executed-json', 'trace.json', [0x2000])]:
            with self.subTest(source=source):
                diff = self.cli('code-write-diff.py', 'before.prg', 'after.prg', option, source)
                self.assertEqual([c['address'] for c in diff['changes']], [0x2000, 0x2001, 0x2003])
                self.assertEqual([c['address'] for c in diff['changedExecutedOrCode']], expected)

    def test_invalid_and_truncated_cfg_entries_do_not_establish_code(self):
        # Invalid opcode at $2000; truncated JSR at the separate entry $2001.
        (self.cwd / 'before.prg').write_bytes(bytes.fromhex('00 20 02 20 aa'))
        (self.cwd / 'after.prg').write_bytes(bytes.fromhex('00 20 ea ea ea'))
        graph = self.cli('cfg6502.py', 'before.prg', '--entry', '0x2000', '--entry', '0x2001', '--json')
        (self.cwd / 'cfg.json').write_text(json.dumps(graph))
        diff = self.cli('code-write-diff.py', 'before.prg', 'after.prg', '--cfg-json', 'cfg.json')
        self.assertEqual(diff['changedExecutedOrCode'], [])

    def test_vic_report_requires_visible_io(self):
        ram = bytearray(65536)
        ram[0], ram[0xdd00], ram[0xd018] = 0x2f, 3, 0x14
        ram[0xd011], ram[0xd016] = 0x1b, 8
        visible = {'dd00': 3, 'd011': 0x1b, 'd016': 8, 'd018': 0x14,
                   'bank': 0, 'screenAddress': 0x0400, 'charsetAddress': 0x1000}
        for port, io_visible in [(0x37, True), (0x34, False)]:
            with self.subTest(port=port):
                ram[1] = port
                (self.cwd / 'snapshot.bin').write_bytes(ram)
                state = self.cli('c64-state-report.py', 'snapshot.bin')
                self.assertIs(state['cpuPort']['ioVisible'], io_visible)
                self.assertEqual(state['vic'], visible if io_visible else dict.fromkeys(visible))

    def test_nmos_indirect_jump_writer_addresses(self):
        # Absolute stores to $12FF, $1200, and $1300, then JMP ($12xx).
        prefix = bytes.fromhex('00 20 8d ff 12 8d 00 12 8d 00 13 6c')
        for lo, expected in [(0xff, [(0x2000, 'low'), (0x2003, 'high')]),
                             (0xfe, [(0x2000, 'high')])]:
            with self.subTest(pointer_low=lo):
                (self.cwd / 'jump.prg').write_bytes(prefix + bytes([lo, 0x12]))
                site, = self.cli('indirect-flow6502.py', 'jump.prg')['indirectJumpSites']
                self.assertEqual([(w['pc'], w['byte']) for w in site['staticPointerByteWrites']], expected)


if __name__ == '__main__':
    unittest.main()
