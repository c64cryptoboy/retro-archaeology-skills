#!/usr/bin/env python3

from dataclasses import replace
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
    CompactionConfig, CompactionError, SmcOperandContract, compact_code_region,
)
from image_integration6502 import (  # noqa: E402
    IntegrationError, SequentialIntegrationStage, TailRegionManifest,
    WholeImageManifest, integrate_tail_region, integrate_whole_image,
    integrate_whole_image_sequence,
)
from routine_runner import InitialState, RoutineSpec, run_routine  # noqa: E402


def run_image(image, *, base=0x8000, entry=0x8000):
    memory = bytearray(65536)
    memory[base:base + len(image)] = image
    memory[0x20] = 5
    return run_routine(
        RoutineSpec(entry, {0x9000}, 100),
        InitialState(bytes(memory), a=0x55, x=0x66, y=0x77,
                     sp=0xFF, flags=0xA1),
    )


class ImageIntegration6502Tests(unittest.TestCase):
    def fixture(self):
        prefix = bytes.fromhex('20 15 80') + bytes((0xEA,)) * 13
        region = bytes.fromhex('a9 01 4c 19 80 20 1d 80 60 ea ea ea 60 60')
        image = prefix + region
        compaction = compact_code_region(
            region, base_address=0x8010,
            config=CompactionConfig(
                entries=(0x8010, 0x8015),
                assert_complete_code_region=True,
                assert_all_incoming_references_repairable=True,
                assert_no_code_as_data=True,
                assert_no_self_modifying_code=True,
                assert_standard_jsr_rts=True,
            ),
        )
        manifest = TailRegionManifest.from_dict({
            'imageSha256': sha256(image).hexdigest(),
            'imageBase': 0x8000, 'imageSize': len(image),
            'regionStart': 0x8010,
            'regionEndExclusive': 0x8000 + len(image),
            'entries': [0x8010, 0x8015],
            'incomingReferences': [{
                'source': 0x8001, 'target': 0x8015,
                'encoding': 'abs16-le', 'expectedBytesHex': '1580',
            }],
        })
        return image, region, compaction, manifest

    def test_integrates_shorter_tail_and_patches_incoming_reference(self):
        image, _region, compaction, manifest = self.fixture()
        result = integrate_tail_region(image, manifest, compaction)
        self.assertEqual(result.reclaimed_tail_bytes, 2)
        self.assertEqual(result.integrated[1:3], bytes.fromhex('14 80'))
        self.assertEqual(result.integrated[:1] + result.integrated[3:16],
                         image[:1] + image[3:16])
        self.assertEqual(result.integrated[16:], compaction.compacted)
        self.assertEqual((result.incoming_patches[0].target_original,
                          result.incoming_patches[0].target_final),
                         (0x8015, 0x8014))

    def test_manifest_and_expected_byte_guards_refuse(self):
        image, _region, compaction, manifest = self.fixture()
        bad_hash = TailRegionManifest(
            '0' * 64, manifest.image_base, manifest.image_size,
            manifest.region_start, manifest.region_end_exclusive,
            manifest.entries, manifest.incoming_references,
        )
        with self.assertRaisesRegex(IntegrationError, 'SHA-256'):
            integrate_tail_region(image, bad_hash, compaction)

        changed = bytearray(image); changed[1] ^= 1
        changed_manifest = TailRegionManifest(
            sha256(changed).hexdigest(), manifest.image_base, manifest.image_size,
            manifest.region_start, manifest.region_end_exclusive,
            manifest.entries, manifest.incoming_references,
        )
        with self.assertRaisesRegex(IntegrationError, 'bytes mismatch'):
            integrate_tail_region(bytes(changed), changed_manifest, compaction)

        with self.assertRaisesRegex(IntegrationError, 'end at image end'):
            TailRegionManifest.from_dict({
                'imageSha256': sha256(image).hexdigest(),
                'imageBase': 0x8000, 'imageSize': len(image),
                'regionStart': 0x8010, 'regionEndExclusive': 0x801D,
                'entries': [0x8010], 'incomingReferences': [],
            })


class WholeImageIntegration6502Tests(unittest.TestCase):
    def whole_fixture(self):
        base = 0x8000
        prefix = (bytes.fromhex(
            '20 10 80'       # JSR compacted region
            '20 1e 80'       # JSR suffix routine
            '4c 00 90'       # fixed external exit
        ) + bytes((0xEA,)) * 5
            + bytes.fromhex('d0 0e'))  # unreachable rel8 reference to suffix
        region = bytes.fromhex(
            'a9 01 4c 19 80'  # known-Z absolute jump
            '20 1d 80 60'     # private JSR/RTS tail call
            'ea ea ea 60 60'
        )
        suffix_code = bytes.fromhex('e6 20 60')
        suffix_data = bytes.fromhex(
            '15 80'  # pointer to second region entry
            '1e 80'  # pointer to suffix entry
            '1e 80'  # split low/high pointer to suffix entry
            '44 55'
        )
        suffix_mixed = bytes.fromhex('aa bb cc dd')
        suffix_vector = bytes.fromhex('1e 80')
        image = prefix + region + suffix_code + suffix_data + suffix_mixed + suffix_vector
        self.assertEqual(len(prefix), 0x10)
        self.assertEqual(len(region), 0x0E)
        self.assertEqual(len(image), 0x2F)
        compaction = compact_code_region(
            region, base_address=0x8010,
            config=CompactionConfig(
                entries=(0x8010, 0x8015),
                assert_complete_code_region=True,
                assert_all_incoming_references_repairable=True,
                assert_no_code_as_data=True,
                assert_no_self_modifying_code=True,
                assert_standard_jsr_rts=True,
            ),
        )
        self.assertEqual(compaction.byte_delta, -2)
        ranges = (
            ('suffix-code', 0x801E, 0x8021, 'code'),
            ('pointer-data', 0x8021, 0x8029, 'data'),
            ('mixed-record', 0x8029, 0x802D, 'mixed'),
            ('vector-data', 0x802D, 0x802F, 'data'),
        )
        range_items = []
        for name, start, end, kind in ranges:
            payload = image[start - base:end - base]
            range_items.append({
                'name': name, 'start': start, 'endExclusive': end,
                'kind': kind, 'expectedSha256': sha256(payload).hexdigest(),
            })
        manifest_dict = {
            'imageSha256': sha256(image).hexdigest(),
            'imageBase': base, 'imageSize': len(image),
            'regionStart': 0x8010, 'regionEndExclusive': 0x801E,
            'entries': [0x8010, 0x8015],
            'shiftedRanges': range_items,
            'references': [
                {'name': 'caller-region', 'source': 0x8001, 'target': 0x8010,
                 'encoding': 'abs16-le', 'expectedBytesHex': '1080',
                 'kind': 'caller'},
                {'name': 'caller-suffix', 'source': 0x8004, 'target': 0x801E,
                 'encoding': 'abs16-le', 'expectedBytesHex': '1e80',
                 'kind': 'caller'},
                {'name': 'relative-suffix', 'source': 0x800F, 'target': 0x801E,
                 'encoding': 'rel8', 'expectedBytesHex': '0e',
                 'kind': 'caller'},
                {'name': 'region-pointer', 'source': 0x8021, 'target': 0x8015,
                 'encoding': 'abs16-le', 'expectedBytesHex': '1580',
                 'kind': 'pointer'},
                {'name': 'suffix-pointer', 'source': 0x8023, 'target': 0x801E,
                 'encoding': 'abs16-le', 'expectedBytesHex': '1e80',
                 'kind': 'pointer'},
                {'name': 'suffix-split-low', 'source': 0x8025, 'target': 0x801E,
                 'encoding': 'low8', 'expectedBytesHex': '1e',
                 'kind': 'split-pointer', 'group': 'suffix-split'},
                {'name': 'suffix-split-high', 'source': 0x8026, 'target': 0x801E,
                 'encoding': 'high8', 'expectedBytesHex': '80',
                 'kind': 'split-pointer', 'group': 'suffix-split'},
                {'name': 'suffix-vector', 'source': 0x802D, 'target': 0x801E,
                 'encoding': 'abs16-le', 'expectedBytesHex': '1e80',
                 'kind': 'vector'},
            ],
            'fixedAnchors': [{
                'name': 'external-exit-jump', 'address': 0x8006,
                'expectedBytesHex': '4c0090',
            }],
            'smcOperandFields': [],
            'assertCompactedRegionAllCode': True,
            'assertNoRegionCodeAsData': True,
            'assertShiftedRangesComplete': True,
            'assertAllReferencesDeclared': True,
            'assertFixedAnchorsComplete': True,
            'assertNoUndeclaredSmc': True,
            'assertWholeImageChangesAuthorized': True,
        }
        return image, compaction, manifest_dict

    def test_non_tail_integration_repairs_callers_pointers_vectors_and_mixed_suffix(self):
        image, compaction, manifest_dict = self.whole_fixture()
        manifest = WholeImageManifest.from_dict(manifest_dict)
        result = integrate_whole_image(image, manifest, compaction)
        self.assertEqual((result.reclaimed_bytes, len(result.integrated)),
                         (2, len(image) - 2))
        self.assertFalse(result.unauthorized_changed_addresses)
        self.assertEqual(result.changed_byte_count, len(result.changed_addresses))
        self.assertGreater(result.changed_byte_count, 0)
        patches = {item.name: item for item in result.relocation_patches}
        self.assertEqual((patches['caller-suffix'].source_final,
                          patches['caller-suffix'].target_final,
                          patches['caller-suffix'].final_bytes),
                         (0x8004, 0x801C, bytes.fromhex('1c80')))
        self.assertEqual((patches['relative-suffix'].source_final,
                          patches['relative-suffix'].target_final,
                          patches['relative-suffix'].final_bytes),
                         (0x800F, 0x801C, bytes.fromhex('0c')))
        self.assertEqual((patches['region-pointer'].source_final,
                          patches['region-pointer'].target_final),
                         (0x801F, 0x8014))
        self.assertEqual((patches['suffix-vector'].source_final,
                          patches['suffix-vector'].target_final),
                         (0x802B, 0x801C))
        self.assertEqual({item.kind for item in result.moved_ranges},
                         {'code', 'data', 'mixed'})
        mixed = next(item for item in result.moved_ranges
                     if item.name == 'mixed-record')
        self.assertEqual(
            result.integrated[mixed.final_start - 0x8000:
                              mixed.final_end_exclusive - 0x8000],
            image[mixed.original_start - 0x8000:
                  mixed.original_end_exclusive - 0x8000],
        )
        self.assertEqual(result.fixed_anchor_checks[0].final_address, 0x8006)
        self.assertEqual(
            {item.kind for item in result.change_authorizations},
            {'compacted-region', 'shifted-range', 'reference-patch', 'truncation'},
        )

    def test_whole_image_cli_writes_fresh_artifact_and_exact_audit(self):
        image, _compaction, manifest_dict = self.whole_fixture()
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            source = directory / 'input.bin'
            manifest = directory / 'manifest.json'
            output = directory / 'output.bin'
            report = directory / 'report.json'
            source.write_bytes(image)
            manifest.write_text(json.dumps(manifest_dict))
            command = [
                sys.executable, str(TOOLS / 'integrate_whole6502.py'),
                str(source), str(output), '--manifest', str(manifest),
                '--report', str(report), '--assert-standard-jsr-rts',
            ]
            completed = subprocess.run(command, text=True, capture_output=True)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            evidence = json.loads(report.read_text())
            self.assertEqual(evidence['format'],
                             '6502-whole-image-integration-report-v2')
            self.assertEqual(evidence['integration']['reclaimedBytes'], 2)
            self.assertEqual(
                evidence['integration']['changedByteCount'],
                len(evidence['integration']['changedAddresses']),
            )
            self.assertFalse(
                evidence['integration']['unauthorizedChangedAddresses']
            )
            self.assertEqual(sha256(output.read_bytes()).hexdigest(),
                             evidence['output']['sha256'])
            repeated = subprocess.run(command, text=True, capture_output=True)
            self.assertNotEqual(repeated.returncode, 0)
            self.assertIn('fresh', repeated.stderr)

    def test_hash_chained_sequential_integration_combines_two_regions(self):
        base = 0x8000
        prefix = bytes.fromhex(
            '20 09 80'       # call first region
            '20 11 80'       # call second region
            '4c 00 90'       # fixed external exit
        )
        first_region = bytes.fromhex('a5 10 c9 00 d0 01 60 60')
        second_region = bytes.fromhex('c9 00 b0 01 60 60')
        image = prefix + first_region + second_region
        config1 = CompactionConfig(
            entries=(0x8009,), terminal_live=frozenset({'SP'}),
            assert_complete_code_region=True,
            assert_all_incoming_references_repairable=True,
            assert_no_code_as_data=True,
            assert_no_self_modifying_code=True,
        )
        manifest1 = WholeImageManifest.from_dict({
            'imageSha256': sha256(image).hexdigest(),
            'imageBase': base, 'imageSize': len(image),
            'regionStart': 0x8009, 'regionEndExclusive': 0x8011,
            'entries': [0x8009],
            'shiftedRanges': [{
                'name': 'second-code', 'start': 0x8011,
                'endExclusive': 0x8017, 'kind': 'code',
                'expectedSha256': sha256(second_region).hexdigest(),
            }],
            'references': [
                {'name': 'first-caller', 'source': 0x8001,
                 'target': 0x8009, 'encoding': 'abs16-le',
                 'expectedBytesHex': '0980', 'kind': 'caller'},
                {'name': 'second-caller', 'source': 0x8004,
                 'target': 0x8011, 'encoding': 'abs16-le',
                 'expectedBytesHex': '1180', 'kind': 'caller'},
            ],
            'fixedAnchors': [{
                'name': 'exit', 'address': 0x8006,
                'expectedBytesHex': '4c0090',
            }],
            'smcOperandFields': [],
            'assertCompactedRegionAllCode': True,
            'assertNoRegionCodeAsData': True,
            'assertShiftedRangesComplete': True,
            'assertAllReferencesDeclared': True,
            'assertFixedAnchorsComplete': True,
            'assertNoUndeclaredSmc': True,
            'assertWholeImageChangesAuthorized': True,
        })
        first_compaction = compact_code_region(
            first_region, base_address=0x8009, config=config1
        )
        first_output = integrate_whole_image(
            image, manifest1, first_compaction
        ).integrated
        self.assertEqual(first_output[0x8004 - base:0x8006 - base],
                         bytes.fromhex('0f80'))

        config2 = CompactionConfig(
            entries=(0x800F,), terminal_live=frozenset({'SP'}),
            assert_complete_code_region=True,
            assert_all_incoming_references_repairable=True,
            assert_no_code_as_data=True,
            assert_no_self_modifying_code=True,
        )
        manifest2 = WholeImageManifest.from_dict({
            'imageSha256': sha256(first_output).hexdigest(),
            'imageBase': base, 'imageSize': len(first_output),
            'regionStart': 0x800F, 'regionEndExclusive': 0x8015,
            'entries': [0x800F], 'shiftedRanges': [],
            'references': [{
                'name': 'second-caller', 'source': 0x8004,
                'target': 0x800F, 'encoding': 'abs16-le',
                'expectedBytesHex': '0f80', 'kind': 'caller',
            }],
            'fixedAnchors': [{
                'name': 'exit', 'address': 0x8006,
                'expectedBytesHex': '4c0090',
            }],
            'smcOperandFields': [],
            'assertCompactedRegionAllCode': True,
            'assertNoRegionCodeAsData': True,
            'assertShiftedRangesComplete': True,
            'assertAllReferencesDeclared': True,
            'assertFixedAnchorsComplete': True,
            'assertNoUndeclaredSmc': True,
            'assertWholeImageChangesAuthorized': True,
        })
        stages = (
            SequentialIntegrationStage('matching-load-zero', manifest1, config1),
            SequentialIntegrationStage('unsigned-zero-fold', manifest2, config2),
        )
        result = integrate_whole_image_sequence(image, stages)
        self.assertEqual(result.reclaimed_bytes, 3)
        self.assertEqual(result.integrated,
                         bytes.fromhex(
                             '20 09 80 20 0f 80 4c 00 90 '
                             'a5 10 d0 01 60 60 4c 13 80 60 60'
                         ))
        self.assertEqual(
            [(item.name, item.integration.reclaimed_bytes,
              item.input_sha256, item.output_sha256)
             for item in result.stages],
            [('matching-load-zero', 2, sha256(image).hexdigest(),
              sha256(first_output).hexdigest()),
             ('unsigned-zero-fold', 1, sha256(first_output).hexdigest(),
              result.output_sha256)],
        )
        left = run_image(image)
        right = run_image(result.integrated)
        self.assertEqual(
            (left.final.pc, left.final.a, left.final.x, left.final.y,
             left.final.sp, left.final.flags, left.final.memory[0x20]),
            (right.final.pc, right.final.a, right.final.x, right.final.y,
             right.final.sp, right.final.flags, right.final.memory[0x20]),
        )
        self.assertEqual(right.final.cycles, left.final.cycles - 4)

        bad_chain = replace(manifest2, image_sha256='0' * 64)
        with self.assertRaisesRegex(IntegrationError, 'exact output'):
            integrate_whole_image_sequence(image, (
                stages[0], SequentialIntegrationStage(
                    'bad-chain', bad_chain, config2
                ),
            ))
        with self.assertRaisesRegex(IntegrationError, 'nonempty and unique'):
            integrate_whole_image_sequence(image, (stages[0], stages[0]))
        with self.assertRaisesRegex(IntegrationError, 'at least one stage'):
            integrate_whole_image_sequence(image, ())

    def test_compacted_external_rel8_is_repatched_for_shifted_target(self):
        base = 0x8000
        region = bytes.fromhex('a5 10 c9 00 d0 03')
        suffix = bytes.fromhex('ea ea ea 60')
        image = region + suffix
        compaction = compact_code_region(
            region, base_address=base,
            config=CompactionConfig(
                entries=(base,),
                terminal_live=frozenset({'A', 'SP', 'F:N', 'F:Z'}),
                assert_complete_code_region=True,
                assert_all_incoming_references_repairable=True,
                assert_no_code_as_data=True,
                assert_no_self_modifying_code=True,
            ),
        )
        self.assertEqual(compaction.compacted,
                         bytes.fromhex('a5 10 d0 05'))
        manifest = WholeImageManifest.from_dict({
            'imageSha256': sha256(image).hexdigest(),
            'imageBase': base, 'imageSize': len(image),
            'regionStart': base, 'regionEndExclusive': 0x8006,
            'entries': [base],
            'shiftedRanges': [{
                'name': 'suffix-code', 'start': 0x8006,
                'endExclusive': 0x800A, 'kind': 'code',
                'expectedSha256': sha256(suffix).hexdigest(),
            }],
            'references': [{
                'name': 'retained-external-branch', 'source': 0x8005,
                'target': 0x8009, 'encoding': 'rel8',
                'expectedBytesHex': '03', 'kind': 'other',
            }],
            'fixedAnchors': [], 'smcOperandFields': [],
            'assertCompactedRegionAllCode': True,
            'assertNoRegionCodeAsData': True,
            'assertShiftedRangesComplete': True,
            'assertAllReferencesDeclared': True,
            'assertFixedAnchorsComplete': True,
            'assertNoUndeclaredSmc': True,
            'assertWholeImageChangesAuthorized': True,
        })
        result = integrate_whole_image(image, manifest, compaction)
        self.assertEqual(result.integrated,
                         bytes.fromhex('a5 10 d0 03 ea ea ea 60'))
        patch = result.relocation_patches[0]
        self.assertEqual((patch.source_original, patch.source_final,
                          patch.target_original, patch.target_final,
                          patch.original_bytes, patch.final_bytes),
                         (0x8005, 0x8003, 0x8009, 0x8007,
                          bytes.fromhex('03'), bytes.fromhex('03')))

    def test_connected_final_address_execution_matches(self):
        image, compaction, manifest_dict = self.whole_fixture()
        result = integrate_whole_image(
            image, WholeImageManifest.from_dict(manifest_dict), compaction
        )
        left = run_image(image)
        right = run_image(result.integrated)
        self.assertEqual(
            (left.final.pc, left.final.a, left.final.x, left.final.y,
             left.final.sp, left.final.flags, left.final.memory[0x20],
             left.final.cycles),
            (right.final.pc, right.final.a, right.final.x, right.final.y,
             right.final.sp, right.final.flags, right.final.memory[0x20],
             right.final.cycles),
        )

    def smc_fixture(self):
        base = 0x8000
        prefix = bytes.fromhex(
            'a9 de'          # LDA #$DE
            '8d 17 80'       # patch low operand byte at old $8017
            'a9 42'
            '20 10 80'       # call region
            '4c 00 90'
        ) + bytes((0xEA,)) * 3
        region = bytes.fromhex(
            'a9 00 d0 00'    # known never-taken branch, removed
            'a9 42'
            '8d de c0'       # SMC operand field $8017-$8018
            '60'
        )
        suffix = bytes.fromhex('18 80 11 22')
        image = prefix + region + suffix
        smc_contract = SmcOperandContract(0x8016, 1, 2)
        compaction = compact_code_region(
            region, base_address=0x8010,
            config=CompactionConfig(
                entries=(0x8010,),
                assert_complete_code_region=True,
                assert_all_incoming_references_repairable=True,
                assert_no_code_as_data=True,
                declared_smc_operand_fields=(smc_contract,),
                assert_no_undeclared_self_modifying_code=True,
            ),
        )
        self.assertEqual(compaction.byte_delta, -2)
        manifest_dict = {
            'imageSha256': sha256(image).hexdigest(),
            'imageBase': base, 'imageSize': len(image),
            'regionStart': 0x8010, 'regionEndExclusive': 0x801A,
            'entries': [0x8010],
            'shiftedRanges': [{
                'name': 'suffix-data', 'start': 0x801A, 'endExclusive': 0x801E,
                'kind': 'data',
                'expectedSha256': sha256(suffix).hexdigest(),
            }],
            'references': [
                {'name': 'smc-low-writer', 'source': 0x8003, 'target': 0x8017,
                 'encoding': 'abs16-le', 'expectedBytesHex': '1780',
                 'kind': 'smc-writer'},
                {'name': 'region-caller', 'source': 0x8008, 'target': 0x8010,
                 'encoding': 'abs16-le', 'expectedBytesHex': '1080',
                 'kind': 'caller'},
                {'name': 'smc-high-writer', 'source': 0x801A, 'target': 0x8018,
                 'encoding': 'abs16-le', 'expectedBytesHex': '1880',
                 'kind': 'smc-writer'},
            ],
            'fixedAnchors': [{
                'name': 'exit-jump', 'address': 0x800A,
                'expectedBytesHex': '4c0090',
            }],
            'smcOperandFields': [{
                'name': 'draw-target', 'instructionAddress': 0x8016,
                'fieldAddress': 0x8017, 'width': 2,
                'expectedBytesHex': 'dec0',
            }],
            'assertCompactedRegionAllCode': True,
            'assertNoRegionCodeAsData': True,
            'assertShiftedRangesComplete': True,
            'assertAllReferencesDeclared': True,
            'assertFixedAnchorsComplete': True,
            'assertNoUndeclaredSmc': True,
            'assertWholeImageChangesAuthorized': True,
        }
        return image, compaction, manifest_dict

    def test_declared_smc_field_in_shifted_code_range_relocates(self):
        base = 0x9000
        region = bytes.fromhex('a9 00 d0 00 a9 42 60')
        suffix = bytes.fromhex(
            'a9 12 8d 12 90'  # preserve low byte of suffix SMC field
            'a9 90 8d 13 90'  # preserve high byte
            '8d de c0 60'      # shifted SMC instruction and field
        )
        image = region + suffix
        compaction = compact_code_region(
            region, base_address=base,
            config=CompactionConfig(
                entries=(base,), assert_complete_code_region=True,
                assert_all_incoming_references_repairable=True,
                assert_no_code_as_data=True,
                assert_no_self_modifying_code=True,
            ),
        )
        manifest = WholeImageManifest.from_dict({
            'imageSha256': sha256(image).hexdigest(),
            'imageBase': base, 'imageSize': len(image),
            'regionStart': base, 'regionEndExclusive': 0x9007,
            'entries': [base],
            'shiftedRanges': [{
                'name': 'suffix-code', 'start': 0x9007,
                'endExclusive': 0x9015, 'kind': 'code',
                'expectedSha256': sha256(suffix).hexdigest(),
            }],
            'references': [
                {'name': 'suffix-smc-low', 'source': 0x900A,
                 'target': 0x9012, 'encoding': 'abs16-le',
                 'expectedBytesHex': '1290', 'kind': 'smc-writer'},
                {'name': 'suffix-smc-high', 'source': 0x900F,
                 'target': 0x9013, 'encoding': 'abs16-le',
                 'expectedBytesHex': '1390', 'kind': 'smc-writer'},
            ],
            'fixedAnchors': [],
            'smcOperandFields': [{
                'name': 'suffix-target', 'instructionAddress': 0x9011,
                'fieldAddress': 0x9012, 'width': 2,
                'expectedBytesHex': 'dec0',
            }],
            'assertCompactedRegionAllCode': True,
            'assertNoRegionCodeAsData': True,
            'assertShiftedRangesComplete': True,
            'assertAllReferencesDeclared': True,
            'assertFixedAnchorsComplete': True,
            'assertNoUndeclaredSmc': True,
            'assertWholeImageChangesAuthorized': True,
        })
        result = integrate_whole_image(image, manifest, compaction)
        field = result.smc_field_relocations[0]
        self.assertEqual((field.instruction_original, field.instruction_final,
                          field.field_original, field.field_final),
                         (0x9011, 0x900F, 0x9012, 0x9010))
        patches = {item.name: item for item in result.relocation_patches}
        self.assertEqual(patches['suffix-smc-low'].final_bytes,
                         bytes.fromhex('1090'))
        self.assertEqual(patches['suffix-smc-high'].final_bytes,
                         bytes.fromhex('1190'))

    def test_declared_smc_field_and_writer_relocate_and_execute(self):
        image, compaction, manifest_dict = self.smc_fixture()
        result = integrate_whole_image(
            image, WholeImageManifest.from_dict(manifest_dict), compaction
        )
        self.assertEqual(len(result.smc_field_relocations), 1)
        field = result.smc_field_relocations[0]
        self.assertEqual((field.instruction_original, field.instruction_final,
                          field.field_original, field.field_final),
                         (0x8016, 0x8014, 0x8017, 0x8015))
        patches = {item.name: item for item in result.relocation_patches}
        self.assertEqual((patches['smc-low-writer'].target_final,
                          patches['smc-low-writer'].final_bytes),
                         (0x8015, bytes.fromhex('1580')))
        self.assertEqual((patches['smc-high-writer'].source_final,
                          patches['smc-high-writer'].target_final,
                          patches['smc-high-writer'].final_bytes),
                         (0x8018, 0x8016, bytes.fromhex('1680')))
        left = run_image(image)
        right = run_image(result.integrated)
        self.assertEqual(
            (left.final.pc, left.final.a, left.final.x, left.final.y,
             left.final.sp, left.final.flags, left.final.memory[0xC0DE]),
            (right.final.pc, right.final.a, right.final.x, right.final.y,
             right.final.sp, right.final.flags, right.final.memory[0xC0DE]),
        )
        self.assertLess(right.final.cycles, left.final.cycles)

    def test_manifest_refuses_gaps_split_errors_missing_assertions_and_unknown_fields(self):
        _image, _compaction, valid = self.whole_fixture()
        bad = dict(valid)
        bad['shiftedRanges'] = [dict(item) for item in valid['shiftedRanges']]
        bad['shiftedRanges'][1]['start'] += 1
        with self.assertRaisesRegex(IntegrationError, 'contiguously cover'):
            WholeImageManifest.from_dict(bad)

        bad = dict(valid)
        bad['references'] = [dict(item) for item in valid['references']
                             if item['name'] != 'suffix-split-high']
        with self.assertRaisesRegex(IntegrationError, 'matching low8/high8'):
            WholeImageManifest.from_dict(bad)

        bad = dict(valid); bad['assertAllReferencesDeclared'] = False
        with self.assertRaisesRegex(IntegrationError, 'explicit true assertions'):
            WholeImageManifest.from_dict(bad)

        bad = dict(valid); bad['surprise'] = True
        with self.assertRaisesRegex(IntegrationError, 'unknown fields'):
            WholeImageManifest.from_dict(bad)

    def test_hash_reference_anchor_and_smc_guards_refuse(self):
        image, compaction, valid = self.whole_fixture()
        bad = dict(valid)
        bad['shiftedRanges'] = [dict(item) for item in valid['shiftedRanges']]
        bad['shiftedRanges'][2]['expectedSha256'] = '0' * 64
        with self.assertRaisesRegex(IntegrationError, 'SHA-256 mismatch'):
            integrate_whole_image(
                image, WholeImageManifest.from_dict(bad), compaction
            )

        bad = dict(valid)
        bad['references'] = [dict(item) for item in valid['references']]
        bad['references'][0]['expectedBytesHex'] = '1180'
        with self.assertRaisesRegex(IntegrationError, 'reference bytes mismatch'):
            integrate_whole_image(
                image, WholeImageManifest.from_dict(bad), compaction
            )

        bad = dict(valid)
        bad['fixedAnchors'] = [{
            'name': 'suffix-must-not-move', 'address': 0x801E,
            'expectedBytesHex': 'e62060',
        }]
        with self.assertRaisesRegex(IntegrationError, 'would move'):
            integrate_whole_image(
                image, WholeImageManifest.from_dict(bad), compaction
            )

        smc_image, smc_compaction, smc_valid = self.smc_fixture()
        bad = dict(smc_valid); bad['smcOperandFields'] = []
        with self.assertRaisesRegex(IntegrationError, 'SMC field requires'):
            WholeImageManifest.from_dict(bad)
        bad = dict(smc_valid)
        bad['smcOperandFields'] = [dict(smc_valid['smcOperandFields'][0])]
        bad['smcOperandFields'][0]['expectedBytesHex'] = 'dfc0'
        with self.assertRaisesRegex(IntegrationError, 'SMC field bytes mismatch'):
            integrate_whole_image(
                smc_image, WholeImageManifest.from_dict(bad), smc_compaction
            )

    def test_compactor_smc_contract_refusals(self):
        region = bytes.fromhex('a9 00 d0 00 a9 42 8d de c0 60')
        common = dict(
            entries=(0x8010,), assert_complete_code_region=True,
            assert_all_incoming_references_repairable=True,
            assert_no_code_as_data=True,
        )
        with self.assertRaisesRegex(CompactionError, 'no-undeclared-SMC'):
            CompactionConfig(
                **common,
                declared_smc_operand_fields=(SmcOperandContract(0x8016, 1, 2),),
            )
        with self.assertRaisesRegex(CompactionError, 'conflicts'):
            CompactionConfig(
                **common, assert_no_self_modifying_code=True,
                declared_smc_operand_fields=(SmcOperandContract(0x8016, 1, 2),),
                assert_no_undeclared_self_modifying_code=True,
            )
        with self.assertRaisesRegex(CompactionError, 'exceeds instruction'):
            compact_code_region(
                region, base_address=0x8010,
                config=CompactionConfig(
                    **common,
                    declared_smc_operand_fields=(SmcOperandContract(0x8016, 2, 2),),
                    assert_no_undeclared_self_modifying_code=True,
                ),
            )


if __name__ == '__main__':
    unittest.main()
