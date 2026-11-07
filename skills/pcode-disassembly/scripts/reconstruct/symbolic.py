"""Conservative BASIC-like symbolic lifting, with separate VM contracts.

No original source, map or annotated-disassembly input. Unsupported effects and
joins kill facts. Text is a reading aid, not automatically runnable BASIC.
"""
from dataclasses import dataclass, field
from decimal import Decimal, localcontext
from fractions import Fraction
import json
import re
from formats import HERE, profile
import expression_display as display
from reading_projection import Statement


@dataclass
class Expr:
    text:str
    deps:set=field(default_factory=set)
    warnings:tuple=()
    reference:bool=False
    stable:bool=False  # Display value cannot be re-read from mutable VM state.
    producer:int|None=None  # Original evaluation site, not a later consumer/call.
    display_node:display.DisplayExpr|None=None  # Presentation only; text remains canonical.


def number(value):
    f=Fraction(str(value))
    if f.denominator==1:return str(f.numerator)
    with localcontext() as ctx:
        ctx.prec=250
        return format(Decimal(f.numerator)/Decimal(f.denominator),'f').rstrip('0').rstrip('.')


def quoted(data):
    parts=[];buf=''
    for b in data:
        if 32<=b<=126 and b!=34:buf+=chr(b)
        else:
            if buf:parts.append('"'+buf+'"');buf=''
            parts.append(f'CHR$({b})')
    if buf:parts.append('"'+buf+'"')
    return '+'.join(parts) or '""'


class Lifter:
    stacks={'stack','ss','alt'}
    def __init__(self,family,report,capture_sites=(),false_test_sites=(),*,readable=True):
        self.readable=readable and family=='dtl'
        # Identity/contracts remain distinct; only the audited encoding adapter is shared.
        self.identity_family=family
        self.family='blitz' if family=='austrospeed' else family
        self.report=report;self.rules=json.loads((HERE/'semantics.json').read_text())['families'][family]
        self.rows=report['instructions'];self.groups=[];self.pending=[];self.regs={};self.stack={k:[] for k in self.stacks}
        self.reading_statements=[];self.reading_arguments=[]
        self.symbols={};self.arrays={};self.output=None;self.input=None;self.readmode=None
        self.array_index=None;self.array_accesses={}
        self.limit=None;self.step=None;self.current=None;self.destination_type=None
        self.capture_sites=frozenset(capture_sites);self.fn_capture_candidates=set()
        self.fn_index=None;self.fn_definitions={};self.fn_returns={};self.fn_calls={}
        self.false_test_sites=frozenset(false_test_sites);self.false_test_candidates=set()
        self.false_test_index=None;self.false_test_joins={};self.false_test_edges={}
        self.for_zero_ready=None;self.for_zero_recoveries={};self.for_zero_stores={}
        self.sys_sites=[];self.rows_by_address={r['address']:r for r in self.rows}
        if self.family=='dtl':
            from dtl_arrays import analyze_arrays
            self.array_index=analyze_arrays(report)
            self.array_accesses={a['address']:a for a in self.array_index['accesses']}
            from dtl_branches import analyze_false_tests, forwarded_edges
            self.false_test_index=analyze_false_tests(report)
            self.false_test_joins={j['address']:j for j in self.false_test_index['joins']}
            self.false_test_edges=forwarded_edges(self.false_test_index,self.false_test_sites)
            self.false_test_index['forwardedEdges']=[self.false_test_edges[a] for a in sorted(self.false_test_edges)]
            from dtl_functions import analyze_functions
            self.fn_index=analyze_functions(report)
            self.fn_definitions={d['header']:d for d in self.fn_index['definitions']}
            self.fn_returns={d['returnAddress']:d for d in self.fn_index['definitions'] if d['status']=='block'}
            self.fn_calls={c['address']:c for c in self.fn_index['calls']}
        self.targets=set()
        for r in self.rows:
            v=r.get('operands',{});self.targets.update(r.get('targets',[]));self.targets.update(v.get('targets',[]))
            for k in ('target','bodyTarget','skipTarget'):
                if k in r:self.targets.add(r[k])
            for k in ('target','body','skip','bodyEntry'):
                if k in v:self.targets.add(v[k])
        for i,r in enumerate(self.rows[:-1]):
            if r['mnemonic'].startswith('FOR_') and r['mnemonic'] not in ('FOR_LIMIT','FOR_LIMIT_STEP'):
                self.targets.add(self.rows[i+1]['address'])
        if self.family=='dtl':
            from dtl_for import zero_candidates
            self.for_zero_stores={c['storeAddress']:c for c in zero_candidates(report,self.targets).values()}
        self.blitz_leaf_definitions={};self.blitz_leaf_returns={};self.blitz_leaf_calls={}
        if self.family=='blitz':
            from blitz_functions import leaf_functions
            self.blitz_leaf_definitions=leaf_functions(report,self.identity_family)
            self.blitz_leaf_returns={d['returnAddress']:d for d in self.blitz_leaf_definitions.values()}
            self.blitz_leaf_calls={d['descriptor']:d for d in self.blitz_leaf_definitions.values()}
        self.tokens=profile('dtl')['basicTokens']

    def wipe(self,io=False):
        self.regs={};self.stack={k:[] for k in self.stacks};self.limit=None;self.step=None;self.destination_type=None
        self.for_zero_ready=None
        if io:self.output='<?>';self.input='<?>';self.readmode=None

    def get(self,key):
        if key.startswith('#'):return Expr(key[1:])
        if key in self.stacks:
            return self.stack[key].pop() if self.stack[key] else Expr('<?>',warnings=('unknown/empty '+key,))
        return self.regs.get(key,Expr('<?>',warnings=('unknown '+key,)))

    def set(self,key,e):
        if len(e.text)>4096:
            e=Expr('<?>',{self.current['address']},e.warnings+('expression size limit; details retained in owned low-level spans',))
        if key in self.stacks:
            if len(self.stack[key])>=256:self.stack[key]=[Expr('<?>',warnings=('stack limit',))]
            self.stack[key].append(e)
        else:self.regs[key]=e

    def expr(self,text,args=(),warnings=(),stable=False,display_node=None):
        return Expr(text,{self.current['address']}|set().union(*(x.deps for x in args)),tuple(dict.fromkeys([*warnings,*[w for x in args for w in x.warnings]])),stable=stable,producer=self.current['address'],display_node=display_node)

    def shown(self,e):
        return display.render(display.node(e)) if self.readable else e.text

    def emit(self,text,kind='inferred',args=(),warnings=(),reset=False,statement=None):
        warns=list(dict.fromkeys([*warnings,*[w for e in args for w in e.warnings]]))
        if '<?>' in text or warns and any('unknown' in w for w in warns):kind='partial'
        self.reading_statements.append(statement if self.readable else None)
        self.reading_arguments.append(tuple(display.node(e) for e in args) if self.readable else ())
        self.groups.append({'text':text,'kind':kind,'warnings':warns,'instructions':self.pending,
                            'evidenceAddresses':sorted(set().union(*(e.deps for e in args))|{r['address'] for r in self.pending})})
        self.pending=[]
        if reset:self.wipe()

    def barrier(self,reason):
        if self.pending:self.emit('REM UNRESOLVED: '+reason,'unresolved')
        self.wipe(io=True)

    def var(self,r,field='value',page3=False):
        v=r.get('operands',{});val=v.get(field,r.get(field))
        if isinstance(val,str):name=val;key='name:'+val;original=True
        else:
            if val is None:return '<?>'
            addr=val+0x300 if page3 else val
            key=f'{self.family}:{addr:04X}';name=v.get('name',f'V_{addr:04X}');original='name' in v
        self.symbols.setdefault(key,{'name':name,'retainedName':original,'source':'binary name bytes' if original else 'generated from encoded storage identity'})
        return name

    def constant(self,r,rule):
        v=r.get('operands',{});b=bytes.fromhex(r['bytes'])
        if self.family=='blitz':
            if 'text' in r:
                n=r.get('length',0);return quoted(b[len(b)-n:] if n else b'')
            value=r.get('exactValue',r.get('value'))
            return '<?>' if value is None else number(value)
        if 'stringHex' in v:return quoted(bytes.fromhex(v['stringHex']))
        if 'payloadHex' in v:return quoted(bytes.fromhex(v['payloadHex']))
        if 'packedFloat' in v:
            data=bytes.fromhex(v['packedFloat']);exp=data[0];mant=int.from_bytes(data[1:],'big')
            f=Fraction(0) if exp==0 else Fraction((1<<31)+(mant&0x7fffffff),1<<31)*Fraction(2)**(exp-129)*(-1 if mant>>31 else 1)
            return number(f)
        if 'numerator' in v:return number(Fraction(v['numerator'],v['denominator']))
        if 'exact' in v:return number(v['exact'])
        value=v.get('signedValue',v.get('value',v.get('constant')))
        if value is None:return '<?>'
        if rule.get('signedWord') and value>=32768:value-=65536
        return number(value)

    def label(self,target):return '<?>' if target is None else f'L_{target:04X}'

    def function(self,name,args,dst,effect=False,warning=''):
        e=self.expr(name+'('+', '.join(x.text for x in args)+')',args,[warning] if warning else [],
                    stable=self.family=='dtl' and not effect and all(x.stable for x in args),
                    display_node=display.call(name,[display.node(x) for x in args],origin=self.current['address']) if self.family=='dtl' else None)
        if effect:
            tmp=f'T_{self.current["address"]:04X}'
            self.emit(tmp+' = '+self.shown(e),args=[e],warnings=['Synthetic temporary preserves evaluation site/order.'],
                      statement=Statement('temporary',(display.node(e),),target=tmp,
                                          eligible=self.readable and name in ('RND','PEEK','FRE','POS')))
            if name=='USR' or name.startswith('FN '):
                if name.startswith('FN ') and self.family=='dtl':
                    # B4/FN_RETURN leave lower physical values intact, not their
                    # source variables: a function body may mutate globals/formals.
                    self.fn_capture_candidates.update(x.producer for x in self.stack['stack']
                                                      if not x.stable and x.producer is not None)
                    lower=[x if x.stable else Expr('<?>',warnings=('FN may change earlier global/formal/array reads.',))
                           for x in self.stack['stack']]
                    self.wipe(io=True)
                    self.stack['stack']=lower
                else:self.wipe(io=True)  # Other FN ABIs and opaque USR are unproved.
            e=Expr(tmp,{self.current['address']},e.warnings,stable=True,
                   display_node=display.temporary(tmp) if self.family=='dtl' else None)
        if self.family=='petspeed' or self.family=='basic64' and dst in ('fac','ss'):
            self.regs.pop('arg',None);self.regs.pop('ia',None)
        self.set(dst,e)

    def standard(self,r,rule):
        op=rule['op'];v=r.get('operands',{});n=r['mnemonic']
        if op=='constant':self.set(rule['dst'],self.expr(self.constant(r,rule)))
        elif op=='literal':self.set(rule['dst'],self.expr(rule['value']))
        elif op=='load':
            view={**r,'operands':{**v,rule['field']:rule['fixedAddress']}} if 'fixedAddress' in rule else r
            e=self.expr(self.var(view,rule['field'],rule.get('page3',False)))
            if self.family=='dtl':e.display_node=display.leaf(e.text,origin=r['address'])
            e.reference=self.family=='blitz' and n=='VAR_DESCRIPTOR'
            if n.startswith('LOAD_FLOAT_AS_INTEGER') or n=='LOAD_BASIC_RESULT_AS_INTEGER':
                e=self.expr('VM_INT('+e.text+')',[e],['Runtime float-to-integer conversion; not assumed to be BASIC INT.'])
                self.regs.pop('fac',None)
            self.set(rule['dst'],e)
        elif op=='move':
            e=self.get(rule['src'])
            warning=('Runtime conversion/rounding applies.',) if rule.get('conversion') else ()
            text=e.text
            if n in ('FAC_TO_INTEGER','FAC_TO_INTEGER_ARG','POP_FLOAT_TO_INTEGER_ARG'):
                text='VM_INT('+text+')';self.regs.pop('fac',None)
            if n in ('PUSH_FAC','FAC_TO_ARG') and self.family=='basic64':
                text='VM_ROUND('+text+')'
                if n=='FAC_TO_ARG':self.set('fac',self.expr(text,[e],warning))
            self.set(rule['dst'],self.expr(text,[e],warning))
        elif op=='binary':
            if rule.get('leftFirst'):left=self.get(rule['left']);right=self.get(rule['right'])
            else:right=self.get(rule['right']);left=self.get(rule['left'])
            warns=[rule['warning']] if rule.get('warning') else []
            if self.family=='dtl' and rule['symbol'] in ('/','^'):warns.append('DTL integer/SI mode can differ from stock BASIC arithmetic.')
            # Arithmetic helpers may destroy their secondary accumulator.
            if self.family in ('petspeed','basic64'):
                self.regs.pop('arg',None);self.regs.pop('ia',None)
            self.set(rule['dst'],self.expr(f'({left.text} {rule["symbol"]} {right.text})',[left,right],warns,
                                           stable=self.family=='dtl' and left.stable and right.stable,
                                           display_node=display.binary(rule['symbol'],display.node(left),display.node(right),origin=r['address']) if self.family=='dtl' else None))
        elif op=='unary':
            e=self.get(rule['src']);symbol='NOT ' if 'NOT' in n else '-'
            self.set(rule['dst'],self.expr('('+symbol+e.text+')',[e],stable=self.family=='dtl' and e.stable,
                                          display_node=display.unary(symbol.strip(),display.node(e),origin=r['address']) if self.family=='dtl' else None))
        elif op=='function':
            args=[self.get(x) for x in rule['args']]
            if rule.get('reverseArgs'):args.reverse()
            self.function(rule['name'],args,rule['dst'],rule.get('effect',False),rule.get('warning',''))
        elif op=='store':
            e=self.get(rule['src']);name=self.var(r,rule['field'],rule.get('page3',False))
            self.emit(name+' = '+self.shown(e),args=[e],reset=True,
                      statement=Statement('assignment',(display.node(e),),target=name,origin=r['address']))
            # Do not infer that a typed store leaves FAC equal to its converted destination.
        elif op=='system':
            name='TI$' if 'STRING' in n else 'TI' if 'TIME' in n else 'ST' if 'STATUS' in n else 'π'
            e=self.expr(name,warnings=['Runtime system-variable representation may differ from stock BASIC.'],
                        display_node=display.leaf(name,origin=r['address']) if self.family=='dtl' else None)
            tmp=f'T_{r["address"]:04X}'
            self.emit(tmp+' = '+name,args=[e],statement=Statement('temporary',(display.node(e),),target=tmp))
            self.set(rule['dst'],Expr(tmp,{r['address']},e.warnings,
                                     display_node=display.temporary(tmp) if self.family=='dtl' else None))
        elif op=='print_function':
            e=self.get(rule['src']);prefix='PRINT' if self.output is None else 'PRINT#'+self.output+', '
            self.emit(prefix+' '+rule['name']+'('+self.shown(e)+');',args=[e],reset=True)
        elif op=='print_comma':
            self.emit('PRINT ,' if self.output is None else 'PRINT#'+self.output+', ,',reset=True)
        elif op in ('print','newline'):
            prefix='PRINT' if self.output is None else 'PRINT#'+self.output+', '
            if op=='newline':self.emit(prefix,reset=True)
            else:
                e=self.get(rule['src']);self.emit(prefix+' '+self.shown(e)+rule.get('suffix','' if rule.get('newline') else ';'),args=[e],reset=True)
            if rule.get('restoreChannels'):self.output=None;self.input=None
        elif op=='simple':
            text={'RESTORE_DATA':'RESTORE','NEW_AND_EXIT':'NEW','CLEAR_AND_RESTORE':'CLR'}.get(n,n)
            self.emit(text,reset=True)
            if text in ('CLR','RUN','NEW'):self.output=None;self.input=None;self.readmode=None
            elif text in ('END','STOP','RETURN'):self.wipe(io=True)
        elif op=='branch':
            target=v.get('target',r.get('target'));self.emit(n+' '+self.label(target),reset=True)
            if n=='GOSUB':self.wipe(io=True)
        elif op=='conditional':
            e=self.get(rule['src']);false=n in ('SKIP_IF_FALSE','IF_FALSE_GOTO','IF_FALSE_SKIP')
            target=v.get('target',r.get('target',next(iter(r.get('targets',[])),None)))
            condition=('('+e.text+') = 0' if false else e.text)
            if self.readable:
                if not false:condition=self.shown(e)
                elif '<?>' in e.text:condition='('+self.shown(e)+') = 0'
                else:condition=display.false_test(display.node(e))
            self.emit('IF '+condition+' THEN GOTO '+self.label(target),args=[e],reset=True,
                      statement=Statement('conditional',(display.node(e),),target=self.label(target),origin=r['address'],false=false))
        elif op=='conditional_return':
            e=self.get(rule['src']);self.emit('IF '+self.shown(e)+' THEN RETURN',args=[e],reset=True)
        elif op=='on':
            e=self.get(rule['src']);targets=v.get('targets',r.get('targets',[]));verb=rule.get('verb',v.get('branchMode','<?>'))
            self.emit('ON '+self.shown(e)+' '+verb+' '+', '.join(self.label(t) for t in targets),args=[e],reset=True,
                      statement=Statement('on',(display.node(e),),target=verb+' '+', '.join(self.label(t) for t in targets),origin=r['address']))
            if verb=='GOSUB':self.wipe(io=True)
        elif op=='statement':
            args=[self.get(x) for x in rule['args']]
            if rule.get('reverseArgs'):args.reverse()
            if rule.get('reverseFirstTwo'):args[:2]=reversed(args[:2])
            self.emit(rule['name']+' '+', '.join(self.shown(x) for x in args),args=args,reset=True,
                      statement=Statement('statement',tuple(display.node(x) for x in args),target=rule['name'],origin=r['address']))
            if rule.get('killsMemory'):self.wipe(io=True)
        elif op=='time_store':
            e=self.get(rule['src']);self.emit('TI$ = '+self.shown(e),args=[e],reset=True)
        elif op=='input_value':
            verb=rule['verb'];tmp=f'T_{r["address"]:04X}'+('$' if 'STRING' in n else '')
            if verb=='selected-input':verb=self.readmode or '<?>'
            combined='modifier' in rule
            args=[];warnings=['Synthetic input temporary; destination assignment follows.']
            if combined:
                if v.get('modifier')!=rule['modifier']:
                    self.barrier('inconsistent contextual input-store modifier');return
                if self.destination_type not in (None,rule['destinationType']):
                    self.barrier('input-store type does not match prepared element destination');return
                dest=self.get('destination');tmp=dest.text;args=[dest]
                warnings=['Prepared element destination; original INPUT/READ grouping not recovered.']
                if rule['destinationType']=='integer':warnings.append('Runtime numeric-to-integer destination conversion; not assumed to be stock BASIC INT.')
            elif 'modifier' in v:
                self.barrier('unmodeled contextual input-store modifier');return
            if verb=='INPUT':
                self.emit('REM INPUT'+('#'+self.input if self.input is not None else '')+' FIELD -> '+tmp,'partial',args=args,warnings=warnings+['Original INPUT grouping/prompt and retry semantics not reconstructed.'])
            else:
                prefix=verb+'#'+self.input+', ' if verb=='GET' and self.input is not None else verb+' '
                self.emit(prefix+tmp,args=args,warnings=warnings)
            if verb=='GET':self.wipe(io=True)  # Do not assume whether this ABI restores its channel.
            elif self.family=='petspeed':self.wipe()  # Input/parsing and typed stores may clobber facts.
            if not combined:self.set(rule['dst'],Expr(tmp,{r['address']}))
        elif op=='barrier':self.emit('REM VM '+n,'structural',reset=True)
        else:raise ValueError('unsupported symbolic contract '+op)

    def dtl(self,r):
        n=r['mnemonic'];v=r['operands'];g=r['grammar']
        if g=='basic_island':
            text=v['text'];self.emit(text,'embedded',reset=True)
            # Names/ranks are associated by the whole-object binary prepass;
            # file order does not establish runtime declaration order.
            if not text.startswith(('PRINT','DIM','DEF')):self.wipe(io=True)
            return True
        if n=='ARRAY_REGISTER':
            self.emit('REM array descriptor '+str(v['value']),'structural',reset=True);return True
        if n in ('DELIMITER','INIT_DECODE','VARIABLE_FILE','INIT_ENTER','DIRECTIVE'):
            self.emit('REM VM '+n,'structural',reset=True);return True
        if n.startswith('INTEGER_') or n in ('REAL_LITERAL','STRING_LITERAL'):
            text=quoted(bytes.fromhex(v['bytes'])) if n=='STRING_LITERAL' else self.constant(r,{})
            self.set('stack',self.expr(text,stable=True));return True
        if n.startswith(('LOAD_','STORE_')):
            if 'ARRAY' in n:
                info=self.array_accesses.get(r['address'])
                if not info or info['status']!='associated':
                    self.barrier('array rank/name not established from binary DIM; association absent or refused');return True
                name,rank=info['name'],info['rank']
                warnings=['Array name/rank from a later binary DIM/registration; runtime initialization is not proved.'] if info['precedesAllRegistrations'] else []
                value=self.get('stack') if n.startswith('STORE') else None
                subs=[self.get('stack') for _ in range(rank)][::-1]
                text=name+'('+', '.join(e.text for e in subs)+')'
                shaped=display.call(name,[display.node(e) for e in subs],origin=r['address'] if value is None else None)
                if value:self.emit((display.render(shaped) if self.readable else text)+' = '+self.shown(value),args=[*subs,value],warnings=warnings,reset=True,
                                   statement=Statement('array-assignment',(shaped,display.node(value)),origin=r['address']))
                else:self.set('stack',self.expr(text,subs,warnings,display_node=shaped))
            else:
                rule={'op':'store' if n.startswith('STORE') else 'load','field':'value','src':'stack','dst':'stack'}
                candidate=self.for_zero_stores.get(r['address'])
                value=self.stack['stack'][0] if len(self.stack['stack'])==1 else None
                zero_ready=bool(candidate and value and value.text=='0' and value.stable and not value.reference and
                                not value.warnings and value.producer==candidate['producerAddress'] and
                                value.deps=={candidate['producerAddress']} and not self.regs and
                                not self.stack['ss'] and not self.stack['alt'] and
                                [p['address'] for p in self.pending]==[candidate['producerAddress'],r['address']])
                self.standard(r,rule)
                # Store still destroys every symbolic expression fact. This is a
                # separate, one-successor, zero-only native-register proof marker.
                if zero_ready:self.for_zero_ready=candidate
            return True
        if n.startswith('COMPARE_'):
            short=n.removeprefix('COMPARE_');self.standard(r,self.rules[short]);return True
        if n in ('FUNCTION','FUNCTION_F8'):
            fn=v['operation']
            if fn in ('PI','TI','TI$','ST'):
                temp={'mnemonic':{'PI':'PI','TI':'TIME','TI$':'TIME_STRING','ST':'STATUS'}[fn],**{k:z for k,z in r.items() if k!='mnemonic'}}
                self.standard(temp,{'op':'system','dst':'stack'});return True
            if fn=='SET_TI$':self.standard(r,{'op':'time_store','src':'stack'});return True
            argc=3 if fn=='MID$' else 2 if fn in ('LEFT$','RIGHT$') else 1
            args=[self.get('stack') for _ in range(argc)][::-1]
            self.function(fn,args,'stack',fn in ('RND','USR','PEEK','FRE','POS'));return True
        if n=='SYS':
            from dtl_navigation import record_sys
            address=self.get('stack');self.sys_sites.append(record_sys(r,address,self.rows_by_address))
            self.emit('SYS '+self.shown(address)+v['tail'],args=[address],warnings=[v['returnCaveat']],reset=True,
                      statement=Statement('sys',(display.node(address),),suffix=v['tail'],origin=r['address']))
            self.wipe(io=True);return True
        if n in ('CLEAR_OR_RUN','RUN_BOOTSTRAP'):
            self.emit('CLR' if n=='CLEAR_OR_RUN' else 'RUN',reset=True);self.output=None;self.input=None;return True
        if n=='IF_SKIP_FALSE':
            edge=self.false_test_edges.get(r['address'])
            view={**r,'mnemonic':'IF_FALSE_SKIP'}
            if edge:view['operands']={**v,'target':edge['readingTarget']}
            self.standard(view,self.rules['IF_FALSE_SKIP'])
            if edge:
                self.groups[-1]['warnings'].append('Reading-view false edge forwarded through '+
                    ', '.join(self.label(a) for a in edge['through'])+'; encoded target remains '+
                    self.label(edge['encodedTarget'])+' in the owned p-code.')
            if r['address'] in self.false_test_sites:
                self.groups[-1]['warnings'].append('Fallthrough-computed test; incoming IF-false edges are forwarded separately. Normal no-STOP path only.')
            return True
        if n=='SKIP':self.emit('GOTO '+self.label(r['targets'][0]),reset=True);return True
        if n in ('GOTO','GOSUB'):
            self.standard({**r,'target':r['targets'][0]},self.rules[n]);return True
        if n.startswith('FOR_'):
            step=self.get('stack') if n.endswith('_STEP') else Expr('1')
            candidate=self.for_zero_ready
            if (candidate and candidate['forAddress']==r['address'] and n=='FOR_REAL' and
                    not any(self.stack.values()) and not self.regs and len(self.pending)==1):
                from dtl_for import ZERO_SCOPE
                limit=Expr('0',{candidate['producerAddress'],candidate['storeAddress']},(ZERO_SCOPE,),stable=True)
                self.for_zero_recoveries[r['address']]={**candidate,'status':'recovered-zero'}
            else:limit=self.get('stack')
            name=self.var(r)
            self.emit(f'FOR {name} = {name} TO {self.shown(limit)} STEP {self.shown(step)}',args=[limit,step],warnings=['Initial assignment is shown separately.'],reset=True,
                      statement=Statement('for',(display.node(limit),display.node(step)),target=name,origin=r['address'],default_step=not n.endswith('_STEP')))
            return True
        if n.startswith('NEXT'):
            self.emit('NEXT'+(' '+self.var(r) if n=='NEXT_NAMED' else ''),reset=True);return True
        if n=='DEF_FN':
            d=self.fn_definitions[r['address']]
            if d['status']=='block':
                self.emit(f'DEF {d["name"]}({d["parameterName"]}); body {self.label(d["bodyEntry"])}; continuation {self.label(d["continuation"])}',
                          warnings=['Inline body is skipped when this definition executes; normal-return structure, not a purity claim.'],reset=True)
            else:
                self.emit(f'REM DEF FN descriptor {v.get("descriptorOffset")}; body {self.label(d["bodyEntry"])}; skip {self.label(d["continuation"])}',
                          'partial',warnings=d['reasons'],reset=True)
            return True
        if n=='FN_CALL':
            c=self.fn_calls[r['address']];e=self.get('stack')
            fallback=v.get('name','F_'+str(v['value'])) if 'scalars' not in self.report else 'F_'+str(v['value'])
            name=c['name'] or ('FN '+fallback.removeprefix('FN '))
            candidates=', '.join(self.label(a) for a in c['candidateDefinitions']) or 'none'
            self.function(name,[e],'stack',True,'Descriptor-indirect function; static definition candidates: '+candidates+
                          '; runtime binding and purity unproved.'+(' '+' '.join(c['reasons']) if c['reasons'] else ''))
            return True
        if n=='FN_RETURN':
            e=self.get('stack');d=self.fn_returns.get(r['address'])
            if d:
                self.emit('RETURN '+d['name']+' = '+self.shown(e),args=[e],
                          warnings=['Result of body at '+self.label(d['bodyEntry'])+'; saved formal is restored on normal return.'],reset=True,
                          statement=Statement('fn-return',(display.node(e),),target=d['name'],origin=r['address']))
            else:self.emit('REM FN RESULT '+self.shown(e),'partial',args=[e],reset=True)
            return True
        return False

    def special(self,r):
        n=r['mnemonic'];v=r.get('operands',{})
        if self.family=='dtl' and self.dtl(r):return True
        if self.family=='petspeed' and n=='ARRAY_BASE':
            self.set('arraybase',self.expr(f'{v["value"]:04X}'));return True
        if self.family=='petspeed' and n in ('ARRAY_LOAD_FAC','INTEGER_ARRAY_LOAD','STRING_ARRAY_LOAD','ARRAY_DEST','INTEGER_ARRAY_DEST','STRING_ARRAY_DEST'):
            index=self.get('fac');base=self.get('arraybase')
            if n.endswith('_DEST'):
                # The native handler resolves $3D/$3E now, before reading input
                # or evaluating a RHS. Never re-evaluate a variable index later.
                temp=f'T_INDEX_{r["address"]:04X}'
                self.emit(temp+' = '+index.text,args=[index],warnings=['Capture index at element-destination preparation, before later effects.'])
                index=Expr(temp,index.deps|{r['address']},index.warnings)
                self.regs.pop('fac',None);self.regs.pop('arg',None)
                self.destination_type='integer' if n.startswith('INTEGER') else 'string' if n.startswith('STRING') else 'number'
            e=self.expr('ELEM_'+base.text+'('+index.text+')',[base,index],['Runtime index conversion/address arithmetic; linear index, original array dimensions/name not recovered.'])
            self.set('destination' if n.endswith('_DEST') else 'fac',e);return True
        if self.family=='petspeed' and n=='CHR_STRING':
            value=self.get('fac')
            producer=self.rows_by_address.get(value.producer,{}).get('mnemonic')
            # Untyped/derived FAC values need a separate conversion/type proof.
            if value.deps!={value.producer} or producer not in (
                    'ZERO_FAC','ONE_FAC','CONST_U8_FAC','CONST_I16_FAC','CONST_FLOAT_FAC'):
                return False
            try:numeric=Fraction(value.text)
            except ValueError:return False
            if not 0<=numeric<256 or producer!='CONST_FLOAT_FAC' and numeric.denominator!=1:
                return False
            # The byte check precedes allocation.  Keep even unused results at
            # this producer site; GC can clobber ARG and the integer scratch.
            self.function('CHR$',[value],'fac',True,
                          'Numeric-literal FAC only; conversion/range check precedes allocation/GC.  Normal-result string; heap/error behavior is not stock BASIC equivalence.')
            return True
        if self.family=='petspeed' and n=='LOAD_STRING_ELEMENT_AT':
            self.set('fac',self.expr(f'STRDESC_{v["value"]:04X}$',warnings=[
                'Synthetic string view of an absolute three-byte descriptor slot; array identity/dimensions/subscripts not recovered; character bytes are not copied.']))
            return True
        if self.family=='petspeed' and n in ('STORE_ELEMENT','STORE_INTEGER_ELEMENT','STORE_ELEMENT_AT','LOAD_ELEMENT_AT'):
            dest=self.expr(f'MEM_{v["value"]:04X}',warnings=['Compiler-resolved element address; original subscript not recovered.']) if 'value' in v else self.get('destination')
            if n=='LOAD_ELEMENT_AT':self.set('fac',dest)
            else:
                value=self.get('fac');self.emit(dest.text+' = '+value.text,args=[dest,value],reset=True)
            return True
        if self.family=='basic64' and 'arrayBase' in v:
            rank=len(v['extentsReversed']);store=n.startswith('STORE')
            value=self.get('ss' if 'STRING' in n else 'iv' if 'INTEGER' in n else 'fac') if store else None
            last=self.get('alt' if store else 'iv')
            subs=[last]+[self.get('alt') for _ in range(rank-1)];subs.reverse()
            suffix='$' if 'STRING' in n else '%' if 'INTEGER' in n else ''
            array=f'AR_{v["arrayBase"]:04X}'+suffix
            dest=self.expr(array+'('+', '.join(e.text for e in subs)+')',subs)
            self.symbols.setdefault(array,{'name':array,'retainedName':False,'source':'binary array descriptor','bounds':[x-1 for x in reversed(v['extentsReversed'])]})
            if store:self.emit(dest.text+' = '+value.text,args=[dest,value],reset=True)
            else:self.set('ss' if 'STRING' in n else 'iv' if 'INTEGER' in n else 'fac',dest)
            return True
        if self.family=='blitz' and n in ('LOAD_ARRAY','STORE_ARRAY'):
            value=self.get('stack') if n=='STORE_ARRAY' else None;index=self.get('stack')
            info=self.arrays.get(r['descriptorOffset'])
            name=info[0] if info else 'ARRAY_'+str(r['descriptorOffset'])
            text=name+'('+index.text+')' if info and info[1]==1 else 'ELEM_'+str(r['descriptorOffset'])+'('+index.text+')'
            e=self.expr(text,[index],[] if info and info[1]==1 else ['Flattened index; multidimensional source subscripts not recovered.'])
            if value:self.emit(text+' = '+value.text,args=[e,value],reset=True)
            else:
                e.reference=True;self.set('stack',e)
            return True
        if self.family=='blitz' and n=='INPUT_BEGIN':
            self.input_fields=[];return True
        if self.family=='blitz' and n in ('INPUT_FIRST','INPUT_NEXT','INPUT_FINAL'):
            e=self.get('stack')
            if not hasattr(self,'input_fields'):self.input_fields=[]
            self.input_fields.append(e)
            if n=='INPUT_FINAL':
                prefix='INPUT' if self.input is None else 'INPUT#'+self.input+','
                fields=self.input_fields;self.input_fields=[]
                self.emit(prefix+' '+', '.join(x.text for x in fields),args=fields,reset=True)
            return True
        if self.family=='blitz' and n in ('OPEN','LOAD','SAVE','VERIFY'):
            count=r.get('value',0)
            minimum,maximum=(1,4) if n=='OPEN' else (0,3)
            if not minimum<=count<=maximum:self.barrier('unsupported '+n+' arity');return True
            args=[self.get('stack') for _ in range(count)]
            self.emit(n+(' '+', '.join(e.text for e in args) if args else ''),args=args,reset=True)
            if n=='LOAD':self.wipe(io=True)
            return True
        if self.family=='blitz' and n in ('READ','READ_NUMERIC','GET','INPUT_KEYBOARD'):
            e=self.get('stack');verb='READ' if n.startswith('READ') else 'INPUT' if n=='INPUT_KEYBOARD' else 'GET'
            # A compiled destination may be an array-reference expression; preserve it explicitly.
            prefix=verb+'#'+self.input+', ' if verb=='GET' and self.input is not None else verb+' '
            self.emit(prefix+e.text,'inferred' if e.reference else 'partial',args=[e],warnings=['Destination-reference interpretation; original statement grouping not recovered.']+([] if e.reference else ['Destination reference not established.']),reset=True)
            if verb=='GET':self.wipe(io=True)
            return True
        if self.family=='blitz' and n.startswith('CONST_'):
            self.set('stack',self.expr(self.constant(r,{})));return True
        if n in ('SELECT_OUTPUT_FILE','SELECT_OUTPUT_CHANNEL','SELECT_INPUT_FILE','SELECT_INPUT_CHANNEL','SELECT_GET_FILE'):
            src='stack' if self.family=='blitz' else 'iv' if self.family=='basic64' else 'fac';e=self.get(src)
            if 'OUTPUT' in n:self.output=e.text
            else:self.input=e.text
            self.emit('REM '+n+' '+e.text,'structural',args=[e]);return True
        if n in ('RESTORE_DEFAULT_CHANNELS','RESTORE_CHANNELS'):
            self.output=None;self.input=None;self.emit('REM restore default I/O channels','structural');return True
        if n=='SELECT_DATA_INPUT':self.readmode='READ';self.emit('REM select DATA cursor','structural');return True
        if n in ('INPUT_BEGIN','INPUT_PROMPT','SELECT_FILE_INPUT'):
            if n=='SELECT_FILE_INPUT':self.input=self.get('iv').text
            self.readmode='INPUT';self.emit('REM '+n+(' '+quoted(bytes.fromhex(v['payloadHex'])) if 'payloadHex' in v else ''),'partial',warnings=['Input field grouping/retry control remains partial.']);return True
        if self.family!='blitz' and n in ('NEXT','NEXT_VARIABLE','NEXT_NAMED'):
            suffix=' '+self.var(r) if n!='NEXT' else ''
            self.emit('NEXT'+suffix,reset=True);return True
        if n in ('FOR_LIMIT','FOR_LIMIT_STEP'):
            limit=self.get('fac') if n=='FOR_LIMIT' else self.get('alt')
            step=Expr('1') if n=='FOR_LIMIT' else self.get('fac')
            temp=f'T_LIMIT_{r["address"]:04X}';step_temp=f'T_STEP_{r["address"]:04X}'
            self.emit(temp+' = '+limit.text+(' : '+step_temp+' = '+step.text if n=='FOR_LIMIT_STEP' else ''),args=[limit,step],warnings=['Capture the runtime limit/step before the later FOR-variable initialization.'])
            self.limit=Expr(temp,limit.deps,limit.warnings)
            self.step=Expr('1') if n=='FOR_LIMIT' else Expr(step_temp,step.deps,step.warnings)
            self.regs.pop('fac',None);self.regs.pop('arg',None);return True
        if n=='FOR_ENTER':
            start=self.get('fac');limit=self.limit or Expr('<?>');step=self.step or Expr('<?>')
            self.emit('FOR '+self.var(r)+' = '+start.text+' TO '+limit.text+' STEP '+step.text,args=[start,limit,step],reset=True);return True
        if n.startswith('FOR_FLOAT_') or n=='FOR_INTEGER_UNIT_STEP':
            name=self.var(r);limit=self.get('iv') if n=='FOR_INTEGER_UNIT_STEP' else self.get('alt')
            step=self.get('fac') if n=='FOR_FLOAT_EXPLICIT_STEP' else Expr('1')
            self.emit(f'FOR {name} = {name} TO {limit.text} STEP {step.text}',args=[limit,step],warnings=['Initial assignment shown separately.'],reset=True);return True
        if self.family=='blitz' and n=='DIM_INTERNAL':
            dims=[self.get('stack') for _ in range(r['dimensions'])][::-1]
            self.arrays[r['descriptorOffset']]=(r['variable'],r['dimensions'])
            self.emit('DIM '+r['variable']+'('+', '.join(e.text for e in dims)+')',args=dims,reset=True);return True
        if self.family=='blitz' and n in ('FOR_SETUP','FOR_SETUP_STEP'):
            name=self.get('stack');step=self.get('stack') if n=='FOR_SETUP_STEP' else Expr('1');limit=self.get('stack')
            self.emit(f'FOR {name.text} = {name.text} TO {limit.text} STEP {step.text}',args=[name,limit,step],warnings=['Initial assignment shown separately.'],reset=True);return True
        if self.family=='blitz' and n in ('NEXT','NEXT_UNNAMED'):
            name=self.get('stack') if n=='NEXT' else Expr('')
            self.emit('NEXT '+name.text,args=[name],reset=True);return True
        if self.family=='blitz' and n=='SYS':
            address=self.get('stack');b=bytes.fromhex(r['bytes'])[1:-1]
            from formats import module
            tail=module('dtl').basic_text(b,self.tokens)
            self.emit('SYS '+address.text+tail,args=[address],warnings=['Native callee may alter state/control.'],reset=True);self.wipe(io=True);return True
        if self.family=='blitz' and r['address'] in self.blitz_leaf_definitions:
            d=self.blitz_leaf_definitions[r['address']]
            self.emit(f'DEF {d["name"]}({d["parameterName"]}); body {self.label(d["bodyEntry"])}; continuation {self.label(d["continuation"])}',
                      'structural',warnings=['Deferred numeric leaf body: skipped when the declaration executes.  F_'+str(d['descriptor'])+' is a synthetic descriptor name.',
                      'On a call, the argument is stored in the five-byte numeric formal; its old bytes are restored on normal FN return.  Runtime conversion/rounding still applies.'],reset=True)
            return True
        if self.family=='blitz' and r['address'] in self.blitz_leaf_returns:
            d=self.blitz_leaf_returns[r['address']];e=self.get('stack')
            self.emit('RETURN '+d['name']+' = '+e.text,args=[e],
                      warnings=['Deferred body result, not a declaration-time computation.  Normal return restores '+d['parameterName']+'; arithmetic/error semantics remain those of '+self.identity_family+'.'],reset=True)
            return True
        if n in ('CALL_FUNCTION','FN_CALL'):
            src='stack' if self.family=='blitz' else 'fac';e=self.get(src);descriptor=v.get('value',r.get('value'))
            d=self.blitz_leaf_calls.get(descriptor) if self.family=='blitz' else None
            warning=('Descriptor-indirect function; static numeric-leaf candidate '+self.label(d['header'])+
                     ' binds '+d['parameterName']+'.  Runtime binding is unproved; call state invalidation is retained.') if d else 'Descriptor-indirect function; original declaration not reconstructed.'
            self.function('FN F_'+str(descriptor),[e],src,True,warning);return True
        if n in ('DEFINE_FUNCTION','DEF_FN'):
            self.emit('REM '+n+' '+str({k:x for k,x in {**r,**v}.items() if k in ('descriptor','body','skip','bodyTarget','skipTarget','functionDescriptorOffset','parameterDescriptorOffset')}),'partial',reset=True);return True
        if n in ('RETURN_FUNCTION','FN_RETURN'):
            e=self.get('stack' if self.family=='blitz' else 'fac');self.emit('REM FN RESULT '+e.text,'partial',args=[e],reset=True);return True
        if n=='BIND_FUNCTION_ARGUMENT':
            name=self.var(r);self.set('fac',self.expr(name));self.emit('REM FN PARAMETER '+name,'partial');return True
        if n=='RESTORE_FUNCTION_ARGUMENT':self.emit('REM restore FN parameter','structural');return True
        if n in ('BASIC_FLOAT_ARGUMENT_SLOT','BASIC_INTEGER_ARGUMENT_SLOT','BASIC_STRING_ARGUMENT_SLOT'):
            e=self.get('ss' if 'STRING' in n else 'iv' if 'INTEGER' in n else 'fac')
            self.emit('REM BASIC_SLOT_'+str(v['value'])+' = '+e.text,'structural',args=[e],warnings=['Temporary interpreter argument, not an original user-variable name.']);return True
        if n=='ENTER_TOKENIZED_BASIC':
            from formats import module
            text=module('dtl').basic_text(bytes.fromhex(v['payloadHex']),self.tokens)
            self.emit(text,'embedded',warnings=['Temporary BASIC argument slots may appear; no original-variable substitution claimed.'],reset=True);self.wipe(io=True);return True
        if n in ('INCREMENT_INTEGER','DECREMENT_INTEGER'):
            e=self.get('iv');self.set('iv',self.expr('('+e.text+(' + 1)' if n=='INCREMENT_INTEGER' else ' - 1)'),[e],['16-bit wrap']));return True
        return False

    def capture_dtl_value(self,r):
        if r['address'] not in self.capture_sites or not self.stack['stack']:return
        e=self.stack['stack'][-1]
        if e.producer!=r['address'] or e.stable or '<?>' in e.text or any('unknown' in w for w in e.warnings):return
        # Capture at the producer, before ALL later argument evaluation. Moving
        # this assignment to the call would re-read mutable values too late.
        tmp=f'T_VALUE_{r["address"]:04X}'
        self.emit(tmp+' = '+self.shown(e),args=[e],warnings=['Synthetic value captured at its original evaluation site, before a later DTL FN call.'],
                  statement=Statement('temporary',(display.node(e),),target=tmp))
        self.stack['stack'][-1]=Expr(tmp,e.deps,e.warnings,stable=True,producer=e.producer,display_node=display.temporary(tmp))

    def dtl_false_test_value(self,r):
        join=self.false_test_joins.get(r['address'])
        if not join or join['status']!='candidate':return None
        stack=self.stack['stack'];e=stack[0] if len(stack)==1 else None
        if (e is None or e.reference or '<?>' in e.text or
                any('unknown' in w for w in e.warnings) or join['predecessor'] not in e.deps):
            join['status']='unresolved'
            join['reasons'].append('Fallthrough lacks one complete value from the immediate producer; no stack facts retained.')
            return None
        # Only one newly evaluated predicate survives; every other fact is killed.
        # Opaque native/interpreter producers do not qualify merely by returning a temp.
        dependencies=[row for row in self.rows if row['address'] in e.deps]
        if any(row.get('region')!=r.get('region') or row.get('grammar')=='basic_island' or
               row['mnemonic']=='SYS' or row.get('operands',{}).get('operation')=='USR' or
               row.get('control') not in ('fallthrough','descriptor-indirect-call') for row in dependencies):
            join['status']='unresolved';join['reasons'].append('Predicate has unsupported or opaque producer effects/control.')
            return None
        self.false_test_candidates.add(r['address'])
        if r['address'] in self.false_test_sites:
            join['status']='recovered';return e
        return None

    def run(self):
        previous_region=None
        for r in self.rows:
            if self.for_zero_ready and r['address']!=self.for_zero_ready['forAddress']:self.for_zero_ready=None
            region=r.get('region','main')
            if (r['address'] in self.targets or previous_region is not None and region!=previous_region):
                predicate=self.dtl_false_test_value(r) if self.family=='dtl' and region==previous_region else None
                if r['address'] in self.false_test_sites and predicate is None:
                    raise ValueError('DTL false-test replay lost its proved fallthrough value')
                if predicate is None and self.pending:self.emit('REM UNRESOLVED expression at control/region boundary','unresolved')
                self.wipe(io=r['address'] in self.targets)
                if predicate is not None:self.stack['stack']=[predicate]
            previous_region=region;self.current=r;self.pending.append(r)
            if not self.special(r):
                rule=self.rules.get(r['mnemonic'])
                if rule:self.standard(r,rule)
                else:self.barrier(r['mnemonic']+' semantics not yet modeled')
            if self.family=='dtl':self.capture_dtl_value(r)
        if self.pending:self.emit('REM UNRESOLVED trailing expression','unresolved')
        result={'schema':'pcode-basic-reconstruction-v1','family':self.identity_family,'sourceSupplied':False,'mapsUsed':False,
                'groups':self.groups,'symbols':self.symbols,'instructionCount':len(self.rows),
                'coverage':{kind:sum(len(g['instructions']) for g in self.groups if g['kind']==kind) for kind in ('inferred','embedded','structural','partial','unresolved')},
                'limitations':['BASIC-like reading aid, not runnable or original BASIC; L_/V_/T_ identifiers are synthetic.',
                               'Runtime integer overflow, conversion, error, string and I/O semantics can differ from stock BASIC.',
                               'No source lines/maps consulted. Full low-level listing is preserved; listing does not establish reachability.',
                               'Unknown effects, joins and calls lose symbolic facts rather than borrowing supplied-source information.']}
        if self.array_index is not None:result['arrayIndex']=self.array_index
        if self.fn_index is not None:result['functionIndex']=self.fn_index
        if self.false_test_index is not None:result['falseTestJoins']=self.false_test_index
        if self.family=='dtl':
            from dtl_for import annotate_initializers
            result['forIndex']=annotate_initializers(self.report,self.groups,self.targets,self.for_zero_recoveries)
            from dtl_navigation import build_sys_index
            result['nativeCallIndex']=build_sys_index(self.sys_sites)
        return result


def lift(family,report,*,readable=True):
    if report.get('source') or report.get('lineMap') or report.get('sourceText'):
        raise ValueError('source/map annotated reports are not reconstruction inputs')
    if any(set(r)&{'sourceText','sourceLine','sourceLineText','annotations'} for r in report['instructions']):
        raise ValueError('source/annotation fields are not reconstruction inputs')
    if family=='speedcompiler':
        from speedcompiler_lift import lift_speedcompiler
        return lift_speedcompiler(report)
    lifter=Lifter(family,report,readable=readable);result=lifter.run()
    if family=='dtl' and lifter.fn_capture_candidates:
        # Discover affected reaching producers without relaxing the call barrier,
        # then replay with selective evaluation-site captures. Unknowns and joins
        # still kill facts; other VM families do not inherit DTL's stack ABI.
        lifter=Lifter(family,report,lifter.fn_capture_candidates,readable=readable);result=lifter.run()
    if family=='dtl' and lifter.false_test_candidates:
        # Discovery does not relax joins. Replay only those with complete local
        # predicates, forwarding every proved incoming false edge in the reading
        # view. Captures precede this gate so mutable reads are never reread late.
        lifter=Lifter(family,report,lifter.capture_sites,lifter.false_test_candidates,readable=readable)
        result=lifter.run()
    if family=='dtl':
        from dtl_xrefs import analyze_xrefs
        result['staticIndex']=analyze_xrefs(report,result['arrayIndex'])
        from dtl_navigation import annotate_runtime, analyze_variable_sys
        result['runtimeIndex']=annotate_runtime(report,result['groups'],profile('dtl'))
        result['nativeVariableIndex']=analyze_variable_sys(report,result['nativeCallIndex'])
    data=[]
    for row in report.get('dataRecords',[]):
        if row['kind']=='terminator':continue
        payload=bytes.fromhex(row['bytes'])[1:]
        text=payload.decode('ascii') if all(32<=b<127 for b in payload) else None
        if text is not None and re.fullmatch(r'[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:E[+-]?[0-9]+)?',text):item=text
        elif text is not None and '"' not in text:item='"'+text+'"'
        else:item=None
        data.append({'address':row['address'],'bytes':row['bytes'],'text':'DATA '+item if item is not None else None,
                     'kind':'inferred' if item is not None else 'opaque','caveat':'Normalized retained DATA item; original quoting/line grouping may be lost.'})
    if 'dataRegion' in report:
        row=report['dataRegion'];raw=bytes.fromhex(row['bytes']);text=None
        lead=0x83 if family=='dtl' else 0x2c
        if raw and raw[0]==lead and raw.endswith(bytes(3)) and b'\0' not in raw[:-3]:
            encoded=raw[:-3] if family=='dtl' else bytes([0x83,32])+raw[1:-3]
            from formats import module
            text=module('dtl').basic_text(encoded,profile('dtl')['basicTokens'])
        data.append({**row,'text':text,'kind':'embedded' if text is not None else 'opaque',
                     'caveat':'Strict observed DATA-text envelope only; original DATA line numbers/grouping are unavailable.'})
    result['retainedData']=data
    if family=='dtl' and readable:
        from dtl_reading import build_reading
        result['readingView']=build_reading(report,result,lifter.reading_statements,lifter.reading_arguments,lifter.targets,lifter.tokens)
    return result


def render(report):
    out=['; SOURCE-BLIND INPUT CONTRACT: binary + compiler profiles only; no source or line map.',
         '; Best-effort BASIC-like reconstruction. Synthetic labels/names; not runnable original BASIC.']
    out.append('; FAMILY '+report['family'])
    for r in report.get('loadedRegions',[]):
        out.append(f'; REGION ${r["start"]:04X}-${r["end"]:04X} (end exclusive): '+r['name'])
    for d in report.get('retainedData',[]):
        out.append(f'\n; DATA REGION ${d["address"]:04X} [{d["kind"]}]: '+(d['text'] or 'opaque bytes'))
        out.append('; '+d['bytes']+' — '+d['caveat'])
    if 'arrayIndex' in report:
        from dtl_arrays import render_arrays
        out.extend(render_arrays(report['arrayIndex']))
    if 'functionIndex' in report:
        from dtl_functions import render_index
        out.extend(render_index(report['functionIndex']))
    if 'falseTestJoins' in report:
        from dtl_branches import render_false_tests
        out.extend(render_false_tests(report['falseTestJoins']))
    if 'staticIndex' in report:
        from dtl_xrefs import render_xrefs
        out.extend(render_xrefs(report['staticIndex']))
    if 'forIndex' in report:
        from dtl_for import render_for
        out.extend(render_for(report['forIndex']))
    if 'runtimeIndex' in report:
        from dtl_navigation import render_runtime
        out.extend(render_runtime(report['runtimeIndex']))
    if 'nativeCallIndex' in report:
        from dtl_navigation import render_sys
        out.extend(render_sys(report['nativeCallIndex']))
    if 'nativeVariableIndex' in report:
        from dtl_navigation import render_variable_sys
        out.extend(render_variable_sys(report['nativeVariableIndex']))
    for g in report['groups']:
        first=g['instructions'][0]['address'] if g['instructions'] else 0
        out.append(f'\nL_{first:04X}: [{g["kind"]}] {g["text"]}')
        for w in g['warnings']:out.append('; '+w)
        for r in g['instructions']:
            fields=('value','signedValue','exact','variable','name','target','targets','body','skip','descriptor','descriptorOffset','dimensions','arrayBase','operation','payloadHex','stringHex','text','tail')
            values={k:v for k,v in {**r,**r.get('operands',{})}.items() if k in fields and v is not None}
            operand=' '+json.dumps(values,ensure_ascii=True,sort_keys=True) if values else ''
            out.append(f'  ${r["address"]:04X}  {r["bytes"]:<35} {r["mnemonic"]}'+operand)
    out.append('\n; COVERAGE '+json.dumps(report['coverage'],sort_keys=True))
    out.extend('; '+s for s in report['limitations'])
    return '\n'.join(out)+'\n'
