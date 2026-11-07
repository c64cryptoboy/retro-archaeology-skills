#!/usr/bin/env python3
"""Conservative BASIC-64 v1.03 p-code decoder. Standard library only.

Source is supplied annotation, never recovered/authenticated BASIC. Native
bridge, header/descriptor/DATA regions and compiler trailer are not p-code.
"""
import argparse
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import re

PROFILE = Path(__file__).with_name('basic64_profile.json')


class DecodeError(ValueError):
    pass


def sha(b):
    return hashlib.sha256(b).hexdigest()


def inspect_image(prg, profile, verify=True):
    if profile.get('schema') != 'basic64-runtime-profile-v1':
        raise DecodeError('unsupported profile schema')
    if len(prg) < 2:
        raise DecodeError('missing PRG header')
    base = int.from_bytes(prg[:2], 'little'); raw = prg[2:]
    def read(address, size):
        off = address-base
        if off < 0 or size < 0 or off+size > len(raw):
            raise DecodeError(f'truncated/out-of-image range at ${address:04X}')
        return raw[off:off+size]
    if base != profile['loadAddress'] or base+len(raw)>65536:
        raise DecodeError('unsupported load address or image extent')
    pin = profile['runtime']
    if verify and sha(read(pin['start'],pin['end']-pin['start'])) != pin['sha256']:
        raise DecodeError('unsupported runtime fingerprint')
    h = int.from_bytes(read(profile['headerPointer'],2),'little')
    if read(h,3) != bytes.fromhex(profile['headerCall']):
        raise DecodeError('unsupported bootstrap header')
    entry, string_top, memory_top, data = [int.from_bytes(read(h+n,2),'little') for n in (3,5,7,9)]
    if not h+11 <= data <= entry < base+len(raw):
        raise DecodeError('invalid descriptor/DATA/object ordering')
    if read(entry,3) != bytes.fromhex(profile['entryCall']):
        raise DecodeError('native/mixed or unknown object entry; expected p-code bridge')
    trailer=bytes.fromhex(profile['trailerHex'])
    loaded_end=base+len(raw); code_end=loaded_end-len(trailer)
    if not trailer or raw[-len(trailer):]!=trailer:
        raise DecodeError('missing or unsupported compiler trailer')
    if entry+3>=code_end: raise DecodeError('empty/truncated main-code interval')
    return raw, base, {'header':h,'descriptorStart':h+11,'dataStart':data,
                       'objectEntry':entry,'codeStart':entry+3,'codeEnd':code_end,
                       'loadedEnd':loaded_end,'trailerHex':trailer.hex(),
                       'stringTop':string_top,'memoryTop':memory_top}


def parse_map(data):
    if len(data)<4 or data[:2]!=b'\x01\x08':
        raise DecodeError('unsupported Z-address-list PRG header')
    pos=2; records=[]
    while True:
        if pos+2>len(data): raise DecodeError('truncated Z-map terminator')
        link=int.from_bytes(data[pos:pos+2],'little')
        if not link: break
        if link!=0x4040: raise DecodeError(f'unsupported Z-map link ${link:04X}')
        if pos+4>len(data): raise DecodeError('truncated Z-map record')
        end=data.find(b'\0',pos+4)
        if end<0: raise DecodeError('unterminated Z-map body')
        body=data[pos+4:end]
        m=re.fullmatch(rb'\xb2 *([0-9]+) *',body)
        if not m: raise DecodeError('unsupported Z-map body grammar')
        records.append({'address':int.from_bytes(data[pos+2:pos+4],'little'),
                        'line':int(m[1]),'link':link})
        pos=end+1
    return {'records':records,'footerHex':data[pos:].hex(),'sha256':sha(data)}


def parse_descriptors(raw, base, layout):
    """Header-relative array records: LE base, dimension count, LE extents.

    Extents are stored in reverse source-subscript order. Element type is not
    stored here; the consuming opcode supplies its stride.
    """
    pos=layout['descriptorStart']; end=layout['dataStart']; result=[]
    while pos<end:
        if pos+3>end: raise DecodeError('truncated array descriptor header')
        off=pos-base; count=raw[off+2]; size=3+2*count
        if not count: raise DecodeError('unsupported zero dimension count')
        if pos+size>end: raise DecodeError('truncated array descriptor extents')
        extents=[int.from_bytes(raw[off+n:off+n+2],'little') for n in range(3,size,2)]
        result.append({'address':pos,'headerOffset':pos-layout['header'],
                       'base':int.from_bytes(raw[off:off+2],'little'),
                       'dimensions':count,'extentsReversed':extents,'size':size})
        pos+=size
    return result


def parse_source(text):
    result={}
    for row in text.splitlines():
        if not row.strip(): continue
        m=re.fullmatch(r'([0-9]+) +(.*)',row)
        if not m or int(m[1]) in result: raise DecodeError('invalid/duplicate source line')
        result[int(m[1])]=m[2]
    return result


def escaped(b):
    return ''.join(chr(x) if 32<=x<=126 and x not in (34,92) else f'\\x{x:02X}' for x in b)


def decode_one(raw, base, pc, end, profile):
    def take(n):
        if pc+n>end: raise DecodeError(f'truncated instruction at ${pc:04X}')
        return raw[pc-base:pc-base+n]
    op=take(1)[0]; spec=profile['opcodes'].get(f'{op:02X}')
    if spec is None: raise DecodeError(f'unknown operand length for opcode ${op:02X} at ${pc:04X}')
    kind=spec['operand']; size={'none':0,'u8':1,'u16le':2,'float5':5,'function_header':4}.get(kind)
    if kind in ('string8','basic8','prompt8_target16'):
        size=1+take(2)[1]+(2 if kind=='prompt8_target16' else 0)
    if kind=='target_table8':
        count=take(2)[1]
        if count>spec['maxCount']: raise DecodeError(f'unsupported target-table count {count} at ${pc:04X}')
        size=1+2*count
    if size is None: raise DecodeError(f'unsupported operand grammar {kind}')
    b=take(1+size); payload=b[1:]; values={}
    if kind in ('u8','u16le'):
        values['value']=int.from_bytes(payload,'little')
        if spec.get('target') and (values['value'] or not spec.get('zeroTargetDisables')): values['target']=values['value']
        if spec.get('signed'): values['signedValue']=int.from_bytes(payload,'little',signed=True)
    elif kind=='float5':
        exp=payload[0]; mant=int.from_bytes(payload[1:],'big')
        value=Fraction(0) if exp==0 else Fraction((1<<31)+(mant&0x7fffffff),1<<31)*Fraction(2)**(exp-129)*(-1 if mant&0x80000000 else 1)
        values.update(value=float(value),exact=str(value),packedHex=payload.hex())
    elif kind in ('string8','basic8'):
        values.update(length=payload[0],text=escaped(payload[1:]),payloadHex=payload[1:].hex())
    elif kind=='prompt8_target16':
        values.update(length=payload[0],text=escaped(payload[1:-2]),payloadHex=payload[1:-2].hex(),target=int.from_bytes(payload[-2:],'little'))
    elif kind=='target_table8':
        values.update(count=payload[0],targets=[int.from_bytes(payload[n:n+2],'little') for n in range(1,len(payload),2)])
        values['targetsText']=', '.join(f'${v:04X}' for v in values['targets'])
    elif kind=='function_header':
        desc=int.from_bytes(payload[:2],'little'); skip=int.from_bytes(payload[2:],'little')
        values.update(descriptor=desc,body=pc+5,skip=skip,targets=[pc+5,skip])
    comment=spec.get('comment','').format(**values)
    return {'address':pc,'opcode':op,'bytes':b.hex(' '),'size':len(b),'mnemonic':spec['mnemonic'],
            'operands':values,'control':spec.get('control','next'),'comment':comment,
            'evidence':spec.get('evidence','')}


def disassemble(prg, profile, line_map=None, source=None, verify=True):
    result={'schema':'basic64-disassembly-v2','imageSha256':sha(prg),
            'profileSha256':sha(json.dumps(profile,sort_keys=True).encode()),
            'instructions':[],'decodedBytes':0,'completeCodeDecode':False,
            'semanticCodeExtentVerified':False,'error':None,
            'limitations':['Native bootstrap and DATA contents are region annotations, not fully decoded.',
                           'Supplied source is annotation, not recovered/authenticated BASIC; decoding does not prove execution.']}
    try:
        raw,base,layout=inspect_image(prg,profile,verify); result['layout']=layout
        result['codeBytes']=layout['codeEnd']-layout['codeStart']
        result['semanticCodeExtentVerified']=True
        result['boundaryEvidence']=profile['trailerEvidence']
        result['descriptors']=parse_descriptors(raw,base,layout)
        cuts=[base,layout['header'],layout['header']+3,layout['descriptorStart'],
              layout['dataStart'],layout['objectEntry'],layout['codeStart'],layout['codeEnd'],layout['loadedEnd']]
        names=['runtime/stub/tables','native-bootstrap','configuration','array-descriptors',
               'DATA','native-pcode-bridge','main-pcode','compiler-trailer']
        result['regions']=[{'kind':name,'start':lo,'end':hi} for name,lo,hi in zip(names,cuts,cuts[1:])]
        result['lineMap']=parse_map(line_map) if line_map is not None else None
        result['source']=parse_source(source) if source is not None else {}
        if source is not None and line_map is None: raise DecodeError('source annotation requires Z-map')
        result['terminalBytesHex']=layout['trailerHex']
        pc=layout['codeStart']
        while pc<layout['codeEnd']:
            item=decode_one(raw,base,pc,layout['codeEnd'],profile)
            result['instructions'].append(item);pc+=item['size'];result['decodedBytes']=pc-layout['codeStart']
        boundaries={i['address'] for i in result['instructions']}
        descriptors={d['headerOffset']:d for d in result['descriptors']}
        for i in result['instructions']:
            spec=profile['opcodes'][f'{i["opcode"]:02X}']
            if 'arrayElementSize' in spec:
                d=descriptors.get(i['operands']['value'])
                if d is None: raise DecodeError('array operand is not a descriptor boundary')
                span=spec['arrayElementSize']
                for extent in d['extentsReversed']: span*=extent
                if not span or not layout['stringTop']<=d['base']<d['base']+span<=layout['memoryTop']:
                    raise DecodeError('array storage extent outside declared initialized RAM')
                i['operands'].update(descriptorAddress=d['address'],arrayBase=d['base'],
                                     extentsReversed=d['extentsReversed'],elementSize=spec['arrayElementSize'])
            v=i['operands']; targets=list(v.get('targets',[]))
            if 'target' in v: targets.append(v['target'])
            for t in targets:
                if t not in boundaries: raise DecodeError(f'control target ${t:04X} is not a decoded instruction boundary')
        if result['instructions'][-1]['control'] not in ('terminate','runtime-return','jump'):
            raise DecodeError('fallthrough leaves declared main-code region')
        if result['lineMap']:
            for row in result['lineMap']['records']:
                if row['address'] not in boundaries: raise DecodeError(f'Z-map anchor ${row["address"]:04X} is not an instruction boundary')
        result['completeCodeDecode']=True
    except DecodeError as e:
        result['error']=str(e)
    return result


def render(r):
    out=['; BASIC-64 supplied-source / p-code listing',
         '; Supplied BASIC is annotation, not recovered source.',
         f'; Decoded {r["decodedBytes"]}/{r.get("codeBytes",0)} main-code bytes; native bridge and compiler trailer excluded.']
    groups={}
    for row in (r.get('lineMap') or {}).get('records',[]): groups.setdefault(row['address'],[]).append(row['line'])
    for i in r['instructions']:
        for line in groups.get(i['address'],[]):
            src=r.get('source',{});body=src.get(line,src.get(str(line),'[source unavailable]'))
            out.append(f'\n; BASIC {line} {body}')
        out.append(f"${i['address']:04X}: {i['bytes']:<30} {i['mnemonic']:<25} ; {i['comment']}")
    if r['error']:out.append('; REFUSED: '+r['error'])
    out += ['; LIMITATION: '+s for s in r['limitations']]
    return '\n'.join(out)+'\n'


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('image',type=Path);p.add_argument('--profile',type=Path,default=PROFILE)
    p.add_argument('--map',type=Path);p.add_argument('--source',type=Path)
    p.add_argument('--json-output',type=Path);p.add_argument('--text-output',type=Path)
    a=p.parse_args()
    for output in (a.json_output,a.text_output):
        if output is not None and output.exists(): p.error(f'refusing to overwrite {output}')
    r=disassemble(a.image.read_bytes(),json.loads(a.profile.read_text()),
                                  a.map.read_bytes() if a.map else None,a.source.read_text() if a.source else None)
    if a.json_output:
        with a.json_output.open('x') as f:f.write(json.dumps(r,indent=2)+'\n')
    if a.text_output:
        with a.text_output.open('x') as f:f.write(render(r))
    else:print(render(r),end='')
    return 0 if r['completeCodeDecode'] else 2


if __name__=='__main__':raise SystemExit(main())
