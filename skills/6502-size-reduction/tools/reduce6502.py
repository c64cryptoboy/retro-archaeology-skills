#!/usr/bin/env python3
"""CLI for conservative straight-line NMOS-6502 size reductions."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

from reduction_rules6502 import ReductionConfig, ReductionError, reduce_straight_block


def integer(text):
    text = text.strip()
    if text.startswith('$'):
        text = '0x' + text[1:]
    value = int(text, 0)
    if not 0 <= value <= 0xffff:
        raise argparse.ArgumentTypeError('address must be 0..65535')
    return value


def entry_fact(text):
    try:
        resource, raw = text.split('=', 1)
        return resource, int(raw, 0)
    except ValueError as exc:
        raise argparse.ArgumentTypeError('entry fact must be RESOURCE=VALUE') from exc


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('input')
    parser.add_argument('output')
    parser.add_argument('--report', required=True)
    parser.add_argument('--base-address', type=integer, required=True)
    parser.add_argument('--expected-sha256', required=True)
    parser.add_argument('--timing-policy', choices=('ordinary', 'interrupt', 'cycle-exact'),
                        default='ordinary')
    parser.add_argument('--terminal-live', nargs='*', default=[])
    parser.add_argument('--entry-fact', action='append', type=entry_fact, default=[])
    parser.add_argument('--assert-no-interior-entries', action='store_true')
    parser.add_argument('--assert-no-code-as-data', action='store_true')
    args = parser.parse_args()

    source = Path(args.input).resolve()
    output = Path(args.output).resolve()
    report_path = Path(args.report).resolve()
    if len({source, output, report_path}) != 3:
        raise SystemExit('reduction refused: input, output, and report paths must differ')
    if output.exists() or report_path.exists():
        raise SystemExit('reduction refused: output and report paths must be fresh')
    data = source.read_bytes()
    digest = sha256(data).hexdigest()
    if digest != args.expected_sha256.lower():
        raise SystemExit('reduction refused: input SHA-256 mismatch')

    try:
        result = reduce_straight_block(
            data, base_address=args.base_address,
            config=ReductionConfig(
                timing_policy=args.timing_policy,
                terminal_live=frozenset(args.terminal_live),
                entry_facts=tuple(args.entry_fact),
                assert_no_interior_entries=args.assert_no_interior_entries,
                assert_no_code_as_data=args.assert_no_code_as_data,
            ),
        )
    except ReductionError as exc:
        raise SystemExit(f'reduction refused: {exc}')

    report = {
        'format': '6502-size-reduction-report-v1',
        'input': {'path': str(source), 'size': len(data), 'sha256': digest,
                  'baseAddress': args.base_address},
        'output': {'path': str(output), 'size': len(result.reduced),
                   'sha256': sha256(result.reduced).hexdigest()},
        'contract': {
            'timingPolicy': result.timing_policy,
            'terminalLive': sorted(args.terminal_live),
            'entryFacts': dict(args.entry_fact),
            'assertNoInteriorEntries': args.assert_no_interior_entries,
            'assertNoCodeAsData': args.assert_no_code_as_data,
        },
        'summary': {
            'changed': result.reduced != result.original,
            'bytesBefore': len(result.original), 'bytesAfter': len(result.reduced),
            'byteDelta': result.byte_delta,
            'nominalCyclesBefore': result.original_cycles,
            'nominalCyclesAfter': result.reduced_cycles,
            'nominalCycleDelta': result.cycle_delta,
            'ruleCount': len(result.ledger),
        },
        'ledger': [
            {
                'rule': item.rule,
                'originalOffsetRange': [item.original_start, item.original_end],
                'originalBytesHex': item.original_bytes.hex(),
                'replacementBytesHex': item.replacement_bytes.hex(),
                'byteDelta': item.byte_delta, 'cycleDelta': item.cycle_delta,
                'proof': item.proof,
            }
            for item in result.ledger
        ],
        'warnings': list(result.warnings),
        'limitations': [
            'The caller asserted one straight-line block with no interior entries.',
            'The shorter output is raw block data; surrounding layout and references are not repaired.',
            'Nominal instruction cycles exclude hardware stalls; v1 rules never increase nominal cycles.',
            'No loop rolling, branch restructuring, NOP deletion, semantic resynthesis, or I/O timing inference is performed.',
            'Bounded testing/integration remains required; this ledger is not a whole-program equivalence proof.',
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(result.reduced)
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    print(json.dumps(report['summary'], sort_keys=True))


if __name__ == '__main__':
    main()
