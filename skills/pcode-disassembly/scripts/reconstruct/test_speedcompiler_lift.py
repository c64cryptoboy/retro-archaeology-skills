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
 def test_unknown_stack_aliasing_bounded(self):
  r=program(*[const(i) for i in range(14)],row('STORE_INTEGER_RESET',slot=0,lowStorage=0x810,highStorage=0x888))
  self.assertIn('I_00% = <?>',text(r))

if __name__=='__main__':unittest.main()
