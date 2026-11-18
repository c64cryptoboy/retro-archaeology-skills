import unittest

from annotate_listing import render, visible_string


class AnnotatedListingTests(unittest.TestCase):
    def test_petscii_controls_are_named_and_grouped(self):
        self.assertEqual(visible_string("\\x93\\x11\\x11A"), '"{CLEAR}{DOWN*2}A"')

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
