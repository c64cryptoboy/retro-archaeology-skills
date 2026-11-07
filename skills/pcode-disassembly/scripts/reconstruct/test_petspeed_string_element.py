"""Synthetic decoded-record semantics, not image admission or target execution."""
import importlib.util
import json
from pathlib import Path
import unittest

from symbolic import Expr, Lifter, lift, render


def row(mnemonic, **operands):
    return {'mnemonic': mnemonic, 'bytes': '00', 'size': 1,
            'grammar': 'none', 'operands': operands}


def program(*rows, family='petspeed'):
    return lift(family, {'instructions': [
        {'address': 0x1000 + i, **record} for i, record in enumerate(rows)
    ], 'typedDataRecords': []})


def load(address=0x2800):
    return row('LOAD_STRING_ELEMENT_AT', value=address)


def texts(result):
    return '\n'.join(group['text'] for group in result['groups'])


class PETSpeedStringElementTests(unittest.TestCase):
    def test_opaque_slot_print_retains_warning_and_exact_ownership(self):
        result = program(load(), row('PRINT_STRING'))
        self.assertEqual(texts(result), 'PRINT STRDESC_2800$;')
        group = result['groups'][0]
        self.assertEqual(group['evidenceAddresses'], [0x1000, 0x1001])
        self.assertEqual([r['address'] for r in group['instructions']], [0x1000, 0x1001])
        self.assertEqual(result['instructionCount'], 2)
        self.assertEqual(result['symbols'], {})
        warnings = ' '.join(group['warnings'])
        self.assertIn('absolute three-byte descriptor slot', warnings)
        self.assertIn('array identity/dimensions/subscripts not recovered', warnings)
        self.assertIn('character bytes are not copied', warnings)
        rendered = render(result)
        self.assertIn('PRINT STRDESC_2800$;', rendered)
        self.assertIn('absolute three-byte descriptor slot', rendered)
        self.assertIn('LOAD_STRING_ELEMENT_AT', rendered)

    def test_direct_contract_replaces_fac_preserves_arg_and_is_not_snapshot(self):
        record = {'address': 0x1000, **load()}
        lifter = Lifter('petspeed', {'instructions': [record]})
        argument = Expr('EARLIER_ARG', {0x0900})
        lifter.regs.update(fac=Expr('STALE_FAC'), arg=argument,
                           arraybase=Expr('OLD_ARRAY_BASE'))
        lifter.current = record
        self.assertTrue(lifter.special(record))
        expression = lifter.get('fac')
        self.assertEqual(expression.text, 'STRDESC_2800$')
        self.assertEqual(expression.deps, {0x1000})
        self.assertEqual(expression.producer, 0x1000)
        self.assertFalse(expression.stable)
        self.assertFalse(expression.reference)
        self.assertIs(lifter.get('arg'), argument)
        self.assertEqual(lifter.get('arraybase').text, 'OLD_ARRAY_BASE')
        self.assertEqual(lifter.symbols, {})

    def test_no_index_or_array_base_needed(self):
        result = program(row('ARRAY_BASE', value=0x4300),
                         row('CONST_U8_FAC', value=99), load(0x2812), row('PRINT_STRING'))
        self.assertEqual(texts(result), 'PRINT STRDESC_2812$;')
        self.assertNotIn('ELEM_', texts(result))
        self.assertNotIn('99', texts(result))

    def test_distinct_slots_remain_distinct_without_inventing_literals(self):
        result = program(load(0x2800), row('PRINT_STRING'),
                         load(0x2803), row('PRINT_STRING'))
        self.assertEqual(texts(result), 'PRINT STRDESC_2800$;\nPRINT STRDESC_2803$;')
        self.assertEqual(result['symbols'], {})
        self.assertNotIn('"', texts(result))

    def test_latest_load_replaces_previous_fac(self):
        result = program(load(0x2800), load(0x2803), row('PRINT_STRING'))
        self.assertEqual(texts(result), 'PRINT STRDESC_2803$;')
        self.assertEqual([r['address'] for g in result['groups'] for r in g['instructions']],
                         [0x1000, 0x1001, 0x1002])

    def test_numeric_absolute_element_behavior_is_unchanged(self):
        result = program(row('LOAD_ELEMENT_AT', value=0x2800),
                         row('STORE_FAC_VAR', variable=0x2810))
        self.assertEqual(texts(result), 'V_2810 = MEM_2800')
        self.assertIn('Compiler-resolved element address; original subscript not recovered.',
                      result['groups'][0]['warnings'])

    def test_unknown_effect_discards_descriptor_fact(self):
        result = program(load(), row('UNMODELED_EFFECT'), row('PRINT_STRING'))
        self.assertIn('UNMODELED_EFFECT semantics not yet modeled', texts(result))
        self.assertNotIn('PRINT STRDESC_', texts(result))
        self.assertIn('<?>', result['groups'][-1]['text'])

    def test_join_discards_descriptor_fact(self):
        result = program(load(), row('PRINT_STRING'), row('GOTO', target=0x1001))
        self.assertNotIn('PRINT STRDESC_', texts(result))
        self.assertIn('<?>', texts(result))

    def test_region_boundary_discards_descriptor_fact(self):
        result = program(load(), {**row('PRINT_STRING'), 'region': 'other'})
        self.assertNotIn('PRINT STRDESC_', texts(result))
        self.assertIn('<?>', result['groups'][-1]['text'])

    def test_call_discards_descriptor_fact(self):
        result = program(load(), row('GOSUB', target=0x1800), row('PRINT_STRING'))
        self.assertNotIn('PRINT STRDESC_', texts(result))
        self.assertIn('<?>', result['groups'][-1]['text'])

    def test_public_decoder_still_refuses_f2(self):
        directory = Path(__file__).resolve().parents[1] / 'petspeed'
        spec = importlib.util.spec_from_file_location('petspeed_f2_refusal', directory / 'petspeed.py')
        decoder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(decoder)
        profile = json.loads((directory / 'petspeed_profile.json').read_text())
        self.assertEqual(decoder.decode_one(b'\xd3', 0x281B, 0x281B, 0x281C, profile)['mnemonic'], 'END')
        for code in (b'\xf2', b'\xf2\x00\x28\xd0'):
            with self.subTest(code=code), self.assertRaisesRegex(
                    decoder.DecodeError, r'^unknown operand length for opcode \$F2 at \$281B$'):
                decoder.decode_one(code, 0x281B, 0x281B, 0x281B + len(code), profile)

    def test_ef_and_chr_remain_unresolved(self):
        for mnemonic in ('LOAD_ARG_TRIPLE_AT_PRESERVE_TAG', 'CHR_STRING'):
            with self.subTest(mnemonic=mnemonic):
                result = program(load(), row(mnemonic, value=0x2803), row('PRINT_STRING'))
                self.assertIn(mnemonic + ' semantics not yet modeled', texts(result))
                self.assertNotIn('PRINT STRDESC_', texts(result))

    def test_rule_does_not_leak_to_other_families(self):
        for family in ('blitz', 'austrospeed', 'basic64', 'dtl', 'speedcompiler'):
            with self.subTest(family=family):
                result = program(load(), family=family)
                expected = ('REM UNRESOLVED trailing expression' if family == 'dtl'
                            else 'REM UNRESOLVED: LOAD_STRING_ELEMENT_AT known encoding; semantic contract not yet modeled'
                            if family == 'speedcompiler'
                            else 'REM UNRESOLVED: LOAD_STRING_ELEMENT_AT semantics not yet modeled')
                self.assertEqual(texts(result), expected)
                self.assertNotIn('STRDESC_', texts(result))


if __name__ == '__main__':
    unittest.main()
