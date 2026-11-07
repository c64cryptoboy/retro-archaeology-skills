#!/usr/bin/env python3
"""Compact and strictly integrate one declared non-tail 6502 image region."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path

from compaction6502 import (
    CompactionConfig, CompactionError, SmcOperandContract, compact_code_region,
)
from image_integration6502 import (
    IntegrationError, WholeImageManifest, integrate_whole_image,
)


RULES = frozenset({
    'tail-call-jsr-rts', 'known-flag-short-jump',
    'never-taken-branch-deletion', 'branch-to-fallthrough-deletion',
    'redundant-zero-compare-after-load',
    'masked-bit-test-via-shift',
    'compare-zero-unsigned-branch-fold',
    'control-only-loop-reversal',
    'compare-immediate-via-index-step', 'compare-two-via-lsr',
    'zero-compare-select-via-rehome',
    'duplicate-transfer', 'duplicate-idempotent-operation',
})


def entry_fact(text):
    try:
        resource, raw = text.split('=', 1)
        return resource, int(raw, 0)
    except ValueError as exc:
        raise argparse.ArgumentTypeError('entry fact must be RESOURCE=VALUE') from exc


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input')
    parser.add_argument('output')
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--report', required=True)
    parser.add_argument('--entry-fact', action='append', type=entry_fact, default=[])
    parser.add_argument('--terminal-live', nargs='*', default=[
        'A', 'X', 'Y', 'SP', 'F:N', 'F:V', 'F:D', 'F:I', 'F:Z', 'F:C',
    ])
    parser.add_argument('--timing-policy',
                        choices=('ordinary', 'interrupt', 'cycle-exact'),
                        default='ordinary')
    parser.add_argument('--cpu-profile',
                        choices=('nmos6502', '6510', '2a03'),
                        default='nmos6502')
    parser.add_argument('--max-instructions', type=int, default=10000)
    parser.add_argument('--external-calls-preserve-decimal', action='store_true')
    parser.add_argument('--disable-rule', action='append', default=[],
                        choices=tuple(sorted(RULES)))
    parser.add_argument('--assert-standard-jsr-rts', action='store_true')
    args = parser.parse_args()

    source = Path(args.input).resolve()
    output = Path(args.output).resolve()
    manifest_path = Path(args.manifest).resolve()
    report_path = Path(args.report).resolve()
    if len({source, output, manifest_path, report_path}) != 4:
        raise SystemExit(
            'whole-image integration refused: input/output/manifest/report must differ'
        )
    if output.exists() or report_path.exists():
        raise SystemExit(
            'whole-image integration refused: output and report must be fresh'
        )
    image = source.read_bytes()
    manifest_bytes = manifest_path.read_bytes()
    try:
        manifest_value = json.loads(manifest_bytes)
        manifest = WholeImageManifest.from_dict(manifest_value)
    except (json.JSONDecodeError, IntegrationError) as exc:
        raise SystemExit(f'whole-image integration refused: {exc}') from exc
    if manifest.image_size != len(image):
        raise SystemExit('whole-image integration refused: image size mismatch')
    if sha256(image).hexdigest() != manifest.image_sha256:
        raise SystemExit('whole-image integration refused: image SHA-256 mismatch')

    region_start = manifest.region_start - manifest.image_base
    region_end = manifest.region_end_exclusive - manifest.image_base
    region = image[region_start:region_end]
    smc_contracts = tuple(SmcOperandContract(
        item.instruction_address,
        item.field_address - item.instruction_address,
        item.width,
    ) for item in manifest.smc_operand_fields
        if manifest.region_start <= item.instruction_address
        < manifest.region_end_exclusive)
    config = CompactionConfig(
        entries=manifest.entries,
        entry_facts=tuple(args.entry_fact),
        terminal_live=frozenset(args.terminal_live),
        timing_policy=args.timing_policy,
        cpu_profile=args.cpu_profile,
        max_instructions=args.max_instructions,
        external_calls_preserve_decimal=args.external_calls_preserve_decimal,
        enabled_rules=RULES - set(args.disable_rule),
        assert_complete_code_region=manifest.assert_compacted_region_all_code,
        assert_all_incoming_references_repairable=
            manifest.assert_all_references_declared,
        assert_no_code_as_data=manifest.assert_no_region_code_as_data,
        assert_no_self_modifying_code=not smc_contracts,
        declared_smc_operand_fields=smc_contracts,
        assert_no_undeclared_self_modifying_code=
            manifest.assert_no_undeclared_smc if smc_contracts else False,
        assert_standard_jsr_rts=args.assert_standard_jsr_rts,
    )
    try:
        compaction = compact_code_region(
            region, base_address=manifest.region_start, config=config
        )
        result = integrate_whole_image(image, manifest, compaction)
    except (CompactionError, IntegrationError, ValueError) as exc:
        raise SystemExit(f'whole-image integration refused: {exc}') from exc

    report = {
        'format': '6502-whole-image-integration-report-v2',
        'input': {
            'path': str(source), 'size': len(image),
            'sha256': sha256(image).hexdigest(),
            'baseAddress': manifest.image_base,
        },
        'manifest': {
            'path': str(manifest_path),
            'sha256': sha256(manifest_bytes).hexdigest(),
        },
        'output': {
            'path': str(output), 'size': len(result.integrated),
            'sha256': result.output_sha256,
            'baseAddress': manifest.image_base,
        },
        'compaction': {
            'originalRange': [manifest.region_start,
                              manifest.region_end_exclusive],
            'finalRange': [manifest.region_start,
                           manifest.region_start + len(compaction.compacted)],
            'byteDelta': compaction.byte_delta,
            'timingPolicy': compaction.timing_policy,
            'applied': [
                {
                    'rule': item.rule,
                    'originalRange': [item.original_start,
                                      item.original_end_exclusive],
                    'finalRange': [item.final_start, item.final_end_exclusive],
                    'byteDelta': item.byte_delta,
                    'nominalCycleDelta': item.nominal_cycle_delta,
                    'originalBytesHex': item.original_bytes.hex(),
                    'finalBytesHex': item.final_bytes.hex(),
                    'proof': item.proof,
                }
                for item in compaction.applied
            ],
        },
        'integration': {
            'reclaimedBytes': result.reclaimed_bytes,
            'relocatedEntries': [
                {'original': old, 'final': final}
                for old, final in result.relocated_entries
            ],
            'referencePatches': [
                {
                    'name': item.name, 'kind': item.kind,
                    'sourceOriginal': item.source_original,
                    'sourceFinal': item.source_final,
                    'targetOriginal': item.target_original,
                    'targetFinal': item.target_final,
                    'encoding': item.encoding,
                    'originalBytesHex': item.original_bytes.hex(),
                    'finalBytesHex': item.final_bytes.hex(),
                }
                for item in result.relocation_patches
            ],
            'movedRanges': [
                {
                    'name': item.name, 'kind': item.kind,
                    'originalRange': [item.original_start,
                                      item.original_end_exclusive],
                    'finalRange': [item.final_start, item.final_end_exclusive],
                    'sha256': item.sha256,
                }
                for item in result.moved_ranges
            ],
            'smcFieldRelocations': [
                {
                    'name': item.name,
                    'instructionOriginal': item.instruction_original,
                    'instructionFinal': item.instruction_final,
                    'fieldOriginal': item.field_original,
                    'fieldFinal': item.field_final,
                    'width': item.width,
                }
                for item in result.smc_field_relocations
            ],
            'fixedAnchors': [
                {
                    'name': item.name,
                    'originalAddress': item.original_address,
                    'finalAddress': item.final_address,
                    'bytesHex': item.bytes.hex(),
                }
                for item in result.fixed_anchor_checks
            ],
            'changeAuthorizations': [
                {
                    'kind': item.kind,
                    'originalRange': [item.original_start,
                                      item.original_end_exclusive],
                    'finalRange': [item.final_start, item.final_end_exclusive],
                    'detail': item.detail,
                }
                for item in result.change_authorizations
            ],
            'changedByteCount': result.changed_byte_count,
            'changedAddresses': list(result.changed_addresses),
            'unauthorizedChangedAddresses':
                list(result.unauthorized_changed_addresses),
        },
        'limitations': [
            'Exactly one complete all-code compacted region is supported.',
            'Every suffix byte must belong to a hash-guarded shifted range.',
            'Reference and fixed-anchor completeness remain explicit caller assertions.',
            'Opaque/mixed shifted ranges move byte-for-byte and are not decoded.',
            'Fixed anchors that would move are refused rather than padded around.',
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(result.integrated)
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    print(json.dumps({
        'bytesBefore': len(image), 'bytesAfter': len(result.integrated),
        'reclaimedBytes': result.reclaimed_bytes,
        'referencePatches': len(result.relocation_patches),
        'changedByteCount': result.changed_byte_count,
    }, sort_keys=True))


if __name__ == '__main__':
    main()
