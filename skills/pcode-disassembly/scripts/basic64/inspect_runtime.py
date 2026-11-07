#!/usr/bin/env python3
"""Bounded CFG-backed BASIC-64 handler views; private input supplied explicitly."""
import argparse
import json
from pathlib import Path
import sys

SHARED = Path(__file__).resolve().parents[4] / 'shared/6502'
sys.path.insert(0, str(SHARED))
import cfg6502

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('image', type=Path)
p.add_argument('--op', action='append', default=[], type=lambda s:int(s,16))
p.add_argument('--entry', action='append', default=[], type=lambda s:int(s,16))
p.add_argument('--view', action='append', default=[], type=lambda s:int(s,16),
               help='display a window without introducing a new CFG root')
p.add_argument('--span', type=int, default=96)
p.add_argument('--output', type=Path)
a = p.parse_args()
b = a.image.read_bytes(); base = int.from_bytes(b[:2],'little'); raw = b[2:]
entries = [(f'entry ${x:04X}',x) for x in a.entry]
for op in a.op:
 if not 0 <= op <= 255: p.error('opcode must fit a byte')
 off = 0x824 + 2*op - base
 if off < 0 or off+2 > len(raw): p.error('dispatch entry outside image')
 entries.append((f'opcode ${op:02X}',int.from_bytes(raw[off:off+2],'little')))
# Include already established handler roots so a hand-entered address cannot
# silently reinterpret the operand of a known instruction as a new routine.
profile = json.loads(Path(__file__).with_name('basic64_profile.json').read_text())
known_roots = []
for key in profile['opcodes']:
 off = 0x824 + 2*int(key,16) - base
 if 0 <= off <= len(raw)-2:
  known_roots.append(int.from_bytes(raw[off:off+2],'little'))
known = cfg6502.analyze(raw,base,known_roots,10000)
for name,addr in entries:
 for i in known['instructions']:
  if i['pc'] < addr < i['pc']+i['length'] and addr not in {v['pc'] for v in known['instructions']}:
   p.error(f'{name} is inside established instruction at ${i["pc"]:04X}')
g = cfg6502.analyze(raw,base,known_roots+[v for _,v in entries],10000)
owned = {}
allowed_overlaps = {tuple(x['starts']) for x in profile.get('nativeOverlaps', [])}
g['approvedOverlaps'] = []
for i in g['instructions']:
 for byte in range(i['pc'],i['pc']+i['length']):
  if byte in owned and owned[byte] != i['pc']:
   pair = tuple(sorted((owned[byte], i['pc'])))
   if pair not in allowed_overlaps:
    p.error(f'conflicting native boundaries at ${byte:04X}; refuse CFG')
   if list(pair) not in g['approvedOverlaps']: g['approvedOverlaps'].append(list(pair))
  owned[byte] = i['pc']
if a.output:
 with a.output.open('x') as f: json.dump(g,f,indent=2);f.write('\n')
for name,addr in entries+[(f'view ${x:04X}',x) for x in a.view]:
 print(f'\n{name} -> ${addr:04X}')
 for i in g['instructions']:
  if addr <= i['pc'] < addr+a.span: print(f"{i['pc']:04X} {i['mnemonic']} {i.get('operand','')}")
print(f"\nWhole traversal: {len(g['instructions'])} instructions; limitReached={g['limitReached']}")
