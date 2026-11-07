#!/usr/bin/env python3

from pathlib import Path
import sys
import unittest

TOOLS = Path(__file__).resolve().parents[1] / 'tools'
sys.path.insert(0, str(TOOLS))

from dataflow6502 import (  # noqa: E402
    ARCH_RESOURCES, CallSummary, DataflowError, FlowEdge,
    analyze_known_state, analyze_liveness, decode_pcs, instruction_effects,
)


def memory_with(address, payload):
    memory = bytearray(65536)
    memory[address:address + len(payload)] = payload
    return bytes(memory)


class Dataflow6502Tests(unittest.TestCase):
    def test_decode_and_index_effects(self):
        memory = memory_with(0x8000, bytes.fromhex('bd 00 20'))  # LDA $2000,X
        instruction = decode_pcs(memory, [0x8000])[0]
        effects = instruction_effects(instruction)
        self.assertEqual(instruction.operand, 0x2000)
        self.assertIn('X', effects.reads)
        self.assertIn('M:*', effects.reads)
        self.assertTrue({'A', 'F:N', 'F:Z'} <= effects.writes)

    def test_implicit_sequential_flow_is_analyzed(self):
        memory = memory_with(0x7FF0, bytes.fromhex('a9 01 8d 00 20 60'))
        instructions = decode_pcs(memory, (0x7FF0, 0x7FF2, 0x7FF5))
        result = analyze_liveness(instructions, (), terminal_live={'X'})
        self.assertIn('A', result.live_out[0x7FF0])
        self.assertNotIn('A', result.live_out[0x7FF2])
        self.assertIn('X', result.live_in[0x7FF0])

    def test_liveness_proves_y_dead_after_call_when_overwritten(self):
        # JSR $9000; STA $2000; LDY #0; RTS
        memory = memory_with(0x8000, bytes.fromhex('20 00 90 8d 00 20 a0 00 60'))
        instructions = decode_pcs(memory, (0x8000, 0x8003, 0x8006, 0x8008))
        edges = (
            FlowEdge(0x8000, 0x9000, 'call'), FlowEdge(0x8000, 0x8003, 'fallthrough'),
            FlowEdge(0x8003, 0x8006, 'fallthrough'), FlowEdge(0x8006, 0x8008, 'fallthrough'),
        )
        summaries = {0x9000: CallSummary({'A'}, {'A', 'Y', 'F:N', 'F:Z'})}
        result = analyze_liveness(
            instructions, edges, terminal_live=ARCH_RESOURCES,
            call_summaries=summaries,
        )
        self.assertIn('A', result.live_out[0x8000])
        self.assertNotIn('Y', result.live_out[0x8000])
        self.assertIn('X', result.live_out[0x8000])

    def test_call_summary_can_make_y_live(self):
        # JSR $9000; JSR $9100; RTS
        memory = memory_with(0x8000, bytes.fromhex('20 00 90 20 00 91 60'))
        instructions = decode_pcs(memory, (0x8000, 0x8003, 0x8006))
        edges = (
            FlowEdge(0x8000, 0x9000, 'call'), FlowEdge(0x8000, 0x8003, 'fallthrough'),
            FlowEdge(0x8003, 0x9100, 'call'), FlowEdge(0x8003, 0x8006, 'fallthrough'),
        )
        summaries = {
            0x9000: CallSummary({'A'}, {'A', 'Y'}),
            0x9100: CallSummary({'Y'}, {'A'}),
        }
        result = analyze_liveness(instructions, edges, call_summaries=summaries)
        self.assertIn('Y', result.live_out[0x8000])

    def test_branch_fallthrough_refines_opposite_branch(self):
        # CMP #1; BNE elsewhere; BEQ elsewhere
        memory = memory_with(0x8000, bytes.fromhex('c9 01 d0 04 f0 04'))
        instructions = decode_pcs(memory, (0x8000, 0x8002, 0x8004))
        edges = (
            FlowEdge(0x8000, 0x8002, 'fallthrough'),
            FlowEdge(0x8002, 0x8008, 'branch'),
            FlowEdge(0x8002, 0x8004, 'fallthrough'),
            FlowEdge(0x8004, 0x800A, 'branch'),
        )
        result = analyze_known_state(instructions, edges, entries={0x8000: {}})
        self.assertEqual(result.facts_in(0x8004)['F:Z'], 1)
        self.assertEqual(result.branch_outcomes[0x8004], 'always-taken')

    def test_known_binary_adc_and_carry_branch(self):
        # CLD; CLC; LDA #1; ADC #2; BCC
        memory = memory_with(0x8100, bytes.fromhex('d8 18 a9 01 69 02 90 00'))
        pcs = (0x8100, 0x8101, 0x8102, 0x8104, 0x8106)
        instructions = decode_pcs(memory, pcs)
        edges = tuple(FlowEdge(left, right, 'fallthrough') for left, right in zip(pcs, pcs[1:]))
        result = analyze_known_state(instructions, edges, entries={0x8100: {}})
        self.assertEqual(result.facts_out(0x8104)['A'], 3)
        self.assertEqual(result.facts_in(0x8106)['F:C'], 0)
        self.assertEqual(result.branch_outcomes[0x8106], 'always-taken')

    def test_join_keeps_only_agreeing_facts(self):
        # Unknown BNE splits to LDX #1 / LDX #2, then joins at NOP.
        memory = memory_with(0x8200, bytes.fromhex('d0 04 a2 01 4c 08 82 a2 02 ea'))
        instructions = decode_pcs(memory, (0x8200, 0x8202, 0x8204, 0x8207, 0x8209))
        edges = (
            FlowEdge(0x8200, 0x8207, 'branch'), FlowEdge(0x8200, 0x8202, 'fallthrough'),
            FlowEdge(0x8202, 0x8204, 'fallthrough'), FlowEdge(0x8204, 0x8209, 'jump'),
            FlowEdge(0x8207, 0x8209, 'fallthrough'),
        )
        result = analyze_known_state(instructions, edges, entries={0x8200: {}})
        self.assertNotIn('X', result.facts_in(0x8209))
        self.assertEqual(result.facts_in(0x8209)['F:Z'], 0)
        self.assertEqual(result.facts_in(0x8209)['F:N'], 0)

    def test_unknown_resources_and_bad_decode_refuse(self):
        with self.assertRaises(DataflowError):
            CallSummary({'Q'}, set())
        bad = bytearray(65536); bad[0x8000] = 0x03
        with self.assertRaises(DataflowError):
            decode_pcs(bytes(bad), [0x8000])


if __name__ == '__main__':
    unittest.main()
