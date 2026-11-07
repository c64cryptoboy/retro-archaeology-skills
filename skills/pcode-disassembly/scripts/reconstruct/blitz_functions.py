"""One bounded BLITZ/Austro numeric leaf-FN structure, not call resolution.

Only a single straight-line, formal-only arithmetic result is admitted.  The
existing family lifter evaluates its VM expression; this module does not inline
calls, infer purity of arbitrary bodies, or import another family's stack ABI.
"""
import re
from formats import profile


NUMERIC_CONSTANTS={'CONST_SMALL','CONST_COMPACT','CONST_U8','CONST_U16','CONST_FAC5'}
BINARY={'ADD','SUBTRACT','MULTIPLY'}


def leaf_functions(report,family):
    """Return admitted headers only; every other header keeps the opaque path."""
    if family not in ('blitz','austrospeed') or report.get('selectedProfile')!=profile(family)['id']:
        return {}
    layout=report.get('layout',{})
    records=report.get('scalarRecords',[])
    if layout.get('variableRecordSize')!=7 or len(records)!=layout.get('variableCount'):
        return {}
    slots={}
    for index,record in enumerate(records):
        try:raw=bytes.fromhex(record.get('bytes',''))
        except (TypeError,ValueError):return {}
        if (len(raw)!=7 or record.get('index')!=index or
                record.get('address')!=layout.get('variableTable',-1)+7*index):
            return {}
        slots[2+7*index]=(record,raw)
    rows=report['instructions'];by_address={r['address']:r for r in rows}
    definitions=[r for r in rows if r['mnemonic']=='DEF_FN']
    admitted={}
    for header in definitions:
        descriptor=header.get('functionDescriptorOffset');formal=header.get('parameterDescriptorOffset')
        if descriptor not in slots or formal not in slots or descriptor==formal:
            continue
        if sum(r.get('functionDescriptorOffset')==descriptor for r in definitions)!=1:
            continue  # A lexical occurrence is not a reaching runtime definition.
        _,fn_bytes=slots[descriptor];parameter,param_bytes=slots[formal]
        # Function slots use the flagged first name byte, not an inferred source
        # spelling.  The formal must be a real, ordinary numeric scalar record.
        if not fn_bytes[0]&0x80 or fn_bytes[1]&0x80 or any(fn_bytes[2:]):
            continue
        name=''.join(chr(b) for b in param_bytes[:2] if b)
        if (not 0x41 <= param_bytes[0] <= 0x5A or param_bytes[1]&0x80 or
                not re.fullmatch(r'[A-Z][A-Z0-9]?',name) or parameter.get('name')!=name):
            continue
        start=header['address'];body=header.get('bodyTarget');skip=header.get('skipTarget')
        if (header.get('size')!=6 or body!=start+6 or skip not in by_address or skip<=body or
                header.get('skip')!=skip-start or by_address[skip].get('region')!=header.get('region')):
            continue
        body_rows=[];pc=body
        while pc<skip and pc in by_address:
            row=by_address[pc]
            if row.get('region')!=header.get('region') or not row.get('size'):
                break
            body_rows.append(row);pc+=row['size']
        if pc!=skip or not body_rows or body_rows[-1]['mnemonic']!='FN_RETURN':
            continue
        # No alternate body entry, including a branch to the return itself.
        # The declaration's own body/skip fields are the only allowed edges.
        external_entry=False
        for row in rows:
            if row is header:continue
            targets=row.get('targets',[])+[row[k] for k in ('target','bodyTarget','skipTarget') if k in row]
            if any(body<=target<skip for target in targets):external_entry=True;break
        if external_entry:continue
        depth=0;valid=True
        for row in body_rows[:-1]:
            mnemonic=row['mnemonic']
            if row.get('control') not in (None,'fallthrough'):
                valid=False;break
            if mnemonic=='LOAD_VAR':
                if row.get('variableIndex')!=parameter['index'] or row.get('variable')!=name:
                    valid=False;break
                depth+=1
            elif mnemonic in NUMERIC_CONSTANTS:
                if row.get('exactValue',row.get('value')) is None:
                    valid=False;break
                depth+=1
            elif mnemonic in BINARY and depth>=2:depth-=1
            elif mnemonic=='NEGATE' and depth>=1:pass
            else:valid=False;break
        if not valid or depth!=1:continue
        admitted[start]={'header':start,'descriptor':descriptor,'parameterOffset':formal,
                         'parameterName':name,'name':'FN F_'+str(descriptor),
                         'bodyEntry':body,'returnAddress':body_rows[-1]['address'],
                         'continuation':skip,'family':family}
    return admitted
