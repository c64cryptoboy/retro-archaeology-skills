"""IF target probes.  No compiler or proprietary runtime is bundled or fetched."""
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from formats import decode
from reconstruct import reconstruct
from symbolic import lift


BASE, TABLE = 0x0801, 0x1F93
# Output for the authored THEN 40 probe, starting at the mutable pointer table.
# The interpreter and the BASIC bootstrap are deliberately not part of the fixture.
TAIL = bytes.fromhex('c11f c81f c81f 9f1f a01f a11f 16 ff 15 50 a000 53 80 '
                     '52 1fb1 ec 4d495353 3e 4f ec 4c454654 3e 4f '
                     'ed 5249474854 3e 4f 4f 41000000000000')
CASES = ((40, 0x1FB1, 'LEFT'), (60, 0x1FB8, 'RIGHT'))


def fixture(target):
    image = bytearray(BASE.to_bytes(2, 'little') + bytes(TABLE - BASE) + TAIL)
    offset = 2 + 0x1FA8 - BASE
    image[offset:offset + 2] = target.to_bytes(2, 'big')
    return bytes(image)


def basic_input(line_number):
    # Tokenized INPUT, IF/THEN, PRINT, and END in a linked C64 BASIC V2 PRG.
    lines = [(10, b'\x85 A'), (20, b'\x8b A \xa7 ' + str(line_number).encode('ascii')),
             (30, b'\x99 "MISS":\x80'), (40, b'\x99 "LEFT":\x80'), (60, b'\x99 "RIGHT":\x80')]
    image = bytearray(BASE.to_bytes(2, 'little'))
    for number, body in lines:
        link = BASE + len(image) - 2 + len(body) + 5
        image += link.to_bytes(2, 'little') + number.to_bytes(2, 'little') + body + b'\0'
    return bytes(image) + b'\0\0'


class ReblitzIfTests(unittest.TestCase):
    def check_reading(self, result, target, word):
        groups = {g['evidenceAddresses'][0]: g for g in result['groups']}
        branch = groups[0x1FA6]
        self.assertEqual(branch['text'], f'IF A THEN GOTO L_{target:04X}')
        self.assertEqual(branch['instructions'][-1]['target'], target)
        self.assertEqual(groups[target]['text'], f'PRINT "{word}"')
        self.assertEqual(groups[0x1FAA]['text'], 'PRINT "MISS"')  # untaken path

    def test_paired_instruction_targets(self):
        for number, target, word in CASES:
            with self.subTest(line=number):
                self.check_reading(lift('blitz', decode(fixture(target), 'blitz')), target, word)

    def test_target_inside_string_is_not_an_instruction(self):
        with self.assertRaisesRegex(ValueError, 'not an instruction start'):
            decode(fixture(0x1FB2), 'blitz')

    @unittest.skipUnless(os.environ.get('REBLITZ64_JS'), 'optional external compiler: set REBLITZ64_JS')
    def test_source_blind_with_real_compiler(self):
        compiler = Path(os.environ['REBLITZ64_JS']).resolve(strict=True)
        self.assertEqual(hashlib.sha256(compiler.read_bytes()).hexdigest(),
                         '11773b01342bbe56d780f1b8035f889a54756a87a9b16a04a42449ff6a78433a')
        objects = []
        with tempfile.TemporaryDirectory() as directory:
            cwd = Path(directory)
            for number, target, word in CASES:
                src, obj = cwd / f'{number}.prg', cwd / f'{number}.out'
                src.write_bytes(basic_input(number))
                subprocess.run(['node', str(compiler), str(src), str(obj)], cwd=cwd,
                               check=True, capture_output=True, timeout=30)
                compiled = obj.read_bytes()
                objects.append(compiled)
                offset = 2 + TABLE - BASE
                self.assertEqual(compiled[offset:], fixture(target)[offset:])
                result = reconstruct(compiled)  # no source, pass log, filename, or selected family
                self.assertEqual(result['family'], 'blitz')
                self.check_reading(result, target, word)
        self.assertEqual(len(objects[0]), len(objects[1]))
        self.assertEqual([i for i, (a, b) in enumerate(zip(*objects)) if a != b], [2 + 0x1FA9 - BASE])
        damaged = bytearray(objects[0])
        damaged[2 + 0x081C - BASE] ^= 1
        with self.assertRaisesRegex(ValueError, 'family unknown'):
            reconstruct(bytes(damaged))
