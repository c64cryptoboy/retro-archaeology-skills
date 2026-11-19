"""Independent, authored DTL nested POKE: test evaluation identity, not spelling alone."""
import unittest
from collections import Counter
from dataclasses import replace
from unittest.mock import patch

from dtl_reading import nested_fn_poke
from symbolic import lift
from test_dtl_fn_reading import call
from test_dtl_for import instruction, place
from test_dtl_reading import basic, load


def example(base=0x5040, between=()):
    # Aliasing makes order material.  Asymmetric BE16 descriptors have nonzero high bytes.
    return place([load('P', 16), load('P', 16), call(0x134, 'FN AL'), *between,
                  call(0x251, 'FN BE'), instruction('POKE', '50'), instruction('END', '57', control='end')],
                 base, [dict(offset=16, type='real', name='P'), dict(offset=0x134, type='function', name='FN AL'),
                        dict(offset=0x251, type='function', name='FN BE')])


class NestedFnPokeTests(unittest.TestCase):
    def test_alias_read_sites_and_nested_call_identities(self):
        for base in (0x5040, 0x2880):
            report = example(base)
            result = lift('dtl', report)
            item = result['readingView']['groups'][0]
            self.assertEqual(item['text'], 'POKE P, FN BE(FN AL(P))')
            order = [base+i for i in (0, 2, 4, 7, 10)]
            self.assertEqual(item['evaluationOrder'], order)
            self.assertEqual(item['instructionAddresses'], order)
            self.assertEqual(item['sourceGroups'], [0, 1, 2, 3])
            self.assertEqual(item['actions'], [dict(kind='fold-nested-fn-poke', calls=order[2:4], poke=order[-1])])
            self.assertTrue(any('runtime binding and purity unproved' in w for w in item['warnings']))
            self.assertEqual([r for g in result['groups'] for r in g['instructions']], report['instructions'])

    def test_either_descriptor_and_interior_entry_must_validate(self):
        for index in (2, 3):
            for field, value in (('bytes', 'b43401'), ('control', 'fallthrough')):
                report = example(); report['instructions'][index][field] = value
                self.assertNotIn('fold-nested-fn-poke', lift('dtl', report)['readingView']['counts'])
        for off in (2, 5, 7, 10):
            report = example(); report['instructions'][-1]['targets'] = [0x5040 + off]
            self.assertNotIn('fold-nested-fn-poke', lift('dtl', report)['readingView']['counts'])
        for middle in ([basic(b'\x99"X"')], [call(0x134, 'FN AL')]):
            result = lift('dtl', example(between=middle))
            self.assertNotIn('fold-nested-fn-poke', result['readingView']['counts'])

    def test_repeated_consumer_wrong_read_site_or_wrong_call_edge_refuse(self):
        with patch('dtl_reading.nested_fn_poke', wraps=nested_fn_poke) as check:
            lift('dtl', example())
        entries, calls, uses, targets = check.call_args.args
        for item in entries[:3]:
            extra = Counter(uses); extra[item['statement'].target] += 1
            self.assertIsNone(nested_fn_poke(entries, calls, extra, targets))
        dest, inner, outer, sink = [item['statement'] for item in entries]
        # Both scalar reads print P.  Never replace the earlier sample with the later one.
        for index, wrong in ((0, inner.expressions[0].children[0]),
                             (2, replace(outer.expressions[0], children=(sink.expressions[0],))),
                             (1, replace(inner.expressions[0], token='FN BE'))):
            altered = entries.copy()
            altered[index] = dict(entries[index], statement=replace(entries[index]['statement'], expressions=(wrong,)))
            self.assertIsNone(nested_fn_poke(altered, calls, uses, targets))
