#!/usr/bin/env python3
"""Normalize a debugger PC-sample JSONL trace into coverage and observed control-flow evidence.

Input lines must be JSON objects with at least `pc`; optional a/x/y/p/sp/cycle fields are retained.
This does not claim to capture a debugger trace itself: capture is platform-specific.
"""
import argparse, json
from collections import Counter
from pathlib import Path
from analysis6502 import dump

def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('trace_jsonl')
    p.add_argument('--entries-only', action='store_true', help='omit raw samples from output')
    args=p.parse_args(); samples=[]
    for line_no,line in enumerate(Path(args.trace_jsonl).read_text().splitlines(),1):
        if not line.strip(): continue
        item=json.loads(line)
        if not isinstance(item.get('pc'),int): p.error(f'line {line_no}: pc must be an integer')
        samples.append(item)
    edges=Counter((a['pc'],b['pc']) for a,b in zip(samples,samples[1:]))
    result={'sampleCount':len(samples),'executedPcs':sorted({x['pc'] for x in samples}),
            'pcHitCounts':dict(sorted(Counter(x['pc'] for x in samples).items())),
            'observedEdges':[{'from':a,'to':b,'count':n} for (a,b),n in sorted(edges.items())]}
    if not args.entries_only: result['samples']=samples
    dump(result)
if __name__=='__main__': main()
