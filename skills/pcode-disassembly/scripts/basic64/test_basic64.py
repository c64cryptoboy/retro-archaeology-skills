"""Synthetic parser/refusal tests: no commercial runtime is bundled."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import basic64 as b

P = json.loads(Path(__file__).with_name('basic64_profile.json').read_text())
START = 0x1DAA


def image(code, descriptors=b''):
    start = START + len(descriptors)
    raw = bytearray(start - 0x801)

    def put(address, value):
        raw[address-0x801:address-0x801+len(value)] = value

    put(0x1D97, b'\x99\x1d')
    put(0x1D99, b'\x20\xb3\x1a' + (start-3).to_bytes(2, 'little') +
        b'\x00\xa0\xfa\xff' + (start-6).to_bytes(2, 'little'))
    put(0x1DA4, descriptors)
    put(start-3, bytes.fromhex('20 11 1b'))
    return b'\x01\x08' + raw + code + b'\0\0'


def line_map(rows, footer=b'\0\0\0'):
    out = bytearray(b'\x01\x08')
    for line, address in rows:
        out += b'\x40\x40' + address.to_bytes(2, 'little') + b'\xb2 ' + str(line).encode() + b' \0'
    return bytes(out) + footer


class DecoderTests(unittest.TestCase):
    def decode(self, code, rows=None, source=None, descriptors=b''):
        return b.disassemble(image(code, descriptors), P,
                             line_map(rows) if rows is not None else None,
                             source, verify=False)

    def test_small_program_and_classified_trailer(self):
        r = self.decode(b'\x37\x03ABC\x83\x84\x73\x73',
                        [(10, START), (20, START+7)], '10 PRINT"ABC"\n20 END\n')
        self.assertTrue(r['completeCodeDecode'], r['error'])
        self.assertTrue(r['semanticCodeExtentVerified'])
        self.assertEqual(r['decodedBytes'], 9)
        self.assertEqual(r['instructions'][0]['size'], 5)
        self.assertIn('; BASIC 10 PRINT"ABC"', b.render(r))
        self.assertEqual(b.render(r), b.render(json.loads(json.dumps(r))))
        self.assertEqual(r['lineMap']['footerHex'], '000000')
        self.assertEqual(r['layout']['loadedEnd']-r['layout']['codeEnd'], 2)

    def test_regions_partition_entire_loaded_image(self):
        r = self.decode(b'\x73')
        regions = r['regions']
        self.assertEqual(regions[0]['start'], 0x801)
        self.assertEqual(regions[-1]['end'], r['layout']['loadedEnd'])
        for left, right in zip(regions, regions[1:]):
            self.assertEqual(left['end'], right['start'])

    def test_trailer_not_consumed_to_complete_operand(self):
        r = self.decode(b'\x26\x12')
        self.assertFalse(r['completeCodeDecode'])
        self.assertIn('truncated', r['error'])

    def test_missing_or_changed_trailer_refuses(self):
        for data in (image(b'\x73')[:-1], image(b'\x73')[:-1]+b'\x01'):
            r = b.disassemble(data, P, verify=False)
            self.assertFalse(r['completeCodeDecode'])
            self.assertIn('trailer', r['error'])

    def test_zero_width_and_duplicate_map_records_survive(self):
        r = self.decode(b'\x73', [(1, START), (2, START), (2, START)])
        self.assertTrue(r['completeCodeDecode'])
        self.assertEqual(len(r['lineMap']['records']), 3)

    def test_opaque_map_footer_preserved(self):
        result = b.parse_map(line_map([(10, START)], b'\0\0\x9a\x41'))
        self.assertEqual(result['footerHex'], '00009a41')

    def test_float5_fac_and_arg(self):
        for op in (0x32, 0x33):
            r = self.decode(bytes([op])+bytes.fromhex('82 e0 00 00 00 73'))
            self.assertTrue(r['completeCodeDecode'])
            self.assertEqual(r['instructions'][0]['operands']['exact'], '-7/2')
            self.assertEqual(r['instructions'][0]['size'], 6)

    def test_word_endianness_byte_width_and_signedness(self):
        r = self.decode(bytes.fromhex('26 34 12 28 78 56 22 ff 23 ff ff 73'))
        self.assertTrue(r['completeCodeDecode'])
        self.assertEqual(r['instructions'][0]['operands']['value'], 0x1234)
        self.assertEqual(r['instructions'][1]['operands']['value'], 0x5678)
        self.assertEqual(r['instructions'][2]['size'], 2)
        self.assertEqual(r['instructions'][3]['operands']['signedValue'], -1)

    def test_basic_payload_not_recursively_decoded(self):
        r = self.decode(bytes.fromhex('9b 03 3a 9e ff 73'))
        self.assertTrue(r['completeCodeDecode'])
        self.assertEqual(r['instructions'][0]['operands']['payloadHex'], '3a9eff')
        self.assertEqual(r['instructions'][0]['control'], 'interpreted')

    def test_function_implicit_body_and_skip(self):
        r = self.decode(bytes.fromhex('72 34 12 b0 1d 73 73'))
        self.assertTrue(r['completeCodeDecode'], r['error'])
        self.assertEqual(r['instructions'][0]['operands']['targets'], [START+5, START+6])
        self.assertEqual(r['instructions'][0]['size'], 5)

    def test_every_function_target_checked(self):
        r = self.decode(bytes.fromhex('72 34 12 ab 1d 73'))
        self.assertFalse(r['completeCodeDecode'])
        self.assertIn('control target', r['error'])

    def test_function_descriptor_is_not_a_code_target(self):
        r = self.decode(bytes.fromhex('93 ff 9f 73'))
        self.assertTrue(r['completeCodeDecode'])
        self.assertNotIn('target', r['instructions'][0]['operands'])

    def test_branch_into_string_refuses(self):
        r = self.decode(bytes.fromhex('8a b0 1d 37 02 41 42 73'))
        self.assertFalse(r['completeCodeDecode'])
        self.assertIn('boundary', r['error'])

    def test_fallthrough_into_trailer_refuses(self):
        r = self.decode(b'\x00')
        self.assertFalse(r['completeCodeDecode'])
        self.assertIn('fallthrough', r['error'])

    def test_branch_to_trailer_refuses(self):
        r = self.decode(bytes.fromhex('8a ad 1d'))
        self.assertFalse(r['completeCodeDecode'])
        self.assertIn('boundary', r['error'])

    def test_map_into_operand_refuses(self):
        r = self.decode(bytes.fromhex('37 02 41 42 73'), [(10, START+2)])
        self.assertFalse(r['completeCodeDecode'])
        self.assertIn('Z-map anchor', r['error'])

    def test_truncations_and_unknown_no_resync(self):
        cases = ['ff 73', '37', '37 02 41', '26 12', '9b 03 41', '32 81',
                 '72 01 02', '7c 00', '7c 03 41 42', '8f 02 aa 1d']
        for text in cases:
            with self.subTest(text=text):
                r = self.decode(bytes.fromhex(text))
                self.assertFalse(r['completeCodeDecode'])
                self.assertEqual(r['decodedBytes'], 0)

    def test_unknown_operand_grammar_refuses(self):
        profile = copy.deepcopy(P)
        profile['opcodes']['73']['operand'] = 'unknown-selector-format'
        r = b.disassemble(image(b'\x73'), profile, verify=False)
        self.assertFalse(r['completeCodeDecode'])

    def test_bad_map_formats(self):
        cases = [b'', b'\x01\x08', b'\x01\x08\x01\x08',
                 b'\x01\x08\x40\x40\x00\x20BAD\0\0\0']
        for data in cases:
            with self.assertRaises(b.DecodeError):
                b.parse_map(data)

    def test_source_requires_map_and_unique_lines(self):
        self.assertFalse(self.decode(b'\x73', source='10 END\n')['completeCodeDecode'])
        with self.assertRaises(b.DecodeError):
            b.parse_source('10 END\n10 END\n')

    def test_fingerprint_header_and_schema_refusals(self):
        self.assertFalse(b.disassemble(image(b'\x73'), P)['completeCodeDecode'])
        prg = bytearray(image(b'\x73'))
        prg[2+0x1DA7-0x801] = 0
        self.assertFalse(b.disassemble(prg, P, verify=False)['completeCodeDecode'])
        bad = copy.deepcopy(P)
        bad['schema'] = 'other'
        self.assertFalse(b.disassemble(image(b'\x73'), bad, verify=False)['completeCodeDecode'])

    def test_input_prompt_with_embedded_nul_and_target(self):
        r = self.decode(bytes.fromhex('7c 03 41 00 42 b1 1d 73'))
        self.assertTrue(r['completeCodeDecode'], r['error'])
        self.assertEqual(r['instructions'][0]['operands']['target'], START+7)
        self.assertEqual(r['instructions'][0]['operands']['length'], 3)

    def test_input_target_inside_prompt_refuses(self):
        r = self.decode(bytes.fromhex('7c 03 41 00 42 ad 1d 73'))
        self.assertFalse(r['completeCodeDecode'])

    def test_three_target_on_tables(self):
        for op in (0x8F, 0x90):
            r = self.decode(bytes([op])+bytes.fromhex('03 b2 1d b3 1d b4 1d 73 73 73'))
            self.assertTrue(r['completeCodeDecode'], r['error'])
            self.assertEqual(r['instructions'][0]['size'], 8)
            self.assertEqual(r['instructions'][0]['operands']['targets'], [START+8, START+9, START+10])

    def test_every_on_target_checked(self):
        for index in range(3):
            data = bytearray.fromhex('8f 03 b2 1d b3 1d b4 1d 73 73 73')
            data[2+index*2:4+index*2] = (START+1).to_bytes(2, 'little')
            self.assertFalse(self.decode(data)['completeCodeDecode'])

    def test_on_count_wrap_refuses(self):
        r = self.decode(b'\x8f\x80'+b'\0'*256)
        self.assertFalse(r['completeCodeDecode'])
        self.assertIn('count 128', r['error'])

    def test_zero_count_on_table(self):
        self.assertTrue(self.decode(bytes.fromhex('8f 00 73'))['completeCodeDecode'])

    def test_error_target_zero_disables(self):
        r = self.decode(bytes.fromhex('9f 00 00 73'))
        self.assertTrue(r['completeCodeDecode'])
        self.assertNotIn('target', r['instructions'][0]['operands'])

    def test_array_descriptor_and_stride(self):
        r = self.decode(bytes.fromhex('38 0b 73'), descriptors=bytes.fromhex('f0 ff 01 02 00'))
        self.assertTrue(r['completeCodeDecode'], r['error'])
        self.assertEqual(r['descriptors'][0]['extentsReversed'], [2])
        self.assertEqual(r['instructions'][0]['operands']['elementSize'], 5)

    def test_array_descriptor_boundary_and_extent_refusals(self):
        for code, desc in [('38 0c 73', 'f0 ff 01 02 00'),
                           ('38 0b 73', 'f0 ff 01 ff ff'),
                           ('73', 'f0 ff 01'), ('73', 'f0 ff 00')]:
            r = self.decode(bytes.fromhex(code), descriptors=bytes.fromhex(desc))
            self.assertFalse(r['completeCodeDecode'])

    def test_repeatable_results(self):
        self.assertEqual(self.decode(b'\x37\x01A\x83\x73'), self.decode(b'\x37\x01A\x83\x73'))

    def test_cli_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            prg = root/'fake.prg'
            prg.write_bytes(image(b'\x73'))
            out = root/'report.json'
            out.write_text('preserve me')
            result = subprocess.run([sys.executable, str(Path(b.__file__)), str(prg),
                                     '--json-output', str(out)], capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(b'refusing to overwrite', result.stderr)
            self.assertEqual(out.read_text(), 'preserve me')


if __name__ == '__main__':
    unittest.main()
