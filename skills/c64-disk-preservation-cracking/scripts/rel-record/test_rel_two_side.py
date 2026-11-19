"""Two linked 1541 side sectors constructed in RAM; no external fixture."""
import unittest

from rel_lookup import lookup

NAME = b'LEDGER'
WIDTH = 73
PLAIN = bytes((i + 17 * (i // 254)) % 256 for i in range(427 * WIDTH))
ENTRY = (357 + 1) * 256  # Slot zero in 18/1
A, B = (7, 5), (7, 9)
PEERS = bytes((*A, *B)) + bytes(8)
# A permutation on tracks 1 through 6, not a physical sort or adjacent sectors.
DATA = [(1 + p // 21, p % 21) for p in (13 * i % 126 for i in range(123))]


def pos(ts):
    t, s = ts  # Only tracks 1 through 7 here, all with 21 sectors.
    return (21 * (t - 1) + s) * 256


def fixture():
    image = bytearray(174848)
    def put(p, data):
        image[p:p + len(data)] = data

    put(357 * 256, bytes([18, 1, 65]))
    put(ENTRY, bytes([0, 255, 0x84, *DATA[0]]) + NAME.ljust(16, b'\xa0') + bytes([*A, WIDTH]))
    put(ENTRY + 30, (123 + 2).to_bytes(2, 'little'))
    put(pos(A), bytes([*B, 0, WIDTH]) + PEERS + bytes(v for ts in DATA[:120] for v in ts))
    put(pos(B), bytes([0, 21, 1, WIDTH]) + PEERS + bytes(v for ts in DATA[120:] for v in ts))
    for i, ts in enumerate(DATA):
        payload = PLAIN[254 * i:254 * (i + 1)]
        link = DATA[i + 1] if i + 1 < len(DATA) else (0, 1 + len(payload))
        put(pos(ts), bytes(link) + payload)
    return image


class TwoSideLookup(unittest.TestCase):
    def test_crossing_and_neighbors(self):
        image = fixture()
        # Byte 30480 splits record 418 into 39 and 34 bytes.  Expected spans
        # are literal coordinates, not taken from the reader's pointer array.
        r = lookup(image, NAME, 418)
        self.assertEqual(r['spans'], [
            dict(track=2, sector=14, sector_offset=217, image_offset=9177, record_offset=0, length=39),
            dict(track=3, sector=6, sector_offset=2, image_offset=12290, record_offset=39, length=34)])
        expected = PLAIN[30441:30514]
        self.assertEqual(bytes.fromhex(r['hex']), expected)
        # Wrong but the same length: skip the first data pointer on side 2.
        self.assertNotEqual(image[9177:9216] + image[15618:15652], expected)
        for n in (1, 417, 419, 427):
            r = lookup(image, NAME, n)
            self.assertEqual(r['count'], 427)
            self.assertEqual(bytes.fromhex(r['hex']), PLAIN[(n - 1) * WIDTH:n * WIDTH])
        with self.assertRaisesRegex(ValueError, 'outside'):
            lookup(image, NAME, 428)

    def test_reorder_index_or_links_only(self):
        for change in ('index', 'links'):
            with self.subTest(change=change):
                image = fixture()
                if change == 'index':
                    image[pos(B) + 16:pos(B) + 20] = bytes((*DATA[121], *DATA[120]))
                else:
                    # Same nodes, same terminal, only the data-chain order differs.
                    for i, j in ((119, 121), (121, 120), (120, 122)):
                        image[pos(DATA[i]):pos(DATA[i]) + 2] = bytes(DATA[j])
                with self.assertRaisesRegex(ValueError, 'pointer order'):
                    lookup(image, NAME, 1)

    def test_replica_must_match_links_not_just_other_copy(self):
        for changed in ((B,), (A, B)):
            with self.subTest(changed=changed):
                image = fixture()
                for ts in changed:
                    image[pos(ts) + 7] = B[1] + 1  # Wrong second member, live link unchanged.
                with self.assertRaisesRegex(ValueError, 'side-sector list'):
                    lookup(image, NAME, 1)

    def test_geometry_and_extents(self):
        for p, data, message in (
                (pos(B) + 2, b'\x00', 'ordinal'), (pos(B) + 3, b'\x24', 'record length'),
                (pos(B), bytes((7, 10)), 'more than two'),
                (pos(B) + 1, b'\x14', 'pointer extent'), (pos(B) + 22, b'\x01', 'pointer extent'),
                (pos(A) + 254, b'\0\0', 'pointer order'), (ENTRY + 30, b'\x7c', 'block count')):
            with self.subTest(p=p, data=data):
                image = fixture()
                image[p:p + len(data)] = data
                with self.assertRaisesRegex(ValueError, message):
                    lookup(image, NAME, 1)


if __name__ == '__main__':
    unittest.main()
