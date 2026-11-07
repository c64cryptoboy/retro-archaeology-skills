"""Synthetic parser/refusal tests: no compiler/runtime/media bytes."""
import copy
import unittest
from speedcompiler import Decoder,default_profile,sha


def fixture(code=b'\x52',data=b'\0'):
 p=default_profile();start=0x2000;dat=start+13+len(code);end=dat+len(data);base=0x801
 raw=bytearray(end-base)
 raw[0x1efe-base:0x1f00-base]=start.to_bytes(2,'little')
 raw[start-base:]=b'\x78\0\x08\x01\x10'+b'\x78'+(end-255).to_bytes(2,'little')+b'\x01\xff'+b'\x46'+dat.to_bytes(2,'little')+code+data
 p['runtimeSha256']=sha(raw[0x900-base:0x196c-base])
 return base.to_bytes(2,'little')+raw,p


def decode(code=b'\x52',data=b'\0'):
 b,p=fixture(code,data);return Decoder(b,p).decode()


class ParserTests(unittest.TestCase):
 def test_smoke_boundaries(self):
  r=decode(b'\x70HELLO\r\0\x52\x52')
  self.assertEqual([x['mnemonic'] for x in r['instructions']],['CLEAR_RANGE','CLEAR_RANGE','RESTORE_DATA','PRINT_LITERAL','END','END'])
  self.assertEqual(r['instructions'][3]['operands']['payloadHex'],b'HELLO\r'.hex())
 def test_complete_partition(self):
  b,p=fixture();r=Decoder(b,p).decode();regions=r['loadedRegions']
  self.assertEqual(sum(x['end']-x['start'] for x in regions),len(b)-2)
  self.assertTrue(all(x['end']==y['start'] for x,y in zip(regions,regions[1:])))
 def test_runtime_mutation_refuses(self):
  b,p=fixture();bad=bytearray(b);bad[2+0xa00-0x801]^=1
  with self.assertRaisesRegex(ValueError,'signature'):Decoder(bad,p)
 def test_all_odd_values_refuse(self):
  for op in range(1,256,2):
   with self.subTest(op=op),self.assertRaisesRegex(ValueError,'unknown'):decode(bytes([op]))
 def test_extension_refuses(self):
  with self.assertRaisesRegex(ValueError,'unknown'):decode(b'\xfe\x70')
 def test_comparison_masks(self):
  for op in (0x10,0x76,0x7c,0xc2):
   for mask in range(1,8):self.assertEqual(decode(bytes([op,mask,0x52]))['instructions'][3]['operands']['value'],mask)
   for mask in (0,8,255):
    with self.assertRaisesRegex(ValueError,'mask'):decode(bytes([op,mask]))
 def test_counted_string_nul_is_data(self):
  r=decode(b'\xc8\x03A\0B\x52');self.assertEqual(r['instructions'][3]['size'],5)
 def test_unterminated_literal(self):
  with self.assertRaisesRegex(ValueError,'unterminated'):decode(b'\x70HELLO')
 def test_truncated_float(self):
  with self.assertRaises(ValueError):decode(b'\x94\x81\0')
 def test_scalar_slot_bounds(self):
  for code in (b'\xca\x78',b'\x96\x80'):
   with self.assertRaisesRegex(ValueError,'slot'):decode(code)
 def test_target_boundary(self):
  decode(b'\x48\x0d\x20')
  with self.assertRaisesRegex(ValueError,'boundary'):decode(b'\x48\x0e\x20')
 def test_on_targets_and_count_bias(self):
  r=decode(b'\x4c\x03\x0d\x20\x13\x20\x52')
  self.assertEqual(r['instructions'][3]['operands']['targets'],[0x200d,0x2013]);self.assertEqual(r['instructions'][3]['size'],6)
  for n in (0,128):
   with self.assertRaisesRegex(ValueError,'count'):decode(bytes([0x4c,n]))
 def test_typed_data_preserves_numeric_string(self):
  r=decode(data=b'\x02\xff\xff\x01\x02-2\x03\x81\0\0\0\0\0')
  self.assertEqual([d['kind'] for d in r['typedDataRecords']],['integer','string','float','terminator'])
  self.assertEqual(r['typedDataRecords'][0]['operands']['signedValue'],-1)
 def test_unknown_data_and_trailer_refuse(self):
  for data in (b'\x04',b'\0\0',b'\x01\x05x'):
   with self.assertRaises(ValueError):decode(data=data)
 def test_layout_refusals(self):
  b,p=fixture()
  for address,value in [(0x1efd,1),(0x1efe,1),(0x2000,0),(0x2007,0)]:
   bad=bytearray(b);bad[2+address-0x801]=value
   with self.assertRaises(ValueError):Decoder(bad,p)
 def test_extent_refusal(self):
  with self.assertRaises(ValueError):Decoder(b'\x01\x08'+bytes(65536))

if __name__=='__main__':unittest.main()
