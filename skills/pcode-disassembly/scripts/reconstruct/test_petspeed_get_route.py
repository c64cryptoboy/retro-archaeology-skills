"""Portable byte probes for the two admitted GET/CHKIN/CLRCHN corridors."""
import importlib
import unittest

from formats import module, profile
from symbolic import lift

PS = module('petspeed')
CLASSIC = profile('petspeed')
ALTERNATE = importlib.import_module(PS.__name__ + '.variant_2267').build_profile(CLASSIC)


class GetRouteTests(unittest.TestCase):
    def groups(self, code, p):
        data = bytes.fromhex(code)
        base, pc, rows = 0x3000, 0x3000, []
        while pc < base + len(data):
            row = PS.decode_one(data, base, pc, base + len(data), p)
            rows.append(row)
            pc += row['size']
        groups = lift('petspeed', dict(instructions=rows, runtimeSha256=p['runtimeSha256']))['groups']
        self.assertEqual([r for g in groups for r in g['instructions']], rows)
        self.assertEqual(b''.join(bytes.fromhex(r['bytes']) for r in rows), data)
        return groups

    def test_selected_both_reads_then_explicit_cleanup(self):
        for p in (CLASSIC, ALTERNATE):
            with self.subTest(profile=p['id']):
                gs = self.groups('52 03 e6 dc 60 db 61 e9 dc 62', p)
                self.assertEqual([g['text'] for g in gs], [
                    'REM SELECT_INPUT_FILE 3', 'GET#3, T_3003$', 'V_2800 = T_3003$',
                    'GET#3, T_3005', 'V_2808 = T_3005', 'REM restore default I/O channels',
                    'GET T_3008$', 'V_2810 = T_3008$'])

    def test_selected_number_unknown_is_not_lost_route(self):
        for p in (CLASSIC, ALTERNATE):
            # Select using a variable, overwrite it, then read twice: don't reread it.
            gs = self.groups('20 e6 52 07 60 db dc', p)
            self.assertEqual([(g['kind'], g['text']) for g in gs[-2:]], [
                ('partial', 'GET#<?>, T_3005'), ('partial', 'GET#<?>, T_3006$')])

    def test_bypass_and_native_call_destroy_route_not_destinations(self):
        for p in (CLASSIC, ALTERNATE):
            for prefix in ('d4 04 52 03 e6', '52 03 e6 8a e8'):
                with self.subTest(profile=p['id'], prefix=prefix):
                    gs = self.groups(prefix + ' dc 60 db 61', p)
                    self.assertEqual([(g['kind'], g['text']) for g in gs[-4:]], [
                        ('partial', 'REM current-channel GET: T_3005$'), ('inferred', 'V_2800 = T_3005$'),
                        ('partial', 'REM current-channel GET: T_3007'), ('inferred', 'V_2808 = T_3007')])

    def test_input_field_is_not_get_and_alternate_empty_skip_is_not_assignment(self):
        for code, expected in [('d4 04 52 03 e6 d7', 'REM current-channel INPUT FIELD -> T_3005$'),
                               ('20 e6 d7', 'REM INPUT#<?> FIELD -> T_3002$')]:
            g = self.groups(code, CLASSIC)[-1]
            self.assertEqual((g['kind'], g['text']), ('partial', expected))
            alt = self.groups(code, ALTERNATE)[-1]
            self.assertEqual(alt['instructions'][-1]['mnemonic'], 'INPUT_STRING_EMPTY_SKIP')
            self.assertEqual(alt['kind'], 'unresolved')


if __name__ == '__main__':
    unittest.main()
