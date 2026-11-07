"""Authored DTL local FOR contracts; no target execution or source oracle."""
from copy import deepcopy
import unittest
from dtl_for import zero_candidates
from symbolic import lift, render
from test_reconstruct import program, row


def instruction(name, raw='00', operands=None, grammar='none', control='fallthrough', **kw):
    return dict(mnemonic=name, bytes=raw, length=len(bytes.fromhex(raw)), operands=operands or {},
                grammar=grammar, control=control, region='main', targets=[], **kw)


def literal(n=0):
    return instruction('INTEGER_SMALL', bytes([0x80+n]).hex(), {'constant': n})


def store(offset=394, name='Q', kind='real', short=False):
    opcode = (0xd0 if kind=='real' else 0xd1) + (0 if short else 4)
    width = 1 if short else 2
    return instruction('STORE_'+kind.upper()+'_SCALAR'+('' if short else '_LONG'),
                       (bytes([opcode])+offset.to_bytes(width,'big')).hex(), {'value':offset,'name':name},
                       grammar='var8' if short else 'var16')


def loop(offset=394, name='Q', kind='real', step=False):
    opcode = (0x42 if kind=='real' else 0x44) + bool(step)
    return instruction('FOR_'+kind.upper()+('_STEP' if step else ''),
                       (bytes([opcode])+offset.to_bytes(2,'big')).hex(), {'value':offset,'name':name},
                       grammar='var16', control='loop-runtime')


def fixture(*middle, offset=394, name='Q', kind='real', step=False, short=False, base=0x4000, initial=0):
    rows = [literal(initial), store(offset,name,kind,short), *deepcopy(middle), loop(offset,name,kind,step),
            instruction('NEXT','46',control='loop-runtime'), instruction('END',control='end')]
    return place(rows, base, [{'offset':offset,'name':name,'type':kind}])


def place(rows, base=0x4000, scalars=None):
    for r in rows:
        r['address']=base; base+=r['length']
    return {'instructions': rows, 'scalars': scalars or []}


def group(result, prefix='FOR '):
    return next(g for g in result['groups'] if g['text'].startswith(prefix))


def recoveries(result):
    return [x['limitRecovery'] for x in result['forIndex']['loops'] if x['limitRecovery']]


class DTLForTests(unittest.TestCase):
    def assert_no_zero(self, report):
        result=lift('dtl',report)
        self.assertEqual(recoveries(result), [])
        return result

    def test_zero_long_store_unit_real_and_exact_evidence(self):
        report=fixture(); before=deepcopy(report); result=lift('dtl',report)
        self.assertEqual(group(result)['text'],'FOR Q = Q TO 0 STEP 1')
        self.assertEqual(result['coverage']['partial'],0)
        self.assertEqual(result['groups'][0]['text'],'Q = 0')
        self.assertEqual(len(recoveries(result)),1)
        self.assertEqual(group(result)['evidenceAddresses'],[r['address'] for r in report['instructions'][:3]])
        self.assertIn('completed-initialization',str(group(result)['warnings']))
        self.assertEqual(report,before)
        self.assertEqual([r for g in result['groups'] for r in g['instructions']],report['instructions'])
        self.assertEqual(lift('dtl',report),result)
        self.assertIn('DTL FOR INITIALIZER PROVENANCE',render(result))

    def test_relocation_names_and_offsets_do_not_select_title(self):
        for base,offset,name in [(0x800,2,'AZ'),(0x5700,1211,'P'),(0x2200,65535,'ZZ')]:
            with self.subTest(base=base,offset=offset):
                r=lift('dtl',fixture(base=base,offset=offset,name=name))
                self.assertEqual(group(r)['text'],f'FOR {name} = {name} TO 0 STEP 1')
                self.assertEqual(recoveries(r)[0]['offset'],offset)

    def test_provenance_does_not_repeat_initializer(self):
        r=lift('dtl',fixture(literal(7),initial=2)); e=r['forIndex']['loops'][0]
        self.assertEqual(e['status'],'associated')
        self.assertEqual([g['text'] for g in r['groups']][:2],['Q = 2','FOR Q = Q TO 7 STEP 1'])
        self.assertIn('not repeated or moved',str(group(r)['warnings']))
        self.assertEqual(recoveries(r),[])

    def test_provenance_can_leave_missing_limit_unknown(self):
        r=self.assert_no_zero(fixture(initial=3))
        self.assertEqual(r['forIndex']['loops'][0]['status'],'associated')
        self.assertEqual(group(r)['text'],'FOR Q = Q TO <?> STEP 1')

    def test_integer_and_explicit_step_provenance_not_zero_rules(self):
        for kind in ('real','integer'):
            for step in (False,True):
                values=[literal(5)]+([literal(2)] if step else [])
                r=self.assert_no_zero(fixture(*values,kind=kind,step=step,name='Z%' if kind=='integer' else 'Z'))
                self.assertEqual(r['forIndex']['loops'][0]['status'],'associated')
                self.assertIn('TO 5 STEP '+('2' if step else '1'),group(r)['text'])

    def test_short_store_provenance_only(self):
        r=self.assert_no_zero(fixture(offset=9,short=True))
        self.assertEqual(r['forIndex']['loops'][0]['status'],'associated')
        self.assertIn('TO <?>',group(r)['text'])

    def test_no_zero_for_integer_or_step_entry(self):
        for options in ({'kind':'integer'},{'step':True},{'kind':'integer','step':True}):
            self.assert_no_zero(fixture(**options))

    def test_nonzero_and_computed_zero_not_carried(self):
        for n in (1,2,7): self.assert_no_zero(fixture(initial=n))
        r=fixture();r['instructions'].insert(1,literal())
        r['instructions'].insert(2,instruction('SUB'))
        place(r['instructions'],scalars=r['scalars'])
        self.assert_no_zero(r)

    def test_other_zero_encoding_is_not_assumed(self):
        r=fixture();r['instructions'][0]=instruction('REAL_LITERAL','000000000000',{'packedFloat':'0000000000'})
        place(r['instructions'],scalars=r['scalars']);self.assert_no_zero(r)

    def test_extra_lower_expression_refuses_even_with_triple(self):
        r=fixture();r['instructions'].insert(0,literal(7));place(r['instructions'],scalars=r['scalars'])
        self.assert_no_zero(r)

    def test_same_display_name_different_offset_not_associated(self):
        r=fixture();r['instructions'][1]=store(401)
        place(r['instructions'],scalars=r['scalars']);result=self.assert_no_zero(r)
        self.assertEqual(result['forIndex']['loops'][0]['status'],'unassociated')

    def test_absent_ambiguous_or_mismatched_scalar_identity(self):
        for records in ([],[{'offset':394,'type':'integer'}],
                        [{'offset':394,'type':'real'},{'offset':394,'type':'real'}]):
            r=fixture();r['scalars']=records;result=self.assert_no_zero(r)
            self.assertEqual(result['forIndex']['loops'][0]['status'],'unassociated')

    def test_store_and_for_alternate_entries_refuse(self):
        for i in (1,2):
            r=fixture();r['instructions'][-1]['targets']=[r['instructions'][i]['address']]
            result=self.assert_no_zero(r)
            self.assertEqual(result['forIndex']['loops'][0]['status'],'unassociated')

    def test_operand_interior_entry_refuses(self):
        r=fixture();r['instructions'][-1]['targets']=[r['instructions'][1]['address']+1]
        self.assert_no_zero(r)

    def test_entry_at_literal_is_allowed_local_reset(self):
        r=fixture();r['instructions'][-1]['targets']=[r['instructions'][0]['address']]
        self.assertEqual(len(recoveries(lift('dtl',r))),1)

    def test_region_and_noncontiguous_triples_refuse(self):
        for i in (1,2):
            r=fixture();r['instructions'][i]['region']='init';self.assert_no_zero(r)
        r=fixture();r['instructions'][1]['address']+=1;self.assert_no_zero(r)

    def test_malformed_shapes_refuse_without_guessing(self):
        for i,key,value in [(0,'bytes','81'),(0,'length',2),(0,'grammar','u8'),
                            (0,'control','call'),(1,'bytes','d4018b'),(1,'grammar','var8'),
                            (1,'control','call'),(2,'bytes','43018a'),(2,'length',4),
                            (2,'grammar','var8'),(2,'control','fallthrough')]:
            with self.subTest(i=i,key=key):
                r=fixture();r['instructions'][i][key]=value;self.assert_no_zero(r)

    def test_literal_operand_mismatch_refuses(self):
        r=fixture();r['instructions'][0]['operands']['constant']=1;self.assert_no_zero(r)

    def test_intervening_delimiter_prevents_provenance_and_zero(self):
        r=self.assert_no_zero(fixture(instruction('DELIMITER','3b')))
        self.assertEqual(r['forIndex']['loops'][0]['status'],'unassociated')

    def test_effect_temporary_not_skipped_or_hoisted(self):
        r=self.assert_no_zero(fixture(literal(1),instruction('FUNCTION','fa00',{'operation':'RND'})))
        self.assertEqual(r['forIndex']['loops'][0]['status'],'unassociated')
        text=[g['text'] for g in r['groups']]
        self.assertEqual(text[0],'Q = 0');self.assertIn(' = RND(1)',text[1]);self.assertTrue(text[2].startswith('FOR Q'))
        self.assertEqual(sum('RND(' in t for t in text),1)

    def test_opaque_usr_does_not_create_initializer_link(self):
        r=self.assert_no_zero(fixture(literal(1),instruction('FUNCTION','fa00',{'operation':'USR'})))
        self.assertEqual(r['forIndex']['loops'][0]['status'],'unassociated')

    def test_zero_fact_does_not_escape_to_next_store_or_for(self):
        r=fixture();rows=r['instructions'];rows[3:3]=[store(),loop()]
        place(rows,scalars=r['scalars']);result=lift('dtl',r)
        self.assertEqual(len(recoveries(result)),1)
        self.assertEqual(len([g for g in result['groups'] if 'TO <?>' in g['text']]),1)

    def test_index_explicitly_does_not_pair_next_or_prove_reachability(self):
        r=lift('dtl',fixture());self.assertFalse(r['forIndex']['nextPairingProved'])
        self.assertFalse(r['forIndex']['runtimeReachabilityProved'])
        self.assertEqual(group(r,'NEXT')['text'],'NEXT')
        self.assertNotIn('matchedFor',str(r['forIndex']))

    def test_other_family_does_not_inherit_dtl_index(self):
        r=program('blitz',row('CONST_U8',value=0),row('END'))
        self.assertNotIn('forIndex',r)


if __name__=='__main__': unittest.main()
