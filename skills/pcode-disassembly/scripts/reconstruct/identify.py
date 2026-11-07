#!/usr/bin/env python3
"""Identify supported BASIC compiler families from binary evidence, not names."""
import argparse
import json
from pathlib import Path
from formats import HERE, sha, inspect


def identify(data, *, raw_base=None, identities=None):
    db=identities or json.loads((HERE/'identities.json').read_text())
    if db.get('schema')!='basic-compiler-identities-v1':raise ValueError('unsupported identity database')
    if raw_base is not None:
        if not 0<=raw_base<=65535 or raw_base+len(data)>65536:raise ValueError('invalid raw image extent')
        prg=raw_base.to_bytes(2,'little')+data
    else:prg=data
    matches=[];base=int.from_bytes(prg[:2],'little') if len(prg)>=2 else -1;raw=prg[2:]
    for pin in db['fingerprints']:
        lo,hi=pin['start']-base,pin['end']-base
        if base!=pin['loadAddress'] or lo<0 or hi>len(raw) or hi<=lo:continue
        if sha(raw[lo:hi])!=pin['sha256']:continue
        evidence={'kind':'exact-region-sha256','start':pin['start'],'end':pin['end'],'sha256':pin['sha256']}
        match={'family':pin['family'],'role':pin['role'],'confidence':'high for the matched signature',
               'evidence':[evidence],'layoutValid':None,'layoutError':None}
        if pin.get('decoderFamily'):match['decoderFamily']=pin['decoderFamily']
        if pin.get('check'):
            try:match['layout']=inspect(prg,pin['check']);match['layoutValid']=True
            except (ValueError,KeyError,IndexError) as exc:match['layoutValid']=False;match['layoutError']=str(exc)
        matches.append(match)
    families=sorted({m['family'] for m in matches})
    return {'schema':'basic-compiler-identification-v1','inputSha256':sha(data),'format':'raw' if raw_base is not None else 'prg',
            'loadAddress':base,'status':'identified' if len(families)==1 else 'ambiguous' if families else 'unknown',
            'family':families[0] if len(families)==1 else None,'matches':matches,
            'caveats':['Known signatures only; packed/encrypted, detached or unfamiliar runtimes may be unrecognized.',
                       'No match is not proof that the input was not compiled BASIC.',
                       'Matching library bytes are not proof of historical authorship, reachability, version support or full decoding.']}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('binary',type=Path)
    p.add_argument('--raw-base',type=lambda x:int(x,0),help='raw payload load address; default input is a PRG')
    p.add_argument('--json-output',type=Path)
    a=p.parse_args()
    try:
        r=identify(a.binary.read_bytes(),raw_base=a.raw_base);text=json.dumps(r,indent=2)+'\n'
        if a.json_output:
            with a.json_output.open('x') as f:f.write(text)
        print(text,end='')
    except (ValueError,OSError) as exc:p.exit(2,str(exc)+'\n')


if __name__=='__main__':main()
