"""Generic constructed DATA records only; no compiler or private inputs."""
import unittest

from petspeed_data import RUNTIME_SHA256, decode_data_region


def decode(raw, address=0x4000):
    return decode_data_region(raw, address, runtime_sha256=RUNTIME_SHA256)


def record(text, extra=b''):
    return bytes([len(text) + 0x40 * len(extra)]) + text + extra


class PetspeedDataTests(unittest.TestCase):
    def test_retained_text_and_original_numeric_suffix(self):
        raw = record(b'+09', b'\x09') + record(b'-257', b'\xff\xfe') + record(b'.25') + b'\x19'
        result = decode(raw)
        self.assertEqual(result['status'], 'complete')
        rows = result['records']
        self.assertEqual([r['text'] for r in rows], ['DATA +09', 'DATA -257', 'DATA .25'])
        self.assertEqual([r['numericBytes'] for r in rows], ['09', 'fffe', ''])
        self.assertEqual([r['numericValue'] for r in rows], [9, -257, None])
        self.assertEqual([r['numericEncoding'] for r in rows], ['unsigned-u8', 'signed-le16', None])
        self.assertEqual(b''.join(bytes.fromhex(r['bytes']) for r in rows) + bytes.fromhex(result['footer']['bytes']), raw)

    def test_empty_and_delimiters(self):
        fields = [b'', b'A,B', b'C:D', b' X ', b'PRINT:GOTO 5']
        rows = decode(b''.join(record(x) for x in fields) + b'\x00')['records']
        self.assertEqual([r['text'] for r in rows], ['DATA ""', 'DATA "A,B"', 'DATA "C:D"', 'DATA " X "', 'DATA "PRINT:GOTO 5"'])
        self.assertEqual(rows[0]['size'], 1)

    def test_high_petscii_and_control_bytes_are_not_source(self):
        payload = b'\x00\x0d\x80\xff\\'
        result = decode(record(payload) + record(b'OK') + b'\xff')
        self.assertEqual(result['status'], 'partial-known-length')
        self.assertTrue(result['completeDataDecode'])
        self.assertEqual(result['unsupportedPresentationCount'], 1)
        row = result['records'][0]
        self.assertEqual(row['textHex'], payload.hex())
        self.assertEqual(row['rawTextLatin1'].encode('latin-1'), payload)
        self.assertEqual(row['textDisplay'], r'\x00\x0D\x80\xFF\x5C')
        self.assertIsNone(row['text'])
        self.assertEqual(result['records'][1]['text'], 'DATA "OK"')

    def test_quotes_are_known_length_not_guessed(self):
        for payload in [b'"', b'"XY"', b'A"B', b'":PRINT 1:DATA"']:
            with self.subTest(payload=payload):
                result = decode(record(payload) + b'\x0d')
                self.assertEqual(result['status'], 'partial-known-length')
                self.assertTrue(result['completeDataDecode'])
                self.assertIsNone(result['records'][0]['text'])

    def test_mismatched_numeric_spelling_is_not_source(self):
        for text, extra in [(b'2', b'\x03'), (b'', b'\x00'), (b'HELLO', b'\x09'),
                            (b'32768', b'\x00\x80'), (b'1E9999999999999999999999999', b'\x01')]:
            with self.subTest(text=text):
                result = decode(record(text, extra) + b'\x0d')
                self.assertEqual(result['status'], 'partial-known-length')
                self.assertTrue(result['completeDataDecode'])
                self.assertIsNone(result['records'][0]['text'])

    def test_all_supported_lengths_are_bounded(self):
        for tag in range(0xC0):
            with self.subTest(tag=tag):
                size = 1 + (tag & 63) + (tag >> 6)
                raw = bytes([tag]) + b'X' * (tag & 63) + bytes(tag >> 6) + b'\xc7'
                result = decode(raw)
                self.assertTrue(result['completeDataDecode'])
                self.assertEqual(result['records'][0]['size'], size)
                self.assertEqual(result['footer']['address'], 0x4000 + size)
                self.assertEqual(result['footer']['bytes'], 'c7')

    def test_every_truncation_does_not_consume_footer(self):
        for extra in [b'', b'\x01', b'\xff\xff']:
            full = record(b'12345', extra)
            for cut in range(1, len(full)):
                with self.subTest(extra=extra, cut=cut):
                    result = decode(full[:cut] + b'\xff')
                    self.assertFalse(result['completeDataDecode'])
                    self.assertEqual(result['status'], 'structural-refusal')
                    self.assertEqual(result['error']['expectedSize'], len(full))
                    self.assertTrue(result['error']['lengthKnown'])
                    self.assertEqual(result['records'], [])
                    self.assertEqual(result['footer']['bytes'], 'ff')

    def test_unsupported_tags_withhold_even_valid_prefix_source(self):
        prefix = record(b'GOOD')
        for tag in range(0xC0, 0x100):
            with self.subTest(tag=tag):
                result = decode(prefix + bytes([tag]) + b'\x0d')
                self.assertEqual(result['status'], 'structural-refusal')
                self.assertFalse(result['error']['lengthKnown'])
                self.assertEqual(result['error']['address'], 0x4000 + len(prefix))
                self.assertEqual(result['undecodedTail']['bytes'], bytes([tag]).hex())
                self.assertIsNone(result['records'][0]['text'])
                self.assertEqual(result['records'][0]['kind'], 'opaque')

    def test_truncation_withholds_prefix_source(self):
        result = decode(record(b'GOOD') + b'\x43X\x0d')
        self.assertEqual(result['status'], 'structural-refusal')
        self.assertTrue(result['error']['lengthKnown'])
        self.assertIsNone(result['records'][0]['text'])

    def test_footer_is_opaque_for_every_value(self):
        for footer in range(256):
            with self.subTest(footer=footer):
                result = decode(bytes([footer]))
                self.assertEqual(result['status'], 'complete')
                self.assertEqual(result['records'], [])
                self.assertEqual(result['footer']['bytes'], f'{footer:02x}')
                self.assertIsNone(result['footer']['text'])

    def test_empty_region_refuses_missing_footer(self):
        result = decode(b'')
        self.assertEqual(result['status'], 'structural-refusal')
        self.assertIsNone(result['footer'])

    def test_identity_and_address_gates(self):
        for identity in ['', '0' * 64]:
            with self.subTest(identity=identity), self.assertRaisesRegex(ValueError, 'fingerprint'):
                decode_data_region(b'\x0d', 0x4000, runtime_sha256=identity)
        for address, raw in [(-1, b'\x00'), (65536, b'\x00'), (65535, b'\x00\x00')]:
            with self.subTest(address=address), self.assertRaisesRegex(ValueError, 'extent'):
                decode(raw, address)
        self.assertEqual(decode(b'\x00', 65535)['end'], 65536)


if __name__ == '__main__':
    unittest.main()
