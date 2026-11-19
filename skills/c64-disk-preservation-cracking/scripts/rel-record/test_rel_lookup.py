"""Original synthetic directory and REL sectors; no disk fixture on the filesystem."""
import unittest

from rel_lookup import lookup

DIR = 361 * 256  # 18/4, after 357 sectors on tracks 1 through 17
ENTRY = DIR + 32
SIDE = 7 * 256
NAME = b'SAMPLE'
WIDTH = 37
PLAIN = bytes((i * 13 + i // 37) % 256 for i in range(15 * WIDTH))


def fixture():
    image = bytearray(174848)
    def put(pos, value):
        image[pos:pos + len(value)] = value

    put(357 * 256, bytes([18, 1, 65]))
    put(358 * 256, bytes([18, 4]))
    put(DIR, bytes([0, 255, 0x82, 1, 1]) + b'OTHER'.ljust(16, b'\xa0'))
    put(ENTRY + 2, bytes([0x84, 1, 20]) + NAME.ljust(16, b'\xa0') + bytes([1, 7, WIDTH]))
    image[ENTRY + 30] = 4
    put(SIDE, bytes([0, 21, 0, WIDTH, 1, 7]))
    put(SIDE + 16, bytes([1, 20, 1, 3, 1, 12]))
    put(20 * 256, bytes([1, 3]) + PLAIN[:254])
    put(3 * 256, bytes([1, 12]) + PLAIN[254:508])
    put(12 * 256, bytes([0, 48]) + PLAIN[508:])
    return image


class NumberedLookup(unittest.TestCase):
    def test_all_records_and_spans(self):
        image = fixture()
        for n in range(1, 16):
            result = lookup(image, NAME, n)
            expected = PLAIN[(n - 1) * WIDTH:n * WIDTH]
            self.assertEqual(bytes.fromhex(result['hex']), expected)
            self.assertEqual(result['count'], 15)
            rebuilt = bytearray()
            for span in result['spans']:
                self.assertEqual(span['record_offset'], len(rebuilt))
                pos = span['image_offset']
                rebuilt.extend(image[pos:pos + span['length']])
            self.assertEqual(rebuilt, expected)
        self.assertEqual(lookup(image, NAME, 7)['spans'], [
            dict(track=1, sector=20, sector_offset=224, image_offset=5344, record_offset=0, length=32),
            dict(track=1, sector=3, sector_offset=2, image_offset=770, record_offset=32, length=5)])

    def test_reorder_even_after_requested_record(self):
        image = fixture()
        image[SIDE + 18:SIDE + 22] = bytes([1, 12, 1, 3])
        with self.assertRaisesRegex(ValueError, 'pointer order'):
            lookup(image, NAME, 1)

    def test_refusals(self):
        for pos, value, message in [
            (SIDE, 1, 'multiple side sectors'), (SIDE + 6, 1, 'multiple side sectors'),
            (SIDE + 1, 19, 'pointer extent'), (SIDE + 1, 20, 'pointer extent'),
            (SIDE + 5, 8, 'self pointer'), (SIDE + 3, 39, 'record length'),
            (ENTRY + 30, 3, 'block count'), (ENTRY + 4, 22, 'pointer order'),
            (3 * 256, 0, 'pointer order or count'), (12 * 256, 1, 'terminal data count'),
            (12 * 256 + 1, 0, 'terminal data count'), (12 * 256 + 1, 47, 'partial record'),
        ]:
            with self.subTest(pos=pos, value=value):
                image = fixture()
                image[pos] = value
                with self.assertRaisesRegex(ValueError, message):
                    lookup(image, NAME, 1)

    def test_source_and_selection_boundaries(self):
        image = fixture()
        for invalid in (image[:-1], image + bytes(683)):
            with self.assertRaisesRegex(ValueError, '174848-byte'):
                lookup(invalid, NAME, 1)
        for n in (0, 16):
            with self.assertRaisesRegex(ValueError, 'outside'):
                lookup(image, NAME, n)
        with self.assertRaisesRegex(ValueError, 'not a closed REL'):
            lookup(image, b'OTHER', 1)
        with self.assertRaisesRegex(ValueError, 'not found'):
            lookup(image, b'sample', 1)


if __name__ == '__main__':
    unittest.main()
