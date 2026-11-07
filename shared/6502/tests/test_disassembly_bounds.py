#!/usr/bin/env python3
"""Synthetic bounds regressions for the shared disassembler and CFG.

DISASSEMBLY_TOOLS optionally selects preserved source for a negative-control run.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

TOOLS = Path(os.environ.get('DISASSEMBLY_TOOLS', Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(TOOLS))
import cfg6502
import dis6502


class DisassemblyBoundsTests(unittest.TestCase):
    def invoke(self, tool, blob, *args):
        with tempfile.TemporaryDirectory() as work:
            path = Path(work) / 'input.prg'
            path.write_bytes(blob)
            return subprocess.run([sys.executable, '-B', str(TOOLS / tool), str(path), *args],
                                  text=True, capture_output=True, timeout=5,
                                  env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})

    def assert_cli_error(self, process, message):
        self.assertEqual(process.returncode, 2, process.stdout + process.stderr)
        self.assertEqual(process.stdout, '')
        self.assertIn(message, process.stderr)
        self.assertNotIn('Traceback', process.stderr)

    def test_truncated_jsr_has_no_invented_operand_or_brk(self):
        process = self.invoke('dis6502.py', bytes.fromhex('00 10 20 34'))
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(process.stdout.splitlines(),
                         ['1000: 20 34    JSR ; INCOMPLETE (expected 3 bytes)'])

    def test_all_incomplete_official_instructions_are_explicit(self):
        for opcode, (mnemonic, mode, length) in dis6502.ops.items():
            for available in range(1, length):
                with self.subTest(opcode=opcode, available=available):
                    raw = bytes([opcode, 0x34, 0x12][:available])
                    process = self.invoke('dis6502.py', b'\x00\x10' + raw)
                    self.assertEqual(process.returncode, 0, process.stderr)
                    self.assertEqual(len(process.stdout.splitlines()), 1)
                    self.assertIn(f'{mnemonic:3} ; INCOMPLETE (expected {length} bytes)',
                                  process.stdout)
                    self.assertNotIn('$', process.stdout)

    def test_formatter_refuses_missing_operand_bytes(self):
        for opcode, (mnemonic, mode, length) in dis6502.ops.items():
            if length == 1:
                continue
            for available in range(length):
                with self.subTest(opcode=opcode, available=available):
                    with self.assertRaisesRegex(ValueError, 'incomplete .* instruction'):
                        dis6502.fmt(mode, bytes([opcode, 0x34, 0x12][:available]), 0x1000)

    def test_complete_official_instructions_still_decode(self):
        for opcode, (mnemonic, mode, length) in dis6502.ops.items():
            with self.subTest(opcode=opcode):
                raw = bytes([opcode, 0x34, 0x12][:length])
                ins = cfg6502.decode(raw, 0x1000, 0x1000)
                self.assertEqual(ins, {'pc': 0x1000, 'bytes': list(raw),
                                      'mnemonic': mnemonic, 'mode': mode, 'length': length,
                                      'operand': dis6502.fmt(mode, raw, 0x1000)})
                self.assertIsInstance(ins['operand'], str)

    def test_complete_cli_output_and_eof(self):
        process = self.invoke('dis6502.py', bytes.fromhex('00 10 a9 42 20 34 12 00'))
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(process.stdout.splitlines(),
                         ['1000: a9 42    LDA #$42', '1002: 20 34 12 JSR $1234',
                          '1005: 00       BRK '])

    def test_complete_then_truncated_stops_at_available_bytes(self):
        process = self.invoke('dis6502.py', bytes.fromhex('00 10 ea a9'))
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(process.stdout.splitlines(),
                         ['1000: ea       NOP ',
                          '1001: a9       LDA ; INCOMPLETE (expected 2 bytes)'])

    def test_unknown_opcode_remains_one_byte(self):
        process = self.invoke('dis6502.py', bytes.fromhex('00 10 02 60'))
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(process.stdout.splitlines(),
                         ['1000: 02       ???$02 ', '1001: 60       RTS '])

    def test_positional_start_count_and_zero_count(self):
        blob = bytes.fromhex('00 10 ea a9 42 60')
        process = self.invoke('dis6502.py', blob, '0x1001', '0x1')
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(process.stdout, '1001: a9 42    LDA #$42\n')
        process = self.invoke('dis6502.py', blob, '0x1000', '0')
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(process.stdout, '')

    def test_cli_rejects_malformed_headers(self):
        for tool in ('dis6502.py', 'cfg6502.py'):
            for blob in (b'', b'\x00', b'\x00\x10'):
                with self.subTest(tool=tool, blob=blob):
                    self.assert_cli_error(self.invoke(tool, blob),
                                          'two-byte load address and at least one byte')

    def test_cli_rejects_invalid_start_and_count(self):
        for args, message in ((('-1',), 'start address'),
                              (('65536',), 'start address'),
                              (('0x1001',), 'start address'),
                              (('0x0fff',), 'start address'),
                              (('bad',), 'invalid'),
                              (('0x1000', '-1'), 'count must be nonnegative')):
            with self.subTest(args=args):
                self.assert_cli_error(self.invoke('dis6502.py', bytes.fromhex('00 10 ea'),
                                                  *args), message)

    def test_cli_rejects_nonwrapping_extent_overflow(self):
        for tool in ('dis6502.py', 'cfg6502.py'):
            with self.subTest(tool=tool):
                self.assert_cli_error(self.invoke(tool, bytes.fromhex('ff ff ea 60')),
                                      'PRG load range exceeds 16-bit address space')

    def test_analyze_rejects_nonwrapping_extent_overflow(self):
        for base, raw in ((0xffff, b'\xea\x60'), (0, b'\xea' * 65537)):
            with self.subTest(base=base):
                with self.assertRaisesRegex(ValueError, 'PRG load range exceeds 16-bit address space'):
                    cfg6502.analyze(raw, base, [base], 10)

    def test_analyze_rejects_invalid_base(self):
        for base in (-1, 65536):
            with self.subTest(base=base):
                with self.assertRaisesRegex(ValueError, 'PRG load address must be a 16-bit address'):
                    cfg6502.analyze(b'\x60', base, [base], 10)

    def test_valid_extent_ending_at_65536(self):
        blob = bytes.fromhex('fe ff ea 60')
        process = self.invoke('cfg6502.py', blob, '--json')
        self.assertEqual(process.returncode, 0, process.stderr)
        result = json.loads(process.stdout)
        self.assertEqual(result['endAddressExclusive'], 65536)
        self.assertEqual([i['pc'] for i in result['instructions']], [65534, 65535])
        self.assertEqual(result['stops'], [{'at': 65535, 'reason': 'rts'}])
        process = self.invoke('dis6502.py', blob)
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(process.stdout.splitlines(),
                         ['FFFE: ea       NOP ', 'FFFF: 60       RTS '])

    def test_relative_format_wraps_in_both_directions(self):
        for pc, raw, expected in ((0xfffe, b'\xd0\x00', '$0000'),
                                  (0xffff, b'\xd0\xff', '$0000'),
                                  (0, b'\xd0\xfc', '$FFFE'),
                                  (0x1000, b'\xd0\xfe', '$1000')):
            with self.subTest(pc=pc, raw=raw):
                self.assertEqual(dis6502.fmt('rel', raw, pc), expected)

    def test_branch_target_and_fallthrough_wrap_without_image_wrap(self):
        result = cfg6502.analyze(b'\xd0\x00', 0xfffe, [0xfffe], 10)
        self.assertEqual(result['instructions'][0]['operand'], '$0000')
        self.assertEqual(result['edges'],
                         [{'from': 65534, 'to': 0, 'kind': kind, 'internal': False}
                          for kind in ('branch', 'fallthrough')])
        self.assertEqual(len(result['instructions']), 1)

    def test_jsr_fallthrough_wraps(self):
        result = cfg6502.analyze(b'\x20\x34\x12', 0xfffd, [0xfffd], 10)
        self.assertEqual(result['edges'],
                         [{'from': 65533, 'to': 0x1234, 'kind': 'call', 'internal': False},
                          {'from': 65533, 'to': 0, 'kind': 'fallthrough', 'internal': False}])

    def test_full_image_allows_known_wrapped_successor(self):
        for tail in (b'\xd0\x00', b'\xea'):
            with self.subTest(tail=tail):
                raw = bytearray(65536)
                raw[-len(tail):] = tail
                start = 65536 - len(tail)
                result = cfg6502.analyze(raw, 0, [start], 10)
                self.assertEqual([i['pc'] for i in result['instructions']], [0, start])
                self.assertEqual(result['stops'], [{'at': 0, 'reason': 'brk'}])
                self.assertTrue(all(e['internal'] for e in result['edges']))

    def test_truncated_at_ffff_does_not_fetch_from_zero(self):
        raw = bytearray(65536)
        raw[-1] = 0xa9
        result = cfg6502.analyze(raw, 0, [0xffff], 10)
        self.assertEqual(result['instructions'], [{'pc': 65535, 'bytes': [0xa9],
                                                  'mnemonic': 'LDA', 'mode': 'imm',
                                                  'length': 2, 'truncated': True}])
        self.assertEqual(result['edges'], [])
        self.assertEqual(result['stops'], [{'at': 65535, 'reason': 'invalid_or_truncated_opcode'}])


if __name__ == '__main__':
    unittest.main()
