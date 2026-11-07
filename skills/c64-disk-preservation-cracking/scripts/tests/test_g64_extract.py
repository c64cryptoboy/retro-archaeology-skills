"""Portable standard-GCR regressions for the sibling g64_extract module.

18 original regressions plus five independently encoded boundary regressions.
No disks or private fixtures are required. Containers use temporary directories.
Independent fixture coordinates/encoder/checksums are construction-derived.
"""
import hashlib
import sys
import tempfile
import unittest
from functools import reduce
from operator import xor
from pathlib import Path

# Support direct execution and unittest discovery from any working directory.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import g64_extract as g

ENC = {value: code for code, value in g.GCR_TO_NIBBLE.items()}
PREFIX = '01' * 32


def encode(raw):
    return ''.join(f'{ENC[v >> 4]:05b}{ENC[v & 15]:05b}' for v in raw)


def header(track=1, sector=0, bad_checksum=False):
    fields = bytes([sector, track, 0x42, 0x41])
    check = g.xor_bytes(fields) ^ int(bad_checksum)
    return '1' * 40 + encode(bytes([8, check]) + fields + b'\x0f\x0f') + '01' * 24


def data(payload=bytes(range(256)), padding='valid', bad_checksum=False):
    assert len(payload) == 256
    check = g.xor_bytes(payload) ^ int(bad_checksum)
    trailer = encode(b'\0\0') if padding == 'valid' else '0' * 20
    return '1' * 40 + encode(b'\x07' + payload + bytes([check])) + trailer + '01' * 32


def pack(bits):
    bits += '0' * (-len(bits) % 8)
    return bytes(int(bits[i:i + 8], 2) for i in range(0, len(bits), 8))


def bitstring(raw):
    return ''.join(f'{v:08b}' for v in raw)


def image(raw):
    return (b'GCR-1541' + bytes([0, 1]) + len(raw).to_bytes(2, 'little')
            + (20).to_bytes(4, 'little') + (3).to_bytes(4, 'little')
            + len(raw).to_bytes(2, 'little') + raw)


def cases():
    """Discriminating fixtures also used by the separate old/new comparison."""
    return {
        'ordinary': pack(PREFIX + header() + data()),
        'invalid_unused_padding': pack(PREFIX + header() + data(padding='invalid')),
        'adjacent_headers': pack(PREFIX + header() + header(sector=1) + data()),
        'unknown_sync': pack(PREFIX + header() + '1' * 40 + '0' * 80 + data()),
        'rejected_data_then_next_sector': pack(PREFIX + header() + data(b'A' * 256, 'invalid')
                                              + header(sector=1) + data(b'B' * 256)),
        'circular_pair': pack(PREFIX + data() + header()),
        'bad_data_checksum': pack(PREFIX + header() + data(bad_checksum=True)),
    }


class DecodeTrackTests(unittest.TestCase):
    def test_ordinary_sector_exact_fields(self):
        got, = g.decode_track(cases()['ordinary'], 6)
        self.assertEqual((got.track, got.sector, got.data, got.physical_slot),
                         (1, 0, bytes(range(256)), 6))
        # The alternating gap's last one joins the following 40-one sync run.
        self.assertEqual((got.header_bit, got.data_bit, got.disk_id_hex), (63, 231, '4241'))
        self.assertTrue(got.header_checksum_valid and got.data_checksum_valid)

    def test_unused_invalid_padding(self):
        got, = g.decode_track(cases()['invalid_unused_padding'], 0)
        self.assertEqual(got.data, bytes(range(256)))
        self.assertTrue(got.data_checksum_valid)

    def test_adjacent_headers_never_borrow(self):
        got = g.decode_track(cases()['adjacent_headers'], 0)
        self.assertEqual([(s.track, s.sector) for s in got], [(1, 1)])

    def test_unknown_sync_breaks_pairing(self):
        self.assertEqual(g.decode_track(cases()['unknown_sync'], 0), [])

    def test_rejected_padding_cannot_shift_payloads(self):
        got = g.decode_track(cases()['rejected_data_then_next_sector'], 0)
        self.assertEqual({s.sector: s.data for s in got}, {0: b'A' * 256, 1: b'B' * 256})

    def test_circular_header_data_pair(self):
        got, = g.decode_track(cases()['circular_pair'], 0)
        self.assertEqual(got.data, bytes(range(256)))
        self.assertGreater(got.header_bit, got.data_bit)

    def test_circular_rotations_and_original_bit_coordinates(self):
        raw = pack(PREFIX + header() + data(padding='invalid')
                   + header(sector=1) + data(b'Z' * 256))
        bits = bitstring(raw)
        original = {s.sector: s for s in g.decode_track(raw, 4)}
        cuts = {0, 1, 7, 8, 63, 64, 65, 102, 104, 160, 200, 220, 1001, len(bits) - 1}
        for s in original.values():
            for start in (s.header_bit, s.data_bit):
                cuts.update((start + delta) % len(bits) for delta in (-1, 1, 7, 20, 39, 40, 41))
        for cut in sorted(cuts):
            with self.subTest(cut=cut):
                got = g.decode_track(pack(bits[cut:] + bits[:cut]), 4)
                self.assertEqual(len(got), 2)
                for s in got:
                    before = original[s.sector]
                    self.assertEqual(s.data, before.data)
                    self.assertEqual(s.header_bit, (before.header_bit - cut) % len(bits))
                    self.assertEqual(s.data_bit, (before.data_bit - cut) % len(bits))
                    self.assertTrue(s.header_checksum_valid and s.data_checksum_valid)

    def test_invalid_essential_gcr_refused(self):
        block = data()
        block = block[:50] + '00000' + block[55:]
        self.assertEqual(g.decode_track(pack(PREFIX + header() + block), 0), [])

    def test_unknown_marker_refused(self):
        block = '1' * 40 + encode(b'\x06' + bytes(257)) + '01' * 32
        self.assertEqual(g.decode_track(pack(PREFIX + header() + block), 0), [])

    def test_bad_header_checksum_retained_but_require_refuses(self):
        got, = g.decode_track(pack(PREFIX + header(bad_checksum=True) + data()), 0)
        self.assertFalse(got.header_checksum_valid)
        self.assertTrue(got.data_checksum_valid)
        with self.assertRaisesRegex(g.G64Error, 'invalid header checksum'):
            g.require_sector({(1, 0): got}, 1, 0)

    def test_bad_data_checksum_retained_but_require_refuses(self):
        got, = g.decode_track(cases()['bad_data_checksum'], 0)
        self.assertTrue(got.header_checksum_valid)
        self.assertFalse(got.data_checksum_valid)
        with self.assertRaisesRegex(g.G64Error, 'invalid data checksum'):
            g.require_sector({(1, 0): got}, 1, 0)

    def test_missing_sector_refused(self):
        with self.assertRaisesRegex(g.G64Error, 'missing standard sector'):
            g.require_sector({}, 1, 0)

    def test_empty_no_sync_and_all_ones(self):
        for raw in (b'', bytes(400), b'\x55' * 400, b'\xff' * 400):
            with self.subTest(length=len(raw), first=raw[:1]):
                self.assertEqual(g.decode_track(raw, 0), [])

    def test_unpaired_header_or_data(self):
        for bits in (PREFIX + header(), PREFIX + data()):
            self.assertEqual(g.decode_track(pack(bits), 0), [])


class ContainerTests(unittest.TestCase):
    def read_image(self, content):
        with tempfile.TemporaryDirectory(prefix='g64-test-') as directory:
            path = Path(directory) / 'synthetic.g64'
            path.write_bytes(content)
            return g.read_g64(path)

    def test_valid_container(self):
        sectors, meta = self.read_image(image(cases()['ordinary']))
        self.assertEqual(g.require_sector(sectors, 1, 0).data, bytes(range(256)))
        self.assertEqual(meta['decodedSectorCount'], 1)
        self.assertEqual(meta['slots'][0]['speed'], 3)

    def test_bad_magic_version_and_tables(self):
        good = image(cases()['ordinary'])
        for content, message in ((b'', 'not a GCR'), (b'x' + good[1:], 'not a GCR'),
                                 (good[:8] + b'\x01' + good[9:], 'unsupported G64'),
                                 (good[:12], 'truncated G64')):
            with self.subTest(message=message), self.assertRaisesRegex(g.G64Error, message):
                self.read_image(content)

    def test_outside_offset_and_truncated_track(self):
        good = image(cases()['ordinary'])
        outside = good[:12] + (len(good) + 1).to_bytes(4, 'little') + good[16:]
        for content, message in ((outside, 'points outside'), (good[:-1], 'invalid track length')):
            with self.subTest(message=message), self.assertRaisesRegex(g.G64Error, message):
                self.read_image(content)

    def test_empty_track(self):
        sectors, meta = self.read_image(image(b''))
        self.assertEqual(sectors, {})
        self.assertEqual(meta['slots'][0]['decodedSectors'], 0)



# Independently constructed boundary fixtures (separate encoder and XOR).
CODES = (0b01010, 0b01011, 0b10010, 0b10011,
         0b01110, 0b01111, 0b10110, 0b10111,
         0b01001, 0b11001, 0b11010, 0b11011,
         0b01101, 0b11101, 0b11110, 0b10101)
PAYLOAD = bytes([((i * 37 + 11) % 256) ^ (0xA6 if i == 137 else 0) for i in range(256)])
CHECKSUM = reduce(xor, PAYLOAD, 0)
RECORDS = []

def independent_gcr(raw):
    return ''.join(format(CODES[n], '05b') for byte in raw for n in (byte >> 4, byte & 15))

def independent_pack(bits):
    assert len(bits) % 8 == 0
    return int(bits, 2).to_bytes(len(bits)//8, 'big') if bits else b''

def independent_header_bytes(sector=3, bad_checksum=False):
    fields = bytes((sector,17,0x32,0x71))
    return bytes((8,reduce(xor,fields,0) ^ int(bad_checksum))) + fields + bytes((15,15))

def independent_header(sector=3, bad_checksum=False):
    return '1'*10 + independent_gcr(independent_header_bytes(sector,bad_checksum))

def independent_data():
    return '1'*10 + independent_gcr(bytes((7,)) + PAYLOAD + bytes((CHECKSUM,)))

def independent_ring(parts):
    bits = '0'*16 + ('0'*16).join(parts) + '0'*16
    return bits + '0'*(-len(bits)%8)

def independent_decode(label,bits,cut=0):
    raw=independent_pack(bits[cut:]+bits[:cut])
    got=g.decode_track(raw,19)
    RECORDS.append(dict(case=label,cut=cut,trackBits=len(bits),inputSha256=hashlib.sha256(raw).hexdigest(),
                        sectors=[dict(track=s.track,sector=s.sector,headerBit=s.header_bit,dataBit=s.data_bit,
                                      headerChecksum=s.header_checksum_valid,dataChecksum=s.data_checksum_valid,
                                      payloadSha256=hashlib.sha256(s.data).hexdigest()) for s in got]))
    return got

class IndependentBoundaryTests(unittest.TestCase):
    def test_minimum_sync_exact_258_bytes_and_known_coordinates_under_rotations(self):
        bits=independent_ring([independent_header(),independent_data()])
        # H sync 16; 10 sync+80 header+16 gap => D sync 122.
        # D body begins132, checksum final symbol2707..2711; end2712.
        self.assertEqual((len(bits),CHECKSUM),(2728,0xA6))
        cuts=(0,1,7,8,15,16,17,24,25,26,27,103,104,105,106,121,
              122,123,130,131,132,133,137,138,139,140,1000,2706,2707,2711,2712,2727)
        for cut in cuts:
            with self.subTest(cut=cut):
                got,=independent_decode('minimum-sync-exact-essential',bits,cut)
                self.assertEqual((got.track,got.sector,got.physical_slot,got.disk_id_hex),(17,3,19,'3271'))
                self.assertEqual(got.data,PAYLOAD)
                self.assertEqual((got.header_bit,got.data_bit),((16-cut)%2728,(122-cut)%2728))
                self.assertTrue(got.header_checksum_valid and got.data_checksum_valid)

    def test_last_essential_symbol_refused_but_unused_bits_not_decoded(self):
        bits=independent_ring([independent_header(),independent_data()])
        good,=independent_decode('zero-unused-trailer',bits)
        self.assertEqual(good.data,PAYLOAD)
        # Last nibble of essential checksum, NOT either unused trailer byte.
        broken=bits[:2707]+'00000'+bits[2712:]
        self.assertEqual(independent_decode('invalid-final-checksum-symbol',broken),[])
        for cut in (2708,2710,2727):
            self.assertEqual(independent_decode('invalid-checksum-symbol-wrapped',broken,cut),[])

    def test_invalid_header_and_unknown_marker_are_immediate_barriers(self):
        invalid=independent_header(4)
        # Corrupt a field in header's required first eight decoded bytes.
        invalid=invalid[:35]+'00000'+invalid[40:]
        unknown='1'*10+independent_gcr(bytes((6,))+bytes(7))
        for label,block in (('invalid-header',invalid),('unknown-marker',unknown)):
            bits=independent_ring([independent_header(),block,independent_data()])
            for cut in (0,16,120,len(bits)-4):
                with self.subTest(label=label,cut=cut):
                    self.assertEqual(independent_decode(label,bits,cut),[])

    def test_bad_checksum_header_does_not_fall_back_to_prior_good_header(self):
        bits=independent_ring([independent_header(3),independent_header(4,bad_checksum=True),independent_data()])
        for cut in (0,125,len(bits)-5):
            got,=independent_decode('bad-checksum-immediate-header',bits,cut)
            self.assertEqual(got.sector,4)
            self.assertFalse(got.header_checksum_valid)
            self.assertTrue(got.data_checksum_valid)
            self.assertEqual(got.data,PAYLOAD)
            with self.assertRaisesRegex(g.G64Error,'invalid header checksum'):
                g.require_sector({(17,4):got},17,4)

    def test_no_legal_circular_pair_and_below_sync_threshold(self):
        unknown='1'*10+'0'*80
        for label,parts in (('two-headers',[independent_header(3),independent_header(4)]),
                            ('two-data',[independent_data(),independent_data()]),
                            ('barriers-across-seam',[unknown,independent_data(),independent_header(),unknown]),
                            ('header-sync-nine-ones',[independent_header()[1:],independent_data()]),
                            ('data-sync-nine-ones',[independent_header(),independent_data()[1:]])):
            bits=independent_ring(parts)
            for cut in (0,20,len(bits)-3):
                with self.subTest(label=label,cut=cut):
                    self.assertEqual(independent_decode(label,bits,cut),[])


if __name__ == '__main__':
    unittest.main()
