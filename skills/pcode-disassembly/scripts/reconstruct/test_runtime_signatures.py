"""Synthetic runtime-region tests; no commercial bytes or private fixtures."""
import copy
import hashlib
import unittest

from runtime_signatures import RuntimeCatalog, as_prg


def sample():
    raw = bytearray(40)
    raw[4:8] = b'ABCD'
    raw[20:24] = b'EFGH'
    prg = b'\x00\x08' + raw
    entry = {'id': 'synthetic', 'family': 'blitz', 'loadAddress': 0x800,
             'sourceEvidence': [{'path': '/nonexistent/private/provenance'}],
             'windows': [{'start': 0x804, 'end': 0x808,
                          'sha256': hashlib.sha256(b'ABCD').hexdigest()},
                         {'start': 0x814, 'end': 0x818,
                          'sha256': hashlib.sha256(b'EFGH').hexdigest()}]}
    return bytes(prg), {'schema': 'basic-runtime-regions-v1', 'entries': [entry]}


class RuntimeSignatureTests(unittest.TestCase):
    def test_all_regions_and_inert_provenance(self):
        prg, catalog = sample()
        match, = RuntimeCatalog(catalog).match(prg)
        self.assertEqual(match['family'], 'blitz')
        self.assertEqual(len(match['evidence']), 2)
        self.assertEqual(match['role'], 'runtime-component')
        self.assertIsNone(match['layoutValid'])
        self.assertFalse(match['decoderAdmitted'])
        self.assertNotIn('decoderFamily', match)

    def test_each_required_byte(self):
        prg, catalog = sample()
        matcher = RuntimeCatalog(catalog)
        for index in [*range(6, 10), *range(22, 26)]:
            mutated = bytearray(prg)
            mutated[index] ^= 1
            self.assertEqual(matcher.match(mutated), [])

    def test_each_window_truncated(self):
        prg, catalog = sample()
        for size in (9, 25):
            self.assertEqual(RuntimeCatalog(catalog).match(prg[:size]), [])

    def test_bytes_outside_regions_not_used(self):
        prg, catalog = sample()
        mutated = bytearray(prg)
        mutated[-1] ^= 1
        self.assertEqual(RuntimeCatalog(catalog).match(prg), RuntimeCatalog(catalog).match(mutated))
        self.assertNotEqual(hashlib.sha256(prg).digest(), hashlib.sha256(mutated).digest())

    def test_raw_equivalence(self):
        prg, catalog = sample()
        matcher = RuntimeCatalog(catalog)
        self.assertEqual(matcher.match(prg), matcher.match(prg[2:], raw_base=0x800))

    def test_wrong_mapping(self):
        prg, catalog = sample()
        self.assertEqual(RuntimeCatalog(catalog).match(b'\x01\x08' + prg[2:]), [])
        self.assertEqual(RuntimeCatalog(catalog).match(prg[2:], raw_base=0x801), [])

    def test_absolute_window_without_load_constraint(self):
        prg, catalog = sample()
        del catalog['entries'][0]['loadAddress']
        # One preceding loaded byte preserves the actual window addresses.
        self.assertTrue(RuntimeCatalog(catalog).match(b'\xff\x07\x00' + prg[2:]))

    def test_conflicting_families_preserved_and_sorted(self):
        prg, catalog = sample()
        other = copy.deepcopy(catalog['entries'][0])
        other.update(id='aaa', family='petspeed')
        catalog['entries'].append(other)
        matches = RuntimeCatalog(catalog).match(prg)
        self.assertEqual([m['catalogId'] for m in matches], ['aaa', 'synthetic'])

    def test_duplicate_id_rejected(self):
        _, catalog = sample()
        catalog['entries'].append(copy.deepcopy(catalog['entries'][0]))
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            RuntimeCatalog(catalog)

    def test_overlapping_and_empty_windows_rejected(self):
        _, catalog = sample()
        catalog['entries'][0]['windows'].append(catalog['entries'][0]['windows'][0])
        with self.assertRaisesRegex(ValueError, 'overlapping'):
            RuntimeCatalog(catalog)
        catalog['entries'][0]['windows'] = []
        with self.assertRaisesRegex(ValueError, 'empty'):
            RuntimeCatalog(catalog)

    def test_invalid_catalog(self):
        _, catalog = sample()
        catalog['schema'] = 'other'
        with self.assertRaisesRegex(ValueError, 'unsupported'):
            RuntimeCatalog(catalog)
        for key, value in [('start', -1), ('end', 65537), ('sha256', 'bad')]:
            _, catalog = sample()
            catalog['entries'][0]['windows'][0][key] = value
            with self.assertRaises(ValueError):
                RuntimeCatalog(catalog)

    def test_empty_short_and_ordinary_input(self):
        _, catalog = sample()
        matcher = RuntimeCatalog(catalog)
        for prg in (b'', b'\x01', b'\x01\x08', b'\x01\x08BLITZ PETSpeed'):
            self.assertEqual(matcher.match(prg), [])

    def test_extents(self):
        _, catalog = sample()
        matcher = RuntimeCatalog(catalog)
        for prg in (b'\xff\xffAB', b'\x01\x08' + bytes(65536)):
            with self.assertRaisesRegex(ValueError, 'PRG image extent'):
                matcher.match(prg)
        for base, raw in [(-1, b''), (65536, b''), (65535, b'AB')]:
            with self.assertRaisesRegex(ValueError, 'raw image extent'):
                matcher.match(raw, raw_base=base)
        self.assertEqual(as_prg(b'A', 65535), b'\xff\xffA')

    def test_names_not_an_input(self):
        prg, catalog = sample()
        with self.assertRaises(TypeError):
            RuntimeCatalog(catalog).match(prg, filename='BLITZ.prg')


if __name__ == '__main__':
    unittest.main()
