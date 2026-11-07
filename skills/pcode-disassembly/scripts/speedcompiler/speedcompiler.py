#!/usr/bin/env python3
"""Refusing decoder for the evidenced INPUT64 Speedcompiler attached VM."""
import argparse
import hashlib
import json
from pathlib import Path

PROFILE=Path(__file__).with_name('speedcompiler_profile.json')
def sha(b):return hashlib.sha256(b).hexdigest()
def default_profile():return json.loads(PROFILE.read_text())


class Decoder:
 def __init__(self,prg,profile=None,verify=True):
  self.p=profile or default_profile();self.prg=prg
  if len(prg)<3:raise ValueError('short Speedcompiler PRG')
  self.base=int.from_bytes(prg[:2],'little');self.raw=prg[2:];self.end=self.base+len(self.raw)
  if self.base!=self.p['loadAddress'] or self.end>65536:raise ValueError('unsupported Speedcompiler image extent')
  if verify and sha(self.read(self.p['runtimeStart'],self.p['runtimeEnd']-self.p['runtimeStart']))!=self.p['runtimeSha256']:
   raise ValueError('Speedcompiler runtime signature mismatch')
  self.start=self.word(self.p['entryPointer'])
  if self.start!=self.p['defaultCodeStart'] or self.read(0x1efd,1)!=b'\0':raise ValueError('unsupported relocated/extension Speedcompiler layout')
  # Native startup fetches this entry; compiler-emitted setup owns two clears
  # followed by the initial DATA cursor. Never infer a boundary from a source map.
  if self.read(self.start,1)!=b'\x78' or self.read(self.start+5,1)!=b'\x78' or self.read(self.start+10,1)!=b'\x46':
   raise ValueError('unsupported Speedcompiler initialization envelope')
  self.data=self.word(self.start+11)
  if not self.start+13<=self.data<self.end:raise ValueError('invalid Speedcompiler code/DATA boundary')
  first=self.read(self.start+1,4);second=self.read(self.start+6,4)
  self.clear_start=int.from_bytes(second[:2],'little')+second[3]
  self.clear_end=int.from_bytes(second[:2],'little')+(second[2] or 256)*256
  if first!=bytes((0,8,1,16)) or self.clear_start!=self.end or not self.end<=self.clear_end<=65536:
   raise ValueError('unsupported Speedcompiler clear/storage envelope')

 def read(self,address,size):
  if size<0 or address<self.base or address+size>self.end:raise ValueError(f'truncated Speedcompiler image at ${address:04X}')
  return self.raw[address-self.base:address-self.base+size]
 def word(self,address):return int.from_bytes(self.read(address,2),'little')
 def one(self,pc):
  opcode=self.read(pc,1)[0];spec=self.p['opcodes'].get(f'{opcode:02X}')
  if spec is None or spec['grammar']=='unknown':raise ValueError(f'unknown Speedcompiler operand grammar ${opcode:02X} at ${pc:04X}')
  g=spec['grammar'];v={};size=1
  fixed={'none':0,'u8':1,'mask':1,'word':2,'target':2,'slot_target':3,'clear':4,'write_byte':3,'float':5}
  if g in fixed:
   payload=self.read(pc+1,fixed[g]);size+=len(payload)
   if g in ('u8','mask'):v['value']=payload[0]
   if g=='mask' and not 1<=v['value']<=7:raise ValueError('unsupported comparison mask')
   if g=='word':v['value']=int.from_bytes(payload,'little')
   if g=='target':v['target']=int.from_bytes(payload,'little')
   if g=='slot_target':v.update(slot=payload[0],target=int.from_bytes(payload[1:],'little'))
   if g=='clear':
    base=int.from_bytes(payload[:2],'little');v.update(base=base,pages=payload[2] or 256,offset=payload[3],start=base+payload[3],end=base+(payload[2] or 256)*256)
   if g=='write_byte':v.update(address=int.from_bytes(payload[:2],'little'),value=payload[2])
   if g=='float':v['packedFloat']=payload.hex()
  elif g=='zstring':
   cursor=pc+1
   while cursor<min(self.data,pc+257) and self.read(cursor,1)!=b'\0':cursor+=1
   if cursor>=min(self.data,pc+257):raise ValueError('unterminated/oversized inline string')
   v['payloadHex']=self.read(pc+1,cursor-pc-1).hex();size=cursor-pc+1
  elif g=='string':
   n=self.read(pc+1,1)[0];v['payloadHex']=self.read(pc+2,n).hex();size=n+2
  elif g=='on_targets':
   count=self.read(pc+1,1)[0]
   if not 1<=count<128:raise ValueError('unsupported ON target count')
   v.update(encodedCount=count,targets=[self.word(pc+2+2*i) for i in range(count-1)]);size=2*count
  else:raise ValueError('unknown profile grammar '+g)
  if pc+size>self.data:raise ValueError('instruction crosses Speedcompiler DATA boundary')
  name=spec['mnemonic']
  if name in ('LOAD_FLOAT','STORE_FLOAT','LOAD_FLOAT_ELEMENT','STORE_FLOAT_ELEMENT','NEXT_FLOAT','LOAD_STRING','STORE_STRING','LOAD_STRING_ELEMENT','STORE_STRING_ELEMENT','LOAD_INTEGER_ELEMENT','STORE_INTEGER_ELEMENT','LOAD_CHARACTER','STORE_CHARACTER'):
   slot=v.get('slot',v.get('value'))
   if slot>=128:raise ValueError('unsupported descriptor slot')
   v['slot']=slot;v['storage']=self.read(0x1f00+slot,1)[0]|self.read(0x1f80+slot,1)[0]<<8
  if name in ('LOAD_INTEGER','STORE_INTEGER','STORE_INTEGER_RESET') or name.startswith('NEXT_INTEGER'):
   slot=v.get('slot',v.get('value'))
   if slot>=120:raise ValueError('unsupported integer slot')
   v.update(slot=slot,lowStorage=0x810+slot,highStorage=0x888+slot)
  return {'address':pc,'opcode':opcode,'bytes':self.read(pc,size).hex(' '),'size':size,'mnemonic':name,'grammar':g,'operands':v,'handler':spec['handler'],'region':'main'}

 def data_records(self):
  pc=self.data;records=[]
  while pc<self.end:
   tag=self.read(pc,1)[0]
   if tag==0:size=1;v={};name='terminator'
   elif tag==1:
    n=self.read(pc+1,1)[0];size=2+n;v={'payloadHex':self.read(pc+2,n).hex()};name='string'
   elif tag==2:size=3;v={'signedValue':int.from_bytes(self.read(pc+1,2),'little',signed=True)};name='integer'
   elif tag==3:size=6;v={'packedFloat':self.read(pc+1,5).hex()};name='float'
   else:raise ValueError(f'unknown DATA tag ${tag:02X} at ${pc:04X}')
   records.append(dict(address=pc,kind=name,size=size,bytes=self.read(pc,size).hex(' '),operands=v));pc+=size
   if tag==0:
    if pc!=self.end:raise ValueError('unmodeled Speedcompiler DATA trailer')
    return records
  raise ValueError('missing DATA terminator')

 def decode(self):
  rows=[];pc=self.start
  while pc<self.data:
   r=self.one(pc);rows.append(r);pc+=r['size']
  starts={r['address'] for r in rows}
  for r in rows:
   v=r['operands'];targets=v.get('targets',[])+([v['target']] if 'target' in v else [])
   if any(t not in starts for t in targets):raise ValueError('Speedcompiler target is not an instruction boundary')
  regions=[dict(name=n,start=a,end=b) for n,a,b in [('bootstrap/integer slots',self.base,0x900),('runtime/tables',0x900,0x196c),('runtime storage/opaque compiler residue',0x196c,0x1f00),('descriptor pointers',0x1f00,self.start),('main p-code (including initialization)',self.start,self.data),('DATA',self.data,self.end)]]
  for r in regions:r['sha256']=sha(self.read(r['start'],r['end']-r['start']))
  return {'schema':'speedcompiler-disassembly-v1','instructions':rows,'layout':{'codeStart':self.start,'codeEnd':self.data,'data':self.data,'imageEnd':self.end,'storageEnd':self.clear_end},'loadedRegions':regions,'typedDataRecords':self.data_records(),'selectedProfile':self.p['id'],'selectedProfileSha256':sha(json.dumps(self.p,sort_keys=True).encode()),'completeCodeDecode':True,'limitations':self.p['limitations']}


def inspect_image(prg,p=None):
 d=Decoder(prg,p)
 return d.base,d.raw,{'codeStart':d.start,'codeEnd':d.data,'imageEnd':d.end,'storageEnd':d.clear_end}
def disassemble(prg,p=None):return Decoder(prg,p).decode()

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('binary',type=Path);p.add_argument('--json-output',type=Path);a=p.parse_args()
 try:
  text=json.dumps(disassemble(a.binary.read_bytes()),indent=2)+'\n'
  if a.json_output:
   with a.json_output.open('x') as f:f.write(text)
  else:print(text,end='')
 except (ValueError,OSError) as e:p.exit(2,str(e)+'\n')

if __name__=='__main__':main()
