"""Synthetic evaluation-site captures; no title bytes/source/VM execution."""
import unittest
from symbolic import Lifter
from test_reconstruct import program, row, texts


def load(name='A',value=1):return row('LOAD_REAL_SCALAR',operands={'name':name,'value':value})
def call(name='F'):return row('FN_CALL',operands={'name':name,'value':2})
def store():return row('STORE_REAL_SCALAR',operands={'name':'Z','value':3})


class DTLCaptureTests(unittest.TestCase):
    def test_no_call_keeps_compact_expression(self):
        r=program('dtl',load(),row('INTEGER_BYTE',2),row('ADD'),store())
        self.assertEqual(texts(r),'Z = A + 2')

    def test_argument_only_read_does_not_need_a_lower_capture(self):
        r=program('dtl',load(),call(),store())
        self.assertNotIn('T_VALUE_',texts(r));self.assertIn('FN F(A)',texts(r))

    def test_capture_precedes_entire_effectful_argument_evaluation(self):
        r=program('dtl',load(),row('INTEGER_WORD',53280),row('FUNCTION',operands={'operation':'PEEK'}),call(),row('ADD'),store())
        lines=texts(r)
        self.assertIn('Z = T_VALUE_1000 + T_1003',lines)
        self.assertLess(lines.index('T_VALUE_1000 = A'),lines.index('T_1002 = PEEK'))
        self.assertLess(lines.index('T_1002 = PEEK'),lines.index('T_1003 = FN'))
        self.assertEqual(lines.count('PEEK('),1)

    def test_array_value_and_index_are_not_reread_after_call(self):
        r=program('dtl',row('BASIC',grammar='basic_island',operands={'text':'DIMA(10)'}),
                  row('ARRAY_REGISTER',0),load('X'),row('LOAD_REAL_ARRAY',0),row('INTEGER_BYTE',4),call(),row('ADD'),store())
        lines=texts(r)
        self.assertIn('T_VALUE_1003 = A(X)',lines)
        self.assertIn('Z = T_VALUE_1003 + T_1005',lines)
        self.assertEqual(lines.count('A(X)'),1)
        self.assertLess(lines.index('T_VALUE_1003 ='),lines.index('T_1005 ='))

    def test_two_lower_values_and_nested_aliasing_argument(self):
        r=program('dtl',load('A'),load('X',2),row('INTEGER_BYTE',4),call('INNER'),
                  row('ADD'),call('OUTER'),row('ADD'),store())
        lines=texts(r)
        self.assertIn('T_VALUE_1000 = A',lines);self.assertIn('T_VALUE_1001 = X',lines)
        self.assertIn('FN OUTER(T_VALUE_1001 + T_1003)',lines)
        self.assertIn('Z = T_VALUE_1000 + T_1005',lines)
        self.assertNotIn('<?>',lines)
        self.assertEqual(lines.count(' = A'),1);self.assertEqual(lines.count(' = X'),1)
        # No unnecessary recapture of a composition now entirely made of values.
        self.assertNotIn('T_VALUE_1004',lines)

    def test_later_mutable_composition_discovered_even_with_prior_unknown(self):
        r=program('dtl',load('A'),row('INTEGER_BYTE',4),call('F'),row('ADD'),
                  load('B'),row('ADD'),row('INTEGER_BYTE',5),call('G'),row('ADD'),store())
        lines=texts(r)
        self.assertIn('T_VALUE_1000 = A',lines)
        self.assertIn('T_VALUE_1005 = T_VALUE_1000 + T_1002 + B',lines)
        self.assertIn('Z = T_VALUE_1005 + T_1007',lines)
        self.assertNotIn('<?>',lines)

    def test_effect_result_is_not_duplicated_by_compound_capture(self):
        r=program('dtl',load(),row('INTEGER_BYTE',1),row('FUNCTION',operands={'operation':'RND'}),
                  row('ADD'),row('INTEGER_BYTE',4),call(),row('ADD'),store())
        lines=texts(r)
        self.assertIn('T_VALUE_1003 = A + T_1002',lines)
        self.assertIn('Z = T_VALUE_1003 + T_1005',lines)
        self.assertEqual(lines.count('RND('),1)

    def test_unknown_expression_is_not_promoted_to_a_known_value(self):
        r=program('dtl',row('INTEGER_BYTE',1),row('ADD'),row('INTEGER_BYTE',4),call(),row('ADD'),store())
        self.assertNotIn('T_VALUE_',texts(r))
        self.assertIn('Z = <?> + T_1003',texts(r));self.assertGreater(r['coverage']['partial'],0)

    def test_unknown_opcode_still_kills_captured_value(self):
        r=program('dtl',load(),row('INTEGER_BYTE',4),call(),row('MYSTERY'),row('INTEGER_BYTE',1),row('ADD'),store())
        self.assertIn('T_VALUE_1000 = A',texts(r))
        self.assertIn('Z = <?> + 1',texts(r));self.assertGreater(r['coverage']['unresolved'],0)

    def test_opaque_usr_still_kills_previously_captured_value(self):
        r=program('dtl',load(),row('INTEGER_BYTE',4),call(),row('FUNCTION',operands={'operation':'USR'}),row('ADD'),store())
        self.assertIn('T_VALUE_1000 = A',texts(r))
        self.assertIn('Z = <?> + T_1003',texts(r))

    def test_control_join_cannot_revive_a_captured_value(self):
        r=program('dtl',load(),row('INTEGER_BYTE',4),call(),row('GOTO',targets=[0x1005]),
                  row('INTEGER_BYTE',1),row('ADD'),store())
        self.assertIn('T_VALUE_1000 = A',texts(r))
        self.assertIn('Z = <?> + <?>',texts(r))

    def test_direct_single_pass_still_invalidates_mutable_alias(self):
        rows=[load(),row('INTEGER_BYTE',4),call(),row('ADD'),store()]
        lifter=Lifter('dtl',{'instructions':[{'address':0x1000+i,**r} for i,r in enumerate(rows)]})
        r=lifter.run()
        self.assertEqual(lifter.fn_capture_candidates,{0x1000})
        self.assertIn('Z = <?> + T_1002',texts(r))

    def test_capture_is_owned_at_original_instruction_not_call(self):
        r=program('dtl',load(),row('INTEGER_BYTE',2),row('ADD'),row('INTEGER_BYTE',4),call(),row('ADD'),store())
        capture=next(g for g in r['groups'] if g['text'].startswith('T_VALUE_'))
        self.assertEqual([i['address'] for i in capture['instructions']],[0x1000,0x1001,0x1002])
        self.assertEqual([i['address'] for g in r['groups'] for i in g['instructions']],list(range(0x1000,0x1007)))
        self.assertEqual(sum(r['coverage'].values()),7)
        self.assertTrue(all(g['instructions'] for g in r['groups']))


if __name__=='__main__':unittest.main()
