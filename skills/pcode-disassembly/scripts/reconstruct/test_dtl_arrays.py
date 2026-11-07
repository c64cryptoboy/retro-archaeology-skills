"""Authored descriptor/record tests; no commercial inputs or VM execution."""
import copy
import unittest
from dtl_arrays import analyze_arrays, parse_dim
from symbolic import lift, render
from test_reconstruct import row, texts, program


def raw(*items, base=0x2000):
    rows = []; address = base
    for item in copy.deepcopy(items):
        item.setdefault('region', 'main'); item.setdefault('control', 'fallthrough')
        item.setdefault('targets', []); item['address'] = address
        address += item.get('length', item.get('size', 1)); rows.append(item)
    return {'instructions': rows}


def dim(text='DIMQ$(9)', offset=12):
    return [row('BASIC', grammar='basic_island', operands={'text': text}),
            row('DELIMITER'), row('ARRAY_REGISTER', offset)]


def use(kind='STRING', offset=12, rank=1, store=False, long=False):
    items = [row('INTEGER_BYTE', n) for n in (7, 11, 3)[:rank]]
    if store:
        items.append(row('INTEGER_BYTE', 23))
    items.append(row(('STORE_' if store else 'LOAD_') + kind + '_ARRAY' + ('_LONG' if long else ''), offset))
    if not store:
        items.append(row('STORE_REAL_SCALAR', 90, operands={'name': 'Z'}))
    return items


class DTLArrayTests(unittest.TestCase):
    def refused(self, report, reason):
        index = analyze_arrays(report)
        self.assertTrue(index['accesses'])
        self.assertTrue(all(a['status'] == 'unresolved' for a in index['accesses']))
        self.assertIn(reason, str(index))
        result = lift('dtl', report)
        self.assertIn('array rank/name not established', texts(result))
        self.assertGreater(result['coverage']['unresolved'], 0)

    def test_forward_string_name_rank_and_warning(self):
        report = raw(*use(), *dim())
        result = lift('dtl', report)
        self.assertIn('Z = Q$(7)', texts(result))
        self.assertEqual(result['coverage']['unresolved'], 0)
        access = result['arrayIndex']['accesses'][0]
        self.assertTrue(access['precedesAllRegistrations'])
        self.assertEqual((access['name'], access['rank'], access['type']), ('Q$', 1, 'string'))
        self.assertTrue(any('runtime initialization is not proved' in str(g['warnings']) for g in result['groups']))
        self.assertFalse(result['arrayIndex']['runtimeInitializationProved'])

    def test_later_uses_preserve_reading(self):
        result = lift('dtl', raw(*dim(), *use()))
        self.assertIn('Z = Q$(7)', texts(result))
        self.assertFalse(result['arrayIndex']['accesses'][0]['precedesAllRegistrations'])

    def test_real_integer_multidimensional_and_long_operands(self):
        for name, kind in [('XY', 'REAL'), ('XY%', 'INTEGER')]:
            with self.subTest(kind=kind):
                result = lift('dtl', raw(*use(kind, 400, 2, long=True), *dim('DIM' + name + '(6,8)', 400)))
                self.assertIn('Z = ' + name + '(7, 11)', texts(result))
                self.assertEqual(result['coverage']['partial'], 0)

    def test_forward_store_subscript_value_order(self):
        result = lift('dtl', raw(*use('INTEGER', rank=2, store=True), *dim('DIMQ%(8,12)')))
        self.assertIn('Q%(7, 11) = 23', texts(result))
        self.assertEqual(result['arrayIndex']['accesses'][0]['access'], 'write')

    def test_parser_nested_bounds_quotes_spaces_and_multiple_arrays(self):
        self.assertEqual(parse_dim('DIM A(FNX(2)), B%(3,4), QQ$(F("x,y"),2) '),
                         [('A', 1, 'real'), ('B%', 2, 'integer'), ('QQ$', 2, 'string')])
        report = raw(*use('INTEGER', 14, 2),
                     row('BASIC', grammar='basic_island', operands={'text': 'DIMA(FNF(2)),B%(3,4)'}),
                     row('ARRAY_REGISTER', 12), row('ARRAY_REGISTER', 14))
        self.assertIn('Z = B%(7, 11)', texts(lift('dtl', report)))

    def test_bad_or_partial_dim_syntax_refused(self):
        for text in ('DIM', 'DIMA()', 'DIMA(,2)', 'DIMA(2,)', 'DIMA(2',
                     'DIMA(2),', 'DIMA(2):PRINT1', 'DIMA("x)', 'DIMA(2)JUNK'):
            with self.subTest(text=text):
                self.assertEqual(parse_dim(text), [])
                self.refused(raw(*use('REAL'), *dim(text)), 'validated DIM')

    def test_no_declaration_refused(self):
        self.refused(raw(*use()), 'No binary DIM')

    def test_unpaired_registration_refused(self):
        self.refused(raw(*use(), row('ARRAY_REGISTER', 12)), 'validated DIM')

    def test_intervening_statement_clears_pending_pairing(self):
        declaration = dim()
        self.refused(raw(*use(), *declaration[:1], row('INTEGER_BYTE', 1), *declaration[1:]), 'validated DIM')

    def test_incomplete_multi_registration_bundle_refused(self):
        self.refused(raw(*use('REAL'), *dim('DIMA(2),B(3)')), 'Incomplete')

    def test_region_or_address_gap_refused(self):
        for mode in ('region', 'gap'):
            report = raw(*use(), *dim())
            if mode == 'region':
                report['instructions'][-1]['region'] = 'initialization'
            else:
                report['instructions'][-1]['address'] += 2
            self.refused(report, 'validated DIM')

    def test_foreign_entry_to_pairing_corridor_refused(self):
        for target in (-2, -1):
            report = raw(*use(), *dim(), row('GOTO'))
            report['instructions'][-1]['targets'] = [report['instructions'][target - 1]['address']]
            # Inspect association only: intentionally incomplete synthetic GOTO operands.
            index = analyze_arrays(report)
            self.assertEqual(index['accesses'][0]['status'], 'unresolved')

    def test_entry_at_dim_is_allowed(self):
        report = raw(*use(), *dim(), row('GOTO'))
        report['instructions'][-1]['targets'] = [report['instructions'][-4]['address']]
        self.assertEqual(analyze_arrays(report)['accesses'][0]['status'], 'associated')

    def test_conflicting_name_rank_or_type_refused_globally(self):
        for text in ('DIMW$(9)', 'DIMQ$(9,2)', 'DIMQ%(9)'):
            with self.subTest(text=text):
                self.refused(raw(*dim(), *use(), *dim(text)), 'Conflicting')

    def test_identical_redeclarations_recorded_not_runtime_proved(self):
        result = lift('dtl', raw(*dim(), *use(), *dim()))
        descriptor = result['arrayIndex']['descriptors'][0]
        self.assertEqual(descriptor['status'], 'associated')
        self.assertEqual(len(descriptor['registrations']), 2)
        self.assertFalse(result['arrayIndex']['runtimeInitializationProved'])

    def test_orphan_reassignment_invalidates_other_valid_candidate(self):
        self.refused(raw(*dim(), *use(), row('ARRAY_REGISTER', 12)), 'validated DIM')

    def test_typed_use_mismatch_refused(self):
        self.refused(raw(*use('REAL'), *dim()), 'Typed array accesses disagree')

    def test_missing_subscript_stays_partial(self):
        result = lift('dtl', raw(row('LOAD_STRING_ARRAY', 12), row('STORE_REAL_SCALAR', 90), *dim()))
        self.assertIn('Q$(<?>)', texts(result))
        self.assertGreater(result['coverage']['partial'], 0)

    def test_relocation_replay_ownership_and_no_mutation(self):
        report = raw(*use(), *dim(), base=0x3800); before = copy.deepcopy(report)
        result = lift('dtl', report)
        self.assertEqual(report, before)
        self.assertEqual([r for g in result['groups'] for r in g['instructions']], report['instructions'])
        self.assertEqual(result, lift('dtl', report))
        self.assertEqual(sum(result['coverage'].values()), len(report['instructions']))
        self.assertIn('; DTL ARRAY INDEX', render(result))
        self.assertIn('L_3805', render(result))

    def test_other_families_do_not_get_dtl_array_rules(self):
        self.assertNotIn('arrayIndex', program('petspeed', row('END')))


if __name__ == '__main__':
    unittest.main()
