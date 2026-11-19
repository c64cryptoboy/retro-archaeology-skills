import unittest

from annotate_listing import render, visible_operand, visible_string


class AnnotatedListingTests(unittest.TestCase):
    def test_petscii_controls_are_named_and_grouped(self):
        self.assertEqual(visible_string("\\x93\\x11\\x11A"), '"{CLEAR}{DOWN*2}A"')

    def test_real_bytes_not_ascii_glyphs_or_spurious_escape_sequences(self):
        self.assertEqual(visible_string(b'A\x5e'), '"A{PETSCII_$5E}"')
        self.assertEqual(visible_string(bytes.fromhex('93 11 11 41')), '"{CLEAR}{DOWN*2}A"')
        for kind, raw in [('inline_string_short', 'ec 5c 78 39 33'),
                          ('inline_string_u8', 'e7 04 5c 78 39 33')]:
            with self.subTest(kind=kind):
                self.assertEqual(visible_operand({'operandKind':kind, 'bytes':raw, 'text':r'\x93'}),
                                 '"{PETSCII_$5C}{PETSCII_$78}93"')

    def test_false_skip_renders_numeric_zero_test(self):
        for value in (1, 0):
            with self.subTest(value=value):
                text = render({"instructions": [
                    {"address": 0x2000, "opcode": 0xB0 + value, "bytes": f"b{value}", "size": 1,
                     "mnemonic": "CONST_SMALL", "operandKind": "none", "value": value},
                    {"address": 0x2001, "opcode": 0x1F, "bytes": "1f 03", "size": 2,
                     "mnemonic": "IF_FALSE_SKIP", "operandKind": "skip_u8", "target": 0x2004},
                ], "diagnostics": []}, {})
                self.assertIn(f"\n; IF ({value}) = 0 THEN GOTO loc_2004\n", text)

    def test_on_transfer_consumes_selector_and_preserves_order(self):
        for opcode, verb in ((0x1B, "GOTO"), (0x1C, "GOSUB")):
            with self.subTest(verb=verb):
                text = render({"instructions": [
                    {"address": 0x1FAA, "bytes": "80", "mnemonic": "LOAD_VAR", "variable": "X"},
                    {"address": 0x1FAB, "bytes": f"{opcode:02x} 08 1f b8 1f b4 1f bd",
                     "mnemonic": "ON_" + verb, "targets": [0x1FB8, 0x1FB4, 0x1FBD]},
                ]}, {})
                self.assertIn(f"\n; ON X {verb} loc_1fb8, loc_1fb4, loc_1fbd\n", text)
                self.assertIn("Final linear-pass expression stack depth: 0", text)

    def test_internal_allocation_consumes_bound_without_a_source_dim(self):
        text = render({'instructions': [
            {'address': 0x2000, 'bytes': 'b3', 'mnemonic': 'CONST_SMALL', 'value': 3},
            {'address': 0x2001, 'bytes': '10 01 da aa 00 00', 'mnemonic': 'DIM_INTERNAL',
             'variable': 'Z*%', 'reservedArray': True, 'dimensions': 1},
        ]}, {})
        self.assertIn('; REM allocate reserved integer array Z*%, upper bound 3', text)
        self.assertNotIn('DIM Z*%', text)
        self.assertIn('Final linear-pass expression stack depth: 0', text)

    def test_postfix_expression_is_explained(self):
        disassembly = {
            "instructions": [
                {"address": 0x2000, "opcode": 0xB2, "bytes": "b2", "size": 1,
                 "mnemonic": "CONST_SMALL", "operandKind": "none", "value": 2},
                {"address": 0x2001, "opcode": 0xB3, "bytes": "b3", "size": 1,
                 "mnemonic": "CONST_SMALL", "operandKind": "none", "value": 3},
                {"address": 0x2002, "opcode": 0x07, "bytes": "07", "size": 1,
                 "mnemonic": "ADD", "operandKind": "none"},
                {"address": 0x2003, "opcode": 0xC0, "bytes": "c0", "size": 1,
                 "mnemonic": "STORE_VAR", "operandKind": "none", "variable": "X"},
            ],
            "diagnostics": [],
        }
        text = render(disassembly, {"addresses": {"0x2000": {"label": "entry"}}})
        self.assertIn("\n; X = (2 + 3)\n", text)
        self.assertNotIn("combine top two", text)
        self.assertIn("X := (2 + 3)", text)
        self.assertIn("Final linear-pass expression stack depth: 0", text)


if __name__ == "__main__":
    unittest.main()
