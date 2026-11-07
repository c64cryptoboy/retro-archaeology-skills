"""Additive fixed-168 controls; synthetic literals, no corpus or encoder."""
import inspect
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import rapidlok_v1_record as d
import test_rapidlok_v1_record as vectors

NEW = 'remaster-v1-compatible-168'
BODY = b'\xED\xCB' + b'\xFF' * 382


def framed(record=vectors.VECTOR, header=vectors.HEADER, h=64, hs=32,
           ds=24, distance=168):
    """Place literal bits, retaining the original diagnostic fixture layout."""
    bits = ['0'] * 5600
    marker = h + distance
    for start, data in ((h, header), (marker, record)):
        text = ''.join(f'{value:08b}' for value in data)
        bits[start:start + len(text)] = text
    bits[h - hs:h] = '1' * hs
    bits[marker - ds:marker] = '1' * ds
    return bytes(int(''.join(bits[j:j + 8]), 2)
                 for j in range(0, len(bits), 8)), marker


def replace_bits(track, start, replacement):
    bits = ''.join(f'{value:08b}' for value in track)
    bits = bits[:start] + replacement + bits[start + len(replacement):]
    return bytes(int(bits[j:j + 8], 2) for j in range(0, len(bits), 8))


class Record168Tests(unittest.TestCase):
    def decode(self, track, marker, **kwargs):
        return d.decode_record(track, marker, profile=NEW, **kwargs)

    def test_retained_39_diagnostic_controls(self):
        # Reuse the diagnostic controls, but call the materialized decoder.
        passed = []

        def positive(name, track, marker, **kwargs):
            with self.subTest(control=name):
                result = self.decode(track, marker, **kwargs)
                self.assertEqual(bytes.fromhex(result['body']['hex']), BODY)
                self.assertEqual(result['auxiliary_hex'], '1401')
                passed.append(name)

        def refuse(name, track, marker, *, profile=NEW, contains=None, **kwargs):
            with self.subTest(control=name):
                with self.assertRaises(d.DecodeError) as caught:
                    d.decode_record(track, marker, profile=profile, **kwargs)
                if contains:
                    self.assertIn(contains, str(caught.exception))
                passed.append(name)

        for ds in (24, 25, 31, 39, 40, 41):
            positive('accepted_data_sync_' + str(ds), *framed(ds=ds))
        for phase in range(8):
            positive('unaligned_phase_' + str(phase), *framed(h=64 + phase))
        track, marker = framed()
        for by in (100, 300):
            rotated = vectors.rotate(track, by)
            moved = (marker - by) % (len(track) * 8)
            refuse('linear_wrap_' + str(by), rotated, moved)
            positive('circular_wrap_' + str(by), rotated, moved, circular=True)
        old, old_marker = vectors.framed()
        before = d.decode_record(old, old_marker, profile=d.PROFILE)
        self.decode(track, marker)
        self.assertEqual(d.decode_record(old, old_marker, profile=d.PROFILE), before)
        passed.append('old_profile_result_identical')
        refuse('old_profile_rejects_new_spacing', track, marker, profile=d.PROFILE)
        refuse('new_profile_rejects_old_spacing', old, old_marker)
        refuse('unknown_profile', track, marker, profile='auto', contains='profile')
        for delta in (-8, -1, 1, 8):
            refuse('marker_displaced_' + str(delta), track, marker + delta)
        refuse('short_header_sync', *framed(hs=9), contains='framing')
        refuse('short_data_sync', *framed(ds=23), contains='framing')
        changed = bytearray(track)
        changed[16:18] = b'\xFF\xFF'
        self.assertEqual(changed[29:], track[29:])
        refuse('intervening_sync', bytes(changed), marker, contains='next sync')
        refuse('one_revolution_bound_603_bytes', bytes(603), 168,
               circular=True, contains='one revolution')
        refuse('linear_truncation', track[:611], marker, contains='truncated')
        for name, index, mask, reason in (
            ('body_integrity', 1, 4, 'integrity'),
            ('stored_integrity', 582, 1, 'integrity'),
            ('body_fixed_bit', 1, 0x80, 'encoding'),
            ('tail_fixed_bit', 581, 0x20, 'encoding'),
        ):
            refuse(name, *framed(record=vectors.mutate(vectors.VECTOR, (index, mask))),
                   contains=reason)
        record = bytearray(vectors.VECTOR)
        record[196] = 0xA4
        refuse('v2_7_discriminator', *framed(record=bytes(record)), contains='v2-7')
        refuse('header_integrity',
               *framed(header=vectors.mutate(vectors.HEADER, (1, 0x40))),
               contains='projected XOR')
        refuse('header_fixed_bit',
               *framed(header=vectors.mutate(vectors.HEADER, (3, 0x20))),
               contains='encoding')
        collision = vectors.mutate(vectors.VECTOR, (1, 4), (4, 4))
        result = self.decode(*framed(record=collision))
        self.assertEqual(result['integrity']['encoded_xor'], 0xE4)
        self.assertNotEqual(bytes.fromhex(result['body']['hex']), BODY)
        passed.append('documented_xor_collision_still_visible')
        self.assertEqual(len(passed), 39)
        self.assertEqual(len(set(passed)), 39)

    def test_legacy_constants_and_required_keyword_signature(self):
        self.assertEqual(d.PROFILE, 'remaster-v1-compatible')
        self.assertEqual(d.HEADER_DISTANCE, 160)
        self.assertEqual(d.RECORD_BYTES, 583)
        self.assertEqual(d.PROFILE_168, NEW)
        self.assertEqual(str(inspect.signature(d.decode_record)),
                         '(track: bytes, marker_bit: int, *, profile: str, '
                         'circular: bool = False) -> dict')
        with self.assertRaises(TypeError):
            d.decode_record(*framed())

    def test_zero_body_vector(self):
        result = self.decode(*framed(record=vectors.ZERO_VECTOR))
        self.assertEqual(bytes.fromhex(result['body']['hex']), bytes(384))
        self.assertEqual(result['auxiliary_hex'], '0000')
        self.assertEqual(result['integrity']['stored_check'], 0)

    def test_profile_evidence_spans_and_qualifications(self):
        track, marker = framed()
        result = self.decode(track, marker)
        self.assertEqual(result['profile'], NEW)
        self.assertEqual(result['header']['start_bit'], marker - 168)
        self.assertEqual(result['header']['end_bit_exclusive'], marker - 112)
        self.assertEqual(result['header']['projected_hex'], '01009697')
        self.assertEqual(result['record_hex'], vectors.VECTOR.hex())
        self.assertEqual(result['record_end_bit_exclusive'], marker + 4664)
        self.assertEqual(result['spans'], {
            'body_encoding': [marker + 8, marker + 4616],
            'auxiliary_encoding': [marker + 4616, marker + 4648],
            'integrity_encoding': [marker + 4648, marker + 4664],
        })
        self.assertFalse(result['historical_revision_established'])
        self.assertFalse(result['file_recovery'])
        self.assertEqual(result['logical_mapping'], 'not-established')
        self.assertEqual(result['auxiliary_meaning'], 'unknown')
        self.assertFalse(result['integrity']['collision_resistant'])

    def test_exact_spacing_no_search_or_fallback(self):
        for distance in (152, 159, 160, 161, 167, 169, 176):
            with self.subTest(distance=distance):
                with self.assertRaises(d.DecodeError):
                    self.decode(*framed(distance=distance))

    def test_intervening_sync_threshold_at_both_gap_edges(self):
        track, marker = framed()
        # Include an unaligned run and the latest run separated from data sync.
        for start in (120, 133, marker - 24 - 11):
            for length in (9, 10):
                with self.subTest(start=start, length=length):
                    changed = replace_bits(track, start, '1' * length)
                    if length == 9:
                        self.assertEqual(self.decode(changed, marker)['body']['hex'], BODY.hex())
                    else:
                        with self.assertRaisesRegex(d.DecodeError, 'next sync'):
                            self.decode(changed, marker)

    def test_intervening_sync_circular_gap(self):
        track, marker = framed()
        changed = replace_bits(track, 133, '1' * 10)
        by = 138
        moved = (marker - by) % (len(track) * 8)
        self.assertEqual(self.decode(vectors.rotate(track, by), moved,
                                     circular=True)['body']['hex'], BODY.hex())
        with self.assertRaisesRegex(d.DecodeError, 'next sync'):
            self.decode(vectors.rotate(changed, by), moved, circular=True)

    def test_terminal_sync_cannot_extend_before_gap(self):
        track, marker = framed()
        changed = replace_bits(track, marker - 113, '1' * 113)
        with self.assertRaisesRegex(d.DecodeError, 'next sync'):
            self.decode(changed, marker)

    def test_sync_barrier_does_not_change_legacy_profile(self):
        track, marker = vectors.framed()
        changed = replace_bits(track, 133, '1' * 10)
        self.assertEqual(d.decode_record(changed, marker, profile=d.PROFILE),
                         d.decode_record(track, marker, profile=d.PROFILE))

    def test_exact_revolution_bound_is_profile_specific(self):
        with self.assertRaisesRegex(d.DecodeError, 'one revolution'):
            self.decode(bytes(603), 168, circular=True)
        # Equality gets past the span gate; these zero tracks still lack sync.
        with self.assertRaisesRegex(d.DecodeError, '^framing: require'):
            self.decode(bytes(604), 168, circular=True)
        with self.assertRaisesRegex(d.DecodeError, '^framing: require'):
            d.decode_record(bytes(603), 160, profile=d.PROFILE, circular=True)

    def test_minimum_header_sync(self):
        self.assertEqual(self.decode(*framed(hs=10))['header']['sync_ones'], 10)

    def test_marker_range_and_value(self):
        track, marker = framed()
        for invalid in (-1, len(track) * 8):
            with self.subTest(marker=invalid):
                with self.assertRaisesRegex(d.DecodeError, 'marker: outside'):
                    self.decode(track, invalid)
        with self.assertRaisesRegex(d.DecodeError, 'expected leading 6B'):
            self.decode(*framed(record=vectors.mutate(vectors.VECTOR, (0, 1))))

    def test_compensated_illegal_encoding_still_refused(self):
        record = vectors.mutate(vectors.VECTOR, (1, 0x80), (4, 0x80))
        with self.assertRaisesRegex(d.DecodeError, 'encoding'):
            self.decode(*framed(record=record))

    def test_header_fingerprint_remains_required(self):
        for index, mask in ((0, 1), (1, 0x80), (2, 8), (4, 1), (5, 1)):
            with self.subTest(index=index):
                with self.assertRaisesRegex(d.DecodeError, 'unsupported fingerprint'):
                    self.decode(*framed(header=vectors.mutate(vectors.HEADER, (index, mask))))

    def test_mutable_input_is_unchanged(self):
        track, marker = framed()
        mutable = bytearray(track)
        self.decode(mutable, marker)
        self.assertEqual(bytes(mutable), track)

    def test_cli_profiles_and_refusal_do_not_write_input(self):
        track, marker = framed()
        with tempfile.TemporaryDirectory(prefix='rapidlok-168-') as directory:
            path = Path(directory) / 'synthetic.bin'
            path.write_bytes(track)
            command = [sys.executable, '-B', str(Path(d.__file__)), str(path), str(marker)]
            result = subprocess.run(command + ['--profile', NEW],
                                    capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)['profile'], NEW)
            for options in ([], ['--profile', 'auto'], ['--profile', d.PROFILE]):
                with self.subTest(options=options):
                    refused = subprocess.run(command + options,
                                             capture_output=True, text=True, check=False)
                    self.assertEqual(refused.returncode, 2)
                    self.assertEqual(refused.stdout, '')
                    if options == ['--profile', d.PROFILE]:
                        self.assertIn('framing: require', refused.stderr)
            self.assertEqual(path.read_bytes(), track)
            self.assertEqual(sorted(p.name for p in Path(directory).iterdir()), ['synthetic.bin'])


if __name__ == '__main__':
    unittest.main()
