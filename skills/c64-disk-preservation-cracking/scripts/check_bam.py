"""An in-memory 1581 sector exercise, not an image parser.  Run with Python 3."""
import unittest


def block(prefix):
    return bytes(prefix).ljust(256, b'\0')


def fixture(old_slot=0, target=9):
    # Raw BAM rows: one free count and five little-endian bitmap bytes.
    free = bytes.fromhex('28 ff ff ff ff ff')
    low = bytearray(block([40, 2])[:16] + free * 40)
    high = bytearray(block([0, 255])[:16] + free * 40)
    low[16:18] = bytes.fromhex('27 7f')       # 1/7
    low[250:252] = bytes.fromhex('24 f0')    # 40/0 through 40/3
    high[16:19] = bytes.fromhex('26 ff fc')  # 41/8 and 41/9
    directory = bytearray(block([0, 255]))
    for i, (kind, track, sector, name) in enumerate([
        (0x81, 1, 7, b'INDEX'), (old_slot, 41, 8, b'OLD'),
    ]):
        entry = 32 * i
        directory[entry+2:entry+5] = bytes([kind, track, sector])
        directory[entry+5:entry+21] = name.ljust(16, b'\xa0')
        directory[entry+30] = 1
    # Only sectors needed by this example, keyed by decimal (track, sector).
    return {(40, 0): block([40, 3]), (40, 3): bytes(directory),
            (40, 1): bytes(low), (40, 2): bytes(high),
            (1, 7): block(b'\x00\x06IDX' + bytes([41, target])),
            (41, 8): block(b'\x00\x04ABC'), (41, 9): block(b'\x00\x04ABC')}


def ledger(disk):
    used = set()
    for t in range(1, 81):
        half, row = divmod(t - 1, 40)
        p = 16 + 6 * row
        bam = disk[40, 1 + half]
        bits = int.from_bytes(bam[p+1:p+6], 'little')
        if bits.bit_count() != bam[p]:
            raise ValueError('BAM count mismatch')
        used.update((t, s) for s in range(40) if not bits & (1 << s))

    def chain(at):
        seen = set()
        while at[0]:
            if at in seen:
                raise ValueError('cycle')
            seen.add(at)
            yield at
            at = tuple(disk[at][:2])

    header = (40, 0)
    dirs = set(chain(tuple(disk[header][:2])))
    files = set()
    for at in dirs:
        for i in range(0, 256, 32):
            slot = disk[at][i:i+32]
            if slot[2] == 0:
                continue
            if slot[2] != 0x81:
                raise ValueError('only closed SEQ entries in this exercise')
            files.update(chain(tuple(slot[3:5])))
    return used, used - {header, (40, 1), (40, 2)} - dirs - files


def index_target(disk):
    data = disk[1, 7]  # Fixture contract, not a search for T/S-shaped bytes.
    if data[:5] != b'\x00\x06IDX':
        raise ValueError('not the stipulated index record')
    return tuple(data[5:7])


class BamEvidence(unittest.TestCase):
    def test_lost_directory_reference(self):
        before, after = fixture(old_slot=0x81), fixture()
        self.assertEqual([(at, i) for at in before for i in range(256)
                          if before[at][i] != after[at][i]], [((40, 3), 34)])
        expected = {(1, 7), (40, 0), (40, 1), (40, 2), (40, 3), (41, 8), (41, 9)}
        self.assertEqual(ledger(before), (expected, {(41, 9)}))
        self.assertEqual(ledger(after), (expected, {(41, 8), (41, 9)}))

    def test_index_is_independent_of_allocation(self):
        a, b = fixture(), fixture(target=8)
        self.assertEqual([(at, i) for at in a for i in range(256)
                          if a[at][i] != b[at][i]], [((1, 7), 6)])
        self.assertEqual(ledger(a), ledger(b))
        self.assertEqual((index_target(a), index_target(b)), ((41, 9), (41, 8)))
        self.assertEqual(a[41, 8], a[41, 9])


if __name__ == '__main__':
    unittest.main()
