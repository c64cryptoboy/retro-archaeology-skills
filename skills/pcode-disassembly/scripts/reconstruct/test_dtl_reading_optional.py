"""Authored optional idiom/refusal contracts; no target program execution."""
from copy import deepcopy
from itertools import product
import unittest
import expression_display as d
from reading_projection import expression_events
from symbolic import lift, render
from test_dtl_reading import load, fn, binary, reading
from test_dtl_for import instruction, literal, place
from test_dtl_functions import fixture


def definition(base=0x2000, body=None):
    if body is None:body=[load('K',9),literal(7),binary('SUBTRACT',2)]
    report=fixture(base,body)
    header=report['instructions'][0];v=header['operands']
    header['bytes']=(bytes((0x53,))+v['descriptorOffset'].to_bytes(2,'big')+bytes((0,8))+
                     v['parameterOffset'].to_bytes(2,'big')+bytes((v['skipBytes'],))).hex()
    ret=next(r for r in report['instructions'] if r['mnemonic']=='FN_RETURN');ret['bytes']='55'
    return report


def conditional(left=None):
    left=left or [load('A',2),literal(1),binary('COMPARE_LT',0x2d)]
    branch=instruction('IF_SKIP_FALSE','4f02',grammar='relative8',control='conditional')
    branch['targets']=[0x4100]
    return place(left+[load('B',9),literal(2),binary('COMPARE_GT',0x2a),binary('OR',0x07),branch])


def evaluate(node, env):
    if node.kind=='leaf':return env[node.token]
    a,b=(evaluate(c,env) for c in node.children)
    if node.token=='AND':return a & b
    if node.token=='OR':return a | b
    return -int({'=':lambda:a==b,'<>':lambda:a!=b,'<':lambda:a<b,'>':lambda:a>b,
                 '<=':lambda:a<=b,'>=':lambda:a>=b}[node.token]())


class OptionalReadingTests(unittest.TestCase):
    def test_simple_function_is_deferred_and_detailed_groups_retained(self):
        report=definition();before=deepcopy(report);result=lift('dtl',report)
        self.assertTrue(reading(result).startswith('DEF FN ZX(K) = K - 7\n'))
        item=result['readingView']['groups'][0]
        self.assertEqual(item['definitionEvaluationOrder'],[0x2000])
        self.assertEqual(item['deferredEvaluationOrder'],[0x2008,0x200b,0x200c])
        self.assertIsNone(item['evaluationOrder'])
        self.assertIn('body L_2008',render(result));self.assertIn('RETURN FN ZX = K - 7',render(result))
        self.assertEqual(report,before);self.assertEqual(result,lift('dtl',report))

    def test_function_relocation_preserves_identities(self):
        result=lift('dtl',definition(0x3800))
        self.assertEqual(result['readingView']['groups'][0]['definitionEvaluationOrder'],[0x3800])
        self.assertEqual(result['readingView']['counts']['single-expression-function'],1)

    def test_multi_group_proved_effect_order_folds_but_opaque_usr_stays_explicit(self):
        for name in ('RND','PEEK'):
            with self.subTest(name=name):
                result=lift('dtl',definition(body=[literal(1),fn(name)]))
                self.assertIn('single-expression-function',result['readingView']['counts'])
                self.assertTrue(reading(result).startswith('DEF FN ZX(K) = '+name+'(1)\n'))
        result=lift('dtl',definition(body=[literal(1),fn('USR')]))
        self.assertNotIn('single-expression-function',result['readingView']['counts'])
        self.assertIn('RETURN FN ZX = T_',reading(result))

    def test_malformed_header_or_return_encoding_refuses_fold(self):
        for mutation in ('header','formal','skip','return','length'):
            with self.subTest(mutation=mutation):
                report=definition();header=report['instructions'][0];raw=bytearray.fromhex(header['bytes'])
                if mutation=='header':raw[0]=0
                elif mutation=='formal':raw[6]=10
                elif mutation=='skip':raw[7]+=1
                elif mutation=='length':header['length']=7
                else:next(r for r in report['instructions'] if r['mnemonic']=='FN_RETURN')['bytes']='54'
                header['bytes']=raw.hex()
                self.assertNotIn('single-expression-function',lift('dtl',report)['readingView']['counts'])

    def test_foreign_body_entry_refuses_function_fold(self):
        report=definition();report['instructions'][-1]['targets']=[0x200a]
        self.assertNotIn('single-expression-function',lift('dtl',report)['readingView']['counts'])

    def test_missing_or_ambiguous_function_identity_stays_explicit(self):
        for mutation in ('missing','duplicate'):
            report=definition()
            if mutation=='missing':report['scalars'].pop(0)
            else:report['scalars'].append(deepcopy(report['scalars'][0]))
            self.assertNotIn('single-expression-function',lift('dtl',report)['readingView']['counts'])

    def test_function_body_tree_and_integer_mode_caveats_remain(self):
        report=definition(body=[load('K',9),literal(7),binary('DIVIDE',4)])
        result=lift('dtl',report);item=result['readingView']['groups'][0]
        self.assertEqual(item['text'],'DEF FN ZX(K) = K / 7')
        self.assertTrue(any('SI mode' in w for w in item['warnings']))

    def test_comparison_only_boolean_branch_and_detailed_text(self):
        result=lift('dtl',conditional())
        self.assertEqual(reading(result),'IF A >= 1 AND B <= 2 THEN GOTO L_4100')
        self.assertEqual(result['groups'][0]['text'],'IF (A < 1 OR B > 2) = 0 THEN GOTO L_4100')
        self.assertEqual(result['readingView']['counts']['boolean-complement'],1)

    def test_nonboolean_bitwise_operand_is_not_negated(self):
        result=lift('dtl',conditional([load('A',2)]))
        self.assertEqual(reading(result),'IF (A OR B > 2) = 0 THEN GOTO L_4100')
        self.assertNotIn('boolean-complement',result['readingView']['counts'])

    def test_boolean_helper_refuses_untyped_leaves_calls_and_unary(self):
        relation=d.binary('<',d.leaf('A'),d.leaf('B'))
        for child in (d.leaf('X'),d.leaf('1'),d.temporary('T1'),d.call('F',[]),d.unary('NOT',relation)):
            self.assertIsNone(d.boolean_complement(d.binary('OR',relation,child)))

    def test_boolean_duality_exhaustive_relational_truths(self):
        for relation,logical in product(d.COMPLEMENT,('AND','OR')):
            tree=d.binary(logical,d.binary(relation,d.leaf('A'),d.leaf('B')),
                          d.binary('<>',d.leaf('C'),d.leaf('D')))
            opposite=d.boolean_complement(tree)
            for values in product((-2,0,1,2),repeat=4):
                env=dict(zip('ABCD',values))
                self.assertEqual(evaluate(opposite,env),-int(evaluate(tree,env)==0))

    def test_boolean_nested_tree_preserves_child_order_and_origins(self):
        a=d.binary('<',d.call('PEEK',[d.leaf('1')],origin=11),d.leaf('2'),origin=12)
        b=d.binary('=',d.leaf('X',origin=13),d.leaf('Y',origin=14),origin=15)
        c=d.binary('>',d.leaf('Z',origin=16),d.leaf('3'),origin=17)
        tree=d.binary('OR',a,d.binary('AND',b,c,origin=18),origin=19)
        opposite=d.boolean_complement(tree)
        self.assertEqual(expression_events(tree),expression_events(opposite))
        self.assertEqual(d.render(opposite),'PEEK(1) >= 2 AND (X <> Y OR Z <= 3)')
        self.assertEqual(d.render(tree),'PEEK(1) < 2 OR X = Y AND Z > 3')

    def test_boolean_transform_keeps_inlined_effect_order(self):
        result=lift('dtl',conditional([literal(1),fn('PEEK'),literal(1),binary('COMPARE_LT',0x2d)]))
        text=reading(result)
        self.assertEqual(text,'IF PEEK(1) >= 1 AND B <= 2 THEN GOTO L_4100')
        self.assertEqual(text.count('PEEK('),1)
        self.assertEqual(result['readingView']['counts']['inline-temporary'],1)

    def test_plain_comparison_still_uses_existing_path(self):
        branch=instruction('IF_SKIP_FALSE','4f02',grammar='relative8',control='conditional');branch['targets']=[0x4100]
        result=lift('dtl',place([load('A'),literal(1),binary('COMPARE_LT',0x2d),branch]))
        self.assertEqual(reading(result),'IF A >= 1 THEN GOTO L_4100')
        self.assertNotIn('boolean-complement',result['readingView']['counts'])


if __name__=='__main__':unittest.main()
