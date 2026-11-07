"""Authored variable-input navigation, not target execution or alias resolution."""
from copy import deepcopy
import unittest
from dtl_navigation import analyze_variable_sys, scalar_sys_identity
from symbolic import lift, render
from test_dtl_for import instruction, literal, place, store
from test_dtl_navigation import sys, real, directive
from test_reconstruct import program, row


def scalar(offset=2, name='Q', kind='real', address=0x6200):
    base_name = name.removesuffix('%')
    a = ord(base_name[0]); b = ord(base_name[1]) if len(base_name) == 2 else 0
    if kind == 'integer': a |= 128; b |= 128
    return dict(offset=offset, name=name, type=kind, address=address,
                raw=bytes([a,b,0,0,0,0,0]).hex())


def load(offset=2, name='Q', kind='real', short=True):
    width = 1 if short else 2
    opcode = (0x90 if kind == 'real' else 0x91) + (0 if short else 4)
    raw = offset.to_bytes(width,'big')
    return instruction('LOAD_'+kind.upper()+'_SCALAR'+('' if short else '_LONG'),
                       (bytes([opcode])+raw).hex(), {'value':offset,'name':name,'raw':raw.hex()},
                       grammar='var8' if short else 'var16')


def fixture(*ops, scalars=None, base=0x4000):
    return place([*deepcopy(ops), instruction('END', control='end')], base,
                 deepcopy([scalar()] if scalars is None else scalars))


def index(report): return lift('dtl',report)['nativeVariableIndex']
def associated(result): return [s for s in result['sites'] if s['status']=='associated']


class DTLVariableSysTests(unittest.TestCase):
    def test_four_numeric_load_forms_and_relocation(self):
        for kind,name in [('real','AZ'),('integer','P2%')]:
            for short,offset in [(True,23),(False,723)]:
                for base in (0x0900,0x4800):
                    with self.subTest(kind=kind,short=short,base=base):
                        report=fixture(load(offset,name,kind,short),sys(),base=base,
                                       scalars=[scalar(offset,name,kind)])
                        result=lift('dtl',report); found=result['nativeVariableIndex']
                        self.assertEqual(len(associated(found)),1)
                        v=found['variables'][0]
                        self.assertEqual((v['namespace'],v['type'],v['offset'],v['name']),('scalar',kind,offset,name))
                        self.assertEqual(v['callers'],[{'address':base+(2 if short else 3),'region':'main','producerAddress':base}])
                        self.assertIsNone(result['nativeCallIndex']['sites'][0]['target'])
                        self.assertEqual(result['nativeCallIndex']['targets'],[])

    def test_repeated_calls_keep_regions_and_site_order(self):
        report=fixture(load(),sys(),load(),sys())
        report['instructions'][0]['region']=report['instructions'][1]['region']='init'
        found=index(report)
        self.assertEqual(len(found['variables']),1)
        self.assertEqual([c['region'] for c in found['variables'][0]['callers']],['init','main'])
        self.assertEqual(len(associated(found)),2)

    def test_same_name_different_offsets_not_merged(self):
        report=fixture(load(9),sys(),load(2),sys(),load(9),sys(),scalars=[scalar(2),scalar(9,address=0x6207)])
        found=index(report)
        self.assertEqual([v['offset'] for v in found['variables']],[2,9])
        self.assertEqual([len(v['callers']) for v in found['variables']],[1,2])
        self.assertEqual([s['variable']['offset'] for s in found['sites']],[9,2,9])

    def test_object_identity_never_shared(self):
        a=index(fixture(load(),sys()))
        b=index(fixture(load(name='Z'),sys(),scalars=[scalar(name='Z')]))
        self.assertEqual(a['variables'][0]['name'],'Q')
        self.assertEqual(b['variables'][0]['name'],'Z')
        self.assertEqual(len(b['variables'][0]['callers']),1)

    def test_assignment_identifies_fresh_read_not_assigned_address(self):
        r=lift('dtl',fixture(real(),store(2,'Q'),load(),sys()))
        self.assertEqual(r['groups'][0]['text'],'Q = 49152')
        self.assertEqual(r['nativeVariableIndex']['variables'][0]['name'],'Q')
        self.assertIsNone(r['nativeCallIndex']['sites'][0]['target'])
        self.assertEqual(r['nativeCallIndex']['targets'],[])

    def test_variable_assignment_does_not_follow_alias(self):
        r=lift('dtl',fixture(load(9,'R'),store(2,'Q'),load(),sys(),scalars=[scalar(),scalar(9,'R')]))
        self.assertEqual(r['groups'][0]['text'],'Q = R')
        self.assertEqual([v['name'] for v in r['nativeVariableIndex']['variables']],['Q'])

    def test_literals_remain_only_in_original_numeric_index(self):
        r=lift('dtl',fixture(real(),sys(),load(),sys()))
        self.assertEqual(r['nativeCallIndex']['targets'][0]['target'],49152)
        self.assertEqual(len(r['nativeVariableIndex']['sites']),1)
        self.assertEqual(len(associated(r['nativeVariableIndex'])),1)

    def test_missing_duplicate_and_type_mismatched_records(self):
        for records in ([],[scalar(),scalar()], [scalar(kind='integer',name='Q%')]):
            with self.subTest(records=records):
                self.assertEqual(associated(index(fixture(load(),sys(),scalars=records))),[])

    def test_record_raw_name_type_shape_and_address_guards(self):
        changes=[{'raw':None},{'raw':'zz'},{'raw':'5100'},{'raw':'52800000000000'},
                 {'raw':'d1000000000000'},{'raw':'52000000000000'}, {'name':'Q\nX'},
                 {'name':'A23'},{'type':'string'},{'address':None},{'address':65530}]
        for change in changes:
            with self.subTest(change=change):
                found=index(fixture(load(),sys(),scalars=[{**scalar(),**change}]))
                self.assertEqual(associated(found),[])
                self.assertTrue(found['sites'][0]['reasons'])

    def test_operand_name_and_consumed_expression_must_agree(self):
        report=fixture(load(name='Z'),sys())
        self.assertEqual(associated(index(report)),[])
        report=fixture(load(),sys()); native=lift('dtl',report)['nativeCallIndex']
        native['sites'][0]['expression']='Z'
        self.assertEqual(associated(analyze_variable_sys(report,native)),[])

    def test_malformed_numeric_load_encodings_refuse(self):
        for short in (True,False):
            producer=load(short=short)
            changes=[{'bytes':'00'},{'length':99},{'opcode':0x92},{'grammar':'none'},
                     {'control':'branch'},{'targets':[0x4000]},
                     {'operands':{**producer['operands'],'value':True}},
                     {'operands':{**producer['operands'],'value':3}},
                     {'operands':{**producer['operands'],'raw':'ff'}}]
            for change in changes:
                with self.subTest(short=short,change=change):
                    identity,reason=scalar_sys_identity({'scalars':[scalar()]},{**producer,**change})
                    self.assertIsNone(identity);self.assertTrue(reason)

    def test_string_array_and_function_producers_not_numeric_variables(self):
        for name,raw,grammar in [('LOAD_STRING_SCALAR','9202','var8'),
                                 ('LOAD_REAL_ARRAY','9802','array8'),
                                 ('FN_CALL','b40002','var16')]:
            identity,reason=scalar_sys_identity({'scalars':[scalar()]},instruction(name,raw,{'value':2,'name':'Q'},grammar=grammar))
            self.assertIsNone(identity);self.assertTrue(reason)

    def test_arithmetic_effect_and_unknown_arguments_unassociated(self):
        cases=[(load(),literal(1),instruction('ADD')),
               (load(),instruction('FUNCTION','af20',{'operation':'RND'},grammar='selector')),
               (literal(1),instruction('FUNCTION','af21',{'operation':'PEEK'},grammar='selector')),
               ()]
        for ops in cases:
            with self.subTest(ops=ops):
                self.assertEqual(associated(index(fixture(*ops,sys()))),[])

    def test_join_region_and_barrier_cleared_facts_not_recovered(self):
        for mode in ('entry','region','directive','prior-sys'):
            report=fixture(load(),sys())
            if mode=='entry':report['instructions'][-1]['targets']=[report['instructions'][1]['address']]
            elif mode=='region':report['instructions'][1]['region']='init'
            elif mode=='directive':report=fixture(load(),directive(),sys())
            else:report=fixture(load(),sys(),sys())
            found=index(report)
            self.assertEqual(len(associated(found)),1 if mode=='prior-sys' else 0)
            if mode=='prior-sys':self.assertEqual(found['sites'][-1]['status'],'unassociated')

    def test_nonadjacent_producer_with_intact_metadata_still_refused(self):
        report=fixture(load(),sys());native=lift('dtl',report)['nativeCallIndex']
        report['instructions'][0]['address']-=1
        original=native['sites'][0];original['producerAddress']-=1
        original['expressionDependencies']=[original['producerAddress']]
        original['producerSite']['address']-=1
        self.assertEqual(associated(analyze_variable_sys(report,native)),[])

    def test_metadata_warnings_dependencies_and_source_provenance_refuse(self):
        report=fixture(load(),sys());native=lift('dtl',report)['nativeCallIndex']
        changes=[{'expressionWarnings':['uncertain']},{'expressionDependencies':[]},
                 {'expressionDependencies':[0x4000,0x4001]},{'producerAddress':None},
                 {'producerSite':None},{'status':'refused'},{'bytes':'5100'}]
        for change in changes:
            with self.subTest(change=change):
                altered=deepcopy(native);altered['sites'][0].update(change)
                self.assertEqual(associated(analyze_variable_sys(report,altered)),[])
        altered=deepcopy(native);altered['sites'][0]['producerSite']['bytes']='9003'
        self.assertEqual(associated(analyze_variable_sys(report,altered)),[])

    def test_malformed_sys_and_duplicate_row_identity_refused(self):
        report=fixture(load(),sys());report['instructions'][1]['operands']['tail']='wrong'
        self.assertEqual(associated(index(report)),[])
        report=fixture(load(),sys());native=lift('dtl',report)['nativeCallIndex']
        report['instructions'].append(deepcopy(report['instructions'][0]))
        self.assertEqual(associated(analyze_variable_sys(report,native)),[])

    def test_no_input_native_index_or_existing_groups_mutation(self):
        report=fixture(load(),sys(b',A,"Q"'));before=deepcopy(report)
        r=lift('dtl',report);native=deepcopy(r['nativeCallIndex']);groups=deepcopy(r['groups'])
        found=analyze_variable_sys(report,r['nativeCallIndex'])
        self.assertEqual(report,before);self.assertEqual(r['nativeCallIndex'],native);self.assertEqual(r['groups'],groups)
        found['variables'][0]['scalarRecord']['raw']='changed'
        found['sites'][0]['sysSite']['operands']['tail']='changed'
        self.assertEqual(report,before);self.assertEqual(r['nativeCallIndex'],native)
        self.assertEqual(r['groups'][0]['text'],'SYS Q,A,"Q"')
        self.assertIn('callee controls',r['nativeCallIndex']['sites'][0]['returnCaveat'])

    def test_replay_owned_rows_and_scope_rendering(self):
        report=fixture(load(),sys());r=lift('dtl',report)
        self.assertEqual(r,lift('dtl',report))
        self.assertEqual([i for g in r['groups'] for i in g['instructions']],report['instructions'])
        found=r['nativeVariableIndex']
        for field in ('numericTargetsResolved','runtimeBindingProved','returnPairingProved'):self.assertFalse(found[field])
        for text in ('DTL SYS INPUT VARIABLES','numeric target unresolved','mutable variable','Variable Q'):
            self.assertIn(text,render(r))
        self.assertEqual(r['nativeCallIndex']['sites'][0]['status'],'unresolved-expression')

    def test_other_families_unchanged(self):
        r=program('blitz',row('CONST_U8',value=1),row('END'))
        self.assertNotIn('nativeVariableIndex',r)


if __name__=='__main__':unittest.main()
