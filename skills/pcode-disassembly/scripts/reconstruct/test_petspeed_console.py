"""Original decoder/lifter fragments and scalar sections; no title or runtime files."""
from importlib import import_module
import unittest

from formats import module, profile
from petspeed_console import compact_string_slots
from symbolic import lift

PS = module('petspeed')
CLASSIC = profile('petspeed')
ALT = import_module(PS.__name__ + '.variant_2267').build_profile(CLASSIC)
SLOT = bytes(6) + b'\xff\0'
END_INIT = bytes.fromhex('71 23 64 00 00')


class ConsoleFieldTests(unittest.TestCase):
    def groups(self, code, *, base=0x31fe, p=ALT, runtime=None, slots=None):
        data = bytes.fromhex(code)
        rows = []
        pc = base
        while pc < base + len(data):
            row = PS.decode_one(data, base, pc, base + len(data), p)
            rows.append(row)
            pc += row['size']
        report = dict(instructions=rows, runtimeSha256=p['runtimeSha256'] if runtime is None else runtime,
                      petspeedCompactStringSlots=compact_string_slots(SLOT * 4, END_INIT) if slots is None else slots)
        gs = lift('petspeed', report)['groups']
        self.assertEqual([r for g in gs for r in g['instructions']], rows)
        self.assertEqual(b''.join(bytes.fromhex(r['bytes']) for r in rows), data)
        return gs

    def denied(self, code, **args):
        gs = self.groups(code, **args)
        self.assertEqual(gs, self.groups(code, **dict(args, slots=[])))
        self.assertFalse(any('on default console' in g['text'] for g in gs))

    def test_fresh_field_paths_and_join_across_page(self):
        g, join = self.groups('b3 d7 63 61')
        self.assertEqual((g['kind'], g['text']), ('partial', 'REM on default console: INPUT string field -> V_2818'))
        self.assertEqual(g['evidenceAddresses'], [0x31fe, 0x31ff, 0x3200])
        self.assertEqual(g['warnings'], ['At $31FF, bare RETURN skips $3200 and keeps the current value.  '
                                         'A parsed field executes $3200; typed "" stores an empty string.  '
                                         'Both continue at $3201 on normal completion.'])
        self.assertEqual(join['text'], 'V_2808 = <?>')  # Do not forward the parsed FAC through the join.

    def test_entry_at_begin_loses_route_but_not_fresh_line(self):
        gs = self.groups('d4 01 b3 d7 60 d3')  # Both edges reach the initializer.
        self.assertEqual(gs[1]['text'], 'REM on default console: INPUT string field -> V_2800')

    def test_no_interior_entry_direct_or_table_or_nearby_empty_skip(self):
        for code in ('b3 d7 61 d1 ff 31', 'b3 d7 61 e2 04 d1 00 32',
                     'd6 ec b3 d7 61 d3'):
            with self.subTest(code=code):
                self.denied(code)

    def test_other_forms_and_continuations(self):
        for code in ('d7 63 d3', 'b3 d6 63 d3', 'b3 dc 63 d3', 'b3 d7 41 d3',
                     'b3 d7 ff 03 d3', 'b3 d7 63', 'b3 d7 63 d7 60 d3',
                     'b3 d7 63 fc 00 40 20 a6 d7 41 d3'):
            with self.subTest(code=code):
                self.denied(code)

    def test_selected_file_even_if_number_unknown(self):
        for select in ('52 07 e6', '22 e6'):
            self.denied(select + ' b3 d7 63 d3')

    def test_other_or_missing_runtime(self):
        self.denied('b3 d7 63 d3', p=CLASSIC)
        self.denied('b3 d7 63 d3', runtime=CLASSIC['runtimeSha256'])
        self.denied('b3 d7 63 d3', runtime='')

    def test_only_complete_compact_string_record_and_empty_init_list(self):
        for raw, init in [(SLOT * 3 + SLOT[:7], END_INIT), (SLOT * 4, b'\0\0\x64'),
                          (SLOT * 4, b'\0\0\0\0\0' + END_INIT),
                          (SLOT * 3 + bytes(6) + bytes([5, 255]), END_INIT),
                          (SLOT * 3 + bytes(6) + bytes([0x96, 255]), END_INIT)]:
            with self.subTest(raw=raw, init=init):
                self.denied('b3 d7 63 d3', slots=compact_string_slots(raw, init))
        self.assertEqual(compact_string_slots(bytes(256) + SLOT, END_INIT), [])


if __name__ == '__main__':
    unittest.main()
