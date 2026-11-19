"""Interpret ordered SID or TED register writes as timed latch states, not inferred notes."""
import argparse
import csv
import itertools
import json
from fractions import Fraction
from pathlib import Path


def _word(reg, lo, hi, mask):
    if lo not in reg or hi not in reg:
        return None
    return reg[lo] | ((reg[hi] & mask) << 8)


def _sid(reg, clock):
    voices = []
    for v in range(3):
        base = 7*v
        word = _word(reg, base, base+1, 255)
        ctl = reg.get(base+4)
        voices.append(dict(voice=v+1, word=word,
            oscillator_hz=None if word is None else float(clock*word/16777216),
            control=ctl, gate=None if ctl is None else bool(ctl & 1),
            waveforms=None if ctl is None else [name for bit, name in enumerate(
                ('triangle', 'sawtooth', 'pulse', 'noise'), 4) if ctl & (1 << bit)],
            test=None if ctl is None else bool(ctl & 8),
            hard_sync=None if ctl is None else bool(ctl & 2),
            ring_mod_requested=None if ctl is None else bool(ctl & 4),
            modulation_source_voice=(3, 1, 2)[v],
            pulse_width=_word(reg,base+2,base+3,15), attack_decay=reg.get(base+5),
            sustain_release=reg.get(base+6)))
    return voices


def _sid_filter(reg):
    lo, hi, routing, mode = (reg.get(i) for i in range(21, 25))
    return dict(cutoff_word=None if lo is None or hi is None else (hi << 3) | (lo & 7),
                resonance=None if routing is None else routing >> 4,
                inputs=None if routing is None else [name for i, name in
                    enumerate(('voice1', 'voice2', 'voice3', 'external')) if routing & (1 << i)],
                modes=None if mode is None else [name for i, name in
                    enumerate(('low-pass', 'band-pass', 'high-pass'), 4) if mode & (1 << i)],
                voice3_dry_disabled=None if mode is None else bool(mode & 128))


def _ted(reg, clock):
    ctl = reg.get(0x11)
    voices = []
    for v,(lo,hi) in enumerate(((0x0e,0x12),(0x0f,0x10)), 1):
        word = _word(reg,lo,hi,3)
        if ctl is None: mode='unknown'
        elif ctl & 0x80: mode='digital-level'
        elif not ctl & 15: mode='volume-zero'
        elif ctl & (0x10 if v == 1 else 0x20): mode='tone'
        elif v == 2 and ctl & 0x40: mode='noise'
        else: mode='disabled'
        if mode == 'tone' and word == 1022: mode='dc'
        # Supply oscillator pitch only for an enabled tone.  Noise clock is not a note.
        hz = float(clock/(16*(1024-((word+1)&1023)))) if mode=='tone' and word is not None else None
        voices.append(dict(voice=v,word=word,mode=mode,oscillator_hz=hz))
    return voices


def interpret(chip, writes, *, clock_hz, tick_hz, end_tick, base=None):
    """Return half-open intervals with ordered writes. Clock values accept Fraction or integer.

    Writes are (integer tick, absolute address, byte), in observed order.  Unwritten
    latches are unknown.  Seed an independently observed initial state at tick 0 if
    needed.  SID clock is PHI2; TED clock is the double clock.  end_tick is exclusive.
    """
    if chip not in ('sid','ted'):
        raise ValueError('chip must be sid or ted')
    clock, rate = Fraction(clock_hz), Fraction(tick_hz)
    if rate <= 0 or clock <= 0 or type(end_tick) is not int or end_tick<=0:
        raise ValueError('positive clocks and exclusive end tick required')
    if base is None: base = 0xd400 if chip=='sid' else 0xff00
    if type(base) is not int or base<0 or base+(24 if chip=='sid' else 18)>65535:
        raise ValueError('register block outside 16-bit address space')
    reg, result = {}, []
    def snapshot(tick, changes, edges):
        volume = reg.get(24 if chip=='sid' else 0x11)
        row = dict(start_tick=tick, writes=changes, gate_edges=edges,
                   volume_nibble=None if volume is None else volume&15,
                   voices=(_sid if chip=='sid' else _ted)(reg, clock))
        if chip == 'sid':
            row['filter'] = _sid_filter(reg)
        return row
    for tick, entries in itertools.groupby(writes, key=lambda w:w[0]):
        if type(tick) is not int or not 0<=tick<end_tick or result and tick<=result[-1]['start_tick']:
            raise ValueError('writes must be ordered, nonnegative, and before end_tick')
        if tick and not result: result.append(snapshot(0,[],[]))
        changes, edges = [], []
        for _,address,value in entries:
            if type(address) is not int or type(value) is not int or not 0<=value<=255:
                raise ValueError('integer address and byte value required')
            r = address-base
            if r not in (range(25) if chip=='sid' else range(0x0e,0x13)):
                raise ValueError(f'not a selected {chip} write register: ${address:04X}')
            old = reg.get(r)
            if chip=='sid' and r in (4,11,18) and old is not None and (old^value)&1:
                edges.append(dict(write_index=len(changes),voice=r//7+1,gate=bool(value&1)))
            reg[r]=value
            changes.append([address,value])
        result.append(snapshot(tick,changes,edges))
    if not result: result.append(snapshot(0,[],[]))
    for i,row in enumerate(result):
        stop=result[i+1]['start_tick'] if i+1<len(result) else end_tick
        row.update(end_tick=stop, seconds=str((stop-row['start_tick'])/rate))
    return dict(chip=chip,base=base,clock_hz=str(clock),tick_hz=str(rate),end_tick=end_tick,intervals=result)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('chip',choices=('sid','ted')); p.add_argument('trace',type=Path)
    p.add_argument('--clock-hz',required=True,type=Fraction); p.add_argument('--tick-hz',required=True,type=Fraction)
    p.add_argument('--end-tick',required=True,type=int); p.add_argument('--base',type=lambda s:int(s,0))
    args=p.parse_args()
    with args.trace.open(newline='') as f:
        writes=((int(row['tick'],0),int(row['address'],0),int(row['value'],0)) for row in csv.DictReader(f))
        result=interpret(args.chip,writes,clock_hz=args.clock_hz,tick_hz=args.tick_hz,end_tick=args.end_tick,base=args.base)
    print(json.dumps(result,indent=2))


if __name__=='__main__': main()
