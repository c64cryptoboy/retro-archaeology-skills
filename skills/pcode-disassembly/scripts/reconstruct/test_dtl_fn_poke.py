"""Authored DTL POKE corridors: call is an event, not a pure expression."""
import unittest
from collections import Counter
from dataclasses import replace

from dtl_reading import fn_value_poke
from expression_display import leaf
from symbolic import lift
from test_dtl_fn_reading import call
from test_dtl_for import instruction, literal, place
from test_dtl_reading import basic, binary, fn, load


def fixture(base=0x3300, before_call=(), after_call=()):
    # Deliberately alias the earlier address read with the call's operand.
    return place([load('Z', 16), literal(3), binary('ADD', 1), load('Z', 16),
                  *before_call, call(), *after_call, instruction('POKE', '50'),
                  instruction('END', '57', control='end')], base,
                 [{'offset': 44, 'type': 'function', 'name': 'FN ZX'},
                  {'offset': 16, 'type': 'real', 'name': 'Z'}])


class FnValuePokeTests(unittest.TestCase):
    def assert_refused(self, report):
        self.assertNotIn('fold-fn-value-poke', lift('dtl', report)['readingView']['counts'])

    def test_address_evaluated_once_before_argument_call_and_write(self):
        for base in (0x3300, 0x4100):
            report = fixture(base)
            result = lift('dtl', report)
            group = result['readingView']['groups'][0]
            self.assertEqual(group['text'], 'POKE Z + 3, FN ZX(Z)')
            self.assertEqual(group['evaluationOrder'], [base+i for i in (0, 3, 4, 6, 9)])
            self.assertEqual(group['sourceGroups'], [0, 1, 2])
            self.assertEqual(group['instructionAddresses'], [base+i for i in (0, 2, 3, 4, 6, 9)])
            self.assertTrue(any('runtime binding and purity unproved' in w for w in group['warnings']))
            self.assertFalse(any('Synthetic' in w for w in group['warnings']))
            self.assertTrue(any('Synthetic value captured' in w for w in group['detailWarnings']))
            self.assertEqual([r for g in result['groups'] for r in g['instructions']], report['instructions'])

    def test_malformed_write_and_descriptor_refuse(self):
        for index, field, value in ((5, 'bytes', '51'), (5, 'control', 'runtime-managed'),
                                    (5, 'grammar', 'basic_island'), (4, 'bytes', 'b40009'),
                                    (4, 'control', 'fallthrough')):
            report = fixture(); row = report['instructions'][index]; row[field] = value
            if value == 'basic_island':
                row['operands']['text'] = 'PRINT'
            self.assert_refused(report)
        report = fixture(); report['scalars'].append(report['scalars'][0].copy())
        self.assert_refused(report)

    def test_entry_at_instruction_or_operand_gap_and_region_refuse(self):
        for address in (0x3301, 0x3304, 0x3306, 0x3307, 0x3309):
            report = fixture(); report['instructions'][-1]['targets'] = [address]
            self.assert_refused(report)
        for field, value in (('region', 'other'), ('address', 0x3320)):
            report = fixture(); report['instructions'][5][field] = value
            self.assert_refused(report)

    def test_nested_effect_opaque_and_embedded_boundaries_refuse(self):
        for mid in (call(), fn('USR'), fn('RND')):
            self.assert_refused(fixture(before_call=[mid]))
        report = fixture(after_call=[basic(b'\x99\x22X\x22')])
        self.assert_refused(report)
        self.assertTrue(any(g['kind'] == 'embedded' for g in lift('dtl', report)['readingView']['groups']))

    def test_repeated_use_and_disordered_tree_refuse(self):
        from unittest.mock import patch
        with patch('dtl_reading.fn_value_poke', wraps=fn_value_poke) as check:
            lift('dtl', fixture())
        a, b, sink, calls, uses, targets = check.call_args.args
        self.assertIsNotNone(fn_value_poke(a, b, sink, calls, uses, targets))
        for name in (a['statement'].target, b['statement'].target):
            extra = Counter(uses); extra[name] += 1
            self.assertIsNone(fn_value_poke(a, b, sink, calls, extra, targets))
        # Same printed address read, but the tree identifies the later read.
        tree = a['statement'].expressions[0]
        tree = replace(tree, children=(leaf('Z', origin=0x3304), tree.children[1]))
        a = dict(a, statement=replace(a['statement'], expressions=(tree,)))
        self.assertIsNone(fn_value_poke(a, b, sink, calls, uses, targets))


if __name__ == '__main__':
    unittest.main()
