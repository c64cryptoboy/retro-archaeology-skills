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

from reduction_rules6502 import (  # noqa: E402
    _FUSIONS, _OPCODE_BY_NAME_MODE, ReductionConfig, ReductionError,
    reduce_straight_block,
)
from isa6502 import OPS  # noqa: E402
from routine_runner import InitialState, RoutineSpec, run_routine  # noqa: E402


def run(data, address, *, a=0, x=0, y=0, flags=0x20):
    memory = bytearray(65536)
    memory[address:address + len(data)] = data
    memory[0x01FE:0x0200] = bytes((0xFF, 0x6F))
    return run_routine(
        RoutineSpec(address, {0x7000}, 100),
        InitialState(bytes(memory), a=a, x=x, y=y, sp=0xFD, flags=flags),
    )


class ReductionRules6502Tests(unittest.TestCase):
    def config(self, **kwargs):
        values = {'assert_no_interior_entries': True, 'assert_no_code_as_data': True}
        values.update(kwargs)
        return ReductionConfig(**values)

    def test_transfer_roundtrip_is_exact_and_smaller(self):
        original = bytes.fromhex('aa 8a 60')  # TAX; TXA; RTS
        result = reduce_straight_block(original, config=self.config())
        self.assertEqual(result.reduced, bytes.fromhex('aa 60'))
        self.assertEqual((result.byte_delta, result.cycle_delta), (-1, -2))
        self.assertEqual(result.ledger[0].rule, 'transfer-roundtrip')
        for a in range(256):
            for flags in (0x20, 0x21, 0x62, 0xE5):
                left = run(original, 0x8000, a=a, x=a ^ 0xFF, flags=flags)
                right = run(result.reduced, 0x8100, a=a, x=a ^ 0xFF, flags=flags)
                self.assertEqual(
                    (left.final.a, left.final.x, left.final.y, left.final.sp,
                     left.final.flags, left.final.pc),
                    (right.final.a, right.final.x, right.final.y, right.final.sp,
                     right.final.flags, right.final.pc),
                )

    def test_load_transfer_fuses_only_when_source_is_dead(self):
        original = bytes.fromhex('a9 42 aa 86 20 60')
        reduced = reduce_straight_block(
            original,
            config=self.config(terminal_live=frozenset({'X', 'SP', 'F:N', 'F:Z'})),
        )
        self.assertEqual(reduced.reduced, bytes.fromhex('a2 42 86 20 60'))
        self.assertEqual((reduced.byte_delta, reduced.cycle_delta), (-1, -2))
        kept = reduce_straight_block(
            original,
            config=self.config(terminal_live=frozenset({'A', 'X', 'SP', 'F:N', 'F:Z'})),
        )
        self.assertEqual(kept.reduced, original)
        for initial_a in (0, 0x42, 0xFF):
            left = run(original, 0x8000, a=initial_a)
            right = run(reduced.reduced, 0x8100, a=initial_a)
            self.assertEqual((left.final.x, left.final.flags, left.final.memory[0x20]),
                             (right.final.x, right.final.flags, right.final.memory[0x20]))

    def test_every_declared_fusion_has_matching_mode_and_operand(self):
        reverse = {(mnemonic, mode): opcode
                   for opcode, (mnemonic, mode, _length) in OPS.items()}
        transfer_target = {'TAX': 'X', 'TAY': 'Y', 'TXA': 'A', 'TYA': 'A'}
        operand = {
            'imm': bytes((0x42,)), 'zp': bytes((0x20,)),
            'abs': bytes((0x34, 0x12)),
            'abx': bytes((0x34, 0x12)), 'aby': bytes((0x34, 0x12)),
        }
        transfer_opcode = {'TAX': 0xAA, 'TAY': 0xA8, 'TXA': 0x8A, 'TYA': 0x98}
        for (load, transfer, mode), (fused_opcode, dead_source) in _FUSIONS.items():
            with self.subTest(load=load, transfer=transfer, mode=mode):
                original = bytes((reverse[(load, mode)],)) + operand[mode] + bytes((transfer_opcode[transfer], 0x60))
                result = reduce_straight_block(
                    original,
                    config=self.config(terminal_live=frozenset({
                        transfer_target[transfer], 'SP', 'F:N', 'F:Z',
                    })),
                )
                self.assertEqual(result.reduced,
                                 bytes((fused_opcode,)) + operand[mode] + bytes((0x60,)))
                self.assertEqual(OPS[fused_opcode][1], mode)
                self.assertEqual(result.ledger[0].proof.split()[0], dead_source)

    def test_known_entry_facts_remove_exact_redundancies(self):
        original = bytes.fromhex('18 a9 00 85 20 60')
        result = reduce_straight_block(
            original,
            config=self.config(entry_facts=(('A', 0), ('F:N', 0),
                                            ('F:Z', 1), ('F:C', 0))),
        )
        self.assertEqual(result.reduced, bytes.fromhex('85 20 60'))
        self.assertEqual((result.byte_delta, result.cycle_delta), (-3, -4))
        self.assertEqual(len(result.ledger), 2)

    def test_known_carry_adjustment_is_exact_in_binary_mode(self):
        cases = (
            (bytes.fromhex('18 69'), 1, 0x21),  # CLC; ADC, incoming C=1
            (bytes.fromhex('38 e9'), 0, 0x20),  # SEC; SBC, incoming C=0
        )
        for prefix, carry, flags in cases:
            for operand in (0x01, 0x7F, 0x81, 0xFF):
                with self.subTest(prefix=prefix.hex(), operand=operand):
                    original = prefix + bytes((operand, 0x60))
                    result = reduce_straight_block(
                        original,
                        config=self.config(entry_facts=(('F:C', carry), ('F:D', 0))),
                    )
                    self.assertEqual(result.reduced,
                                     prefix[1:2] + bytes(((operand - 1) & 0xFF, 0x60)))
                    self.assertEqual((result.byte_delta, result.cycle_delta), (-1, -2))
                    self.assertEqual(result.ledger[0].rule,
                                     'known-carry-immediate-adjustment')
                    for a in range(256):
                        left = run(original, 0x8000, a=a, flags=flags)
                        right = run(result.reduced, 0x8100, a=a, flags=flags)
                        self.assertEqual(
                            (left.final.a, left.final.x, left.final.y,
                             left.final.sp, left.final.flags),
                            (right.final.a, right.final.x, right.final.y,
                             right.final.sp, right.final.flags),
                        )

    def test_known_carry_adjustment_refuses_decimal_and_flag_boundaries(self):
        original = bytes.fromhex('18 69 01 60')
        for facts in ((), (('F:C', 1),), (('F:C', 1), ('F:D', 1))):
            result = reduce_straight_block(
                original, config=self.config(entry_facts=facts)
            )
            self.assertEqual(result.reduced, original)
        for operand in (0x00, 0x80):
            result = reduce_straight_block(
                bytes((0x18, 0x69, operand, 0x60)),
                config=self.config(entry_facts=(('F:C', 1), ('F:D', 0))),
            )
            self.assertEqual(result.reduced, bytes((0x18, 0x69, operand, 0x60)))

    def test_duplicate_setter_rule_operates_without_known_state_rule(self):
        result = reduce_straight_block(
            bytes.fromhex('38 38 60'),
            config=self.config(enabled_rules=frozenset({'duplicate-flag-setter'})),
        )
        self.assertEqual(result.reduced, bytes.fromhex('38 60'))
        self.assertEqual(result.ledger[0].rule, 'duplicate-flag-setter')

    def test_zero_page_operand_narrowing_and_index_wrap_guards(self):
        direct = reduce_straight_block(
            bytes.fromhex('ad 20 00 60'), config=self.config()
        )
        self.assertEqual(direct.reduced, bytes.fromhex('a5 20 60'))
        self.assertEqual((direct.byte_delta, direct.cycle_delta), (-1, -1))
        self.assertEqual(direct.ledger[0].rule, 'zero-page-operand-narrowing')
        for a in (0, 0x80, 0xFF):
            left = run(bytes.fromhex('ad 20 00 60'), 0x8000, a=a)
            right = run(direct.reduced, 0x8100, a=a)
            self.assertEqual((left.final.a, left.final.flags),
                             (right.final.a, right.final.flags))

        safe = reduce_straight_block(
            bytes.fromhex('bd f0 00 60'),
            config=self.config(entry_facts=(('X', 15),)),
        )
        self.assertEqual(safe.reduced, bytes.fromhex('b5 f0 60'))
        for facts in ((), (('X', 16),)):
            unsafe = reduce_straight_block(
                bytes.fromhex('bd f0 00 60'),
                config=self.config(entry_facts=facts),
            )
            self.assertEqual(unsafe.reduced, bytes.fromhex('bd f0 00 60'))

    def test_every_supported_absolute_mode_narrows_to_matching_zero_page_mode(self):
        mode_pairs = (('abs', 'zp', None), ('abx', 'zpx', 'X'), ('aby', 'zpy', 'Y'))
        for (mnemonic, mode), opcode in _OPCODE_BY_NAME_MODE.items():
            for wide_mode, narrow_mode, index in mode_pairs:
                if mode != wide_mode:
                    continue
                narrow_opcode = _OPCODE_BY_NAME_MODE.get((mnemonic, narrow_mode))
                if narrow_opcode is None:
                    continue
                with self.subTest(mnemonic=mnemonic, mode=mode):
                    facts = () if index is None else ((index, 0),)
                    result = reduce_straight_block(
                        bytes((opcode, 0x20, 0x00, 0x60)),
                        config=self.config(entry_facts=facts),
                    )
                    self.assertEqual(result.reduced, bytes((narrow_opcode, 0x20, 0x60)))

    def test_interrupt_policy_never_adds_cycles(self):
        result = reduce_straight_block(
            bytes.fromhex('a8 98 60'),
            config=self.config(timing_policy='interrupt'),
        )
        self.assertLess(result.byte_delta, 0)
        self.assertLessEqual(result.cycle_delta, 0)

    def test_cycle_exact_missing_assertion_and_control_flow_refuse(self):
        with self.assertRaisesRegex(ReductionError, 'cycle-exact'):
            reduce_straight_block(bytes.fromhex('ea 60'),
                                  config=self.config(timing_policy='cycle-exact'))
        with self.assertRaisesRegex(ReductionError, 'no interior entries'):
            reduce_straight_block(bytes.fromhex('ea 60'))
        with self.assertRaisesRegex(ReductionError, 'not read or written as data'):
            reduce_straight_block(
                bytes.fromhex('ea 60'),
                config=ReductionConfig(assert_no_interior_entries=True),
            )
        with self.assertRaisesRegex(ReductionError, 'outside straight-line'):
            reduce_straight_block(bytes.fromhex('d0 fe'), config=self.config())

    def test_nop_is_preserved_and_warned(self):
        result = reduce_straight_block(bytes.fromhex('ea 60'), config=self.config())
        self.assertEqual(result.reduced, bytes.fromhex('ea 60'))
        self.assertRegex(result.warnings[0], 'cycle padding')

    def test_cli_hash_guards_and_writes_fresh_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            source = directory / 'in.bin'
            output = directory / 'out.bin'
            report = directory / 'report.json'
            source.write_bytes(bytes.fromhex('aa 8a 60'))
            command = [
                sys.executable, str(TOOLS / 'reduce6502.py'),
                str(source), str(output), '--report', str(report),
                '--base-address', '0x8000',
                '--expected-sha256', sha256(source.read_bytes()).hexdigest(),
                '--assert-no-interior-entries', '--assert-no-code-as-data',
                '--terminal-live', 'A', 'X', 'Y', 'SP', 'F:N', 'F:V',
                'F:D', 'F:I', 'F:Z', 'F:C',
            ]
            completed = subprocess.run(command, text=True, capture_output=True)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(output.read_bytes(), bytes.fromhex('aa 60'))
            evidence = json.loads(report.read_text())
            self.assertEqual(evidence['summary']['byteDelta'], -1)
            self.assertEqual(evidence['summary']['nominalCycleDelta'], -2)
            repeated = subprocess.run(command, text=True, capture_output=True)
            self.assertNotEqual(repeated.returncode, 0)
            self.assertIn('fresh', repeated.stderr)


if __name__ == '__main__':
    unittest.main()
