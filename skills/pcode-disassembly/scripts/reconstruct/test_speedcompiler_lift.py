"""Synthetic tests of Speedcompiler's distinct state and ownership contracts."""
import unittest
from symbolic import lift,render


def row(name,**operands):return dict(mnemonic=name,operands=operands,bytes='00',size=1)
def program(*rows):
 r={'instructions':[{'address':0x2000+i,**x} for i,x in enumerate(rows)],'typedDataRecords':[]}
 return lift('speedcompiler',r)
def text(r):return '\n'.join(x['text'] for x in r['groups'])
def const(value):return row('CONST_BYTE',value=value)
def fconst(value):
 # Small integer constants can enter float through the actual conversion path.
 return [const(value),row('INTEGER_TO_FLOAT')]
def store():return row('STORE_FLOAT',slot=0,storage=0x3000)


class SpeedLiftTests(unittest.TestCase):
 def test_noncommutative_float_order(self):
  for op,symbol in [('FLOAT_SUBTRACT','-'),('FLOAT_DIVIDE','/'),('FLOAT_POWER','^')]:
   r=program(*fconst(19),*fconst(4),row(op),store())
   self.assertIn('VM_ROUND(VM_I16_TO_FLOAT(19)) '+symbol+' VM_I16_TO_FLOAT(4)',text(r))
 def test_integer_width_preserved(self):
  r=program(const(255),const(3),row('INTEGER_MULTIPLY'),row('STORE_INTEGER_RESET',slot=0,lowStorage=0x810,highStorage=0x888))
  self.assertIn('VM_IMUL(255, 3)',text(r));self.assertNotIn('(255 * 3)',text(r))
 def test_float_spill_explicit(self):
  r=program(*fconst(1),*fconst(2),row('FLOAT_ADD'),*fconst(3),row('FLOAT_SUBTRACT'),store())
  self.assertIn('VM_ROUND((VM_ROUND(VM_I16_TO_FLOAT(1)) + VM_I16_TO_FLOAT(2)))',text(r))
 def test_effectful_function_once(self):
  r=program(*fconst(1),row('RND'),store());self.assertEqual(text(r).count('RND('),1)
 def test_missing_integer_is_unknown(self):
  r=program(row('INTEGER_ADD'),row('STORE_INTEGER_RESET',slot=0,lowStorage=0x810,highStorage=0x888))
  self.assertIn('<?>',text(r));self.assertNotIn('VM_IADD(0, 0)',text(r))
 def test_string_concat_order(self):
  r=program(row('CONST_STRING',payloadHex=b'LEFT'.hex()),row('CONST_STRING',payloadHex=b'RIGHT'.hex()),row('STRING_CONCAT'),row('STORE_STRING',slot=0,storage=0x3200))
  self.assertIn('("LEFT" + "RIGHT")',text(r))
 def test_clock_write_is_not_a_sample_or_a_stack_result(self):
  s=lambda:row('STORE_STRING',slot=0,storage=0x3200)
  r=program(row('TIME_STRING'),s(),row('CONST_STRING',payloadHex=b'012345'.hex()),row('SET_TIME_STRING'),s())
  self.assertEqual([g['text'] for g in r['groups']],
                   ['T_2000 = VM_TIME_STRING()','V_3200$ = T_2000','TI$ = "012345"','V_3200$ = <?>'])
  write=r['groups'][2];self.assertEqual(write['kind'],'inferred')
  self.assertEqual(write['evidenceAddresses'],[0x2002,0x2003])
  self.assertEqual([i['mnemonic'] for i in write['instructions']],['CONST_STRING','SET_TIME_STRING'])
 def test_clock_write_refuses_unproved_frame(self):
  setter=row('SET_TIME_STRING');lit=lambda s:row('CONST_STRING',payloadHex=s.hex())
  for seq in ([lit(b'12345'),setter],[lit(b'12:345'),setter],
              [row('LOAD_STRING',slot=3,storage=0x3000),setter],
              [lit(b'012345'),setter,row('GOTO',target=0x2001)],
              [lit(b'012345'),dict(setter,address=0x2010)]):
   with self.subTest(seq=seq):
    g=next(g for g in program(*seq)['groups'] if g['instructions'][-1]['mnemonic']=='SET_TIME_STRING')
    self.assertEqual(g['kind'],'unresolved');self.assertNotIn('TI$ =',g['text'])
 def test_read_integer_discards_old_depth(self):
  r=program(const(99),row('READ_INTEGER'),row('STORE_INTEGER_RESET',slot=0,lowStorage=0x810,highStorage=0x888))
  self.assertIn('I_00% = <?>',text(r));self.assertNotIn('I_00% = 99',text(r))
  self.assertTrue(any('tag-dependent' in w for g in r['groups'] for w in g['warnings']))
 def test_input_replaces_string_not_expression_push(self):
  r=program(row('CONST_STRING',payloadHex=b'OLD'.hex()),row('INPUT_NEXT'),row('STORE_STRING',slot=0,storage=0x3200))
  self.assertIn('VM_INPUT_NEXT()',text(r));self.assertIn('V_3200$ = T_2001',text(r))
 def test_conditional_false_is_zero_not_bitwise_not(self):
  r=program(const(7),row('IF_INTEGER_FALSE',target=0x2002),row('END'))
  self.assertIn('IF 7 = 0 THEN GOTO L_2002',text(r));self.assertNotIn('IF NOT',text(r))
 def test_unmodeled_known_instruction_kills_facts(self):
  r=program(const(4),row('SYS'),row('STORE_INTEGER_RESET',slot=0,lowStorage=0x810,highStorage=0x888))
  self.assertIn('UNRESOLVED',text(r));self.assertIn('I_00% = <?>',text(r))
 def test_typed_data_no_source_substitution(self):
  r=lift('speedcompiler',{'instructions':[], 'typedDataRecords':[{'address':0x3000,'bytes':'01 02 2d 32','kind':'string','operands':{'payloadHex':'2d32'}}]})
  self.assertIn('DATA_STRING "-2"',render(r));self.assertFalse(r['sourceSupplied'])
 def test_instruction_ownership_and_aliases(self):
  rows=[*fconst(2),store(),*fconst(3),row('STORE_FLOAT',slot=1,storage=0x3000),row('END')]
  r=program(*rows);self.assertEqual([i['address'] for g in r['groups'] for i in g['instructions']],list(range(0x2000,0x2000+len(rows))))
  self.assertEqual(len(r['symbols']),1)
 def test_typed_print_keeps_signedness_and_no_newline(self):
  for op,helper in [('PRINT_INTEGER','VM_I16'),('PRINT_UNSIGNED','VM_U16')]:
   r=program(row('CONST_WORD',value=65535),row(op));self.assertIn('PRINT '+helper+'(65535);',text(r))
 def test_string_print_newline_is_separate(self):
  r=program(row('CONST_STRING',payloadHex='4142'),row('PRINT_STRING'),row('PRINT_NEWLINE'))
  self.assertEqual(text(r),'PRINT "AB";\nPRINT')
 def test_channel_loss_is_not_a_file_selection(self):
  r=program(row('GOTO',target=0x2001),row('PRINT_LITERAL',payloadHex='41'),row('SELECT_OUTPUT'),row('PRINT_NEWLINE'),
            const(3),row('SELECT_OUTPUT'),row('PRINT_NEWLINE'),row('RESTORE_CHANNELS'),row('PRINT_NEWLINE'))
  prints=[g for g in r['groups'] if g['text'].startswith('PRINT')]
  self.assertEqual([g['text'] for g in prints],['PRINT "A";','PRINT#<?>,','PRINT#3,','PRINT'])
  self.assertEqual(prints[0]['kind'],'partial');self.assertTrue(any('current output channel is unknown' in w for w in prints[0]['warnings']))
  self.assertFalse(prints[-1]['warnings'])
 def test_file_selector_is_a_value_at_selection_not_a_live_variable(self):
  slot=dict(slot=0,lowStorage=0x810,highStorage=0x888)
  var=row('LOAD_INTEGER',**slot);assign=row('STORE_INTEGER_RESET',**slot)
  r=program(const(3),assign,var,row('SELECT_OUTPUT'),const(4),assign,row('PRINT_NEWLINE'))
  self.assertIn('CMD I_00%',text(r));self.assertEqual(r['groups'][-1]['text'],'PRINT#<?>,')
  r=program(var,row('INPUT_FILE'),const(4),assign,row('INPUT_NEXT'))
  self.assertIn('VM_INPUT_FILE(I_00%)',text(r));self.assertIn('VM_INPUT_NEXT(<?>)',text(r))
 def test_immediate_and_split_slot_byte_writes(self):
  r=program(row('CONST_WORD',value=0xabcd),row('CONST_WORD',value=0x1234),row('POKE'),
            row('WRITE_BYTE',address=0x6789,value=0xcd),const(47),row('CONST_ZERO'),row('POKE'))
  self.assertEqual(text(r),'POKE 43981, 52\nPOKE 26505, 205\nPOKE 47, 0')
  self.assertEqual([g['evidenceAddresses'] for g in r['groups']],
                   [[0x2000,0x2001,0x2002],[0x2003],[0x2004,0x2005,0x2006]])
 def test_split_slot_write_rejects_unproved_depth_or_operands(self):
  for prefix in ([row('INTEGER_RESERVE')],[row('GET_STRING')],[const(99)],
                 [row('WRITE_BYTE',address=0x1a,value=3)]):
   r=program(*prefix,const(17),const(9),row('POKE'))
   self.assertEqual(r['groups'][-1]['kind'],'unresolved');self.assertNotIn('POKE 17, 9',text(r))
  for entry in range(0x2000,0x2003):
   r=program(const(17),const(9),row('POKE'),row('GOTO',target=entry))
   self.assertNotIn('POKE 17, 9',text(r));self.assertTrue(any(g['kind']=='unresolved' for g in r['groups']))
 def test_peeks_sample_in_order_once_and_add_truncates_only_at_write(self):
  # Read twice from the same potentially effectful address. The two samples
  # stay distinct; the first is the destination, the second feeds the value.
  r=program(const(47),row('PEEK'),const(47),row('PEEK'),row('CONST_WORD',value=65535),
            row('INTEGER_ADD'),row('POKE'))
  self.assertEqual(text(r),'T_2001 = PEEK(47)\nT_2003 = PEEK(47)\nPOKE T_2001, VM_LOW_BYTE(VM_IADD(T_2003, 65535))')
  self.assertEqual(r['groups'][-1]['evidenceAddresses'],list(range(0x2000,0x2007)))
  self.assertEqual([[i['address'] for i in g['instructions']] for g in r['groups']],
                   [[0x2000,0x2001],[0x2002,0x2003],[0x2004,0x2005,0x2006]])
 def test_sum_is_word_at_peek_and_poke_address_not_low_byte(self):
  base=[row('CONST_WORD',value=65534),const(1),row('INTEGER_ADD')]
  r=program(*base,row('PEEK'),row('CONST_WORD',value=0x0180),row('POKE'),
            *base,const(254),row('POKE'))
  self.assertEqual(text(r),'T_2003 = PEEK(VM_U16(VM_IADD(65534, 1)))\nPOKE T_2003, 128\nPOKE VM_U16(VM_IADD(65534, 1)), 254')
 def test_computed_write_refuses_bypassed_operands_and_unknown_depth(self):
  body=[const(77),const(40),row('PEEK'),const(9),row('INTEGER_ADD'),row('POKE')]
  for i in range(len(body)):
   r=program(*body,row('GOTO',target=0x2000+i))
   self.assertFalse(any(g['text'].startswith('POKE ') for g in r['groups']))
  for prefix in ([const(1)],[row('INTEGER_ADD')],[row('PEEK')],[row('SYS')],
                 [row('CLEAR_RANGE',start=0x19,end=0x30)],
                 [row('CLEAR_RANGE',start=0xff01,end=0x10030)]):
   self.assertEqual(program(*prefix,*body)['groups'][-1]['kind'],'unresolved')
  r=program(const(77),const(40),row('PEEK'),row('WRITE_BYTE',address=0x2c,value=9),row('POKE'))
  self.assertEqual(r['groups'][-1]['kind'],'unresolved')
 def test_clear_restore_at_empty_depth_and_reset_after_refusal(self):
  body=[const(83),const(49),row('PEEK'),row('POKE')]
  r=program(row('CLEAR_RANGE',start=0x3000,end=0x3100),row('RESTORE_DATA',value=0x2345),
            *body,row('INTEGER_RESERVE'),*body,*body)
  writes=[g for g in r['groups'] if g['instructions'][-1]['mnemonic']=='POKE']
  self.assertEqual([g['kind'] for g in writes],['inferred','unresolved','inferred'])
  self.assertEqual([writes[i]['text'] for i in (0,2)],['POKE 83, T_2004','POKE 83, T_200D'])
 def test_wait_keeps_word_address_and_both_low_bytes(self):
  r=program(row('CONST_WORD',value=0xff80),row('CONST_WORD',value=0xfd01),
            row('CONST_WORD',value=0xfe02),row('WAIT_BITS'),const(1),const(0),const(0),row('WAIT_BITS'))
  self.assertEqual(text(r),'WAIT 65408, 1, 2\nWAIT 1, 0, 0')
  self.assertEqual(r['groups'][0]['evidenceAddresses'],list(range(0x2000,0x2004)))
 def test_wait_preserves_prior_samples_not_a_one_time_poll(self):
  r=program(const(49),row('PEEK'),const(49),row('PEEK'),row('CONST_WORD',value=257),
            row('INTEGER_ADD'),const(0),row('WAIT_BITS'))
  self.assertEqual(text(r),'T_2001 = PEEK(49)\nT_2003 = PEEK(49)\nWAIT T_2001, VM_LOW_BYTE(VM_IADD(T_2003, 257)), 0')
  self.assertEqual(r['groups'][-1]['evidenceAddresses'],list(range(0x2000,0x2008)))
  self.assertEqual([i['address'] for g in r['groups'] for i in g['instructions']],list(range(0x2000,0x2008)))
 def test_wait_refuses_bypassed_clobbered_and_wrong_depth(self):
  body=[const(41),const(2),const(1),row('WAIT_BITS')]
  for offset in range(len(body)):
   r=program(*body,row('GOTO',target=0x2000+offset));self.assertFalse(any(g['text'].startswith('WAIT ') for g in r['groups']))
  for seq in ([const(41),const(2),row('WAIT_BITS')],[const(99),*body],
              [row('SYS'),*body],[*body[:3],row('WRITE_BYTE',address=0x2d,value=9),row('WAIT_BITS')]):
   groups=program(*seq,*body)['groups']
   self.assertEqual(groups[-2]['kind'],'unresolved')
   self.assertEqual(groups[-1]['text'],'WAIT 41, 2, 1')
 def test_close_uses_logical_file_low_byte_and_does_not_select_output(self):
  r=program(row('CONST_WORD',value=0x0107),row('CLOSE_FILE'),row('PRINT_NEWLINE'))
  self.assertEqual(text(r),'CLOSE 7\nPRINT');self.assertEqual(r['groups'][0]['evidenceAddresses'],[0x2000,0x2001])
  self.assertTrue(any('current output channel is unknown' in w for w in r['groups'][1]['warnings']))
 def test_close_reset_survives_operand_refusal_not_an_alternate_entry(self):
  for prefix in ([],[const(1),const(2)],[row('SYS'),const(1)]):
   r=program(*prefix,row('CLOSE_FILE'),const(9),row('CLOSE_FILE'),const(18),const(42),row('POKE'))
   self.assertEqual(r['groups'][-3]['kind'],'unresolved')
   self.assertEqual([g['text'] for g in r['groups'][-2:]],['CLOSE 9','POKE 18, 42'])
  r=program(const(9),row('CLOSE_FILE'),const(18),const(42),row('POKE'),row('GOTO',target=0x2002))
  self.assertEqual(r['groups'][0]['text'],'CLOSE 9');self.assertEqual(r['groups'][1]['kind'],'unresolved')
 def test_compare_true_branch_resets_depth_but_forwards_no_value(self):
  # Unknown input depth/predicate. Only the new fall-through push supplies n.
  seq=[row('SYS'),row('INTEGER_COMPARE',value=2),row('IF_INTEGER_TRUE',target=0x2005),
       const(17),row('CLOSE_FILE'),const(19),row('CLOSE_FILE')]
  groups=program(*seq)['groups'];self.assertIn('<?>',groups[-3]['text'])
  self.assertEqual(groups[-2]['text'],'CLOSE 17');self.assertEqual(groups[-2]['evidenceAddresses'],[0x2003,0x2004])
  self.assertEqual(groups[-1]['kind'],'unresolved')  # Target entry is not seeded.
  r=program(const(4),const(4),row('INTEGER_COMPARE',value=2),
            row('IF_INTEGER_TRUE',target=0x2005),row('CLOSE_FILE'),row('END'))
  self.assertEqual(r['groups'][-2]['kind'],'unresolved')  # No post-reset push.
 def test_compare_branch_proof_refuses_other_entries_or_untraced_dispatch(self):
  tail=[row('IF_INTEGER_TRUE',target=0x2000),const(17),row('CLOSE_FILE')]
  for entry in (0x2001,0x2002,0x2003):  # Bypass compare, reset, or literal.
   r=program(row('INTEGER_COMPARE',value=2),*tail,row('GOTO',target=entry))
   self.assertNotIn('CLOSE 17',text(r))
  r=program(row('SYS'),*tail);self.assertEqual(r['groups'][-1]['kind'],'unresolved')
 def test_counted_open_uses_reaching_name_and_ordered_lfs_bytes(self):
  def reading(*,prefix='4e',suffix='2c50',slot=5,storage=0x3600,reset='CLOSE_FILE',target=None,swap=False):
   rows=[row(reset),row('CONST_STRING',payloadHex=prefix),row('STORE_STRING',slot=5,storage=storage),
         const(11),const(7),const(9),row('LOAD_STRING',slot=slot,storage=storage),
         row('CONST_STRING',payloadHex=suffix),row('STRING_CONCAT'),row('OPEN_FILE')]
   if swap:rows[4],rows[5]=rows[5],rows[4]
   if target is not None:rows.append(row('GOTO',target=0x2000+target))
   report={'instructions':[{'address':0x2000+i,**r} for i,r in enumerate(rows)],'typedDataRecords':[],
           'layout':{'imageEnd':0x2200,'storageEnd':0x4000}}
   return next(g for g in lift('speedcompiler',report)['groups'] if g['instructions'][-1]['mnemonic']=='OPEN_FILE')
  g=reading();self.assertEqual(g['text'],'OPEN 11, 7, 9, "N,P"');self.assertEqual(g['kind'],'inferred')
  self.assertEqual(g['evidenceAddresses'],list(range(0x2000,0x200a)))
  self.assertEqual(reading(swap=True)['text'],'OPEN 11, 9, 7, "N,P"')
  self.assertEqual(reading(prefix='00',suffix='51')['text'],'OPEN 11, 7, 9, CHR$(0)+"Q"')
  for kw in [{'target':i} for i in range(1,10)]+[{'slot':6},{'storage':0x1c00},{'storage':0x3fff},
                                                  {'prefix':'41'*254},{'reset':'RESTORE_CHANNELS'}]:
   with self.subTest(kw=kw):self.assertEqual(reading(**kw)['kind'],'unresolved')
 def scalar_sys(self,*,storage=0x3456,extra=(),tail=(),entry=None,reset='WAIT_BITS'):
  rows=[const(68),const(3),const(1),row(reset),*extra,row('LOAD_FLOAT',slot=7,storage=storage),
        row('FLOAT_TO_INTEGER'),row('SYS'),*tail]
  if entry is not None:rows.append(row('ON_GOTO',targets=[0x2100+entry]))
  return lift('speedcompiler',{'instructions':[{'address':0x2100+i,**r} for i,r in enumerate(rows)],
              'layout':{'imageEnd':0x3000,'storageEnd':0x4000},'typedDataRecords':[]})['groups']
 def test_scalar_sys_is_an_unsigned_converted_value_not_a_storage_address(self):
  for storage in (0x3456,0x3ffb):
   g=self.scalar_sys(storage=storage)[-1]
   self.assertEqual(g['text'],f'SYS VM_FLOAT_TO_ADDR16(V_{storage:04X})')
   self.assertEqual(g['kind'],'partial');self.assertEqual(g['evidenceAddresses'],list(range(0x2102,0x2107)))
   self.assertEqual([r['address'] for r in g['instructions']],[0x2104,0x2105,0x2106])
 def test_scalar_sys_refuses_bypass_nonbottom_clobber_and_unsafe_descriptor(self):
  for kw in ([{'entry':i} for i in range(3,7)]+[{'extra':[const(99)]},{'reset':'INTEGER_RESERVE'},
             {'extra':[row('WRITE_BYTE',address=0x1a,value=7)]},{'storage':0x002b},{'storage':0x3ffc}]):
   with self.subTest(kw=kw):
    g=next(g for g in self.scalar_sys(**kw) if g['instructions'][-1]['mnemonic']=='SYS')
    self.assertEqual(g['kind'],'unresolved');self.assertNotIn('V_',g['text'])
 def test_sys_is_a_value_depth_and_channel_barrier(self):
  tail=[row('STORE_INTEGER_RESET',slot=1,lowStorage=0x811,highStorage=0x889),row('PRINT_NEWLINE'),row('INPUT_NEXT')]
  groups=self.scalar_sys(tail=tail)
  self.assertIn('<?>',groups[-3]['text']);self.assertIn('unknown',groups[-2]['warnings'][0])
  self.assertIn('VM_INPUT_NEXT(<?>)',groups[-1]['text'])
  groups=self.scalar_sys(tail=[const(17),row('CLOSE_FILE')]);self.assertEqual(groups[-1]['kind'],'unresolved')
  # A refused SYS also kills selectors that were known before the call.
  groups=program(const(3),row('INPUT_FILE'),const(8),row('SELECT_OUTPUT'),row('SYS'),*tail)['groups']
  self.assertEqual(groups[-2]['text'],'PRINT');self.assertIn('unknown',groups[-2]['warnings'][0])
  self.assertIn('VM_INPUT_NEXT(<?>)',groups[-1]['text'])
 def test_poke_word_remains_distinct(self):
  r=program(const(17),const(9),row('POKE_WORD'));self.assertEqual(r['groups'][-1]['kind'],'unresolved')
 def test_immediate_output_workspace_write_invalidates_selector(self):
  r=program(const(3),row('SELECT_OUTPUT'),row('WRITE_BYTE',address=0x13,value=7),row('PRINT_NEWLINE'))
  self.assertEqual(r['groups'][-1]['text'],'PRINT');self.assertIn('unknown',r['groups'][-1]['warnings'][0])
 def test_unknown_stack_aliasing_bounded(self):
  r=program(*[const(i) for i in range(14)],row('STORE_INTEGER_RESET',slot=0,lowStorage=0x810,highStorage=0x888))
  self.assertIn('I_00% = <?>',text(r))

if __name__=='__main__':unittest.main()
