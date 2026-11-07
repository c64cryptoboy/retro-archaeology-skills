#!/usr/bin/env python3
"""Boundedly execute common official-6502 decoder loops from a PRG.

This is intentionally a decoder-loop simulator, not a cycle-perfect C64 emulator. It supports
loads/stores, EOR/ADC/SBC, index changes, comparisons, branches, JMP, and flag setup; unsupported
opcodes stop without modifying further memory.  Supply --set ADDRESS=BYTE for required initial RAM.
Instruction fetches require supplied bytes and executable admission (the PRG load range by default).
Repeated --exec-range START:END options replace that default; END is exclusive.  Data reads retain
the existing flat-RAM model, so callers must still supply all material initial state.
"""
import argparse
from analysis6502 import load_prg, decode, operand_word, number, dump
from dis6502 import ops

def executable_range(value):
 try:
  start,end=map(number,value.split(':'))
  if 0<=start<end<=65536: return start,end
 except ValueError: pass
 raise argparse.ArgumentTypeError('invalid executable range; use START:END with 0 <= START < END <= 65536')

def main():
 p=argparse.ArgumentParser(description=__doc__); p.add_argument('prg'); p.add_argument('--start',type=number)
 p.add_argument('--a',type=number,default=0); p.add_argument('--x',type=number,default=0); p.add_argument('--y',type=number,default=0); p.add_argument('--carry',type=int,choices=(0,1),default=0); p.add_argument('--set',action='append',default=[]); p.add_argument('--max-instructions',type=int,default=10000); p.add_argument('--trace-limit',type=int,default=200); p.add_argument('--output-prg',help='write the final simulated bytes over the original PRG load range')
 p.add_argument('--exec-range',action='append',type=executable_range,default=[],metavar='START:END',help='repeatable half-open executable ranges; replaces the PRG load-range default, but does not supply bytes')
 a=p.parse_args(); base,prg=load_prg(a.prg)
 if base+len(prg)>65536: p.error('PRG load range exceeds 16-bit address space')
 mem=bytearray(65536); mem[base:base+len(prg)]=prg
 known=bytearray(65536); known[base:base+len(prg)]=b'\x01'*len(prg)
 ranges=a.exec_range or [(base,base+len(prg))]
 for spec in a.set:
  address,value=spec.split('=',1); address=number(address)&0xffff
  mem[address]=number(value)&255; known[address]=1
 # Admission tracks supplied bytes, not dataflow taint.  Stores change mem but
 # never promote an unsupplied byte into instruction-fetch evidence.
 before=mem[:]
 A,X,Y,C=a.a&255,a.x&255,a.y&255,a.carry; Z=N=0; pc=a.start if a.start is not None else base; trace=[]; reason='instruction_limit'
 instructions=0; fetch_stop=None; source=None
 def fetch_problem(address):
  if not 0<=address<65536: return 'instruction_fetch_outside_memory'
  if not any(start<=address<end for start,end in ranges): return 'outside_executable_ranges'
  if not known[address]: return 'unknown_instruction_byte'
  return None
 def flags(v):
  nonlocal Z,N; Z=int((v&255)==0); N=int(bool(v&128)); return v&255
 def ea(ins):
  m=ins['mode']; b=ins['bytes'][1] if len(ins['bytes'])>1 else 0; w=operand_word(ins) if len(ins['bytes'])>2 else 0
  if m in ('zp','zpx','zpy'): return (b+(X if m=='zpx' else Y if m=='zpy' else 0))&255
  if m in ('abs','abx','aby'): return (w+(X if m=='abx' else Y if m=='aby' else 0))&65535
  if m=='izy': return (mem[b]|mem[(b+1)&255]<<8)+Y & 65535
  if m=='izx':
   q=(b+X)&255; return mem[q]|mem[(q+1)&255]<<8
  return None
 for step in range(a.max_instructions):
  address=pc; problem=fetch_problem(address); length=None
  if problem is None:
   length=ops.get(mem[pc],(None,None,1))[2]
   for address in range(pc+1,pc+length):
    problem=fetch_problem(address)
    if problem is not None: break
  if problem is not None:
   supplied=0<=address<65536 and bool(known[address])
   reason=problem; fetch_stop={'pc':pc,'address':address,'byteOffset':address-pc,'instructionLength':length,'source':source,'supplied':supplied,'value':mem[address] if supplied else None}; break
  instructions+=1
  ins=decode(mem,0,pc)
  if not ins or ins.get('invalid') or ins.get('truncated'): reason='invalid_or_truncated_opcode'; break
  if len(trace)<a.trace_limit: trace.append({'pc':pc,'a':A,'x':X,'y':Y,'carry':C,'opcode':ins['opcode'],'mnemonic':ins['mnemonic']})
  m,mode=ins['mnemonic'],ins['mode']; nxt=(pc+ins['length'])&65535; address=ea(ins); value=mem[address] if address is not None else None
  source={'pc':pc,'mnemonic':m}
  if m in ('LDA','LDX','LDY'):
   v=ins['bytes'][1] if mode=='imm' else value
   if m=='LDA': A=flags(v)
   elif m=='LDX': X=flags(v)
   else: Y=flags(v)
  elif m in ('STA','STX','STY') and address is not None: mem[address]={'STA':A,'STX':X,'STY':Y}[m]
  elif m=='EOR': A=flags(A^(ins['bytes'][1] if mode=='imm' else value))
  elif m in ('ADC','SBC'):
   v=ins['bytes'][1] if mode=='imm' else value; total=A+(v if m=='ADC' else v^255)+C; C=int(total>255); A=flags(total)
  elif m in ('CMP','CPX','CPY'):
   q={'CMP':A,'CPX':X,'CPY':Y}[m]; v=ins['bytes'][1] if mode=='imm' else value; C=int(q>=v); flags((q-v)&255)
  elif m in ('INX','DEX','INY','DEY'):
   if m=='INX': X=flags(X+1)
   elif m=='DEX': X=flags(X-1)
   elif m=='INY': Y=flags(Y+1)
   else: Y=flags(Y-1)
  elif m in ('INC','DEC') and address is not None: mem[address]=flags(mem[address]+(1 if m=='INC' else -1))
  elif m=='CLC': C=0
  elif m=='SEC': C=1
  elif m=='JMP' and mode=='abs': pc=operand_word(ins); continue
  elif m in {'RTS','RTI','BRK'}: reason=m.lower(); break
  elif m in {'BPL','BMI','BCC','BCS','BNE','BEQ'}:
   take={'BPL':not N,'BMI':N,'BCC':not C,'BCS':C,'BNE':not Z,'BEQ':Z}[m]
   if take:
    off=ins['bytes'][1]; pc=(pc+2+(off-256 if off>=128 else off))&65535; continue
  elif m not in {'NOP'}: reason='unsupported_'+m; break
  pc=nxt
 changed=[{'address':i,'before':before[i],'after':mem[i]} for i in range(65536) if before[i]!=mem[i]]
 if a.output_prg:
  with open(a.output_prg,'wb') as output:
   output.write(bytes((base&255,(base>>8)&255))+mem[base:base+len(prg)])
 dump({'start':a.start if a.start is not None else base,'reason':reason,'instructionsExecuted':instructions,'registers':{'a':A,'x':X,'y':Y,'carry':C,'zero':Z,'negative':N,'pc':pc},'changes':changed,'trace':trace,'traceTruncated':instructions>a.trace_limit,'outputPrg':a.output_prg,'executableRanges':ranges,'fetchStop':fetch_stop})
if __name__=='__main__': main()
