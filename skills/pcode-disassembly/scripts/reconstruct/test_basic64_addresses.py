"""Authored BASIC-64 byte fragments, decoded but never executed."""
import unittest
from formats import module, profile
from symbolic import lift


def groups(hex_string):
    raw = bytes.fromhex(hex_string)
    decoder, p = module('basic64'), profile('basic64')
    rows = []
    pc = 0
    while pc < len(raw):
        row = decoder.decode_one(raw, 0, pc, len(raw), p)
        rows.append(row)
        pc += row['size']
    result = lift('basic64', {'instructions': rows})['groups']
    assert [row for group in result for row in group['instructions']] == rows
    return result


class AddressTests(unittest.TestCase):
    def test_literal_word_in_address_position(self):
        for code, expected in [('1f 00 c0 96', 'SYS 49152'), ('1f 00 c0 67', 'T_0003 = PEEK(49152)'),
                               ('1f 00 c0 1a 1e 09 91', 'POKE 49152, 9'),
                               ('1f 00 c0 1a 1e 01 1a 1e 02 97', 'WAIT 49152, 1, 2')]:
            with self.subTest(code=code):
                self.assertEqual(groups(code)[0]['text'], expected)

    def test_signed_nonaddress_and_unknown_address_are_unchanged(self):
        self.assertEqual(groups('1f ff ff a7 02')[0]['text'], 'V_0302 = -1')
        self.assertEqual(groups('1f 00 00 1a 1f ff ff 91')[0]['text'], 'POKE 0, -1')
        self.assertEqual(groups('96')[0]['text'], 'SYS <?>')

    def test_derived_address_is_not_folded(self):
        from test_reconstruct import program, row, texts
        result = program('basic64', row('CONST_WORD_INTEGER_ARG', 5), row('CONST_WORD_INTEGER', 65535),
                         row('INTEGER_SUBTRACT'), row('SYS'))
        self.assertEqual(texts(result), 'SYS (5 - -1)')

    def test_handler_install_is_not_a_jump_and_zero_disables(self):
        installed, disabled = groups('9f 23 81 9f 00 00')
        self.assertEqual((installed['text'], installed['kind']), ('REM set runtime error target $8123', 'structural'))
        self.assertEqual((disabled['text'], disabled['kind']), ('REM disable custom error target', 'structural'))
