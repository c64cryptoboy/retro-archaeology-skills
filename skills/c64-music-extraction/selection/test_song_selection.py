import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from song_selection import select_song


# Original header-only fixture: 256 songs, default 2, bits 1 and 31 set.
# There are no tune bytes, addresses, or working player in this fixture.
def header(version=2, flags=0):
    size = 118 if version == 1 else 124
    prefix = b'PSID' + version.to_bytes(2, 'big') + bytes([0, size])
    fields = bytes.fromhex('00 00 00 00 00 00   01 00   00 02   80 00 00 02')
    common = (prefix + fields).ljust(118, b'\0')
    return common if version == 1 else common + flags.to_bytes(2, 'big') + bytes(4)


class SongTests(unittest.TestCase):
    def test_high_song_rule_and_accumulator(self):
        cases = [(1, 0, 0)]
        for version in (2, 3, 4):
            cases.extend([(version, 0x0115, 31), (version, 0x0117, 0)])
        for version, flags, index33 in cases:
            with self.subTest(version=version, flags=flags):
                h = header(version, flags)
                source = io.BytesIO(h + b'unread')
                r = select_song(source, 33)
                self.assertEqual(source.tell(), len(h))
                self.assertEqual((r['version'], r['songs']), (version, 256))
                self.assertEqual(r['default'], dict(song=2, init_a=1, speed_bit_index=1,
                                                     speed_bit=1, initial_source='CIA1 Timer A'))
                # A universal wrap would give bit 0 (VBI) for ordinary v2NG.
                bit, label = (1, 'CIA1 Timer A') if index33 == 31 else (0, 'VBI')
                self.assertEqual(r['selected'], dict(song=33, init_a=32, speed_bit_index=index33,
                                                      speed_bit=bit, initial_source=label))
                for song, a in [(32, 31), (256, 255)]:
                    self.assertEqual(select_song(io.BytesIO(h), song)['selected'],
                                     dict(song=song, init_a=a, speed_bit_index=31,
                                          speed_bit=1, initial_source='CIA1 Timer A'))

    def test_first_song(self):
        self.assertEqual(select_song(io.BytesIO(header()), 1)['selected'],
                         dict(song=1, init_a=0, speed_bit_index=0, speed_bit=0, initial_source='VBI'))

    def test_invalid_headers(self):
        h = header()
        invalid = [(b'RSID' + h[4:], 'RSID'), (b'JUNK' + h[4:], 'magic'),
                   (header(5), 'unsupported PSID version 5'), (header(0), 'unsupported PSID version 0'),
                   (h[:6] + b'\x00\x76' + h[8:], 'offset'), (h[:7], 'truncated'),
                   (header(1)[:-1], 'truncated'), (h[:-1], 'truncated')]
        for offset, value, error in [(14, 0, 'count'), (14, 257, 'count'),
                                     (16, 0, 'default'), (16, 257, 'default')]:
            invalid.append((h[:offset] + value.to_bytes(2, 'big') + h[offset+2:], error))
        for data, error in invalid:
            with self.subTest(error=error), self.assertRaisesRegex(ValueError, error):
                select_song(io.BytesIO(data), 1)

    def test_invalid_request(self):
        for song in (0, -1, 257, True, 1.5):
            with self.subTest(song=song), self.assertRaisesRegex(ValueError, 'requested song'):
                select_song(io.BytesIO(header()), song)
        two_songs = header()[:14] + b'\x00\x02' + header()[16:]
        with self.assertRaisesRegex(ValueError, 'requested song'):
            select_song(io.BytesIO(two_songs), 3)

    def test_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'header.bin'
            path.write_bytes(header())  # header only, not a SID file
            cmd = [sys.executable, '-B', str(Path(__file__).with_name('song_selection.py')), str(path)]
            default = json.loads(subprocess.check_output(cmd))
            self.assertEqual(default['default'], default['selected'])
            self.assertEqual(default['selected']['song'], 2)
            result = json.loads(subprocess.check_output(cmd + ['--song', '33']))
            self.assertEqual((result['default']['song'], result['selected']['speed_bit_index']), (2, 31))
            bad = subprocess.run(cmd + ['--song', '0'], capture_output=True)
            self.assertEqual(bad.returncode, 2)
            self.assertIn(b'requested song', bad.stderr)
            self.assertEqual(bad.stdout, b'')
            self.assertEqual(path.read_bytes(), header())


if __name__ == '__main__':
    unittest.main()
