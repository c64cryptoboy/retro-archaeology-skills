"""Original in-memory header fixtures.  No player, tune, or external libraries."""

import io
import unittest

from sid_chip_map import annotate_address, read_chip_map


def header(version, second=0, third=0):
    size = 118 if version == 1 else 124
    fields = bytearray(size)
    fields[:8] = b'PSID' + version.to_bytes(2, 'big') + size.to_bytes(2, 'big')
    fields[14:18] = b'\x00\x01\x00\x01'  # one song, default song one
    if version != 1:
        fields[122:124] = bytes((second, third))
    return bytes(fields)


class ChipMapTests(unittest.TestCase):
    def test_fixed_headers_never_consume_payload(self):
        for version in (1, 2, 3, 4):
            raw = header(version)
            # Looks like SID2/SID3 in v1 if code reads past its shorter header.
            stream = io.BytesIO(raw + b'\0\0\0\0\x42\xe0')
            self.assertEqual(read_chip_map(stream), {'version': version, 'bases': {1: 0xd400}, 'warnings': []})
            self.assertEqual(stream.tell(), len(raw))

    def test_refuse_unknown_layouts_and_short_headers(self):
        raw = header(4)
        for bad in (raw[:7], raw[:-1], b'RSID' + raw[4:], header(5, 0x42, 0xe0),
                    raw[:6] + b'\x00\x76' + raw[8:]):
            with self.assertRaises(ValueError):
                read_chip_map(io.BytesIO(bad))

    def test_reserved_is_not_a_declaration(self):
        for version, bases, count in [(2, {1: 0xd400}, 2), (3, {1: 0xd400, 2: 0xd420}, 1)]:
            result = read_chip_map(io.BytesIO(header(version, 0x42, 0xfe)))
            self.assertEqual(result['bases'], bases)
            self.assertEqual(len(result['warnings']), count)
            self.assertTrue(all('reserved' in w for w in result['warnings']))

    def test_address_windows_and_forbidden_gap(self):
        for raw, base in [(0x42, 0xd420), (0x7e, 0xd7e0), (0xe0, 0xde00), (0xfe, 0xdfe0)]:
            info = read_chip_map(io.BytesIO(header(4, 0, raw)))
            self.assertEqual(info['bases'], {1: 0xd400, 3: base})  # preserve field identity
            self.assertEqual(info['warnings'], [])
        for raw in (0x01, 0x40, 0x41, 0x80, 0xa0, 0xdf, 0xe1, 0xff):
            for second, third in ((raw, 0), (0, raw)):
                info = read_chip_map(io.BytesIO(header(4, second, third)))
                self.assertEqual(info['bases'], {1: 0xd400})
                self.assertEqual(len(info['warnings']), 1)

    def test_duplicate_and_half_block_overlap(self):
        for third, why in ((0x44, 'duplicates'), (0x43, 'unaligned'), (0x45, 'unaligned')):
            info = read_chip_map(io.BytesIO(header(4, 0x44, third)))
            self.assertEqual(info['bases'], {1: 0xd400, 2: 0xd440})
            self.assertIn(why, info['warnings'][0])
        info = read_chip_map(io.BytesIO(header(4, 0x45, 0x44)))  # invalid second cannot mask third
        self.assertEqual(info['bases'], {1: 0xd400, 3: 0xd440})

    def test_slot_order_not_address_order_or_modulo(self):
        bases = read_chip_map(io.BytesIO(header(4, 0xe0, 0x42)))['bases']
        for address, expected in [(0xd400, (1, 1, 'freq_lo')), (0xde04, (2, 1, 'control')),
                                  (0xd424, (3, 1, 'control')), (0xd427, (3, 2, 'freq_lo')),
                                  (0xde14, (2, 3, 'sustain_release')), (0xde15, (2, None, 'cutoff_lo')),
                                  (0xd438, (3, None, 'mode_volume')), (0xd43f, (3, None, 'unused'))]:
            row = annotate_address(bases, address)
            self.assertEqual((row['chip'], row['local_voice'], row['register']), expected)
            self.assertEqual(row['base'] + row['offset'], address)
        for address, region in [(0xd440, 'possible_stock_mirror'), (0xd7ff, 'possible_stock_mirror'),
                                (0xd800, 'outside_declared_blocks'), (0xde20, 'outside_declared_blocks')]:
            self.assertEqual(annotate_address(bases, address), {'address': address, 'region': region})
        self.assertEqual(annotate_address({1: 0xd400}, 0xd424)['region'], 'possible_stock_mirror')


if __name__ == '__main__':
    unittest.main()
