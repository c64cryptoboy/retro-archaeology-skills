import unittest

from address_lookup import describe_address


def row(address, raw, mnemonic):
    return dict(address=address, bytes=raw, mnemonic=mnemonic)


def group(*rows, text='X = 1'):
    return dict(instructions=rows, evidenceAddresses=[0x2000], text=text,
                kind='partial', warnings=['unknown channel'])


class AddressLookupTests(unittest.TestCase):
    def setUp(self):
        self.report = dict(family='demo', loadedRegions=[dict(start=0x1000, end=0x1006, name='main')],
                           groups=[group(row(0x1000,'AD 20 33','LOAD'), row(0x1004,'D1','WRITE')),
                                   group(row(0x1005,'FF','END'),text='END')])

    def test_first_middle_and_last_byte_within_an_instruction(self):
        for address, tag in [(0x1000,'instruction start'),(0x1001,'byte +1'),(0x1002,'byte +2')]:
            with self.subTest(address=address):
                text = describe_address(self.report,address)
                self.assertIn(tag+' of $1000 LOAD [AD 20 33]',text)
                self.assertIn('L_1000: [partial] X = 1',text)
                self.assertIn('unknown channel',text)

    def test_second_instruction_same_group_and_adjacent_other_group(self):
        self.assertIn('L_1000: [partial] X = 1',describe_address(self.report,0x1004))
        self.assertIn('L_1005: [partial] END',describe_address(self.report,0x1005))

    def test_holes_region_end_and_nonowning_evidence(self):
        for address, label in [(0x1003,'(main)'),(0x1006,'(outside reported regions)'),
                               (0x2000,'(outside reported regions)')]:
            with self.subTest(address=address):
                text = describe_address(self.report,address)
                self.assertIn('no decoded p-code instruction owns this byte '+label,text)
                self.assertNotIn('X = 1',text)

    def test_cross_group_evidence_is_not_ownership(self):
        self.report['groups'][1]['evidenceAddresses'] = [0x1000]
        text = describe_address(self.report, 0x1002)
        self.assertIn('Other detailed groups citing this instruction: L_1005', text)
        self.assertNotIn('[partial] END', text)
        self.assertNotIn('citing', describe_address(self.report, 0x1004))

    def test_compact_reading_uses_exact_instruction_membership(self):
        self.report['readingView'] = dict(schema='dtl-idiomatic-reading-v1', groups=[dict(
            instructionAddresses=[0x1000, 0x1005], kind='partial', text='B = T',
            warnings=['unknown channel', 'partial type'])])
        text = describe_address(self.report, 0x1001)
        self.assertIn('Compact reading: [partial] B = T', text)
        self.assertIn('partial type', text)
        self.assertEqual(text.count('unknown channel'), 1)
        self.assertNotIn('Compact reading:', describe_address(self.report, 0x1004))

    def test_numbered_lines_only_at_exact_emission_sites(self):
        self.report['readingView'] = dict(schema='petspeed-numbered-reading-v1', lines=[
            dict(number=n, emissionAddress=a, text=t) for n, a, t in [
                (10, None, 'DIM A(2)'), (20, 0x1000, 'X=1'), (30, 0x1000, 'Y=2'),
                (40, 0x1005, 'END')]])
        text = describe_address(self.report, 0x1001)
        self.assertIn('20 X=1', text); self.assertIn('30 Y=2', text)
        self.assertNotIn('10 DIM', text); self.assertNotIn('40 END', text)
        self.assertNotIn('emitted', describe_address(self.report, 0x1004))

    def test_overlap_and_invalid_addresses_refused(self):
        self.report['groups'].append(group(row(0x1001,'E0','OTHER')))
        with self.assertRaisesRegex(ValueError,'ambiguous instruction ownership'):
            describe_address(self.report,0x1001)
        for address in [-1,0x10000]:
            with self.assertRaisesRegex(ValueError,'outside 16-bit'):
                describe_address(self.report,address)
