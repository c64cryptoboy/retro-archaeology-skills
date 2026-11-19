"""Original two-slot puppet, its tiny playback routine, and an independent export recipe."""
import json
import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from animation import export_animation
from test_graphics_export import read_png

try:
    from PIL import Image
except ImportError:
    Image = None


# The synthetic original runs on ticks.  It knows neither the JSON recipe nor
# the sprite decoder: its artist's dot coordinates are the independent oracle.
class Puppet:
    def __init__(self):
        self.cue = self.remaining = 0
        self.dots = {}

    def tick(self):
        if not self.remaining:
            if self.cue in (0, 1):
                x = 1 + self.cue
                self.dots = {(x, 2): 2, (x+3, 2): 2, (x+23, 22): 2}
                if self.cue == 1:
                    for offset, color in enumerate((3, 3, 0, 0, 5, 5)):
                        self.dots[5+offset, 2] = color
                self.remaining = 2
            elif self.cue == 2:
                del self.dots[2, 2]
                self.dots[3, 2], self.dots[2, 3] = 7, 0
                self.remaining = 1
            elif self.cue == 3:  # New cue, same completed drawing.
                self.remaining = 1
            else:
                self.dots.clear()
                self.remaining = 2
            self.cue = 1 if self.cue == 4 else self.cue + 1
        self.remaining -= 1
        return bytes(self.dots.get((x, y), 255) for y in range(26) for x in range(30))


def fixture(root):
    # All source artwork is generated here. Padding is distinctive, not a 22nd row.
    (root/'body.spr').write_bytes(b'\x90' + bytes(61) + b'\x01\xa7')
    (root/'badge.spr').write_bytes(b'\x6c' + bytes(62))
    (root/'wink.idx').write_bytes(bytes([255, 7, 0, 255]))
    body = {'asset': 'body', 'at': [292, 72]}
    badge = {'asset': 'badge', 'at': [295, 72]}
    wink = {'asset': 'wink', 'at': [292, 72], 'draw': 'replace'}
    poses = [('enter', 2, 'clear', [{'asset': 'body', 'at': [291, 72]}]),
             ('look', 2, 'clear', [body, badge]), ('wink', 1, 'previous', [wink]),
             ('rest', 1, 'previous', []), ('gone', 2, 'clear', [])]
    return {'format': 'c64-animation-v1', 'size': [30, 26], 'origin': [290, 70],
            'crop': [1, 2, 26, 21], 'scale': 2,
            'clock': {'label': 'synthetic 60 ticks/s', 'hz_num': 60, 'hz_den': 1},
            'source_loop': [1, 5], 'movie_repeat': True,
            'assets': {'body': {'sprite': 'body.spr', 'own': 2},
                       'badge': {'sprite': 'badge.spr', 'multicolor': True, 'own': 0,
                                 'shared_0': 3, 'shared_1': 5},
                       'wink': {'indices': 'wink.idx', 'size': [2, 2]}},
            'frames': [dict(id=id_, hold=n, base=base, layers=layers) for id_, n, base, layers in poses]}


def movie_ticks(out):
    meta = json.loads((out/'manifest.json').read_bytes())
    return [plane for f in meta['frames'] for plane in [(out/f['indices']).read_bytes()] * f['hold']]


def expected_rgba(plane):
    # Independent swatches, registration, crop, and integer dot replication.
    swatches = {255: '00000000', 0: '000000ff', 2: '884444ff', 3: '88ccccff',
                5: '55aa55ff', 7: 'dddd77ff'}
    return b''.join(bytes.fromhex(swatches[plane[(2+y//2)*30+1+x//2]])
                    for y in range(42) for x in range(52))


class AnimationTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.spec = fixture(self.root)
        self.seq = self.root/'sequence.json'
        self.save_spec()
        self.player = Puppet()
        self.expected = [self.player.tick() for _ in range(8)]

    def save_spec(self):
        self.seq.write_text(json.dumps(self.spec), encoding='utf-8')

    def test_cli_native_runner_and_source_loop(self):
        out = self.root/'out'
        cmd = [sys.executable, '-B', str(ROOT/'animation.py'), str(self.seq), str(out)]
        subprocess.run(cmd, check=True, capture_output=True)
        self.assertEqual(movie_ticks(out), self.expected)
        self.assertEqual(self.player.tick(), self.expected[2])  # source skips the entry pose on wrap
        self.assertNotEqual(self.expected[2], self.expected[0])
        manifest = json.loads((out/'manifest.json').read_bytes())
        self.assertEqual(manifest['source_loop'], [1, 5])
        self.assertEqual(manifest['sequence_sha256'], hashlib.sha256(self.seq.read_bytes()).hexdigest())
        self.assertTrue(manifest['movie_repeat'])
        for name, src in (('body', 'body.spr'), ('badge', 'badge.spr'), ('wink', 'wink.idx')):
            src_data = (self.root / src).read_bytes()
            obj = manifest['assets'][name]
            self.assertEqual((out / obj['file']).read_bytes(), src_data)
            self.assertEqual(obj['sha256'], hashlib.sha256(src_data).hexdigest())
        frames = manifest['frames']
        self.assertEqual([f['gif_cs'] for f in frames], [3, 4, 1, 2, 3])
        self.assertEqual([f['end_tick'] for f in frames], [2, 4, 5, 6, 8])
        self.assertEqual([f['seconds'] for f in frames], [[1, 30], [1, 30], [1, 60], [1, 60], [1, 30]])
        for f, tick in zip(frames, (0, 2, 4, 5, 6)):
            self.assertEqual(f['sha256'], hashlib.sha256(self.expected[tick]).hexdigest())
            self.assertEqual(read_png(out/f['png']), (52, 42, expected_rgba(self.expected[tick])))
        self.assertNotEqual(subprocess.run(cmd, capture_output=True).returncode, 0)

    def test_wrong_reconstructions_disagree_with_running_original(self):
        # All three are syntactically valid.  Failure comes from comparing
        # actual timed drawings, not labels, dimensions, or descriptor hashes.
        for wrong in ('order', 'hold', 'drawing'):
            with self.subTest(wrong=wrong):
                self.spec = fixture(self.root)
                f = self.spec['frames']
                if wrong == 'order':
                    f[0], f[1] = f[1], f[0]
                elif wrong == 'hold':
                    f[1]['hold'], f[2]['hold'] = 1, 2
                else:
                    f[1]['layers'].reverse()  # rear slot now obscures a foreground dot
                self.save_spec()
                out = self.root / wrong
                export_animation(self.seq, out)
                actual = movie_ticks(out)
                self.assertEqual(len(actual), len(self.expected))
                self.assertNotEqual(actual, self.expected)

    def test_verified_gif_or_explicit_missing_dependency(self):
        out = self.root/'movie'
        if Image is None:
            with self.assertRaisesRegex(ValueError, 'requires Pillow'):
                export_animation(self.seq, out, gif=True)
            self.assertFalse(out.exists())
            return
        for repeat in (True, False):
            self.spec['movie_repeat'] = repeat
            self.save_spec()
            out = self.root / str(repeat)
            export_animation(self.seq, out, gif=True)
            with Image.open(out/'animation.gif') as gif:
                self.assertEqual(gif.info.get('loop'), 0 if repeat else None)
                self.assertEqual((gif.size, gif.n_frames), ((52, 42), 5))
                for i, (tick, ms) in enumerate(zip((0, 2, 4, 5, 6), (30, 40, 10, 20, 30))):
                    gif.seek(i)
                    self.assertEqual(gif.convert('RGBA').tobytes(), expected_rgba(self.expected[tick]))
                    self.assertEqual(gif.info['duration'], ms)

    def test_native_timing_not_clamped_to_gif(self):
        self.spec['clock'].update(hz_num=12000, hz_den=11)
        self.save_spec()
        m = export_animation(self.seq, self.root/'native')
        self.assertEqual(m['frames'][0]['seconds'], [11, 6000])
        self.assertEqual(m['frames'][0]['gif_cs'], 0)
        if Image is not None:
            with self.assertRaisesRegex(ValueError, 'unrepresentable GIF hold'):
                export_animation(self.seq, self.root/'movie', gif=True)


if __name__ == '__main__':
    unittest.main()
