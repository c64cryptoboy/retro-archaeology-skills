"""Synthetic PETSpeed decode/lift contracts; no runtime or source bytes bundled."""
import unittest

from formats import module, profile
from symbolic import lift
from test_reconstruct import program, row, store, texts


def prepared(kind='number'):
    name={'number':'ARRAY_DEST','integer':'INTEGER_ARRAY_DEST','string':'STRING_ARRAY_DEST'}[kind]
    return [row('ARRAY_BASE',0x4000),row('LOAD_FAC_VAR',operands={'variable':0x2800}),row(name)]


def combined(verb,kind):
    suffix='STORE_INTEGER_ELEMENT' if kind=='integer' else 'STORE_ELEMENT'
    return row(verb+('_STRING' if kind=='string' else '_NUMBER')+'_'+suffix,
               operands={'modifier':0x42 if kind=='integer' else 0x41})


class PETSpeedInputTests(unittest.TestCase):
    def test_all_normal_contextual_forms_decode_and_lift(self):
        core=module('petspeed');p=profile('petspeed')
        for opcode,verb in [(0xD6,'INPUT'),(0xD9,'READ'),(0xDB,'GET'),(0xD7,'INPUT'),(0xDA,'READ'),(0xDC,'GET')]:
            string=opcode in (0xD7,0xDA,0xDC)
            for modifier in ([0x41] if string else [0x41,0x42]):
                kind='string' if string else 'integer' if modifier==0x42 else 'number'
                dest={'number':0xA0,'integer':0xA3,'string':0xA6}[kind]
                data=bytes([0xFC,0,0x40,0x20,dest,opcode,modifier,0xD3])
                rows=[];pc=0x3000
                while pc<0x3000+len(data):
                    r=core.decode_one(data,0x3000,pc,0x3000+len(data),p)
                    rows.append(r);pc+=r['size']
                result=lift('petspeed',{'instructions':rows});text=texts(result)
                with self.subTest(opcode=opcode,modifier=modifier):
                    self.assertIn('T_INDEX_3004 = V_2800',text)
                    self.assertIn(('REM INPUT FIELD -> ' if verb=='INPUT' else verb+' ')+'ELEM_4000(T_INDEX_3004)',text)
                    self.assertEqual(result['coverage']['unresolved'],0)
                    self.assertEqual([r for g in result['groups'] for r in g['instructions']],rows)
                    group=next(g for g in result['groups'] if any('modifier' in r['operands'] for r in g['instructions']))
                    self.assertEqual(group['kind'],'partial' if verb=='INPUT' else 'inferred')
                    self.assertIn(0x3000,group['evidenceAddresses'])
                    self.assertIn(0x3004,group['evidenceAddresses'])

    def test_input_channel_and_retry_caveat_retained(self):
        r=program('petspeed',row('CONST_U8_FAC',3),row('SELECT_INPUT_FILE'),*prepared('string'),combined('INPUT','string'))
        self.assertIn('REM INPUT#3 FIELD -> ELEM_4000(T_INDEX_1004)',texts(r))
        self.assertIn('retry semantics not reconstructed',str(r['groups']))

    def test_get_uses_selected_channel_before_invalidating_it(self):
        r=program('petspeed',row('CONST_U8_FAC',3),row('SELECT_INPUT_FILE'),*prepared('string'),combined('GET','string'),row('GET_STRING'))
        self.assertIn('GET#3, ELEM_4000(T_INDEX_1004)',texts(r))
        self.assertIn('GET#<?>, T_1006$',texts(r))

    def test_read_does_not_use_selected_file(self):
        r=program('petspeed',row('CONST_U8_FAC',3),row('SELECT_INPUT_FILE'),*prepared(),combined('READ','number'))
        self.assertIn('READ ELEM_4000',texts(r));self.assertNotIn('READ#',texts(r))

    def test_combined_store_does_not_invent_preserved_fac(self):
        r=program('petspeed',*prepared('integer'),combined('READ','integer'),store())
        self.assertIn('V_2800 = <?>',texts(r))
        self.assertIn('numeric-to-integer destination conversion',str(r['groups']))

    def test_plain_input_drops_stale_arg_but_retains_new_value(self):
        for verb in ('READ','INPUT','GET'):
            r=program('petspeed',row('CONST_U8_ARG',19),row(verb+'_NUMBER'),row('ADD'),store())
            self.assertIn('(T_1001 + <?>)',texts(r));self.assertNotIn('+ 19',texts(r))

    def test_missing_destination_is_partial(self):
        r=program('petspeed',combined('READ','integer'))
        self.assertEqual(texts(r),'READ <?>');self.assertEqual(r['groups'][0]['kind'],'partial')

    def test_join_drops_prepared_destination(self):
        r=program('petspeed',*prepared('integer'),combined('READ','integer'),row('GOTO',operands={'target':0x1003}))
        self.assertIn('READ <?>',texts(r))

    def test_destination_capture_precedes_rhs_and_kills_old_fac(self):
        r=program('petspeed',*prepared(),row('STORE_ELEMENT'))
        self.assertIn('T_INDEX_1002 = V_2800',texts(r))
        self.assertIn('ELEM_4000(T_INDEX_1002) = <?>',texts(r))

    def test_mismatched_prepared_type_not_normalized(self):
        r=program('petspeed',*prepared('string'),combined('READ','integer'))
        self.assertIn('input-store type does not match',texts(r))

    def test_descriptor_as_integer_store_remains_unresolved(self):
        r=program('petspeed',*prepared('integer'),row('READ_STRING_STORE_INTEGER_ELEMENT',operands={'modifier':0x42}))
        self.assertIn('semantics not yet modeled',texts(r))

    def test_inconsistent_modifier_not_normalized(self):
        r=program('petspeed',*prepared('integer'),row('READ_NUMBER_STORE_INTEGER_ELEMENT',operands={'modifier':0x41}))
        self.assertIn('inconsistent contextual',texts(r))

    def test_nested_typed_spill_expressions_preserve_lifo(self):
        r=program('petspeed',row('CONST_U8_FAC',19),row('PUSH_FAC'),
                  row('CONST_STRING_FAC',operands={'stringHex':'4142'}),row('PUSH_FAC'),
                  row('CONST_U8_FAC',1),row('POP_ARG'),row('LEFT_STRING'),
                  row('LEN'),row('POP_ARG'),row('SUBTRACT'),store())
        self.assertIn('(19 - LEN(LEFT$("AB", 1)))',texts(r))


if __name__=='__main__':unittest.main()
