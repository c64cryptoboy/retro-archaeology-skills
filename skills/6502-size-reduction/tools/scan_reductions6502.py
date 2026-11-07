#!/usr/bin/env python3
"""Hash-guarded read-only CFG and 6502 size-reduction candidate scanner."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path

from cfg_reduction6502 import CFGScanConfig, CFGScanError, scan_cfg_candidates


def integer(text):
    text = text.strip()
    if text.startswith('$'):
        text = '0x' + text[1:]
    value = int(text, 0)
    if not 0 <= value <= 0xFFFF:
        raise argparse.ArgumentTypeError('address must be 0..65535')
    return value


def entry_fact(text):
    try:
        resource, raw = text.split('=', 1)
        return resource, int(raw, 0)
    except ValueError as exc:
        raise argparse.ArgumentTypeError('entry fact must be RESOURCE=VALUE') from exc


def _instruction(item):
    return {
        'address': item.pc, 'opcode': item.opcode, 'mnemonic': item.mnemonic,
        'mode': item.mode, 'length': item.length, 'bytesHex': item.data.hex(),
        'operand': item.operand,
    }


def _candidate(item):
    return {
        'rule': item.rule,
        'addressRange': [item.start, item.end_exclusive],
        'originalBytesHex': item.original_bytes.hex(),
        'replacementBytesHexCurrentLayout': item.replacement_bytes.hex(),
        'byteDelta': item.byte_delta,
        'nominalCycleDelta': item.nominal_cycle_delta,
        'timingAdmissible': item.timing_admissible,
        'proof': item.proof,
        'requirements': list(item.requirements),
        'warnings': list(item.warnings),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input')
    parser.add_argument('--report', required=True)
    parser.add_argument('--base-address', type=integer, required=True)
    parser.add_argument('--entry', action='append', type=integer, required=True)
    parser.add_argument('--entry-fact', action='append', type=entry_fact, default=[])
    parser.add_argument('--terminal-live', nargs='*', default=[
        'A', 'X', 'Y', 'SP', 'F:N', 'F:V', 'F:D', 'F:I', 'F:Z', 'F:C',
    ])
    parser.add_argument('--expected-sha256', required=True)
    parser.add_argument('--timing-policy', choices=('ordinary', 'interrupt', 'cycle-exact'),
                        default='ordinary')
    parser.add_argument('--cpu-profile', choices=('nmos6502', '6510', '2a03'),
                        default='nmos6502')
    parser.add_argument('--max-instructions', type=int, default=10000)
    parser.add_argument('--external-calls-preserve-decimal', action='store_true')
    args = parser.parse_args()

    source = Path(args.input).resolve()
    report_path = Path(args.report).resolve()
    if source == report_path:
        raise SystemExit('scan refused: input and report paths must differ')
    if report_path.exists():
        raise SystemExit('scan refused: report path must be fresh')
    data = source.read_bytes()
    digest = sha256(data).hexdigest()
    if digest != args.expected_sha256.lower():
        raise SystemExit('scan refused: input SHA-256 mismatch')

    config = CFGScanConfig(
        entries=tuple(args.entry), entry_facts=tuple(args.entry_fact),
        terminal_live=frozenset(args.terminal_live),
        timing_policy=args.timing_policy, cpu_profile=args.cpu_profile,
        max_instructions=args.max_instructions,
        external_calls_preserve_decimal=args.external_calls_preserve_decimal,
    )
    try:
        result = scan_cfg_candidates(data, base_address=args.base_address, config=config)
    except CFGScanError as exc:
        raise SystemExit(f'scan refused: {exc}')

    report = {
        'format': '6502-size-reduction-candidate-scan-v1',
        'input': {
            'path': str(source), 'size': len(data), 'sha256': digest,
            'baseAddress': args.base_address,
            'endAddressExclusive': args.base_address + len(data),
        },
        'contract': {
            'entries': list(result.entries),
            'entryFactsAppliedToExplicitEntries': dict(args.entry_fact),
            'terminalLive': sorted(args.terminal_live),
            'timingPolicy': args.timing_policy,
            'cpuProfile': args.cpu_profile,
            'maxInstructions': args.max_instructions,
            'externalCallsPreserveDecimal': args.external_calls_preserve_decimal,
        },
        'summary': {
            'instructionCount': len(result.instructions),
            'basicBlockCount': len(result.blocks),
            'edgeCount': len(result.edges),
            'candidateCount': len(result.candidates),
            'registerRehomeOptionCount': len(result.register_rehomes),
            'indexedTraversalReversalOptionCount':
                len(result.indexed_traversal_reversals),
            'timingAdmissibleCandidateCount': sum(
                item.timing_admissible for item in result.candidates
            ),
            'potentialBytesSaved': -sum(
                item.byte_delta for item in result.candidates
                if item.timing_admissible
            ),
            'limitReached': result.limit_reached,
            'issueCount': len(result.issues),
        },
        'decimalPolicy': {
            'description': result.decimal_policy,
            'clearInvariant': result.decimal_clear_invariant,
        },
        'instructions': [_instruction(item) for item in result.instructions],
        'basicBlocks': [
            {
                'start': block.start, 'endExclusive': block.end_exclusive,
                'instructionAddresses': list(block.instruction_pcs),
                'successors': list(block.successors),
            }
            for block in result.blocks
        ],
        'edges': [
            {'from': edge.source, 'to': edge.target, 'kind': edge.kind,
             'internal': edge.internal}
            for edge in result.edges
        ],
        'knownState': {
            'iterations': result.known_iterations,
            'factsIn': [
                {'address': pc, 'facts': dict(facts)}
                for pc, facts in result.known_facts_in
            ],
            'branchOutcomes': [
                {'address': pc, 'outcome': outcome}
                for pc, outcome in result.branch_outcomes
            ],
        },
        'liveness': {
            'iterations': result.liveness_iterations,
            'liveIn': [
                {'address': pc, 'resources': list(resources)}
                for pc, resources in result.live_in
            ],
            'liveOut': [
                {'address': pc, 'resources': list(resources)}
                for pc, resources in result.live_out
            ],
            'availableRegistersIn': [
                {'address': pc, 'registers': list(registers)}
                for pc, registers in result.available_in
            ],
            'availableRegistersOut': [
                {'address': pc, 'registers': list(registers)}
                for pc, registers in result.available_out
            ],
            'availableFlagsIn': [
                {'address': pc, 'flags': list(flags)}
                for pc, flags in result.available_flags_in
            ],
            'availableFlagsOut': [
                {'address': pc, 'flags': list(flags)}
                for pc, flags in result.available_flags_out
            ],
        },
        'candidates': [_candidate(item) for item in result.candidates],
        'registerRehomeOptions': [
            {
                'originalRegister': item.original_register,
                'replacementRegister': item.replacement_register,
                'producer': item.producer,
                'consumer': item.consumer,
                'intervalEndExclusive': item.interval_end_exclusive,
                'originalProducerBytesHex': item.original_producer_bytes.hex(),
                'replacementProducerBytesHex': item.replacement_producer_bytes.hex(),
                'originalConsumerBytesHex': item.original_consumer_bytes.hex(),
                'replacementConsumerBytesHex': item.replacement_consumer_bytes.hex(),
                'byteDelta': item.byte_delta,
                'nominalCycleDelta': item.nominal_cycle_delta,
                'proof': item.proof,
                'status': 'enabling option; not applied without a composed clobbering reduction',
            }
            for item in result.register_rehomes
        ],
        'indexedTraversalReversalOptions': [
            {
                'register': item.register, 'strategy': item.strategy,
                'addressRange': [item.start, item.end_exclusive],
                'startValue': item.start_value,
                'terminalValue': item.terminal_value,
                'tripCount': item.trip_count,
                'bodyInstructionAddresses': list(item.body_instruction_pcs),
                'indexUseAddresses': list(item.index_use_pcs),
                'originalBytesHex': item.original_bytes.hex(),
                'replacementBytesHexCurrentLayout': item.replacement_bytes.hex(),
                'byteDelta': item.byte_delta,
                'nominalCycleDelta': item.nominal_cycle_delta,
                'timingAdmissible': item.timing_admissible,
                'proof': item.proof,
                'semanticRequirements': list(item.semantic_requirements),
                'warnings': list(item.warnings),
                'status': 'analysis-only; requires LLM semantic acceptance and bespoke guarded integration',
            }
            for item in result.indexed_traversal_reversals
        ],
        'stops':  [{'address': pc, 'reason': reason} for pc, reason in result.stops],
        'issues': list(result.issues),
        'limitations': [
            'This is a read-only candidate scan; no bytes or references were changed.',
            'Recursive descent proves boundaries only for modeled entries and direct flow.',
            'Indirect flow, code-as-data, self-modification, banking, and missing entries require external evidence.',
            'Candidate replacement bytes use current addresses and must be regenerated after final compaction.',
            'Tail-call stack conventions and complete references remain explicit integration requirements.',
            'Candidate counts and potential savings are not an equivalence or whole-image reduction claim.',
        ],
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    print(json.dumps(report['summary'], sort_keys=True))


if __name__ == '__main__':
    main()
