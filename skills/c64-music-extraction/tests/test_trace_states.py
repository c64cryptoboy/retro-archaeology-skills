import sys
import unittest
from fractions import Fraction
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from trace_states import interpret


class Trace(unittest.TestCase):
    def test_sid_ordered_edges_and_unknown(self):
        writes=[(3,0xd400,0),(3,0xd401,64),(3,0xd404,0x21),
                (4,0xd404,0x20),(4,0xd404,0x21),(4,0xd404,0x21)]
        rows=interpret('sid',writes,clock_hz=1000000,tick_hz=Fraction(60,1),end_tick=7)['intervals']
        self.assertEqual([r['seconds'] for r in rows],['1/20','1/60','1/20'])
        self.assertIsNone(rows[0]['voices'][0]['word']); self.assertIsNone(rows[2]['volume_nibble'])
        self.assertEqual(rows[1]['voices'][0]['oscillator_hz'],976.5625)
        self.assertEqual(rows[1]['gate_edges'],[])
        self.assertEqual([(e['write_index'],e['gate']) for e in rows[2]['gate_edges']],[(0,False),(1,True)])
        self.assertEqual(rows[2]['voices'][0]['word'],0x4000)

    def test_sid_filter_is_not_an_oscillator_frequency_or_global_voice3_mute(self):
        writes = [(0,0xd415,0xfd), (1,0xd416,0x23), (1,0xd417,0xac),
                  (1,0xd418,0xdf), (2,0xd418,0x8f), (3,0xd417,0)]
        rows = interpret('sid',writes,clock_hz=985248,tick_hz=50,end_tick=4)['intervals']
        self.assertEqual(rows[0]['filter'], dict(cutoff_word=None, resonance=None,
                         inputs=None, modes=None, voice3_dry_disabled=None))
        self.assertEqual(rows[1]['filter'], dict(cutoff_word=285, resonance=10,
                         inputs=['voice3','external'], modes=['low-pass','high-pass'],
                         voice3_dry_disabled=True))
        self.assertEqual(rows[1]['volume_nibble'],15)
        self.assertEqual(rows[2]['filter']['modes'],[])
        self.assertEqual(rows[2]['filter']['inputs'],['voice3','external'])
        self.assertEqual(rows[3]['filter']['inputs'],[])
        self.assertIsNone(rows[1]['voices'][2]['oscillator_hz'])

    def test_sid_control_records_requests_without_inventing_sound(self):
        writes = [(1,0xd404,0x27), (1,0xd40b,0x88), (2,0xd412,0)]
        rows = interpret('sid',writes,clock_hz=985248,tick_hz=50,end_tick=3)['intervals']
        self.assertEqual([v['modulation_source_voice'] for v in rows[0]['voices']], [3,1,2])
        self.assertIsNone(rows[0]['voices'][0]['waveforms'])
        v1,v2,v3 = rows[-1]['voices']
        self.assertEqual((v1['waveforms'],v1['test'],v1['hard_sync'],v1['ring_mod_requested']),
                         (['sawtooth'],False,True,True))
        self.assertEqual((v2['waveforms'],v2['test']), (['noise'],True))
        self.assertEqual(v3['waveforms'],[])
        self.assertIsNone(v1['oscillator_hz'])
        self.assertEqual(rows[-1]['gate_edges'],[])

    def test_ted_special_words_and_masks(self):
        writes=[(0,0xff0e,254),(0,0xff12,0x7f),(0,0xff0f,255),(0,0xff10,255),
                (0,0xff11,0x78),(1,0xff11,0x48),(2,0xff11,0xb8),(3,0xff11,0x30)]
        rows=interpret('ted',writes,clock_hz=1638400,tick_hz=50,end_tick=4)['intervals']
        self.assertEqual([v['mode'] for v in rows[0]['voices']],['dc','tone'])
        self.assertEqual(rows[0]['voices'][1]['oscillator_hz'],100)
        self.assertEqual([v['mode'] for v in rows[1]['voices']],['disabled','noise'])
        self.assertEqual(rows[2]['voices'][0]['mode'],'digital-level')
        self.assertEqual(rows[3]['voices'][1]['mode'],'volume-zero')

    def test_rejects_outside_and_disordered(self):
        for data in ([(1,0xd400,2),(0,0xd401,3)],[(2,0xd400,0)],[(0,0xd420,4)],[(0,0xd400,256)]):
            with self.subTest(data=data),self.assertRaises(ValueError):
                interpret('sid',data,clock_hz=1000000,tick_hz=60,end_tick=2)

    def test_missing_high_byte_is_not_zero(self):
        rows=interpret('ted',[(0,0xff0f,30),(0,0xff11,0x23)],clock_hz=1773447,tick_hz=50,end_tick=1)['intervals']
        self.assertEqual(rows[0]['voices'][1]['mode'],'tone')
        self.assertIsNone(rows[0]['voices'][1]['oscillator_hz'])
