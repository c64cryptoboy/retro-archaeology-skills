#!/usr/bin/env python3
"""Tests for bounded, hardware-free routine execution."""

from pathlib import Path
import sys
import unittest

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

import cpu6502  # noqa: E402
from routine_runner import (  # noqa: E402
    InitialState,
    RoutineConfigurationError,
    RoutineSpec,
    Termination,
    build_memory,
    run_routine,
)


class MemoryTrackingTests(unittest.TestCase):
    def test_core_tracks_reads_writes_and_ordered_old_new_values(self):
        cpu = cpu6502.Cpu6502Emulator()
        cpu.inject_bytes(0x8000, [
            0xA9, 0x42,       # LDA #$42
            0x8D, 0x00, 0x20, # STA $2000
            0xAD, 0x00, 0x20, # LDA $2000
        ])
        cpu.init_cpu(0x8000)
        cpu.clear_memory_usage()
        for _ in range(3):
            self.assertTrue(cpu.runcpu())

        self.assertIn(0x8000, cpu.read_addresses())
        self.assertIn(0x8007, cpu.read_addresses())
        self.assertIn(0x2000, cpu.read_addresses())
        self.assertEqual(cpu.written_addresses(), {0x2000})
        self.assertEqual(cpu.write_trace, [(0x2000, 0x00, 0x42)])

    def test_usage_clear_removes_setup_evidence(self):
        cpu = cpu6502.Cpu6502Emulator()
        cpu.set_mem(0x1234, 0x56)
        self.assertEqual(cpu.written_addresses(), {0x1234})
        cpu.clear_memory_usage()
        self.assertEqual(cpu.read_addresses(), set())
        self.assertEqual(cpu.written_addresses(), set())
        self.assertEqual(cpu.write_trace, [])


class RoutineRunnerTests(unittest.TestCase):
    def test_explicit_exit_and_complete_snapshot(self):
        memory = build_memory([
            (0x8000, bytes([
                0xA9, 0x42,       # LDA #$42
                0x8D, 0x00, 0x20, # STA $2000
                0x4C, 0x00, 0x90, # JMP $9000
            ])),
        ])
        initial = InitialState(memory, x=3, y=4, sp=0xF0, flags=cpu6502.FU | cpu6502.FC)
        spec = RoutineSpec(0x8000, {0x9000}, max_instructions=10)

        result = run_routine(spec, initial)

        self.assertEqual(result.termination, Termination.EXIT_PC)
        self.assertTrue(result.reached_legal_exit)
        self.assertEqual(result.instructions, 3)
        self.assertEqual(result.final.pc, 0x9000)
        self.assertEqual(result.final.a, 0x42)
        self.assertEqual(result.final.x, 3)
        self.assertEqual(result.final.y, 4)
        self.assertEqual(result.final.sp, 0xF0)
        self.assertEqual(result.final.memory[0x2000], 0x42)
        self.assertEqual(result.access.written_addresses, frozenset({0x2000}))
        self.assertEqual(result.access.write_trace, ((0x2000, 0, 0x42),))
        self.assertIsNone(result.exception_type)

    def test_explicit_pc_entry_events_capture_ordered_cpu_state(self):
        memory = build_memory([
            (0x8000, bytes([
                0xA9, 0x11, 0x20, 0x00, 0x90,
                0xA9, 0x22, 0x20, 0x00, 0x90,
                0x4C, 0x00, 0xA0,
            ])),
            (0x9000, bytes([0x60])),
        ])
        result = run_routine(
            RoutineSpec(
                0x8000, {0xA000}, max_instructions=20,
                observed_pcs={0x9000},
            ),
            InitialState(memory),
        )
        self.assertEqual(result.termination, Termination.EXIT_PC)
        self.assertEqual([event.pc for event in result.entry_events],
                         [0x9000, 0x9000])
        self.assertEqual([event.a for event in result.entry_events], [0x11, 0x22])
        self.assertEqual([event.instructions for event in result.entry_events], [2, 5])
        self.assertEqual([event.sp for event in result.entry_events], [0xFD, 0xFD])

    def test_instruction_limit_stops_infinite_loop(self):
        memory = build_memory([(0x8000, bytes([0x4C, 0x00, 0x80]))])
        result = run_routine(
            RoutineSpec(0x8000, {0x9000}, max_instructions=5),
            InitialState(memory),
        )
        self.assertEqual(result.termination, Termination.INSTRUCTION_LIMIT)
        self.assertEqual(result.instructions, 5)
        self.assertEqual(result.final.pc, 0x8000)

    def test_cpu_stop_is_distinct_from_legal_exit(self):
        memory = build_memory([(0x8000, bytes([0x00]))])  # BRK
        result = run_routine(
            RoutineSpec(0x8000, {0x9000}, max_instructions=5),
            InitialState(memory),
        )
        self.assertEqual(result.termination, Termination.CPU_STOP)
        self.assertFalse(result.reached_legal_exit)
        self.assertEqual(result.instructions, 1)

    def test_exception_returns_bounded_diagnostic(self):
        memory = build_memory([(0x8000, bytes([0x03]))])
        result = run_routine(
            RoutineSpec(0x8000, {0x9000}, max_instructions=5),
            InitialState(memory),
        )
        self.assertEqual(result.termination, Termination.EXCEPTION)
        self.assertEqual(result.exception_type, "Cpu6502NotImplemented")
        self.assertIn("unimplemented opcode", result.exception_message)

    def test_configuration_and_segments_are_validated(self):
        with self.assertRaises(RoutineConfigurationError):
            InitialState(bytes(10))
        with self.assertRaises(RoutineConfigurationError):
            RoutineSpec(0x8000, set())
        with self.assertRaises(RoutineConfigurationError):
            RoutineSpec(0x8000, {0x9000}, max_instructions=0)
        with self.assertRaises(RoutineConfigurationError):
            RoutineSpec(0x8000, {0x9000}, observed_pcs={0x10000})
        with self.assertRaises(RoutineConfigurationError):
            build_memory([(0x1000, b"ab"), (0x1001, b"cd")])
        with self.assertRaises(RoutineConfigurationError):
            build_memory([(0xFFFF, b"ab")])


if __name__ == "__main__":
    unittest.main()
