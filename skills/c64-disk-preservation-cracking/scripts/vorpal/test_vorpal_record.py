"""Portable synthetic tests only.  No commercial bytes or private file reads."""
import unittest

from vorpal_record import PROFILE, RECORD_BITS, RecordError, decode_record

# These are hand-transcribed wire vectors, not candidate-encoder output.
MARKER = '0111111110101010'  # 7F AA.
ZERO_BYTE = '0100101001'    # 09,09 -> 00.
ID_ZERO = '010010010'       # Kept positions 0,2,3,5,6,8 are all zero.
ZERO = MARKER + ZERO_BYTE * 129 + ID_ZERO
# 01 23 45 67 89 AB CD EF XOR to 00; 5A then makes XOR=5A.
MIXED_PAIRS = (
    '0100101010' '0101101101' '0111001111' '1001010011'
    '1010110110' '1011111001' '1101011011' '1110111110'
    '0110010111'  # Alternate 0C -> nibble 5, 17 -> nibble A.
)
MIXED = MARKER + MIXED_PAIRS + ZERO_BYTE * 119 + '0110010111' + '010010011'
MIXED_PAYLOAD = bytes.fromhex('0123456789abcdef5a') + bytes(119)


def pack(bits):
    """MSB-first transport packing only, independent of any format table."""
    padded = bits + '0' * (-len(bits) % 8)
    return bytes(int(padded[i:i+8], 2) for i in range(0, len(padded), 8))


def changed(bits, start, width, replacement):
    assert len(replacement) == width
    return bits[:start] + replacement + bits[start+width:]


def decode(bits, marker_bit=0):
    return decode_record(pack(bits), profile=PROFILE, marker_bit=marker_bit, bit_length=len(bits))


class SyntheticTests(unittest.TestCase):
    def refuses(self, bits, code, **kwargs):
        with self.assertRaises(RecordError) as caught:
            decode(bits, **kwargs)
        self.assertEqual(caught.exception.code, code)

    def test_hand_zero_record(self):
        self.assertEqual(len(ZERO), 1315)
        self.assertEqual(RECORD_BITS, 1315)
        result = decode(ZERO)
        self.assertEqual(result.payload, bytes(128))
        self.assertEqual((result.stored_checksum, result.calculated_checksum), (0, 0))
        self.assertEqual(result.sector_id, 0)
        self.assertEqual(result.sector_id_raw, 0b010010010)
        self.assertEqual(result.raw_packed, pack(ZERO))
        self.assertEqual(len(result.raw_packed), 165)
        self.assertEqual(result.raw_packed[-1] & 31, 0)
        self.assertEqual(result.integrity, 'xor8-payload-only')

    def test_hand_mixed_record_and_coordinate_phases(self):
        for phase in range(8):
            with self.subTest(phase=phase):
                wire = '0' * phase + MIXED
                result = decode(wire, marker_bit=phase)
                self.assertEqual(result.payload, MIXED_PAYLOAD)
                self.assertEqual((result.stored_checksum, result.calculated_checksum), (0x5a, 0x5a))
                self.assertEqual(result.sector_id, 1)
                self.assertEqual((result.marker_bit, result.payload_bit, result.checksum_bit,
                                  result.sector_id_bit, result.end_bit_exclusive),
                                 (phase, phase+16, phase+1296, phase+1306, phase+1315))
                self.assertEqual(result.raw_packed, pack(MIXED))

    def test_all_twenty_legal_symbols_hand_mapped(self):
        # Independent explicit wire/nibble oracle, including all four aliases.
        vectors = (
            ('00101', 14), ('00110', 15), ('01001', 0), ('01010', 1),
            ('01011', 2), ('01100', 5), ('01101', 3), ('01110', 4),
            ('01111', 5), ('10010', 6), ('10011', 7), ('10100', 10),
            ('10101', 8), ('10110', 9), ('10111', 10), ('11001', 11),
            ('11010', 12), ('11011', 13), ('11101', 14), ('11110', 15),
        )
        for symbol, nibble in vectors:
            for high in (False, True):
                with self.subTest(symbol=symbol, high=high):
                    pair = symbol + '01001' if high else '01001' + symbol
                    bits = MARKER + pair + ZERO_BYTE * 127 + pair + ID_ZERO
                    record = decode(bits)
                    expected = nibble << 4 if high else nibble
                    self.assertEqual(record.payload, bytes([expected]) + bytes(127))
                    self.assertEqual(record.stored_checksum, expected)

    def test_single_legal_payload_change_fails_checksum(self):
        # 09 -> 0B changes first byte from 00 to 20 without an illegal symbol.
        self.refuses(changed(ZERO, 16, 5, '01011'), 'checksum-mismatch')

    def test_single_legal_checksum_change_fails(self):
        self.refuses(changed(ZERO, 1296, 5, '01010'), 'checksum-mismatch')

    def test_every_illegal_symbol_in_payload_and_checksum_halves(self):
        # In particular 00 must not turn into a synthetic zero and pass XOR=0.
        illegal = (0, 1, 2, 3, 4, 7, 8, 16, 17, 24, 28, 31)
        for position in (16, 21, 1296, 1301):
            for symbol in illegal:
                with self.subTest(position=position, symbol=symbol):
                    self.refuses(changed(ZERO, position, 5, f'{symbol:05b}'), 'illegal-symbol')

    def test_every_bit_truncation_refused(self):
        for length in range(1315):
            with self.subTest(length=length):
                self.refuses(ZERO[:length], 'truncated')

    def test_wrong_marker_alignment_and_nonwrapping(self):
        self.refuses('1' + ZERO[1:], 'bad-marker')
        self.refuses('0' + ZERO, 'bad-marker')
        # A complete circular record is deliberately not recovered across EOF.
        rotated = ZERO[100:] + ZERO[:100]
        self.refuses(rotated, 'truncated', marker_bit=1215)

    def test_profile_and_inputs_fail_closed(self):
        for profile in ('auto', 'vorpal', 'early', '', None):
            with self.subTest(profile=profile), self.assertRaises(RecordError) as caught:
                decode_record(pack(ZERO), profile=profile, marker_bit=0, bit_length=1315)
            self.assertEqual(caught.exception.code, 'unsupported-profile')
        for data, position, length in (
            (bytearray(pack(ZERO)), 0, 1315), (pack(ZERO), -1, 1315),
            (pack(ZERO), True, 1315), (pack(ZERO), 0, True),
            (pack(ZERO), 0, -1), (pack(ZERO), 0, 1321),
            (pack(ZERO), 0.0, 1315), (pack(ZERO), 0, 1315.0),
        ):
            with self.subTest(position=position, length=length), self.assertRaises(RecordError) as caught:
                decode_record(data, profile=PROFILE, marker_bit=position, bit_length=length)
            self.assertEqual(caught.exception.code, 'invalid-input')
        self.refuses(ZERO, 'truncated', marker_bit=1316)

    def test_unsupported_sector_id(self):
        # Six kept bits encode 47, outside the source's stated 0..46 range.
        self.refuses(ZERO[:-9] + '110111111', 'unsupported-id')

    def test_header_id_and_filler_are_not_checksum_covered(self):
        changed_id = decode(ZERO[:-1] + '1')
        self.assertEqual(changed_id.sector_id, 1)
        self.assertEqual(changed_id.payload, bytes(128))
        self.assertEqual(changed_id.integrity, 'xor8-payload-only')
        filler_changed = decode(changed(ZERO, 1307, 1, '0'))
        self.assertEqual(filler_changed.sector_id, 0)
        self.assertNotEqual(filler_changed.sector_id_raw, decode(ZERO).sector_id_raw)

    def test_xor_is_not_authentication(self):
        # Equal changes in two data bytes cancel.  State the real limitation.
        two_changes = changed(changed(ZERO, 16, 5, '01010'), 26, 5, '01010')
        self.assertEqual(decode(two_changes).payload[:2], b'\x10\x10')
        self.assertEqual(decode(two_changes).stored_checksum, 0)

    def test_transport_padding_and_extra_track_bits_are_outside_record(self):
        wire = pack(ZERO)
        dirty_padding = wire[:-1] + bytes([wire[-1] | 31])
        result = decode_record(dirty_padding, profile=PROFILE, marker_bit=0, bit_length=1315)
        self.assertEqual(result.raw_packed, wire)
        self.assertEqual(decode(ZERO + '11111111').raw_packed, wire)


if __name__ == '__main__':
    unittest.main()
