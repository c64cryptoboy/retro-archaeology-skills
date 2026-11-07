"""Synthetic grammar/refusal tests: no commercial runtime bytes required."""
import copy
import json
from pathlib import Path
import unittest

import petspeed as ps

PROFILE = json.loads(Path(__file__).with_name('petspeed_profile.json').read_text())


def fixture(code):
    profile = copy.deepcopy(PROFILE)
    base, start = 0x0801, 0x281B
    raw = bytearray(start + len(code) - base)
    raw[0x819-base:0x81c-base] = bytes.fromhex(profile['entryBytes'])
    for key, value in dict(data=0x2810, arrays=0x2811, initialization=0x2812,
                           codeCursor=start-1, topCode=start+len(code)).items():
        p = profile['headerWords'][key] - base
        raw[p:p+2] = value.to_bytes(2, 'little')
    profile['runtimeSha256'] = ps.sha(raw[0x826-base:0x2800-base])
    raw[start-base:] = code
    return base.to_bytes(2, 'little') + raw, profile


def w_map(code_size, rows, footer=b'\xff\xff\xff\xee'):
    return (f' 10267 \r {10267+code_size+1} \r'.encode()
            + b''.join(a.to_bytes(2, 'little')+b.to_bytes(2, 'little') for a,b in rows) + footer)


class DecoderTests(unittest.TestCase):
    def decode(self, code, rows=None, source=None):
        prg, profile = fixture(code)
        return ps.disassemble(prg, profile, w_map(len(code), rows) if rows is not None else None, source)

    def test_string_print_end_and_exact_byte_coverage(self):
        result = self.decode(b'\x46\x02HI\xd0\xec\xd3\xd3', [(10,0),(20,6),(20,7)], '10 PRINT"HI"\n20 END\n')
        self.assertTrue(result['completeCodeDecode'])
        self.assertEqual(result['decodedBytes'], 8)
        self.assertEqual([r['mnemonic'] for r in result['instructions']], ['CONST_STRING_FAC','PRINT_STRING','PRINT_NEWLINE','END','END'])
        text = ps.render(result)
        self.assertIn('10 PRINT"HI"', text)
        self.assertIn('additional compiler map record', text)
        self.assertEqual(text, ps.render(result))
        self.assertEqual(text, ps.render(json.loads(json.dumps(result))))

    def test_unknown_does_not_resynchronize(self):
        result = self.decode(b'\x52\x01\x41\xd3')
        self.assertFalse(result['completeCodeDecode'])
        self.assertEqual(result['decodedBytes'], 2)
        self.assertIn('unknown operand length', result['error'])
        self.assertEqual(len(result['instructions']), 1)

    def test_each_truncated_operand_refused(self):
        for data in [b'\x40\x01', b'\x43\x81', b'\x46', b'\x46\x03A', b'\x52',
                     b'\xac\x28', b'\xd2\x00', b'\xfc\x11', b'\xf0\x1b', b'\xf3\x1b']:
            with self.subTest(data=data):
                self.assertFalse(self.decode(data)['completeCodeDecode'])

    def test_empty_string(self):
        r = self.decode(b'\x46\x00\xd3')
        self.assertTrue(r['completeCodeDecode'])
        self.assertEqual(r['instructions'][0]['operands']['display'], '""')

    def test_integer_endianness_sign_and_byte(self):
        r = self.decode(b'\x40\x00\x80\x49\xff\x7f\x52\xff\x55\x00')
        self.assertEqual([i['operands']['value'] for i in r['instructions']], [-32768,32767,255,0])

    def test_float6(self):
        r = self.decode(b'\x43\x80\x80\x00\x00\x00\x00\x4c\x81\x80\x00\x00\x00\x80')
        self.assertEqual([(i['operands']['numerator'],i['operands']['denominator']) for i in r['instructions']], [(1,2),(-1,1)])

    def test_compact_variable_families(self):
        r = self.decode(bytes([0,31,32,63,96,127]))
        self.assertEqual([i['operands']['slot'] for i in r['instructions']], [0,31,0,31,0,31])
        self.assertEqual(r['instructions'][-1]['operands']['variable'], 0x28F8)

    def test_map_anchor_inside_operand_refused(self):
        r = self.decode(b'\x46\x02HI\xd3', [(10,1)])
        self.assertFalse(r['completeCodeDecode'])
        self.assertIn('inside an instruction', r['error'])

    def test_duplicate_map_address_retained(self):
        r = self.decode(b'\xd3', [(10,0),(20,0)], '10 REM X\n20 END\n')
        self.assertTrue(r['completeCodeDecode'])
        self.assertIn('shares the next source', ps.render(r))

    def test_map_footer_is_not_assumed_zero(self):
        p, profile = fixture(b'\xd3')
        for footer in [b'\x00\x00\xa9\x69',b'\xff\xff\xff\xee']:
            r = ps.disassemble(p,profile,w_map(1,[(10,0)],footer))
            self.assertEqual(r['lineMap']['opaqueFooterHex'], footer.hex())
            self.assertEqual(len(r['lineMap']['records']),1)

    def test_bad_map_headers_and_truncation(self):
        p,profile=fixture(b'\xd3')
        for w in [b'bad',w_map(1,[(10,0)])[:-1],w_map(2,[(10,0)])]:
            with self.subTest(w=w), self.assertRaises(ps.DecodeError):
                ps.disassemble(p,profile,w)

    def test_bad_map_line_order_or_bounds(self):
        p,profile=fixture(b'\xd3\xd3')
        for rows in [[(20,0),(10,1)],[(10,2)],[(64000,0)],[(10,1),(20,0)]]:
            with self.subTest(rows=rows),self.assertRaises(ps.DecodeError):
                ps.disassemble(p,profile,w_map(2,rows))

    def test_wrong_runtime_or_stub_refused(self):
        p,profile=fixture(b'\xd3')
        for address in [0x819,0x926]:
            bad=bytearray(p);bad[address-0x801+2]^=1
            with self.subTest(address=address),self.assertRaises(ps.DecodeError):
                ps.disassemble(bytes(bad),profile)

    def test_region_order_and_truncated_image_refused(self):
        p,profile=fixture(b'\xd3')
        with self.assertRaises(ps.DecodeError):ps.disassemble(p[:-1],profile)
        bad=bytearray(p);bad[0x820-0x801+2:0x822-0x801+2]=b'\xff\x7f'
        with self.assertRaises(ps.DecodeError):ps.disassemble(bytes(bad),profile)

    def test_source_without_map_and_duplicate_source_refused(self):
        p,profile=fixture(b'\xd3')
        with self.assertRaises(ps.DecodeError):ps.disassemble(p,profile,source_text='10 END')
        with self.assertRaises(ps.DecodeError):ps.parse_source('10 END\n10 PRINT1')

    def test_absolute_and_conditional_targets(self):
        r = self.decode(b'\xd4\x03\xd3\xd3\xd1\x1b\x28')
        self.assertTrue(r['completeCodeDecode'])
        self.assertEqual(r['instructions'][0]['operands']['target'], 0x281F)
        self.assertEqual(r['instructions'][-1]['operands']['target'], 0x281B)

    def test_bad_control_targets_refused(self):
        for code in [b'\xd1\xff\xff', b'\xd1\x1c\x28', b'\xd4\x00\xd3']:
            with self.subTest(code=code):
                r = self.decode(code)
                self.assertFalse(r['completeCodeDecode'])
                self.assertIn('control target', r['error'])

    def test_for_next_operand_and_unencoded_target(self):
        r = self.decode(b'\xcb\x8a\xcd\x00\x28\xd5\xd3')
        self.assertTrue(r['completeCodeDecode'])
        self.assertEqual(r['instructions'][2]['operands']['value'], 0x2800)
        self.assertEqual(r['instructions'][3]['control'], 'runtime-managed')
        self.assertNotIn('target', r['instructions'][3]['operands'])

    def test_mixed_endianness_and_data_pointer_not_control_target(self):
        r = self.decode(b'\xcd\x08\x28\xac\x28\x08\xd3')
        self.assertTrue(r['completeCodeDecode'])
        self.assertEqual([i['operands']['value'] for i in r['instructions'][:2]], [0x2808, 0x2808])
        self.assertNotIn('target', r['instructions'][1]['operands'])

    def test_call_and_return(self):
        r = self.decode(b'\xd2\x1f\x28\xd3\xd8')
        self.assertTrue(r['completeCodeDecode'])
        self.assertEqual(r['instructions'][0]['operands']['target'], 0x281F)
        self.assertEqual([i['control'] for i in r['instructions']], ['call', 'terminate', 'return'])

    def test_array_forms_and_shared_handler_distinction(self):
        r = self.decode(bytes.fromhex('fc 11 28 8a a0 52 07 f8 f0 1b 28 f5 f7 9f d3'))
        self.assertTrue(r['completeCodeDecode'])
        self.assertEqual(r['instructions'][0]['operands']['value'], 0x2811)
        self.assertEqual(r['instructions'][2]['mnemonic'], 'ARRAY_DEST')
        self.assertEqual(r['instructions'][-2]['mnemonic'], 'ARRAY_LOAD_FAC')
        self.assertEqual(r['instructions'][5]['operands']['value'], 0x281B)

    def test_data_line_can_share_read_boundary(self):
        r = self.decode(bytes.fromhex('d9 60 da 61 eb d3'), [(10, 0), (20, 0)],
                        '10 DATA7,"HI"\n20 READA,A$:RESTORE:END\n')
        self.assertTrue(r['completeCodeDecode'])
        self.assertIn('shares the next source', ps.render(r))
        self.assertEqual(r['instructions'][0]['mnemonic'], 'READ_NUMBER')
        self.assertEqual(r['instructions'][2]['mnemonic'], 'READ_STRING')

    def test_secondary_dispatch_and_refusal(self):
        r = self.decode(bytes.fromhex('80 0f 80 10 d3'))
        self.assertTrue(r['completeCodeDecode'])
        self.assertEqual([i['mnemonic'] for i in r['instructions']], ['PI_FAC', 'PI_ARG', 'END'])
        self.assertEqual([i['size'] for i in r['instructions']], [2, 2, 1])
        for code in [b'\x80', b'\x80\xee\xd3']:
            self.assertFalse(self.decode(code)['completeCodeDecode'])

    def test_secondary_dispatch_payload_prefix(self):
        code = bytes.fromhex('80 ee 02 48 49 d3')
        prg, profile = fixture(code)
        profile['opcodes']['80']['selectors']['EE'] = {
            'mnemonic': 'SYNTHETIC_STRING', 'operand': 'string8', 'comment': '{display}'}
        r = ps.disassemble(prg, profile)
        self.assertTrue(r['completeCodeDecode'])
        self.assertEqual(r['instructions'][0]['size'], 5)
        self.assertEqual(r['instructions'][0]['operands']['display'], '"HI"')

    def test_contextual_store_modifiers_not_standalone_opcodes(self):
        r = self.decode(bytes.fromhex('d9 42 da 41 d9 60 d3'))
        self.assertTrue(r['completeCodeDecode'])
        self.assertEqual([i['size'] for i in r['instructions']], [2, 2, 1, 1, 1])
        self.assertEqual(r['instructions'][0]['mnemonic'], 'READ_NUMBER_STORE_INTEGER_ELEMENT')
        self.assertEqual(r['instructions'][1]['mnemonic'], 'READ_STRING_STORE_ELEMENT')
        self.assertFalse(self.decode(bytes.fromhex('41 d3'))['completeCodeDecode'])
        self.assertFalse(self.decode(bytes.fromhex('d9 41 d1 1c 28'))['completeCodeDecode'])

    def test_string_input_modifier_set_is_narrower_than_read(self):
        for op in (0xD7, 0xDC):
            with self.subTest(op=op):
                self.assertTrue(self.decode(bytes([op, 0x41, 0xD3]))['completeCodeDecode'])
                r = self.decode(bytes([op, 0x42, 0xD3]))
                self.assertFalse(r['completeCodeDecode'])
                self.assertEqual(r['decodedBytes'], 1)
        self.assertTrue(self.decode(bytes.fromhex('d9 42 d3'))['completeCodeDecode'])

    def test_extended_variable_stride_and_slot(self):
        r = self.decode(bytes.fromhex('ff 00 fd 01 fe ff d3'))
        self.assertTrue(r['completeCodeDecode'])
        self.assertEqual([i['operands']['variable'] for i in r['instructions'][:3]], [0x2900, 0x2907, 0x2FF9])
        self.assertEqual([i['operands']['slot'] for i in r['instructions'][:3]], [32, 33, 287])
        self.assertFalse(self.decode(b'\xfd')['completeCodeDecode'])

    def test_typed_array_dispatch_identities(self):
        r = self.decode(bytes.fromhex('a2 a3 a5 a6 d3'))
        self.assertTrue(r['completeCodeDecode'])
        self.assertEqual([i['mnemonic'] for i in r['instructions'][:4]],
                         ['INTEGER_ARRAY_LOAD', 'INTEGER_ARRAY_DEST', 'STRING_ARRAY_LOAD', 'STRING_ARRAY_DEST'])

    def test_omnibus_scalar_math_lengths_and_names(self):
        forms = {0xB4: 'SGN', 0xB6: 'ABS', 0xB8: 'FRE', 0xB9: 'POS',
                 0xBA: 'SQR', 0xBB: 'RND', 0xBC: 'LOG', 0xBD: 'EXP',
                 0xC0: 'TAN', 0xC1: 'ATN'}
        for opcode, name in forms.items():
            with self.subTest(opcode=opcode):
                r = self.decode(bytes([opcode, 0xD3]))
                self.assertTrue(r['completeCodeDecode'])
                self.assertEqual([i['size'] for i in r['instructions']], [1, 1])
                self.assertEqual(r['instructions'][0]['mnemonic'], name)

    def test_numeric_and_string_comparison_orientation(self):
        forms = {0x93: 'NOT_EQUAL', 0x95: 'GREATER_EQUAL', 0x96: 'LESS_EQUAL',
                 0x8B: 'GREATER_THAN', 0x90: 'NOT', 0x98: 'STRING_GREATER_THAN',
                 0x99: 'STRING_LESS_THAN', 0x9A: 'STRING_GREATER_EQUAL',
                 0x9B: 'STRING_LESS_EQUAL', 0x9D: 'STRING_EQUAL'}
        for opcode, name in forms.items():
            with self.subTest(opcode=opcode):
                r = self.decode(bytes([0x21, 0x00, opcode, 0x62]))
                self.assertTrue(r['completeCodeDecode'])
                self.assertEqual(r['instructions'][2]['mnemonic'], name)
                self.assertEqual(r['decodedBytes'], 4)
        self.assertIn('ARG string < FAC string', self.decode(b'\x99')['instructions'][0]['comment'])
        self.assertIn('ARG < FAC', self.decode(b'\x8c')['instructions'][0]['comment'])

    def test_mid_variants_and_integer_store(self):
        r = self.decode(bytes.fromhex('c6 c4 df e0 f9 d3'))
        self.assertTrue(r['completeCodeDecode'])
        self.assertEqual([i['mnemonic'] for i in r['instructions'][:5]],
                         ['ASC', 'STR_STRING', 'MID_TAIL_STRING', 'MID_ONE_STRING', 'STORE_INTEGER_ELEMENT'])
        self.assertIn('ARG string, FAC start', r['instructions'][2]['comment'])
        self.assertIn('FAC string, ARG start, 1', r['instructions'][3]['comment'])

    def test_on_tables_both_modes_and_zero_entries(self):
        for mode, name in [(0xD1, 'GOTO'), (0xD2, 'GOSUB')]:
            r = self.decode(bytes([0xE2, 6, mode, 0x22, 0x28, 0x23, 0x28, 0xD3, 0xD8]))
            self.assertTrue(r['completeCodeDecode'])
            i = r['instructions'][0]
            self.assertEqual(i['size'], 7)
            self.assertEqual(i['operands']['targets'], [0x2822, 0x2823])
            self.assertEqual(i['operands']['branchMode'], name)
        self.assertTrue(self.decode(bytes.fromhex('e2 02 d1 d3'))['completeCodeDecode'])

    def test_on_table_refusals_and_all_target_validation(self):
        good = bytes.fromhex('e2 06 d1 22 28 23 28 d3 d8')
        for data in [good[:n] for n in range(1, 7)] + [
                bytes.fromhex('e2 03 d1 00'), bytes.fromhex('e2 00 d1'),
                bytes.fromhex('e2 02 d3'), bytes.fromhex('e2 04 d1 1d 28 d3'),
                bytes.fromhex('e2 06 d2 22 28 00 00 d3')]:
            with self.subTest(data=data):
                self.assertFalse(self.decode(data)['completeCodeDecode'])
        # A .W anchor cannot reinterpret a target-table word as a new instruction.
        self.assertFalse(self.decode(good, [(10, 3)])['completeCodeDecode'])

    def test_function_header_body_call_and_stop_line(self):
        code = bytes.fromhex('fa 00 30 21 28 0b a7 10 28 a4 d8 fb 00 30 e1 6e 05 d3')
        r = self.decode(code, [(10, 0), (20, 11)])
        self.assertTrue(r['completeCodeDecode'], r['error'])
        header = r['instructions'][0]
        self.assertEqual(header['size'], 6)
        self.assertEqual(header['operands']['descriptor'], 0x3000)
        self.assertEqual(header['operands']['targets'], [0x2821, 0x2826])
        self.assertEqual(r['instructions'][4]['control'], 'indirect-call')
        stop = r['instructions'][5]
        self.assertEqual(stop['operands']['value'], 1390)
        self.assertNotIn('target', stop['operands'])

    def test_function_header_truncation_and_bad_body_or_skip(self):
        code = bytes.fromhex('fa 00 30 21 28 08 a4 d8 d3')
        self.assertTrue(self.decode(code)['completeCodeDecode'])
        for bad in [code[:n] for n in range(1, 6)] + [
                bytes.fromhex('fa 00 30 1c 28 08 a4 d8 d3'),
                bytes.fromhex('fa 00 30 21 28 05 a4 d8 d3'), b'\xfb\x00', b'\xa7\x00', b'\xe1\x00']:
            with self.subTest(bad=bad):
                self.assertFalse(self.decode(bad)['completeCodeDecode'])

    def test_get_number_contextual_stores_and_io_scalars(self):
        r = self.decode(bytes.fromhex('db 42 db 41 db 60 ea e7 ae e5 e3 e4 d3'))
        self.assertTrue(r['completeCodeDecode'])
        self.assertEqual([i['size'] for i in r['instructions'][:3]], [2, 2, 1])
        self.assertEqual(r['instructions'][0]['mnemonic'], 'GET_NUMBER_STORE_INTEGER_ELEMENT')

    def test_status_clock_and_load_selectors(self):
        forms = {0x01: 'LOAD_RELOCATED', 0x03: 'LOAD_ABSOLUTE', 0x05: 'STATUS_FAC',
                 0x06: 'TIME_FAC', 0x08: 'TIME_STRING_FAC', 0x0E: 'SET_TIME_STRING'}
        for selector, name in forms.items():
            with self.subTest(selector=selector):
                r = self.decode(bytes([0x80, selector, 0xD3]))
                self.assertTrue(r['completeCodeDecode'])
                self.assertEqual(r['instructions'][0]['size'], 2)
                self.assertEqual(r['instructions'][0]['mnemonic'], name)
        self.assertIn('sign-extended', self.decode(b'\x80\x05')['instructions'][0]['comment'])
        self.assertFalse(self.decode(b'\x80\x07\xd3')['completeCodeDecode'])

    def test_program_controls_and_multiple_sys_calls(self):
        r = self.decode(bytes.fromhex('ca c8 20 e8 8a e8 52 02 e8 d3'))
        self.assertTrue(r['completeCodeDecode'])
        self.assertEqual([i['control'] for i in r['instructions'][:2]], ['restart', 'terminate'])
        self.assertEqual(sum(i['mnemonic'] == 'SYS' for i in r['instructions']), 3)

    def test_petscii_escape(self):
        self.assertEqual(ps.petscii_literal(b'A\x93"\\'), '"A\\x93\\x22\\x5C"')


if __name__ == '__main__':
    unittest.main()
