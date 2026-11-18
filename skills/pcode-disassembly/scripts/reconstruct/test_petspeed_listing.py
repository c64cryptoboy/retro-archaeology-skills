"""Public frontend contracts; no compiler, executable runtime, or external corpus."""
from types import SimpleNamespace
import unittest

from petspeed_listing import backend, build, check_effect_counts, check_target_entries, display, retained_data, serialize
from reading_projection import render_reading


class NumberedReadingTests(unittest.TestCase):
    def test_wrong_runtime_or_partial_never_calls_translator(self):
        for report in ({}, {'completeCodeDecode': True, 'runtimeSha256': 'wrong'}):
            with self.assertRaisesRegex(ValueError, 'exact supported runtime'):
                build(b'', report)

    def test_dropped_and_repeated_effects_refuse(self):
        for op in (0xbb, 0xc2, 0xb8):
            rows = [{'opcode': op}]
            check_effect_counts(rows, [SimpleNamespace(body=bytes([op]))])
            for body in (b'', bytes([op, op])):
                with self.assertRaisesRegex(ValueError, 'call count'):
                    check_effect_counts(rows, [SimpleNamespace(body=body)])

    def test_keyword_bytes_in_quote_data_rem_are_not_calls(self):
        body = b'"\xbb":\x83"a:b",\xbb:\xbb:\x8f\xbb'
        check_effect_counts([{'opcode': 0xbb}], [SimpleNamespace(body=body)])

    def test_display_not_used_for_token_export(self):
        text = display('"\x93"')
        self.assertEqual(text, '"{0x93}"')
        view = {'schema': 'petspeed-numbered-reading-v1', 'lines': [
            {'number': 10, 'text': 'PRINT' + text, 'tokenHex': '99229322'}]}
        report = {'readingView': view}
        self.assertEqual(render_reading(report), '10 PRINT"{0x93}"\n')
        self.assertEqual(serialize(report), bytes.fromhex('01080a080a0099229322000000'))

    def test_data_evidence_keeps_address_suffix_and_opaque_footer(self):
        image = backend('petspeed_core').Image(0x4000, (0x4000, 0x4006, 0, 0, 0),
                                               bytes.fromhex('0040 01 41 41 37 07 9c'))
        data = retained_data(image)
        self.assertEqual(data['records'], [dict(address=0x4000, tag=1, textHex='41', numericHex=''),
                                           dict(address=0x4002, tag=65, textHex='37', numericHex='07')])
        self.assertEqual(data['footer'], dict(address=0x4005, byte=0x9c))

    def test_transfer_into_scalar_store_refuses_guessed_reaching_value(self):
        target = SimpleNamespace(address=0x28D0)
        for op in (0x60, 0x7f, 0xff):
            rows = [{'address': target.address, 'opcode': op}]
            with self.assertRaisesRegex(ValueError, 'incoming value'):
                check_target_entries(rows, [target])
            check_target_entries(rows, [])  # ordinary stores need no target refusal
        with self.assertRaisesRegex(ValueError, 'boundaries'):
            check_target_entries([], [target])

    def test_reading_refusal_is_explained(self):
        for function in (serialize, render_reading):
            with self.assertRaisesRegex(ValueError, 'compact only'):
                function({'readingRefusal': 'compact only'})


if __name__ == '__main__':
    unittest.main()
