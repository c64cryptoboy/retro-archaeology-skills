"""Authored idiomatic-view contracts; no title payload or target execution."""
from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import expression_display as d
from dtl_reading import build_reading, spaced_basic, projection_reason
from formats import module, profile
from reading_projection import Statement, expressions, render_reading, render_statement
from symbolic import lift, render
from test_dtl_for import instruction, literal, store, loop, place, fixture
from test_reconstruct import program, row

TOKENS = profile('dtl')['basicTokens']


def fn(name='RND'):
    selector = {'RND':7, 'PEEK':14, 'INT':1, 'USR':6}[name]
    return instruction('FUNCTION', bytes((0xb8, selector)).hex(),
                       {'operation':name,'selector':selector}, grammar='selector')


def load(name='RD', offset=2):
    return instruction('LOAD_REAL_SCALAR', bytes((0x90, offset)).hex(),
                       {'name':name,'value':offset}, grammar='var8')


def binary(name, opcode):
    return instruction(name, bytes((opcode,)).hex())


def basic(data):
    return instruction('BASIC', (b'\0'+data).hex(),
                       {'text':module('dtl').basic_text(data,TOKENS)},
                       grammar='basic_island',control='interpreter-fallthrough')


def reading(result):
    return '\n'.join(g['text'] for g in result['readingView']['groups'])


def manual(rows, statements, spans):
    placed=place(rows)
    groups=[]
    for statement, (start,end) in zip(statements,spans):
        groups.append(dict(text=render_statement(statement),kind='inferred',warnings=[],
                           instructions=placed['instructions'][start:end],evidenceAddresses=[]))
    result=dict(groups=groups,forIndex={'loops':[]})
    before=deepcopy(result)
    view=build_reading(placed,result,statements,[expressions(s) for s in statements],set(),TOKENS)
    assert result==before
    return view


class DTLReadingTests(unittest.TestCase):
    def test_immediate_random_assignment_and_old_groups_exact(self):
        report=place([load(),fn(),store(44,'A',short=True)])
        before=deepcopy(report); new=lift('dtl',report)
        self.assertEqual(reading(new),'A = RND(RD)')
        self.assertEqual([g['text'] for g in new['groups']],['T_4002 = RND(RD)','A = T_4002'])
        self.assertIn('T_4002 = RND(RD)',render(new))
        self.assertIn('A = RND(RD)',render_reading(new))
        self.assertEqual(new,lift('dtl',report));self.assertEqual(report,before)

    def test_peek_direct_comparison_retains_branch_target(self):
        condition=instruction('IF_SKIP_FALSE','4f02',grammar='relative8',control='conditional')
        condition['targets']=[0x4100]
        report=place([literal(2),fn('PEEK'),literal(2),binary('COMPARE_GT',0x2a),condition])
        result=lift('dtl',report)
        self.assertEqual(reading(result),'IF PEEK(2) <= 2 THEN GOTO L_4100')
        self.assertEqual(result['readingView']['groups'][0]['evaluationOrder'],[0x4001,0x4004,0x4005])

    def test_nested_arithmetic_not_reassociated(self):
        report=place([literal(1),load(),fn(),literal(2),binary('MULTIPLY',3),fn('INT'),
                      binary('ADD',1),store(44,'A',short=True)])
        result=lift('dtl',report)
        self.assertEqual(reading(result),'A = 1 + INT(RND(RD) * 2)')
        self.assertEqual(reading(result).count('RND('),1)

    def test_reverse_random_order_keeps_first_capture(self):
        rows=[literal(1),fn(),literal(1),fn(),binary('SUBTRACT',2),store(2,'A',short=True)]
        statements=[Statement('temporary',(d.call('RND',[d.leaf('1')],origin=0x4001),),target='T1',eligible=True),
                    Statement('temporary',(d.call('RND',[d.leaf('1')],origin=0x4004),),target='T2',eligible=True),
                    Statement('assignment',(d.binary('-',d.temporary('T2'),d.temporary('T1'),origin=0x4006),),
                              target='A',origin=0x4007)]
        view=manual(rows,statements,[(0,2),(2,4),(4,6)])
        self.assertEqual([g['text'] for g in view['groups']],['T1 = RND(1)','A = RND(1) - T1'])
        self.assertIn('order',view['refusals'][0]['reason'])

    def test_repeated_use_never_duplicates_call(self):
        rows=[literal(1),fn(),binary('ADD',1),store(2,'A',short=True)]
        statements=[Statement('temporary',(d.call('RND',[d.leaf('1')],origin=0x4001),),target='T1',eligible=True),
                    Statement('assignment',(d.binary('+',d.temporary('T1'),d.temporary('T1'),origin=0x4003),),
                              target='A',origin=0x4004)]
        view=manual(rows,statements,[(0,2),(2,4)])
        self.assertEqual(len(view['groups']),2)
        self.assertIn('repeated',view['refusals'][0]['reason'])

    def test_mutable_read_cannot_move_before_random(self):
        # A + RND() spelling would re-read A before the already-completed RND.
        rows=[literal(1),fn(),load('A'),binary('ADD',1),store(9,'Z',short=True)]
        statements=[Statement('temporary',(d.call('RND',[d.leaf('1')],origin=0x4001),),target='T1',eligible=True),
                    Statement('assignment',(d.binary('+',d.leaf('A',origin=0x4003),d.temporary('T1'),origin=0x4005),),
                              target='Z',origin=0x4006)]
        view=manual(rows,statements,[(0,2),(2,5)])
        self.assertEqual(len(view['groups']),2)
        self.assertIn('order',view['refusals'][0]['reason'])

    def test_pure_operation_error_timing_is_also_ordered(self):
        rows=place([literal(1),literal(0),binary('DIVIDE',4),literal(1),fn(),binary('ADD',1),store(2,'A',short=True)])['instructions']
        division=d.binary('/',d.leaf('1'),d.leaf('0'),origin=0x4002)
        random=d.call('RND',[d.leaf('1')],origin=0x4004)
        reordered=Statement('assignment',(d.binary('+',random,division,origin=0x4006),),target='A',origin=0x4007)
        self.assertIn('order',projection_reason(rows,reordered,set()))

    def test_opaque_call_is_not_inlined(self):
        result=lift('dtl',place([literal(1),fn('USR'),store(2,'A',short=True)]))
        self.assertIn('T_4001 = USR(1)',reading(result))
        self.assertEqual(result['readingView']['counts'],{})

    def test_no_cross_statement_or_write_search(self):
        report=place([literal(1),fn(),store(2,'A',short=True),literal(0),store(2,'A',short=True),
                      load('A'),store(9,'Z',short=True)])
        self.assertEqual(reading(lift('dtl',report)),'A = RND(1)\nA = 0\nZ = A')

    def test_entries_regions_and_gaps_refuse(self):
        for mutation in ('entry','region','gap','operand-entry'):
            with self.subTest(mutation=mutation):
                report=place([literal(1),fn(),store(2,'A',short=True)])
                if mutation=='entry':report['instructions'][-1]['targets']=[report['instructions'][1]['address']]
                if mutation=='operand-entry':report['instructions'][-1]['targets']=[report['instructions'][1]['address']+1]
                if mutation=='region':report['instructions'][-1]['region']='init'
                if mutation=='gap':report['instructions'][-1]['address']+=1
                self.assertNotEqual(reading(lift('dtl',report)),'A = RND(1)')

    def test_for_initializer_and_default_step(self):
        report=fixture(literal(7),initial=1)
        result=lift('dtl',report)
        self.assertIn('FOR Q = 1 TO 7\nNEXT',reading(result))
        self.assertNotIn('STEP 1',reading(result))
        self.assertEqual(result['groups'][0]['text'],'Q = 1')
        self.assertEqual(result['groups'][1]['text'],'FOR Q = Q TO 7 STEP 1')
        self.assertEqual(result['readingView']['counts']['fuse-for-initializer'],1)

    def test_loop_variable_in_limit_is_read_after_initializer(self):
        # The loop bound reads the initialized Q, not its earlier value.
        report=fixture(literal(2),load('Q',2),binary('ADD',1),offset=2,initial=1,short=True)
        result=lift('dtl',report)
        self.assertIn('FOR Q = 1 TO 2 + Q',reading(result))
        item=result['readingView']['groups'][0]
        self.assertEqual(item['evaluationOrder'],[0x4001,0x4004,0x4006,0x4007])

    def test_explicit_step_one_retains_evaluation(self):
        result=lift('dtl',fixture(literal(7),literal(1),step=True,initial=1))
        self.assertIn('FOR Q = 1 TO 7 STEP 1',reading(result))
        self.assertNotIn('omit-default-step',result['readingView']['counts'])

    def test_integer_loop_and_named_next_retained(self):
        report=fixture(literal(5),initial=1,kind='integer',name='I%')
        report['instructions'][-2]=instruction('NEXT_NAMED','47018a',{'value':394,'name':'I%'},grammar='var16',control='loop-runtime')
        place(report['instructions'],scalars=report['scalars'])
        result=lift('dtl',report)
        self.assertIn('FOR I% = 1 TO 5',reading(result))
        self.assertIn('NEXT I%',reading(result))

    def test_ambiguous_loop_identity_and_entry_do_not_fuse(self):
        for ambiguity in (True,False):
            report=fixture(literal(7),initial=1)
            if ambiguity:report['scalars'].append(deepcopy(report['scalars'][0]))
            else:report['instructions'][-1]['targets']=[report['instructions'][2]['address']]
            result=lift('dtl',report)
            self.assertNotIn('fuse-for-initializer',result['readingView']['counts'])

    def test_incomplete_value_not_fused(self):
        result=lift('dtl',fixture(initial=3))
        self.assertNotIn('fuse-for-initializer',result['readingView']['counts'])
        self.assertIn('<?>',reading(result))

    def test_keyword_spacing_no_print_separator_insertion(self):
        data=b'\x99"TYPE THE "B$" WORD"'
        result=lift('dtl',place([basic(data)]))
        self.assertEqual(reading(result),'PRINT "TYPE THE "B$" WORD"')
        self.assertEqual(result['groups'][0]['text'],'PRINT"TYPE THE "B$" WORD"')
        self.assertNotIn(';',reading(result))
        self.assertFalse(result['readingView']['printSeparatorInsertion'])

    def test_read_input_open_and_existing_spacing(self):
        for data,wanted in [(b'\x87A$','READ A$'),(b'\x85D$','INPUT D$'),
                            (b'\x9f15,8,15,"I0"','OPEN 15,8,15,"I0"'),
                            (b'\x99 E$','PRINT E$')]:
            self.assertEqual(spaced_basic(data,TOKENS),wanted)

    def test_quotes_data_rem_and_existing_separators(self):
        for data in (b'\x8fPRINTA$;X',b'\x83WORD, 1,"A;B"',b'\x99 "PRINTA$;":\x8fFOO'):
            # First PRINT is already spaced; DATA/REM and quoted bodies exact.
            self.assertEqual(spaced_basic(data,TOKENS),module('dtl').basic_text(data,TOKENS))
        self.assertEqual(spaced_basic(b'\x99A$;B$,C$;',TOKENS),'PRINT A$;B$,C$;')
        self.assertEqual(spaced_basic(b'\x99"\x99"',TOKENS),'PRINT "{$99}"')

    def test_missing_or_mismatched_island_extent_refuses_spacing(self):
        for length in (None,1):
            with self.subTest(length=length):
                report=place([basic(b'\x99E$')])
                if length is None:report['instructions'][0].pop('length')
                else:report['instructions'][0]['length']=length
                before=deepcopy(report)
                result=lift('dtl',report)
                self.assertEqual(reading(result),'PRINTE$')
                self.assertEqual(result['readingView']['groups'][0]['actions'],[])
                self.assertEqual(report,before)

    def test_native_sys_tail_is_never_keyword_formatted(self):
        tail=',"PRINTE$;"'
        sysrow=instruction('SYS','513a',{'tail':tail,'returnCaveat':'native return unknown'},grammar='sys_basic_tail',control='native-call-dynamic-return')
        result=lift('dtl',place([literal(1),sysrow]))
        self.assertEqual(reading(result),'SYS 1'+tail)

    def test_foreign_families_have_no_reading_projection(self):
        other=program('petspeed',row('PUSH_CONST_REAL',1),row('STORE_REAL_VAR',2))
        self.assertNotIn('readingView',other)
        with self.assertRaisesRegex(ValueError,'No evidenced'):
            render_reading(other)

    def test_cli_basic_output_uses_portable_renderer(self):
        import reconstruct as frontend
        result=lift('dtl',place([literal(1),fn(),store(2,'A',short=True)]))
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/'input.prg'; source.write_bytes(b'fixture')
            output=Path(directory)/'reading.txt'
            with patch.object(frontend,'reconstruct',return_value=result), \
                 patch('sys.argv',['reconstruct.py',str(source),'--basic-output',str(output)]), \
                 redirect_stdout(io.StringIO()):
                frontend.main()
            self.assertEqual(output.read_text(),render_reading(result))
            self.assertEqual(source.read_bytes(),b'fixture')

    def test_cli_basic_output_is_exclusive(self):
        import reconstruct as frontend
        result=lift('dtl',place([literal(1),fn(),store(2,'A',short=True)]))
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/'input.prg'; source.write_bytes(b'fixture')
            output=Path(directory)/'reading.txt'; output.write_text('preserved')
            with patch.object(frontend,'reconstruct',return_value=result), \
                 patch('sys.argv',['reconstruct.py',str(source),'--basic-output',str(output)]), \
                 redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                frontend.main()
            self.assertEqual(error.exception.code,2)
            self.assertEqual(output.read_text(),'preserved')

    def test_cli_unsupported_projection_refuses_before_any_output(self):
        import reconstruct as frontend
        other=program('petspeed',row('PUSH_CONST_REAL',1),row('STORE_REAL_VAR',2))
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/'input.prg'; source.write_bytes(b'fixture')
            output=Path(directory)/'reading.txt'; evidence=Path(directory)/'report.json'
            with patch.object(frontend,'reconstruct',return_value=other), \
                 patch('sys.argv',['reconstruct.py',str(source),'--basic-output',str(output),'--json-output',str(evidence)]), \
                 redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                frontend.main()
            self.assertEqual(error.exception.code,2)
            self.assertFalse(output.exists());self.assertFalse(evidence.exists())

    def test_explicit_legacy_mode_does_not_add_projection(self):
        report=place([literal(1),fn(),store(2,'A',short=True)])
        self.assertNotIn('readingView',lift('dtl',report,readable=False))


if __name__=='__main__':unittest.main()
