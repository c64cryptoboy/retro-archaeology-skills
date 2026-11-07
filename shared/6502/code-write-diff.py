#!/usr/bin/env python3
"""Compare two same-address PRG images and flag changed bytes in known executed/code addresses."""
import argparse
from analysis6502 import load_prg, read_json, dump

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('before'); p.add_argument('after'); p.add_argument('--cfg-json')
    p.add_argument('--executed-json', help='JSON array of executed PCs, or an object with an executedPcs array')
    args=p.parse_args(); base, old=load_prg(args.before); after_base,new=load_prg(args.after)
    if base != after_base or len(old) != len(new): p.error('images must have identical load address and length')
    watched=set()
    if args.cfg_json: watched |= {x['pc'] for x in read_json(args.cfg_json)['instructions']}
    if args.executed_json:
        raw=read_json(args.executed_json); watched |= set(raw.get('executedPcs',raw) if isinstance(raw,dict) else raw)
    changes=[]
    for i,(a,b) in enumerate(zip(old,new)):
        if a != b: changes.append({'address':base+i,'before':a,'after':b,'executedOrCode':base+i in watched})
    dump({'loadAddress':base,'changes':changes,'changedExecutedOrCode':[x for x in changes if x['executedOrCode']],
          'warning':'A diff proves mutation, not that the writer or its semantic purpose is known.'})
if __name__=='__main__': main()
