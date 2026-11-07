"""Authored records and abstract path checks; no target VM/payload execution."""
import copy
import unittest
from dtl_branches import analyze_false_tests
from symbolic import lift, render
from test_dtl_functions import instruction
from test_reconstruct import program, row, texts


def load(name='B'):
    return instruction('LOAD_REAL_SCALAR', 2, {'value': 9, 'name': name})


def literal(n=7):
    return instruction('INTEGER_BYTE', 2, {'value': n})


def fixture(base=0x4000, predicates=None):
    if predicates is None:
        predicates = [[load(), literal(), instruction('COMPARE_GT')]]
    def test(label):
        return instruction('IF_SKIP_FALSE', 2, control='conditional', grammar='relative8', label=label)
    rows = [load('A'), test('source')]
    for i, predicate in enumerate(predicates):
        rows += copy.deepcopy(predicate) + [test('join' + str(i))]
    rows += [literal(1), instruction('STORE_REAL_SCALAR', 2, {'value': 16, 'name': 'C'}),
             instruction('END', control='end', label='end')]
    address = base
    labels = {}
    for r in rows:
        r['address'] = address
        address += r['length']
        if 'label' in r:
            labels[r.pop('label')] = r['address']
    targets = [labels['join0']] + [labels.get('join' + str(i + 1), labels['end']) for i in range(len(predicates))]
    for r, target in zip([r for r in rows if r['mnemonic'] == 'IF_SKIP_FALSE'], targets):
        delta = target - r['address']
        r.update(targets=[target], bytes=bytes([0x4f, delta]).hex(), operands={'raw': f'{delta:02x}'})
    return {'instructions': rows, 'scalars': [{'offset': 44, 'type': 'function', 'name': 'FN ZX'}]}, labels


class DTLBranchTests(unittest.TestCase):
    def assert_refused(self, report, reason):
        before = copy.deepcopy(report)
        result = lift('dtl', report)
        self.assertEqual(report, before)
        self.assertEqual(result['falseTestJoins']['forwardedEdges'], [])
        self.assertTrue(all(j['status'] == 'unresolved' for j in result['falseTestJoins']['joins']))
        self.assertIn(reason, str(result['falseTestJoins']))
        self.assertIn('IF (<?>) = 0', texts(result))
        self.assertEqual([r for g in result['groups'] for r in g['instructions']], report['instructions'])
        return result

    def test_distinct_false_and_fallthrough_paths_and_original_target(self):
        report, labels = fixture()
        before = copy.deepcopy(report)
        result = lift('dtl', report)
        text = texts(result)
        self.assertIn(f'IF A = 0 THEN GOTO L_{labels["end"]:04X}', text)
        self.assertIn(f'IF B <= 7 THEN GOTO L_{labels["end"]:04X}', text)
        self.assertNotIn('<?>', text)
        self.assertNotIn(' AND ', text)
        self.assertEqual(result['coverage']['unresolved'], 0)
        index = result['falseTestJoins']
        self.assertEqual(index['joins'][0]['status'], 'recovered')
        self.assertEqual(index['forwardedEdges'], [{'source': labels['source'], 'encodedTarget': labels['join0'],
                         'readingTarget': labels['end'], 'through': [labels['join0']]}])
        self.assertEqual(report, before)
        self.assertEqual([r for g in result['groups'] for r in g['instructions']], report['instructions'])
        self.assertEqual(lift('dtl', report), result)
        self.assertIn('encoded target remains', render(result))
        self.assertIn('; DTL FALSE-TEST JOINS', render(result))

    def test_abstract_asymmetric_path_table_not_eager_and(self):
        report, labels = fixture()
        edge = lift('dtl', report)['falseTestJoins']['forwardedEdges'][0]
        # Model only the evidenced test/edge contract, not machine execution.
        for first in (0, 2, -7):
            for second in (0, 3, -1):
                original_effects = []
                current = first
                if first != 0:
                    original_effects.append('compute-second'); current = second
                original = labels['end'] if current == 0 else labels['join0'] + 2
                reading_effects = []
                if first == 0:
                    reading = edge['readingTarget']
                else:
                    reading_effects.append('compute-second')
                    reading = labels['end'] if second == 0 else labels['join0'] + 2
                self.assertEqual((reading, reading_effects), (original, original_effects))

    def test_plain_load_predicate_not_just_comparisons(self):
        report, _ = fixture(predicates=[[load('D')]])
        result = lift('dtl', report)
        self.assertEqual(result['falseTestJoins']['joins'][0]['status'], 'recovered')
        self.assertIn('IF D = 0', texts(result))

    def test_multiple_forward_tests_transitively_forwarded(self):
        report, labels = fixture(predicates=[[load('B')], [load('D')]])
        result = lift('dtl', report)
        edges = {e['source']: e for e in result['falseTestJoins']['forwardedEdges']}
        self.assertEqual(edges[labels['source']]['through'], [labels['join0'], labels['join1']])
        self.assertEqual(edges[labels['source']]['readingTarget'], labels['end'])
        self.assertEqual(edges[labels['join0']]['through'], [labels['join1']])
        self.assertEqual(result['coverage']['partial'], 0)
        self.assertIn('IF B = 0', texts(result)); self.assertIn('IF D = 0', texts(result))

    def test_multiple_false_incoming_edges(self):
        report, labels = fixture()
        extra = [load('Z'), instruction('IF_SKIP_FALSE', 2, control='conditional', grammar='relative8')]
        extra[0]['address'] = 0x3ffc
        extra[1].update(address=0x3ffe, targets=[labels['join0']],
                        bytes=bytes([0x4f, labels['join0'] - 0x3ffe]).hex())
        report['instructions'] = extra + report['instructions']
        result = lift('dtl', report)
        self.assertEqual(len(result['falseTestJoins']['forwardedEdges']), 2)
        self.assertEqual(result['falseTestJoins']['joins'][0]['status'], 'recovered')

    def test_effect_is_not_duplicated_or_moved_to_false_path(self):
        report, labels = fixture(predicates=[[literal(1), instruction('FUNCTION', 2, {'operation': 'RND'})]])
        result = lift('dtl', report)
        text = texts(result)
        self.assertEqual(text.count('RND('), 1)
        self.assertLess(text.index('IF A ='), text.index('RND('))
        self.assertLess(text.index('RND('), text.index('IF T_'))
        self.assertIn(f'IF A = 0 THEN GOTO L_{labels["end"]:04X}', text)
        self.assertEqual(result['coverage']['partial'], 0)

    def test_descriptor_fn_result_keeps_single_temp(self):
        report, _ = fixture(predicates=[[literal(2), instruction('FN_CALL', 3, {'value': 44, 'name': 'FN ZX'},
                                                                 control='descriptor-indirect-call')]])
        result = lift('dtl', report)
        self.assertEqual(texts(result).count('FN ZX(2)'), 1)
        self.assertIn('IF T_', texts(result))
        self.assertEqual(result['falseTestJoins']['joins'][0]['status'], 'recovered')

    def test_fn_producer_capture_survives_branch_replay(self):
        report, _ = fixture(predicates=[[load('B'), literal(2),
                       instruction('FN_CALL', 3, {'value': 44, 'name': 'FN ZX'}, control='descriptor-indirect-call'),
                       instruction('COMPARE_GT')]])
        result = lift('dtl', report)
        text = texts(result)
        self.assertEqual(text.count(' = B'), 1)
        self.assertIn('T_VALUE_', text); self.assertNotIn('<?>', text)
        self.assertLess(text.index(' = B'), text.index('FN ZX(2)'))
        self.assertEqual(result['falseTestJoins']['joins'][0]['status'], 'recovered')

    def test_mixed_goto_incoming_is_refused(self):
        report, labels = fixture()
        report['instructions'].append(instruction('GOTO', 3, control='jump', targets=[labels['join0']],
                                                 address=labels['end'] + 1))
        self.assert_refused(report, 'Incoming edge is not')

    def test_unmodeled_extra_target_field_is_refused(self):
        report, labels = fixture()
        report['instructions'][-1]['operands']['target'] = labels['join0']
        self.assert_refused(report, 'Incoming edge is not')

    def test_loop_self_target_is_refused(self):
        report, labels = fixture()
        join = next(r for r in report['instructions'] if r['address'] == labels['join0'])
        join.update(targets=[labels['join0']], bytes='4f00')
        self.assert_refused(report, 'forward-target')

    def test_region_crossing_is_refused(self):
        report, labels = fixture()
        next(r for r in report['instructions'] if r['address'] == labels['join0'])['region'] = 'other'
        self.assert_refused(report, 'region contract')

    def test_encoding_and_missing_target_are_refused(self):
        for mode in ('encoding', 'target', 'control', 'grammar'):
            with self.subTest(mode=mode):
                report, labels = fixture()
                join = next(r for r in report['instructions'] if r['address'] == labels['join0'])
                if mode == 'encoding': join['bytes'] = '4f00'
                elif mode == 'target': join['targets'] = [0x7000]
                elif mode == 'control': join['control'] = 'unknown'
                else: join['grammar'] = 'unknown'
                self.assert_refused(report, 'contract is inconsistent')

    def test_extra_stack_values_are_not_retained(self):
        report, _ = fixture(predicates=[[load('Z'), load('B'), literal(), instruction('COMPARE_GT')]])
        self.assert_refused(report, 'one complete value')

    def test_unknown_producer_remains_unknown(self):
        report, _ = fixture(predicates=[[instruction('UNKNOWN_EXPRESSION', 2), literal(), instruction('COMPARE_GT')]])
        self.assert_refused(report, 'one complete value')

    def test_opaque_usr_producer_refused(self):
        report, _ = fixture(predicates=[[literal(1), instruction('FUNCTION', 2, {'operation': 'USR'})]])
        self.assert_refused(report, 'opaque producer')

    def test_no_value_from_immediate_predecessor_refused(self):
        report, _ = fixture(predicates=[[load(), instruction('DELIMITER')]])
        self.assert_refused(report, 'one complete value')

    def test_gap_before_join_refused(self):
        report, labels = fixture()
        previous = next(r for r in report['instructions'] if r['address'] == labels['join0'] - 1)
        previous['length'] = 2
        self.assert_refused(report, 'contiguous ordinary')

    def test_new_values_after_opaque_call_can_be_read_normally(self):
        # Do not propagate across the opaque call; independently reload afterwards.
        report, _ = fixture(predicates=[[literal(1), instruction('FUNCTION', 2, {'operation': 'USR'}),
                      instruction('STORE_REAL_SCALAR', 2, {'value': 16, 'name': 'C'}), load('D')]])
        result = lift('dtl', report)
        self.assertEqual(result['falseTestJoins']['joins'][0]['status'], 'recovered')
        self.assertIn('IF D = 0', texts(result))

    def test_relocation_and_other_family_isolation(self):
        report, labels = fixture(base=0x6500)
        result = lift('dtl', report)
        self.assertEqual(result['falseTestJoins']['forwardedEdges'][0]['readingTarget'], labels['end'])
        other = program('blitz', row('CONST_U8', value=1), row('END'))
        self.assertNotIn('falseTestJoins', other)
        self.assertEqual(analyze_false_tests({'instructions': []})['joins'], [])


if __name__ == '__main__':
    unittest.main()
