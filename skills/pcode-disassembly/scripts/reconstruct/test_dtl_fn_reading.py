"""Authored function-local reading/order/provenance contracts; no title bytes."""
from collections import Counter
from copy import deepcopy
import unittest
import expression_display as d
from dtl_fn_reading import compact_spelling, fold_body
from dtl_reading import instruction_events
from dtl_functions import analyze_functions
from reading_projection import Statement, render_reading
from symbolic import lift, render
from test_dtl_for import instruction, literal, store
from test_dtl_reading import load, fn, binary, basic, reading
from test_dtl_reading_optional import definition


def call(offset=44, name='FN ZX'):
    return instruction('FN_CALL',(b'\xb4'+offset.to_bytes(2,'big')).hex(),
                       {'value':offset,'name':name},grammar='var16',control='descriptor-indirect-call')


def nested(base=0x2000):
    return definition(base, [literal(2),load('K',9),call(),binary('MULTIPLY',3),literal(3),binary('ADD',1)])


def attach_embedded(report, data=b'\x96\xa5ZX(K)\xb22\xac\xa5ZX(K)\xaa3'):
    report=deepcopy(report);rows=report['instructions'];end=rows[0]['targets'][1]
    index=next(i for i,r in enumerate(rows) if r['address']==end)
    island=basic(data);island['address']=end
    island['operands'].update(terminator=58,terminatorAddress=end+island['length'],terminatorOwned=False)
    delimiter=instruction('DELIMITER','3a');delimiter['address']=end+island['length']
    for row in rows[index:]:row['address']+=island['length']+1
    rows[index:index]=[island,delimiter]
    return report


def manual_body(reverse=False, repeated=False):
    """Independent statement tree can intentionally contradict the original order."""
    report=definition(body=[literal(1),call(),literal(2),call(),binary('SUBTRACT',2)])
    rows=report['instructions'];index=analyze_functions(report);definition_=index['definitions'][0]
    c1,c2=rows[2],rows[4];ret=rows[6]
    header=dict(indices=[0],rows=[rows[0]],statement=None,actions=[])
    first=Statement('temporary',(d.call('FN ZX',[d.leaf('1')],origin=c1['address']),),target='T1')
    second=Statement('temporary',(d.call('FN ZX',[d.leaf('2')],origin=c2['address']),),target='T2')
    names=('T2','T1') if reverse else ('T1','T1') if repeated else ('T1','T2')
    result=Statement('fn-return',(d.binary('-',*(d.temporary(n) for n in names),origin=rows[5]['address']),),
                     target='FN ZX',origin=ret['address'])
    body=[dict(indices=[1],rows=rows[1:3],statement=first,actions=[]),
          dict(indices=[2],rows=rows[3:5],statement=second,actions=[]),
          dict(indices=[3],rows=rows[5:7],statement=result,actions=[])]
    calls={c['address']:c for c in index['calls']}
    return header,body,definition_,calls,set(rows[0]['targets']),Counter({'T1':1,'T2':1}),instruction_events


class FunctionReadingTests(unittest.TestCase):
    def test_nested_fn_is_one_deferred_expression_not_callee_inlining(self):
        result=lift('dtl',nested());item=result['readingView']['groups'][0]
        self.assertEqual(item['text'],'DEF FN ZX(K) = 2 * FN ZX(K) + 3')
        self.assertEqual(item['deferredEvaluationOrder'],[0x2009,0x200b,0x200e,0x2010,0x2011])
        self.assertEqual(item['definitionEvaluationOrder'],[0x2000])
        self.assertIsNone(item['evaluationOrder']);self.assertEqual(item['text'].count('FN ZX(K)'),2)
        self.assertIn('T_200B = FN ZX(K)',render(result))

    def test_matching_embedded_definition_is_one_inferred_line(self):
        result=lift('dtl',attach_embedded(nested()));item=result['readingView']['groups'][0]
        self.assertEqual(item['text'],'DEF FN ZX(K) = 2 * FN ZX(K) + 3')
        self.assertEqual(item['kind'],'inferred');self.assertEqual(item['instructionAddresses'][-1],0x2012)
        self.assertEqual(item['definitionEvaluationOrder'],[0x2000,0x2012])
        self.assertEqual(item['definitionRepresentations'],[{'kind':'inferred','address':0x2000},
                                                           {'kind':'embedded','address':0x2012}])
        self.assertIn('[inferred $2000..$2012] DEF FN ZX(K) = 2 * FN ZX(K) + 3\n\n[structural',render_reading(result))
        self.assertIn('DEFFNZX(K)=2*FNZX(K)+3',render(result))

    def test_removed_bookkeeping_is_preserved_as_metadata_and_detailed_warnings(self):
        result=lift('dtl',attach_embedded(nested()));item=result['readingView']['groups'][0]
        self.assertEqual(item['warnings'],[]);self.assertGreater(len(item['detailWarnings']),2)
        self.assertEqual(item['detailWarnings'],list(dict.fromkeys(w for i in item['sourceGroups']
                                                 for w in result['groups'][i]['warnings'])))

    def test_nonmatching_embedded_does_not_supply_or_repair_expression(self):
        result=lift('dtl',attach_embedded(nested(),b'\x96\xa5ZX(K)\xb27'))
        self.assertEqual(result['readingView']['groups'][0]['text'],'DEF FN ZX(K) = 2 * FN ZX(K) + 3')
        self.assertNotIn('coalesce-embedded-function',result['readingView']['counts'])
        self.assertTrue(any(g['kind']=='embedded' for g in result['readingView']['groups']))

    def test_incomplete_or_opaque_body_cannot_borrow_matching_source(self):
        for body in ([call()], [literal(1),fn('USR')]):
            result=lift('dtl',attach_embedded(definition(body=body)))
            self.assertNotIn('single-expression-function',result['readingView']['counts'])
            self.assertNotIn('coalesce-embedded-function',result['readingView']['counts'])

    def test_separately_entered_embedded_definition_stays_separate(self):
        report=attach_embedded(nested());report['instructions'][-1]['targets']=[0x2012]
        result=lift('dtl',report)
        self.assertIn('single-expression-function',result['readingView']['counts'])
        self.assertNotIn('coalesce-embedded-function',result['readingView']['counts'])

    def test_foreign_body_entry_stays_explicit(self):
        report=nested();report['instructions'][-1]['targets']=[0x200b]
        self.assertNotIn('single-expression-function',lift('dtl',report)['readingView']['counts'])

    def test_malformed_nested_call_encoding_and_identity_refuse(self):
        for key,value in (('bytes','b4002d'),('grammar','var8'),('length',2)):
            report=nested();next(r for r in report['instructions'] if r['address']==0x200b)[key]=value
            self.assertNotIn('single-expression-function',lift('dtl',report)['readingView']['counts'])
        report=nested();report['scalars'].append(deepcopy(report['scalars'][0]))
        self.assertNotIn('single-expression-function',lift('dtl',report)['readingView']['counts'])

    def test_different_name_offset_and_relocation(self):
        report=nested(0x3800)
        for scalar in report['scalars']:
            if scalar['offset']==44:scalar.update(offset=58,name='FN M')
        h=report['instructions'][0];h['operands']['descriptorOffset']=55
        raw=bytearray.fromhex(h['bytes']);raw[1:3]=(55).to_bytes(2,'big');h['bytes']=raw.hex()
        for row in report['instructions']:
            if row['mnemonic']=='FN_CALL':
                row['operands'].update(value=58,name='FN M');row['bytes']='b4003a';row['grammar']='var16'
        item=lift('dtl',report)['readingView']['groups'][0]
        self.assertEqual(item['text'],'DEF FN M(K) = 2 * FN M(K) + 3')
        self.assertEqual(item['definitionEvaluationOrder'],[0x3800])

    def test_read_and_multiple_call_order_is_exact(self):
        args=manual_body();fold=fold_body(*args)
        self.assertEqual(fold['text'],'DEF FN ZX(K) = FN ZX(1) - FN ZX(2)')
        self.assertEqual(fold['deferredEvaluationOrder'],[0x2009,0x200d,0x2010,0x2011])
        self.assertIsNone(fold_body(*manual_body(reverse=True)))
        self.assertIsNone(fold_body(*manual_body(repeated=True)))

    def test_additional_consumer_or_unresolved_temporary_refuses(self):
        args=list(manual_body());args[5]['T1']=2;self.assertIsNone(fold_body(*args))
        args=list(manual_body());args[1][-1]['statement']=Statement('fn-return',(d.temporary('OTHER'),),target='FN ZX')
        self.assertIsNone(fold_body(*args))

    def test_function_local_mutable_capture_keeps_read_before_call(self):
        result=lift('dtl',definition(body=[load('Z',16),load('K',9),call(),binary('ADD',1)]))
        item=result['readingView']['groups'][0]
        self.assertEqual(item['text'],'DEF FN ZX(K) = Z + FN ZX(K)')
        self.assertEqual(item['deferredEvaluationOrder'][:3],[0x2008,0x200a,0x200c])
        self.assertIn('T_VALUE_2008',render(result))

    def test_mutating_statement_body_stays_explicit(self):
        result=lift('dtl',definition(body=[literal(1),store(16,'Z',short=True),literal(2)]))
        self.assertNotIn('single-expression-function',result['readingView']['counts'])

    def test_ordinary_outside_fn_call_temporary_is_unchanged(self):
        result=lift('dtl',nested())
        after=[g for g in result['readingView']['groups'] if g['instructionAddresses'][0]>=0x2012]
        self.assertTrue(any(g['text'].startswith('T_') for g in after))
        self.assertTrue(any(g['text'].startswith('Z = T_') for g in after))

    def test_arithmetic_caveats_and_parentheses_remain(self):
        result=lift('dtl',definition(body=[load('K',9),literal(2),literal(3),binary('ADD',1),binary('DIVIDE',4)]))
        item=result['readingView']['groups'][0]
        self.assertEqual(item['text'],'DEF FN ZX(K) = K / (2 + 3)')
        self.assertTrue(any('SI mode' in w for w in item['warnings']))

    def test_island_bytes_text_region_and_location_must_agree(self):
        for change in ('bytes','text','region','location'):
            report=attach_embedded(nested());island=next(r for r in report['instructions'] if r['mnemonic']=='BASIC')
            if change=='bytes':island['bytes']=island['bytes'][:-2]+'34'
            elif change=='text':island['operands']['text']='DEFFNZX(K)=7'
            elif change=='region':island['region']='other'
            else:island['address']+=1
            self.assertNotIn('coalesce-embedded-function',lift('dtl',report)['readingView']['counts'])

    def test_ascii_keyword_lookalike_is_not_a_tokenized_definition(self):
        result=lift('dtl',attach_embedded(nested(),b'DEFFNZX(K)=2*FNZX(K)+3'))
        self.assertNotIn('coalesce-embedded-function',result['readingView']['counts'])

    def test_lexical_match_preserves_quoted_spaces_case_and_grouping(self):
        self.assertEqual(compact_spelling('DEF FN M(X) = X + 1'),'DEFFNM(X)=X+1')
        self.assertNotEqual(compact_spelling('F("A B")'),compact_spelling('F("AB")'))
        self.assertNotEqual(compact_spelling('X + (Y + Z)'),compact_spelling('X + Y + Z'))
        self.assertNotEqual(compact_spelling('X'),compact_spelling('x'))
        self.assertIsNone(compact_spelling('F("oops)'))

    def test_input_original_ownership_and_replay_unchanged(self):
        report=attach_embedded(nested());before=deepcopy(report);result=lift('dtl',report)
        self.assertEqual(report,before);self.assertEqual(result,lift('dtl',report))
        self.assertEqual([r for g in result['groups'] for r in g['instructions']],report['instructions'])
        self.assertEqual([i for g in result['readingView']['groups'] for i in g['sourceGroups']],list(range(len(result['groups']))))
        self.assertEqual([a for g in result['readingView']['groups'] for a in g['instructionAddresses']],
                         [r['address'] for r in report['instructions']])


if __name__=='__main__':unittest.main()
