"""Synthetic Austro adapter/semantic regressions; no commercial runtime bytes."""
import hashlib
import unittest
from formats import profile,decode,inspect
from identify import identify
from symbolic import lift
from test_reconstruct import program,row,texts


def image(code=b'\x4f'):
 base=0x801;table=0x1f79;init=table+12;main=init+2;end=main+len(code)
 raw=bytearray(end-base)
 raw[table-base:table-base+12]=b''.join(v.to_bytes(2,'little') for v in (end,end,end,init,init+1,main))
 raw[init-base:]=b'\x16\xff'+code
 return base.to_bytes(2,'little')+raw


class AustroTests(unittest.TestCase):
 def test_distinct_profile(self):
  self.assertEqual(profile('austrospeed')['dispatch']['startupPointerTable'],0x1f79)
  self.assertEqual(profile('blitz')['dispatch']['startupPointerTable'],0x1f93)
 def test_decode_partition_and_identity(self):
  r=decode(image(),'austrospeed');self.assertEqual([i['mnemonic'] for i in r['instructions']],['INIT_RETURN','END'])
  self.assertEqual(sum(x['end']-x['start'] for x in r['loadedRegions']),len(image())-2)
  self.assertEqual(lift('austrospeed',r)['family'],'austrospeed')
 def test_signature_layout_independent(self):
  b=image();db={'schema':'basic-compiler-identities-v1','fingerprints':[dict(family='austrospeed',role='compiled-object',loadAddress=0x801,start=0x803,end=0x1f79,sha256=hashlib.sha256(b[4:2+0x1f79-0x801]).hexdigest(),check='austrospeed')]}
  self.assertTrue(identify(b,identities=db)['matches'][0]['layoutValid'])
  bad=bytearray(b);bad[0x1f79-0x801+2:0x1f79-0x801+4]=b'\0\0'
  self.assertEqual(identify(bad,identities=db)['family'],'austrospeed')
  self.assertFalse(identify(bad,identities=db)['matches'][0]['layoutValid'])
 def test_truncated_string(self):
  with self.assertRaises(ValueError):decode(image(b'\xe7\x10X'),'austrospeed')
 def test_bad_target(self):
  with self.assertRaises(ValueError):decode(image(b'\x19\x00\x00'),'austrospeed')
 def test_multiply_not_silently_normalized(self):
  r=program('austrospeed',row('CONST_SMALL',2),row('CONST_SMALL',3),row('MULTIPLY'),row('STORE_VAR',variable='X'))
  self.assertIn('VM_AUSTRO_MULTIPLY(2, 3)',texts(r));self.assertTrue(any(g['kind']=='partial' for g in r['groups']))
  b=program('blitz',row('CONST_SMALL',2),row('CONST_SMALL',3),row('MULTIPLY'),row('STORE_VAR',variable='X'))
  self.assertIn('(2 * 3)',texts(b));self.assertNotIn('VM_AUSTRO',texts(b))
 def test_missing_index_is_not_repaired(self):
  r=program('austrospeed',row('CONST_SMALL',0),row('STORE_VAR',variable='I'),row('LOAD_ARRAY',descriptorOffset=7),row('GET'))
  self.assertIn('ELEM_7(<?>)',texts(r));self.assertNotIn('ELEM_7(I)',texts(r))
  self.assertEqual(sum(len(g['instructions']) for g in r['groups']),4)
 def test_oversized(self):
  with self.assertRaises(ValueError):inspect(b'\x01\x08'+bytes(65536),'austrospeed')

if __name__=='__main__':unittest.main()
