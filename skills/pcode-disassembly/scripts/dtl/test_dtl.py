import copy
import json
from pathlib import Path
import unittest

from dtl import Decoder, DecodeError, sha, render, basic_text


PROFILE=json.loads(Path(__file__).with_name('dtl64_profile.json').read_text())


def fixture(main=b'\x00\x80', init=b'\x54\x5b\x01V\x57', scalars=b''):
    p=copy.deepcopy(PROFILE)
    p['layout']['bootstrapSha256']=sha(bytes(0x77))
    data=bytearray(0x87)+init+main+b'\0\0\0'
    variables=0x801+len(data)
    data+=scalars
    array=0x801+len(data)
    data+=b'\0\0\x04\0'
    data+=int(array+255).to_bytes(2,'little')+int(variables+255).to_bytes(2,'little')+b'\xff\xff'+bytes(10)
    for off,value in [(0x7a,0x87),(0x7c,0x87),(0x7e,0x87+len(init)),(0x82,0x801+len(data))]:
        data[off:off+2]=value.to_bytes(2,'little')
    return b'\x01\x08'+data,p


def lmap(*rows):
    return b''.join(a.to_bytes(2,'big')+b.to_bytes(2,'big') for a,b in rows)


class Tests(unittest.TestCase):
    def test_smoke_regions_and_determinism(self):
        raw,p=fixture()
        report=Decoder(raw,p).decode(lmap((10,0),(0xff00,2)),'10 END\n')
        self.assertEqual([r['bytes'] for r in report['regions']],[5,2])
        self.assertEqual(report,Decoder(raw,p).decode(lmap((10,0),(0xff00,2)),'10 END\n'))
        self.assertIn('10 END',render(report))
        self.assertEqual(report['instructions'][-1]['operands']['text'],'END')

    def test_unknown_opcode(self):
        raw,p=fixture(b'\xff')
        with self.assertRaisesRegex(DecodeError,'unknown operand grammar'):
            Decoder(raw,p).decode()

    def test_undefined_selector(self):
        raw,p=fixture(b'\x5e\xff')
        with self.assertRaisesRegex(DecodeError,'unknown selector'):
            Decoder(raw,p).decode()

    def test_truncated_selector(self):
        raw,p=fixture(b'\x5e')
        with self.assertRaisesRegex(DecodeError,'truncated'):
            Decoder(raw,p).decode()

    def test_truncated_counted(self):
        raw,p=fixture(init=b'\x5b\x05X')
        with self.assertRaisesRegex(DecodeError,'truncated'):
            Decoder(raw,p).decode()

    def test_bad_bootstrap(self):
        raw,p=fixture(); raw=raw[:2]+b'\x01'+raw[3:]
        with self.assertRaisesRegex(DecodeError,'bootstrap'):
            Decoder(raw,p)

    def test_wrong_end(self):
        raw,p=fixture(); raw=bytearray(raw); raw[0x84]^=1
        with self.assertRaisesRegex(DecodeError,'end word'):
            Decoder(raw,p)

    def test_wrong_padding(self):
        raw,p=fixture(); d=Decoder(raw,p); raw=bytearray(raw)
        raw[d.code_end-d.base+2]=1
        with self.assertRaisesRegex(DecodeError,'separator'):
            Decoder(raw,p)

    def test_quotes_protect_colon(self):
        raw,p=fixture(b'\x00\x99"A:B"\x3a\x00\x80')
        rows=Decoder(raw,p).decode()['instructions']
        self.assertEqual(rows[3]['operands']['text'],'PRINT"A:B"')
        self.assertEqual(rows[4]['mnemonic'],'DELIMITER')

    def test_unmodeled_basic(self):
        raw,p=fixture(b'\x00\x8fREM')
        with self.assertRaisesRegex(DecodeError,'unmodeled interpreter'):
            Decoder(raw,p).decode()

    def test_duplicate_map_offsets(self):
        raw,p=fixture()
        maps=Decoder(raw,p).decode(lmap((10,0),(20,0),(0xff00,2)))['sourceMap']
        self.assertEqual(len(maps),3)
        self.assertEqual(maps[0]['address'],maps[1]['address'])

    def test_interior_map_is_evidence_not_length(self):
        raw,p=fixture(b'\x00\x99"X"')
        maps=Decoder(raw,p).decode(lmap((10,0),(20,2),(0xff00,5)))['sourceMap']
        self.assertFalse(maps[1]['instructionBoundary'])
        self.assertEqual(maps[1]['owningInstruction'],maps[0]['address'])

    def test_bad_maps(self):
        raw,p=fixture()
        for data in [b'\0',lmap((10,0)),lmap((0xff00,0),(10,0)),lmap((10,1),(20,0),(0xff00,2)),lmap((10,0),(0xff00,3))]:
            with self.subTest(data=data),self.assertRaises(DecodeError):
                Decoder(raw,p).decode(data)

    def test_duplicate_supplied_source(self):
        raw,p=fixture()
        with self.assertRaisesRegex(DecodeError,'duplicate supplied'):
            Decoder(raw,p).decode(lmap((10,0),(0xff00,2)),'10 END\n10 END\n')

    def test_u16_big_endian(self):
        raw,p=fixture(b'\x8d\x12\x34')
        p['opcodes']['8D'].update(grammar='u16be',mnemonic='TEST')
        row=Decoder(raw,p).decode()['instructions'][-1]
        self.assertEqual(row['operands']['value'],0x1234)

    def test_target_validation(self):
        raw,p=fixture(b'\x48\x00\x00\x00\x80')
        p['opcodes']['48'].update(grammar='xor_target',mnemonic='TEST')
        d=Decoder(raw,p); start=d.main
        raw=bytearray(raw); pos=start-d.base+2
        raw[pos+1:pos+3]=bytes([(start+3)>>8 ^ 255,(start+3)&255 ^ 255])
        report=Decoder(raw,p).decode()
        self.assertEqual(report['instructions'][3]['targets'],[start+3])
        raw[pos+2]^=2  # target interior of branch
        with self.assertRaisesRegex(DecodeError,'boundary'):
            Decoder(raw,p).decode()

    def test_native_order_asymmetric_branch_keys_and_pointer_biases(self):
        # Independent encoding from the native accepted-identity path:
        # trailer[4] is identity low / target-high XOR; trailer[5] is
        # identity high / target-low XOR. The same bytes offset array and
        # scalar pointer words respectively. Do not use Decoder.target here.
        for identity in (0x2402,0x1234,0xffff):
            with self.subTest(identity=f'{identity:04X}'):
                high,low=identity>>8,identity&255
                main=0x801+0x87+5  # fixture's 5-byte init, independent of decoder
                dest=[main+12,main+6,main,main+3,main+16]
                encode=lambda address: bytes(((address>>8)^low,(address&255)^high))
                code=(b'\x48'+encode(dest[0])+b'\x4a'+encode(dest[1])+
                      b'\x4d\x04'+encode(dest[2])+encode(dest[3])+
                      b'\x4e\x02'+encode(dest[4])+b'\x80')
                raw,p=fixture(code,scalars=b'A\0'+bytes(5))
                raw=bytearray(raw)
                array=int.from_bytes(raw[-16:-14],'little')-255
                variables=int.from_bytes(raw[-14:-12],'little')-255
                raw[-16:-14]=(array+low).to_bytes(2,'little')
                raw[-14:-12]=(variables+high).to_bytes(2,'little')
                raw[-12:-10]=bytes((low,high))
                d=Decoder(raw,p)
                self.assertEqual((d.array,d.variables),(array,variables))
                self.assertEqual(d.names[2],'A')
                rows=d.decode()['instructions'][3:]
                self.assertEqual([r['targets'] for r in rows],
                                 [[dest[0]],[dest[1]],dest[2:4],[dest[4]],[]])
                self.assertEqual([r['mnemonic'] for r in rows],
                                 ['GOTO','GOSUB','ON_GOTO','ON_GOSUB','INTEGER_SMALL'])
                raw[2+0x87+5+1:2+0x87+5+3]=encode(main+1)
                with self.assertRaisesRegex(DecodeError,'boundary'):
                    Decoder(raw,p).decode()

    def test_asymmetric_branch_operand_truncation(self):
        for code in (b'\x48\x09',b'\x4a\x09',b'\x4d\x04\x09\x08'):
            with self.subTest(code=code):
                raw,p=fixture(code)
                raw=bytearray(raw); raw[-12:-10]=b'\x02\x24'
                # Pointer bases use the same identity bytes, independently
                # of which bytes XOR the two halves of a branch address.
                raw[-16:-14]=(int.from_bytes(raw[-16:-14],'little')-255+2).to_bytes(2,'little')
                raw[-14:-12]=(int.from_bytes(raw[-14:-12],'little')-255+36).to_bytes(2,'little')
                with self.assertRaisesRegex(DecodeError,'truncated'):
                    Decoder(raw,p).decode()

    def test_odd_on_table(self):
        raw,p=fixture(b'\x4d\x01\0')
        p['opcodes']['4D'].update(grammar='target_table',mnemonic='TEST')
        with self.assertRaisesRegex(DecodeError,'odd'):
            Decoder(raw,p).decode()

    def test_scalars(self):
        raw,p=fixture(scalars=b'A\0'+bytes(5)+b'\xc2\x80'+bytes(5)+b'C\x80'+bytes(5))
        report=Decoder(raw,p).decode()
        self.assertEqual([s['name'] for s in report['scalars']],['A','B%','C$'])
        self.assertEqual([s['offset'] for s in report['scalars']],[2,9,16])

    def test_negative_word(self):
        raw,p=fixture(b'\x8d\xff\xfe')
        row=Decoder(raw,p).decode()['instructions'][-1]
        self.assertEqual(row['operands']['signedValue'],-2)

    def test_function_selector_limit(self):
        raw,p=fixture(b'\xb8\x1c')
        with self.assertRaisesRegex(DecodeError,'unknown selector'):
            Decoder(raw,p).decode()

    def test_system_function_order(self):
        self.assertEqual(PROFILE['opcodes']['B8']['selectors']['1A'],'ST')
        self.assertEqual(PROFILE['opcodes']['B8']['selectors']['18'],'TI')
        self.assertEqual(PROFILE['opcodes']['B8']['selectors']['19'],'TI$')

    def test_fn_header_truncated_and_bad_skip(self):
        for code in [b'\x53\0',b'\x53\0\x02\0\x08\0\x09\x07']:
            raw,p=fixture(code)
            with self.assertRaises(DecodeError): Decoder(raw,p).decode()

    def test_sys_tail_refused(self):
        raw,p=fixture(b'\x51\x2c')
        with self.assertRaisesRegex(DecodeError,'SYS tail'):
            Decoder(raw,p).decode()

    def test_count_wrap_refused(self):
        raw,p=fixture(b'\x8a\xff'+bytes(255))
        with self.assertRaisesRegex(DecodeError,'overflowing'):
            Decoder(raw,p).decode()

    def test_trailer_and_external_layout_refused(self):
        raw,p=fixture(); raw=bytearray(raw); raw[-16:-14]=b'\0\0'
        with self.assertRaisesRegex(DecodeError,'regions'):
            Decoder(raw,p)

    def test_bad_scalar_stride(self):
        raw,p=fixture(scalars=b'X')
        with self.assertRaisesRegex(DecodeError,'scalar'):
            Decoder(raw,p)

    def test_tokenizer_data_rem_and_quotes(self):
        self.assertEqual(basic_text(b'\x83\x99: \x99',PROFILE['basicTokens']),'DATA{$99}: PRINT')
        self.assertEqual(basic_text(b'\x8f\x99',PROFILE['basicTokens']),'REM{$99}')


if __name__=='__main__': unittest.main()
