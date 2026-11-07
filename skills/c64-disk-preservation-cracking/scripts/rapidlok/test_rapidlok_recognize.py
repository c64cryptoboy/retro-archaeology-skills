"""Independent hand-derived fixtures; no encoder or commercial bytes."""
import unittest

from rapidlok_recognize import (
    RecognitionError, SOURCE_V1_HINT, SOURCE_V2_HINT, decode_header,
    inspect_record, read_bits, source_integrity_probe,
)

# Hand bit placement: 48 90 D8 -> A5 3C; 45 10 00 -> 99 00.
# A5 XOR 3C XOR 99 = 00.  This checks the projection, not drive legality.
HEADER = bytes.fromhex('75 48 90 d8 45 10 00')
# 92 49 24 is 100100100100100100100100.  Starting at its bit 1,
# with the next byte's top bit 1, yields four 001001 symbols (09).
# 193 triples give 772 symbols.  FF supplies the final bit and makes
# XOR(193 * (92 XOR 49 XOR 24), FF) = FF XOR FF = 00.
# Tail A4 A4 selects zero in all eight source parity bit positions.
RECORD = b'\x6b' + bytes.fromhex('92 49 24') * 193 + bytes.fromhex('ff a4 a4')
TRACK = bytes.fromhex('00 ff ff ff ff') + HEADER + b'\x55' * 8 + b'\xff' * 5 + RECORD + b'\x55' * 3
MARKER = 25 * 8


class RecognitionTests(unittest.TestCase):
    def test_header_hand_vector(self):
        self.assertEqual(decode_header(HEADER)['decoded_hex'], 'a53c9900')

    def test_header_corrupt_data_bit_rejected(self):
        changed = bytearray(HEADER)
        changed[1] ^= 0x40
        with self.assertRaisesRegex(RecognitionError, 'XOR integrity mismatch'):
            decode_header(bytes(changed))

    def test_header_wrong_marker_and_truncation(self):
        for bad in (HEADER[:-1], b'\x6b' + HEADER[1:]):
            with self.assertRaises(RecognitionError):
                decode_header(bad)

    def test_integrity_hand_basis_vectors(self):
        # b, a, expected parity: explicit one-hot source parity positions.
        for b, a, expected in ((0, 1, 1), (0, 2, 2), (0, 8, 4), (0, 16, 8),
                               (1, 0, 16), (2, 0, 32), (8, 0, 64), (16, 0, 128)):
            with self.subTest(b=b, a=a):
                record = b'\x6b' + bytes([expected]) + bytes(579) + bytes([b, a])
                check = source_integrity_probe(record)['v1_encoded_integrity']
                self.assertEqual(check, {'xor': expected, 'tail_parity': expected, 'matches': True})

    def test_integrity_mismatch_is_explicit_not_payload_success(self):
        changed = bytearray(RECORD)
        changed[1] ^= 1
        check = source_integrity_probe(bytes(changed))
        self.assertFalse(check['v1_encoded_integrity']['matches'])
        self.assertEqual(check['payload_recovery'], 'refused')

    def test_recognized_shape_is_not_variant_proof(self):
        result = inspect_record(TRACK, MARKER)
        self.assertEqual(result['status'], 'recognition-only')
        self.assertEqual(result['field']['distinct_symbols'], [9])
        self.assertEqual(result['field']['start_bit'], 209)
        self.assertEqual(result['field']['end_bit_exclusive'], 4841)
        self.assertEqual(result['candidate_end_bit_exclusive'], 4864)
        self.assertEqual(result['header']['decoded_hex'], 'a53c9900')
        self.assertTrue(result['v1_encoded_integrity']['matches'])
        self.assertFalse(result['variant_established'])
        self.assertEqual(result['payload_recovery'], 'refused')

    def test_corrupt_symbol_rejected(self):
        changed = bytearray(TRACK)
        changed[26] &= 0x80  # First six-bit symbol becomes 000000.
        with self.assertRaisesRegex(RecognitionError, 'corrupt-symbol: index 0'):
            inspect_record(bytes(changed), MARKER)

    def test_truncated_record_rejected(self):
        with self.assertRaisesRegex(RecognitionError, 'truncated'):
            inspect_record(TRACK[:25 + 582], MARKER)
        with self.assertRaisesRegex(RecognitionError, 'exactly 583'):
            source_integrity_probe(RECORD[:-1])

    def test_wrong_variant_rejected_both_directions(self):
        with self.assertRaisesRegex(RecognitionError, 'wrong-variant'):
            inspect_record(TRACK, MARKER, require_source_hint=SOURCE_V2_HINT)
        changed = bytearray(RECORD)
        changed[196] = 0xA4
        with self.assertRaisesRegex(RecognitionError, 'wrong-variant'):
            source_integrity_probe(bytes(changed), require_source_hint=SOURCE_V1_HINT)
        result = source_integrity_probe(bytes(changed), require_source_hint=SOURCE_V2_HINT)
        self.assertFalse(result['variant_established'])
        self.assertTrue(result['v2_7_integrity'].startswith('not-evaluated:'))

    def test_v2_discriminator_cannot_pass_observed_layout(self):
        # Byte 196 A4 fixes symbol 260 to 010010 (12), outside the
        # observed alphabet.  A diagnostic source hint is not admission.
        changed = bytearray(TRACK)
        changed[25 + 196] = 0xA4
        self.assertEqual(read_bits(bytes(changed), MARKER + 9 + 260 * 6, 6), 0x12)
        with self.assertRaisesRegex(RecognitionError, 'corrupt-symbol: index 260'):
            inspect_record(bytes(changed), MARKER, require_source_hint=SOURCE_V2_HINT)

    def test_marker_sync_and_header_refusals(self):
        for index, value in ((25, 0x6A), (24, 0), (5, 0)):
            with self.subTest(index=index), self.assertRaises(RecognitionError):
                changed = bytearray(TRACK)
                changed[index] = value
                inspect_record(bytes(changed), MARKER)

    def test_bit_orientation_and_wrap(self):
        self.assertEqual(read_bits(b'\x96\x3a', 0, 8), 0x96)
        self.assertEqual(read_bits(b'\x96\x3a', 4, 8), 0x63)
        self.assertEqual(read_bits(b'\x96\x3a', 12, 8, circular=True), 0xA9)
        with self.assertRaisesRegex(RecognitionError, 'truncated'):
            read_bits(b'\x96\x3a', 12, 8)
        with self.assertRaisesRegex(RecognitionError, 'truncated'):
            read_bits(b'\x96', 0, 9, circular=True)

    def test_unaligned_record_and_circular_track(self):
        bits = '000' + ''.join(f'{b:08b}' for b in TRACK) + '00000'
        shifted = int(bits, 2).to_bytes(len(bits) // 8, 'big')
        self.assertEqual(inspect_record(shifted, MARKER + 3)['field']['distinct_symbols'], [9])
        rotation = 100
        rotated = TRACK[rotation:] + TRACK[:rotation]
        marker = (MARKER - rotation * 8) % (len(TRACK) * 8)
        result = inspect_record(rotated, marker, circular=True)
        self.assertTrue(result['crosses_track_end'])
        self.assertEqual(result['header']['decoded_hex'], 'a53c9900')
        with self.assertRaisesRegex(RecognitionError, 'truncated'):
            inspect_record(rotated, marker)

    def test_checksum_collision_does_not_admit_payload(self):
        changed = bytearray(RECORD)
        changed[10] ^= 1
        changed[11] ^= 1
        result = source_integrity_probe(bytes(changed))
        self.assertTrue(result['v1_encoded_integrity']['matches'])
        self.assertFalse(result['variant_established'])
        self.assertEqual(result['payload_recovery'], 'refused')


if __name__ == '__main__':
    unittest.main(verbosity=2)
