"""Title-free control-entry regressions for the accepted compact backend."""

import unittest

from decompy_compat.basic_v2 import detokenize, read_program, write_program
from decompy_compat.speedcode import decode_with_evidence
from test_decompy_compat import synthetic_image


START = 0x2821


def literal(value):
    return bytes([0x46, len(value)]) + value


def edge(kind, address, target):
    word = target.to_bytes(2, "little")
    if kind == "IF":
        # LOAD_ONE_FAC, then a relative false branch from its opcode address.
        return bytes([0x8a, 0xd4, target - (address + 1) - 1])
    if kind.startswith("ON "):
        op = 0xd1 if kind == "ON GOTO" else 0xd2
        return b"\x8a\xe2\x04" + bytes([op]) + word
    return bytes([0xd1 if kind == "GOTO" else 0xd2]) + word


class PrintEntryTests(unittest.TestCase):
    def decode(self, code):
        result = decode_with_evidence(synthetic_image(code + b"\xd3\xd3"))
        self.assertEqual(read_program(write_program(result.lines)), result.lines)
        return result, [detokenize(line.body) for line in result.lines]

    def test_forward_entry_keeps_second_label(self):
        # A jump skips the first item, not both items of a merged PRINT.
        first = literal(b"ONE") + b"\xd0"
        target = START + 3 + len(first)
        result, text = self.decode(edge("GOTO", START, target)
                                   + first + literal(b"TWO") + b"\xd0\xec")
        self.assertEqual(text, ['GOTO 30', 'PRINT "ONE";', 'PRINT "TWO"', 'END'])
        entry, = result.targets
        self.assertEqual((entry.address, entry.line_number, entry.emission_address),
                         (target, 30, target + len(literal(b"TWO"))))
        self.assertEqual(result.statements[0].branch_targets, (target,))

    def test_backward_and_on_entries_are_known_before_print_merging(self):
        first = literal(b"ONE") + b"\xd0"
        second = literal(b"TWO") + b"\xd0\xec"
        target = START + len(first)
        for kind in ("GOTO", "GOSUB", "ON GOTO", "ON GOSUB"):
            with self.subTest(kind=kind):
                result, text = self.decode(first + second
                    + edge(kind, START + len(first + second), target))
                self.assertEqual(text[:2], ['PRINT "ONE";', 'PRINT "TWO"'])
                self.assertTrue(text[2].endswith("20"), text)
                self.assertEqual(result.targets[0].address, target)
                self.assertEqual(result.targets[0].line_number, 20)

    def test_forward_conditional_and_on_entries_split(self):
        first = literal(b"ONE") + b"\xd0"
        for kind, size in (("IF", 3), ("GOSUB", 3), ("ON GOTO", 6), ("ON GOSUB", 6)):
            with self.subTest(kind=kind):
                target = START + size + len(first)
                _, text = self.decode(edge(kind, START, target)
                                     + first + literal(b"TWO") + b"\xd0\xec")
                self.assertEqual(text[1:3], ['PRINT "ONE";', 'PRINT "TWO"'])
                self.assertTrue(text[0].endswith("30"), text)

    def test_ordinary_non_target_items_still_group(self):
        _, text = self.decode(literal(b"ONE") + b"\xd0"
                             + literal(b"TWO") + b"\xd0\xec")
        self.assertEqual(text, ['PRINT "ONE";"TWO"', 'END'])

    def test_newline_target_does_not_repeat_prior_item(self):
        item = literal(b"ONE") + b"\xd0"
        target = START + 3 + len(item)
        _, text = self.decode(edge("GOTO", START, target) + item + b"\xec")
        self.assertEqual(text, ['GOTO 30', 'PRINT "ONE";', 'PRINT', 'END'])

    def test_entry_inside_first_or_later_print_expression_refuses(self):
        for prior in (b"", literal(b"ONE") + b"\xd0"):
            for backward in (False, True):
                with self.subTest(prior=prior, backward=backward):
                    prefix_size = 0 if backward else 3
                    # Entry at CHR$ bypasses its numeric argument producer.
                    target = START + prefix_size + len(prior) + 2
                    body = prior + b"\x52\x41\xc7\xd0\xec"
                    code = (body + edge("GOTO", START + len(body), target) if backward
                            else edge("GOTO", START, target) + body)
                    with self.assertRaisesRegex(ValueError, "unresolved PRINT expression.*\\$[0-9A-F]{4}"):
                        self.decode(code)

    def test_print_consumer_entry_refuses_inherited_fac(self):
        target = START + 3 + len(literal(b"ONE"))
        with self.assertRaisesRegex(ValueError, "unresolved PRINT expression"):
            self.decode(edge("GOTO", START, target) + literal(b"ONE") + b"\xd0\xec")

    def test_reloading_fac_does_not_prove_inherited_arg_or_stack(self):
        # The entered literal replaces FAC, but the addition still needs ARG.
        for before, after in ((b"\x55\x02", b"\x52\x03\x82"),
                              (b"\x52\x02\xf5", b"\x52\x03\xf7\x82"),
                              (b"\x52\x02\xf5", b"\xf6")):
            with self.subTest(before=before, after=after):
                target = START + 3 + len(before)
                with self.assertRaisesRegex(ValueError, "unresolved PRINT expression"):
                    self.decode(edge("GOTO", START, target) + before + after + b"\xcf\xec")

    def test_self_contained_expression_at_entry_can_print(self):
        target = START + 3 + len(literal(b"ONE") + b"\xd0")
        _, text = self.decode(edge("GOTO", START, target) + literal(b"ONE") + b"\xd0"
                             + b"\x55\x02\x52\x03\x82\xcf\xec")
        self.assertEqual(text, ['GOTO 30', 'PRINT "ONE";', 'PRINT (2+3)', 'END'])


if __name__ == "__main__":
    unittest.main()
