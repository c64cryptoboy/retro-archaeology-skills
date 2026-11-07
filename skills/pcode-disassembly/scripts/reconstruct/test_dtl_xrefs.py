"""Authored DTL static-reference cases, not execution or source-oracle tests."""
from copy import deepcopy
import unittest
from dtl_arrays import analyze_arrays
from dtl_xrefs import analyze_xrefs, render_xrefs
from symbolic import Lifter, lift, render
from test_reconstruct import row, program
from test_dtl_arrays import raw, dim, use


def scalar(offset, name, kind='real'):
    return {'offset': offset, 'address': 0x6000 + offset - 2, 'name': name, 'type': kind, 'raw': '00000000000000'}


def xrefs(report):
    return analyze_xrefs(report, analyze_arrays(report))


def var(index, namespace, offset):
    return next(v for v in index['variables'] if (v['namespace'], v['offset']) == (namespace, offset))


def gosub(*targets, table=False):
    return row('ON_GOSUB' if table else 'GOSUB',
               grammar='target_table' if table else 'xor_target',
               control='multi-branch' if table else 'call',
               length=2 + 2 * len(targets) if table else 3,
               operands={'count': 2 * len(targets)} if table else {'raw': '0000'}, targets=list(targets))


class DTLXrefTests(unittest.TestCase):
    def test_scalar_typed_short_long_read_write_and_table_identity(self):
        for kind, name in [('real', 'AZ'), ('integer', 'AZ%'), ('string', 'AZ$')]:
            with self.subTest(kind=kind):
                report = raw(row('LOAD_' + kind.upper() + '_SCALAR', 19),
                             row('STORE_' + kind.upper() + '_SCALAR_LONG', 19))
                report['scalars'] = [scalar(19, name, kind)]
                index = xrefs(report); item = var(index, 'scalar', 19)
                self.assertEqual(item['name'], name)
                self.assertEqual(item['nameProvenance'], 'binary-scalar-record')
                self.assertEqual([s['role'] for s in item['sites']], ['read', 'write'])
                self.assertTrue(all(s['status'] == 'decoded-reference' for s in item['sites']))
                self.assertEqual(item['scalarRecords'], report['scalars'])

    def test_scalar_and_array_offsets_are_separate_namespaces(self):
        report = raw(row('LOAD_REAL_SCALAR', 12), *dim(), *use())
        report['scalars'] = [scalar(12, 'Q')]
        index = xrefs(report)
        self.assertEqual(var(index, 'scalar', 12)['name'], 'Q')
        self.assertEqual(var(index, 'array', 12)['name'], 'Q$')
        self.assertEqual([s['role'] for s in var(index, 'array', 12)['sites']], ['descriptor-write', 'read'])

    def test_forward_array_name_rank_and_store_role(self):
        report = raw(*use('INTEGER', rank=2, store=True, long=True), *dim('DIMQ%(4,5)'))
        item = var(xrefs(report), 'array', 12)
        self.assertEqual((item['name'], item['rank'], item['type']), ('Q%', 2, 'integer'))
        self.assertEqual([s['role'] for s in item['sites']], ['write', 'descriptor-write'])
        self.assertEqual(item['registrations'], [report['instructions'][-1]['address']])

    def test_conflicting_array_association_stays_unnamed(self):
        item = var(xrefs(raw(*dim(), *use(), *dim('DIMR$(3)'))), 'array', 12)
        self.assertIsNone(item['name'])
        self.assertTrue(all(s['status'] == 'unnamed-reference' for s in item['sites']))
        self.assertIn('Conflicting', str(item['reasons']))

    def test_missing_scalar_record_does_not_trust_operand_name(self):
        report = raw(row('LOAD_REAL_SCALAR', 21, operands={'name': 'GUESS'}))
        item = var(xrefs(report), 'scalar', 21)
        self.assertIsNone(item['name'])
        self.assertEqual(item['sites'][0]['operands']['name'], 'GUESS')
        self.assertEqual(item['sites'][0]['status'], 'unnamed-reference')

    def test_duplicate_or_malformed_scalar_names_refuse_naming(self):
        for records in ([scalar(9, 'X'), scalar(9, 'Y')], [scalar(9, 'TOOLONG')], [scalar(9, 'X$', 'real')]):
            report = raw(row('LOAD_REAL_SCALAR', 9)); report['scalars'] = records
            self.assertIsNone(var(xrefs(report), 'scalar', 9)['name'])

    def test_type_mismatch_is_not_presented_as_normal_typed_access(self):
        report = raw(row('STORE_STRING_SCALAR', 9)); report['scalars'] = [scalar(9, 'X')]
        index = xrefs(report); item = var(index, 'scalar', 9)
        self.assertEqual(item['name'], 'X')
        self.assertEqual(item['sites'][0]['status'], 'type-mismatch')
        self.assertIn('!type-mismatch', '\n'.join(render_xrefs(index)))

    def test_retained_record_without_sites_not_called_dead(self):
        report = raw(row('DELIMITER')); report['scalars'] = [scalar(9, 'X')]
        item = var(xrefs(report), 'scalar', 9)
        self.assertEqual(item['sites'], [])
        self.assertIn('not proof of unused', '\n'.join(render_xrefs(xrefs(report))))

    def test_loop_roles_do_not_invent_initializer_or_next_binding(self):
        report = raw(row('FOR_REAL', 9), row('FOR_REAL_STEP', 9), row('FOR_INTEGER', 16),
                     row('FOR_INTEGER_STEP', 16), row('NEXT_NAMED', 9), row('NEXT'))
        report['scalars'] = [scalar(9, 'I'), scalar(16, 'J%', 'integer')]
        index = xrefs(report)
        self.assertEqual([s['role'] for s in var(index, 'scalar', 9)['sites']],
                         ['loop-setup-reference', 'loop-setup-reference', 'implicit-read-write'])
        self.assertEqual(len(index['dynamicSites']), 1)
        self.assertNotIn('offset', index['dynamicSites'][0])
        self.assertFalse(any(s['role'] == 'write' for v in index['variables'] for s in v['sites']))

    def test_function_descriptor_bias_and_formal_reference(self):
        report = raw(row('DEF_FN', operands={'descriptorOffset': 13, 'parameterOffset': 9}),
                     row('FN_CALL', 16), row('FN_RETURN'))
        report['scalars'] = [scalar(9, 'X'), scalar(16, 'FN Z', 'function')]
        index = xrefs(report)
        function = var(index, 'scalar', 16)
        self.assertEqual([s['role'] for s in function['sites']], ['descriptor-write', 'descriptor-read'])
        self.assertEqual(function['sites'][0]['operandField'], 'descriptorOffset + 3')
        self.assertEqual(function['sites'][0]['operands']['descriptorOffset'], 13)
        self.assertEqual(var(index, 'scalar', 9)['sites'][0]['role'], 'formal-reference')
        self.assertEqual(index['dynamicSites'][0]['role'], 'formal-restore')
        self.assertEqual(index['callSites'], [])

    def test_direct_calls_and_unpaired_returns(self):
        report = raw(gosub(0x2006), gosub(0x2006), row('RETURN'))
        index = xrefs(report)
        self.assertEqual(len(index['callSites']), 2)
        self.assertEqual(len(index['subroutineTargets']), 1)
        self.assertEqual([c['address'] for c in index['subroutineTargets'][0]['callers']], [0x2000, 0x2003])
        self.assertEqual([s['address'] for s in index['returnSites']], [0x2006])
        self.assertFalse(index['returnPairingProved'])
        self.assertNotIn('end', index['subroutineTargets'][0])

    def test_on_gosub_preserves_table_order_and_duplicate_targets(self):
        report = raw(gosub(0x2009, 0x2008, 0x2009, table=True), row('RETURN'), row('RETURN'))
        index = xrefs(report); entries = index['callSites'][0]['entries']
        self.assertEqual([(e['target'], e['tableEntry']) for e in entries], [(0x2009, 1), (0x2008, 2), (0x2009, 3)])
        self.assertEqual([c['tableEntry'] for c in index['subroutineTargets'][1]['callers']], [1, 3])
        self.assertIn('entry 3', '\n'.join(render_xrefs(index)))

    def test_empty_on_table_is_not_an_invented_target(self):
        index = xrefs(raw(gosub(table=True), row('RETURN')))
        self.assertEqual(index['callSites'][0]['status'], 'decoded-targets')
        self.assertEqual(index['subroutineTargets'], [])

    def test_goto_and_function_calls_not_counted_as_gosub(self):
        index = xrefs(raw(row('GOTO', targets=[0x2003]), row('ON_GOTO', targets=[0x2003]),
                          row('FN_CALL', 9), row('RETURN')))
        self.assertEqual(index['callSites'], [])
        self.assertEqual(index['subroutineTargets'], [])

    def test_cross_region_call_retains_both_regions(self):
        report = raw(gosub(0x2003), row('RETURN', region='init'))
        index = xrefs(report); target = index['subroutineTargets'][0]
        self.assertEqual(target['region'], 'init')
        self.assertEqual(target['callers'][0]['region'], 'main')

    def test_bad_target_or_table_contract_is_not_linked(self):
        fixtures = [raw(gosub(0x2222), row('RETURN')), raw(gosub(0x2001)),
                    raw(gosub(0x2003, 0x2003), row('RETURN')),
                    raw(gosub(0x2004, table=True), row('RETURN'))]
        fixtures[-1]['instructions'][0]['operands']['count'] = 4
        for report in fixtures:
            index = xrefs(report)
            self.assertEqual(index['callSites'][0]['status'], 'refused')
            self.assertTrue(index['callSites'][0]['reasons'])
            self.assertEqual(index['subroutineTargets'], [])

    def test_opaque_basic_native_and_memory_sites_not_false_variable_uses(self):
        report = raw(row('BASIC', grammar='basic_island', operands={'text': 'READQ$'}),
                     row('SYS'), row('FUNCTION', operands={'operation': 'USR'}),
                     row('FUNCTION_F8', operands={'operation': 'PEEK'}), row('POKE'), row('DIRECTIVE'))
        index = xrefs(report)
        self.assertEqual(len(index['opaqueSites']), 6)
        self.assertEqual(index['variables'], [])
        self.assertEqual(index['callSites'], [])
        self.assertFalse(index['completeAccessGraph'])
        self.assertFalse(index['reachabilityProved'])

    def test_data_cursor_locations_not_data_values_or_destinations(self):
        report = raw(row('BASIC', grammar='basic_island', operands={'text': 'READA,B$'}), row('RESTORE'),
                     row('BASIC', grammar='basic_island', operands={'text': 'PRINT"READA"'}))
        index = xrefs(report)
        self.assertEqual([s['role'] for s in index['dataCursorSites']], ['embedded-READ', 'reset-DATA-cursor'])
        self.assertEqual(index['variables'], [])

    def test_system_variables_separate_from_storage_offsets(self):
        report = raw(*(row('FUNCTION_F8', operands={'operation': op}) for op in ('TI', 'TI$', 'ST', 'SET_TI$')))
        index = xrefs(report)
        self.assertEqual([s['role'] for s in index['systemVariableSites']], ['read', 'read', 'read', 'write'])
        self.assertEqual(index['systemVariableSites'][-1]['name'], 'TI$')
        self.assertEqual(index['variables'], [])

    def test_global_runtime_sites_not_distributed_as_writes(self):
        report = raw(*(row(n) for n in ('CLEAR_OR_RUN', 'RUN_BOOTSTRAP', 'INIT_DECODE', 'INIT_ENTER', 'VARIABLE_FILE')))
        index = xrefs(report)
        self.assertEqual(len(index['dynamicSites']), 5)
        self.assertEqual(index['variables'], [])

    def test_unknown_or_invalid_operand_is_visible_not_guessed(self):
        report = raw(row('UNKNOWN_REFERENCE', 9, grammar='var16'), row('LOAD_REAL_SCALAR', -1),
                     row('LOAD_REAL_SCALAR', True), row('LOAD_REAL_SCALAR', 65536))
        index = xrefs(report)
        self.assertEqual(len(index['unclassifiedReferences']), 4)
        self.assertEqual(index['variables'], [])

    def test_deterministic_relocation_copy_and_lifting_is_metadata_only(self):
        report = raw(row('INTEGER_BYTE', 4), row('STORE_REAL_SCALAR', 9), *dim(), *use(), base=0x3200)
        report['scalars'] = [scalar(9, 'X'), scalar(90, 'Z')]; before = deepcopy(report)
        direct = Lifter('dtl', report).run(); result = lift('dtl', report)
        self.assertEqual(result['groups'], direct['groups'])
        self.assertEqual(result['coverage'], direct['coverage'])
        self.assertEqual(result['staticIndex'], xrefs(report))
        self.assertEqual(result, lift('dtl', report))
        self.assertEqual(report, before)
        self.assertIn('L_3201[main]', render(result))
        result['staticIndex']['variables'][-1]['sites'][0]['operands']['value'] = 999
        self.assertEqual(report, before)

    def test_other_families_have_no_dtl_xrefs(self):
        self.assertNotIn('staticIndex', program('blitz', row('END')))


if __name__ == '__main__':
    unittest.main()
