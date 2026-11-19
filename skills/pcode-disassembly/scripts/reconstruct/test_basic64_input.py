"""Synthetic decoded corridors, never executed."""
import unittest

from test_basic64_addresses import groups


class DataStringFieldTests(unittest.TestCase):
    def test_persistent_selector_not_an_original_statement_boundary(self):
        gs = groups('7b 7f a7 10 80 ab fe 80 ab fe 73')
        self.assertEqual([g['text'] for g in gs[3:5]], ['READ V_03FE', 'READ V_03FE'])
        self.assertEqual([g['evidenceAddresses'] for g in gs[3:5]], [[0, 4, 5], [0, 7, 8]])
        self.assertEqual([[r['address'] for r in g['instructions']] for g in gs[3:5]], [[4, 5], [7, 8]])
        self.assertEqual(gs[0]['text'], 'REM select DATA cursor')
        self.assertIn('grouping is not known', gs[3]['warnings'][0])

    def test_absolute_store_must_not_clobber_mode_or_cursors(self):
        from basic64_input import fold_data_string_fields
        layout = dict(loadedEnd=0x3000, stringTop=0x9000, memoryTop=0xFFFA)
        for dest, fold in [('11 00', False), ('3e 00', False), ('fc ff', False), ('fa 9f', True)]:
            with self.subTest(dest=dest):
                gs = groups('7b 7e 28 ' + dest + ' 80 ab 3f 73')  # no binary layout in fragment
                self.assertNotIn('READ V_033F', [g['text'] for g in gs])
                result = fold_data_string_fields(gs, set(), layout)
                self.assertEqual(any(g['text'] == 'READ V_033F' for g in result), fold)
                # Also require contiguous rows in the same region.
                if fold:
                    for key, value in [('region', 'other'), ('address', 0x7777)]:
                        row = gs[3]['instructions'][0]
                        changed = gs[:3] + [{**gs[3], 'instructions': [{**row, key: value}]}] + gs[4:]
                        self.assertFalse(any(g['text'] == 'READ V_033F' for g in fold_data_string_fields(changed, set(), layout)))

    def test_mode_kills_and_wrong_consumers(self):
        for code in ('80 ab ff', '7b 7d 80 ab ff', '7b 7c 00 08 00 80 ab ff 73',
                     '7b 96 80 ab ff', '7b 92 80 ab ff', '7b 88 07 00 80 ab ff 73',
                     '7b 7a ab ff', '7b 80 aa ff', '7b 80 3e 10', '7b 7f ab ff',
                     '7b 80 84 ab ff', '7b 80'):
            with self.subTest(code=code):
                self.assertFalse(any(g['text'].startswith('READ V_') for g in groups(code)))
        gs = groups('7b 7d 80 ab ff 7b 80 ab fe')
        self.assertEqual([g['text'] for g in gs if g['text'].startswith('READ V_')], ['READ V_03FE'])

    def test_entry_anywhere_after_selector_invalidates_proof(self):
        corridor = ' 7b 7f a7 10 80 ab fe 80 ab fd 73'
        for op in ('8a', '9f'):  # A normal branch or a runtime error entry.
            for target in (4, 5, 7, 8):  # Either intervening numeric row, or either string row.
                with self.subTest(op=op, target=target):
                    gs = groups(f'{op} {target:02x} 00' + corridor)
                    self.assertFalse(any(g['text'].startswith('READ V_') for g in gs))
            gs = groups(f'{op} 03 00' + corridor)  # selector executes even on alternate entry
            self.assertEqual([g['text'] for g in gs if g['text'].startswith('READ V_')], ['READ V_03FE', 'READ V_03FD'])
            gs = groups(f'{op} 0b 00' + corridor)  # interior of the second pair only
            self.assertEqual([g['text'] for g in gs if g['text'].startswith('READ V_')], ['READ V_03FE'])


class ScalarInputTests(unittest.TestCase):
    def test_exact_field_and_unsigned_destination(self):
        cases = [
            ('7c 00 08 00 7e 28 01 fe 73', 'INPUT V_FE01', 'floating-point'),
            ('7c 02 4e 3f 09 00 7f a7 ff 73', 'INPUT "N?";V_03FF', 'signed integer'),
            ('7c 00 07 00 80 ab 80 73', 'INPUT V_0380', 'string descriptor'),
        ]
        for code, text, field_type in cases:
            with self.subTest(code=code):
                g, after = groups(code)
                self.assertEqual((g['text'], g['kind']), (text, 'inferred'))
                self.assertIn(field_type, g['warnings'][0])
                self.assertEqual(g['evidenceAddresses'], [r['address'] for r in g['instructions']])
                self.assertEqual(after['instructions'][0]['address'], g['instructions'][0]['operands']['target'])

    def test_skip_modes_and_effect_boundaries(self):
        for code in (
            '7c 00 07 00 7f a7 ff',             # successor not decoded
            '7c 00 05 00 7f a7 ff 73',          # skip lands on store
            '7c 00 0a 00 7f a7 ff 80 ab 80 73', # second field is included
            '7c 00 08 00 7f 84 a7 ff 73',       # intervening output effect
            '7c 00 07 00 7f ab ff 73',          # wrong store class
            '7c 00 07 00 7f 3b 01 73',          # array destination
            '7c 01 93 08 00 80 ab ff 73',       # nonliteral display spelling
            '7c 01 22 08 00 80 ab ff 73',       # embedded quote
            '7b 7f a7 ff 73', '7d 80 ab ff 73',  # DATA or selected logical file
            '7c 00 07 00 7a ab ff 73',          # GET is not a parsed field
        ):
            with self.subTest(code=code):
                self.assertFalse(any(g['text'].startswith('INPUT ') for g in groups(code)))

    def test_prompted_string_list_keeps_order_and_descriptor_stores(self):
        # The second field can overwrite the same destination; never deduplicate it.
        g, after = groups('7c 01 51 0e 00 80 ab 80 80 ab 80 80 ab 22 73')
        self.assertEqual((g['kind'], g['text']), ('inferred', 'INPUT "Q";V_0380, V_0380, V_0322'))
        self.assertEqual(g['evidenceAddresses'], [0, 5, 6, 8, 9, 11, 12])
        self.assertEqual(after['instructions'][0]['address'], 14)
        self.assertIn('descriptors in order', g['warnings'][0])

    def test_string_list_refuses_foreign_modes_stores_and_entries(self):
        for code in (
            '7c 00 0a 00 80 ab 10 80 3e 11 73',  # string array store
            '7c 00 0a 00 80 ab 10 80 aa 11 73',  # copy preparation, not descriptor reference
            '7c 00 0a 00 80 ab 10 7a ab 11 73',  # GET, not a parsed field
            '7c 00 0a 00 80 ab 10 7f a7 11 73',  # mixed representation
            '7c 00 09 00 80 ab 10 80 ab 11 73',  # skip inside last operand
            '7c 00 0a 00 80 ab 10 80 ab 11',     # no decoded successor
            '7d 80 ab 10 80 ab 11 73',            # logical file input
            '7b 80 ab 10 80 ab 11 73',            # DATA fields
            '80 ab 10 80 ab 11 73',               # ambient fields alone do not prove INPUT
        ):
            with self.subTest(code=code):
                self.assertFalse(any(g['text'].startswith('INPUT ') for g in groups(code)))
        # Even an installed error entry into the *second* pair prevents folding.
        for entry in ('8a 0a 00', '9f 0b 00'):
            with self.subTest(entry=entry):
                gs = groups(entry + ' 7c 00 0d 00 80 ab 10 80 ab 11 73')
                self.assertFalse(any(g['text'].startswith('INPUT ') for g in gs))

    def test_foreign_entries(self):
        corridor = ' 7c 00 0a 00 7f a7 ff 73'
        for entry in ('8a 07 00', '9f 08 00'):
            with self.subTest(entry=entry):
                self.assertFalse(any(g['text'].startswith('INPUT ') for g in groups(entry + corridor)))
        self.assertEqual(groups('8a 03 00' + corridor)[1]['text'], 'INPUT V_03FF')
