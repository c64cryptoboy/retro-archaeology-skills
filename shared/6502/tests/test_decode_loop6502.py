#!/usr/bin/env python3
"""Synthetic, bounded CLI tests for decoder-loop instruction-fetch admission.

DECODE_LOOP_TOOL optionally selects a baseline copy.  SIMULATOR_TEST_TMP keeps
all temporary artifacts inside an isolated candidate lane when required.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

TOOL = Path(os.environ.get("DECODE_LOOP_TOOL", Path(__file__).resolve().parents[1] / "decode-loop6502.py"))


class DecoderFetchTests(unittest.TestCase):
    def invoke(self, program, *args, base=0x1000, output=False):
        with tempfile.TemporaryDirectory(dir=os.environ.get("SIMULATOR_TEST_TMP")) as work:
            path = Path(work) / "synthetic.prg"
            path.write_bytes(base.to_bytes(2, "little") + bytes(program))
            output_path = Path(work) / "derived.prg"
            command = [sys.executable, "-B", str(TOOL), str(path), "--max-instructions", "20", *args]
            if output:
                command += ["--output-prg", str(output_path)]
            process = subprocess.run(command, text=True, capture_output=True, timeout=5,
                                     env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
            derived = output_path.read_bytes() if output_path.exists() else None
            return process, derived

    def simulate(self, program, *args, **kwargs):
        process, _ = self.invoke(program, *args, **kwargs)
        self.assertEqual(process.returncode, 0, process.stderr)
        return json.loads(process.stdout)

    def assert_fetch_stop(self, result, reason, pc, address, count, source=None, length=None,
                          supplied=False, value=None):
        self.assertEqual(result["reason"], reason)
        self.assertEqual(result["registers"]["pc"], pc)
        self.assertEqual(result["instructionsExecuted"], count)
        self.assertEqual(result["fetchStop"], {"pc": pc, "address": address,
                                             "byteOffset": address - pc,
                                             "instructionLength": length, "source": source,
                                             "supplied": supplied, "value": value})
        self.assertFalse(any(row["mnemonic"] == "BRK" for row in result["trace"]))

    def test_initial_entry_outside_image_is_not_brk(self):
        result = self.simulate([0xEA], "--start", "0x2000")
        self.assert_fetch_stop(result, "outside_executable_ranges", 0x2000, 0x2000, 0)
        self.assertEqual(result["trace"], [])
        self.assertEqual(result["changes"], [])

    def test_jmp_to_unknown_memory_is_not_brk(self):
        result = self.simulate([0x4C, 0x00, 0x20])
        self.assert_fetch_stop(result, "outside_executable_ranges", 0x2000, 0x2000, 1,
                               {"pc": 0x1000, "mnemonic": "JMP"})
        self.assertEqual([row["mnemonic"] for row in result["trace"]], ["JMP"])

    def test_taken_branch_to_unknown_memory_is_not_brk(self):
        result = self.simulate([0xD0, 0x7E])  # Default Z=0; BNE $1080.
        self.assert_fetch_stop(result, "outside_executable_ranges", 0x1080, 0x1080, 1,
                               {"pc": 0x1000, "mnemonic": "BNE"})

    def test_fallthrough_to_unknown_memory_is_not_brk(self):
        result = self.simulate([0xEA])
        self.assert_fetch_stop(result, "outside_executable_ranges", 0x1001, 0x1001, 1,
                               {"pc": 0x1000, "mnemonic": "NOP"})

    def test_multibyte_load_crossing_image_stops_before_execution(self):
        result = self.simulate([0xA9], "--a", "0x37")
        self.assert_fetch_stop(result, "outside_executable_ranges", 0x1000, 0x1001, 0, length=2)
        self.assertEqual(result["registers"]["a"], 0x37)
        self.assertEqual(result["trace"], [])

    def test_multibyte_store_crossing_image_has_no_side_effect(self):
        result = self.simulate([0x8D, 0x00], "--a", "0x37")
        self.assert_fetch_stop(result, "outside_executable_ranges", 0x1000, 0x1002, 0, length=3)
        self.assertEqual(result["changes"], [])
        self.assertEqual(result["trace"], [])

    def test_known_brk_is_still_brk(self):
        result = self.simulate([0x00])
        self.assertEqual(result["reason"], "brk")
        self.assertEqual(result["instructionsExecuted"], 1)
        self.assertEqual(result["trace"][0]["mnemonic"], "BRK")

    def test_untaken_branch_does_not_precheck_unused_destination(self):
        result = self.simulate([0xA9, 0x00, 0xD0, 0x7E, 0x00])
        self.assertEqual(result["reason"], "brk")
        self.assertEqual(result["instructionsExecuted"], 3)
        self.assertEqual(result["registers"]["pc"], 0x1004)

    def test_configured_range_does_not_invent_known_bytes(self):
        result = self.simulate([0xEA], "--start", "0x2000", "--exec-range", "0x2000:0x2001")
        self.assert_fetch_stop(result, "unknown_instruction_byte", 0x2000, 0x2000, 0)

    def test_jump_to_declared_but_unknown_region(self):
        result = self.simulate([0x4C, 0x00, 0x20], "--exec-range", "0x1000:0x1003",
                               "--exec-range", "0x2000:0x2001")
        self.assert_fetch_stop(result, "unknown_instruction_byte", 0x2000, 0x2000, 1,
                               {"pc": 0x1000, "mnemonic": "JMP"})

    def test_set_does_not_grant_executable_status(self):
        result = self.simulate([0x4C, 0x00, 0x20], "--set", "0x2000=0")
        self.assert_fetch_stop(result, "outside_executable_ranges", 0x2000, 0x2000, 1,
                               {"pc": 0x1000, "mnemonic": "JMP"}, supplied=True, value=0)

    def test_set_and_explicit_range_admit_external_brk(self):
        result = self.simulate([0x4C, 0x00, 0x20], "--set", "0x2000=0",
                               "--exec-range", "0x1000:0x1003", "--exec-range", "0x2000:0x2001")
        self.assertEqual(result["reason"], "brk")
        self.assertEqual(result["instructionsExecuted"], 2)
        self.assertIsNone(result["fetchStop"])
        self.assertEqual(result["executableRanges"], [[0x1000, 0x1003], [0x2000, 0x2001]])

    def test_explicit_ranges_replace_default_and_can_exclude_loaded_data(self):
        result = self.simulate([0x00, 0xEA], "--exec-range", "0x1001:0x1002")
        self.assert_fetch_stop(result, "outside_executable_ranges", 0x1000, 0x1000, 0, supplied=True, value=0)

    def test_operand_crossing_executable_range_is_not_decoded(self):
        result = self.simulate([0xA9, 0x42], "--exec-range", "0x1000:0x1001")
        self.assert_fetch_stop(result, "outside_executable_ranges", 0x1000, 0x1001, 0,
                               length=2, supplied=True, value=0x42)
        self.assertEqual(result["registers"]["a"], 0)

    def test_unknown_operand_inside_executable_range_is_not_decoded(self):
        result = self.simulate([0xA9], "--exec-range", "0x1000:0x1002")
        self.assert_fetch_stop(result, "unknown_instruction_byte", 0x1000, 0x1001, 0, length=2)
        self.assertEqual(result["trace"], [])

    def test_set_operand_and_adjacent_ranges_cover_complete_instruction(self):
        result = self.simulate([0xA9], "--set", "0x1001=0x42", "--exec-range", "0x1000:0x1001",
                               "--exec-range", "0x1001:0x1002")
        self.assert_fetch_stop(result, "outside_executable_ranges", 0x1002, 0x1002, 1,
                               {"pc": 0x1000, "mnemonic": "LDA"})
        self.assertEqual(result["registers"]["a"], 0x42)

    def test_multibyte_fetch_does_not_wrap_address_space(self):
        result = self.simulate([0xA9], base=0xFFFF)
        self.assert_fetch_stop(result, "instruction_fetch_outside_memory", 0xFFFF, 0x10000, 0, length=2)
        self.assertEqual(result["trace"], [])

    def test_known_brk_at_last_address(self):
        result = self.simulate([0x00], base=0xFFFF)
        self.assertEqual(result["reason"], "brk")
        self.assertEqual(result["registers"]["pc"], 0xFFFF)

    def test_invalid_start_has_no_negative_index_or_wrap(self):
        for start in ("-1", "65536"):
            with self.subTest(start=start):
                result = self.simulate([0x00], "--start", start)
                self.assert_fetch_stop(result, "instruction_fetch_outside_memory", int(start), int(start), 0)

    def test_in_place_opcode_self_modification_and_output(self):
        program = [0xA9, 0x00, 0x8D, 0x08, 0x10, 0x4C, 0x08, 0x10, 0x60]
        process, derived = self.invoke(program, output=True)
        self.assertEqual(process.returncode, 0, process.stderr)
        result = json.loads(process.stdout)
        self.assertEqual(result["reason"], "brk")
        self.assertEqual(result["instructionsExecuted"], 4)
        self.assertEqual(result["changes"], [{"address": 0x1008, "before": 0x60, "after": 0}])
        self.assertEqual(derived, b"\x00\x10" + bytes(program[:-1]) + b"\x00")

    def test_in_place_operand_self_modification(self):
        result = self.simulate([0xA9, 0x2A, 0x8D, 0x09, 0x10, 0x4C, 0x08, 0x10, 0xA9, 0, 0])
        self.assertEqual(result["reason"], "brk")
        self.assertEqual(result["registers"]["a"], 0x2A)
        self.assertEqual(result["instructionsExecuted"], 5)

    def test_in_place_rmw_self_modification(self):
        for opcode, initial in ((0xEE, 0xFF), (0xCE, 0x01)):
            with self.subTest(opcode=opcode):
                result = self.simulate([opcode, 0x06, 0x10, 0x4C, 0x06, 0x10, initial])
                self.assertEqual(result["reason"], "brk")
                self.assertEqual(result["instructionsExecuted"], 3)
                self.assertEqual(result["changes"], [{"address": 0x1006, "before": initial, "after": 0}])

    def test_self_modified_instruction_length_is_rechecked(self):
        result = self.simulate([0xA9, 0xA9, 0x8D, 0x08, 0x10, 0x4C, 0x08, 0x10, 0xEA])
        self.assert_fetch_stop(result, "outside_executable_ranges", 0x1008, 0x1009, 3,
                               {"pc": 0x1005, "mnemonic": "JMP"}, length=2)
        self.assertEqual(result["registers"]["a"], 0xA9)
        self.assertEqual(result["changes"], [{"address": 0x1008, "before": 0xEA, "after": 0xA9}])

    def test_store_to_missing_byte_does_not_promote_fetch_evidence(self):
        result = self.simulate([0xA9, 0, 0x8D, 0, 0x20, 0x4C, 0, 0x20],
                               "--exec-range", "0x1000:0x1008", "--exec-range", "0x2000:0x2001")
        self.assert_fetch_stop(result, "unknown_instruction_byte", 0x2000, 0x2000, 3,
                               {"pc": 0x1005, "mnemonic": "JMP"})

    def test_existing_data_read_model_is_unchanged(self):
        # Deliberately not a taint analysis: callers still supply material RAM state.
        result = self.simulate([0xAD, 0x00, 0x20, 0x00], "--a", "0x42")
        self.assertEqual(result["reason"], "brk")
        self.assertEqual(result["registers"]["a"], 0)

    def test_existing_set_masking_is_unchanged(self):
        result = self.simulate([0xEA], "--start", "0x2000", "--set", "0x12000=0x100",
                               "--exec-range", "0x2000:0x2001")
        self.assertEqual(result["reason"], "brk")

    def test_existing_invalid_and_unsupported_stops(self):
        for opcode, reason in ((0x02, "invalid_or_truncated_opcode"), (0x0A, "unsupported_ASL"),
                               (0x60, "rts"), (0x40, "rti")):
            with self.subTest(opcode=opcode):
                result = self.simulate([opcode])
                self.assertEqual(result["reason"], reason)
                self.assertEqual(result["instructionsExecuted"], 1)

    def test_instruction_limit_does_not_probe_unattempted_fetch(self):
        result = self.simulate([0xEA], "--max-instructions", "1")
        self.assertEqual(result["reason"], "instruction_limit")
        self.assertEqual(result["instructionsExecuted"], 1)
        self.assertIsNone(result["fetchStop"])

    def test_zero_budget_reports_zero_attempts(self):
        result = self.simulate([0x00], "--max-instructions", "0")
        self.assertEqual(result["reason"], "instruction_limit")
        self.assertEqual(result["instructionsExecuted"], 0)
        self.assertEqual(result["trace"], [])

    def test_bounded_loop_trace_and_stop_source_without_trace(self):
        result = self.simulate([0x4C, 0x00, 0x10], "--max-instructions", "3", "--trace-limit", "2")
        self.assertEqual(result["reason"], "instruction_limit")
        self.assertEqual(result["instructionsExecuted"], 3)
        self.assertEqual(len(result["trace"]), 2)
        self.assertTrue(result["traceTruncated"])
        result = self.simulate([0x4C, 0x00, 0x20], "--trace-limit", "0")
        self.assert_fetch_stop(result, "outside_executable_ranges", 0x2000, 0x2000, 1,
                               {"pc": 0x1000, "mnemonic": "JMP"})
        self.assertEqual(result["trace"], [])
        self.assertTrue(result["traceTruncated"])

    def test_invalid_executable_ranges_are_rejected(self):
        for span in ("0x1000", "0x1001:0x1000", "-1:0x1000", "0:0x10001", "0:0", "bad:4"):
            with self.subTest(span=span):
                # '=' delivers a leading-minus value to the type validator,
                # rather than letting argparse interpret it as another option.
                process, _ = self.invoke([0x00], "--exec-range=" + span)
                self.assertEqual(process.returncode, 2)
                self.assertIn("invalid executable range", process.stderr)

    def test_separate_leading_minus_argument_remains_rejected(self):
        process, _ = self.invoke([0x00], "--exec-range", "-1:0x1000")
        self.assertEqual(process.returncode, 2)
        self.assertIn("argument --exec-range: expected one argument", process.stderr)

    def test_prg_load_cannot_expand_memory_past_64k(self):
        process, _ = self.invoke([0xEA, 0x00], base=0xFFFF)
        self.assertEqual(process.returncode, 2)
        self.assertIn("PRG load range exceeds 16-bit address space", process.stderr)


if __name__ == "__main__":
    unittest.main()
