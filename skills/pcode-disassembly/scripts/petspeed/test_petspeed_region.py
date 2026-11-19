"""Synthetic interval/refusal tests; no specimen, runtime, or private dependency.

Only the hash function's response for an all-zero synthetic runtime is mocked
for positive grammar tests.  The built-in profile, selection, layout inspection,
and instruction decoder remain real.  Separate unmocked tests require refusal
of that synthetic fingerprint.  This is not real-runtime validation.
"""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import petspeed as ps
import petspeed_region as region


PROFILE = json.loads(Path(__file__).with_name('petspeed_profile.json').read_text())
START = 0x3000
RUNTIME = bytes(0x2800 - 0x0826)


def fixture(code: bytes) -> bytes:
    base = 0x0801
    raw = bytearray(START + len(code) - base)
    raw[0x0819 - base:0x081C - base] = bytes.fromhex('4c4522')
    for key, value in dict(data=0x2800, arrays=0x2800, initialization=0x2800,
                           codeCursor=START - 1, topCode=START + len(code)).items():
        offset = PROFILE['headerWords'][key] - base
        raw[offset:offset + 2] = value.to_bytes(2, 'little')
    raw[START - base:] = code
    return base.to_bytes(2, 'little') + raw


@contextlib.contextmanager
def synthetic_runtime():
    real_sha = ps.sha
    with mock.patch.object(ps, 'sha', side_effect=lambda data:
                           PROFILE['runtimeSha256'] if data == RUNTIME else real_sha(data)):
        yield


class RegionTests(unittest.TestCase):
    def decode(self, code, start=START, stop=None):
        with synthetic_runtime():
            return region.disassemble_region(fixture(code), start,
                                             START + len(code) if stop is None else stop)

    def test_pinned_builtin_identity(self):
        self.assertEqual(PROFILE['entryBytes'], '4c4522')
        self.assertEqual(PROFILE['runtimeSha256'],
                         'cee17449b6e9700af4642546477c06dbb42413888fa5e594ebded33014c5dbaf')

    def test_exact_partition_and_canonical_rows(self):
        code = bytes.fromhex('52 07 46 02 58 59 d5 d8')
        result = self.decode(code)
        self.assertEqual([i['address'] for i in result['instructions']],
                         [START, START + 2, START + 6, START + 7])
        self.assertEqual([i['size'] for i in result['instructions']], [2, 4, 1, 1])
        raw, base, layout = None, None, None
        with synthetic_runtime():
            raw, base, layout = ps.inspect_image(fixture(code), PROFILE)
        expected = [ps.decode_one(raw, base, item['address'], layout['topCode'], PROFILE)
                    for item in result['instructions']]
        self.assertEqual(result['instructions'], expected)
        self.assertEqual(result['decodedBytes'], len(code))
        self.assertTrue(result['completeIntervalDecode'])
        self.assertFalse(result['completeCodeDecode'])
        self.assertEqual(result['entryBasis'], 'declared-code-start')
        self.assertEqual(result['encodedTargets'], [])
        self.assertEqual(result, json.loads(json.dumps(result)))
        self.assertEqual(result, self.decode(code))

    def test_interval_chr_has_no_operand_and_is_a_branch_boundary(self):
        result = self.decode(bytes.fromhex('d1 05 30 52 c7 c7'))
        literal, char = result['instructions'][1:]
        self.assertEqual(literal['operands']['value'], 0xc7)
        self.assertEqual((char['mnemonic'], char['bytes'], char['size'], char['operands'], char['control']),
                         ('CHR_STRING', 'c7', 1, {}, 'fallthrough'))
        self.assertEqual(result['encodedTargets'], [
            {'source': START, 'target': START + 5, 'scope': 'internal', 'boundaryVerified': True}])
        self.assertFalse(result['completeCodeDecode'])
        with self.assertRaisesRegex(ps.DecodeError, 'falls inside an instruction'):
            self.decode(bytes.fromhex('d1 04 30 52 c7 c7'))

    def test_interval_chr_does_not_admit_unknown_or_truncated_successor(self):
        for code, error in [('c7 f4', 'truncated instruction'), ('c7 f1', 'truncated instruction'),
                            ('c7 ee', 'truncated instruction'), ('c7 48', 'unknown operand length'),
                            ('c7 52', 'truncated instruction')]:
            with self.subTest(code=code), self.assertRaisesRegex(ps.DecodeError, error):
                self.decode(bytes.fromhex(code))

    def test_word_store_and_both_operand_cuts(self):
        code = bytes.fromhex('f4 34 12 d8')
        r = self.decode(code, stop=START + 3)
        self.assertEqual(r['instructions'][0]['operands'], {'value': 0x1234})
        self.assertEqual(r['encodedTargets'], [])
        for offset in (1, 2):
            with self.subTest(offset=offset):
                with self.assertRaisesRegex(ps.DecodeError, 'stop falls inside'):
                    self.decode(code, stop=START + offset)
                with self.assertRaisesRegex(ps.DecodeError, 'start falls inside'):
                    self.decode(code, start=START + offset)

    def test_no_decode_sweep_or_reachability(self):
        code = bytes.fromhex('41 d8 41')
        with synthetic_runtime(), mock.patch.object(ps, 'decode_one', wraps=ps.decode_one) as decode:
            result = region.disassemble_region(fixture(code), START + 1, START + 2)
        self.assertEqual([call.args[2] for call in decode.call_args_list], [START, START + 1])
        self.assertEqual(result['entryBasis'], 'caller-assumed')
        self.assertEqual([i['mnemonic'] for i in result['instructions']], ['RETURN'])

    def test_unproved_entry_remains_caller_assumed(self):
        # Zero looks like an opcode even when it could be a preceding string's
        # payload.  Without an anchored prefix, decoding cannot establish entry.
        result = self.decode(bytes.fromhex('41 46 01 00 d3'), START + 3, START + 4)
        self.assertEqual(result['entryBasis'], 'caller-assumed')
        self.assertEqual(result['instructions'][0]['mnemonic'], 'LOAD_ARG_VAR')

    def test_demonstrable_start_inside_first_instruction_refused(self):
        for offset in (1, 2, 3):
            with self.subTest(offset=offset), self.assertRaisesRegex(ps.DecodeError, 'start falls inside'):
                self.decode(bytes.fromhex('46 02 00 00 d3'), START + offset)

    def test_fixed_and_variable_stop_cuts_refused(self):
        for code, stop in [(b'\x52\x00\xd3', START + 1),
                           (b'\x46\x02XY\xd3', START + 3),
                           (b'\x80\x05\xd3', START + 1)]:
            with self.subTest(code=code), self.assertRaisesRegex(ps.DecodeError, 'stop falls inside'):
                self.decode(code, stop=stop)

    def test_stop_cannot_hide_contextual_modifier(self):
        for opcode, modifier in [(0xD6, 0x41), (0xDB, 0x42), (0xDC, 0x41)]:
            code = bytes([opcode, modifier, 0xD3])
            with self.subTest(opcode=opcode):
                with self.assertRaisesRegex(ps.DecodeError, 'stop falls inside'):
                    self.decode(code, stop=START + 1)
                with self.assertRaisesRegex(ps.DecodeError, 'start falls inside'):
                    self.decode(code, START + 1)
                result = self.decode(code, stop=START + 2)
                self.assertEqual(result['instructions'][0]['size'], 2)
        self.assertEqual(self.decode(b'\xd6')['instructions'][0]['size'], 1)
        self.assertEqual(self.decode(b'\xdc\x42', stop=START + 1)['decodedBytes'], 1)

    def test_unknown_opcode_selector_and_truncated_forms_refused(self):
        for code in [b'\x41', b'\x80\x07', b'\x80', b'\x52', b'\x40\x01',
                     b'\x46', b'\x46\x03X', b'\xe2\x06\xd1\x00',
                     b'\xfa\x00\x40', b'\xd3\x41']:
            with self.subTest(code=code), self.assertRaises(ps.DecodeError):
                self.decode(code)

    def test_invalid_ranges_and_types_refused(self):
        for start, stop in [(START, START), (START + 1, START), (START - 1, START + 1),
                            (START, START + 3), (START + 2, START + 3),
                            (-1, START), (START, 0x10001), (True, START + 1),
                            (START, False), (float(START), START + 1), ('0x3000', START + 1)]:
            with self.subTest(start=start, stop=stop), self.assertRaises(ps.DecodeError):
                self.decode(b'\xd3\xd8', start, stop)

    def test_internal_direct_and_relative_targets(self):
        result = self.decode(bytes.fromhex('d4 04 d1 00 30 d8'))
        self.assertEqual(result['encodedTargets'], [
            {'source': START, 'target': START + 5, 'scope': 'internal', 'boundaryVerified': True},
            {'source': START + 2, 'target': START, 'scope': 'internal', 'boundaryVerified': True}])

    def test_interior_direct_and_relative_targets_refused(self):
        for code in [bytes.fromhex('d1 01 30 d8'), bytes.fromhex('d4 02 52 00 d8')]:
            with self.subTest(code=code), self.assertRaisesRegex(ps.DecodeError, 'falls inside an instruction'):
                self.decode(code)

    def test_external_targets_before_start_and_at_stop(self):
        code = bytes.fromhex('d3 d1 00 30 d1 07 30 d8')
        result = self.decode(code, START + 1, START + 7)
        self.assertEqual(result['encodedTargets'], [
            {'source': START + 1, 'target': START, 'scope': 'external', 'boundaryVerified': False},
            {'source': START + 4, 'target': START + 7, 'scope': 'external', 'boundaryVerified': False}])

    def test_targets_outside_declared_code_including_top_refused(self):
        for target in (0, START - 1, START + 4, 0xFFFF):
            code = b'\xd1' + target.to_bytes(2, 'little') + b'\xd8'
            with self.subTest(target=target), self.assertRaisesRegex(ps.DecodeError, 'outside declared code'):
                self.decode(code)
        with self.assertRaisesRegex(ps.DecodeError, 'outside declared code'):
            self.decode(b'\xd4\xff\xd8')

    def test_all_on_table_targets_checked(self):
        code = bytes.fromhex('e2 06 d1 07 30 08 30 d3 d8')
        result = self.decode(code, stop=START + 8)
        self.assertEqual([t['scope'] for t in result['encodedTargets']], ['internal', 'external'])
        for bad in [bytes.fromhex('e2 06 d1 07 30 01 30 d3 d8'),
                    bytes.fromhex('e2 06 d1 07 30 00 00 d3 d8'),
                    bytes.fromhex('e2 03 d1 00'), bytes.fromhex('e2 02 d3')]:
            with self.subTest(bad=bad), self.assertRaises(ps.DecodeError):
                self.decode(bad)

    def test_function_body_skip_and_nontarget_descriptor(self):
        code = bytes.fromhex('fa 00 40 06 30 08 a4 d8 d3')
        result = self.decode(code, stop=START + 8)
        self.assertEqual([t['target'] for t in result['encodedTargets']], [START + 6, START + 8])
        self.assertEqual([t['scope'] for t in result['encodedTargets']], ['internal', 'external'])
        for bad in [bytes.fromhex('fa 00 40 01 30 08 a4 d8 d3'),
                    bytes.fromhex('fa 00 40 06 30 05 a4 d8 d3')]:
            with self.subTest(bad=bad), self.assertRaisesRegex(ps.DecodeError, 'falls inside an instruction'):
                self.decode(bad)

    def test_data_operands_and_runtime_managed_edges_not_targets(self):
        result = self.decode(bytes.fromhex('fc 00 40 f0 00 40 e1 00 40 d5 d8'))
        self.assertEqual(result['encodedTargets'], [])
        self.assertEqual(result['instructions'][-2]['control'], 'runtime-managed')

    def test_unmocked_fingerprint_refused(self):
        with self.assertRaisesRegex(ps.DecodeError, 'unsupported runtime fingerprint'):
            region.disassemble_region(fixture(b'\xd3'), START, START + 1)

    def test_header_stub_runtime_and_layout_refusals(self):
        original = fixture(b'\xd3')
        cases = [b'', b'\x01\x08', b'\x00\x08' + original[2:]]
        for address, data in [(0x0819, b'\xea'), (0x0826, b'\x01'),
                              (PROFILE['headerWords']['topCode'], b'\xff\x2f')]:
            bad = bytearray(original)
            offset = 2 + address - 0x0801
            bad[offset:offset + len(data)] = data
            cases.append(bytes(bad))
        for bad in cases:
            with self.subTest(length=len(bad)), synthetic_runtime(), self.assertRaises(ps.DecodeError):
                region.disassemble_region(bad, START, START + 1)

    def test_alternate_selection_refused(self):
        alternate = dict(PROFILE, entryBytes='4c6722')
        with mock.patch.object(ps, 'select_profile', return_value=alternate) as select:
            with self.assertRaisesRegex(ps.DecodeError, 'only the pinned JMP'):
                region.disassemble_region(fixture(b'\xd3'), START, START + 1)
        select.assert_called_once()

    def test_no_profile_or_hash_override_api(self):
        for keyword in ('profile', 'runtimeSha256', 'allow_hash_mismatch'):
            with self.subTest(keyword=keyword), self.assertRaises(TypeError):
                region.disassemble_region(fixture(b'\xd3'), START, START + 1, **{keyword: PROFILE})

    def test_cli_json_success_and_refusal_without_output(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'synthetic.prg'
            original = fixture(b'\xd3')
            path.write_bytes(original)
            output = io.StringIO()
            with synthetic_runtime(), contextlib.redirect_stdout(output):
                status = region.main([str(path), '--start', '$3000', '--stop', '12289'])
            self.assertEqual(status, 0)
            self.assertEqual(json.loads(output.getvalue())['decodedBytes'], 1)
            output, error = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(output), contextlib.redirect_stderr(error):
                with self.assertRaises(SystemExit) as exc:
                    region.main([str(path), '--start', '0x3000', '--stop', '0x3001'])
            self.assertEqual(exc.exception.code, 2)
            self.assertEqual(output.getvalue(), '')
            self.assertIn('REFUSED: unsupported runtime fingerprint', error.getvalue())
            self.assertEqual(path.read_bytes(), original)

    def test_cli_requires_both_bounds_and_has_no_overrides(self):
        for args in [[], ['--start', '0x3000'], ['--stop', '0x3001'],
                     ['--start', 'bad', '--stop', '0x3001'],
                     ['--start', '0x3000', '--stop', '0x3001', '--profile', 'custom.json'],
                     ['--start', '0x3000', '--stop', '0x3001', '--allow-hash-mismatch']]:
            with self.subTest(args=args), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as exc:
                    region.main(['unused.prg', *args])
            self.assertEqual(exc.exception.code, 2)


if __name__ == '__main__':
    unittest.main()
