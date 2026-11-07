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

from cfg_reduction6502 import (  # noqa: E402
    CFGScanConfig, CFGScanError, scan_cfg_candidates,
)


class CFGReduction6502Tests(unittest.TestCase):
    def scan(self, data, base=0x8000, entries=None, **kwargs):
        return scan_cfg_candidates(
            data, base_address=base,
            config=CFGScanConfig(entries=tuple(entries or (base,)), **kwargs),
        )

    def test_discovers_cfg_tail_call_and_known_flag_short_jump(self):
        image = bytearray(0x11)
        image[0:5] = bytes.fromhex('a9 01 4c 0a 80')
        image[0x0A:0x0E] = bytes.fromhex('20 10 80 60')
        image[0x10] = 0x60
        result = self.scan(bytes(image))
        by_rule = {item.rule: item for item in result.candidates}

        short = by_rule['known-flag-short-jump']
        self.assertEqual((short.start, short.original_bytes, short.replacement_bytes),
                         (0x8002, bytes.fromhex('4c 0a 80'), bytes.fromhex('d0 06')))
        self.assertEqual((short.byte_delta, short.nominal_cycle_delta), (-1, 0))
        self.assertTrue(short.timing_admissible)
        self.assertIn('F:Z=0', short.proof)

        tail = by_rule['tail-call-jsr-rts']
        self.assertEqual((tail.start, tail.end_exclusive), (0x800A, 0x800E))
        self.assertEqual(tail.replacement_bytes, bytes.fromhex('4c 10 80'))
        self.assertEqual((tail.byte_delta, tail.nominal_cycle_delta), (-1, -9))
        self.assertTrue(result.decimal_clear_invariant)
        self.assertGreaterEqual(len(result.blocks), 3)

    def test_duplicate_idempotent_operations_are_generalized_safely(self):
        cases = (
            (bytes.fromhex('29 f0 29 f0 60'), bytes.fromhex('29 f0')),
            (bytes.fromhex('c9 07 c9 07 60'), bytes.fromhex('c9 07')),
            (bytes.fromhex('ba ba 60'), bytes.fromhex('ba')),
        )
        for image, replacement in cases:
            with self.subTest(image=image.hex()):
                result = self.scan(image)
                candidate = next(item for item in result.candidates
                                 if item.rule == 'duplicate-idempotent-operation')
                self.assertEqual(candidate.replacement_bytes, replacement)
        for image in (bytes.fromhex('a5 10 a5 10 60'),
                      bytes.fromhex('ea ea 60')):
            result = self.scan(image)
            self.assertNotIn('duplicate-idempotent-operation',
                             {item.rule for item in result.candidates})

    def test_duplicate_transfer_candidate_requires_private_second_instruction(self):
        result = self.scan(bytes.fromhex('aa aa 60'))
        candidate = next(item for item in result.candidates
                         if item.rule == 'duplicate-transfer')
        self.assertEqual((candidate.replacement_bytes, candidate.byte_delta,
                          candidate.nominal_cycle_delta), (bytes.fromhex('aa'), -1, -2))
        shared = self.scan(bytes.fromhex('aa aa 60'), entries=(0x8000, 0x8001))
        self.assertNotIn('duplicate-transfer',
                         {item.rule for item in shared.candidates})

    def test_tail_call_requires_private_rts_control_entry(self):
        image = bytes.fromhex('20 08 80 60')
        result = self.scan(image, entries=(0x8000, 0x8003))
        self.assertNotIn('tail-call-jsr-rts', {item.rule for item in result.candidates})

    def test_unknown_flag_does_not_authorize_short_jump(self):
        image = bytearray(9)
        image[0:3] = bytes.fromhex('4c 08 80')
        image[8] = 0x60
        result = self.scan(bytes(image))
        self.assertNotIn('known-flag-short-jump',
                         {item.rule for item in result.candidates})

    def test_interrupt_rejects_page_crossing_short_jump(self):
        image = bytearray(8)
        image[0:5] = bytes.fromhex('a9 01 4c 01 81')
        image[7] = 0x60
        result = self.scan(bytes(image), base=0x80FA, timing_policy='interrupt')
        candidate = next(item for item in result.candidates
                         if item.rule == 'known-flag-short-jump')
        self.assertEqual(candidate.replacement_bytes, bytes.fromhex('d0 03'))
        self.assertEqual(candidate.nominal_cycle_delta, 1)
        self.assertFalse(candidate.timing_admissible)
        self.assertRegex(candidate.warnings[0], 'crosses a page')

    def test_reports_known_never_taken_branch_deletion(self):
        image = bytes.fromhex('a9 00 d0 02 60 00 60')
        result = self.scan(image)
        candidate = next(item for item in result.candidates
                         if item.rule == 'never-taken-branch-deletion')
        self.assertEqual((candidate.start, candidate.replacement_bytes), (0x8002, b''))
        self.assertEqual((candidate.byte_delta, candidate.nominal_cycle_delta), (-2, -2))

    def test_reports_guaranteed_branch_to_own_fallthrough(self):
        result = self.scan(bytes.fromhex('a9 01 d0 00 60'))
        candidate = next(item for item in result.candidates
                         if item.rule == 'branch-to-fallthrough-deletion')
        self.assertEqual((candidate.start, candidate.replacement_bytes), (0x8002, b''))
        self.assertEqual((candidate.byte_delta, candidate.nominal_cycle_delta), (-2, -3))

    def test_register_availability_enables_alternative_compare_lowering(self):
        image = bytes.fromhex('a5 10 c9 ff f0 01 60 60')
        result = self.scan(image, terminal_live=frozenset({'SP'}))
        candidate = next(item for item in result.candidates
                         if item.rule == 'compare-immediate-via-index-step')
        self.assertEqual(candidate.replacement_bytes,
                         bytes.fromhex('a6 10 e8 f0 01'))
        self.assertEqual((candidate.byte_delta, candidate.nominal_cycle_delta), (-1, 0))
        available = dict(result.available_out)
        self.assertTrue({'A', 'X', 'Y'} <= set(available[0x8004]))
        available_flags = dict(result.available_flags_out)
        self.assertIn('F:C', available_flags[0x8004])

        use_y = self.scan(
            image, terminal_live=frozenset({'SP', 'X'})
        )
        candidate = next(item for item in use_y.candidates
                         if item.rule == 'compare-immediate-via-index-step')
        self.assertEqual(candidate.replacement_bytes,
                         bytes.fromhex('a4 10 c8 f0 01'))

        for terminal in ({'SP', 'A'}, {'SP', 'X', 'Y'}, {'SP', 'F:C'}):
            refused = self.scan(image, terminal_live=frozenset(terminal))
            self.assertNotIn('compare-immediate-via-index-step',
                             {item.rule for item in refused.candidates})

    def test_removes_redundant_zero_compare_after_matching_load(self):
        image = bytes.fromhex('a5 10 c9 00 d0 01 60 60')
        result = self.scan(
            image,
            terminal_live=frozenset({'A', 'SP', 'F:N', 'F:Z'}),
        )
        candidate = next(item for item in result.candidates
                         if item.rule == 'redundant-zero-compare-after-load')
        self.assertEqual((candidate.start, candidate.end_exclusive,
                          candidate.original_bytes, candidate.replacement_bytes),
                         (0x8002, 0x8004, bytes.fromhex('c9 00'), b''))
        self.assertEqual((candidate.byte_delta, candidate.nominal_cycle_delta),
                         (-2, -2))
        self.assertIn('compare-only C=1 result is dead', candidate.proof)

        carry_live = self.scan(
            image, terminal_live=frozenset({'SP', 'F:C'})
        )
        self.assertNotIn('redundant-zero-compare-after-load',
                         {item.rule for item in carry_live.candidates})
        compare_entry = self.scan(
            image, entries=(0x8000, 0x8002),
            terminal_live=frozenset({'SP'}),
        )
        self.assertNotIn('redundant-zero-compare-after-load',
                         {item.rule for item in compare_entry.candidates})
        for refused_image in (
                bytes.fromhex('a5 10 e0 00 d0 01 60 60'),
                bytes.fromhex('a5 10 c9 00 90 01 60 60')):
            refused = self.scan(
                refused_image, terminal_live=frozenset({'SP'})
            )
            self.assertNotIn('redundant-zero-compare-after-load',
                             {item.rule for item in refused.candidates})

    def test_folds_unsigned_branch_after_compare_zero(self):
        always = self.scan(
            bytes.fromhex('c9 00 b0 01 60 60'),
            terminal_live=frozenset({'SP'}),
        )
        candidate = next(item for item in always.candidates
                         if item.rule == 'compare-zero-unsigned-branch-fold')
        self.assertEqual((candidate.original_bytes,
                          candidate.replacement_bytes,
                          candidate.byte_delta, candidate.nominal_cycle_delta),
                         (bytes.fromhex('c9 00 b0 01'),
                          bytes.fromhex('4c 05 80'), -1, -2))

        never = self.scan(
            bytes.fromhex('e0 00 90 01 60 60'),
            terminal_live=frozenset({'SP'}),
        )
        candidate = next(item for item in never.candidates
                         if item.rule == 'compare-zero-unsigned-branch-fold')
        self.assertEqual((candidate.original_bytes,
                          candidate.replacement_bytes,
                          candidate.byte_delta, candidate.nominal_cycle_delta),
                         (bytes.fromhex('e0 00 90 01'), b'', -4, -4))

        image = bytes.fromhex('c0 00 b0 01 60 60')
        for resource in ('F:C', 'F:N', 'F:Z'):
            refused = self.scan(
                image, terminal_live=frozenset({'SP', resource})
            )
            self.assertNotIn('compare-zero-unsigned-branch-fold',
                             {item.rule for item in refused.candidates})
        for entries in ((0x8000, 0x8002),):
            refused = self.scan(
                image, entries=entries, terminal_live=frozenset({'SP'})
            )
            self.assertNotIn('compare-zero-unsigned-branch-fold',
                             {item.rule for item in refused.candidates})
        equality = self.scan(
            bytes.fromhex('c9 00 f0 01 60 60'),
            terminal_live=frozenset({'SP'}),
        )
        self.assertNotIn('compare-zero-unsigned-branch-fold',
                         {item.rule for item in equality.candidates})

    def test_reverses_control_only_fixed_trip_loop(self):
        image = bytes.fromhex('a2 01 e6 20 e8 e0 11 d0 f9 60')
        result = self.scan(image, terminal_live=frozenset({'SP'}))
        candidate = next(item for item in result.candidates
                         if item.rule == 'control-only-loop-reversal')
        self.assertEqual((candidate.start, candidate.end_exclusive),
                         (0x8000, 0x8009))
        self.assertEqual(candidate.original_bytes,
                         bytes.fromhex('a2 01 e6 20 e8 e0 11 d0 f9'))
        self.assertEqual(candidate.replacement_bytes,
                         bytes.fromhex('a2 10 e6 20 ca d0 fb'))
        self.assertEqual((candidate.byte_delta,
                          candidate.nominal_cycle_delta), (-2, -32))
        self.assertIn('16 iterations are preserved', candidate.proof)

        y_loop = self.scan(
            bytes.fromhex('a0 fa e6 20 c8 c0 04 d0 f9 60'),
            terminal_live=frozenset({'SP'}),
        )
        candidate = next(item for item in y_loop.candidates
                         if item.rule == 'control-only-loop-reversal')
        self.assertEqual(candidate.replacement_bytes,
                         bytes.fromhex('a0 0a e6 20 88 d0 fb'))

        cycle_exact = self.scan(
            image, terminal_live=frozenset({'SP'}),
            timing_policy='cycle-exact',
        )
        candidate = next(item for item in cycle_exact.candidates
                         if item.rule == 'control-only-loop-reversal')
        self.assertFalse(candidate.timing_admissible)
        interrupt = self.scan(
            image, terminal_live=frozenset({'SP'}),
            timing_policy='interrupt',
        )
        candidate = next(item for item in interrupt.candidates
                         if item.rule == 'control-only-loop-reversal')
        self.assertTrue(candidate.timing_admissible)

        refused = (
            # Indexed body use.
            (bytes.fromhex('a2 01 9d 00 c0 e8 e0 11 d0 f6 60'),
             (0x8000,), frozenset({'SP'})),
            # Terminal X is observed.
            (bytes.fromhex('a2 01 e6 20 e8 e0 11 d0 f9 86 21 60'),
             (0x8000,), frozenset({'SP'})),
            # Carry from CPX is observed at the next iteration.
            (bytes.fromhex('a2 01 69 01 e8 e0 11 d0 f9 60'),
             (0x8000,), frozenset({'SP'})),
            # Alternate entry into the loop body.
            (image, (0x8000, 0x8002), frozenset({'SP'})),
            # A 256-iteration modulo loop is deferred.
            (bytes.fromhex('a2 00 e6 20 e8 e0 00 d0 f9 60'),
             (0x8000,), frozenset({'SP'})),
        )
        for refused_image, entries, terminal_live in refused:
            with self.subTest(image=refused_image.hex(), entries=entries):
                scan = self.scan(
                    refused_image, entries=entries,
                    terminal_live=terminal_live,
                )
                self.assertNotIn('control-only-loop-reversal',
                                 {item.rule for item in scan.candidates})

    def test_reports_indexed_traversal_reversal_for_semantic_review(self):
        one_based = bytes.fromhex('a2 01 9d 00 c0 e8 e0 11 d0 f8 60')
        result = self.scan(one_based, terminal_live=frozenset({'SP'}))
        self.assertNotIn('control-only-loop-reversal',
                         {item.rule for item in result.candidates})
        self.assertEqual(len(result.indexed_traversal_reversals), 1)
        option = result.indexed_traversal_reversals[0]
        self.assertEqual(
            (option.register, option.strategy, option.start_value,
             option.terminal_value, option.trip_count),
            ('X', 'one-based-decrement-bne', 1, 17, 16),
        )
        self.assertEqual(option.index_use_pcs, (0x8002,))
        self.assertEqual(option.replacement_bytes,
                         bytes.fromhex('a2 10 9d 00 c0 ca d0 fa'))
        self.assertEqual((option.byte_delta, option.nominal_cycle_delta),
                         (-2, -32))
        self.assertIn('behavioral equivalence is not', option.proof)
        self.assertRegex(' '.join(option.warnings), 'memory order reverses')

        zero_based = self.scan(
            bytes.fromhex('a2 00 9d 00 c0 e8 e0 10 d0 f8 60'),
            terminal_live=frozenset({'SP'}),
        )
        option = zero_based.indexed_traversal_reversals[0]
        self.assertEqual(option.strategy, 'zero-based-decrement-bpl')
        self.assertEqual(option.replacement_bytes,
                         bytes.fromhex('a2 0f 9d 00 c0 ca 10 fa'))

        y_based = self.scan(
            bytes.fromhex('a0 01 99 00 c0 c8 c0 05 d0 f8 60'),
            terminal_live=frozenset({'SP'}),
        )
        option = y_based.indexed_traversal_reversals[0]
        self.assertEqual((option.register, option.trip_count), ('Y', 4))
        self.assertEqual(option.replacement_bytes,
                         bytes.fromhex('a0 04 99 00 c0 88 d0 fa'))

        cycle_exact = self.scan(
            one_based, terminal_live=frozenset({'SP'}),
            timing_policy='cycle-exact',
        )
        self.assertFalse(
            cycle_exact.indexed_traversal_reversals[0].timing_admissible
        )

        refused = (
            # Unsupported arbitrary start value.
            bytes.fromhex('a2 02 9d 00 c0 e8 e0 11 d0 f8 60'),
            # Zero-based BPL form is bounded to nonnegative initial values.
            bytes.fromhex('a2 00 9d 00 c0 e8 e0 81 d0 f8 60'),
            # Final X remains observable.
            bytes.fromhex('a2 01 9d 00 c0 e8 e0 11 d0 f8 86 20 60'),
            # Body changes the induction register.
            bytes.fromhex('a2 01 aa e8 e0 11 d0 fa 60'),
        )
        for image in refused:
            scan = self.scan(image, terminal_live=frozenset({'SP'}))
            self.assertFalse(scan.indexed_traversal_reversals)

    def test_masked_bit_tests_lower_through_accumulator_shift(self):
        cases = (
            ('a5 10 29 01 f0 01 60 60', 'a5 10 4a 90 01', -1, 0),
            ('a5 10 29 40 d0 01 60 60', 'a5 10 0a 30 01', -1, 0),
            ('a5 10 29 80 f0 01 60 60', 'a5 10 10 01', -2, -2),
        )
        for original_hex, replacement_hex, byte_delta, cycle_delta in cases:
            with self.subTest(original=original_hex):
                result = self.scan(
                    bytes.fromhex(original_hex),
                    terminal_live=frozenset({'SP'}),
                )
                candidate = next(item for item in result.candidates
                                 if item.rule == 'masked-bit-test-via-shift')
                self.assertEqual(candidate.replacement_bytes,
                                 bytes.fromhex(replacement_hex))
                self.assertEqual((candidate.byte_delta,
                                  candidate.nominal_cycle_delta),
                                 (byte_delta, cycle_delta))

        refusal_resources = {
            0x01: ('A', 'F:C', 'F:Z'),
            0x40: ('A', 'F:C', 'F:N', 'F:Z'),
            0x80: ('A', 'F:Z'),
        }
        for mask, resources in refusal_resources.items():
            image = bytes((0xA5, 0x10, 0x29, mask, 0xF0, 0x01,
                           0x60, 0x60))
            for resource in resources:
                refused = self.scan(
                    image, terminal_live=frozenset({'SP', resource})
                )
                self.assertNotIn('masked-bit-test-via-shift',
                                 {item.rule for item in refused.candidates})
        for image, entries in (
                (bytes.fromhex('a5 10 29 02 f0 01 60 60'), (0x8000,)),
                (bytes.fromhex('a5 10 29 01 f0 01 60 60'),
                 (0x8000, 0x8002)),
                (bytes.fromhex('a5 10 29 01 f0 01 60 60'),
                 (0x8000, 0x8004))):
            refused = self.scan(
                image, entries=entries, terminal_live=frozenset({'SP'})
            )
            self.assertNotIn('masked-bit-test-via-shift',
                             {item.rule for item in refused.candidates})

    def test_compare_two_lowers_to_lsr_when_clobbers_are_available(self):
        image = bytes.fromhex('a5 10 c9 02 90 01 60 60')
        result = self.scan(image, terminal_live=frozenset({'SP'}))
        candidate = next(item for item in result.candidates
                         if item.rule == 'compare-two-via-lsr')
        self.assertEqual(candidate.replacement_bytes,
                         bytes.fromhex('a5 10 4a f0 01'))
        self.assertEqual((candidate.byte_delta, candidate.nominal_cycle_delta), (-1, 0))
        for resource in ('A', 'F:C', 'F:N', 'F:Z'):
            refused = self.scan(image, terminal_live=frozenset({'SP', resource}))
            self.assertNotIn('compare-two-via-lsr',
                             {item.rule for item in refused.candidates})

    def test_reports_simple_register_live_range_rehoming_options(self):
        image = bytes.fromhex('a9 00 ea 8d 20 d0 60')
        result = self.scan(image, terminal_live=frozenset({'SP'}))
        options = {(item.original_register, item.replacement_register): item
                   for item in result.register_rehomes}
        self.assertEqual(set(options), {('A', 'X'), ('A', 'Y')})
        self.assertEqual(options[('A', 'Y')].replacement_producer_bytes,
                         bytes.fromhex('a0 00'))
        self.assertEqual(options[('A', 'Y')].replacement_consumer_bytes,
                         bytes.fromhex('8c 20 d0'))
        self.assertEqual((options[('A', 'Y')].byte_delta,
                          options[('A', 'Y')].nominal_cycle_delta), (0, 0))

        x_reserved = self.scan(
            image, terminal_live=frozenset({'SP', 'X'})
        )
        self.assertEqual(
            {item.replacement_register for item in x_reserved.register_rehomes},
            {'Y'},
        )
        source_live = self.scan(
            image, terminal_live=frozenset({'SP', 'A'})
        )
        self.assertFalse(source_live.register_rehomes)

    def test_composes_zero_compare_with_two_path_register_rehome(self):
        image = bytes.fromhex('a9 20 c0 00 f0 02 a9 51 8d de c0 60')
        result = self.scan(image, terminal_live=frozenset({'SP'}))
        candidate = next(item for item in result.candidates
                         if item.rule == 'zero-compare-select-via-rehome')
        self.assertEqual(candidate.replacement_bytes,
                         bytes.fromhex('a2 20 98 f0 02 a2 51 8e de c0'))
        self.assertEqual((candidate.byte_delta, candidate.nominal_cycle_delta), (-1, 0))
        self.assertIn('rehomed to dead X', candidate.proof)

        for terminal in ({'SP', 'A'}, {'SP', 'X'}, {'SP', 'F:C'}):
            refused = self.scan(image, terminal_live=frozenset(terminal))
            self.assertNotIn('zero-compare-select-via-rehome',
                             {item.rule for item in refused.candidates})
        for interior_entry in (0x8006, 0x8008):
            shared = self.scan(
                image, entries=(0x8000, interior_entry),
                terminal_live=frozenset({'SP'}),
            )
            self.assertNotIn('zero-compare-select-via-rehome',
                             {item.rule for item in shared.candidates})

    def test_index_compare_can_use_its_own_dead_register(self):
        image = bytes.fromhex('a6 10 e0 01 d0 01 60 60')
        result = self.scan(image, terminal_live=frozenset({'SP'}))
        candidate = next(item for item in result.candidates
                         if item.rule == 'compare-immediate-via-index-step')
        self.assertEqual(candidate.replacement_bytes,
                         bytes.fromhex('a6 10 ca d0 01'))

    def test_decimal_policy_uses_program_scan_and_cpu_profile(self):
        no_setter = self.scan(bytes.fromhex('18 69 01 60'))
        self.assertTrue(no_setter.decimal_clear_invariant)
        self.assertRegex(no_setter.decimal_policy, 'no reachable decimal')

        setter = self.scan(bytes.fromhex('f8 18 69 01 60'))
        self.assertFalse(setter.decimal_clear_invariant)
        self.assertIn('$8000', setter.decimal_policy)

        explicit_decimal = self.scan(
            bytes.fromhex('18 69 01 60'), entry_facts=(('F:D', 1),)
        )
        self.assertFalse(explicit_decimal.decimal_clear_invariant)

        disabled = self.scan(bytes.fromhex('f8 18 69 01 60'), cpu_profile='2a03')
        self.assertTrue(disabled.decimal_clear_invariant)
        self.assertRegex(disabled.decimal_policy, 'disabled')

    def test_external_call_requires_decimal_preservation_contract(self):
        image = bytes.fromhex('20 00 90 60')
        unknown = self.scan(image)
        self.assertFalse(unknown.decimal_clear_invariant)
        preserved = self.scan(image, external_calls_preserve_decimal=True)
        self.assertTrue(preserved.decimal_clear_invariant)

    def test_overlapping_control_target_refuses(self):
        with self.assertRaisesRegex(CFGScanError, 'overlap|enters instruction'):
            self.scan(bytes.fromhex('d0 01 a9 00 60'))

    def test_cli_hash_guard_writes_fresh_read_only_report(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            source = directory / 'image.bin'
            report = directory / 'scan.json'
            source.write_bytes(bytes.fromhex('20 08 80 60'))
            original = source.read_bytes()
            command = [
                sys.executable, str(TOOLS / 'scan_reductions6502.py'),
                str(source), '--report', str(report),
                '--base-address', '0x8000', '--entry', '0x8000',
                '--expected-sha256', sha256(original).hexdigest(),
            ]
            completed = subprocess.run(command, text=True, capture_output=True)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(source.read_bytes(), original)
            evidence = json.loads(report.read_text())
            self.assertEqual(evidence['format'],
                             '6502-size-reduction-candidate-scan-v1')
            self.assertEqual(evidence['summary']['candidateCount'], 1)
            repeated = subprocess.run(command, text=True, capture_output=True)
            self.assertNotEqual(repeated.returncode, 0)
            self.assertIn('fresh', repeated.stderr)


if __name__ == '__main__':
    unittest.main()
