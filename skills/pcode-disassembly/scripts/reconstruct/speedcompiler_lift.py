"""Speedcompiler's split integer stack, lazy float stack and three string frames.

Presentation/provenance utilities are shared; this is not the BLITZ or FAC/ARG
execution model. Unknown native effects remain explicit barriers.
"""
from symbolic import Lifter,Expr,quoted


class SpeedLifter(Lifter):
 stacks={'ints','floats','strings'}
 def __init__(self,report):
  super().__init__('speedcompiler',report);self.float_live=False
 def wipe(self,io=False):
  super().wipe(io);self.float_live=False
 def set(self,key,e):
  if key in ('ints','floats') and len(self.stack[key])>=13:
   self.wipe(io=True)
   e=Expr('<?>',{self.current['address']},('unknown native stack aliasing beyond modeled 13 slots',))
  super().set(key,e)
 def fpush(self,e,computed=False):
  if self.float_live and self.stack['floats']:
   old=self.stack['floats'][-1]
   self.stack['floats'][-1]=self.expr('VM_ROUND('+old.text+')',[old],['Native FAC spill rounds to packed five-byte storage.'])
  self.set('floats',e);self.float_live=computed
 def spush(self,e):
  self.stack['strings']=self.stack['strings'][-2:];self.set('strings',e)
 def event(self,name,args,dst,warning=''):
  e=self.expr(name+'('+', '.join(x.text for x in args)+')',args,[warning] if warning else [])
  tmp=f'T_{self.current["address"]:04X}'
  self.emit(tmp+' = '+e.text,'partial',args=[e],warnings=['Single runtime event; synthetic value snapshot, not reconstructed source grouping.'])
  if name=='USR':self.wipe(io=True)
  e=Expr(tmp,{self.current['address']},e.warnings)
  if dst=='strings':self.spush(e)
  elif dst=='floats':self.fpush(e,True)
  else:self.set(dst,e)
 def binary(self,stack,name,computed=False,warning=''):
  right=self.get(stack);left=self.get(stack)
  e=self.expr(name+'('+left.text+', '+right.text+')',[left,right],[warning] if warning else [])
  if stack=='floats':self.set(stack,e);self.float_live=computed
  else:self.set(stack,e)
 def statement(self,name,args,warning=''):
  self.emit(name+(' '+', '.join(e.text for e in args) if args else ''),'partial' if warning else 'inferred',args=args,warnings=[warning] if warning else [])
 def symbol(self,v,integer=False,array=False):
  if integer and not array:
   name=f'I_{v["slot"]:02X}%';identity=f'integer-slot:{v["slot"]}'
   record={'name':name,'retainedName':False,'lowStorage':v['lowStorage'],'highStorage':v['highStorage']}
  else:
   address=v.get('storage',v.get('value'));name=('AR_' if array else 'V_')+f'{address:04X}'
   identity=f'memory:{address:04X}';record={'name':name,'retainedName':False,'address':address}
  self.symbols.setdefault(identity,record);return name
 def handle(self,r):
  n=r['mnemonic'];v=r['operands'];e=lambda t:self.expr(t)
  if n.startswith('NOP'):
   self.emit('REM VM '+n,'structural');return
  if n in ('CLEAR_RANGE','WRITE_BYTE','RESTORE_DATA'):
   self.emit('REM VM '+n+' '+str(v),'structural');self.wipe(io=n=='CLEAR_RANGE' and v['start']<=0x13<v['end']);return
  if n in ('CONST_ZERO','CONST_BYTE','CONST_WORD'):
   self.set('ints',e(str(0 if n=='CONST_ZERO' else v['value'])));return
  if n=='CONST_FLOAT':self.fpush(e(self.constant(r,{})));return
  if n=='CONST_STRING':self.spush(e(quoted(bytes.fromhex(v['payloadHex']))));return
  if n=='LOAD_INTEGER':self.set('ints',e(self.symbol(v,True)));return
  if n=='LOAD_FLOAT':self.fpush(e(self.symbol(v)));return
  if n=='LOAD_STRING':self.spush(e(self.symbol(v)+'$'));return
  if n in ('STORE_INTEGER','STORE_INTEGER_RESET'):
   value=self.stack['ints'][0] if self.stack['ints'] else Expr('<?>',warnings=('unknown bottom integer slot',))
   self.statement(self.symbol(v,True)+' =',[value],'16-bit split storage; signedness is operation-specific.')
   if n=='STORE_INTEGER_RESET':self.stack['ints']=[]
   return
  if n in ('STORE_FLOAT','STORE_FLOAT_ABSOLUTE'):
   value=self.get('floats');self.statement(self.symbol(v)+' =',[value],'Store to packed five-byte float; native rounding applies.');self.float_live=False;return
  if n=='STORE_STRING':
   value=self.get('strings');self.statement(self.symbol(v)+'$ =',[value],'Static string buffer; length/alias behavior differs from BASIC heap strings.');self.stack['strings']=[];return
  if n.endswith('_ELEMENT'):
   index=self.get('ints');name=self.symbol(v,array=True)
   ref=self.expr(name+'('+index.text+')',[index],['Flattened runtime index; original rank/subscripts and bounds not reconstructed.'])
   if n.startswith('LOAD'):
    if 'FLOAT' in n:self.fpush(ref)
    elif 'STRING' in n:self.spush(ref)
    else:self.set('ints',ref)
   else:
    kind='floats' if 'FLOAT' in n else 'strings' if 'STRING' in n else 'ints'
    value=self.get(kind) if kind!='ints' else self.stack['ints'][0] if self.stack['ints'] else Expr('<?>')
    self.statement(ref.text+' =',[value],'Typed element store; native width/rounding/string capacity applies.')
    self.groups[-1]['evidenceAddresses']=sorted(set(self.groups[-1]['evidenceAddresses'])|ref.deps)
    self.float_live=False if kind=='floats' else self.float_live
    if kind=='ints':self.stack['ints']=[]
   return
  ib={'INTEGER_ADD':'VM_IADD','INTEGER_SUBTRACT':'VM_ISUB','INTEGER_MULTIPLY':'VM_IMUL','INTEGER_MULTIPLY_BYTE':'VM_IMUL_BYTE','INTEGER_DIVIDE':'VM_IDIV','INTEGER_DIVIDE_UNSIGNED':'VM_UDIV','INTEGER_AND':'VM_IAND','INTEGER_OR':'VM_IOR'}
  if n in ib:self.binary('ints',ib[n],warning='16-bit VM arithmetic, not unrestricted BASIC real arithmetic.');return
  if n in ('INTEGER_NOT','INTEGER_NEGATE'):
   x=self.get('ints');self.set('ints',self.expr(('VM_INOT' if n=='INTEGER_NOT' else 'VM_INEG')+'('+x.text+')',[x]));return
  fb={'FLOAT_ADD':'+','FLOAT_SUBTRACT':'-','FLOAT_MULTIPLY':'*','FLOAT_DIVIDE':'/','FLOAT_POWER':'^'}
  if n in fb:
   right=self.get('floats');left=self.get('floats');self.set('floats',self.expr('('+left.text+' '+fb[n]+' '+right.text+')',[left,right]));self.float_live=True;return
  if n=='INTEGER_TO_FLOAT':
   x=self.get('ints');self.fpush(self.expr('VM_I16_TO_FLOAT('+x.text+')',[x]),True);return
  if n=='FLOAT_TO_INTEGER':
   x=self.get('floats');self.set('ints',self.expr('VM_FLOAT_TO_I16('+x.text+')',[x],['Runtime rounding/conversion; not assumed to be INT.']));self.float_live=False;return
  if n in ('INTEGER_COMPARE','INTEGER_COMPARE_UNSIGNED','FLOAT_COMPARE','STRING_COMPARE'):
   stack='floats' if n=='FLOAT_COMPARE' else 'strings' if n=='STRING_COMPARE' else 'ints'
   right=self.get(stack);left=self.get(stack);relation={1:'>',2:'=',3:'>=',4:'<',5:'<>',6:'<=',7:'ANY_ORDERED'}[v['value']]
   text='('+left.text+' '+relation+' '+right.text+')'
   if stack=='ints':text=('VM_UCMP' if n.endswith('UNSIGNED') else 'VM_ICMP')+'('+left.text+', '+right.text+', '+str(v['value'])+')'
   self.set('ints',self.expr(text,[left,right],['VM comparison mask and operand types retained.']));self.float_live=False;return
  if n in ('SGN','ABS','SQR','LOG','EXP','COS','SIN','TAN','ATN','INT','FLOAT_NEGATE'):
   x=self.get('floats');fn='VM_NEGATE_FLOAT' if n=='FLOAT_NEGATE' else n
   self.set('floats',self.expr(fn+'('+x.text+')',[x]));self.float_live=True;return
  if n in ('RND','USR'):
   self.event(n,[self.get('floats')],'floats','Runtime state/call effects; not assumed pure.');return
  if n=='PEEK':self.event('PEEK',[self.get('ints')],'ints');return
  if n in ('POS','TIME','TIME_STRING','STATUS','ARITHMETIC_STATUS'):
   self.event('VM_'+n,[],'strings' if n=='TIME_STRING' else 'floats' if n=='TIME' else 'ints');return
  if n in ('CHR_STRING','STR_INTEGER','STR_UNSIGNED','STR_FLOAT'):
   kind='floats' if n=='STR_FLOAT' else 'ints';x=self.get(kind)
   self.spush(self.expr({'CHR_STRING':'CHR$','STR_INTEGER':'VM_STR_I16$','STR_UNSIGNED':'VM_STR_U16$','STR_FLOAT':'STR$'}[n]+'('+x.text+')',[x]));self.float_live=False if kind=='floats' else self.float_live;return
  if n in ('LEN','ASC','VAL'):
   x=self.get('strings');new=self.expr(n+'('+x.text+')',[x],['Speedcompiler string conversion/empty-value semantics apply.'])
   if n=='VAL':self.fpush(new,True)
   else:self.set('ints',new)
   return
  if n=='STRING_CONCAT':
   right=self.get('strings');left=self.get('strings');self.spush(self.expr('('+left.text+' + '+right.text+')',[left,right],['Fixed temporary buffer, not unbounded string concatenation.']));return
  if n in ('LEFT_STRING','RIGHT_STRING','MID_STRING'):
   count=self.get('ints');args=[self.get('strings')]
   if n=='MID_STRING':args+=[self.get('ints')]
   args+=[count];fn={'LEFT_STRING':'VM_LEFT$','RIGHT_STRING':'VM_RIGHT$','MID_STRING':'VM_MID$'}[n]
   self.spush(self.expr(fn+'('+', '.join(x.text for x in args)+')',args,['Runtime byte-count/string-slice semantics retained.']));return
  if n=='PRINT_LITERAL':self.statement('PRINT' if self.output is None else 'PRINT#'+self.output+',',[e(quoted(bytes.fromhex(v['payloadHex']))+';')]);return
  if n=='PRINT_NEWLINE':self.statement('PRINT' if self.output is None else 'PRINT#'+self.output+',',[]);return
  if n in ('PRINT_FLOAT','PRINT_INTEGER','PRINT_UNSIGNED','PRINT_STRING'):
   kind='floats' if n=='PRINT_FLOAT' else 'strings' if n=='PRINT_STRING' else 'ints';value=self.get(kind)
   if n in ('PRINT_INTEGER','PRINT_UNSIGNED'):
    value=self.expr(('VM_I16' if n=='PRINT_INTEGER' else 'VM_U16')+'('+value.text+')',[value])
   value=self.expr(value.text+';',[value])
   self.statement('PRINT' if self.output is None else 'PRINT#'+self.output+',',[value],'Native formatting/channel state applies; trailing newline is a separate instruction.');self.float_live=False if kind=='floats' else self.float_live;return
  if n in ('PRINT_TAB','PRINT_SPC','PRINT_COMMA'):
   args=[] if n=='PRINT_COMMA' else [self.stack['ints'][0] if self.stack['ints'] else Expr('<?>')]
   self.statement('VM_'+n,args,'Runtime cursor/spacing behavior.');self.stack['ints']=[];return
  if n in ('GET_STRING','GET_FILE_STRING','READ_STRING','READ_INTEGER','READ_FLOAT','INPUT_PROMPT','INPUT_NEXT','INPUT_FILE'):
   args=[]
   if n=='INPUT_PROMPT':args=[e(quoted(bytes.fromhex(v['payloadHex'])))];self.input=None
   if n in ('GET_FILE_STRING','INPUT_FILE'):
    args=[self.stack['ints'][0] if self.stack['ints'] else Expr('<?>')];self.stack['ints']=[]
    if n=='INPUT_FILE':self.input=args[0].text
   if n=='INPUT_NEXT' and self.input is not None:args=[Expr(self.input)]
   # Input handlers do not share string-expression push semantics. READ_INTEGER
   # resets the integer depth; retain no unproven floating/string frames.
   if n=='READ_INTEGER':self.stack['ints']=[]
   elif n=='READ_FLOAT':self.stack['floats']=[];self.float_live=False
   else:self.stack['strings']=[]
   self.event('VM_'+n,args,'ints' if n=='READ_INTEGER' else 'floats' if n=='READ_FLOAT' else 'strings','Typed DATA or input parser/retry semantics; not normalized into stock BASIC READ/INPUT.')
   if n in ('READ_INTEGER','READ_FLOAT'):
    # The empty-string DATA path writes zero without the same depth update as
    # numeric-tag paths ($145A/$1487 versus $1423/$1432). Without a proved DATA
    # cursor/tag, claiming a uniform push would fabricate subsequent operands.
    self.groups[-1]['warnings'].append('Numeric READ post-state is tag-dependent; destination dataflow remains unknown.')
    self.wipe()
   elif n=='READ_STRING':
    self.stack['ints']=[];self.stack['floats']=[];self.float_live=False
   return
  if n in ('GOTO','GOSUB','RETURN','END'):
   self.statement(n,[] if n in ('END','RETURN') else [e(self.label(v['target']))]);self.wipe(io=True);return
  if n in ('IF_INTEGER_TRUE','IF_INTEGER_FALSE','IF_FLOAT_FALSE'):
   stack='floats' if n=='IF_FLOAT_FALSE' else 'ints';x=self.stack[stack][0] if self.stack[stack] else Expr('<?>')
   self.emit('IF '+x.text+(' <> 0' if n=='IF_INTEGER_TRUE' else ' = 0')+' THEN GOTO '+self.label(v['target']),args=[x]);self.wipe(io=True);return
  if n=='ON_GOTO':
   x=self.stack['ints'][0] if self.stack['ints'] else Expr('<?>');self.emit('ON '+x.text+' GOTO '+', '.join(self.label(t) for t in v['targets']),args=[x]);self.wipe(io=True);return
  if n.startswith('NEXT_'):
   self.emit('REM VM '+n+' slot '+str(v['slot'])+' -> '+self.label(v['target']),'partial',warnings=['Loop counter/limit/step storage and source FOR structure not yet reconstructed.']);self.wipe(io=True);return
  if n in ('CHECK_INDEX_BYTE','CHECK_INDEX_WORD','CHECK_STRING_LENGTH','CHECK_RETURN_STACK'):
   self.emit('REM VM '+n+' '+str(v),'structural');return
  if n=='SELECT_OUTPUT':
   x=self.stack['ints'][0] if self.stack['ints'] else Expr('<?>');self.output=x.text;self.statement('CMD',[x]);self.stack['ints']=[];return
  if n=='RESTORE_CHANNELS':self.output=None;self.input=None;self.emit('REM restore default channels','structural');return
  # Native I/O, stack manipulation and byte-addressed character access have
  # known widths but incomplete high-level contracts; do not guess or retain facts.
  self.barrier(n+' known encoding; semantic contract not yet modeled')
 def run(self):
  for r in self.rows:
   if r['address'] in self.targets:
    if self.pending:self.emit('REM UNRESOLVED expression at control join','unresolved')
    self.wipe(io=True)
   self.current=r;self.pending.append(r);self.handle(r)
  if self.pending:self.emit('REM UNRESOLVED trailing expression','unresolved')
  return {'schema':'pcode-basic-reconstruction-v1','family':'speedcompiler','sourceSupplied':False,'mapsUsed':False,'groups':self.groups,'symbols':self.symbols,'instructionCount':len(self.rows),'coverage':{k:sum(len(g['instructions']) for g in self.groups if g['kind']==k) for k in ('inferred','embedded','structural','partial','unresolved')},'limitations':['BASIC-like reading aid, not executable original source.','Distinct integer/float/string state model; VM_* operations preserve typed differences.','Loop/FN declarations, interactive input, file I/O and some native operations remain partial/unresolved.','Opaque scratch can retain source/compiler residue; it is not consulted by this lifter.','Known-development evidence, not independent source-blind semantic validation.']}


def lift_speedcompiler(report):
 from pathlib import Path
 from formats import sha
 lifter=SpeedLifter(report);result=lifter.run()
 result['backendSha256']=sha(Path(__file__).read_bytes())
 result['typedDataRecords']=report['typedDataRecords']
 result['retainedData']=[{'address':r['address'],'bytes':r['bytes'],'kind':'structural',
   'text':'REM VM DATA_'+r['kind'].upper()+' '+lifter.constant(r,{}),
   'caveat':'Encoded DATA type retained; a numeric-looking string is not silently changed to numeric DATA.'}
   for r in report['typedDataRecords'] if r['kind']!='terminator']
 return result
