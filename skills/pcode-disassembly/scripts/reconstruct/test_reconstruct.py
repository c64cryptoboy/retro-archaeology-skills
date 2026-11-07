"""Synthetic tests; no commercial bytes or target preimages are bundled."""
import copy
import hashlib
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch
from formats import blitz_layout, profile, decode, inspect
from identify import identify
import reconstruct as reconstruction
from symbolic import lift, quoted, number, render


def row(name,value=None,**kw):
    operands=kw.pop('operands',{})
    if value is not None:operands['value']=value
    # BLITZ keeps scalar immediates at row level; other cores use operands.
    return {'mnemonic':name,'bytes':'00','size':1,'grammar':'none','operands':operands,'value':value,**kw}


def program(family,*rows):
    return lift(family,{'instructions':[{'address':0x1000+i,**r} for i,r in enumerate(rows)]})


def texts(result):return '\n'.join(g['text'] for g in result['groups'])


def store(family='petspeed'):
    return row('STORE_FAC_VAR',operands={'variable':0x2800}) if family=='petspeed' else row('STORE_FAC',0x300)


def toy_blitz(trailer=b'',code=b'\x4f'):
    base=0x801;table=8083;init=table+12;main=init+2;vt=main+len(code)
    raw=bytearray(vt-base)
    raw[table-base:table-base+12]=b''.join(x.to_bytes(2,'little') for x in (vt,vt,vt,init,init+1,main))
    raw[init-base:]=bytes([0x16,0xff])+code
    return base.to_bytes(2,'little')+raw+trailer


class IdentificationTests(unittest.TestCase):
    def db(self,*families):
        return {'schema':'basic-compiler-identities-v1','fingerprints':[{'family':f,'role':'runtime-library','loadAddress':0x801,'start':0x801,'end':0x805,'sha256':hashlib.sha256(b'test').hexdigest()} for f in families]}

    def test_known_hash_not_filename(self):
        r=identify(b'\x01\x08test',identities=self.db('blitz'))
        self.assertEqual((r['status'],r['family']),('identified','blitz'))
        self.assertIsNone(r['matches'][0]['layoutValid'])

    def test_ambiguous(self):self.assertEqual(identify(b'\x01\x08test',identities=self.db('blitz','petspeed'))['status'],'ambiguous')
    def test_mutated_signature(self):self.assertEqual(identify(b'\x01\x08tesT',identities=self.db('blitz'))['status'],'unknown')
    def test_truncated(self):self.assertEqual(identify(b'\x01\x08tes',identities=self.db('blitz'))['status'],'unknown')
    def test_random_and_interpreted_basic_negative(self):
        for data in (b'',bytes(65538),b'\x01\x08\x0b\x08\x0a\0\x99"HI"\0\0\0',b'BLITZ PETSpeed BASIC-64 DTL RTL-64'):
            self.assertEqual(identify(data)['status'],'unknown')
    def test_wrong_load(self):self.assertEqual(identify(b'\x00\x08test',identities=self.db('blitz'))['status'],'unknown')
    def test_raw(self):self.assertEqual(identify(b'test',raw_base=0x801,identities=self.db('blitz'))['family'],'blitz')
    def test_raw_extent_refused(self):
        with self.assertRaises(ValueError):identify(bytes(2),raw_base=65535)
    def test_hash_match_layout_failure_is_not_decode_support(self):
        db=self.db('blitz');db['fingerprints'][0]['check']='blitz'
        r=identify(b'\x01\x08test',identities=db)
        self.assertEqual(r['family'],'blitz');self.assertFalse(r['matches'][0]['layoutValid'])
    def test_distinct_identity_and_decoder_contract(self):
        data=toy_blitz();raw=data[2:]
        db={'schema':'basic-compiler-identities-v1','fingerprints':[{'family':'austrospeed','role':'compiled-object','loadAddress':0x801,'start':0x801,'end':0x801+len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'check':'blitz','decoderFamily':'blitz'}]}
        identity=identify(data,identities=db)
        self.assertEqual(identity['family'],'austrospeed');self.assertEqual(identity['matches'][0]['decoderFamily'],'blitz')
        with patch.object(reconstruction,'identify',return_value=identity):
            result=reconstruction.reconstruct(data)
        self.assertEqual(result['family'],'austrospeed');self.assertEqual(result['selectedProfile'],'blitz-attached-runtime-generic')
    def test_cli_rejects_source_or_map(self):
        cli=Path(__file__).with_name('reconstruct.py')
        for flag in ('--source','--map','--annotations'):
            p=subprocess.run([sys.executable,str(cli),'unused',flag,'unused'],capture_output=True,text=True)
            self.assertEqual(p.returncode,2);self.assertIn('unrecognized arguments',p.stderr)


class LayoutTests(unittest.TestCase):
    def test_oversized_image_refused_before_family_layout(self):
        for family in ('blitz','petspeed','basic64','dtl'):
            with self.assertRaisesRegex(ValueError,'PRG extent'):
                inspect(b'\x01\x08'+bytes(65536),family)
    def test_empty_variable_table(self):self.assertEqual(blitz_layout(toy_blitz(),profile('blitz'))[1]['layout']['variableCount'],0)
    def test_observed_zero_tail(self):self.assertEqual(blitz_layout(toy_blitz(bytes(7)),profile('blitz'))[1]['layout']['retainedOpaqueTrailer'],'00'*7)
    def test_nonzero_or_wrong_length_tail_refused(self):
        for tail in (bytes(6),bytes(8),bytes(6)+b'\x01'):
            with self.assertRaises(ValueError):blitz_layout(toy_blitz(tail),profile('blitz'))
    def test_bad_pointer_order(self):
        p=bytearray(toy_blitz());p[8083-2049+2:8083-2049+4]=bytes(2)
        with self.assertRaises(ValueError):blitz_layout(bytes(p),profile('blitz'))
    def test_blitz_binary_only_decode_and_data(self):
        r=decode(toy_blitz(),'blitz')
        self.assertEqual([x['mnemonic'] for x in r['instructions']],['INIT_RETURN','END'])
        self.assertEqual(r['dataRecords'][0]['kind'],'terminator')
    def test_blitz_return_if_true_has_no_operand(self):
        r=decode(toy_blitz(code=b'\xb1\x58\x4f'),'blitz')
        self.assertEqual([x['mnemonic'] for x in r['instructions']],['INIT_RETURN','CONST_SMALL','RETURN_IF_TRUE','END'])


class SemanticTests(unittest.TestCase):
    def test_pet_noncommutative_orientation(self):
        for op,expected in [('SUBTRACT','(19 - 4)'),('SUBTRACT_FAC_ARG','(4 - 19)'),('DIVIDE','(4 / 19)'),('DIVIDE_ARG_FAC','(19 / 4)'),('POWER','(19 ^ 4)')]:
            r=program('petspeed',row('CONST_U8_ARG',19),row('CONST_U8_FAC',4),row(op),store())
            self.assertIn('= '+expected,texts(r))
    def test_basic64_integer_orientation_and_signed_words(self):
        r=program('basic64',row('CONST_WORD_INTEGER_ARG',65535),row('CONST_BYTE_INTEGER',3),row('INTEGER_SUBTRACT'),row('STORE_INTEGER_PAGE3',10))
        self.assertIn('V_030A = (-1 - 3)',texts(r));self.assertIn('16-bit',str(r['groups']))
    def test_basic64_float_orientation(self):
        r=program('basic64',row('CONST_BYTE_FLOAT_ARG',19),row('CONST_BYTE_FAC',4),row('FLOAT_DIVIDE'),store('basic64'))
        self.assertIn('(19 / 4)',texts(r))
    def test_blitz_rpn_subtract(self):
        r=program('blitz',row('CONST_U8',value=19),row('CONST_U8',value=4),row('SUBTRACT'),row('STORE_VAR',variable='A'))
        self.assertIn('A = (19 - 4)',texts(r))
    def test_dtl_rpn_subtract(self):
        r=program('dtl',row('INTEGER_BYTE',19),row('INTEGER_BYTE',4),row('SUBTRACT'),row('STORE_REAL',2,operands={'name':'A'}))
        self.assertIn('A = 19 - 4',texts(r))
    def test_dtl_poke_order_is_not_blitz_order(self):
        d=program('dtl',row('INTEGER_WORD',4096),row('INTEGER_BYTE',3),row('POKE'))
        b=program('blitz',row('CONST_U8',value=3),row('CONST_U16',value=4096),row('POKE'))
        self.assertIn('POKE 4096, 3',texts(d));self.assertIn('POKE 4096, 3',texts(b))
    def test_pet_stack_is_not_postfix(self):
        r=program('petspeed',row('CONST_U8_FAC',19),row('PUSH_FAC'),row('CONST_U8_FAC',4),row('POP_ARG'),row('SUBTRACT'),store())
        self.assertIn('(19 - 4)',texts(r))
    def test_pet_string_order(self):
        for op,expected in [('CONCAT','("LEFT" + "RIGHT")'),('CONCAT_FAC_ARG','("RIGHT" + "LEFT")')]:
            r=program('petspeed',row('CONST_STRING_ARG',operands={'stringHex':b'LEFT'.hex()}),row('CONST_STRING_FAC',operands={'stringHex':b'RIGHT'.hex()}),row(op),store())
            self.assertIn(expected,texts(r))
    def test_basic64_string_order(self):
        for op,expected in [('CONCATENATE_STRINGS','("LEFT" + "RIGHT")'),('CONCATENATE_STRINGS_REVERSED','("RIGHT" + "LEFT")')]:
            r=program('basic64',row('PUSH_INLINE_STRING',operands={'payloadHex':b'LEFT'.hex()}),row('PUSH_INLINE_STRING',operands={'payloadHex':b'RIGHT'.hex()}),row(op),row('STORE_STRING_PAGE3',0))
            self.assertIn(expected,texts(r))
    def test_false_branch_is_zero_test_not_bitwise_not(self):
        r=program('petspeed',row('CONST_U8_FAC',2),row('SKIP_IF_FALSE',operands={'target':0x1002}),row('END'))
        self.assertIn('IF (2) = 0 THEN',texts(r));self.assertNotIn('IF NOT',texts(r))
    def test_blitz_conditional_return(self):
        r=program('blitz',row('CONST_SMALL',1),row('RETURN_IF_TRUE'))
        self.assertEqual(texts(r),'IF 1 THEN RETURN')
    def test_basic64_fac_to_arg_rounds_both_views(self):
        r=program('basic64',row('CONST_BYTE_FAC',3),row('FAC_TO_ARG'),row('FLOAT_ADD'),store('basic64'))
        self.assertIn('(VM_ROUND(3) + VM_ROUND(3))',texts(r))
    def test_blitz_print_channel_owns_newline_and_clears_channels(self):
        r=program('blitz',row('CONST_U8',value=3),row('SELECT_OUTPUT_CHANNEL'),row('CONST_U8',value=9),row('PRINT_CHANNEL'),row('CONST_U8',value=7),row('PRINT'))
        self.assertIn('PRINT#3,  9\nPRINT 7',texts(r));self.assertNotIn('9;',texts(r))
    def test_blitz_print_comma_consumes_value(self):
        r=program('blitz',row('CONST_U8',value=9),row('PRINT_COMMA'))
        self.assertEqual(texts(r),'PRINT 9,')
    def test_io_selection_not_assumed_at_join(self):
        r=program('petspeed',row('GOTO',operands={'target':0x1003}),row('CONST_U8_FAC',3),row('SELECT_OUTPUT_CHANNEL'),row('PRINT_NEWLINE'))
        self.assertIn('PRINT#<?>',texts(r))
    def test_pet_for_limit_captured_before_initialization(self):
        r=program('petspeed',row('LOAD_FAC_VAR',operands={'variable':0x2800}),row('FOR_LIMIT'),row('CONST_U8_FAC',2),row('FOR_ENTER',0x2800),row('END'))
        self.assertIn('T_LIMIT_1001 = V_2800',texts(r));self.assertIn('FOR V_2800 = 2 TO T_LIMIT_1001',texts(r))
    def test_native_expanded_absolute_integer(self):
        r=program('basic64',row('LOAD_INTEGER',0x5000),row('DOUBLE_INTEGER'),row('STORE_INTEGER',0x5002))
        self.assertIn('V_5002 = (V_5000 * 2)',texts(r))
    def test_fixed_interpreter_result_not_inline_pointer(self):
        r=program('basic64',row('LOAD_BASIC_FLOAT_RESULT'),store('basic64'))
        self.assertIn('V_0300 = V_02C2',texts(r))
    def test_file_get_does_not_become_keyboard_get(self):
        r=program('petspeed',row('CONST_U8_FAC',3),row('SELECT_INPUT_CHANNEL'),row('GET_STRING'),store())
        self.assertIn('GET#3, T_1002$',texts(r));self.assertIn('V_2800 = T_1002$',texts(r))
    def test_basic64_file_input_channel_retained_in_partial_field(self):
        r=program('basic64',row('CONST_BYTE_INTEGER',3),row('SELECT_FILE_INPUT'),row('READ_FLOAT_FIELD'),store('basic64'))
        self.assertIn('INPUT#3 FIELD',texts(r))
    def test_missing_literal_field_is_not_invented_zero(self):
        r=program('petspeed',row('CONST_U8_FAC'),store())
        self.assertIn('V_2800 = <?>',texts(r))
    def test_unknown_kills_stale_fac_and_channel(self):
        r=program('petspeed',row('CONST_U8_FAC',19),row('UNMODELED_EFFECT'),store(),row('PRINT_NEWLINE'))
        self.assertIn('V_2800 = <?>',texts(r));self.assertIn('PRINT#<?>',texts(r))
    def test_target_join_kills_stale_value(self):
        r=program('petspeed',row('CONST_U8_FAC',19),store(),row('GOTO',operands={'target':0x1001}))
        self.assertIn('V_2800 = <?>',texts(r))
    def test_gosub_kills_stale_register(self):
        r=program('petspeed',row('CONST_U8_FAC',19),row('GOSUB',operands={'target':0x1003}),store(),row('END'))
        self.assertIn('V_2800 = <?>',texts(r))
    def test_binary_kills_secondary_accumulator(self):
        r=program('petspeed',row('CONST_U8_ARG',19),row('CONST_U8_FAC',4),row('ADD'),row('ADD'),store())
        self.assertIn('<?>',texts(r))
    def test_typed_store_does_not_forge_preserved_fac(self):
        r=program('petspeed',row('CONST_U8_FAC',19),store(),row('STORE_FAC_VAR',operands={'variable':0x2808}))
        self.assertIn('V_2808 = <?>',texts(r))
    def test_effectful_function_materialized_once(self):
        r=program('petspeed',row('CONST_U8_FAC',1),row('RND'),row('PUSH_FAC'),row('POP_ARG'),row('ADD'),store())
        self.assertEqual(texts(r).count('RND('),1);self.assertIn('(T_1001 + T_1001)',texts(r))
    def test_usr_does_not_reuse_pre_call_variable_load(self):
        r=program('blitz',row('LOAD_VAR',variable='A'),row('CONST_U8',value=1),row('USR'),row('ADD'),row('STORE_VAR',variable='B'))
        self.assertIn('<?>',texts(r));self.assertEqual(texts(r).count('USR('),1)
    def test_dtl_fn_call_preserves_lower_expression_stack(self):
        r=program('dtl',row('LOAD_REAL_SCALAR',operands={'name':'A','value':1}),row('FN_CALL',operands={'name':'F','value':1}),row('LOAD_REAL_SCALAR',operands={'name':'B','value':2}),row('FN_CALL',operands={'name':'G','value':2}),row('COMPARE_NE'),row('STORE_REAL_SCALAR',operands={'name':'C','value':3}))
        self.assertIn('C = T_1001 <> T_1003',texts(r));self.assertNotIn('<?>',texts(r))
    def test_dtl_fn_preserves_constants_and_captures_mutable_values(self):
        for lower,expected,capture in [([row('INTEGER_BYTE',2),row('INTEGER_BYTE',3),row('ADD')],'2 + 3',None),
                                      ([row('LOAD_REAL_SCALAR',operands={'name':'A','value':1})],'T_VALUE_1000','T_VALUE_1000 = A'),
                                      ([row('LOAD_REAL_SCALAR',operands={'name':'X','value':1}),row('INTEGER_BYTE',2),row('ADD')],'T_VALUE_1002','T_VALUE_1002 = X + 2')]:
            r=program('dtl',*lower,row('INTEGER_BYTE',4),row('FN_CALL',operands={'name':'F','value':2}),row('ADD'),row('STORE_REAL_SCALAR',operands={'name':'B','value':3}))
            self.assertIn('B = '+expected+' + T_',texts(r))
            if capture:
                self.assertIn(capture,texts(r));self.assertLess(texts(r).index(capture),texts(r).index(' = FN F('))
            else:self.assertNotIn('T_VALUE_',texts(r))
    def test_dtl_memory_read_captured_before_later_fn_effect(self):
        r=program('dtl',row('INTEGER_WORD',53280),row('FUNCTION',operands={'operation':'PEEK'}),
                  row('INTEGER_BYTE',4),row('FN_CALL',operands={'name':'F','value':2}),
                  row('ADD'),row('STORE_REAL_SCALAR',operands={'name':'B','value':3}))
        lines=texts(r)
        self.assertIn('T_1001 = PEEK(53280)',lines)
        self.assertIn('B = T_1001 + T_1003',lines)
        self.assertEqual(lines.count('PEEK('),1)
        self.assertLess(lines.index('T_1001 ='),lines.index('T_1003 ='))
    def test_dtl_fn_nested_argument_does_not_reuse_formal_alias(self):
        r=program('dtl',row('LOAD_REAL_SCALAR',operands={'name':'X','value':1}),row('INTEGER_BYTE',4),
                  row('FN_CALL',operands={'name':'INNER','value':2}),row('ADD'),row('FN_CALL',operands={'name':'OUTER','value':3}),
                  row('STORE_REAL_SCALAR',operands={'name':'B','value':4}))
        self.assertIn('T_VALUE_1000 = X',texts(r))
        self.assertIn('FN OUTER(T_VALUE_1000 + T_1002)',texts(r))
        self.assertNotIn('FN OUTER(X +',texts(r))
    def test_dtl_fn_can_change_channel_and_usr_still_invalidates(self):
        r=program('dtl',row('INTEGER_BYTE',2),row('FN_CALL',operands={'name':'F','value':1}))
        self.assertEqual(r['coverage']['partial'],0)
        from symbolic import Lifter
        call=Lifter('dtl',{'instructions':[]});call.current={'address':0x1000};call.output='3';call.input='4'
        call.function('FN F',[call.expr('1',stable=True)],'stack',True)
        self.assertEqual((call.output,call.input),('<?>','<?>'))
        r=program('dtl',row('INTEGER_BYTE',5),row('INTEGER_BYTE',2),row('FUNCTION',operands={'operation':'USR'}),row('ADD'),row('STORE_REAL_SCALAR',operands={'name':'B','value':1}))
        self.assertIn('B = <?> + T_1002',texts(r))
    def test_other_family_fn_does_not_inherit_dtl_stack_preservation(self):
        for family in ('blitz','austrospeed'):
            r=program(family,row('CONST_U8',value=3),row('CONST_U8',value=4),row('CALL_FUNCTION',value=1),row('ADD'),row('STORE_VAR',variable='B'))
            self.assertIn('B = (<?> + T_1002)',texts(r),family)
        for family in ('petspeed','basic64'):
            from symbolic import Lifter
            call=Lifter(family,{'instructions':[]});call.current={'address':0x1000};call.regs['arg']=call.expr('A')
            call.function('FN F',[call.expr('X')],'fac',True)
            self.assertNotIn('arg',call.regs)
    def test_float_to_integer_is_explicit_not_silently_erased(self):
        r=program('basic64',row('CONST_BYTE_FAC',3),row('FAC_TO_INTEGER'),row('STORE_INTEGER_PAGE3',0))
        self.assertIn('VM_INT(3)',texts(r))
    def test_instruction_ownership(self):
        r=program('petspeed',row('CONST_U8_FAC',1),row('RND'),row('MYSTERY'),row('END'))
        self.assertEqual([i['address'] for g in r['groups'] for i in g['instructions']],[0x1000,0x1001,0x1002,0x1003])
        self.assertEqual(sum(r['coverage'].values()),4)
    def test_dtl_embedded_basic_is_distinct(self):
        r=program('dtl',row('BASIC',grammar='basic_island',operands={'text':'PRINT"EMBEDDED"'}))
        self.assertEqual(r['groups'][0]['kind'],'embedded');self.assertFalse(r['sourceSupplied']);self.assertFalse(r['mapsUsed'])
    def test_data_strict_envelope(self):
        for family,raw in [('dtl',b'\x83 1,"A,B"\0\0\0'),('basic64',b',1,"A,B"\0\0\0')]:
            r=lift(family,{'instructions':[],'dataRegion':{'address':0x2000,'bytes':raw.hex()}})
            self.assertEqual(r['retainedData'][0]['text'],'DATA 1,"A,B"')
    def test_data_unknown_envelope_remains_opaque(self):
        r=lift('dtl',{'instructions':[],'dataRegion':{'address':0x2000,'bytes':b'\x83 1\0x\0\0\0'.hex()}})
        self.assertEqual(r['retainedData'][0]['kind'],'opaque')
    def test_blitz_data_normalized_and_quoting_unknown(self):
        r=lift('blitz',{'instructions':[],'dataRecords':[{'kind':'string','address':0x2000,'bytes':'03 41 2c 42'},{'kind':'string','address':0x2004,'bytes':'01 22'}]})
        self.assertEqual(r['retainedData'][0]['text'],'DATA "A,B"');self.assertIsNone(r['retainedData'][1]['text'])
    def test_byte_literals_do_not_forge_control_character_text(self):self.assertEqual(quoted(bytes([65,34,0,66])),'"A"+CHR$(34)+CHR$(0)+"B"')
    def test_fraction_not_host_float_rounded(self):self.assertEqual(number('3/8'),'0.375')
    def test_basic64_array_index_order(self):
        r=program('basic64',row('CONST_BYTE_INTEGER',2),row('PUSH_INTEGER'),row('CONST_BYTE_INTEGER',3),row('LOAD_FLOAT_ARRAY',operands={'arrayBase':0x4000,'extentsReversed':[5,4]}),store('basic64'))
        self.assertIn('AR_4000(2, 3)',texts(r))
    def test_basic64_array_store_uses_saved_index_not_rhs_integer(self):
        r=program('basic64',row('CONST_BYTE_INTEGER',2),row('PUSH_INTEGER'),row('CONST_BYTE_INTEGER',99),row('STORE_INTEGER_ARRAY',operands={'arrayBase':0x4000,'extentsReversed':[5]}))
        self.assertIn('AR_4000%(2) = 99',texts(r))
    def test_dtl_array_rank_not_guessed(self):
        r=program('dtl',row('INTEGER_BYTE',1),row('LOAD_REAL_ARRAY',0))
        self.assertIn('rank/name not established',texts(r))
    def test_dtl_nested_dim_expression_is_not_a_second_array(self):
        r=program('dtl',row('BASIC',grammar='basic_island',operands={'text':'DIMA(FNF(2)),B(3,4)'}),row('ARRAY_REGISTER',0),row('ARRAY_REGISTER',2),row('INTEGER_BYTE',1),row('INTEGER_BYTE',2),row('LOAD_REAL_ARRAY',2),row('STORE_REAL',4,operands={'name':'Z'}))
        self.assertIn('Z = B(1, 2)',texts(r))
    def test_no_source_fields_used(self):
        a=row('CONST_U8_FAC',4);a.update(comment='PRINT "CHEAT"',sourceText='PRINT "CHEAT"',line=123)
        with self.assertRaises(ValueError):program('petspeed',a,store())
    def test_oversized_expression_bounded(self):
        rows=[row('CONST_U8_FAC',1)]
        for _ in range(20):rows += [row('PUSH_FAC'),row('POP_ARG'),row('ADD')]
        r=program('petspeed',*rows,store());self.assertLess(len(texts(r)),10000)


if __name__=='__main__':unittest.main()
