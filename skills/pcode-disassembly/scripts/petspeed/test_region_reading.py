"""Projection tests use invented p-code and the interval tests' synthetic VM fixture."""
import unittest

from petspeed_region import disassemble_region
from region_reading import reading_groups, render, string_literal
from test_petspeed_region import START, fixture, synthetic_runtime


def projected(hex_code):
    code = bytes.fromhex(hex_code)
    with synthetic_runtime():
        region = disassemble_region(fixture(code), START, START + len(code))
    groups = reading_groups(region)
    assert [r for g in groups for r in g['instructions']] == region['instructions']
    assert b''.join(bytes.fromhex(r['bytes']) for g in groups for r in g['instructions']) == code
    return [g['text'] for g in groups], render(region)


class RegionReadingTests(unittest.TestCase):
    def test_io_fields_require_restore_and_matching_scalar_store(self):
        lines, _ = projected('52 03 e6 b3 d6 61 e9 52 07 e6 dc 62 e9')
        self.assertEqual(lines, ['INPUT#3, V_2808', 'GET#7, V_2810$'])
        for code in ('52 00 e6 dc 62 e9', '52 07 e6 dc 62', '52 07 e6 dc 41 e9'):
            self.assertFalse(any('GET#' in s for s in projected(code)[0]))

    def test_print_selected_peek_byte(self):
        for load, alias in [('21', 'V_2808'), ('fd 03', 'V_2915')]:
            with self.subTest(load=load):
                lines, listing = projected(f'52 03 e5 {load} c2 c7 d0 e9 d8')
                self.assertEqual(lines, [f'PRINT#3, CHR$(PEEK({alias}));', 'RETURN'])
                self.assertIn('restore on success', listing)

    def test_print_selected_peek_requires_exact_order_restore_and_entry(self):
        for code in ('52 03 e6 21 c2 c7 d0 e9', '52 03 e5 21 c7 c2 d0 e9',
                     '52 03 e5 21 c2 c7 d0', '52 00 e5 21 c2 c7 d0 e9',
                     '52 03 e5 21 c2 c7 d0 e9 d1 05 30'):
            with self.subTest(code=code):
                lines, _ = projected(code)
                self.assertFalse(any(s.startswith('PRINT#') for s in lines))
                self.assertIn('REM VM CHR_STRING', lines)

    def test_two_gets_share_selection_not_destination(self):
        lines, listing = projected('52 06 e6 dc 61 dc ff 03 e9 d8')
        self.assertEqual(lines, ['GET#6, V_2808$, V_2915$', 'RETURN'])
        self.assertIn('first GET and store precede second GET and store', listing)
        self.assertEqual(projected('52 02 e6 dc 61 dc 61 e9')[0],
                         ['GET#2, V_2808$, V_2808$'])

    def test_paired_get_requires_complete_sequence_and_single_entry(self):
        for code in ('52 00 e6 dc 61 dc 62 e9', '52 06 e6 dc 61 dc 62',
                     '52 06 e6 dc 61 d6 62 e9', '52 06 e6 dc 61 dc 62 e9 d1 05 30',
                     '52 06 e6 dc 61 dc 62 e9 d1 07 30'):
            with self.subTest(code=code):
                self.assertFalse(any(s.startswith('GET#') and s.count(',') == 2
                                     for s in projected(code)[0]))

    def test_loop_captures_limit_and_leaves_next_unpaired(self):
        self.assertEqual(projected('20 cb 9e cd 08 28 d5 d8')[0],
                         ['FOR V_2808 = 0 TO V_2800', 'NEXT', 'RETURN'])
        self.assertNotIn('FOR V_', projected('20 cb 9e cd 00 28')[1])

    def test_conditional_jump_requires_exact_guard_extent(self):
        self.assertEqual(projected('21 02 9d d4 04 d1 09 30 d5 d8')[0][0],
                         'IF V_2810$ = V_2808$ THEN GOTO L_3009')
        self.assertEqual(projected('21 02 9d d4 05 d1 09 30 d5 d8')[0][:2],
                         ['IF V_2810$ <> V_2808$ THEN GOTO L_3009', 'GOTO L_3009'])

    def test_conditional_assignment_is_a_fresh_comparison(self):
        self.assertEqual(projected('46 01 a1 00 9d d4 05 46 01 58 60 d8')[0],
                         ['IF V_2800$ = CHR$(161) THEN V_2800$ = "X"', 'RETURN'])
        self.assertIn('IF V_2800$ <> CHR$(161)', projected('46 01 a1 00 9d d4 04 46 01 58 60 d8')[1])

    def test_concatenation_is_arg_then_fac_even_for_distinct_dest(self):
        self.assertEqual(projected('23 01 91 62')[0], ['V_2810$ = V_2808$ + V_2818$'])

    def test_descriptor_store_is_conditional_on_fresh_rhs_type(self):
        lines, listing = projected('fc 00 38 21 a6 fd 03 f8')
        self.assertEqual(lines, ['REM string path: AR_3800$(V_2808) = V_2915$'])
        self.assertIn('fresh negative FAC tag', listing)
        self.assertNotIn('string path:', projected('fc 00 38 21 a0 fd 03 f8')[1])

    def test_jump_into_fold_splits_statements(self):
        lines, _ = projected('52 04 e6 dc 60 e9 d1 04 30')
        self.assertNotIn('GET#4, V_2800$', lines)
        self.assertIn('REM VM STORE_FAC_VAR', lines)
        self.assertIn('GOTO L_3004', lines)

    def test_conditional_nul_normalization_is_not_unconditional_or_eof(self):
        template = '46 00 01 9d d4 04 9e c7 61'
        good, listing = projected(template + ' d8')
        self.assertEqual(good, ['IF V_2808$ = "" THEN V_2808$ = CHR$(0)', 'RETURN'])
        self.assertIn('not an EOF test', listing)
        for code in (template.replace('d4 04', 'd4 03'), template[:-2] + '62',
                     template.replace('46 00', '46 01 41'), template + ' d1 07 30'):
            self.assertFalse(any('= CHR$(0)' in line for line in projected(code + ' d8')[0]))

    def test_word_expression_preserves_operand_roles_and_single_entry(self):
        body = '21 c6 f5 23 c6 49 00 01 83 f7 82 62'
        self.assertEqual(projected(body + ' d8')[0],
                         ['V_2810 = ASC(V_2808$) + ASC(V_2818$) * 256', 'RETURN'])
        for code in (body.replace('00 01', '01 00'), body.replace('83 f7', '82 f7'),
                     body.replace('f5', '9e'), body[:-3], body + ' d1 04 30'):
            self.assertNotIn(' + ASC(', projected(code)[1])
        self.assertEqual(projected('d2 04 30 d8 d8')[0], ['GOSUB L_3004', 'RETURN', 'RETURN'])

    def test_literal_display_preserves_empty_quote_nul_and_non_ascii(self):
        self.assertEqual(string_literal(''), '""')
        self.assertEqual(string_literal('4122005c60a0'),
                         '"A" + CHR$(34) + CHR$(0) + CHR$(92) + CHR$(96) + CHR$(160)')


if __name__ == '__main__':
    unittest.main()
