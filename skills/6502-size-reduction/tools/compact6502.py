#!/usr/bin/env python3
"""Hash-guarded packed compaction of one complete declared 6502 code region."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path

from compaction6502 import (
    CompactionConfig, CompactionError, SmcOperandContract, compact_code_region,
)


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


def smc_field(text):
    try:
        instruction, offset, width = text.split(':', 2)
        return SmcOperandContract(integer(instruction), int(offset, 0), int(width, 0))
    except (ValueError, CompactionError) as exc:
        raise argparse.ArgumentTypeError(
            'SMC field must be INSTRUCTION:OPERAND_OFFSET:WIDTH'
        ) from exc


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input')
    parser.add_argument('output')
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
    parser.add_argument('--disable-rule', action='append', default=[], choices=(
        'tail-call-jsr-rts', 'known-flag-short-jump',
        'never-taken-branch-deletion', 'branch-to-fallthrough-deletion',
        'redundant-zero-compare-after-load',
        'masked-bit-test-via-shift',
        'compare-zero-unsigned-branch-fold',
        'control-only-loop-reversal',
        'compare-immediate-via-index-step', 'compare-two-via-lsr',
        'zero-compare-select-via-rehome',
        'duplicate-transfer', 'duplicate-idempotent-operation',
    ))
    parser.add_argument('--assert-complete-code-region', action='store_true')
    parser.add_argument('--assert-all-incoming-references-repairable', action='store_true')
    parser.add_argument('--assert-no-code-as-data', action='store_true')
    parser.add_argument('--assert-no-self-modifying-code', action='store_true')
    parser.add_argument('--declared-smc-field', action='append', type=smc_field,
                        default=[])
    parser.add_argument('--assert-no-undeclared-self-modifying-code',
                        action='store_true')
    parser.add_argument('--assert-standard-jsr-rts', action='store_true')
    args = parser.parse_args()

    source = Path(args.input).resolve()
    output = Path(args.output).resolve()
    report_path = Path(args.report).resolve()
    if len({source, output, report_path}) != 3:
        raise SystemExit('compaction refused: input, output, and report paths must differ')
    if output.exists() or report_path.exists():
        raise SystemExit('compaction refused: output and report paths must be fresh')
    original = source.read_bytes()
    digest = sha256(original).hexdigest()
    if digest != args.expected_sha256.lower():
        raise SystemExit('compaction refused: input SHA-256 mismatch')

    enabled = {
        'tail-call-jsr-rts', 'known-flag-short-jump',
        'never-taken-branch-deletion', 'branch-to-fallthrough-deletion',
        'redundant-zero-compare-after-load',
        'masked-bit-test-via-shift',
        'compare-zero-unsigned-branch-fold',
        'control-only-loop-reversal',
        'compare-immediate-via-index-step', 'compare-two-via-lsr',
        'zero-compare-select-via-rehome',
        'duplicate-transfer', 'duplicate-idempotent-operation',
    } - set(args.disable_rule)
    config = CompactionConfig(
        entries=tuple(args.entry), entry_facts=tuple(args.entry_fact),
        terminal_live=frozenset(args.terminal_live),
        timing_policy=args.timing_policy, cpu_profile=args.cpu_profile,
        max_instructions=args.max_instructions,
        external_calls_preserve_decimal=args.external_calls_preserve_decimal,
        enabled_rules=frozenset(enabled),
        assert_complete_code_region=args.assert_complete_code_region,
        assert_all_incoming_references_repairable=
            args.assert_all_incoming_references_repairable,
        assert_no_code_as_data=args.assert_no_code_as_data,
        assert_no_self_modifying_code=args.assert_no_self_modifying_code,
        declared_smc_operand_fields=tuple(args.declared_smc_field),
        assert_no_undeclared_self_modifying_code=
            args.assert_no_undeclared_self_modifying_code,
        assert_standard_jsr_rts=args.assert_standard_jsr_rts,
    )
    try:
        result = compact_code_region(
            original, base_address=args.base_address, config=config
        )
    except (CompactionError, ValueError) as exc:
        raise SystemExit(f'compaction refused: {exc}')

    compacted_digest = sha256(result.compacted).hexdigest()
    report = {
        'format': '6502-packed-code-compaction-report-v1',
        'input': {
            'path': str(source), 'size': len(original), 'sha256': digest,
            'baseAddress': args.base_address,
            'endAddressExclusive': args.base_address + len(original),
        },
        'output': {
            'path': str(output), 'size': len(result.compacted),
            'sha256': compacted_digest, 'baseAddress': args.base_address,
            'endAddressExclusive': args.base_address + len(result.compacted),
        },
        'contract': {
            'entries': list(args.entry),
            'entryFacts': dict(args.entry_fact),
            'terminalLive': sorted(args.terminal_live),
            'timingPolicy': args.timing_policy,
            'cpuProfile': args.cpu_profile,
            'enabledRules': sorted(enabled),
            'externalCallsPreserveDecimal': args.external_calls_preserve_decimal,
            'assertCompleteCodeRegion': args.assert_complete_code_region,
            'assertAllIncomingReferencesRepairable':
                args.assert_all_incoming_references_repairable,
            'assertNoCodeAsData': args.assert_no_code_as_data,
            'assertNoSelfModifyingCode': args.assert_no_self_modifying_code,
            'declaredSmcOperandFields': [
                {
                    'instructionAddress': item.instruction_address,
                    'operandOffset': item.operand_offset,
                    'width': item.width,
                }
                for item in args.declared_smc_field
            ],
            'assertNoUndeclaredSelfModifyingCode':
                args.assert_no_undeclared_self_modifying_code,
            'assertStandardJsrRts': args.assert_standard_jsr_rts,
        },
        'summary': {
            'bytesBefore': len(original), 'bytesAfter': len(result.compacted),
            'byteDelta': result.byte_delta,
            'scannerCandidateCount': result.scanner_candidate_count,
            'appliedCount': len(result.applied),
            'referenceRepairCount': len(result.reference_repairs),
            'entryRelocationCount': sum(old != new for old, new in result.relocated_entries),
            'appliedNominalCycleDeltaSum': sum(
                item.nominal_cycle_delta for item in result.applied
            ),
            'retainedTakenBranchPageCrossCycleDeltaSum': sum(
                item.taken_page_cross_delta for item in result.reference_repairs
                if item.kind in {
                    'relative-control', 'compare-lowering-branch',
                    'rehome-composed-branch',
                }
            ),
        },
        'relocatedEntries': [
            {'original': old, 'final': new} for old, new in result.relocated_entries
        ],
        'addressMap': [
            {'original': old, 'final': new} for old, new in result.address_map
        ],
        'applied': [
            {
                'rule': item.rule,
                'originalRange': [item.original_start, item.original_end_exclusive],
                'finalRange': [item.final_start, item.final_end_exclusive],
                'originalBytesHex': item.original_bytes.hex(),
                'finalBytesHex': item.final_bytes.hex(),
                'byteDelta': item.byte_delta,
                'nominalCycleDelta': item.nominal_cycle_delta,
                'proof': item.proof,
            }
            for item in result.applied
        ],
        'referenceRepairs': [
            {
                'mnemonic': item.mnemonic, 'kind': item.kind,
                'originalSource': item.original_source,
                'finalSource': item.final_source,
                'originalTarget': item.original_target,
                'finalTarget': item.final_target,
                'originalBytesHex': item.original_bytes.hex(),
                'finalBytesHex': item.final_bytes.hex(),
                'takenPageCrossCycleDelta': item.taken_page_cross_delta,
            }
            for item in result.reference_repairs
        ],
        'provenance': [
            {
                'originalRange': [item.original_start, item.original_end_exclusive],
                'finalRange': [item.final_start, item.final_end_exclusive],
                'kind': item.kind,
            }
            for item in result.provenance
        ],
        'warnings': list(result.warnings),
        'limitations': [
            'Only the declared packed code region is emitted; surrounding image integration remains external.',
            'Declared relocated entries require every external incoming reference to be repaired by the caller.',
            'Only direct relative/JSR/JMP control references are regenerated.',
            'No data pointers, vectors, code-as-data, self-modification, indirect flow, or banking are repaired.',
            'NOPs and visible unrolling are preserved.',
            'The result proves guarded mechanical layout, not whole-program equivalence.',
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(result.compacted)
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    print(json.dumps(report['summary'], sort_keys=True))


if __name__ == '__main__':
    main()
