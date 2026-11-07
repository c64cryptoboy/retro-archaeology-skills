#!/usr/bin/env python3

from dataclasses import replace
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / 'tools'
sys.path.insert(0, str(TOOLS))

from cfg_reduction6502 import CFGScanConfig, scan_cfg_candidates  # noqa: E402
from routine_runner import InitialState, RoutineSpec, run_routine  # noqa: E402
from semantic_loop6502 import (  # noqa: E402
    IndexedTraversalSemanticContract, SemanticLoopError,
    materialize_indexed_traversal_reversal,
)


BASE = 0x109A
SHDMG = 0x1CA1
ORIGINAL = bytes.fromhex('a2 00 a9 03 9d a1 1c e8 e0 20 d0 f6')


def option_for(data=ORIGINAL, timing_policy='ordinary'):
    scan = scan_cfg_candidates(
        data, base_address=BASE,
        config=CFGScanConfig(
            entries=(BASE,), terminal_live=frozenset({'SP'}),
            timing_policy=timing_policy, cpu_profile='6510',
        ),
    )
    return scan.indexed_traversal_reversals[0]


def contract():
    return IndexedTraversalSemanticContract(
        equivalence_kind='exact-final-state',
        assert_same_index_set=True,
        assert_reverse_order_equivalent=True,
        assert_no_alias_or_overlap_dependency=True,
        assert_no_order_sensitive_io=True,
        assert_no_early_exit_or_recurrence=True,
        assert_no_smc_or_asynchronous_observer=True,
        assert_final_index_and_flags_unobserved=True,
    )


def run_loop(code, exit_pc):
    memory = bytearray(65536)
    memory[BASE:BASE + len(code)] = code
    memory[SHDMG:SHDMG + 32] = bytes(range(32))
    return run_routine(
        RoutineSpec(BASE, {exit_pc}, 1000),
        InitialState(bytes(memory), a=0x55, x=0xAA, y=0xCC,
                     sp=0xF0, flags=0xE1),
    )


class SemanticLoop6502Tests(unittest.TestCase):
    def test_materializes_explicitly_accepted_reverse_order_loop(self):
        option = option_for()
        result = materialize_indexed_traversal_reversal(
            ORIGINAL, base_address=BASE, option=option, contract=contract()
        )
        self.assertEqual(result.compacted,
                         bytes.fromhex('a2 1f a9 03 9d a1 1c ca 10 f8'))
        self.assertEqual((result.byte_delta, result.nominal_cycle_delta),
                         (-2, -64))
        left = run_loop(ORIGINAL, BASE + len(ORIGINAL))
        right = run_loop(result.compacted, BASE + len(result.compacted))
        self.assertTrue(left.reached_legal_exit and right.reached_legal_exit)
        self.assertEqual(left.final.memory[SHDMG:SHDMG + 32], bytes((3,)) * 32)
        self.assertEqual(left.final.memory[SHDMG:SHDMG + 32],
                         right.final.memory[SHDMG:SHDMG + 32])
        self.assertEqual((left.final.a, left.final.y, left.final.sp),
                         (right.final.a, right.final.y, right.final.sp))
        self.assertEqual(right.final.cycles, left.final.cycles - 64)
        left_addresses = tuple(item[0] for item in left.access.write_trace)
        right_addresses = tuple(item[0] for item in right.access.write_trace)
        self.assertEqual(left_addresses, tuple(range(SHDMG, SHDMG + 32)))
        self.assertEqual(right_addresses,
                         tuple(range(SHDMG + 31, SHDMG - 1, -1)))

    def test_refuses_missing_contract_identity_and_timing(self):
        option = option_for()
        for field in (
                'assert_same_index_set',
                'assert_reverse_order_equivalent',
                'assert_no_alias_or_overlap_dependency',
                'assert_no_order_sensitive_io',
                'assert_no_early_exit_or_recurrence',
                'assert_no_smc_or_asynchronous_observer',
                'assert_final_index_and_flags_unobserved'):
            with self.subTest(field=field):
                with self.assertRaisesRegex(SemanticLoopError, 'explicit true'):
                    materialize_indexed_traversal_reversal(
                        ORIGINAL, base_address=BASE, option=option,
                        contract=replace(contract(), **{field: False}),
                    )
        with self.assertRaisesRegex(SemanticLoopError, 'guarded option'):
            materialize_indexed_traversal_reversal(
                ORIGINAL[:-1] + b'\x00', base_address=BASE,
                option=option, contract=contract(),
            )
        with self.assertRaisesRegex(SemanticLoopError, 'timing policy'):
            materialize_indexed_traversal_reversal(
                ORIGINAL, base_address=BASE,
                option=option_for(timing_policy='cycle-exact'),
                contract=contract(),
            )
        with self.assertRaisesRegex(SemanticLoopError, 'canonical local rewrite'):
            materialize_indexed_traversal_reversal(
                ORIGINAL, base_address=BASE,
                option=replace(option, replacement_bytes=b'\x60', byte_delta=-11),
                contract=contract(),
            )


if __name__ == '__main__':
    unittest.main()
