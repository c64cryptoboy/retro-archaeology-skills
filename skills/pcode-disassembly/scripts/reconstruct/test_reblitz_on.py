"""Optional forward-compiler oracle for ordered ON destinations, never execution."""
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from reconstruct import reconstruct


def authored_prg(verb_token, order):
    # These are literal BASIC V2 tokens, not a tokenizer or a supplied line map.
    lines = [(10, b'\x85 X:\x8d 30:\x80'),
             (30, b'\x91 X ' + bytes([verb_token]) + b' ' + order),
             (40, b'\x8e'), (50, b'\x99 "A":\x8e'), (70, b'\x99 "BB":\x8e'),
             (90, b'\x99 "CCC":\x8e')]
    prg = bytearray(b'\x01\x08')
    for number, body in lines:
        link = 0x0801 + len(prg) - 2 + len(body) + 5
        prg += link.to_bytes(2, 'little') + number.to_bytes(2, 'little') + body + b'\0'
    return bytes(prg) + b'\0\0'


class ReblitzOnTests(unittest.TestCase):
    @unittest.skipUnless(os.environ.get('REBLITZ64_JS'), 'optional pinned Reblitz64 compiler')
    def test_transfer_kind_target_order_and_instruction_boundaries(self):
        compiler = Path(os.environ['REBLITZ64_JS']).resolve(strict=True)
        self.assertEqual(hashlib.sha256(compiler.read_bytes()).hexdigest(),
                         '11773b01342bbe56d780f1b8035f889a54756a87a9b16a04a42449ff6a78433a')
        a, b, c = 0x1FB4, 0x1FB8, 0x1FBD  # independently checked PRINT destinations
        cases = [('GOTO', 0x89, b'70,50,90', [b, a, c], 'multi_branch'),
                 ('GOSUB', 0x8D, b'70,50,90', [b, a, c], 'multi_branch_call'),
                 ('GOSUB', 0x8D, b'90,50,70', [c, a, b], 'multi_branch_call')]
        for verb, tok, order, targets, control in cases:
            with self.subTest(verb=verb, order=order), tempfile.TemporaryDirectory() as tmp:
                src, obj = Path(tmp) / 'probe.prg', Path(tmp) / 'object.prg'
                src.write_bytes(authored_prg(tok, order))
                completed = subprocess.run(['node', str(compiler), str(src), str(obj)],
                                           cwd=tmp, capture_output=True, check=True, timeout=30)
                self.assertRegex(completed.stdout, rb'ERRORS:\s*0\s*EXTENSIONS:\s*0\b')
                compiled = obj.read_bytes()
                result = reconstruct(compiled)
                self.assertEqual(result['family'], 'blitz')
                groups = {g['evidenceAddresses'][0]: g for g in result['groups']}
                group = groups[0x1FAA]
                self.assertEqual(group['text'], f'ON X {verb} ' + ', '.join(f'L_{t:04X}' for t in targets))
                row = group['instructions'][-1]
                self.assertEqual((row['control'], row['targets'], row['size']), (control, targets, 8))
                self.assertEqual(groups[row['address'] + row['size']]['text'], 'RETURN')
                self.assertEqual([groups[t]['text'] for t in (a, b, c)],
                                 ['PRINT "A"', 'PRINT "BB"', 'PRINT "CCC"'])
                # Retain a valid runtime and size, but point inside "CCC", not at its load.
                bad = bytearray(compiled)
                bad[2 + (0x1FB1 - 0x0801):2 + (0x1FB3 - 0x0801)] = (c + 1).to_bytes(2, 'big')
                with self.assertRaisesRegex(ValueError, 'not an instruction start'):
                    reconstruct(bytes(bad))
