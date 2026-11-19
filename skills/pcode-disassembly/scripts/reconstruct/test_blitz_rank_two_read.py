"""Value reads with two live scalar axes.  The optional probe compiles but never plays."""
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from reconstruct import reconstruct
from test_blitz_file_input import groups
from test_blitz_rank_two_store import DIM


def authored_input():
    image = bytearray(b'\x01\x08')
    lines = [(10, b'\x86 TA(6,9)'), (20, b'\x85 X,Y'),
             (30, b'V\xb2TA(X,Y)'), (40, b'W\xb2TA(Y,X)'), (50, b'\x80')]
    for number, body in lines:
        link = 0x801 + len(image) - 2 + len(body) + 5
        image += link.to_bytes(2, 'little') + number.to_bytes(2, 'little') + body + b'\0'
    return bytes(image) + b'\0\0'


class RankTwoReadTests(unittest.TestCase):
    def test_zero_filled_runtime_cannot_authorize_axes(self):
        # Same p-code shape, but no executable runtime attesting the rank/pop contract.
        result = groups('blitz', DIM + '82 82 a4 09 c2')
        store = next(g for g in result if g['instructions'][-1]['mnemonic'] == 'STORE_VAR')
        self.assertFalse('U2(Q9, Q9)' in store['text'])
        self.assertIn('(Q9)', store['text'])

    @unittest.skipUnless(os.environ.get('REBLITZ64_JS'), 'optional pinned Reblitz64 compiler')
    def test_reverse_the_axes_in_authored_source(self):
        compiler = Path(os.environ['REBLITZ64_JS']).resolve(strict=True)
        self.assertEqual(hashlib.sha256(compiler.read_bytes()).hexdigest(),
                         '11773b01342bbe56d780f1b8035f889a54756a87a9b16a04a42449ff6a78433a')
        with tempfile.TemporaryDirectory() as directory:
            src, obj = (Path(directory) / name for name in ('axes.prg', 'object.prg'))
            src.write_bytes(authored_input())
            subprocess.run(['node', str(compiler), str(src), str(obj)], cwd=directory,
                           check=True, capture_output=True, timeout=30)
            result = reconstruct(obj.read_bytes())
        stores = [g['text'] for g in result['groups']
                  if g['instructions'][-1]['mnemonic'] == 'STORE_VAR']
        self.assertEqual(stores, ['V = TA(X, Y)', 'W = TA(Y, X)'])
