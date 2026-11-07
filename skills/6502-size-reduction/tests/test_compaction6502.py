#!/usr/bin/env python3

from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / 'tools'
sys.path.insert(0, str(TOOLS))

from compaction6502 import (  # noqa: E402
    CompactionConfig, CompactionError, compact_code_region,
)
from routine_runner import InitialState, RoutineSpec, run_routine  # noqa: E402


def run(code, base, entry, *, a=0, x=0, y=0, flags=0x20, memory_values=None):
    memory = bytearray(65536)
    memory[base:base + len(code)] = code
    for address, value in (memory_values or {}).items():
        memory[address] = value
    memory[0x01FE:0x0200] = bytes((0xFF, 0x6F))
    return run_routine(
        RoutineSpec(entry, {0x7000}, 100),
        InitialState(bytes(memory), a=a, x=x, y=y, sp=0xFD, flags=flags),
    )


class Compaction6502Tests(unittest.TestCase):
    def config(self, entries=(0x8000,), **kwargs):
        values = {
            'entries': entries,
            'assert_complete_code_region': True,
            'assert_all_incoming_references_repairable': True,
            'assert_no_code_as_data': True,
            'assert_no_self_modifying_code': True,
            'assert_standard_jsr_rts': True,
        }
        values.update(kwargs)
        return CompactionConfig(**values)

    @staticmethod
    def combined_image():
        # $8000: known-state JMP path; $8005: private JSR/RTS tail call.
        return bytes.fromhex('a9 01 4c 09 80 20 0d 80 60 ea ea ea 60 60')

    def test_packs_tail_and_short_jump_and_matches_both_entries(self):
        original = self.combined_image()
        result = compact_code_region(
            original, base_address=0x8000,
            config=self.config(entries=(0x8000, 0x8005)),
        )
        self.assertEqual(result.compacted,
                         bytes.fromhex('a9 01 d0 03 4c 0b 80 ea ea ea 60 60'))
        self.assertEqual(result.byte_delta, -2)
        self.assertEqual(dict(result.relocated_entries), {0x8000: 0x8000, 0x8005: 0x8004})
        self.assertEqual({item.rule for item in result.applied}, {
            'known-flag-short-jump', 'tail-call-jsr-rts',
        })
        self.assertEqual(sum(item.nominal_cycle_delta for item in result.applied), -9)
        self.assertTrue(any(item.kind == 'tail-call-target'
                            and item.final_target == 0x800B
                            for item in result.reference_repairs))

        for original_entry, final_entry in result.relocated_entries:
            for state in ((0, 0, 0, 0x20), (0xFF, 3, 7, 0xE1)):
                left = run(original, 0x8000, original_entry,
                           a=state[0], x=state[1], y=state[2], flags=state[3])
                right = run(result.compacted, 0x8000, final_entry,
                            a=state[0], x=state[1], y=state[2], flags=state[3])
                self.assertEqual(
                    (left.final.a, left.final.x, left.final.y, left.final.sp,
                     left.final.flags, left.final.pc),
                    (right.final.a, right.final.x, right.final.y, right.final.sp,
                     right.final.flags, right.final.pc),
                )

    def test_repairs_retained_internal_jsr_when_tail_rule_disabled(self):
        original = self.combined_image()
        enabled = frozenset({
            'known-flag-short-jump', 'never-taken-branch-deletion',
            'branch-to-fallthrough-deletion',
        })
        result = compact_code_region(
            original, base_address=0x8000,
            config=self.config(entries=(0x8000, 0x8005), enabled_rules=enabled),
        )
        self.assertEqual(result.byte_delta, -1)
        repaired = next(item for item in result.reference_repairs
                        if item.kind == 'absolute-control' and item.mnemonic == 'JSR')
        self.assertEqual((repaired.original_target, repaired.final_target),
                         (0x800D, 0x800C))
        self.assertEqual(repaired.final_bytes, bytes.fromhex('20 0c 80'))

    def test_repairs_retained_relative_branch_after_inner_shrink(self):
        # Unknown BNE surrounds a known-state JMP that shrinks by one byte.
        original = bytes.fromhex('a5 10 d0 06 a9 01 4c 0a 80 60 60')
        result = compact_code_region(
            original, base_address=0x8000,
            config=self.config(entries=(0x8000, 0x8009)),
        )
        self.assertEqual(result.byte_delta, -1)
        repair = next(item for item in result.reference_repairs
                      if item.original_source == 0x8002)
        self.assertEqual((repair.original_target, repair.final_target),
                         (0x800A, 0x8009))
        self.assertEqual(repair.final_bytes, bytes.fromhex('d0 05'))

    def test_compacts_general_duplicate_idempotent_operation(self):
        original = bytes.fromhex('29 f0 29 f0 60')
        result = compact_code_region(
            original, base_address=0x8000, config=self.config()
        )
        self.assertEqual(result.compacted, bytes.fromhex('29 f0 60'))
        self.assertEqual((result.applied[0].rule, result.byte_delta,
                          result.applied[0].nominal_cycle_delta),
                         ('duplicate-idempotent-operation', -2, -2))

    def test_applies_both_dead_branch_deletion_families(self):
        cases = (
            (bytes.fromhex('a9 00 d0 01 60 60'),
             'never-taken-branch-deletion', bytes.fromhex('a9 00 60 60')),
            (bytes.fromhex('a9 01 d0 00 60'),
             'branch-to-fallthrough-deletion', bytes.fromhex('a9 01 60')),
        )
        for original, rule, expected in cases:
            with self.subTest(rule=rule):
                result = compact_code_region(
                    original, base_address=0x8000, config=self.config()
                )
                self.assertEqual(result.compacted, expected)
                self.assertEqual(result.applied[0].rule, rule)
                for flags in (0x20, 0xE1):
                    left = run(original, 0x8000, 0x8000, flags=flags)
                    right = run(expected, 0x8000, 0x8000, flags=flags)
                    self.assertEqual(
                        (left.final.a, left.final.x, left.final.y, left.final.sp,
                         left.final.flags, left.final.pc),
                        (right.final.a, right.final.x, right.final.y, right.final.sp,
                         right.final.flags, right.final.pc),
                    )

    def test_interrupt_refuses_page_cross_regression_after_packing(self):
        original = bytes.fromhex('a9 00 d0 00 d0 00 a5 10 d0 05')
        ordinary = compact_code_region(
            original, base_address=0x80F6,
            config=self.config(entries=(0x80F6,), timing_policy='ordinary'),
        )
        repair = next(item for item in ordinary.reference_repairs
                      if item.original_source == 0x80FE)
        self.assertEqual(repair.taken_page_cross_delta, 1)
        with self.assertRaisesRegex(CompactionError, 'adds a page-cross cycle'):
            compact_code_region(
                original, base_address=0x80F6,
                config=self.config(entries=(0x80F6,), timing_policy='interrupt'),
            )

    def test_compacts_available_register_compare_lowering(self):
        original = bytes.fromhex('a5 10 c9 ff f0 01 60 60')
        result = compact_code_region(
            original, base_address=0x8000,
            config=self.config(terminal_live=frozenset({'SP', 'F:N', 'F:Z'})),
        )
        self.assertEqual(result.compacted,
                         bytes.fromhex('a6 10 e8 f0 01 60 60'))
        self.assertEqual(result.applied[0].rule,
                         'compare-immediate-via-index-step')
        self.assertEqual((result.byte_delta,
                          result.applied[0].nominal_cycle_delta), (-1, 0))
        for value in range(256):
            for flags in (0x20, 0xE1):
                left = run(original, 0x8000, 0x8000, a=0x55, x=0xAA,
                           flags=flags, memory_values={0x10: value})
                right = run(result.compacted, 0x8000, 0x8000,
                            a=0x55, x=0xAA, flags=flags,
                            memory_values={0x10: value})
                self.assertEqual(left.final.sp, right.final.sp)
                self.assertEqual(left.final.pc, right.final.pc)
                self.assertEqual(left.final.flags & 0x82,
                                 right.final.flags & 0x82)

    def test_compacts_real_shape_zero_compare_select_via_rehome(self):
        original = bytes.fromhex('a9 20 c0 00 f0 02 a9 51 8d de c0 60')
        result = compact_code_region(
            original, base_address=0x8000,
            config=self.config(terminal_live=frozenset({'SP'})),
        )
        self.assertEqual(result.compacted,
                         bytes.fromhex('a2 20 98 f0 02 a2 51 8e de c0 60'))
        self.assertEqual((result.applied[0].rule, result.byte_delta,
                          result.applied[0].nominal_cycle_delta),
                         ('zero-compare-select-via-rehome', -1, 0))
        self.assertEqual(result.reference_repairs[0].kind,
                         'rehome-composed-branch')
        for value in range(256):
            for flags in (0x20, 0xE1):
                left = run(original, 0x8000, 0x8000, a=0x55, x=0xAA,
                           y=value, flags=flags)
                right = run(result.compacted, 0x8000, 0x8000,
                            a=0x55, x=0xAA, y=value, flags=flags)
                self.assertEqual(left.final.memory[0xC0DE],
                                 0x20 if value == 0 else 0x51)
                self.assertEqual(left.final.memory[0xC0DE],
                                 right.final.memory[0xC0DE])
                self.assertEqual(
                    (left.final.y, left.final.sp, left.final.pc,
                     left.final.flags & 0xFE, left.final.cycles),
                    (right.final.y, right.final.sp, right.final.pc,
                     right.final.flags & 0xFE, right.final.cycles),
                )

    def test_compacts_redundant_zero_compare_and_repairs_branch(self):
        original = bytes.fromhex('a5 10 c9 00 d0 01 60 60')
        result = compact_code_region(
            original, base_address=0x8000,
            config=self.config(terminal_live=frozenset({
                'A', 'SP', 'F:N', 'F:Z',
            })),
        )
        self.assertEqual(result.compacted,
                         bytes.fromhex('a5 10 d0 01 60 60'))
        self.assertEqual((result.applied[0].rule, result.byte_delta,
                          result.applied[0].nominal_cycle_delta),
                         ('redundant-zero-compare-after-load', -2, -2))
        repair = next(item for item in result.reference_repairs
                      if item.mnemonic == 'BNE')
        self.assertEqual((repair.original_source, repair.final_source,
                          repair.original_target, repair.final_target),
                         (0x8004, 0x8002, 0x8007, 0x8005))
        for value in range(256):
            for flags in (0x20, 0xE1):
                left = run(original, 0x8000, 0x8000, flags=flags,
                           memory_values={0x10: value})
                right = run(result.compacted, 0x8000, 0x8000,
                            flags=flags, memory_values={0x10: value})
                self.assertEqual(
                    (left.final.a, left.final.x, left.final.y, left.final.sp,
                     left.final.flags & 0xFE, left.final.pc),
                    (right.final.a, right.final.x, right.final.y,
                     right.final.sp, right.final.flags & 0xFE,
                     right.final.pc),
                )
                self.assertEqual(right.final.cycles, left.final.cycles - 2)

    def test_compacts_compare_zero_unsigned_branch_folds(self):
        cases = (
            ('c9 00 b0 01 60 60',
             '4c 04 80 60 60', 'A', -2),
            ('e0 00 90 01 60 60',
             '60 60', 'X', -4),
            ('c0 00 b0 01 60 60',
             '4c 04 80 60 60', 'Y', -2),
        )
        for original_hex, expected_hex, register, cycle_delta in cases:
            with self.subTest(original=original_hex):
                original = bytes.fromhex(original_hex)
                result = compact_code_region(
                    original, base_address=0x8000,
                    config=self.config(terminal_live=frozenset({'SP'})),
                )
                self.assertEqual(result.compacted,
                                 bytes.fromhex(expected_hex))
                self.assertEqual(result.applied[0].rule,
                                 'compare-zero-unsigned-branch-fold')
                for value in range(256):
                    state = {'a': 0x55, 'x': 0xAA, 'y': 0xCC}
                    state[register.lower()] = value
                    for flags in (0x20, 0xE1):
                        left = run(original, 0x8000, 0x8000,
                                   flags=flags, **state)
                        right = run(result.compacted, 0x8000, 0x8000,
                                    flags=flags, **state)
                        self.assertEqual(
                            (left.final.a, left.final.x, left.final.y,
                             left.final.sp, left.final.pc,
                             left.final.flags & 0x7C),
                            (right.final.a, right.final.x, right.final.y,
                             right.final.sp, right.final.pc,
                             right.final.flags & 0x7C),
                        )
                        self.assertEqual(right.final.cycles,
                                         left.final.cycles + cycle_delta)

    def test_compacts_control_only_loop_reversal(self):
        original = bytes.fromhex('a2 01 e6 20 e8 e0 11 d0 f9 60')
        result = compact_code_region(
            original, base_address=0x8000,
            config=self.config(terminal_live=frozenset({'SP'})),
        )
        self.assertEqual(result.compacted,
                         bytes.fromhex('a2 10 e6 20 ca d0 fb 60'))
        applied = result.applied[0]
        self.assertEqual((applied.rule, applied.byte_delta,
                          applied.nominal_cycle_delta),
                         ('control-only-loop-reversal', -2, -32))
        repair = next(item for item in result.reference_repairs
                      if item.kind == 'control-only-loop-back-edge')
        self.assertEqual((repair.original_source, repair.final_source,
                          repair.original_target, repair.final_target,
                          repair.final_bytes),
                         (0x8007, 0x8005, 0x8002, 0x8002,
                          bytes.fromhex('d0 fb')))
        copied_body = next(item for item in result.provenance
                           if item.original_start == 0x8002)
        self.assertEqual((copied_body.kind, copied_body.final_start),
                         ('copied-instruction', 0x8002))
        for initial_memory in (0, 1, 0x7F, 0xF8, 0xFF):
            for flags in (0x20, 0xE1):
                left = run(
                    original, 0x8000, 0x8000, flags=flags,
                    memory_values={0x20: initial_memory},
                )
                right = run(
                    result.compacted, 0x8000, 0x8000, flags=flags,
                    memory_values={0x20: initial_memory},
                )
                self.assertEqual(
                    (left.final.a, left.final.y, left.final.sp,
                     left.final.pc, left.final.flags & 0xC2,
                     left.final.memory[0x20]),
                    (right.final.a, right.final.y, right.final.sp,
                     right.final.pc, right.final.flags & 0xC2,
                     right.final.memory[0x20]),
                )
                self.assertEqual(right.final.cycles,
                                 left.final.cycles - 32)

        interrupt = compact_code_region(
            original, base_address=0x8000,
            config=self.config(
                terminal_live=frozenset({'SP'}), timing_policy='interrupt'
            ),
        )
        self.assertEqual(interrupt.compacted, result.compacted)

    def test_compacts_masked_bit_tests_with_exhaustive_values(self):
        cases = (
            ('a5 10 29 01 f0 01 60 60',
             'a5 10 4a 90 01 60 60', 0xFC, 0),
            ('a5 10 29 40 d0 01 60 60',
             'a5 10 0a 30 01 60 60', 0x7C, 0),
            ('a5 10 29 80 f0 01 60 60',
             'a5 10 10 01 60 60', 0xFD, -2),
        )
        for original_hex, expected_hex, flag_mask, cycle_delta in cases:
            with self.subTest(original=original_hex):
                original = bytes.fromhex(original_hex)
                result = compact_code_region(
                    original, base_address=0x8000,
                    config=self.config(terminal_live=frozenset({'SP'})),
                )
                self.assertEqual(result.compacted,
                                 bytes.fromhex(expected_hex))
                self.assertEqual(result.applied[0].rule,
                                 'masked-bit-test-via-shift')
                self.assertEqual(result.applied[0].nominal_cycle_delta,
                                 cycle_delta)
                self.assertEqual(result.reference_repairs[0].kind,
                                 'masked-bit-test-branch')
                for value in range(256):
                    for flags in (0x20, 0xE1):
                        left = run(original, 0x8000, 0x8000,
                                   a=0x55, flags=flags,
                                   memory_values={0x10: value})
                        right = run(result.compacted, 0x8000, 0x8000,
                                    a=0x55, flags=flags,
                                    memory_values={0x10: value})
                        self.assertEqual(
                            (left.final.x, left.final.y, left.final.sp,
                             left.final.pc, left.final.flags & flag_mask),
                            (right.final.x, right.final.y, right.final.sp,
                             right.final.pc, right.final.flags & flag_mask),
                        )
                        self.assertEqual(right.final.cycles,
                                         left.final.cycles + cycle_delta)

    def test_compacts_compare_two_via_lsr(self):
        original = bytes.fromhex('a5 10 c9 02 90 01 60 60')
        result = compact_code_region(
            original, base_address=0x8000,
            config=self.config(terminal_live=frozenset({'SP'})),
        )
        self.assertEqual(result.compacted,
                         bytes.fromhex('a5 10 4a f0 01 60 60'))
        self.assertEqual(result.applied[0].rule, 'compare-two-via-lsr')
        for value in range(256):
            left = run(original, 0x8000, 0x8000,
                       memory_values={0x10: value})
            right = run(result.compacted, 0x8000, 0x8000,
                        memory_values={0x10: value})
            self.assertEqual((left.final.sp, left.final.pc),
                             (right.final.sp, right.final.pc))

    def test_selects_best_non_overlapping_lowering(self):
        original = bytes.fromhex('a9 00 c9 ff f0 01 60 60')
        result = compact_code_region(
            original, base_address=0x8000,
            config=self.config(terminal_live=frozenset({'SP'})),
        )
        self.assertEqual(result.compacted, bytes.fromhex('a9 00 c9 ff 60 60'))
        self.assertEqual([item.rule for item in result.applied],
                         ['never-taken-branch-deletion'])
        self.assertTrue(any('better overlapping selection' in warning
                            for warning in result.warnings))

    def test_contract_assertions_and_cycle_exact_refuse(self):
        original = bytes.fromhex('60')
        checks = (
            ({}, 'every region byte'),
            ({'assert_complete_code_region': True}, 'incoming references'),
            ({'assert_complete_code_region': True,
              'assert_all_incoming_references_repairable': True}, 'not read as data'),
            ({'assert_complete_code_region': True,
              'assert_all_incoming_references_repairable': True,
              'assert_no_code_as_data': True}, 'not self-modifying'),
        )
        for supplied, message in checks:
            with self.subTest(message=message):
                with self.assertRaisesRegex(CompactionError, message):
                    compact_code_region(
                        original, base_address=0x8000,
                        config=CompactionConfig(entries=(0x8000,), **supplied),
                    )
        with self.assertRaisesRegex(CompactionError, 'cycle-exact'):
            compact_code_region(
                original, base_address=0x8000,
                config=self.config(timing_policy='cycle-exact'),
            )

    def test_uncovered_region_and_tail_without_stack_assertion(self):
        with self.assertRaisesRegex(CompactionError, 'uncovered byte'):
            compact_code_region(
                bytes.fromhex('60 ea'), base_address=0x8000,
                config=self.config(),
            )

        result = compact_code_region(
            bytes.fromhex('20 08 80 60'), base_address=0x8000,
            config=self.config(assert_standard_jsr_rts=False),
        )
        self.assertEqual(result.compacted, bytes.fromhex('20 08 80 60'))
        self.assertRegex(result.warnings[0], 'tail call skipped')

    def test_cli_accepts_declared_smc_operand_contract(self):
        original = bytes.fromhex('a9 00 d0 00 a9 42 8d de c0 60')
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            source = directory / 'in.bin'
            output = directory / 'out.bin'
            report = directory / 'report.json'
            source.write_bytes(original)
            command = [
                sys.executable, str(TOOLS / 'compact6502.py'),
                str(source), str(output), '--report', str(report),
                '--base-address', '0x8010', '--entry', '0x8010',
                '--expected-sha256', sha256(original).hexdigest(),
                '--assert-complete-code-region',
                '--assert-all-incoming-references-repairable',
                '--assert-no-code-as-data',
                '--declared-smc-field', '0x8016:1:2',
                '--assert-no-undeclared-self-modifying-code',
            ]
            completed = subprocess.run(command, text=True, capture_output=True)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            evidence = json.loads(report.read_text())
            self.assertEqual(evidence['contract']['declaredSmcOperandFields'], [{
                'instructionAddress': 0x8016, 'operandOffset': 1, 'width': 2,
            }])
            self.assertTrue(
                evidence['contract']['assertNoUndeclaredSelfModifyingCode']
            )
            self.assertEqual(output.read_bytes(),
                             bytes.fromhex('a9 00 a9 42 8d de c0 60'))

    def test_cli_enables_composed_rehome_rule_and_reports_branch_timing(self):
        original = bytes.fromhex('a9 20 c0 00 f0 02 a9 51 8d de c0 60')
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            source = directory / 'in.bin'
            output = directory / 'out.bin'
            report = directory / 'report.json'
            source.write_bytes(original)
            command = [
                sys.executable, str(TOOLS / 'compact6502.py'),
                str(source), str(output), '--report', str(report),
                '--base-address', '0x8000', '--entry', '0x8000',
                '--terminal-live', 'SP',
                '--expected-sha256', sha256(original).hexdigest(),
                '--assert-complete-code-region',
                '--assert-all-incoming-references-repairable',
                '--assert-no-code-as-data', '--assert-no-self-modifying-code',
            ]
            completed = subprocess.run(command, text=True, capture_output=True)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            evidence = json.loads(report.read_text())
            self.assertIn('zero-compare-select-via-rehome',
                          evidence['contract']['enabledRules'])
            self.assertEqual(evidence['applied'][0]['rule'],
                             'zero-compare-select-via-rehome')
            self.assertEqual(
                evidence['summary']['retainedTakenBranchPageCrossCycleDeltaSum'], 0
            )
            self.assertEqual(output.read_bytes(),
                             bytes.fromhex('a2 20 98 f0 02 a2 51 8e de c0 60'))

    def test_cli_writes_fresh_compacted_output_and_ledger(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            source = directory / 'in.bin'
            output = directory / 'out.bin'
            report = directory / 'report.json'
            source.write_bytes(self.combined_image())
            command = [
                sys.executable, str(TOOLS / 'compact6502.py'),
                str(source), str(output), '--report', str(report),
                '--base-address', '0x8000', '--entry', '0x8000',
                '--entry', '0x8005',
                '--expected-sha256', sha256(source.read_bytes()).hexdigest(),
                '--assert-complete-code-region',
                '--assert-all-incoming-references-repairable',
                '--assert-no-code-as-data', '--assert-no-self-modifying-code',
                '--assert-standard-jsr-rts',
            ]
            completed = subprocess.run(command, text=True, capture_output=True)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            evidence = json.loads(report.read_text())
            self.assertEqual(evidence['summary']['byteDelta'], -2)
            self.assertEqual(evidence['summary']['appliedCount'], 2)
            self.assertEqual(output.read_bytes(),
                             bytes.fromhex('a9 01 d0 03 4c 0b 80 ea ea ea 60 60'))
            repeated = subprocess.run(command, text=True, capture_output=True)
            self.assertNotEqual(repeated.returncode, 0)
            self.assertIn('fresh', repeated.stderr)


if __name__ == '__main__':
    unittest.main()
