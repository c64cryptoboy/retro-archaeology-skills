"""Additive offline controls.  No target, compiler, or emulator execution."""
import copy
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

LANE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LANE))
import region_evidence as pilot
from synthetic_fixture import BASE, START, VM_CONSUMER, example


class RegionalEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(os.environ['PUBLIC_TOOLKIT_ROOT'])
        cls.helpers, cls.hashes = pilot.load_helpers(cls.root)

    def run_case(self, data, worksheet):
        return pilot.analyze(data, worksheet, self.helpers, self.hashes)

    def altered_stream(self, payload, kind='vm'):
        data, worksheet = example(kind)
        data = data[:START - BASE] + payload
        worksheet['input']['sha256'] = pilot.sha(data)
        worksheet['region']['end'] = BASE + len(data)
        return data, worksheet

    def assert_unknown_origin(self, result):
        self.assertEqual(result['historicalAuthorship']['status'], 'unresolved')
        self.assertEqual(result['generationEvidence']['status'], 'none-established')
        self.assertEqual(result['mechanism']['actualReachability'], 'unknown')

    def test_annotated_consumer_bytes_and_official_opcodes_agree(self):
        # Static correspondence only, not execution or automatic semantic verification.
        kind, checked = None, 0
        for line in (LANE / 'synthetic-consumers.asm').read_text().splitlines():
            if line.startswith('; VM consumer'):
                kind = 'vm'
            elif line.startswith('; Generic direct-address-cell consumer'):
                kind = 'thread'
            elif line.startswith('; Ordinary pointer-data reader'):
                kind = 'table'
            match = re.match(r'; ([0-9A-F]{4})\s+((?:[0-9A-F]{2} ){0,2}[0-9A-F]{2})\s+([A-Z]{3})', line)
            if match:
                address, encoded, mnemonic = match.groups()
                pc, expected = int(address, 16), bytes.fromhex(encoded)
                data, _ = example(kind)
                self.assertEqual(data[pc - BASE:pc - BASE + len(expected)], expected, line)
                instruction = self.helpers['cfg'].decode(data, BASE, pc)
                self.assertEqual(instruction['mnemonic'], mnemonic, line)
                checked += 1
        self.assertEqual(checked, 45)

    def test_vm_boundaries_and_no_authorship(self):
        result = self.run_case(*example())
        mechanism = result['mechanism']
        self.assertEqual(mechanism['representationCandidate'], 'vm-opcodes')
        self.assertEqual(mechanism['stream']['status'], 'consistent')
        self.assertEqual([r['start'] for r in mechanism['stream']['records']], [0x1040, 0x1042, 0x1045])
        self.assertEqual(mechanism['stream']['unknownRanges'], [])
        self.assertEqual(result['componentIdentity']['publicBaseline']['status'], 'unknown')
        self.assertIsNotNone(mechanism['nativeStaticGraph'])
        self.assert_unknown_origin(result)

    def test_same_cells_dispatch_vs_pointer_data(self):
        threaded, tw = example('thread')
        table, pw = example('table')
        self.assertEqual(threaded[START - BASE:], table[START - BASE:])
        good = self.run_case(threaded, tw)
        no = self.run_case(table, pw)
        self.assertEqual(good['mechanism']['representationCandidate'], 'threaded-cells')
        self.assertEqual(no['mechanism']['representationCandidate'], 'unknown')
        self.assertEqual(no['mechanism']['stream']['reason'], 'supplied-consumer-is-not-a-stream-dispatcher')
        stops = good['mechanism']['nativeStaticGraph']['stops']
        self.assertTrue(any(s['reason'] == 'unresolved_indirect_jump' for s in stops))
        self.assert_unknown_origin(good)
        self.assert_unknown_origin(no)

    def test_native_call_chain_is_not_generated_statements(self):
        data, worksheet = self.altered_stream(bytes.fromhex('200010 200010 60'))
        worksheet['consumer']['operation'] = 'native-calls'
        worksheet['consumer']['representation'] = 'native'
        result = self.run_case(data, worksheet)
        self.assertEqual(result['mechanism']['representationCandidate'], 'unknown')
        self.assert_unknown_origin(result)

    def test_inline_native_call_parameters_not_automatically_pcode(self):
        data, worksheet = self.altered_stream(bytes.fromhex('200010 7f00 60'))
        worksheet['consumer'] = None
        result = self.run_case(data, worksheet)
        self.assertEqual(result['mechanism']['stream']['reason'], 'absent-consumer')
        self.assert_unknown_origin(result)

    def test_absent_consumer_with_valid_looking_stream(self):
        data, worksheet = example()
        worksheet['consumer'] = None
        result = self.run_case(data, worksheet)
        self.assertEqual(result['mechanism']['stream']['reason'], 'absent-consumer')
        self.assertEqual(result['mechanism']['representationCandidate'], 'unknown')

    def test_copied_unused_runtime_does_not_prove_application_generation(self):
        data, worksheet = self.altered_stream(bytes.fromhex('60'))
        worksheet['componentPins'] = [{
            'start': BASE, 'end': BASE + len(VM_CONSUMER), 'sha256': pilot.sha(VM_CONSUMER),
            'label': 'synthetic copied VM component', 'evidence': 'Synthetic copied bytes; no caller/consumer link supplied.'}]
        worksheet['consumer'] = None
        result = self.run_case(data, worksheet)
        self.assertTrue(result['componentIdentity']['suppliedPins'][0]['matched'])
        self.assertEqual(result['mechanism']['representationCandidate'], 'unknown')
        self.assert_unknown_origin(result)

    def test_public_identifier_exact_match_keeps_failed_layout_separate(self):
        data, worksheet = example()
        # Synthetic test-only database, never a production CLI option or private corpus.
        db = {'schema': 'basic-compiler-identities-v1', 'fingerprints': [{
            'loadAddress': BASE, 'start': BASE, 'end': BASE + len(VM_CONSUMER),
            'sha256': pilot.sha(VM_CONSUMER), 'family': 'synthetic-component',
            'role': 'runtime', 'check': 'blitz'}]}
        real_identify = self.helpers['identifier'].identify
        with patch.object(self.helpers['identifier'], 'identify',
                          side_effect=lambda blob, **kw: real_identify(blob, identities=db, **kw)):
            result = self.run_case(data, worksheet)
        baseline = result['componentIdentity']['publicBaseline']
        self.assertEqual(baseline['status'], 'identified')
        self.assertFalse(baseline['matches'][0]['layoutValid'])
        self.assertEqual(baseline['matches'][0]['layoutError'], 'unsupported BLITZ image extent')
        self.assert_unknown_origin(result)

    def test_truncated_operands(self):
        result = self.run_case(*self.altered_stream(bytes.fromhex('017f 0245')))
        stream = result['mechanism']['stream']
        self.assertEqual(stream['status'], 'refused')
        self.assertEqual(stream['violations'][0]['reason'], 'truncated-operands')
        self.assertEqual(stream['unknownRanges'], [{'start': 0x1042, 'end': 0x1044}])

    def test_truncated_two_byte_token(self):
        result = self.run_case(*self.altered_stream(bytes.fromhex('2010 24'), 'thread'))
        self.assertEqual(result['mechanism']['stream']['violations'][0]['reason'], 'truncated-token')

    def test_unknown_token_is_not_a_handwritten_fallback(self):
        result = self.run_case(*self.altered_stream(bytes.fromhex('ff')))
        self.assertEqual(result['mechanism']['representationCandidate'], 'unknown')
        self.assertEqual(result['mechanism']['stream']['violations'][0]['reason'], 'unknown-token')
        self.assert_unknown_origin(result)

    def test_unvisited_bytes_remain_unknown(self):
        result = self.run_case(*self.altered_stream(bytes.fromhex('00 ff')))
        self.assertEqual(result['mechanism']['stream']['status'], 'partial')
        self.assertEqual(result['mechanism']['stream']['unknownRanges'], [{'start': START + 1, 'end': START + 2}])
        self.assertEqual(result['mechanism']['representationCandidate'], 'unknown')

    def test_jump_into_operand_rejected(self):
        result = self.run_case(*self.altered_stream(bytes.fromhex('017f 024110 00')))
        self.assertEqual(result['mechanism']['stream']['status'], 'refused')
        self.assertEqual(result['mechanism']['stream']['violations'][0]['reason'], 'edge-into-operand')

    def test_reverse_order_overlap_rejected(self):
        data, worksheet = example()
        worksheet['region']['entries'] = [START + 1, START]
        worksheet['consumer']['contract']['rules'].append({
            'token': 0x7F, 'operandBytes': 0, 'flow': 'stop', 'evidence': 'Synthetic conflicting entry control.'})
        result = self.run_case(data, worksheet)
        self.assertEqual(result['mechanism']['stream']['status'], 'refused')
        self.assertTrue(any(v['reason'] == 'overlapping-record' for v in result['mechanism']['stream']['violations']))

    def test_branch_graph_control(self):
        data, worksheet = self.altered_stream(bytes.fromhex('034510 017f 00'))
        contract = worksheet['consumer']['contract']
        contract['rules'].append({'token': 3, 'operandBytes': 2, 'flow': 'branch',
                                  'targetOffset': 0, 'evidence': 'Synthetic boundary-algorithm rule, not VM consumer semantics.'})
        result = pilot.check_stream(data, BASE, worksheet['region'], contract)
        self.assertEqual(result['status'], 'consistent')
        self.assertEqual(result['records'][0]['successors'], [0x1045, 0x1043])

    def test_external_edge_and_fallthrough_rejected(self):
        for payload in (bytes.fromhex('020020'), bytes.fromhex('017f')):
            with self.subTest(payload=payload.hex()):
                result = self.run_case(*self.altered_stream(payload))
                self.assertEqual(result['mechanism']['stream']['violations'][0]['reason'], 'edge-outside-region')

    def test_loop_is_boundary_consistent_not_a_termination_claim(self):
        result = self.run_case(*self.altered_stream(bytes.fromhex('024010')))
        self.assertEqual(result['mechanism']['stream']['status'], 'consistent')
        self.assert_unknown_origin(result)

    def test_mismatched_consumer_bytes_abstain(self):
        data, worksheet = example()
        worksheet['consumer']['sha256'] = '0' * 64
        result = self.run_case(data, worksheet)
        self.assertEqual(result['mechanism']['stream']['reason'], 'consumer-bytes-not-matched')
        self.assertEqual(result['mechanism']['representationCandidate'], 'unknown')

    def test_supplied_reachability_not_promoted_to_observation(self):
        data, worksheet = example()
        worksheet['consumer']['reachabilityEvidence'] = 'Manual assertion that startup reaches dispatcher.'
        result = self.run_case(data, worksheet)
        self.assertEqual(result['mechanism']['consumerAssertion']['reachabilityEvidence']['status'],
                         'supplied-not-automatically-proved')
        self.assert_unknown_origin(result)

    def test_incorrect_supplied_semantics_are_not_automatically_detected(self):
        # Deliberately false dispatch assertion.  Demonstrates the documented trust boundary.
        data, worksheet = example('table')
        worksheet['consumer']['operation'] = 'dispatch'
        result = self.run_case(data, worksheet)
        self.assertEqual(result['mechanism']['stream']['status'], 'consistent')
        self.assertEqual(result['mechanism']['consumerAssertion']['evidence']['status'],
                         'supplied-not-automatically-proved')
        self.assert_unknown_origin(result)

    def test_input_identity_bounds_and_contract_guards(self):
        for mutation, message in (
            (lambda w: w['input'].update(sha256='0' * 64), 'input SHA-256'),
            (lambda w: w['region'].update(end=0x2000), 'region is not wholly'),
            (lambda w: w['region'].update(entries=[]), 'at least one'),
            (lambda w: w['consumer']['contract'].update(tokenBytes=3), 'tokenBytes'),
            (lambda w: w['consumer']['contract']['rules'].append(copy.deepcopy(w['consumer']['contract']['rules'][0])), 'duplicate token'),
        ):
            data, worksheet = example()
            mutation(worksheet)
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                self.run_case(data, worksheet)

    def test_prg_raw_equivalence(self):
        data, worksheet = example()
        raw = self.run_case(data, worksheet)
        prg = BASE.to_bytes(2, 'little') + data
        worksheet['input'].update(format='prg', sha256=pilot.sha(prg))
        result = self.run_case(prg, worksheet)
        self.assertEqual(result['mechanism'], raw['mechanism'])

    def test_cli_new_output_only(self):
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name)
            data, worksheet = example()
            binary, manifest, output = [directory / p for p in ('test.bin', 'worksheet.json', 'report.json')]
            binary.write_bytes(data)
            manifest.write_text(json.dumps(worksheet))
            command = [sys.executable, '-B', str(LANE / 'region_evidence.py'), str(binary), str(manifest),
                       '--public-root', str(self.root), '--output', str(output)]
            first = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(first.returncode, 0, first.stderr)
            before = output.read_bytes()
            second = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(second.returncode, 2)
            self.assertEqual(output.read_bytes(), before)
            self.assertEqual(binary.read_bytes(), data)
            self.assertEqual(json.loads(before)['mechanism']['stream']['status'], 'consistent')


if __name__ == '__main__':
    unittest.main()
