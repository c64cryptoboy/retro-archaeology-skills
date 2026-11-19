"""Generated identifiers must survive tokenization next to BASIC word operators."""
import unittest

from decompy_compat.basic_v2 import detokenize, tokenize, write_program
from decompy_compat.petspeed_core import Image
from decompy_compat.speedcode import decode


def expression_image(slot, operator, tag=0x96):
    # Allocate names by first use, as the translator normally does.  Last ARG
    # load selects the named left operand; FAC gets literal 1, then store in A0.
    code = bytes(range(slot + 1)) + bytes((0x52, 1, operator, 0x60, 0xd3, 0xd3))
    base, start = 0x0801, 0x2910
    data = bytearray(start - base + 2 + len(code))
    for index in range(slot + 1):
        data[0x2806 + 8 * index - base + 2] = tag if index == slot else 0x96
    # Artificial dispatch words only; no executable runtime or image admission.
    for op, addr in ((0x8d, 0x11a5), (0x8f, 0x11bd), (0xd3, 0x236a)):
        offset = 0x0826 + 2 * (op - 0x80) - base + 2
        data[offset:offset + 2] = addr.to_bytes(2, 'little')
    data[start - base + 2:] = code
    return Image(base, (0x2900, 0x2901, 0x2901, start - 1, start + len(code)), bytes(data))


class KeywordJoinTests(unittest.TestCase):
    def test_equal_text_is_not_a_token_oracle(self):
        intended = b'AF\xb01'  # AF, OR, 1
        mistaken = b'A\x811'   # A, FOR, 1
        self.assertEqual(detokenize(intended), 'AFOR1')
        self.assertEqual(detokenize(mistaken), 'AFOR1')
        self.assertEqual(tokenize(detokenize(mistaken)), mistaken)

    def test_saved_word_operator(self):
        # Expected token bytes, not expected detokenized spellings.  Spaces
        # are significant here: existing unambiguous exports should not change.
        for slot, op, tag, middle in (
            (15, 0x8f, 0x96, b'AF \xb0 1'),  # F + OR otherwise becomes FOR
            (16, 0x8f, 0x96, b'AG \xb0 1'),  # G + O otherwise becomes GO
            (29, 0x8f, 0x96, b'AT \xb0 1'),  # T + O otherwise becomes TO
            (29, 0x8d, 0x96, b'AT \xaf 1'),  # T + AN otherwise becomes TAN
            (15, 0x8f, 0x05, b'AF%\xb01'),   # type suffix separates the tokens
            (2, 0x8d, 0x96, b'A2\xaf1'),     # a safe numeric-tail alias
        ):
            with self.subTest(slot=slot, op=op, tag=tag):
                prg = write_program(decode(expression_image(slot, op, tag)))
                body = b'A0\xb2(' + middle + b')'
                next_record = 0x0801 + 5 + len(body)
                expected = (b'\x01\x08' + next_record.to_bytes(2, 'little') + b'\x0a\0' + body + b'\0'
                            + (next_record + 6).to_bytes(2, 'little') + b'\x14\0\x80\0\0\0')
                self.assertEqual(prg, expected)


if __name__ == '__main__':
    unittest.main()
