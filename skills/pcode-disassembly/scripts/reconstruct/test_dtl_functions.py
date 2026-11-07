"""Portable authored records, not title bytes, source or executed VM fixtures."""
import copy
import unittest
from dtl_functions import analyze_functions
from symbolic import lift, render
from test_reconstruct import program, row, texts


def instruction(name, length=1, operands=None, control='fallthrough', targets=(), **kw):
    return {'mnemonic': name, 'length': length, 'bytes': '00' * length,
            'operands': operands or {}, 'control': control, 'targets': list(targets),
            'grammar': 'none', 'region': 'main', **kw}


def fixture(base=0x2000, body=None):
    if body is None:
        body = [instruction('LOAD_REAL_SCALAR', 2, {'value': 9, 'name': 'K'}),
                instruction('INTEGER_BYTE', 2, {'value': 7}), instruction('SUBTRACT')]
    body = copy.deepcopy(body) + [instruction('FN_RETURN', control='function-return')]
    end = base + 8 + sum(r['length'] for r in body)
    header = instruction('DEF_FN', 8, {'descriptorOffset': 41, 'parameterOffset': 9,
                         'bodyEntry': base + 8, 'skipBytes': end - base},
                         control='definition', targets=[base + 8, end], grammar='fn_definition')
    rows = [header] + body + [instruction('INTEGER_BYTE', 2, {'value': 19}),
                             instruction('FN_CALL', 3, {'value': 44, 'name': 'FN ZX'},
                                         control='descriptor-indirect-call'),
                             instruction('STORE_REAL_SCALAR', 2, {'value': 16, 'name': 'Z'}),
                             instruction('END', control='end')]
    address = base
    for r in rows:
        r['address'] = address
        address += r['length']
    return {'instructions': rows, 'scalars': [{'offset': 44, 'type': 'function', 'name': 'FN ZX'},
                                            {'offset': 9, 'type': 'real', 'name': 'K'},
                                            {'offset': 16, 'type': 'real', 'name': 'Z'}]}


class DTLFunctionTests(unittest.TestCase):
    def assert_block_refused(self, report, reason):
        index = analyze_functions(report)
        self.assertEqual(index['definitions'][0]['status'], 'unresolved')
        self.assertIn(reason, ' '.join(index['definitions'][0]['reasons']))
        result = lift('dtl', report)
        self.assertIn('REM DEF FN descriptor', texts(result))
        self.assertNotIn('RETURN FN ZX =', texts(result))
        self.assertGreater(result['coverage']['partial'], 0)
        self.assertEqual([r for g in result['groups'] for r in g['instructions']], report['instructions'])

    def test_descriptor_plus_three_and_formal_name(self):
        report = fixture()
        result = lift('dtl', report)
        d = result['functionIndex']['definitions'][0]
        self.assertEqual((d['descriptorOffset'], d['descriptorValueOffset']), (41, 44))
        self.assertEqual((d['name'], d['parameterName'], d['status']), ('FN ZX', 'K', 'block'))
        self.assertIn('DEF FN ZX(K); body L_2008; continuation L_200E', texts(result))
        self.assertIn('RETURN FN ZX = K - 7', texts(result))
        self.assertIn('FN ZX(19)', texts(result))
        self.assertEqual(d['callSites'], [0x2010])
        self.assertEqual(result['functionIndex']['calls'][0]['candidateDefinitions'], [0x2000])
        self.assertEqual(result['coverage']['partial'], 0)

    def test_relocation_and_exact_ownership_without_mutating_input(self):
        report = fixture(0x3800)
        before = copy.deepcopy(report)
        result = lift('dtl', report)
        self.assertEqual(report, before)
        self.assertEqual([r for g in result['groups'] for r in g['instructions']], report['instructions'])
        self.assertTrue(all(g['instructions'] for g in result['groups']))
        self.assertEqual(sum(result['coverage'].values()), len(report['instructions']))
        self.assertIn('body L_3808', texts(result))
        self.assertIn('; DTL FUNCTION INDEX', render(result))
        self.assertIn('static call sites: L_3810', render(result))
        self.assertEqual(lift('dtl', report), result)
        self.assertFalse(result['sourceSupplied']); self.assertFalse(result['mapsUsed'])

    def test_wrong_encoded_offset_does_not_link_by_spelling(self):
        report = fixture()
        report['instructions'][-3]['operands']['value'] = 41
        c = analyze_functions(report)['calls'][0]
        self.assertEqual(c['candidateDefinitions'], [])
        self.assertEqual(c['status'], 'unresolved')
        self.assertIn('FN F_41(19)', texts(lift('dtl', report)))

    def test_missing_duplicate_or_wrong_typed_function_scalar(self):
        for mode in ('missing', 'duplicate', 'type', 'name'):
            with self.subTest(mode=mode):
                report = fixture()
                if mode == 'missing': report['scalars'].pop(0)
                elif mode == 'duplicate': report['scalars'].append(dict(report['scalars'][0]))
                elif mode == 'type': report['scalars'][0]['type'] = 'real'
                else: report['scalars'][0]['name'] = 'ZX'
                self.assert_block_refused(report, 'Function scalar/name')

    def test_missing_duplicate_or_wrong_typed_formal(self):
        for mode in ('missing', 'duplicate', 'type', 'name'):
            with self.subTest(mode=mode):
                report = fixture()
                if mode == 'missing': report['scalars'].pop(1)
                elif mode == 'duplicate': report['scalars'].append(dict(report['scalars'][1]))
                elif mode == 'type': report['scalars'][1]['type'] = 'integer'
                else: report['scalars'][1]['name'] = 'K$'
                self.assert_block_refused(report, 'Formal scalar/name')

    def test_call_name_mismatch_remains_explicit(self):
        report = fixture()
        report['instructions'][-3]['operands']['name'] = 'FN XY'
        result = lift('dtl', report)
        c = result['functionIndex']['calls'][0]
        self.assertEqual(c['status'], 'unresolved')
        self.assertIn('disagrees', ' '.join(c['reasons']))
        self.assertIn('FN F_44(19)', texts(result))

    def test_no_definition_and_embedded_definition_not_conflated(self):
        report = fixture()
        report['instructions'] = report['instructions'][-4:]
        report['instructions'].insert(0, instruction('BASIC', operands={'text': 'DEFFNZX(K)=K+2'},
                                                   grammar='basic_island', address=0x1800))
        result = lift('dtl', report)
        index = result['functionIndex']
        self.assertEqual(index['definitions'], [])
        self.assertEqual(index['calls'][0]['candidateDefinitions'], [])
        self.assertEqual(len(index['embeddedDefinitions']), 1)
        self.assertEqual(result['groups'][0]['kind'], 'embedded')
        self.assertIn('EMBEDDED L_1800', render(result))

    def test_multiple_definitions_and_calls_before_definition_not_runtime_binding(self):
        report = fixture()
        other = fixture(0x3000)
        before = instruction('FN_CALL', 3, {'value': 44, 'name': 'FN ZX'},
                             control='descriptor-indirect-call', address=0x1900)
        report['instructions'] = [before] + report['instructions'] + other['instructions']
        index = analyze_functions(report)
        self.assertFalse(index['runtimeBindingProved']); self.assertFalse(index['purityProved'])
        self.assertTrue(all(d['status'] == 'block' for d in index['definitions']))
        for c in index['calls']:
            self.assertEqual(c['candidateDefinitions'], [0x2000, 0x3000])
            self.assertEqual(c['status'], 'multiple-static-candidates')
        self.assertIn('CALL L_1900 [multiple-static-candidates]', render(lift('dtl', report)))

    def test_single_candidate_before_definition_also_unproved(self):
        report = fixture()
        call = copy.deepcopy(report['instructions'][-3]); call['address'] = 0x1900
        report['instructions'].insert(0, call)
        index = analyze_functions(report)
        self.assertEqual(index['calls'][0]['status'], 'one-static-candidate')
        self.assertFalse(index['runtimeBindingProved'])

    def test_recursive_call_is_indexed_without_inlining_or_purity(self):
        report = fixture(body=[instruction('LOAD_REAL_SCALAR', 2, {'value': 9, 'name': 'K'}),
                               instruction('FN_CALL', 3, {'value': 44, 'name': 'FN ZX'},
                                           control='descriptor-indirect-call')])
        result = lift('dtl', report)
        self.assertEqual(len(result['functionIndex']['definitions'][0]['callSites']), 2)
        self.assertIn('RETURN FN ZX = T_200A', texts(result))
        self.assertFalse(result['functionIndex']['purityProved'])
        self.assertIn('runtime binding and purity unproved', str(result['groups']))

    def test_interfunction_call_does_not_inline_other_body(self):
        report = fixture(body=[instruction('INTEGER_BYTE', 2, {'value': 3}),
                               instruction('FN_CALL', 3, {'value': 51, 'name': 'FN YQ'},
                                           control='descriptor-indirect-call')])
        other = fixture(0x3000)
        other['instructions'][0]['operands']['descriptorOffset'] = 48
        other['scalars'][0].update(offset=51, name='FN YQ')
        other['instructions'][-3]['operands'].update(value=51, name='FN YQ')
        report['instructions'] += other['instructions']
        report['scalars'].append(other['scalars'][0])
        result = lift('dtl', report)
        self.assertEqual(result['functionIndex']['calls'][0]['candidateDefinitions'], [0x3000])
        self.assertIn('T_200A = FN YQ(3)', texts(result))
        self.assertIn('RETURN FN ZX = T_200A', texts(result))

    def test_effectful_body_preserves_temps_once_in_order(self):
        report = fixture(body=[instruction('INTEGER_BYTE', 2, {'value': 1}),
                               instruction('FUNCTION', 2, {'operation': 'RND'}),
                               instruction('LOAD_REAL_SCALAR', 2, {'value': 9, 'name': 'K'}),
                               instruction('ADD')])
        result = lift('dtl', report)
        text = texts(result)
        self.assertEqual(text.count('RND('), 1)
        self.assertLess(text.index('T_200A = RND(1)'), text.index('RETURN FN ZX = T_200A + K'))
        self.assertFalse(result['functionIndex']['purityProved'])

    def test_body_capture_remains_at_producer_before_argument_effects(self):
        report = fixture(body=[instruction('LOAD_REAL_SCALAR', 2, {'value': 9, 'name': 'K'}),
                               instruction('INTEGER_BYTE', 2, {'value': 1}),
                               instruction('FUNCTION', 2, {'operation': 'RND'}),
                               instruction('FN_CALL', 3, {'value': 44, 'name': 'FN ZX'},
                                           control='descriptor-indirect-call'), instruction('ADD')])
        result = lift('dtl', report); text = texts(result)
        self.assertLess(text.index('T_VALUE_2008 = K'), text.index('T_200C = RND'))
        self.assertIn('RETURN FN ZX = T_VALUE_2008 + T_200E', text)
        self.assertEqual(text.count('RND('), 1)

    def test_missing_return_refuses_block(self):
        report = fixture(); report['instructions'][4]['mnemonic'] = 'END'
        self.assert_block_refused(report, 'FN_RETURN')

    def test_header_skip_and_target_inconsistency_refuses(self):
        for field in ('bodyEntry', 'skipBytes'):
            with self.subTest(field=field):
                report = fixture(); report['instructions'][0]['operands'][field] += 1
                self.assert_block_refused(report, 'Header/body/skip')

    def test_discontiguous_body_refuses(self):
        report = fixture(); report['instructions'][2]['address'] += 1
        self.assert_block_refused(report, 'not contiguous')

    def test_region_crossing_and_missing_continuation_refuse(self):
        report = fixture(); report['instructions'][2]['region'] = 'init'
        self.assert_block_refused(report, 'region boundary')
        report = fixture(); report['instructions'][5]['region'] = 'init'
        self.assert_block_refused(report, 'Continuation')

    def test_foreign_entry_at_body_or_return_refuses(self):
        for target in (0x2008, 0x200D):
            with self.subTest(target=target):
                report = fixture()
                report['instructions'].insert(0, instruction('GOTO', control='jump', targets=[target], address=0x1800))
                self.assert_block_refused(report, 'foreign explicit')

    def test_internal_control_or_early_return_refuses(self):
        for name, control in (('GOTO', 'jump'), ('SYS', 'native-call'), ('FN_RETURN', 'function-return')):
            with self.subTest(name=name):
                report = fixture()
                report['instructions'][2].update(mnemonic=name, control=control, targets=[0x200D])
                if name == 'SYS':
                    report['instructions'][2]['operands'].update(tail='', returnCaveat='opaque native call')
                self.assert_block_refused(report, 'unsupported body control')

    def test_overlapping_or_nested_definitions_refuse_both(self):
        report = fixture(); nested = fixture(0x2008)
        report['instructions'].append(nested['instructions'][0])
        index = analyze_functions(report)
        self.assertEqual(len(index['definitions']), 2)
        for d in index['definitions']:
            self.assertEqual(d['status'], 'unresolved')
            self.assertIn('overlap or nest', ' '.join(d['reasons']))

    def test_unknown_body_expression_stays_partial(self):
        report = fixture(body=[instruction('MYSTERY')])
        result = lift('dtl', report)
        self.assertEqual(result['functionIndex']['definitions'][0]['status'], 'block')
        self.assertIn('RETURN FN ZX = <?>', texts(result))
        self.assertGreater(result['coverage']['partial'], 0)
        self.assertGreater(result['coverage']['unresolved'], 0)

    def test_other_families_do_not_get_dtl_function_index(self):
        for family in ('blitz', 'austrospeed', 'petspeed', 'basic64'):
            with self.subTest(family=family):
                result = program(family, row('END'))
                self.assertNotIn('functionIndex', result)


if __name__ == '__main__':
    unittest.main()
