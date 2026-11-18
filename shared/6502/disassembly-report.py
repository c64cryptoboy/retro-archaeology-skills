#!/usr/bin/env python3
"""Render a Markdown evidence/worklist report from cfg6502 JSON and optional analyst notes JSON."""
import argparse
from analysis6502 import read_json
from cfg6502 import inline_jsr_summary

def main():
 p=argparse.ArgumentParser(description=__doc__); p.add_argument('cfg_json'); p.add_argument('--notes-json',help='object with facts, hypotheses, worklist arrays'); p.add_argument('--output',required=True)
 a=p.parse_args(); cfg=read_json(a.cfg_json); notes=read_json(a.notes_json) if a.notes_json else {}
 heading = 'Static control-flow evidence' if 'inlineJsr' in cfg else 'Confirmed control-flow evidence'
 lines=['# 6502 Disassembly Evidence Report','',f"- PRG range: `${cfg['loadAddress']:04X}-${cfg['endAddressExclusive']-1:04X}`",f"- Entry points: {', '.join(f'`${x:04X}`' for x in cfg['entries'])}",f"- Recursively reached instructions: {len(cfg['instructions'])}",'',f'## {heading}','']
 for edge in cfg['edges']:
  if edge['kind'] != 'analyst_supplied_continuation':
   lines.append(f"- `${edge['from']:04X}` → `${edge['to']:04X}` — {edge['kind']}{' (outside PRG)' if not edge['internal'] else ''}")
 if 'inlineJsr' in cfg:
  lines += ['', '## Analyst-supplied inline JSR', ''] + ['- ' + line for line in inline_jsr_summary(cfg['inlineJsr'])]
 lines += ['','## Absolute-memory references','']
 lines += [f"- `${x['address']:04X}`: " + ', '.join(f"`${r['from']:04X}` {r['mnemonic']} ({r['kind']})" for r in x['references']) for x in cfg['dataXrefs']] or ['- None recorded.']
 lines += ['','## Unresolved or terminated paths','']
 lines += [f"- `${x['at']:04X}` — {x['reason']}" for x in cfg['stops']] or ['- None recorded.']
 for key,title in [('facts','Analyst-confirmed facts'),('hypotheses','Hypotheses'),('worklist','Worklist')]:
  lines += ['',f'## {title}',''] + [f'- {x}' for x in notes.get(key,[])]
 if cfg.get('limitReached'): lines += ['','> Analysis instruction limit was reached; results are incomplete.']
 open(a.output,'w').write('\n'.join(lines)+'\n')
if __name__=='__main__': main()
