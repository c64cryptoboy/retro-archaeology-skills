"""Synthetic DOS 3.3 reader checks; no commercial images or token fixtures."""

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest


READER_PATH = Path(__file__).resolve().parents[1] / 'tools' / 'apple_dos33.py'
SPEC = importlib.util.spec_from_file_location('apple_dos33', READER_PATH)
apple_dos33 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(apple_dos33)
read_image = apple_dos33.read_image


class Disk:
    """Build only the fields needed by the stated DOS 3.3 profile."""

    def __init__(self):
        self.data = bytearray(35 * 16 * 256)
        vtoc = self.sector(17, 0)
        vtoc[1:4] = bytes([17, 15, 3])
        vtoc[6] = 254
        vtoc[0x27] = 122
        vtoc[0x34:0x38] = bytes([35, 16, 0, 1])
        # All bitmap bits are zero (allocated), including metadata sectors.

    def sector(self, track, sector):
        offset = (track * 16 + sector) * 256
        return memoryview(self.data)[offset:offset + 256]

    def entry(self, slot=0, name='SAMPLE', file_type=2, ts=(18, 0), count=2,
              catalog=(17, 15), raw_name=None):
        record = bytearray(35)
        record[:3] = bytes([*ts, file_type])
        record[3:33] = (raw_name if raw_name is not None else
                         bytes(value | 128 for value in name.encode('ascii')).ljust(30, b'\xa0'))
        record[33:35] = count.to_bytes(2, 'little')
        offset = 11 + slot * 35
        self.sector(*catalog)[offset:offset + 35] = record

    def ts_list(self, coordinate=(18, 0), pairs=((1, 0),), start=0, next_list=(0, 0)):
        raw = self.sector(*coordinate)
        raw[1:3] = bytes(next_list)
        raw[5:7] = start.to_bytes(2, 'little')
        for index, pair in enumerate(pairs):
            raw[12 + 2 * index:14 + 2 * index] = bytes(pair)

    def basic(self, payload=b'not a BASIC program', file_type=2):
        self.entry(file_type=file_type)
        self.ts_list()
        block = len(payload).to_bytes(2, 'little') + payload
        self.sector(1, 0)[:] = block.ljust(256, b'\x5a')
        return self

    def read(self):
        return read_image(bytes(self.data))


def codes(manifest):
    return {diagnostic['code'] for diagnostic in manifest['issues']}


class AppleDos33Tests(unittest.TestCase):
    def test_basic_raw_boundaries_without_decoding(self):
        for file_type in (1, 2, 0x82):
            with self.subTest(file_type=file_type):
                disk = Disk().basic(file_type=file_type)
                original = bytes(disk.data)
                manifest, artifacts = disk.read()
                entry = manifest['files'][0]
                prefix = 'files/entry-000/'
                self.assertEqual(manifest['issues'], [])
                self.assertTrue(manifest['catalog_chain_complete'])
                self.assertEqual(entry['locked'], bool(file_type & 128))
                self.assertEqual(artifacts[prefix + 'payload.bin'], b'not a BASIC program')
                self.assertEqual(artifacts[prefix + 'header.bin'], bytes([19, 0]))
                self.assertEqual(artifacts[prefix + 'slack.bin'], b'\x5a' * 235)
                self.assertEqual(artifacts[prefix + 'allocated.bin'],
                                 b''.join(artifacts[prefix + name + '.bin']
                                          for name in ('header', 'payload', 'slack')))
                self.assertEqual(entry['payload_status'], 'bounded_by_header')
                self.assertEqual(bytes(disk.data), original)
                self.assertEqual(disk.read(), (manifest, artifacts))
                json.dumps(manifest)

    def test_binary_load_address_and_zero_or_exact_lengths(self):
        for file_type, header_size in ((1, 2), (2, 2), (4, 4)):
            for length in (0, 256 - header_size):
                with self.subTest(file_type=file_type, length=length):
                    disk = Disk()
                    disk.entry(file_type=file_type)
                    disk.ts_list()
                    header = (b'\x00\x20' if file_type == 4 else b'') + length.to_bytes(2, 'little')
                    disk.sector(1, 0)[:] = (header + b'x' * length).ljust(256, b'z')
                    manifest, artifacts = disk.read()
                    entry = manifest['files'][0]
                    self.assertEqual(manifest['issues'], [])
                    self.assertEqual(artifacts['files/entry-000/payload.bin'], b'x' * length)
                    self.assertEqual(entry['slack_bytes'], 256 - header_size - length)
                    if file_type == 4:
                        self.assertEqual(entry['binary_load_address'], 0x2000)

    def test_multiple_ts_lists_nonzero_start_and_logical_order(self):
        disk = Disk()
        coordinates = [(1 + index // 16, index % 16) for index in range(123)]
        blocks = [bytes([index]) * 256 for index in range(123)]
        for coordinate, block in zip(coordinates, blocks):
            disk.sector(*coordinate)[:] = block
        disk.entry(file_type=0, count=125)
        # Visit the higher logical block first, forcing assembly by file offset.
        disk.ts_list(pairs=coordinates[122:], start=122, next_list=(18, 1))
        disk.ts_list(coordinate=(18, 1), pairs=coordinates[:122], start=0)
        manifest, artifacts = disk.read()
        entry = manifest['files'][0]
        self.assertEqual(manifest['issues'], [])
        self.assertEqual([item['file_sector_start'] for item in entry['ts_lists']], [122, 0])
        self.assertEqual(entry['observed_sector_references'], 125)
        self.assertEqual(artifacts['files/entry-000/allocated.bin'], b''.join(blocks))
        self.assertEqual(entry['gaps'], [])
        self.assertNotIn('files/entry-000/payload.bin', artifacts)

    def test_leading_and_internal_gaps_preserve_observed_bytes_only(self):
        for start, pairs, gaps in ((5, ((1, 0),), [0, 1, 2, 3, 4]),
                                   (0, ((1, 0), (0, 0), (1, 1)), [1])):
            with self.subTest(start=start):
                disk = Disk()
                disk.entry(count=1 + sum(pair != (0, 0) for pair in pairs))
                disk.ts_list(start=start, pairs=pairs)
                disk.sector(1, 0)[:] = b'a' * 256
                disk.sector(1, 1)[:] = b'b' * 256
                manifest, artifacts = disk.read()
                entry = manifest['files'][0]
                self.assertIn('file_gaps', codes(manifest))
                self.assertEqual(entry['gaps'], gaps)
                self.assertEqual(entry['assembly'], 'not_assembled')
                self.assertNotIn('files/entry-000/allocated.bin', artifacts)
                self.assertNotIn('files/entry-000/payload.bin', artifacts)
                self.assertEqual(artifacts['files/entry-000/data-0000.bin'], b'a' * 256)
                self.assertEqual(len(entry['data_sectors']), len(pairs) - pairs.count((0, 0)))

    def test_catalog_and_ts_cycles(self):
        disk = Disk().basic()
        disk.sector(17, 15)[1:3] = bytes([17, 14])
        disk.sector(17, 14)[1:3] = bytes([17, 15])
        manifest, artifacts = disk.read()
        self.assertIn('catalog_cycle', codes(manifest))
        self.assertFalse(manifest['catalog_chain_complete'])
        self.assertEqual(len(manifest['catalog_chain']), 2)
        self.assertIn('metadata/catalog-001.bin', artifacts)

        disk = Disk().basic()
        disk.sector(18, 0)[1:3] = bytes([18, 1])
        disk.ts_list(coordinate=(18, 1), pairs=(), next_list=(18, 0))
        manifest, artifacts = disk.read()
        self.assertIn('ts_cycle', codes(manifest))
        self.assertFalse(manifest['files'][0]['allocation_chain_complete'])
        self.assertEqual(len(manifest['files'][0]['ts_lists']), 2)
        self.assertNotIn('files/entry-000/allocated.bin', artifacts)
        self.assertNotIn('files/entry-000/payload.bin', artifacts)
        self.assertIn('files/entry-000/data-0000.bin', artifacts)

    def test_bad_coordinates_are_diagnostics_not_valid_chains(self):
        cases = [('catalog', (17, 0), 1, 'invalid_catalog_coordinate'),
                 ('ts', (17, 15), 11, 'invalid_ts_coordinate'),
                 ('data', (18, 0), 12, 'invalid_data_coordinate')]
        for label, coordinate, offset, diagnostic in cases:
            for invalid in ((35, 0), (1, 16), (255, 255)):
                # 255 in an entry's first byte marks a deleted file, not a pointer.
                if label == 'ts' and invalid[0] == 255:
                    continue
                with self.subTest(kind=label, invalid=invalid):
                    disk = Disk().basic()
                    disk.sector(*coordinate)[offset:offset + 2] = bytes(invalid)
                    manifest, artifacts = disk.read()
                    self.assertIn(diagnostic, codes(manifest))
                    if label == 'catalog':
                        self.assertFalse(manifest['catalog_chain_complete'])
                    else:
                        self.assertFalse(manifest['files'][0]['allocation_chain_complete'])
                        self.assertNotIn('files/entry-000/allocated.bin', artifacts)
                        self.assertNotIn('files/entry-000/payload.bin', artifacts)

    def test_nonzero_terminator_is_not_silently_accepted(self):
        for coordinate, diagnostic in (((17, 15), 'nonzero_catalog_terminator'),
                                       ((18, 0), 'nonzero_ts_terminator')):
            with self.subTest(coordinate=coordinate):
                disk = Disk().basic()
                disk.sector(*coordinate)[1:3] = bytes([0, 16])
                manifest, artifacts = disk.read()
                self.assertIn(diagnostic, codes(manifest))
                if coordinate == (18, 0):
                    self.assertNotIn('files/entry-000/payload.bin', artifacts)

    def test_duplicate_logical_slots_keep_both_evidence_sectors(self):
        disk = Disk().basic()
        disk.sector(18, 0)[1:3] = bytes([18, 1])
        disk.ts_list(coordinate=(18, 1), pairs=((1, 1),), start=0)
        disk.sector(1, 1)[:] = b'b' * 256
        manifest, artifacts = disk.read()
        self.assertIn('duplicate_file_sector', codes(manifest))
        self.assertNotIn('files/entry-000/allocated.bin', artifacts)
        self.assertNotEqual(artifacts['files/entry-000/data-0000.bin'],
                            artifacts['files/entry-000/data-0001.bin'])
        self.assertEqual([item['file_sector'] for item in manifest['files'][0]['data_sectors']], [0, 0])

    def test_oversize_and_missing_headers_do_not_invent_payload(self):
        for file_type, header_size in ((1, 2), (2, 2), (4, 4)):
            with self.subTest(file_type=file_type):
                disk = Disk()
                disk.entry(file_type=file_type)
                disk.ts_list()
                block = disk.sector(1, 0)
                offset = 2 if file_type == 4 else 0
                block[offset:offset + 2] = (257 - header_size).to_bytes(2, 'little')
                manifest, artifacts = disk.read()
                self.assertIn('payload_exceeds_allocation', codes(manifest))
                self.assertEqual(manifest['files'][0]['payload_status'], 'invalid_header')
                self.assertIn('files/entry-000/allocated.bin', artifacts)
                self.assertIn('files/entry-000/header.bin', artifacts)
                self.assertNotIn('files/entry-000/payload.bin', artifacts)
                self.assertNotIn('files/entry-000/slack.bin', artifacts)

                disk.ts_list(pairs=((0, 0),))
                manifest, artifacts = disk.read()
                self.assertIn('short_header', codes(manifest))
                self.assertNotIn('files/entry-000/payload.bin', artifacts)

    def test_colliding_and_unsafe_names_remain_metadata(self):
        names = ['SAME', 'same', 'SAME', '../escape', 'C:\\bad', '', '\x00\x7f']
        disk = Disk()
        for slot, name in enumerate(names):
            disk.entry(slot=slot, name=name, ts=(18, slot))
            disk.ts_list(coordinate=(18, slot), pairs=((1, slot),))
            disk.sector(1, slot)[:] = bytes([1, 0, slot]) + b'\0' * 253
        manifest, artifacts = disk.read()
        self.assertEqual(manifest['issues'], [])
        self.assertEqual([entry['name'] for entry in manifest['files']], names)
        for slot, entry in enumerate(manifest['files']):
            self.assertEqual(entry['id'], f'entry-{slot:03d}')
            self.assertEqual(artifacts[f'files/entry-{slot:03d}/payload.bin'], bytes([slot]))
            self.assertEqual(bytes.fromhex(entry['name_raw_hex']),
                             bytes(value | 128 for value in names[slot].encode('ascii')).ljust(30, b'\xa0'))
        for path in artifacts:
            self.assertNotIn('..', path.split('/'))
            self.assertNotIn('\\', path)
            self.assertFalse(path.startswith('/'))
        self.assertEqual(len({path.casefold() for path in artifacts}), len(artifacts))

    def test_ids_include_unused_deleted_and_prior_catalog_slots(self):
        disk = Disk()
        disk.sector(17, 15)[1:3] = bytes([17, 14])
        disk.entry(slot=1, ts=(255, 0))
        disk.entry(slot=2)
        disk.ts_list()
        disk.entry(slot=0, catalog=(17, 14), ts=(18, 1))
        disk.ts_list(coordinate=(18, 1), pairs=((1, 1),))
        manifest, _ = disk.read()
        self.assertEqual([entry['id'] for entry in manifest['files']], ['entry-002', 'entry-007'])
        self.assertEqual(manifest['files'][0]['catalog']['entry_offset'], 81)

    def test_allocation_counts_overlap_and_free_bitmap_orientation(self):
        disk = Disk().basic()
        disk.entry(count=9)
        disk.ts_list(pairs=((1, 0), (1, 0)))
        # The low bit of bitmap byte 1 denotes sector 0, not sector 15.
        disk.sector(17, 0)[0x38 + 4 + 1] = 1
        manifest, _ = disk.read()
        self.assertTrue({'catalog_allocation_mismatch', 'sector_overlap',
                         'referenced_sector_free'} <= codes(manifest))
        disk = Disk().basic()
        disk.sector(17, 0)[0x38 + 4] = 128
        self.assertNotIn('referenced_sector_free', codes(disk.read()[0]))
        disk.ts_list(pairs=((1, 15),))
        self.assertIn('referenced_sector_free', codes(disk.read()[0]))

    def test_text_padding_and_unsupported_types_are_not_decoded(self):
        for file_type, status in ((0, 'no_length_header'), (8, 'unsupported_type'), (3, 'unsupported_type')):
            with self.subTest(file_type=file_type):
                disk = Disk()
                disk.entry(file_type=file_type)
                disk.ts_list()
                block = b'\xc1\x8d\0\0\xc2' + b'\0' * 251
                disk.sector(1, 0)[:] = block
                manifest, artifacts = disk.read()
                entry = manifest['files'][0]
                self.assertEqual(entry['payload_status'], status)
                self.assertEqual(artifacts['files/entry-000/allocated.bin'], block)
                self.assertNotIn('files/entry-000/payload.bin', artifacts)
                if file_type == 0:
                    self.assertEqual(entry['first_nul'], 2)
                    self.assertTrue(entry['nonzero_after_first_nul'])
                else:
                    self.assertIn('unsupported_payload_type', codes(manifest))

    def test_unsupported_geometry_uses_explicit_exceptions(self):
        for size in (0, 143359, 143361, 40 * 16 * 256):
            with self.subTest(size=size), self.assertRaisesRegex(ValueError, '35-track'):
                read_image(bytes(size))
        for offset, value in ((3, 2), (0x27, 121), (0x34, 40), (0x35, 13), (0x36, 128), (0x37, 2)):
            with self.subTest(offset=offset):
                disk = Disk()
                disk.sector(17, 0)[offset] = value
                with self.assertRaisesRegex(ValueError, 'unsupported VTOC'):
                    disk.read()

    def test_optimized_python_retains_external_validation(self):
        script = '''
import importlib.util
import sys
spec = importlib.util.spec_from_file_location('reader', sys.argv[1])
reader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reader)
for data in (b'', bytes(143360)):
    try:
        reader.read_image(data)
    except ValueError:
        pass
    else:
        raise RuntimeError('invalid geometry accepted under optimized Python')
'''
        result = subprocess.run([sys.executable, '-B', '-O', '-c', script, str(READER_PATH)],
                                capture_output=True, text=True, timeout=10,
                                env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
