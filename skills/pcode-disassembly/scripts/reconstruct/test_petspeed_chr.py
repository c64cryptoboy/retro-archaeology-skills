"""Decoded-record reading checks, not native execution or image admission."""
import unittest

from symbolic import Expr, Lifter, lift, render
from formats import module, profile


def row(mnemonic, **operands):
    return {'mnemonic': mnemonic, 'bytes': '00', 'size': 1,
            'grammar': 'none', 'operands': operands}


def report(*rows):
    return {'instructions': [{'address': 0x1000 + i, **record}
                             for i, record in enumerate(rows)],
            'typedDataRecords': []}


def program(*rows):
    return lift('petspeed', report(*rows))


def texts(result):
    return '\n'.join(group['text'] for group in result['groups'])


def chr_row():
    return row('CHR_STRING')


def printing(*rows):
    return program(*rows, chr_row(), row('PRINT_STRING'))


class PETSpeedChrTests(unittest.TestCase):
    def assert_refused(self, *rows):
        result = printing(*rows)
        self.assertIn('CHR_STRING semantics not yet modeled', texts(result))
        self.assertNotIn(' = CHR$(', texts(result))
        self.assertIn('<?>', result['groups'][-1]['text'])
        return result

    def test_zero_and_one_are_effectful_not_folded_literals(self):
        for name, value in (('ZERO_FAC', '0'), ('ONE_FAC', '1')):
            with self.subTest(name=name):
                result = printing(row(name))
                self.assertEqual(texts(result),
                                 f'T_1001 = CHR$({value})\nPRINT T_1001;')
                self.assertEqual([g['kind'] for g in result['groups']],
                                 ['inferred', 'inferred'])

    def test_unsigned_byte_and_signed_word_positive_boundaries(self):
        for name in ('CONST_U8_FAC', 'CONST_I16_FAC'):
            for value in (0, 1, 65, 128, 255):
                with self.subTest(name=name, value=value):
                    self.assertEqual(texts(printing(row(name, value=value))),
                                     f'T_1001 = CHR$({value})\nPRINT T_1001;')

    def test_float_literals_keep_their_conversion_argument(self):
        for numerator, denominator, shown in ((0, 1, '0'), (1, 2, '0.5'),
                                               (511, 2, '255.5'),
                                               (1023, 4, '255.75')):
            with self.subTest(shown=shown):
                result = printing(row('CONST_FLOAT_FAC', numerator=numerator,
                                      denominator=denominator))
                self.assertEqual(texts(result),
                                 f'T_1001 = CHR$({shown})\nPRINT T_1001;')
                self.assertNotIn('CHR$(255)', texts(result))

    def test_negative_signed_words_and_upper_boundary_are_not_masked(self):
        for value in (-32768, -256, -1, 256, 32767, 65535):
            with self.subTest(value=value):
                self.assert_refused(row('CONST_I16_FAC', value=value))

    def test_negative_fraction_and_float_upper_boundary_are_refused(self):
        for numerator, denominator in ((-1, 2), (-1, 1), (256, 1), (513, 2)):
            with self.subTest(numerator=numerator, denominator=denominator):
                self.assert_refused(row('CONST_FLOAT_FAC', numerator=numerator,
                                        denominator=denominator))

    def test_missing_numeric_operand_is_not_a_literal(self):
        self.assert_refused(row('CONST_I16_FAC'))

    def test_string_inputs_are_not_numeric_even_if_they_look_numeric(self):
        for record in (row('CONST_STRING_FAC', stringHex='3635'),
                       row('LOAD_STRING_ELEMENT_AT', value=0x2800)):
            with self.subTest(record=record):
                self.assert_refused(record)

    def test_unknown_variables_and_numeric_looking_names_are_refused(self):
        self.assert_refused()
        self.assert_refused(row('LOAD_FAC_VAR', variable=0x2800))
        self.assert_refused(row('LOAD_FAC_VAR', variable=0x2800, name='65'))

    def test_derived_values_remain_outside_this_literal_rule(self):
        self.assert_refused(row('ONE_FAC'), row('ONE_ARG'), row('ADD'))
        self.assert_refused(row('ZERO_FAC'), row('NEGATE'))
        self.assert_refused(row('ONE_FAC'), row('PUSH_FAC'), row('POP_FAC'))

    def test_unknown_effect_discards_literal_fact(self):
        self.assert_refused(row('ZERO_FAC'), row('UNMODELED_EFFECT'))

    def test_join_at_chr_discards_literal_fact(self):
        result = program(row('ZERO_FAC'), chr_row(), row('PRINT_STRING'),
                         row('GOTO', target=0x1001))
        self.assertIn('CHR_STRING semantics not yet modeled', texts(result))
        self.assertNotIn(' = CHR$(', texts(result))

    def test_region_boundary_discards_literal_fact(self):
        result = program(row('ZERO_FAC'), {**chr_row(), 'region': 'other'},
                         {**row('PRINT_STRING'), 'region': 'other'})
        self.assertIn('CHR_STRING semantics not yet modeled', texts(result))
        self.assertNotIn(' = CHR$(', texts(result))

    def test_call_discards_literal_fact(self):
        self.assert_refused(row('ZERO_FAC'), row('GOSUB', target=0x1800))

    def test_descriptor_result_cannot_be_reused_as_a_numeric_literal(self):
        result = program(row('ZERO_FAC'), chr_row(), chr_row(), row('PRINT_STRING'))
        self.assertEqual(texts(result).count(' = CHR$('), 1)
        self.assertIn('T_1001 = CHR$(0)', texts(result))
        self.assertIn('CHR_STRING semantics not yet modeled', texts(result))
        self.assertIn('<?>', result['groups'][-1]['text'])

    def test_argument_and_integer_accumulator_are_killed_saved_alt_survives(self):
        source = report(row('CONST_U8_FAC', value=65), chr_row())
        lifter = Lifter('petspeed', source)
        constant, operation = source['instructions']
        lifter.current = constant
        lifter.standard(constant, lifter.rules[constant['mnemonic']])
        saved = Expr('SAVED_VALUE', {0x0900})
        lifter.regs.update(arg=Expr('STALE_ARG'), ia=Expr('STALE_INTEGER'))
        lifter.stack['alt'] = [saved]
        lifter.current = operation
        lifter.pending = [constant, operation]
        self.assertTrue(lifter.special(operation))
        self.assertNotIn('arg', lifter.regs)
        self.assertNotIn('ia', lifter.regs)
        self.assertEqual(len(lifter.stack['alt']), 1)
        self.assertIs(lifter.stack['alt'][0], saved)
        result = lifter.get('fac')
        self.assertEqual(result.text, 'T_1001')
        self.assertTrue(result.stable)
        self.assertFalse(result.reference)
        self.assertEqual(result.deps, {0x1001})
        self.assertEqual(len(lifter.groups), 1)

    def test_pop_arg_restores_the_saved_value_after_allocation(self):
        result = program(row('CONST_STRING_FAC', stringHex='41'), row('PUSH_FAC'),
                         row('ZERO_FAC'), chr_row(), row('POP_ARG'),
                         row('CONCAT'), row('PRINT_STRING'))
        self.assertEqual(texts(result),
                         'T_1003 = CHR$(0)\nPRINT ("A" + T_1003);')

    def test_unsaved_arg_is_not_reused_after_allocation(self):
        result = program(row('CONST_STRING_ARG', stringHex='41'), row('ZERO_FAC'),
                         chr_row(), row('CONCAT'), row('PRINT_STRING'))
        self.assertEqual(texts(result),
                         'T_1002 = CHR$(0)\nPRINT (<?> + T_1002);')
        self.assertEqual(result['groups'][-1]['kind'], 'partial')

    def test_repeated_allocations_and_fre_keep_producer_order(self):
        result = program(row('ZERO_FAC'), chr_row(), row('ZERO_FAC'), row('FRE'),
                         row('ZERO_FAC'), chr_row(), row('PRINT_STRING'))
        self.assertEqual(texts(result), 'T_1001 = CHR$(0)\nT_1003 = FRE(0)\n'
                                       'T_1005 = CHR$(0)\nPRINT T_1005;')
        self.assertEqual(texts(result).count(' = CHR$('), 2)

    def test_chr_is_not_deleted_when_fac_is_overwritten(self):
        result = program(row('ZERO_FAC'), chr_row(), row('ONE_FAC'),
                         row('STORE_FAC_VAR', variable=0x2800))
        self.assertEqual(texts(result), 'T_1001 = CHR$(0)\nV_2800 = 1')

    def test_instructions_and_dependencies_are_owned_exactly_once(self):
        source = report(row('CONST_U8_FAC', value=65), chr_row(), row('PRINT_STRING'))
        result = lift('petspeed', source)
        self.assertEqual([r for g in result['groups'] for r in g['instructions']],
                         source['instructions'])
        self.assertEqual(result['groups'][0]['evidenceAddresses'], [0x1000, 0x1001])
        self.assertEqual(result['groups'][1]['evidenceAddresses'], [0x1001, 0x1002])
        self.assertEqual(result['instructionCount'], 3)
        self.assertEqual(result['symbols'], {})
        output = render(result)
        for text in ('T_1001 = CHR$(65)', 'PRINT T_1001;', 'CHR_STRING',
                     'conversion/range check precedes allocation/GC',
                     'not stock BASIC equivalence', 'Synthetic temporary'):
            self.assertIn(text, output)

    def test_numeric_text_without_literal_producer_proof_is_refused(self):
        operation = {'address': 0x1001, **chr_row()}
        lifter = Lifter('petspeed', {'instructions': [operation]})
        lifter.current = operation
        lifter.regs['fac'] = Expr('65')
        self.assertFalse(lifter.special(operation))

    def test_rule_is_only_petspeed(self):
        for family in ('blitz', 'austrospeed', 'basic64', 'dtl', 'speedcompiler'):
            with self.subTest(family=family):
                source = report(row('ZERO_FAC'), chr_row())
                lifter = Lifter(family, source)
                lifter.current = source['instructions'][1]
                lifter.regs['fac'] = Expr('0', {0x1000}, producer=0x1000)
                self.assertFalse(lifter.special(lifter.current))

    def test_public_decoder_c7_admission_does_not_change(self):
        decoder, selected = module('petspeed'), profile('petspeed')
        for code in (b'\xc7', b'\xc7\xd0'):
            with self.subTest(code=code), self.assertRaisesRegex(
                    decoder.DecodeError, r'^unknown operand length for opcode \$C7 at \$281B$'):
                decoder.decode_one(code, 0x281B, 0x281B, 0x281B + len(code), selected)

    def test_signed_word_decoder_remains_signed(self):
        decoder, selected = module('petspeed'), profile('petspeed')
        record = decoder.decode_one(b'\x40\xff\xff', 0x1000, 0x1000, 0x1003, selected)
        self.assertEqual(record['operands']['value'], -1)
        self.assert_refused(record)


if __name__ == '__main__':
    unittest.main()
