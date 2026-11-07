#!/usr/bin/env python3
"""Contract and taxonomy tests for differential routine equivalence."""

from pathlib import Path
import sys
import unittest

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

import cpu6502  # noqa: E402
from equivalence import (  # noqa: E402
    EntryEventRule,
    EquivalenceConfigurationError,
    MemoryPolicy,
    MemoryRule,
    ObservationContract,
    compare_runs,
)
from routine_runner import InitialState, RoutineSpec, build_memory, run_routine  # noqa: E402


class EquivalenceTests(unittest.TestCase):
    def run_code(self, code, *, start=0x8000, exit_pc=0x9000, flags=cpu6502.FU):
        memory = build_memory([(start, bytes(code))])
        return run_routine(
            RoutineSpec(start, {exit_pc}, max_instructions=100),
            InitialState(memory, flags=flags),
        )

    def contract(self, *rules, left_exit=0x9000, right_exit=0x9000,
                 registers=frozenset(("a", "x", "y", "sp")), flags_mask=0xFF,
                 reject_unspecified_writes=True, event_rules=()):
        return ObservationContract(
            registers=registers,
            flags_mask=flags_mask,
            exit_pairs={(left_exit, right_exit)},
            memory_rules=rules,
            entry_event_rules=event_rules,
            reject_unspecified_writes=reject_unspecified_writes,
        )

    def test_reordered_border_background_writes_are_final_state_equivalent(self):
        left = self.run_code([
            0xA9, 0x00, 0x8D, 0x20, 0xD0, 0x8D, 0x21, 0xD0,
            0x4C, 0x00, 0x90,
        ])
        right = self.run_code([
            0xA9, 0x00, 0x8D, 0x21, 0xD0, 0x8D, 0x20, 0xD0,
            0x4C, 0x00, 0x90,
        ])
        rule = MemoryRule("vic-colors", 0xD020, 0xD020, 2, MemoryPolicy.FINAL_STATE)
        result = compare_runs(left, right, self.contract(rule))
        self.assertTrue(result.equivalent, result.differences)

    def test_same_color_writes_fail_ordered_event_policy(self):
        left = self.run_code([
            0xA9, 0x00, 0x8D, 0x20, 0xD0, 0x8D, 0x21, 0xD0,
            0x4C, 0x00, 0x90,
        ])
        right = self.run_code([
            0xA9, 0x00, 0x8D, 0x21, 0xD0, 0x8D, 0x20, 0xD0,
            0x4C, 0x00, 0x90,
        ])
        rule = MemoryRule("raster-events", 0xD020, 0xD020, 2, MemoryPolicy.ORDERED_EVENTS)
        result = compare_runs(left, right, self.contract(rule))
        self.assertFalse(result.equivalent)
        self.assertEqual(result.differences[0].category, "memory_ordered_events")

    def test_forward_and_reverse_screen_clear_are_equivalent(self):
        left = self.run_code([
            0xA9, 0x20, 0x8D, 0x00, 0x04, 0x8D, 0x01, 0x04,
            0x4C, 0x00, 0x90,
        ])
        right = self.run_code([
            0xA9, 0x20, 0x8D, 0x01, 0x04, 0x8D, 0x00, 0x04,
            0x4C, 0x00, 0x90,
        ])
        rule = MemoryRule("screen", 0x0400, 0x0400, 2, MemoryPolicy.FINAL_STATE)
        self.assertTrue(compare_runs(left, right, self.contract(rule)).equivalent)

    def test_corresponding_relocated_ranges_compare_by_relative_offset(self):
        left = self.run_code([
            0xA9, 0x55, 0x8D, 0x00, 0x20, 0x4C, 0x00, 0x90,
        ])
        right = self.run_code([
            0xA9, 0x55, 0x8D, 0x00, 0x30, 0x4C, 0x00, 0xA0,
        ], exit_pc=0xA000)
        rule = MemoryRule("output", 0x2000, 0x3000, 1, MemoryPolicy.FINAL_STATE)
        result = compare_runs(
            left, right,
            self.contract(rule, left_exit=0x9000, right_exit=0xA000),
        )
        self.assertTrue(result.equivalent, result.differences)

    def test_ignored_scratch_permits_different_writes(self):
        left = self.run_code([
            0xA9, 0x11, 0x85, 0x10, 0xA9, 0x00, 0x4C, 0x00, 0x90,
        ])
        right = self.run_code([
            0xA9, 0x22, 0x85, 0x10, 0xA9, 0x00, 0x4C, 0x00, 0x90,
        ])
        rule = MemoryRule("private-scratch", 0x0010, 0x0010, 1, MemoryPolicy.IGNORED)
        self.assertTrue(compare_runs(left, right, self.contract(rule)).equivalent)

    def test_unspecified_writes_are_rejected_by_default(self):
        left = self.run_code([
            0xA9, 0x01, 0x8D, 0x00, 0x20, 0x4C, 0x00, 0x90,
        ])
        right = self.run_code([
            0xA9, 0x01, 0x8D, 0x00, 0x20, 0x4C, 0x00, 0x90,
        ])
        result = compare_runs(left, right, self.contract())
        self.assertFalse(result.equivalent)
        self.assertEqual(
            {difference.category for difference in result.differences},
            {"left_unspecified_writes", "right_unspecified_writes"},
        )

    def test_register_and_flag_observation_is_selectable(self):
        left = self.run_code([0xA9, 0x01, 0x38, 0x4C, 0x00, 0x90])  # SEC
        right = self.run_code([0xA9, 0x02, 0x18, 0x4C, 0x00, 0x90])  # CLC

        strict = compare_runs(left, right, self.contract())
        self.assertFalse(strict.equivalent)
        self.assertEqual(
            {difference.category for difference in strict.differences},
            {"register", "flags"},
        )

        relaxed = compare_runs(
            left, right,
            self.contract(registers=frozenset(("x", "y", "sp")), flags_mask=0),
        )
        self.assertTrue(relaxed.equivalent)

    def test_ordered_pc_entry_events_compare_selected_registers(self):
        def run(values):
            code = []
            for value in values:
                code.extend((0xA9, value, 0x20, 0x00, 0x90))
            code.extend((0x4C, 0x00, 0xA0))
            memory = build_memory([
                (0x8000, bytes(code)),
                (0x9000, bytes([0x60])),
            ])
            return run_routine(
                RoutineSpec(0x8000, {0xA000}, max_instructions=30,
                            observed_pcs={0x9000}),
                InitialState(memory),
            )

        rule = EntryEventRule(
            "character-stream", 0x9000, 0x9000,
            registers={"a"}, flags_mask=0,
        )
        same = compare_runs(
            run((0x11, 0x22)), run((0x11, 0x22)),
            self.contract(left_exit=0xA000, right_exit=0xA000,
                          reject_unspecified_writes=False,
                          event_rules=(rule,)),
        )
        self.assertTrue(same.equivalent, same.differences)

        changed = compare_runs(
            run((0x11, 0x22)), run((0x11, 0x23)),
            self.contract(left_exit=0xA000, right_exit=0xA000,
                          registers=frozenset(("x", "y", "sp")),
                          flags_mask=0, reject_unspecified_writes=False,
                          event_rules=(rule,)),
        )
        self.assertFalse(changed.equivalent)
        self.assertEqual(changed.differences[0].category, "entry_events")
        self.assertEqual(changed.differences[0].rule, "character-stream")

    def test_contract_rejects_overlap_and_missing_exit_pairs(self):
        rule1 = MemoryRule("one", 0x2000, 0x3000, 2, MemoryPolicy.FINAL_STATE)
        rule2 = MemoryRule("two", 0x2001, 0x4000, 2, MemoryPolicy.IGNORED)
        with self.assertRaises(EquivalenceConfigurationError):
            ObservationContract(exit_pairs={(0x9000, 0x9000)}, memory_rules=(rule1, rule2))
        with self.assertRaises(EquivalenceConfigurationError):
            ObservationContract()


if __name__ == "__main__":
    unittest.main()
