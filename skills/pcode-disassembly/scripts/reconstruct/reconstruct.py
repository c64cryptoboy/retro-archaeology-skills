#!/usr/bin/env python3
"""Binary-only best-effort BASIC above p-code, for six evidenced VM families.

Deliberately accepts no source, map, names file or annotated-disassembly input.
"""
import argparse
import json
from pathlib import Path
from formats import decode, sha, HERE
from identify import identify
from symbolic import lift, render
from reading_projection import render_reading


def reconstruct(data,raw_base=None):
    identity=identify(data,raw_base=raw_base)
    if identity['status']!='identified':raise ValueError('cannot reconstruct: compiler family '+identity['status'])
    family=identity['family']
    object_matches=[m for m in identity['matches'] if m['role']=='compiled-object' and m['layoutValid']]
    if not object_matches:
        raise ValueError('identified library or unsupported object layout; not a decodable compiled object')
    decoder_families={m.get('decoderFamily',family) for m in object_matches}
    if len(decoder_families)!=1:raise ValueError('ambiguous decoder contract for identified object')
    decoder_family=next(iter(decoder_families))
    prg=data if raw_base is None else raw_base.to_bytes(2,'little')+data
    decoded=decode(prg,decoder_family)
    result=lift(decoder_family,decoded)
    result['family']=family
    result.update(inputSha256=sha(data),identification=identity,contractsSha256=sha((HERE/'semantics.json').read_bytes()),
                  loadedRegions=decoded['loadedRegions'],selectedProfile=decoded['selectedProfile'],selectedProfileSha256=decoded['selectedProfileSha256'])
    if family=='dtl':result['limitations'].append('External RTL-64 is not in this object; semantic interpretation assumes the evidenced runtime associated with this bootstrap.')
    if family=='austrospeed' and decoder_family=='austrospeed':result['limitations'].append('Separately pinned Austro runtime: multiplication uses an explicit VM operation; CLR/file-I/O/input/error paths differ from BLITZ. Missing array indices remain unknown, never repaired from presumed source syntax.')
    if family!=decoder_family:result['limitations'].append('Compiler identity and decoder contract differ: this exact runtime revision uses the evidenced '+decoder_family+' VM contract; the family label is retained separately.')
    # Every decoded instruction is retained exactly once, including unsupported semantics.
    retained=[r['address'] for g in result['groups'] for r in g['instructions']]
    assert retained==[r['address'] for r in decoded['instructions']]
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('binary',type=Path)
    p.add_argument('--raw-base',type=lambda x:int(x,0));p.add_argument('--json-output',type=Path);p.add_argument('--text-output',type=Path)
    p.add_argument('--basic-output',type=Path,help='Optional evidenced compact reading view (currently DTL only); exclusive-create output')
    a=p.parse_args()
    try:
        result=reconstruct(a.binary.read_bytes(),a.raw_base)
        outputs=[(a.json_output,json.dumps(result,indent=2)+'\n'),(a.text_output,render(result))]
        if a.basic_output is not None:outputs.append((a.basic_output,render_reading(result)))
        for path,text in outputs:
            if path is not None:
                with path.open('x') as f:f.write(text)
        if a.text_output is None:print(render(result),end='')
    except (ValueError,OSError,KeyError,IndexError) as exc:p.exit(2,'Reconstruction refused: '+str(exc)+'\n')


if __name__=='__main__':main()
