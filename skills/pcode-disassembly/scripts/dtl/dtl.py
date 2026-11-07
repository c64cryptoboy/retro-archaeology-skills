#!/usr/bin/env python3
"""Refusing, profile-driven DTL object disassembly. No compiler/runtime bytes bundled.

This is a structural disassembler with supplied-source annotation, not a claim
of original source recovery or BASIC behavioral equivalence.
"""
import argparse
import hashlib
import json
from pathlib import Path


class DecodeError(ValueError):
    pass


def sha(data):
    return hashlib.sha256(data).hexdigest()


def word(data, offset, order='little'):
    if offset < 0 or offset+2 > len(data):
        raise DecodeError('truncated word')
    return int.from_bytes(data[offset:offset+2], order)


def basic_text(data, tokens):
    out, quoted, rem, in_data = [], False, False, False
    for b in data:
        if b == 34 and not rem:
            quoted = not quoted
            out.append('"')
        elif not quoted and not rem and not in_data and f'{b:02X}' in tokens:
            out.append(tokens[f'{b:02X}'])
            rem = b == 0x8f
            in_data = b == 0x83
        else:
            out.append(chr(b) if 32 <= b <= 126 else f'{{$%02X}}' % b)
            if b == 58 and not quoted and not rem:
                in_data = False
    return ''.join(out)


def source_lines(text):
    result = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        parts = line.strip().split(maxsplit=1)
        try:
            number = int(parts[0])
        except ValueError as exc:
            raise DecodeError('source requires numbered BASIC lines') from exc
        if number in result:
            raise DecodeError(f'duplicate supplied source line {number}')
        result[number] = line.strip()
    return result


class Decoder:
    def __init__(self, prg, profile):
        if profile.get('schema') != 'dtl-pcode-profile-v1':
            raise DecodeError('unsupported profile schema')
        self.profile = profile
        self.base = word(prg, 0)
        self.data = prg[2:]
        self.end = self.base + len(self.data)
        h = profile['layout']
        if self.base != h['loadAddress'] or self.end > 65536:
            raise DecodeError('unsupported load address or image extent')
        prefix = self.data[:h['bootstrapSize']]
        if sha(prefix) != h['bootstrapSha256']:
            raise DecodeError('unrecognized object bootstrap')
        self.data_start = self.base + word(self.data, h['dataOffset'])
        self.init = self.base + word(self.data, h['initOffset'])
        self.main = self.base + word(self.data, h['mainOffset'])
        if word(self.data, h['imageEndOffset']) != self.end:
            raise DecodeError('image end word does not match file size')
        if len(self.data) < h['trailerSize']:
            raise DecodeError('truncated trailer')
        tail = self.data[-h['trailerSize']:]
        self.trailer = self.end-len(tail)
        self.array = word(tail, h['arrayWord'])-tail[h['arrayBias']]
        self.variables = word(tail, h['variableWord'])-tail[h['variableBias']]
        self.key_hi, self.key_lo = tail[h['branchKeyHigh']], tail[h['branchKeyLow']]
        self.code_end = self.variables-h['paddingSize']
        if not (self.base+h['bootstrapSize'] <= self.data_start <= self.init < self.main <= self.code_end <= self.variables <= self.array <= self.trailer):
            raise DecodeError('invalid or unsupported image regions (external variable files unsupported)')
        if self.take(self.code_end, self.variables-self.code_end) != bytes(h['paddingSize']):
            raise DecodeError('unrecognized program/variable separator')
        if (self.array-self.variables) % h['scalarStride']:
            raise DecodeError('unaligned scalar table')
        self.names = {}
        self.scalars = []
        for address in range(self.variables, self.array, h['scalarStride']):
            record = self.take(address, h['scalarStride'])
            a,b = record[:2]
            name = chr(a & 127)+(chr(b & 127) if b & 127 else '')
            typ = ('integer' if a & 128 else 'string') if b & 128 else ('function' if a & 128 else 'real')
            name = ('FN ' if typ == 'function' else '')+name+{'integer':'%', 'string':'$'}.get(typ,'')
            self.names[address-self.variables+2] = name
            self.scalars.append(dict(address=address, offset=address-self.variables+2, name=name, type=typ, raw=record.hex()))

    def take(self, address, count, limit=None):
        if count < 0 or address < self.base or address+count > (self.end if limit is None else min(limit,self.end)):
            raise DecodeError(f'truncated/out-of-bounds operand at ${address:04X}')
        return self.data[address-self.base:address-self.base+count]

    def target(self, data):
        return ((data[0] ^ self.key_hi) << 8) | (data[1] ^ self.key_lo)

    def one(self, pc, end):
        opcode = self.take(pc,1,end)[0]
        spec = self.profile['opcodes'].get(f'{opcode:02X}')
        if not spec or spec.get('grammar') is None:
            raise DecodeError(f'unknown operand grammar ${opcode:02X} at ${pc:04X}')
        grammar = spec['grammar']
        row = dict(address=pc, opcode=opcode, mnemonic=spec['mnemonic'], grammar=grammar,
                   confidence=spec.get('confidence','strong'), control=spec.get('control','fallthrough'),
                   operands={}, targets=[])
        n = 1
        if grammar == 'none':
            pass
        elif grammar in ('u8','u16be','float5','xor_target','relative8','var8','var16','array8','array16'):
            count = 5 if grammar=='float5' else 2 if grammar in ('u16be','xor_target','var16','array16') else 1
            data = self.take(pc+1,count,end); n += count
            value = int.from_bytes(data,'big')
            row['operands']['raw'] = data.hex()
            if grammar == 'float5':
                row['operands']['packedFloat'] = data.hex()
            elif grammar == 'xor_target':
                row['targets'] = [self.target(data)]
            elif grammar == 'relative8':
                row['targets'] = [pc+value]
            else:
                row['operands']['value'] = value
                if spec.get('signed'):
                    row['operands']['signedValue'] = int.from_bytes(data,'big',signed=True)
                if grammar.startswith('var') and value in self.names:
                    row['operands']['name'] = self.names[value]
        elif grammar in ('counted_bytes','target_table'):
            count = self.take(pc+1,1,end)[0]
            if count > spec.get('maxCount',253):
                raise DecodeError(f'unmodeled overflowing byte count at ${pc:04X}')
            payload = self.take(pc+2,count,end); n=2+count
            row['operands']['count'] = count
            if grammar=='target_table':
                if count % 2:
                    raise DecodeError(f'odd target-table byte count at ${pc:04X}')
                row['targets']=[self.target(payload[i:i+2]) for i in range(0,count,2)]
            else:
                row['operands']['bytes'] = payload.hex()
                row['operands']['text'] = basic_text(payload,{})
        elif grammar == 'selector':
            selector = self.take(pc+1,1,end)[0]
            sub = spec['selectors'].get(f'{selector:02X}')
            if sub is None:
                raise DecodeError(f'unknown selector ${selector:02X} at ${pc:04X}')
            n=2; row['operands']={'selector':selector, 'operation':sub}
        elif grammar == 'basic_island':
            start = pc+1
            first = self.take(start,1,end)[0]
            if f'{first:02X}' not in spec['allowedStarts']:
                raise DecodeError(f'unmodeled interpreter statement ${first:02X} at ${pc:04X}')
            quoted=False; cursor=start
            while cursor <= end:
                b=self.take(cursor,1)[0]  # terminator may be first byte of retained zero padding
                if b == 0 or (b == 58 and not quoted):
                    break
                if cursor == end:
                    raise DecodeError(f'unterminated interpreter island at ${pc:04X}')
                if b == 34:
                    quoted=not quoted
                cursor+=1
            if cursor==start:
                raise DecodeError('empty interpreter island')
            n=cursor-pc
            payload=self.take(start,n-1,end)
            row['operands']={'text':basic_text(payload,self.profile['basicTokens']), 'terminator':b,
                             'terminatorAddress':cursor, 'terminatorOwned':False}
            row['control']=spec.get('statementControls',{}).get(f'{first:02X}','interpreter-fallthrough')
        elif grammar == 'fn_definition':
            fields=self.take(pc+1,7,end); n=8
            descriptor=word(fields,0,'big'); body=word(fields,2,'big')+self.main
            parameter=word(fields,4,'big'); skip=fields[6]
            if skip < n:
                raise DecodeError(f'FN skip points inside header at ${pc:04X}')
            row['operands']={'descriptorOffset':descriptor,'parameterOffset':parameter,'bodyEntry':body,'skipBytes':skip}
            row['targets']=[body,pc+skip]
        elif grammar == 'sys_basic_tail':
            cursor=pc+1; quoted=False
            first=self.take(cursor,1,end)[0]
            if first not in spec['allowedStarts']:
                raise DecodeError(f'unmodeled SYS tail start at ${pc:04X}')
            while True:
                b=self.take(cursor,1,end)[0]
                if b == spec['delimiter']:
                    if quoted:
                        raise DecodeError(f'colon inside quoted SYS tail at ${pc:04X}')
                    break
                if b == 0:
                    raise DecodeError(f'NUL before SYS delimiter at ${pc:04X}')
                if b == 34: quoted=not quoted
                cursor+=1
            n=cursor-pc+1
            payload=self.take(pc+1,n-2,end)
            row['operands']={'tail':basic_text(payload,self.profile['basicTokens']),
                             'rawTail':payload.hex(),'terminator':b,'terminatorOwned':True,
                             'returnCaveat':'callee controls text cursor; encoded tail is not a guarantee it consumes arguments or returns here'}
        elif grammar == 'sys_delimiter':
            if self.take(pc+1,1,end)[0] != spec['delimiter']:
                raise DecodeError(f'unmodeled SYS tail at ${pc:04X}')
            n=2
            row['operands']['tail']='empty; delimiter consumed through text pointer'
        else:
            raise DecodeError(f'unsupported grammar {grammar}')
        row['length']=n
        row['bytes']=self.take(pc,n,end).hex()
        if 'constant' in spec:
            row['operands']['constant']=spec['constant']
        return row

    def decode(self, map_data=None, source=None):
        rows=[]; regions=[]
        for label,start,end in [('init',self.init,self.main),('main',self.main,self.code_end)]:
            pc=start; first=len(rows)
            while pc < end:
                row=self.one(pc,end); row['region']=label
                rows.append(row); pc+=row['length']
            regions.append(dict(name=label,start=start,end=end,bytes=end-start,instructions=len(rows)-first))
        starts={r['address'] for r in rows}
        for r in rows:
            for target in r['targets']:
                if target not in starts:
                    raise DecodeError(f'target ${target:04X} from ${r["address"]:04X} is not an instruction boundary')
        maps=[]
        if map_data is not None:
            if len(map_data)<4 or len(map_data)%4:
                raise DecodeError('truncated LN map')
            supplied=source_lines(source) if source is not None else {}
            previous=-1
            for offset in range(0,len(map_data),4):
                line=word(map_data,offset,'big'); rel=word(map_data,offset+2,'big')
                if rel<previous or self.main+rel>self.code_end:
                    raise DecodeError('nonmonotonic/out-of-range map offset')
                previous=rel
                terminal=line==self.profile['map']['terminalLine']
                if terminal != (offset==len(map_data)-4):
                    raise DecodeError('missing or misplaced LN terminal record')
                address=self.main+rel
                owner=next((r['address'] for r in rows if r['address']<=address<r['address']+r['length']),None)
                maps.append(dict(line=line,offset=rel,address=address,terminal=terminal,
                                 instructionBoundary=address in starts,owningInstruction=owner,
                                 source=supplied.get(line)))
        return dict(schema='dtl-disassembly-v1',profile=self.profile['id'],
                    caveat='Structural decode; source annotation is supplied correspondence, not original-source recovery. Not a reachability or behavioral-equivalence claim.',
                    regions=regions,instructions=rows,sourceMap=maps,scalars=self.scalars,
                    otherRegions=[dict(name=n,start=a,end=b,bytes=self.take(a,b-a).hex()) for n,a,b in [
                        ('bootstrap/header',self.base,self.data_start),('data',self.data_start,self.init),
                        ('program separator',self.code_end,self.variables),('scalars',self.variables,self.array),
                        ('array metadata',self.array,self.trailer),('trailer',self.trailer,self.end)]],
                    branchKey={'high':self.key_hi,'low':self.key_lo},unknownInstructions=0)


def render(report):
    lines=[report['caveat']]
    maps=report['sourceMap']
    for r in report['instructions']:
        for m in maps:
            if m['address']==r['address']:
                text=m['source'] or ('[terminal map anchor]' if m['terminal'] else f'[source line {m["line"]}]')
                lines.append('\n'+text)
        desc=json.dumps(r['operands'],sort_keys=True)
        targets=' '.join(f'${t:04X}' for t in r['targets'])
        lines.append(f"${r['address']:04X}  {bytes.fromhex(r['bytes']).hex(' '):<35} {r['mnemonic']:<20} {desc} {targets}".rstrip())
    for m in maps:
        if not m['instructionBoundary']:
            lines.append(f"MAP line {m['line']} ${m['address']:04X}: interior/end anchor; owner={m['owningInstruction']}")
    return '\n'.join(lines)+'\n'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('prg',type=Path)
    parser.add_argument('--profile',type=Path,default=Path(__file__).with_name('dtl64_profile.json'))
    parser.add_argument('--runtime',type=Path,required=True,help='Original RTL-64 PRG, hash checked; never executed')
    parser.add_argument('--map',type=Path)
    parser.add_argument('--source',type=Path,help='Optional numbered text; not authenticated original source')
    parser.add_argument('--json-output',type=Path)
    parser.add_argument('--text-output',type=Path)
    args=parser.parse_args()
    try:
        profile=json.loads(args.profile.read_text())
        if sha(args.runtime.read_bytes()) != profile['runtimeSha256']:
            raise DecodeError('runtime hash mismatch')
        raw=args.prg.read_bytes()
        report=Decoder(raw,profile).decode(args.map.read_bytes() if args.map else None,args.source.read_text() if args.source else None)
        report.update(inputSha256=sha(raw),profileSha256=sha(args.profile.read_bytes()))
        text=render(report)
        if args.json_output: args.json_output.write_text(json.dumps(report,indent=2)+'\n')
        if args.text_output: args.text_output.write_text(text)
        if not args.text_output: print(text,end='')
    except (DecodeError,OSError) as exc:
        parser.exit(2,f'DTL decode refused: {exc}\n')


if __name__=='__main__':
    main()
