"""Synthetic scanner tests; no commercial bytes, paths, or private dependency."""
from hashlib import sha256
import json
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest

from test_vorpal_record import (ID_ZERO, MARKER, MIXED, MIXED_PAYLOAD, ZERO,
                                changed, pack)
from vorpal_record import PROFILE, RECORD_BITS, RecordError, decode_record
from vorpal_inventory import scan_track


def scan(bits):
    return scan_track(pack(bits), profile=PROFILE, bit_length=len(bits))


def marker_oracle(bits):
    # Independent full sliding-window enumeration, not the scanner's find loop.
    return [p for p in range(max(0, len(bits) - 15))
            if bits[p:p + 16] == MARKER]


class InventoryTests(unittest.TestCase):
    def test_empty_and_no_marker_tracks(self):
        for bits in ('', '0' * 2000, '1' * 2000, MARKER[:15]):
            with self.subTest(length=len(bits)):
                result = scan(bits)
                self.assertEqual(result['candidates'], [])
                self.assertEqual(result['summary']['candidate_count'], 0)
                self.assertEqual(result['summary']['accepted_count'], 0)
                self.assertEqual(result['repeated_ids'], [])

    def test_all_eight_phases_and_source_hashes(self):
        for phase in range(8):
            with self.subTest(phase=phase):
                bits = '0' * phase + MIXED
                result = scan(bits)
                self.assertEqual(result['source']['sha256'], sha256(pack(bits)).hexdigest())
                self.assertEqual(result['summary']['candidate_count'], 1)
                item = result['candidates'][0]
                self.assertEqual(item['marker_bit'], phase)
                self.assertEqual(item['requested_end_bit_exclusive'], phase + RECORD_BITS)
                self.assertEqual(item['payload_bit'], phase + 16)
                self.assertEqual(item['checksum_bit'], phase + 1296)
                self.assertEqual(item['sector_id_bit'], phase + 1306)
                self.assertEqual(item['status'], 'accepted')
                self.assertEqual(item['sector_id'], 1)
                self.assertEqual(item['raw_packed_sha256'], sha256(pack(MIXED)).hexdigest())
                self.assertEqual(item['payload_sha256'], sha256(MIXED_PAYLOAD).hexdigest())
                self.assertEqual(item['raw_zero_tail_padding_bits'], 5)

    def test_one_bit_record_overlap_not_skipped(self):
        bits = ZERO[:-1] + MIXED
        result = scan(bits)
        self.assertEqual(marker_oracle(bits), [0, 1314])
        self.assertEqual([c['marker_bit'] for c in result['candidates']], [0, 1314])
        self.assertEqual(result['summary']['accepted_count'], 2)
        self.assertEqual([c['sector_id'] for c in result['candidates']], [0, 1])
        self.assertEqual(result['candidates'][0]['raw_packed_sha256'],
                         sha256(pack(ZERO)).hexdigest())

    def test_preserves_identical_duplicates_aliases_and_conflicting_ids(self):
        # Filler is not checksum-covered; four observations, no selected winner.
        filler_variant = changed(ZERO, 1307, 1, '0')
        conflict = MIXED[:-9] + ID_ZERO
        bits = ZERO + ZERO + filler_variant + conflict
        result = scan(bits)
        self.assertEqual(result['summary']['accepted_count'], 4)
        self.assertEqual(result['summary']['observed_accepted_ids'], [0])
        self.assertEqual(result['summary']['conflicting_id_count'], 1)
        group = result['repeated_ids'][0]
        self.assertEqual(group['marker_bits'], [0, 1315, 2630, 3945])
        self.assertTrue(group['conflicting_accepted_payloads'])
        self.assertEqual(len(group['raw_groups']), 3)
        self.assertEqual(len(group['payload_groups']), 2)
        self.assertEqual(group['raw_groups'][sha256(pack(ZERO)).hexdigest()], [0, 1315])
        self.assertEqual(group['payload_groups'][sha256(bytes(128)).hexdigest()],
                         [0, 1315, 2630])
        self.assertNotIn('selected', group)

    def test_exact_refusal_codes_and_messages_are_preserved(self):
        fixtures = (
            (changed(ZERO, 16, 5, '00000'), 'illegal-symbol'),
            (changed(ZERO, 1296, 5, '00000'), 'illegal-symbol'),
            (changed(ZERO, 16, 5, '01011'), 'checksum-mismatch'),
            (ZERO[:-9] + '110111111', 'unsupported-id'),
            (ZERO[:-1], 'truncated'),
        )
        for bits, code in fixtures:
            with self.subTest(code=code, length=len(bits)):
                with self.assertRaises(RecordError) as caught:
                    decode_record(pack(bits), profile=PROFILE, marker_bit=0,
                                  bit_length=len(bits))
                result = scan(bits)
                item = result['candidates'][0]
                self.assertEqual(item['status'], 'refused')
                self.assertEqual(item['refusal_code'], code)
                self.assertEqual(item['refusal_message'], str(caught.exception))
                self.assertEqual(result['summary']['accepted_count'], 0)
                self.assertEqual(item['raw_packed_sha256'], sha256(pack(bits)).hexdigest())
                self.assertNotIn('payload_sha256', item)
                self.assertNotIn('sector_id', item)

    def test_all_truncated_marker_windows_remain_refused(self):
        for length in range(16, RECORD_BITS):
            with self.subTest(length=length):
                item = scan(ZERO[:length])['candidates'][0]
                self.assertEqual(item['status'], 'refused')
                self.assertEqual(item['refusal_code'], 'truncated')
                self.assertEqual(item['observed_end_bit_exclusive'], length)
                self.assertEqual(item['raw_bit_length'], length)
                self.assertEqual(item['raw_packed_sha256'], sha256(pack(ZERO[:length])).hexdigest())

    def test_no_circular_record_or_split_marker_recovery(self):
        rotated = ZERO[100:] + ZERO[:100]
        result = scan(rotated)
        self.assertEqual(result['summary']['accepted_count'], 0)
        item = result['candidates'][0]
        self.assertEqual(item['marker_bit'], 1215)
        self.assertEqual(item['refusal_code'], 'truncated')
        self.assertEqual(item['raw_bit_length'], 100)
        split_marker = ZERO[8:] + ZERO[:8]
        self.assertEqual(scan(split_marker)['summary']['candidate_count'], 0)

    def test_transport_padding_is_not_scanned_or_hashed_as_record_bits(self):
        data = pack(ZERO)
        dirty = data[:-1] + bytes([data[-1] | 31])
        clean = scan_track(data, profile=PROFILE, bit_length=len(ZERO))
        result = scan_track(dirty, profile=PROFILE, bit_length=len(ZERO))
        self.assertNotEqual(result['source']['sha256'], clean['source']['sha256'])
        self.assertEqual(result['candidates'], clean['candidates'])
        extra = pack(ZERO + MARKER)
        self.assertEqual(scan_track(extra, profile=PROFILE, bit_length=len(ZERO))['candidates'],
                         clean['candidates'])
        self.assertEqual(scan_track(extra, profile=PROFILE,
                                    bit_length=len(ZERO + MARKER))['summary']['refused_count'], 1)

    def test_explicit_profile_and_input_validation_even_without_markers(self):
        for profile in ('auto', 'vorpal', 'early', '', None):
            with self.subTest(profile=profile), self.assertRaises(RecordError) as caught:
                scan_track(b'', profile=profile, bit_length=0)
            self.assertEqual(caught.exception.code, 'unsupported-profile')
        for data, length in ((bytearray(), 0), ('', 0), (b'', True),
                             (b'', -1), (b'', 1), (b'', 0.0), (b'', None)):
            with self.subTest(length=length), self.assertRaises(RecordError) as caught:
                scan_track(data, profile=PROFILE, bit_length=length)
            self.assertEqual(caught.exception.code, 'invalid-input')
        with self.assertRaises(TypeError):
            scan_track(b'', bit_length=0)
        with self.assertRaises(TypeError):
            scan_track(b'', profile=PROFILE)

    def test_marker_completeness_and_direct_decoder_equivalence(self):
        rng = random.Random(20261024)
        bits = ''.join(str(rng.randrange(2)) for _ in range(6000))
        bits += ZERO[:-1] + MIXED + MARKER + '0' * 1400 + MARKER
        result = scan(bits)
        self.assertEqual([c['marker_bit'] for c in result['candidates']], marker_oracle(bits))
        for item in result['candidates']:
            marker = item['marker_bit']
            observed = bits[marker:min(marker + RECORD_BITS, len(bits))]
            self.assertEqual(item['raw_packed_sha256'], sha256(pack(observed)).hexdigest())
            try:
                direct = decode_record(pack(bits), profile=PROFILE, marker_bit=marker,
                                       bit_length=len(bits))
            except RecordError as error:
                self.assertEqual((item['status'], item['refusal_code'], item['refusal_message']),
                                 ('refused', error.code, str(error)))
            else:
                self.assertEqual(item['status'], 'accepted')
                self.assertEqual(item['payload_sha256'], sha256(direct.payload).hexdigest())
                self.assertEqual(item['raw_packed_sha256'], sha256(direct.raw_packed).hexdigest())
                self.assertEqual(item['sector_id_raw'], direct.sector_id_raw)

    def test_cli_json_and_missing_profile_refusal(self):
        script = Path(__file__).with_name('vorpal_inventory.py')
        with tempfile.TemporaryDirectory() as tmp:
            raw = Path(tmp) / 'synthetic-track.bin'
            raw.write_bytes(pack(MIXED))
            command = [sys.executable, '-B', str(script), str(raw),
                       '--bit-length', str(len(MIXED))]
            missing = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(missing.returncode, 2)
            self.assertEqual(missing.stdout, '')
            good = subprocess.run(command + ['--profile', PROFILE],
                                  capture_output=True, text=True)
            self.assertEqual(good.returncode, 0, good.stderr)
            self.assertEqual(json.loads(good.stdout), scan(MIXED))
            self.assertEqual(raw.read_bytes(), pack(MIXED))


if __name__ == '__main__':
    unittest.main()
