"""Literal hand vectors and refusing controls; no commercial bytes or encoder."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import rapidlok_v1_record as decoder
from rapidlok_recognize import RecognitionError, inspect_record

HEADER = bytes.fromhex('75 92 59 24 D6 ED 6F')
VECTOR = bytes.fromhex('6B 96 69 EC') + bytes.fromhex('92 49 24') * 191 + bytes.fromhex('A5 AC A4 A5 BA AC')
ZERO_VECTOR = b'\x6B' + bytes.fromhex('EF BE FB') * 192 + b'\xA4' * 6


def framed(record=VECTOR, header=HEADER, header_bit=64, data_sync=24, header_sync=32):
    """Place literal bits; this is not a payload-to-RapidLok encoder."""
    bits = ['0'] * 5600
    marker = header_bit + 160
    for start, data in ((header_bit, header), (marker, record)):
        text = ''.join(f'{byte:08b}' for byte in data)
        bits[start:start + len(text)] = text
    bits[header_bit - header_sync:header_bit] = '1' * header_sync
    bits[marker - data_sync:marker] = '1' * data_sync
    return bytes(int(''.join(bits[i:i + 8]), 2) for i in range(0, len(bits), 8)), marker


def mutate(record, *changes):
    result = bytearray(record)
    for index, mask in changes:
        result[index] ^= mask
    return bytes(result)


def rotate(track, by):
    bits = ''.join(f'{byte:08b}' for byte in track)
    bits = bits[by:] + bits[:by]
    return bytes(int(bits[i:i + 8], 2) for i in range(0, len(bits), 8))


class RecordTests(unittest.TestCase):
    def decode(self, track, marker, **kwargs):
        return decoder.decode_record(track, marker, profile=decoder.PROFILE, **kwargs)

    def test_hand_vector(self):
        result = self.decode(*framed())
        self.assertEqual(bytes.fromhex(result['body']['hex']), b'\xED\xCB' + b'\xFF' * 382)
        self.assertEqual(result['body']['bytes'], 384)
        self.assertEqual(result['auxiliary_hex'], '1401')
        self.assertEqual(result['header']['projected_hex'], '01009697')
        self.assertEqual(result['integrity']['encoded_xor'], 0xE4)
        self.assertEqual(result['integrity']['stored_check'], 0xE4)
        self.assertFalse(result['historical_revision_established'])
        self.assertFalse(result['file_recovery'])
        self.assertEqual(result['logical_mapping'], 'not-established')
        self.assertEqual(result['record_hex'], VECTOR.hex())

    def test_zero_body_hand_vector(self):
        result = self.decode(*framed(ZERO_VECTOR))
        self.assertEqual(bytes.fromhex(result['body']['hex']), bytes(384))
        self.assertEqual(result['auxiliary_hex'], '0000')
        self.assertEqual(result['integrity']['stored_check'], 0)

    def test_both_observed_sync_lengths(self):
        for count in (24, 25):
            with self.subTest(count=count):
                self.assertEqual(self.decode(*framed(data_sync=count))['data_sync_ones'], count)

    def test_old_recognizer_sync_contract_unchanged(self):
        with self.assertRaisesRegex(RecognitionError, 'fewer than 25'):
            inspect_record(*framed())

    def test_insufficient_data_sync(self):
        with self.assertRaisesRegex(decoder.DecodeError, 'framing'):
            self.decode(*framed(data_sync=23))

    def test_insufficient_header_sync(self):
        with self.assertRaisesRegex(decoder.DecodeError, 'framing'):
            self.decode(*framed(header_sync=9))

    def test_header_distance_not_searched(self):
        track, marker = framed()
        with self.assertRaises(decoder.DecodeError):
            self.decode(track, marker + 8)

    def test_valid_header_displaced_without_moving_record(self):
        track, marker = framed()
        self.assertEqual(self.decode(track, marker)['record_hex'], VECTOR.hex())
        for displacement in (-1, 1):
            with self.subTest(displacement_bytes=displacement):
                changed = bytearray(track)
                changed[4:15] = bytes(11)  # Remove only the old sync and header.
                header_byte = 8 + displacement
                changed[header_byte - 4:header_byte] = b'\xFF' * 4
                changed[header_byte:header_byte + len(HEADER)] = HEADER
                # The data sync, marker, and complete valid record stay fixed.
                self.assertEqual(changed[25:], track[25:])
                self.assertEqual(changed[header_byte:header_byte + 7], HEADER)
                with self.assertRaises(decoder.DecodeError):
                    self.decode(bytes(changed), marker)

    def test_explicit_profile_required(self):
        with self.assertRaises(TypeError):
            decoder.decode_record(*framed())
        with self.assertRaisesRegex(decoder.DecodeError, 'profile'):
            decoder.decode_record(*framed(), profile='auto')

    def test_v2_discriminator_refused(self):
        record = bytearray(VECTOR)
        record[196] = 0xA4
        with self.assertRaisesRegex(decoder.DecodeError, 'v2-7'):
            self.decode(*framed(bytes(record)))

    def test_wrong_marker(self):
        with self.assertRaisesRegex(decoder.DecodeError, 'leading 6B'):
            self.decode(*framed(mutate(VECTOR, (0, 1))))

    def test_wrong_orientation(self):
        track, marker = framed()
        reversed_bits = bytes(int(f'{byte:08b}'[::-1], 2) for byte in track)
        with self.assertRaises(decoder.DecodeError):
            self.decode(reversed_bits, marker)

    def test_header_integrity(self):
        with self.assertRaisesRegex(decoder.DecodeError, 'header: projected XOR'):
            self.decode(*framed(header=mutate(HEADER, (1, 0x40))))

    def test_unused_header_bit(self):
        with self.assertRaisesRegex(decoder.DecodeError, 'header: unsupported fingerprint'):
            self.decode(*framed(header=mutate(HEADER, (1, 0x80))))

    def test_header_canonical_encoding(self):
        with self.assertRaisesRegex(decoder.DecodeError, 'encoding'):
            self.decode(*framed(header=mutate(HEADER, (3, 0x20))))

    def test_body_integrity(self):
        with self.assertRaisesRegex(decoder.DecodeError, 'integrity'):
            self.decode(*framed(mutate(VECTOR, (1, 4))))

    def test_stored_integrity(self):
        with self.assertRaisesRegex(decoder.DecodeError, 'integrity'):
            self.decode(*framed(mutate(VECTOR, (582, 1))))

    def test_encoding_gate_despite_matching_xor(self):
        changed = mutate(VECTOR, (1, 2), (582, 2))
        with self.assertRaisesRegex(decoder.DecodeError, 'encoding'):
            self.decode(*framed(changed))

    def test_tail_fixed_bit(self):
        with self.assertRaisesRegex(decoder.DecodeError, 'encoding: noncanonical tail'):
            self.decode(*framed(mutate(VECTOR, (581, 0x20))))

    def test_all_triple_fixed_and_adjustment_bits(self):
        for index, mask in ((1, 0x80), (1, 2), (1, 0x10), (2, 8), (2, 0x40), (2, 1), (3, 0x20), (3, 4)):
            with self.subTest(index=index, mask=mask):
                with self.assertRaisesRegex(decoder.DecodeError, 'encoding'):
                    self.decode(*framed(mutate(VECTOR, (index, mask))))

    def test_tail_adjustment_bit(self):
        with self.assertRaisesRegex(decoder.DecodeError, 'encoding'):
            self.decode(*framed(mutate(VECTOR, (577, 4))))

    def test_known_xor_collision_is_not_hidden(self):
        changed = mutate(VECTOR, (1, 4), (4, 4))
        result = self.decode(*framed(changed))
        self.assertEqual(result['integrity']['encoded_xor'], 0xE4)
        self.assertNotEqual(result['body']['hex'], self.decode(*framed())['body']['hex'])
        self.assertFalse(result['integrity']['collision_resistant'])

    def test_exact_codec_lengths(self):
        for record in (VECTOR[:-1], VECTOR + b'\x00'):
            with self.assertRaisesRegex(decoder.DecodeError, 'exactly 583'):
                decoder._decode_body(record)

    def test_empty_and_out_of_range(self):
        for track, marker in ((b'', 0), (bytes(700), -1), (bytes(700), 5600)):
            with self.assertRaisesRegex(decoder.DecodeError, 'outside'):
                self.decode(track, marker)

    def test_one_revolution_bound(self):
        with self.assertRaisesRegex(decoder.DecodeError, 'one revolution'):
            self.decode(bytes(600), 200, circular=True)

    def test_linear_truncation(self):
        track, marker = framed()
        with self.assertRaisesRegex(decoder.DecodeError, 'truncated'):
            self.decode(track[:610], marker)

    def test_all_unaligned_phases(self):
        expected = self.decode(*framed())['body']['hex']
        for phase in range(8):
            with self.subTest(phase=phase):
                result = self.decode(*framed(header_bit=64 + phase))
                self.assertEqual(result['body']['hex'], expected)
                self.assertEqual(result['spans']['body_encoding'][0], 232 + phase)

    def test_circular_record_and_header_wraps(self):
        track, marker = framed()
        for shift in (300, 100):
            with self.subTest(shift=shift):
                rotated = rotate(track, shift)
                relocated = (marker - shift) % (len(track) * 8)
                with self.assertRaises(decoder.DecodeError):
                    self.decode(rotated, relocated)
                result = self.decode(rotated, relocated, circular=True)
                self.assertEqual(result['record_hex'], VECTOR.hex())
                self.assertEqual(result['body']['hex'], self.decode(track, marker)['body']['hex'])
                self.assertEqual(result['record_end_bit_exclusive'], relocated + 4664)

    def test_cli_and_input_preservation(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'track.bin'
            track, marker = framed()
            path.write_bytes(track)
            command = [sys.executable, '-B', str(Path(decoder.__file__)), str(path), str(marker)]
            result = subprocess.run(command + ['--profile', decoder.PROFILE], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)['body']['bytes'], 384)
            self.assertEqual(path.read_bytes(), track)
            refused = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(refused.returncode, 2)
            self.assertEqual(path.read_bytes(), track)


if __name__ == '__main__':
    unittest.main()
