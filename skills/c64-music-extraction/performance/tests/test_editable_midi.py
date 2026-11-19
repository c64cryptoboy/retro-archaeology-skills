"""Reopen the physical track chunks, not an already-merged event stream."""
import struct
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
from performance_midi import write_performance_midi
from read_performance_smf import parse_smf


def read_tracks(path):
    with path.open('rb') as f:
        tag, size, kind, count, ppq = struct.unpack('>4sIHHH', f.read(14))
        if (tag, size, kind, ppq) != (b'MThd', 6, 1, 1000):
            raise ValueError('expected Type 1 at 1000 PPQ')
        tracks = []
        for _ in range(count):
            chunk = f.read(8)
            length = struct.unpack('>4sI', chunk)[1]
            # Give the independent single-track event reader this unchanged MTrk.
            header = struct.pack('>4sIHHH', tag, size, 0, 1, ppq)
            _, events = parse_smf(header + chunk + f.read(length))
            tracks.append(events)
        if f.read(1):
            raise ValueError('extra data after declared tracks')
        return tracks


class EditableMidiTests(unittest.TestCase):
    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / 'editable.mid'
        unison = [{'start_us': 100000, 'end_us': 250000, 'key': 60,
                   'curve': [{'us': 100000, 'pitch': 60}, {'us': 180000, 'pitch': 60.5}]},
                  {'start_us': 250000, 'end_us': 300000, 'key': 60,
                   'curve': [{'us': 250000, 'pitch': 60}]}]
        self.ledger = {'end_us': 500000, 'bend_range': 2, 'voices': [
            {'name': 'SID 1 voice 1', 'channel': 4, 'notes': unison},
            {'name': 'SID 2 voice 1', 'channel': 7, 'notes': unison},
            {'name': 'SID 2 voice 2', 'channel': 2, 'notes': []}],
            'noise': [{'start_us': 120000, 'end_us': 140000, 'gm_key': 42}]}

    def render(self):
        write_performance_midi(self.ledger, self.path, smf_type=1)
        return read_tracks(self.path)

    def test_physical_tracks_and_absolute_times(self):
        conductor, first, second, silent, noise = self.render()
        self.assertEqual([t[0] for t in (conductor, first, second, silent, noise)],
                         [(0, 'meta', 3, name) for name in
                          (b'Conductor', b'SID 1 voice 1', b'SID 2 voice 1',
                           b'SID 2 voice 2', b'Noise markers (optional GM surrogate)')])
        for track in (conductor, first, second, silent, noise):
            self.assertEqual(track[-1], (1000, 'meta', 47, b''))
        self.assertEqual(conductor[1:-1], [(0, 'meta', 81, bytes.fromhex('07 a1 20'))])
        for track, ch in ((first, 4), (second, 7), (silent, 2)):
            expected = [(0, 'cc', ch, cc, value) for cc, value in
                        [(101, 0), (100, 0), (6, 2), (38, 0), (101, 127), (100, 127)]]
            if ch != 2:
                expected += [(200, 'bend', ch, 8192), (200, 'on', ch, 60, 80),
                             (360, 'bend', ch, 10240), (500, 'off', ch, 60, 0),
                             (500, 'bend', ch, 8192), (500, 'on', ch, 60, 80),
                             (600, 'off', ch, 60, 0)]
            self.assertEqual(track[1:-1], expected)
        self.assertEqual(noise[1:-1], [(240, 'meta', 6, b'noise:on'), (240, 'on', 10, 42, 80),
                                       (280, 'meta', 6, b'noise:off'), (280, 'off', 10, 42, 0)])

    def test_no_noise_and_unnamed_voice(self):
        del self.ledger['noise'], self.ledger['voices'][2]['name']
        tracks = self.render()
        self.assertEqual(len(tracks), 4)
        self.assertEqual(tracks[-1][0], (0, 'meta', 3, b'Channel 2'))

    def test_type_zero_is_not_an_editable_master(self):
        write_performance_midi(self.ledger, self.path)
        with self.assertRaisesRegex(ValueError, 'expected Type 1'):
            read_tracks(self.path)

    def test_reject_shared_and_percussion_channels(self):
        for bad in (4, 10):
            with self.subTest(channel=bad), self.assertRaisesRegex(ValueError, 'own channel'):
                self.ledger['voices'][1]['channel'] = bad
                self.render()
