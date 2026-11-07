#!/usr/bin/env python3
"""Report conservative string, repetition, sprite, and charset data candidates in a PRG."""
import argparse
from analysis6502 import load_prg, dump

# Normal uppercase/graphics screen-code approximation; custom character RAM is unknowable here.
def screen_char(b):
    if b == 0x20: return ' '
    if 1 <= b <= 26: return chr(64 + b)
    if 0x30 <= b <= 0x39: return chr(b)
    return None

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('prg'); p.add_argument('--min-string', type=int, default=4)
    args = p.parse_args(); base, mem = load_prg(args.prg); strings=[]; repeated=[]; graphics=[]
    i=0
    while i < len(mem):
        # ASCII/PETSCII printable byte candidates. PETSCII high-bit/reverse variants are deliberately not guessed.
        j=i
        while j < len(mem) and (32 <= mem[j] <= 126): j += 1
        if j-i >= args.min_string:
            strings.append({'address':base+i,'encoding':'ASCII-or-PETSCII-candidate',
                            'text':bytes(mem[i:j]).decode('latin-1'),'length':j-i})
        i=max(i+1,j)
    i=0
    while i < len(mem):
        j=i+1
        while j < len(mem) and mem[j] == mem[i]: j+=1
        if j-i >= 8: repeated.append({'address':base+i,'byte':mem[i],'length':j-i})
        i=j
    # 64-byte aligned blocks are only layout-sized candidates, not asserted sprites.
    for i in range(0, len(mem)-63, 64):
        block=mem[i:i+64]; density=sum(b.bit_count() for b in block)/512
        if .03 < density < .97:
            graphics.append({'address':base+i,'length':64,'kind':'64-byte sprite-layout candidate',
                             'setBitDensity':round(density,3)})
    dump({'loadAddress':base,'strings':strings,'repeatedByteRuns':repeated,
          'graphicsCandidates':graphics,
          'warning':'All results are candidates. Exclude known code and validate references/runtime use.'})
if __name__ == '__main__': main()
