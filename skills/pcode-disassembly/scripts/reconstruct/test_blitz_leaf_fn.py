"""Authored byte/record fixtures only; no compiler, emulator, or PRG execution."""
import copy
import unittest
from formats import decode,profile
from symbolic import lift,render


def fixture(family='blitz',body=bytes.fromhex('80 80 09 39'),continuation=bytes.fromhex('b3 38 00 09 c3 4f')):
    base=0x801;table=profile(family)['dispatch']['startupPointerTable']
    init=table+12;main=init+2
    # X at value offset 2, flagged function slot at 9, Y at 16, A at 23.
    names=(b'X\0',b'\xd3Q',b'Y\0',b'A\0')
    code=bytes([0x37,9,0,2,0,6+len(body)])+body+continuation
    vt=main+len(code);end=vt+7*len(names)
    raw=bytearray(end-base)
    raw[table-base:table-base+12]=b''.join(x.to_bytes(2,'little') for x in (vt,end,end,init,init+1,main))
    raw[init-base:vt-base]=b'\x16\xff'+code
    raw[vt-base:]=b''.join(n+bytes(5) for n in names)
    return decode(base.to_bytes(2,'little')+raw,family)


def output(report,family='blitz'):
    original=copy.deepcopy(report);result=lift(family,report)
    assert report==original,'lifter mutated decoded input'
    assert [r for g in result['groups'] for r in g['instructions']]==report['instructions']
    return result,'\n'.join(g['text'] for g in result['groups'])


class LeafFunctionTests(unittest.TestCase):
    def opaque(self,report,family='blitz'):
        result,text=output(report,family)
        self.assertNotIn('DEF FN F_9(X)',text)
        self.assertIn('REM DEF_FN',text)
        self.assertNotIn('RETURN FN F_9 =',text)
        return result

    def test_declaration_formal_body_return_and_call(self):
        result,text=output(fixture())
        self.assertIn('DEF FN F_9(X); body L_',text)
        self.assertIn('RETURN FN F_9 = (X * X)',text)
        self.assertIn('FN F_9(3)',text)
        human=render(result)
        self.assertIn('Deferred numeric leaf body: skipped',human)
        self.assertIn('synthetic descriptor name',human)
        self.assertIn('Normal return restores X',human)
        self.assertIn('Runtime binding is unproved; call state invalidation is retained.',human)
        self.assertIn('not runnable original BASIC',human)

    def test_austro_identity_and_multiplication_remain_distinct(self):
        r=fixture('austrospeed');result,text=output(r,'austrospeed')
        self.assertEqual(result['family'],'austrospeed')
        self.assertEqual(r['selectedProfile'],'austrospeed-1e-attached-v1')
        self.assertIn('DEF FN F_9(X)',text)
        self.assertIn('RETURN FN F_9 = VM_AUSTRO_MULTIPLY(X, X)',text)
        group=next(g for g in result['groups'] if g['text'].startswith('RETURN FN'))
        self.assertEqual(group['kind'],'partial')
        self.assertIn('unknown stock-BASIC-equivalent multiplication',render(result))

    def test_operand_order_and_parentheses_unchanged(self):
        # Formal - (2 - 3), not (formal - 2) - 3.
        r=fixture(body=bytes.fromhex('80 b2 b3 08 08 39'))
        _,text=output(r)
        self.assertIn('RETURN FN F_9 = (X - (2 - 3))',text)

    def test_leaf_constant_and_negation(self):
        r=fixture(body=bytes.fromhex('b3 39'))
        _,text=output(r);self.assertIn('RETURN FN F_9 = 3',text)
        r=fixture();r['instructions'][3]['mnemonic']='NEGATE'
        self.opaque(r)  # Unary operation leaves too few values for multiplication.

    def test_global_read_is_not_captured_as_formal(self):
        self.opaque(fixture(body=bytes.fromhex('80 82 09 39')))

    def test_calls_and_recursion_in_body_are_opaque(self):
        self.opaque(fixture(body=bytes.fromhex('80 38 00 09 39')))

    def test_unsupported_effects_and_descriptor_reads_are_opaque(self):
        for name in ('PEEK','USR','SYS','STORE_VAR','VAR_DESCRIPTOR','LOAD_ARRAY','OP_UNKNOWN'):
            with self.subTest(name=name):
                r=fixture();r['instructions'][2]['mnemonic']=name
                # Set operands needed by legacy opaque-body processing, where relevant.
                r['instructions'][2].update(descriptorOffset=0,bytes='4c 3a')
                self.opaque(r)

    def test_stack_underflow_and_surplus_are_opaque(self):
        for body in ('09 39','80 80 39','39'):
            with self.subTest(body=body):self.opaque(fixture(body=bytes.fromhex(body)))

    def test_wrong_formal_type_or_name_is_opaque(self):
        for raw,name in (('d8000000000000','X%'),('58800000000000','X$'),('58000000000000','Y')):
            with self.subTest(raw=raw,name=name):
                r=fixture();r.setdefault('scalarRecords',[{}, {}, {}, {}])[0].update(bytes=raw,name=name)
                self.opaque(r)

    def test_descriptor_alignment_bounds_alias_and_initial_binding(self):
        for key,val in (('functionDescriptorOffset',8),('functionDescriptorOffset',999),('functionDescriptorOffset',2),('parameterDescriptorOffset',3)):
            with self.subTest(key=key,value=val):
                r=fixture();r['instructions'][1][key]=val;self.opaque(r)
        r=fixture();r.setdefault('scalarRecords',[{}, {}, {}, {}])[1]['bytes']='d3510000010000';self.opaque(r)

    def test_missing_or_untrusted_table_and_profile_are_opaque(self):
        for mutate in (lambda r:r.pop('scalarRecords',None),lambda r:r.update(selectedProfile='other-revision'),
                       lambda r:r['layout'].update(variableRecordSize=8)):
            r=fixture();mutate(r);self.opaque(r)
        r=fixture();r.setdefault('scalarRecords',[{}, {}, {}, {}])[0]['address']=0;self.opaque(r)
        for raw in ('invalid-hex',None):
            r=fixture();r.setdefault('scalarRecords',[{}, {}, {}, {}])[0]['bytes']=raw;self.opaque(r)

    def test_missing_return_wrong_skip_and_region_are_opaque(self):
        r=fixture();r['instructions'][5]['mnemonic']='RETURN';self.opaque(r)
        r=fixture();r['instructions'][1]['skipTarget']+=1;self.opaque(r)
        r=fixture();r['instructions'][3]['region']='init';self.opaque(r)

    def test_external_entry_to_body_or_return_is_opaque(self):
        for offset in (0,3):
            r=fixture();r['instructions'][-1]['target']=r['instructions'][1]['bodyTarget']+offset;self.opaque(r)

    def test_duplicate_definition_is_not_resolved_lexically(self):
        r=fixture();row=copy.deepcopy(r['instructions'][1]);row['address']=r['instructions'][-1]['address']+1
        r['instructions'].append(row);self.opaque(r)

    def test_opaque_calls_still_kill_earlier_reads(self):
        # A lower Y read precedes the argument.  Unsupported reaching bindings
        # must not retain it merely because a numeric leaf declaration exists.
        r=fixture(continuation=bytes.fromhex('82 b3 38 00 09 07 c3 4f'))
        _,text=output(r)
        self.assertIn('<?> + T_',text)

    def test_family_mismatch_does_not_promote(self):
        self.opaque(fixture('austrospeed'),'blitz')


if __name__=='__main__':unittest.main()
