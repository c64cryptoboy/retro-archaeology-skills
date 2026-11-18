"""Synthetic compatibility regressions; no native runtime or private fixtures."""

from fractions import Fraction
import random
import re
import unittest
from unittest.mock import patch

from decompy_compat.basic_v2 import BasicLine, detokenize, read_program, tokenize, write_program
from decompy_compat.petspeed_core import DataItem, Image, decompile, decompile_with_evidence
from decompy_compat.speedcode import (
    _HANDLERS, decode, decode_with_evidence, float_literal, instructions,
    string_literal,
)


def synthetic_image(code: bytes) -> Image:
    """An artificial data image with dispatch words, not native handlers."""
    start = 0x2821
    data = bytearray(start - 0x0801 + 2 + len(code))
    for op, handler in _HANDLERS.items():
        offset = 0x0826 + 2 * (op - 0x80) - 0x0801 + 2
        data[offset:offset + 2] = handler.to_bytes(2, "little")
    # One numeric scalar, and an empty DATA region with a footer byte.
    data[0x2806 - 0x0801 + 2] = 0x96
    data[start - 0x0801 + 2:] = code
    return Image(0x0801, (0x2810, 0x2811, 0x2811, start - 1, start + len(code)), bytes(data))


def literal_value(expression: str) -> bytes:
    """Independent parser for just quoted bytes and CHR$(integer) joins."""
    parts = re.findall(r'"[^\"]*"|CHR\$\([0-9]+\)', expression)
    if "+".join(parts) != expression:
        raise AssertionError("unexpected string expression")
    return b"".join(part[1:-1].encode("latin-1") if part.startswith('"')
                    else bytes([int(part[5:-1])]) for part in parts)


class LiteralTests(unittest.TestCase):
    def test_embedded_nul_does_not_end_basic_line(self):
        value = b'A\0"B\0'
        expression = string_literal(value)
        self.assertEqual(literal_value(expression), value)
        line = BasicLine(10, tokenize("PRINT " + expression))
        self.assertNotIn(b"\0", line.body)
        self.assertEqual(read_program(write_program([line])), [line])
        # The upstream spelling embedded NUL directly; the writer refused it.
        broken = '+CHR$(34)+'.join('"' + part + '"'
                                  for part in value.decode("latin-1").split('"'))
        with self.assertRaisesRegex(ValueError, "outside PETSCII"):
            tokenize("PRINT " + broken)

    def test_every_literal_byte_and_mixed_quotes_controls(self):
        for value in [bytes([i]) for i in range(256)] + [b'', b'"\0\r\n\x93A"\xff']:
            with self.subTest(value=value):
                expression = string_literal(value)
                self.assertEqual(literal_value(expression), value)
                self.assertEqual(detokenize(tokenize(expression)), expression)

    def test_ordinary_literals_keep_upstream_spelling(self):
        self.assertEqual(string_literal(b"ABC"), '"ABC"')
        self.assertEqual(string_literal(b'A"B'), '"A"+CHR$(34)+"B"')

    def test_float_retains_low_significand_bit(self):
        # Artificial normalized 1 + 2**-31; .10g wrongly renders it as 1.
        data = bytes([129, 0, 0, 0, 1, 0])
        exact = Fraction(1) + Fraction(1, 2**31)
        old = format(float(exact), ".10g")
        self.assertEqual(old, "1")
        self.assertGreater(abs(Fraction(old) - exact), Fraction(1, 2**32))
        self.assertLess(abs(Fraction(float_literal(data)) - exact), Fraction(1, 2**32))

    def test_float_model_across_exponents_signs_and_mantissas(self):
        rng = random.Random(2267)
        for exponent in (1, 32, 64, 128, 129, 160, 200, 255):
            for mantissa in (0, 1, 2**31 - 1, *(rng.randrange(2**31) for _ in range(20))):
                for sign in (0, 128):
                    data = bytes([exponent]) + mantissa.to_bytes(4, "big") + bytes([sign])
                    ulp = Fraction(2) ** (exponent - 160)
                    exact = ((2**31 + mantissa) * ulp) * (-1 if sign else 1)
                    self.assertLess(abs(Fraction(float_literal(data)) - exact), ulp / 2)
        self.assertEqual(float_literal(bytes(6)), "0")
        self.assertEqual(float_literal(bytes([129, 0, 0, 0, 0, 0])), "1")


class BranchEvidenceTests(unittest.TestCase):
    def test_label_like_literal_is_never_replaced(self):
        image = synthetic_image(b'\x46\x05@282D\xcf\xec\xd1\x2d\x28\xd3\xd3')
        result = decode_with_evidence(image)
        self.assertEqual([detokenize(line.body) for line in result.lines],
                         ['PRINT "@282D"', "GOTO 30", "END"])
        self.assertEqual(decode(image), result.lines)
        self.assertEqual([item.emission_address for item in result.statements],
                         [0x2828, 0x282A, 0x282D])
        self.assertEqual(result.statements[1].branch_targets, (0x282D,))
        self.assertEqual(result.statements[0].branch_targets, ())
        target, = result.targets
        self.assertEqual((target.address, target.line_number, target.emission_address),
                         (0x282D, 30, 0x282D))
        self.assertEqual(target.policy, "next-emission")

    def test_on_targets_are_structured_and_duplicates_preserved(self):
        image = synthetic_image(b'\x8a\xe2\x06\xd1\x29\x28\x29\x28\xd3\xd3')
        result = decode_with_evidence(image)
        self.assertEqual(detokenize(result.lines[0].body), "ON 1 GOTO 20,20")
        self.assertEqual(result.statements[0].branch_targets, (0x2829, 0x2829))
        self.assertEqual(len(result.targets), 1)

    def test_mapping_reports_legacy_redirection_not_fake_entry(self):
        # Target is an instruction start, but assignment emits two bytes later.
        image = synthetic_image(b'\xd1\x24\x28\x52\x07\x60\xd3\xd3')
        result = decode_with_evidence(image)
        target, = result.targets
        self.assertEqual((target.address, target.emission_address), (0x2824, 0x2826))
        self.assertEqual(target.policy, "next-emission")

    def test_branch_into_operand_still_refuses(self):
        image = synthetic_image(b'\xd1\x22\x28\xd3\xd3')
        with self.assertRaisesRegex(ValueError, "branch into operand"):
            decode(image)

    def test_arithmetic_order_preserved(self):
        for op, expression in ((0x81, "(9-2)"), (0x84, "(9/2)"),
                               (0x88, "(2-9)"), (0x89, "(2/9)")):
            image = synthetic_image(bytes([0x52, 2, 0x55, 9, op, 0x60, 0xD3, 0xD3]))
            self.assertEqual(detokenize(decode(image)[0].body), "A0=" + expression)

    def test_generated_data_evidence_and_compatibility_api(self):
        image = synthetic_image(b'\xd3\xd3')
        with patch("decompy_compat.petspeed_core.read_image", return_value=image), \
             patch.object(Image, "data_items", return_value=[DataItem("7", 1, b"")]):
            result = decompile_with_evidence(b"synthetic")
            self.assertEqual(decompile(b"synthetic"), result.lines)
        self.assertEqual(result.statements[-1].generated, "DATA")
        self.assertIsNone(result.statements[-1].emission_address)
        self.assertEqual(result.statements[-1].line, result.lines[-1])
        self.assertEqual(read_program(write_program(result.lines)), result.lines)

    def test_unknown_handler_and_truncation_still_refuse(self):
        image = synthetic_image(b'\xd1\x21\x28\xd3\xd3')
        data = bytearray(image.data)
        data[image.offset(0x0826 + 2 * (0xD1 - 0x80))] ^= 1
        changed = Image(image.load, image.sections, bytes(data))
        with self.assertRaisesRegex(ValueError, "unknown handler"):
            instructions(changed)
        with self.assertRaisesRegex(ValueError, "truncated instruction"):
            instructions(synthetic_image(b'\xd1\x21'))


if __name__ == "__main__":
    unittest.main()
