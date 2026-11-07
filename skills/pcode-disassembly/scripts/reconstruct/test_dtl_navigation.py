"""Authored navigation contracts; no title bytes, runtime execution or source oracle."""
from copy import deepcopy
from fractions import Fraction
import hashlib
import unittest

from dtl_navigation import (annotate_runtime, describe_directive, describe_variable_file,
                            literal_value, record_sys, variable_table_context)
from formats import module, profile
from symbolic import Expr, lift, render
from test_dtl_for import instruction, literal, place, store
from test_reconstruct import program, row


def word(value):
    raw=value.to_bytes(2,'big',signed=True)
    return instruction('INTEGER_WORD','8d'+raw.hex(),
                       {'raw':raw.hex(),'value':int.from_bytes(raw,'big'),'signedValue':value},grammar='u16be')


def byte(value):
    return instruction('INTEGER_BYTE','89'+bytes([value]).hex(),{'raw':bytes([value]).hex(),'value':value},grammar='u8')


def real(packed='9040000000'):
    return instruction('REAL_LITERAL','88'+packed,{'raw':packed,'packedFloat':packed},grammar='float5')


def sys(tail=b''):
    return instruction('SYS','51'+tail.hex()+'3a',
                       {'tail':module('dtl').basic_text(tail,profile('dtl')['basicTokens']),
                        'rawTail':tail.hex(),'terminator':58,'terminatorOwned':True,
                        'returnCaveat':'callee controls text cursor; return not proved'},
                       grammar='sys_basic_tail',control='native-call-dynamic-return')


def directive(selector=2):
    operation=profile('dtl')['opcodes']['5E']['selectors'].get(f'{selector:02X}','unsupported')
    return instruction('DIRECTIVE','5e'+bytes([selector]).hex(),{'selector':selector,'operation':operation},grammar='selector')


def variable_file(payload=b'VARS'):
    return instruction('VARIABLE_FILE',(bytes([0x5b,len(payload)])+payload).hex(),
                       {'count':len(payload),'bytes':payload.hex(),'text':'display not used'},grammar='counted_bytes')


def fixture(*rows, base=0x4000):
    return place([*deepcopy(rows),instruction('END',control='end')],base)


def header_context(flag=1):
    # Authored fake bootstrap with a test-only matching profile, never a shipped payload.
    p=deepcopy(profile('dtl')); h=bytearray(0x86); base=p['layout']['loadAddress']; end=0x1800
    h[:119]=bytes(range(119));p['layout']['bootstrapSha256']=hashlib.sha256(h[:119]).hexdigest()
    h[p['layout']['dataOffset']:p['layout']['dataOffset']+2]=len(h).to_bytes(2,'little')
    h[p['layout']['imageEndOffset']:p['layout']['imageEndOffset']+2]=end.to_bytes(2,'little');h[0x85]=flag
    return {'otherRegions':[{'name':'bootstrap/header','start':base,'end':base+len(h),'bytes':h.hex()},
                            {'name':'trailer','start':end-16,'end':end,'bytes':bytes(16).hex()}]},p


def sites(result):return result['nativeCallIndex']['sites']


class DTLNavigationTests(unittest.TestCase):
    def test_all_profile_directives_named_without_mode_facts(self):
        for selector,operation in profile('dtl')['opcodes']['5E']['selectors'].items():
            r=lift('dtl',fixture(directive(int(selector,16))))
            self.assertIn(operation,r['groups'][0]['text'])
            self.assertEqual(r['groups'][0]['kind'],'structural')
            self.assertFalse(r['runtimeIndex']['modePropagationPerformed'])
            self.assertFalse(r['runtimeIndex']['runtimeIdentityProved'])
            self.assertEqual(r['runtimeIndex']['directives'][0]['status'],'described')

    def test_bad_directive_shapes_remain_generic(self):
        row=fixture(directive())['instructions'][0]
        for change in ({'bytes':'5e03'},{'length':3},{'control':'branch'},{'grammar':'none'},
                       {'targets':[0x4100]},{'opcode':0x5b}, {'operands':{'selector':2,'operation':'enable-stop'}},
                       {'operands':{'selector':True,'operation':'enable-stop'}},{'bytes':'not hex'}):
            with self.subTest(change=change):
                e=describe_directive({**row,**change},profile('dtl'))
                self.assertEqual(e['status'],'refused');self.assertEqual(e['heading'],'REM VM DIRECTIVE')
        self.assertEqual(describe_directive(fixture(directive(6))['instructions'][0],profile('dtl'))['status'],'refused')

    def test_directive_barrier_and_opaque_site_are_unchanged(self):
        r=lift('dtl',fixture(literal(1),directive(2),sys()))
        self.assertEqual(sites(r)[0]['status'],'unresolved-expression')
        self.assertEqual(sites(r)[0]['expression'],'<?>')
        self.assertIn('DIRECTIVE',[s['mnemonic'] for s in r['staticIndex']['opaqueSites']])

    def test_saved_nonzero_flags_inline_not_live_proof(self):
        for flag in (1,2,255):
            report,p=header_context(flag);context=variable_table_context(report,p)
            self.assertEqual(context['status'],'saved-inline');self.assertEqual(context['inlineFlag'],flag)
            self.assertEqual(context['flagAddress'],0x0886)
            self.assertFalse(context['runtimeStateProved']);self.assertFalse(context['initializationProved'])
            self.assertEqual(context['header'],report['otherRegions'][0])
            self.assertEqual(context['trailer'],report['otherRegions'][1])

    def test_zero_flag_is_only_external_eligible(self):
        report,p=header_context(0);c=variable_table_context(report,p)
        self.assertEqual(c['status'],'external-load-eligible')
        self.assertIn('skip/reuse',str(c));self.assertIn('unsupported',str(c['reasons']))

    def test_absent_duplicate_or_wrong_load_context_refused(self):
        report,p=header_context()
        for regions in ([],report['otherRegions'][:1],report['otherRegions']+report['otherRegions'][:1]):
            self.assertEqual(variable_table_context({'otherRegions':regions},p)['status'],'unclassified')
        p['layout']['loadAddress']=0x1001
        self.assertEqual(variable_table_context(report,p)['status'],'unclassified')

    def test_header_hash_extent_data_end_and_trailer_guards(self):
        report,p=header_context()
        changes=[(0,'bytes','00'),(0,'start',0x0800),(0,'end',0x999),(1,'start',0x1000),
                 (1,'bytes','00'),(1,'end',None),(1,'end',65537),(0,'bytes','xx')]
        for index,key,value in changes:
            with self.subTest(index=index,key=key):
                r=deepcopy(report);r['otherRegions'][index][key]=value
                self.assertEqual(variable_table_context(r,p)['status'],'unclassified')
        for offset in (0,p['layout']['dataOffset'],p['layout']['imageEndOffset']):
            r=deepcopy(report);raw=bytearray.fromhex(r['otherRegions'][0]['bytes']);raw[offset]^=1
            r['otherRegions'][0]['bytes']=raw.hex()
            self.assertEqual(variable_table_context(r,p)['status'],'unclassified')

    def test_data_pointer_relative_but_image_end_absolute(self):
        report,p=header_context();header=report['otherRegions'][0]
        raw=bytearray.fromhex(header['bytes']);offset=p['layout']['dataOffset']
        self.assertEqual(int.from_bytes(raw[offset:offset+2],'little'),len(raw))
        self.assertEqual(variable_table_context(report,p)['status'],'saved-inline')
        # The former guard and fixture mistakenly agreed on an absolute DATA word.
        raw[offset:offset+2]=header['end'].to_bytes(2,'little');header['bytes']=raw.hex()
        self.assertEqual(variable_table_context(report,p)['status'],'unclassified')
        report,p=header_context();header=report['otherRegions'][0]
        raw=bytearray.fromhex(header['bytes']);offset=p['layout']['imageEndOffset']
        raw[offset:offset+2]=(report['otherRegions'][1]['end']-header['start']).to_bytes(2,'little')
        header['bytes']=raw.hex()
        self.assertEqual(variable_table_context(report,p)['status'],'unclassified')

    def test_filename_display_escapes_not_injected_lines(self):
        r=fixture(variable_file(b'A"\n\x00\\Z'));result=lift('dtl',r)
        entry=result['runtimeIndex']['variableFiles'][0]
        self.assertEqual(entry['filenameHex'],'41220a005c5a')
        self.assertNotIn('\n',result['groups'][0]['text'])
        self.assertIn('\\n',result['groups'][0]['text']);self.assertIn('\\u0000',result['groups'][0]['text'])
        self.assertIn('not established',result['groups'][0]['text'])

    def test_empty_and_maximum_counted_filenames(self):
        c=variable_table_context({},profile('dtl'))
        for payload in (b'',b'A'*255):
            r=fixture(variable_file(payload))['instructions'][0]
            self.assertEqual(describe_variable_file(r,c)['status'],'described')

    def test_malformed_filename_count_bytes_control_refused(self):
        r=fixture(variable_file())['instructions'][0];c=variable_table_context({},profile('dtl'))
        for change in ({'bytes':'5b03414243'},{'grammar':'none'},{'targets':[0x4000]},
                       {'operands':{**r['operands'],'bytes':'00'}},{'control':'runtime-load'}):
            self.assertEqual(describe_variable_file({**r,**change},c)['status'],'refused')

    def test_runtime_pass_only_changes_two_descriptors(self):
        report=fixture(directive(),variable_file(),literal(2),sys());before=deepcopy(report)
        result=lift('dtl',report);old_groups=deepcopy(result['groups']);h,p=header_context()
        runtime=annotate_runtime({**report,**h},result['groups'],p)
        self.assertEqual(runtime['variableTableContext']['status'],'saved-inline')
        self.assertEqual(result['groups'][2:],old_groups[2:]);self.assertEqual(report,before)
        self.assertIn('normal inline-table path',result['groups'][1]['text'])

    def test_inline_context_copied_not_shared(self):
        report,p=header_context();c=variable_table_context(report,p)
        c['header']['bytes']='changed';self.assertNotEqual(c['header'],report['otherRegions'][0])

    def test_small_byte_signed_word_and_real_integral_literals(self):
        for literal_row,value in ((literal(0),0),(literal(7),7),(byte(255),255),(word(12345),12345),
                                  (real(),49152),(real('907fff0000'),65535),(real('0000000000'),0)):
            with self.subTest(value=value):
                r=lift('dtl',fixture(literal_row,sys()));s=sites(r)[0]
                self.assertEqual(s['status'],'literal-address-candidate');self.assertEqual(s['target'],value)
                self.assertEqual(r['nativeCallIndex']['targets'][0]['target'],value)
                self.assertEqual(r['groups'][0]['text'],'SYS '+str(value))

    def test_negative_fractional_and_out_of_range_literals_not_wrapped(self):
        for value in (word(-1),real('81c0000000'),real('8100000001'),real('9140000000')):
            r=lift('dtl',fixture(value,sys()));self.assertEqual(sites(r)[0]['status'],'unsupported-literal')
            self.assertEqual(r['nativeCallIndex']['targets'],[])

    def test_variable_alias_arithmetic_and_effect_temp_not_folded(self):
        variable=instruction('LOAD_REAL_SCALAR_LONG','940002',{'value':2,'name':'Q'},grammar='var16')
        cases=[(variable,), (literal(1),literal(2),instruction('ADD')),
               (literal(1),instruction('FUNCTION','af20',{'operation':'RND'},grammar='selector'))]
        for rows in cases:
            r=lift('dtl',fixture(*rows,sys()));self.assertIsNone(sites(r)[0]['target'])
        r=lift('dtl',fixture(real(),store(2,'Q'),variable,sys()))
        self.assertEqual(sites(r)[0]['expression'],'Q');self.assertIsNone(sites(r)[0]['target'])
        self.assertEqual(r['groups'][0]['text'],'Q = 49152')

    def test_signed_word_encoding_is_not_unsigned_address(self):
        r=word(-16384);self.assertEqual(r['operands']['value'],49152)
        result=lift('dtl',fixture(r,sys()));self.assertEqual(sites(result)[0]['expression'],'-16384')
        self.assertIsNone(sites(result)[0]['target'])

    def test_same_target_duplicates_keep_regions_and_relocated_sites(self):
        for base in (0x1000,0x5100):
            report=fixture(real(),sys(),real(),sys(),base=base)
            report['instructions'][0]['region']=report['instructions'][1]['region']='init'
            r=lift('dtl',report);t=r['nativeCallIndex']['targets'][0]
            self.assertEqual(len(t['callers']),2)
            self.assertEqual(t['callers'],[{'address':base+6,'region':'init'},{'address':base+14,'region':'main'}])

    def test_target_sort_and_call_site_order_independent(self):
        r=lift('dtl',fixture(word(300),sys(),byte(8),sys(),word(300),sys()))
        self.assertEqual([t['target'] for t in r['nativeCallIndex']['targets']],[8,300])
        self.assertEqual([s['target'] for s in sites(r)],[300,8,300])

    def test_join_region_and_prior_sys_kill_target_facts(self):
        for kind in ('entry','region'):
            report=fixture(real(),sys())
            if kind=='entry':report['instructions'][-1]['targets']=[report['instructions'][1]['address']]
            else:report['instructions'][1]['region']='init'
            self.assertIsNone(sites(lift('dtl',report))[0]['target'])
        r=lift('dtl',fixture(real(),sys(),sys()))
        self.assertEqual(sites(r)[0]['target'],49152);self.assertIsNone(sites(r)[1]['target'])

    def test_tail_and_return_caveat_retained_but_not_executed(self):
        report=fixture(real(),sys(b',A,"Q"'))
        r=lift('dtl',report);s=sites(r)[0]
        self.assertEqual(s['target'],49152);self.assertEqual(s['operands'],report['instructions'][1]['operands'])
        self.assertEqual(r['groups'][0]['text'],'SYS 49152,A,"Q"')
        self.assertIn('callee controls',s['returnCaveat']);self.assertFalse(r['nativeCallIndex']['returnPairingProved'])

    def test_malformed_sys_tail_or_shape_is_refused(self):
        report=fixture(real(),sys());producer,call=report['instructions'][:2]
        e=Expr('49152',{producer['address']},stable=True,producer=producer['address'])
        for change in ({'bytes':'5100'},{'control':'fallthrough'},{'grammar':'none'},{'targets':[0x4000]},
                       {'operands':{**call['operands'],'tail':'wrong'}},
                       {'operands':{**call['operands'],'terminatorOwned':False}},
                       {'operands':{**call['operands'],'rawTail':'00'}}):
            self.assertEqual(record_sys({**call,**change},e,{producer['address']:producer})['status'],'refused')
        for tail in (b'A',b',\0',b',"',b',":"'):
            bad=fixture(real(),sys(tail))
            self.assertEqual(sites(lift('dtl',bad))[0]['status'],'refused')

    def test_inconsistent_literal_evidence_does_not_group(self):
        for producer in (literal(2),byte(33),word(300),real()):
            for change in ({'bytes':'00'},{'length':99},{'grammar':'invalid-grammar'},{'targets':[0x4200]}):
                with self.subTest(producer=producer['mnemonic'],change=change):
                    self.assertIsNone(literal_value({**producer,**change}))
            changed=deepcopy(producer)
            for key in ('constant','value','signedValue'):
                if key in changed['operands']:changed['operands'][key]+=1
            if 'packedFloat' in changed['operands']:changed['operands']['packedFloat']='0000000000'
            self.assertIsNone(literal_value(changed))

    def test_expression_dependency_identity_guard(self):
        report=fixture(real(),sys());producer,call=report['instructions'][:2];a=producer['address']
        for e in (Expr('49152',{a,a+1},stable=True,producer=a),Expr('49152',{a},producer=a),
                  Expr('49152',{a},('uncertain',),stable=True,producer=a),
                  Expr('49152',{a},reference=True,stable=True,producer=a),
                  Expr('49152',{a},stable=True,producer=None)):
            self.assertIsNone(record_sys(call,e,{a:producer})['target'])
        e=Expr('49153',{a},stable=True,producer=a)
        self.assertEqual(record_sys(call,e,{a:producer})['status'],'refused')

    def test_replay_input_ownership_and_copied_provenance(self):
        report=fixture(directive(),variable_file(),real(),sys());before=deepcopy(report)
        r=lift('dtl',report);self.assertEqual(r,lift('dtl',report));self.assertEqual(report,before)
        self.assertEqual([i for g in r['groups'] for i in g['instructions']],report['instructions'])
        s=sites(r)[0];self.assertEqual(s['producerSite']['bytes'],'889040000000')
        s['operands']['tail']='changed';self.assertEqual(report,before)

    def test_render_contains_scopes_and_unresolved_expressions(self):
        r=lift('dtl',fixture(directive(),variable_file(),real(),sys(),sys()));text=render(r)
        for expected in ('DTL RUNTIME DIRECTIVES','DTL SYS LITERAL TARGETS','Candidate $C000',
                         'UNGROUPED SYS','<?>','not a complete native call graph','live flags'):
            self.assertIn(expected,text)

    def test_other_families_do_not_receive_indexes(self):
        r=program('blitz',row('CONST_U8',value=1),row('END'))
        self.assertNotIn('runtimeIndex',r);self.assertNotIn('nativeCallIndex',r)

    def test_directive_does_not_propagate_stop_or_poke_modes(self):
        r=lift('dtl',fixture(directive(2),directive(5),real(),sys()))
        self.assertEqual(sites(r)[0]['target'],49152)
        self.assertEqual(r['groups'][2]['text'],'SYS 49152')
        self.assertEqual(list(r['runtimeIndex'].keys()),['schema','scope','variableTableContext','directives','variableFiles',
                                                       'modePropagationPerformed','runtimeIdentityProved'])

    def test_exact_real_value_not_float_rounding(self):
        self.assertEqual(literal_value(real('8100000001')),Fraction((1<<31)+1,1<<31))
        self.assertEqual(literal_value(real()),Fraction(49152))


if __name__=='__main__':unittest.main()
