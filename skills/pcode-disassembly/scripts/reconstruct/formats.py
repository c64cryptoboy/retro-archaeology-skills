"""Thin binary-only adapters around the canonical refusing decoders/profiles."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent


def sha(data): return hashlib.sha256(data).hexdigest()


def module(family):
    family='blitz' if family=='austrospeed' else family
    name='_pcode_binary_'+family
    if name not in sys.modules:
        path=ROOT/family/('blitz_pcode.py' if family=='blitz' else family+'.py')
        spec=importlib.util.spec_from_file_location(name,path)
        mod=importlib.util.module_from_spec(spec);sys.modules[name]=mod;spec.loader.exec_module(mod)
    return sys.modules[name]


def profile(family):
    path={'blitz':HERE/'blitz_profile.json','austrospeed':ROOT/'austrospeed/austrospeed_profile.json','petspeed':ROOT/'petspeed/petspeed_profile.json',
          'basic64':ROOT/'basic64/basic64_profile-extended.json','dtl':ROOT/'dtl/dtl64_profile-omnibus.json',
          'speedcompiler':ROOT/'speedcompiler/speedcompiler_profile.json'}[family]
    return json.loads(path.read_text())


def blitz_layout(prg,p):
    m=module('blitz');base=int.from_bytes(prg[:2],'little');raw=prg[2:]
    if base!=2049 or base+len(raw)>65536: raise ValueError('unsupported BLITZ image extent')
    image=m.Image(Path('<binary>'),base,raw,sha(prg))
    table=p['dispatch']['startupPointerTable']
    vt,e1,e2,init,data,main=[int.from_bytes(image.read(table+2*i,2),'little') for i in range(6)]
    if not (table+12<=init<=data<=main<vt<=e1==e2<=image.end):raise ValueError('invalid BLITZ startup pointer ordering')
    trailing=image.read(e1,image.end-e1)
    if trailing and not (vt==e1 and trailing==bytes(7)):
        raise ValueError('unsupported bytes after BLITZ declared end')
    stride=p['layout']['variableRecordSize']
    if (e1-vt)%stride:raise ValueError('invalid BLITZ variable records')
    q=copy.deepcopy(p)
    q['layout'].update(initPcode=init,dataStart=data,dataEndExclusive=main,mainPcode=main,pcodeEndExclusive=vt,
                       variableTable=vt,variableCount=(e1-vt)//stride,endExclusive=e1,arrayDescriptors={},
                       retainedOpaqueTrailer=trailing.hex(),loadedEnd=image.end)
    return image,q


def check_extent(prg):
    if len(prg)<3 or int.from_bytes(prg[:2],'little')+len(prg)-2>65536:
        raise ValueError('unsupported C64 PRG extent')


def inspect(prg,family):
    check_extent(prg)
    m=module(family);p=profile(family)
    if family in ('blitz','austrospeed'):return blitz_layout(prg,p)[1]['layout']
    if family=='dtl':
        d=m.Decoder(prg,p)
        return {'init':d.init,'main':d.main,'codeEnd':d.code_end,'imageEnd':d.end}
    return m.inspect_image(prg,p)[2]


def decode(prg,family):
    """No source, maps, previous listings or filenames enter these decoders."""
    check_extent(prg)
    m=module(family);p=profile(family)
    if family=='speedcompiler':return m.disassemble(prg,p)
    if family=='dtl':
        report=m.Decoder(prg,p).decode()
    elif family in ('blitz','austrospeed'):
        image,p=blitz_layout(prg,p);names=m.variable_names(image,p);rows=[];regions=[]
        for label,start,end in [('init',p['layout']['initPcode'],p['layout']['dataStart']),('main',p['layout']['mainPcode'],p['layout']['variableTable'])]:
            pc=start
            while pc<end:
                row=m.decode_one(image,p,pc,names)
                if row['size'] is None or pc+row['size']>end:raise ValueError(f'unknown/truncated BLITZ opcode at ${pc:04X}')
                row['region']=label;rows.append(row);pc+=row['size']
            regions.append({'name':label,'start':start,'end':end})
        starts={r['address'] for r in rows}
        for r in rows:
            targets=r.get('targets',[])+[r[k] for k in ('target','bodyTarget','skipTarget') if k in r]
            if any(t not in starts for t in targets):raise ValueError('BLITZ target is not an instruction start')
        report={'instructions':rows,'regions':regions,'layout':p['layout'],'dataRecords':m.decode_data_block(image,p)['records']}
        # Retain storage identity and type bytes for the bounded FN/formal contract.
        report['scalarRecords']=[{'index':i,'address':p['layout']['variableTable']+7*i,
                                  'bytes':image.read(p['layout']['variableTable']+7*i,7).hex(),
                                  'name':name} for i,name in enumerate(names)]
    else:
        report=m.disassemble(prg,p)
        if not report['completeCodeDecode']:raise ValueError(report['error'])
    if family in ('basic64','dtl'):
        regions=report['regions'] if family=='basic64' else report['otherRegions']
        region=next(r for r in regions if r.get('kind',r.get('name','')).lower()=='data')
        base=int.from_bytes(prg[:2],'little')
        report['dataRegion']={'address':region['start'],'bytes':prg[2+region['start']-base:2+region['end']-base].hex()}
    base=int.from_bytes(prg[:2],'little');end=base+len(prg)-2
    if family in ('blitz','austrospeed'):
        l=report['layout'];table=p['dispatch']['startupPointerTable']
        bounds=[base,table,table+12,l['initPcode'],l['dataStart'],l['mainPcode'],l['variableTable'],l['endExclusive'],end]
        labels=['bootstrap/runtime/tables','startup pointers','pre-init opaque gap','init p-code','DATA','main p-code','scalar records','opaque appended record']
        regions=[dict(name=n,start=a,end=b) for n,a,b in zip(labels,bounds,bounds[1:])]
    elif family=='petspeed':
        l=report['layout'];bounds=[base,p['runtimeStart'],p['runtimeEnd'],l['data'],l['arrays'],l['initialization'],l['codeStart'],l['topCode'],end]
        labels=['bootstrap/header','runtime/tables','variable region','DATA (not lifted)','array region','initialization (not lifted)','main p-code','opaque trailing region']
        regions=[dict(name=n,start=a,end=b) for n,a,b in zip(labels,bounds,bounds[1:])]
    elif family=='basic64':regions=[dict(name=r['kind'],start=r['start'],end=r['end']) for r in report['regions']]
    else:regions=[dict(name=r['name'],start=r['start'],end=r['end']) for r in report['regions']+report['otherRegions']]
    regions=sorted((r for r in regions if r['end']>r['start']),key=lambda r:r['start'])
    cursor=base
    for r in regions:
        if r['start']!=cursor:raise ValueError('loaded-region partition has a gap/overlap')
        cursor=r['end'];r['sha256']=sha(prg[2+r['start']-base:2+cursor-base])
    if cursor!=end:raise ValueError('loaded-region partition is incomplete')
    report['loadedRegions']=regions
    report['selectedProfile']=p['id']
    report['selectedProfileSha256']=sha(json.dumps(p,sort_keys=True).encode())
    # Canonical output is newly generated here, never loaded from annotated JSON.
    return report
