#!/usr/bin/env python3
"""Locate static JMP (pointer) sites and nearby/direct writes to their pointer bytes in a PRG."""
import argparse
from analysis6502 import load_prg, decode, operand_word, dump

def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('prg'); args=p.parse_args()
    base,mem=load_prg(args.prg); instructions=[]
    pc=base
    # Linear scan is intentional here: it finds candidates, not confirmed code.
    while pc < base+len(mem):
        ins=decode(mem,base,pc); instructions.append(ins); pc += ins['length']
    sites=[]
    for ins in instructions:
        if ins.get('mnemonic')=='JMP' and ins.get('mode')=='ind' and not ins.get('truncated'):
            pointer=operand_word(ins); writes=[]
            for writer in instructions:
                if writer.get('mnemonic') in {'STA','STX','STY'} and writer.get('mode')=='abs' and not writer.get('truncated'):
                    dest=operand_word(writer)
                    if dest in {pointer,(pointer+1)&0xffff}: writes.append({'pc':writer['pc'],'mnemonic':writer['mnemonic'],'byte':'low' if dest==pointer else 'high'})
            sites.append({'pc':ins['pc'],'pointer':pointer,'staticPointerByteWrites':writes,
                          'status':'unresolved; inspect runtime pointer value and writers'})
    dump({'loadAddress':base,'indirectJumpSites':sites,
          'warning':'Linear scanning can decode data as instructions; confirm all listed writers with CFG/runtime evidence.'})
if __name__=='__main__': main()
