"""Synthetic post-stage1 grammar tests; no commercial inputs."""
import copy
import json
from pathlib import Path
import unittest
from dtl import Decoder, DecodeError
from test_dtl import fixture

PROFILE=json.loads(Path(__file__).with_name('dtl64_profile-omnibus.json').read_text())


def sample(main):
    raw,p=fixture(main)
    p['opcodes']=copy.deepcopy(PROFILE['opcodes'])
    return raw,p


class OmnibusTests(unittest.TestCase):
    def test_fn_call_big_endian_indirect(self):
        raw,p=sample(b'\xb4\x12\x34')
        r=Decoder(raw,p).decode()['instructions'][-1]
        self.assertEqual(r['length'],3)
        self.assertEqual(r['operands']['value'],0x1234)
        self.assertEqual(r['control'],'descriptor-indirect-call')
        self.assertEqual(r['targets'],[])

    def test_fn_call_truncated(self):
        raw,p=sample(b'\xb4\x12')
        with self.assertRaisesRegex(DecodeError,'truncated'):Decoder(raw,p).decode()

    def test_run_bootstrap_has_no_inline_operand(self):
        raw,p=sample(b'\x58\x81')
        rows=Decoder(raw,p).decode()['instructions']
        self.assertEqual(rows[-2]['length'],1)
        self.assertEqual(rows[-2]['control'],'runtime-managed-transfer')
        self.assertEqual(rows[-1]['operands']['constant'],1)

    def test_sys_tail_ownership(self):
        for tail in (b'',b',1,2,3,4',b',,,9',b',"ABC",1'):
            with self.subTest(tail=tail):
                raw,p=sample(b'\x51'+tail+b':\x81')
                rows=Decoder(raw,p).decode()['instructions']
                self.assertEqual(rows[-2]['length'],len(tail)+2)
                self.assertEqual(rows[-2]['operands']['rawTail'],tail.hex())
                self.assertTrue(rows[-2]['operands']['terminatorOwned'])
                self.assertIn('callee controls',rows[-2]['operands']['returnCaveat'])
                self.assertEqual(rows[-1]['operands']['constant'],1)

    def test_sys_tail_refusal(self):
        for tail in (b',1',b',\0:',b',"A:B":',b'X:'):
            with self.subTest(tail=tail):
                raw,p=sample(b'\x51'+tail)
                with self.assertRaises(DecodeError):Decoder(raw,p).decode()

    def test_target_into_owned_sys_tail_refused(self):
        raw,p=sample(b'\x4f\x03\x51,1:')
        with self.assertRaisesRegex(DecodeError,'boundary'):Decoder(raw,p).decode()

    def test_remaining_unknowns_refuse(self):
        for code in (0x4b,0x56):
            raw,p=sample(bytes([code]))
            with self.subTest(code=code),self.assertRaisesRegex(DecodeError,'unknown operand grammar'):
                Decoder(raw,p).decode()


if __name__=='__main__':unittest.main()
