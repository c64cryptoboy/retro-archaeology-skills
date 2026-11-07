#!/usr/bin/env python3
"""Strict manifest-driven integration of compacted 6502 code regions.

V1 retains the original end-of-image tail contract. V2 supports one compacted
non-tail all-code region followed by exhaustively declared bytewise-shifted
code/data/mixed ranges. Every relocated reference, SMC operand field, fixed
anchor, and changed byte remains guarded and ledgered.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from string import hexdigits
from typing import Mapping

from compaction6502 import (
    CompactionConfig, CompactionResult, compact_code_region,
)


class IntegrationError(ValueError):
    pass


def _valid_sha256(value: str) -> bool:
    return (len(value) == 64
            and all(character in hexdigits for character in value))


def _strict_keys(value: Mapping, allowed: set[str], context: str):
    unknown = set(value) - allowed
    if unknown:
        raise IntegrationError(
            f'{context} contains unknown fields: {sorted(unknown)}'
        )


@dataclass(frozen=True)
class IncomingReference:
    source: int
    target: int
    encoding: str
    expected_bytes: bytes


@dataclass(frozen=True)
class TailRegionManifest:
    image_sha256: str
    image_base: int
    image_size: int
    region_start: int
    region_end_exclusive: int
    entries: tuple[int, ...]
    incoming_references: tuple[IncomingReference, ...]
    fill_byte: int = 0

    @classmethod
    def from_dict(cls, value: Mapping):
        try:
            references = tuple(IncomingReference(
                int(item['source']), int(item['target']), str(item['encoding']),
                bytes.fromhex(item['expectedBytesHex']),
            ) for item in value.get('incomingReferences', ()))
            manifest = cls(
                str(value['imageSha256']).lower(), int(value['imageBase']),
                int(value['imageSize']), int(value['regionStart']),
                int(value['regionEndExclusive']),
                tuple(int(item) for item in value['entries']), references,
                int(value.get('fillByte', 0)),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise IntegrationError(f'invalid integration manifest: {exc}') from exc
        manifest.validate_shape()
        return manifest

    def validate_shape(self):
        image_end = self.image_base + self.image_size
        if not _valid_sha256(self.image_sha256):
            raise IntegrationError('manifest imageSha256 must be 64 hexadecimal digits')
        if not 0 <= self.image_base <= 0xFFFF or image_end > 0x10000:
            raise IntegrationError('manifest image does not fit 16-bit address space')
        if self.region_end_exclusive != image_end:
            raise IntegrationError('v1 requires the packed region to end at image end')
        if not self.image_base <= self.region_start < self.region_end_exclusive:
            raise IntegrationError('invalid tail region range')
        if not self.entries or any(not self.region_start <= item < self.region_end_exclusive
                                   for item in self.entries):
            raise IntegrationError('every declared entry must be inside the tail region')
        if len(set(self.entries)) != len(self.entries):
            raise IntegrationError('declared entries must be unique')
        if not 0 <= self.fill_byte <= 0xFF:
            raise IntegrationError('fillByte must be 0..255')
        seen = set()
        lengths = {'abs16-le': 2, 'low8': 1, 'high8': 1, 'rel8': 1}
        for reference in self.incoming_references:
            if reference.encoding not in lengths:
                raise IntegrationError(f'unsupported incoming encoding {reference.encoding}')
            if len(reference.expected_bytes) != lengths[reference.encoding]:
                raise IntegrationError('incoming expected-byte length does not match encoding')
            if not self.image_base <= reference.source < self.region_start:
                raise IntegrationError('v1 incoming reference source must precede the tail region')
            if reference.source + lengths[reference.encoding] > self.region_start:
                raise IntegrationError('incoming reference overlaps the tail region')
            if not self.region_start <= reference.target < self.region_end_exclusive:
                raise IntegrationError('incoming reference target must be in the tail region')
            occupied = set(range(reference.source, reference.source + lengths[reference.encoding]))
            if seen & occupied:
                raise IntegrationError('incoming reference byte ranges overlap')
            seen |= occupied


@dataclass(frozen=True)
class IncomingPatch:
    source: int
    target_original: int
    target_final: int
    encoding: str
    original_bytes: bytes
    final_bytes: bytes


@dataclass(frozen=True)
class ImageIntegrationResult:
    original: bytes
    integrated: bytes
    manifest: TailRegionManifest
    incoming_patches: tuple[IncomingPatch, ...]
    reclaimed_tail_bytes: int


def _encode_tail(reference: IncomingReference, final_target: int) -> bytes:
    if reference.encoding == 'abs16-le':
        return bytes((final_target & 0xFF, final_target >> 8))
    if reference.encoding == 'low8':
        return bytes((final_target & 0xFF,))
    if reference.encoding == 'high8':
        return bytes((final_target >> 8,))
    raw = (final_target - ((reference.source + 1) & 0xFFFF)) & 0xFFFF
    if raw <= 0x7F:
        displacement = raw
    elif raw >= 0xFF80:
        displacement = raw - 0x10000
    else:
        raise IntegrationError(
            f'final incoming branch at ${reference.source - 1:04X} is out of range'
        )
    return bytes((displacement & 0xFF,))


def integrate_tail_region(image: bytes, manifest: TailRegionManifest,
                          compaction: CompactionResult) -> ImageIntegrationResult:
    image = bytes(image)
    manifest.validate_shape()
    if len(image) != manifest.image_size:
        raise IntegrationError('image size does not match manifest')
    if sha256(image).hexdigest() != manifest.image_sha256:
        raise IntegrationError('image SHA-256 does not match manifest')
    if compaction.base_address != manifest.region_start:
        raise IntegrationError('compaction base does not match manifest regionStart')
    region_offset = manifest.region_start - manifest.image_base
    if compaction.original != image[region_offset:]:
        raise IntegrationError('compaction original bytes do not match the image tail region')
    if tuple(compaction.entries) != manifest.entries:
        raise IntegrationError('compaction entries do not match manifest entries')
    address_map = dict(compaction.address_map)
    output = bytearray(image[:region_offset])
    patches = []
    for reference in manifest.incoming_references:
        offset = reference.source - manifest.image_base
        actual = bytes(output[offset:offset + len(reference.expected_bytes)])
        if actual != reference.expected_bytes:
            raise IntegrationError(
                f'incoming reference bytes mismatch at ${reference.source:04X}'
            )
        if reference.target not in address_map:
            raise IntegrationError(
                f'incoming target ${reference.target:04X} has no compaction mapping'
            )
        final_target = address_map[reference.target]
        final = _encode_tail(reference, final_target)
        output[offset:offset + len(final)] = final
        patches.append(IncomingPatch(
            reference.source, reference.target, final_target,
            reference.encoding, actual, final,
        ))
    output.extend(compaction.compacted)
    integrated = bytes(output)
    reclaimed = len(image) - len(integrated)
    if reclaimed != -compaction.byte_delta or reclaimed < 0:
        raise AssertionError('tail integration size ledger does not balance')
    return ImageIntegrationResult(
        image, integrated, manifest, tuple(patches), reclaimed,
    )


# V2 non-tail whole-image integration.

_REFERENCE_ENCODINGS = {'abs16-le': 2, 'low8': 1, 'high8': 1, 'rel8': 1}
_REFERENCE_KINDS = {
    'caller', 'vector', 'pointer', 'split-pointer', 'smc-writer', 'other',
}
_SHIFTED_KINDS = {'code', 'data', 'mixed', 'opaque'}


@dataclass(frozen=True)
class ShiftedRange:
    name: str
    start: int
    end_exclusive: int
    kind: str
    expected_sha256: str


@dataclass(frozen=True)
class RelocationReference:
    name: str
    source: int
    target: int
    encoding: str
    expected_bytes: bytes
    kind: str
    group: str | None = None


@dataclass(frozen=True)
class FixedAnchor:
    name: str
    address: int
    expected_bytes: bytes


@dataclass(frozen=True)
class SmcOperandField:
    name: str
    instruction_address: int
    field_address: int
    width: int
    expected_bytes: bytes


@dataclass(frozen=True)
class WholeImageManifest:
    image_sha256: str
    image_base: int
    image_size: int
    region_start: int
    region_end_exclusive: int
    entries: tuple[int, ...]
    shifted_ranges: tuple[ShiftedRange, ...]
    references: tuple[RelocationReference, ...]
    fixed_anchors: tuple[FixedAnchor, ...]
    smc_operand_fields: tuple[SmcOperandField, ...]
    assert_compacted_region_all_code: bool
    assert_no_region_code_as_data: bool
    assert_shifted_ranges_complete: bool
    assert_all_references_declared: bool
    assert_fixed_anchors_complete: bool
    assert_no_undeclared_smc: bool
    assert_whole_image_changes_authorized: bool

    @classmethod
    def from_dict(cls, value: Mapping):
        if not isinstance(value, Mapping):
            raise IntegrationError('whole-image manifest must be an object')
        allowed = {
            'imageSha256', 'imageBase', 'imageSize', 'regionStart',
            'regionEndExclusive', 'entries', 'shiftedRanges', 'references',
            'fixedAnchors', 'smcOperandFields',
            'assertCompactedRegionAllCode', 'assertNoRegionCodeAsData',
            'assertShiftedRangesComplete', 'assertAllReferencesDeclared',
            'assertFixedAnchorsComplete', 'assertNoUndeclaredSmc',
            'assertWholeImageChangesAuthorized',
        }
        _strict_keys(value, allowed, 'whole-image manifest')
        try:
            shifted = []
            for item in value.get('shiftedRanges', ()):
                _strict_keys(item, {'name', 'start', 'endExclusive', 'kind',
                                    'expectedSha256'}, 'shifted range')
                shifted.append(ShiftedRange(
                    str(item['name']), int(item['start']), int(item['endExclusive']),
                    str(item['kind']), str(item['expectedSha256']).lower(),
                ))
            references = []
            for item in value.get('references', ()):
                _strict_keys(item, {'name', 'source', 'target', 'encoding',
                                    'expectedBytesHex', 'kind', 'group'},
                             'relocation reference')
                references.append(RelocationReference(
                    str(item['name']), int(item['source']), int(item['target']),
                    str(item['encoding']), bytes.fromhex(item['expectedBytesHex']),
                    str(item['kind']),
                    (str(item['group']) if item.get('group') is not None else None),
                ))
            anchors = []
            for item in value.get('fixedAnchors', ()):
                _strict_keys(item, {'name', 'address', 'expectedBytesHex'},
                             'fixed anchor')
                anchors.append(FixedAnchor(
                    str(item['name']), int(item['address']),
                    bytes.fromhex(item['expectedBytesHex']),
                ))
            smc_fields = []
            for item in value.get('smcOperandFields', ()):
                _strict_keys(item, {'name', 'instructionAddress', 'fieldAddress',
                                    'width', 'expectedBytesHex'},
                             'SMC operand field')
                smc_fields.append(SmcOperandField(
                    str(item['name']), int(item['instructionAddress']),
                    int(item['fieldAddress']), int(item['width']),
                    bytes.fromhex(item['expectedBytesHex']),
                ))
            assertion_keys = (
                'assertCompactedRegionAllCode', 'assertNoRegionCodeAsData',
                'assertShiftedRangesComplete', 'assertAllReferencesDeclared',
                'assertFixedAnchorsComplete', 'assertNoUndeclaredSmc',
                'assertWholeImageChangesAuthorized',
            )
            for key in assertion_keys:
                if type(value.get(key)) is not bool:
                    raise IntegrationError(f'{key} must be a JSON boolean')
            manifest = cls(
                str(value['imageSha256']).lower(), int(value['imageBase']),
                int(value['imageSize']), int(value['regionStart']),
                int(value['regionEndExclusive']),
                tuple(int(item) for item in value['entries']), tuple(shifted),
                tuple(references), tuple(anchors), tuple(smc_fields),
                value['assertCompactedRegionAllCode'],
                value['assertNoRegionCodeAsData'],
                value['assertShiftedRangesComplete'],
                value['assertAllReferencesDeclared'],
                value['assertFixedAnchorsComplete'],
                value['assertNoUndeclaredSmc'],
                value['assertWholeImageChangesAuthorized'],
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise IntegrationError(f'invalid whole-image manifest: {exc}') from exc
        manifest.validate_shape()
        return manifest

    def validate_shape(self):
        image_end = self.image_base + self.image_size
        if not _valid_sha256(self.image_sha256):
            raise IntegrationError('imageSha256 must be 64 hexadecimal digits')
        if not 0 <= self.image_base <= 0xFFFF or image_end > 0x10000:
            raise IntegrationError('manifest image does not fit 16-bit address space')
        if not self.image_base <= self.region_start < self.region_end_exclusive <= image_end:
            raise IntegrationError('invalid compacted region range')
        if not self.entries or len(set(self.entries)) != len(self.entries):
            raise IntegrationError('compacted-region entries must be nonempty and unique')
        if any(not self.region_start <= entry < self.region_end_exclusive
               for entry in self.entries):
            raise IntegrationError('every entry must be inside the compacted region')
        assertions = {
            'assertCompactedRegionAllCode': self.assert_compacted_region_all_code,
            'assertNoRegionCodeAsData': self.assert_no_region_code_as_data,
            'assertShiftedRangesComplete': self.assert_shifted_ranges_complete,
            'assertAllReferencesDeclared': self.assert_all_references_declared,
            'assertFixedAnchorsComplete': self.assert_fixed_anchors_complete,
            'assertNoUndeclaredSmc': self.assert_no_undeclared_smc,
            'assertWholeImageChangesAuthorized':
                self.assert_whole_image_changes_authorized,
        }
        missing = [name for name, enabled in assertions.items() if not enabled]
        if missing:
            raise IntegrationError(
                'whole-image manifest requires explicit true assertions: '
                + ', '.join(missing)
            )

        names = []
        cursor = self.region_end_exclusive
        for item in sorted(self.shifted_ranges, key=lambda value: value.start):
            names.append(item.name)
            if not item.name or item.kind not in _SHIFTED_KINDS:
                raise IntegrationError('shifted ranges require names and valid kinds')
            if item.start != cursor or not item.start < item.end_exclusive <= image_end:
                raise IntegrationError(
                    'shifted ranges must exactly and contiguously cover the suffix'
                )
            if not _valid_sha256(item.expected_sha256):
                raise IntegrationError('shifted range expectedSha256 is invalid')
            cursor = item.end_exclusive
        if cursor != image_end:
            raise IntegrationError(
                'shifted ranges must exactly and contiguously cover the suffix'
            )
        if len(names) != len(set(names)):
            raise IntegrationError('shifted range names must be unique')

        source_bytes = set()
        reference_names = set()
        split_groups: dict[str, list[RelocationReference]] = {}
        for item in self.references:
            if not item.name or item.name in reference_names:
                raise IntegrationError('reference names must be nonempty and unique')
            reference_names.add(item.name)
            length = _REFERENCE_ENCODINGS.get(item.encoding)
            if length is None or item.kind not in _REFERENCE_KINDS:
                raise IntegrationError('reference encoding or kind is unsupported')
            if len(item.expected_bytes) != length:
                raise IntegrationError('reference expected-byte length mismatch')
            if not self.image_base <= item.source < image_end \
                    or item.source + length > image_end:
                raise IntegrationError('reference source is outside the image')
            if not self.image_base <= item.target < image_end:
                raise IntegrationError('reference target is outside the image')
            occupied = set(range(item.source, item.source + length))
            if source_bytes & occupied:
                raise IntegrationError('reference source byte ranges overlap')
            source_bytes |= occupied
            if item.kind == 'split-pointer':
                if not item.group:
                    raise IntegrationError('split-pointer references require a group')
                split_groups.setdefault(item.group, []).append(item)
            elif item.group is not None:
                raise IntegrationError('only split-pointer references may declare a group')
        for group, items in split_groups.items():
            if (len(items) != 2 or {item.encoding for item in items} != {'low8', 'high8'}
                    or len({item.target for item in items}) != 1):
                raise IntegrationError(
                    f'split-pointer group {group!r} must contain matching low8/high8 targets'
                )

        anchor_names = set()
        for item in self.fixed_anchors:
            if not item.name or item.name in anchor_names or not item.expected_bytes:
                raise IntegrationError('fixed anchors require unique names and bytes')
            anchor_names.add(item.name)
            if not self.image_base <= item.address < image_end \
                    or item.address + len(item.expected_bytes) > image_end:
                raise IntegrationError('fixed anchor is outside the image')

        smc_names = set()
        smc_bytes = set()
        for item in self.smc_operand_fields:
            if not item.name or item.name in smc_names:
                raise IntegrationError('SMC field names must be nonempty and unique')
            smc_names.add(item.name)
            if item.width not in {1, 2} or len(item.expected_bytes) != item.width:
                raise IntegrationError('SMC field width/expected bytes mismatch')
            in_compacted_region = (
                self.region_start <= item.instruction_address
                < self.region_end_exclusive
                and item.instruction_address < item.field_address
                and item.field_address + item.width <= self.region_end_exclusive
            )
            owning_shifted_ranges = [
                shifted for shifted in self.shifted_ranges
                if shifted.start <= item.instruction_address < item.field_address
                and item.field_address + item.width <= shifted.end_exclusive
            ]
            in_shifted_code = (
                len(owning_shifted_ranges) == 1
                and owning_shifted_ranges[0].kind == 'code'
            )
            if not (in_compacted_region or in_shifted_code):
                raise IntegrationError(
                    'SMC instruction/operand must be in the compacted region '
                    'or one shifted code range'
                )
            occupied = set(range(item.field_address, item.field_address + item.width))
            if smc_bytes & occupied:
                raise IntegrationError('SMC operand fields overlap')
            smc_bytes |= occupied
        declared_smc_target_bytes = {
            address
            for item in self.smc_operand_fields
            for address in range(item.field_address, item.field_address + item.width)
        }
        writer_targets = {
            item.target for item in self.references if item.kind == 'smc-writer'
        }
        if not writer_targets <= declared_smc_target_bytes or any(
                not writer_targets.intersection(
                    range(item.field_address, item.field_address + item.width)
                ) for item in self.smc_operand_fields):
            raise IntegrationError(
                'every SMC field requires declared writer references and no undeclared writer target'
            )


@dataclass(frozen=True)
class RelocationPatch:
    name: str
    kind: str
    source_original: int
    source_final: int
    target_original: int
    target_final: int
    encoding: str
    original_bytes: bytes
    final_bytes: bytes


@dataclass(frozen=True)
class MovedRange:
    name: str
    kind: str
    original_start: int
    original_end_exclusive: int
    final_start: int
    final_end_exclusive: int
    sha256: str


@dataclass(frozen=True)
class SmcFieldRelocation:
    name: str
    instruction_original: int
    instruction_final: int
    field_original: int
    field_final: int
    width: int


@dataclass(frozen=True)
class AnchorCheck:
    name: str
    original_address: int
    final_address: int
    bytes: bytes


@dataclass(frozen=True)
class ChangeAuthorization:
    kind: str
    original_start: int
    original_end_exclusive: int
    final_start: int
    final_end_exclusive: int
    detail: str


@dataclass(frozen=True)
class WholeImageIntegrationResult:
    original: bytes
    integrated: bytes
    manifest: WholeImageManifest
    relocated_entries: tuple[tuple[int, int], ...]
    relocation_patches: tuple[RelocationPatch, ...]
    moved_ranges: tuple[MovedRange, ...]
    smc_field_relocations: tuple[SmcFieldRelocation, ...]
    fixed_anchor_checks: tuple[AnchorCheck, ...]
    change_authorizations: tuple[ChangeAuthorization, ...]
    changed_addresses: tuple[int, ...]
    changed_byte_count: int
    unauthorized_changed_addresses: tuple[int, ...]
    reclaimed_bytes: int
    output_sha256: str


@dataclass(frozen=True)
class SequentialIntegrationStage:
    """One strict V2 stage expressed against the preceding stage output."""

    name: str
    manifest: WholeImageManifest
    compaction_config: CompactionConfig


@dataclass(frozen=True)
class SequentialStageResult:
    name: str
    input_sha256: str
    output_sha256: str
    compaction: CompactionResult
    integration: WholeImageIntegrationResult


@dataclass(frozen=True)
class SequentialIntegrationResult:
    original: bytes
    integrated: bytes
    stages: tuple[SequentialStageResult, ...]
    reclaimed_bytes: int
    changed_addresses: tuple[int, ...]
    changed_byte_count: int
    output_sha256: str


def _map_region_byte(address: int, compaction: CompactionResult) -> int:
    mapping = dict(compaction.address_map)
    if address in mapping:
        return mapping[address]
    for span in compaction.provenance:
        if (span.kind == 'copied-instruction'
                and span.original_start <= address < span.original_end_exclusive
                and (span.original_end_exclusive - span.original_start
                     == span.final_end_exclusive - span.final_start)):
            return span.final_start + (address - span.original_start)
    raise IntegrationError(
        f'compacted-region byte ${address:04X} has no stable final provenance'
    )


def _map_address(address: int, manifest: WholeImageManifest,
                 compaction: CompactionResult,
                 smc_map: Mapping[int, int]) -> int:
    if address < manifest.region_start:
        return address
    if address >= manifest.region_end_exclusive:
        return address + compaction.byte_delta
    if address in smc_map:
        return smc_map[address]
    return _map_region_byte(address, compaction)


def _map_byte_range(start: int, length: int, manifest: WholeImageManifest,
                    compaction: CompactionResult,
                    smc_map: Mapping[int, int]) -> int:
    mapped = tuple(
        _map_address(start + offset, manifest, compaction, smc_map)
        for offset in range(length)
    )
    if mapped != tuple(range(mapped[0], mapped[0] + length)):
        raise IntegrationError(
            f'reference bytes at ${start:04X} do not map contiguously'
        )
    return mapped[0]


def _encode_reference(reference: RelocationReference, final_source: int,
                      final_target: int) -> bytes:
    if reference.encoding == 'abs16-le':
        return bytes((final_target & 0xFF, final_target >> 8))
    if reference.encoding == 'low8':
        return bytes((final_target & 0xFF,))
    if reference.encoding == 'high8':
        return bytes((final_target >> 8,))
    raw = (final_target - ((final_source + 1) & 0xFFFF)) & 0xFFFF
    if raw <= 0x7F:
        displacement = raw
    elif raw >= 0xFF80:
        displacement = raw - 0x10000
    else:
        raise IntegrationError(
            f'final relative reference {reference.name!r} at '
            f'${final_source - 1:04X} is out of range'
        )
    return bytes((displacement & 0xFF,))


def integrate_whole_image(image: bytes, manifest: WholeImageManifest,
                          compaction: CompactionResult) -> WholeImageIntegrationResult:
    """Integrate one compacted non-tail region and audit the entire image."""
    image = bytes(image)
    manifest.validate_shape()
    image_end = manifest.image_base + manifest.image_size
    if len(image) != manifest.image_size:
        raise IntegrationError('image size does not match whole-image manifest')
    if sha256(image).hexdigest() != manifest.image_sha256:
        raise IntegrationError('image SHA-256 does not match whole-image manifest')
    if compaction.base_address != manifest.region_start:
        raise IntegrationError('compaction base does not match regionStart')
    region_offset = manifest.region_start - manifest.image_base
    region_end_offset = manifest.region_end_exclusive - manifest.image_base
    if compaction.original != image[region_offset:region_end_offset]:
        raise IntegrationError('compaction original does not match declared image region')
    if tuple(compaction.entries) != manifest.entries:
        raise IntegrationError('compaction entries do not match manifest entries')
    if compaction.byte_delta >= 0:
        raise IntegrationError('whole-image integration requires a shorter compacted region')

    for item in manifest.shifted_ranges:
        payload = image[item.start - manifest.image_base:
                        item.end_exclusive - manifest.image_base]
        if sha256(payload).hexdigest() != item.expected_sha256:
            raise IntegrationError(
                f'shifted range {item.name!r} SHA-256 mismatch'
            )

    declared_compaction_smc = {
        (item.instruction_address,
         item.instruction_address + item.operand_offset,
         item.width)
        for item in compaction.declared_smc_operand_fields
    }
    manifest_smc = {
        (item.instruction_address, item.field_address, item.width)
        for item in manifest.smc_operand_fields
        if manifest.region_start <= item.instruction_address
        < manifest.region_end_exclusive
    }
    if declared_compaction_smc != manifest_smc:
        raise IntegrationError(
            'compaction and whole-image SMC operand declarations differ'
        )

    prefix = image[:region_offset]
    suffix = image[region_end_offset:]
    output = bytearray(prefix + compaction.compacted + suffix)
    if len(output) != len(image) + compaction.byte_delta:
        raise AssertionError('whole-image size ledger does not balance')

    smc_map = {}
    smc_relocations = []
    address_map = dict(compaction.address_map)
    for item in manifest.smc_operand_fields:
        old = image[item.field_address - manifest.image_base:
                    item.field_address - manifest.image_base + item.width]
        if old != item.expected_bytes:
            raise IntegrationError(
                f'SMC field bytes mismatch for {item.name!r}'
            )
        if manifest.region_start <= item.instruction_address \
                < manifest.region_end_exclusive:
            instruction_final = address_map.get(item.instruction_address)
            if instruction_final is None:
                raise IntegrationError(
                    f'SMC instruction ${item.instruction_address:04X} has no final mapping'
                )
            field_offset = item.field_address - item.instruction_address
            field_final = instruction_final + field_offset
        else:
            instruction_final = _map_address(
                item.instruction_address, manifest, compaction, smc_map
            )
            field_final = _map_address(
                item.field_address, manifest, compaction, smc_map
            )
            if field_final - instruction_final != (
                    item.field_address - item.instruction_address):
                raise IntegrationError(
                    f'SMC field {item.name!r} did not relocate with its instruction'
                )
        final_offset = field_final - manifest.image_base
        if bytes(output[final_offset:final_offset + item.width]) != item.expected_bytes:
            raise IntegrationError(
                f'SMC field {item.name!r} was not preserved by compaction'
            )
        for offset in range(item.width):
            smc_map[item.field_address + offset] = field_final + offset
        smc_relocations.append(SmcFieldRelocation(
            item.name, item.instruction_address, instruction_final,
            item.field_address, field_final, item.width,
        ))

    patches = []
    occupied_final_sources = set()
    for item in manifest.references:
        length = _REFERENCE_ENCODINGS[item.encoding]
        original_offset = item.source - manifest.image_base
        original_bytes = image[original_offset:original_offset + length]
        if original_bytes != item.expected_bytes:
            raise IntegrationError(
                f'reference bytes mismatch for {item.name!r} at ${item.source:04X}'
            )
        final_source = _map_byte_range(
            item.source, length, manifest, compaction, smc_map
        )
        occupied = set(range(final_source, final_source + length))
        if occupied_final_sources & occupied:
            raise IntegrationError('final relocation patch byte ranges overlap')
        occupied_final_sources |= occupied
        current_offset = final_source - manifest.image_base
        current = bytes(output[current_offset:current_offset + length])
        expected_current = item.expected_bytes
        if manifest.region_start <= item.source < manifest.region_end_exclusive:
            for repair in compaction.reference_repairs:
                source_offset = item.source - repair.original_source
                if (0 <= source_offset
                        and source_offset + length <= len(repair.original_bytes)
                        and final_source == repair.final_source + source_offset):
                    expected_current = repair.final_bytes[
                        source_offset:source_offset + length
                    ]
                    break
        if current != expected_current:
            raise IntegrationError(
                f'relocated source bytes for {item.name!r} changed before patching'
            )
        final_target = _map_address(
            item.target, manifest, compaction, smc_map
        )
        final_bytes = _encode_reference(item, final_source, final_target)
        output[current_offset:current_offset + length] = final_bytes
        patches.append(RelocationPatch(
            item.name, item.kind, item.source, final_source,
            item.target, final_target, item.encoding,
            original_bytes, final_bytes,
        ))

    anchor_checks = []
    for item in manifest.fixed_anchors:
        original_offset = item.address - manifest.image_base
        if image[original_offset:original_offset + len(item.expected_bytes)] \
                != item.expected_bytes:
            raise IntegrationError(
                f'fixed anchor bytes mismatch for {item.name!r}'
            )
        final_address = _map_byte_range(
            item.address, len(item.expected_bytes), manifest, compaction, smc_map
        )
        if final_address != item.address:
            raise IntegrationError(
                f'fixed anchor {item.name!r} would move from '
                f'${item.address:04X} to ${final_address:04X}'
            )
        final_offset = final_address - manifest.image_base
        if bytes(output[final_offset:final_offset + len(item.expected_bytes)]) \
                != item.expected_bytes:
            raise IntegrationError(
                f'fixed anchor {item.name!r} changed during integration'
            )
        anchor_checks.append(AnchorCheck(
            item.name, item.address, final_address, item.expected_bytes,
        ))

    moved_ranges = tuple(MovedRange(
        item.name, item.kind, item.start, item.end_exclusive,
        item.start + compaction.byte_delta,
        item.end_exclusive + compaction.byte_delta,
        item.expected_sha256,
    ) for item in manifest.shifted_ranges)

    authorizations = [ChangeAuthorization(
        'compacted-region', manifest.region_start, manifest.region_end_exclusive,
        manifest.region_start, manifest.region_start + len(compaction.compacted),
        'guarded compaction output and provenance ledger',
    )]
    authorizations.extend(ChangeAuthorization(
        'shifted-range', item.original_start, item.original_end_exclusive,
        item.final_start, item.final_end_exclusive,
        f'{item.kind}:{item.name}',
    ) for item in moved_ranges)
    authorizations.extend(ChangeAuthorization(
        'reference-patch', item.source_original,
        item.source_original + len(item.original_bytes), item.source_final,
        item.source_final + len(item.final_bytes), f'{item.kind}:{item.name}',
    ) for item in patches)
    new_end = manifest.image_base + len(output)
    authorizations.append(ChangeAuthorization(
        'truncation', new_end, image_end, new_end, new_end,
        'bytes reclaimed by compacted region',
    ))

    prefix_patch_addresses = {
        address
        for item in patches
        if item.source_final < manifest.region_start
        for address in range(item.source_final,
                             item.source_final + len(item.final_bytes))
    }
    changed_addresses = []
    unauthorized = []
    for address in range(manifest.image_base, image_end):
        old = image[address - manifest.image_base]
        new = (output[address - manifest.image_base]
               if address < new_end else None)
        if old == new:
            continue
        changed_addresses.append(address)
        if address < manifest.region_start and address not in prefix_patch_addresses:
            unauthorized.append(address)
    if unauthorized:
        raise IntegrationError(
            'whole-image audit found unauthorized changed bytes: '
            + ', '.join(f'${address:04X}' for address in unauthorized[:8])
        )

    integrated = bytes(output)
    reclaimed = len(image) - len(integrated)
    if reclaimed != -compaction.byte_delta:
        raise AssertionError('whole-image reclaimed-byte ledger does not balance')
    relocated_entries = tuple(
        (entry, address_map[entry]) for entry in manifest.entries
    )
    return WholeImageIntegrationResult(
        image, integrated, manifest, relocated_entries, tuple(patches),
        moved_ranges, tuple(smc_relocations), tuple(anchor_checks),
        tuple(authorizations), tuple(changed_addresses), len(changed_addresses),
        tuple(unauthorized), reclaimed, sha256(integrated).hexdigest(),
    )


def integrate_whole_image_sequence(
        image: bytes,
        stages: tuple[SequentialIntegrationStage, ...],
) -> SequentialIntegrationResult:
    """Apply hash-chained strict V2 stages without intermediate artifacts.

    Every stage manifest is expressed against the exact output bytes of the
    preceding stage. The existing V2 identity, reference, SMC, anchor, and
    changed-byte audits therefore remain acceptance gates at each step.
    """
    original = bytes(image)
    if not stages:
        raise IntegrationError('sequential integration requires at least one stage')
    names = [item.name for item in stages]
    if any(not name for name in names) or len(names) != len(set(names)):
        raise IntegrationError(
            'sequential integration stage names must be nonempty and unique'
        )
    image_base = stages[0].manifest.image_base
    current = original
    stage_results = []
    total_reclaimed = 0
    for index, stage in enumerate(stages):
        if stage.manifest.image_base != image_base:
            raise IntegrationError(
                f'sequential stage {stage.name!r} changes image base'
            )
        current_sha256 = sha256(current).hexdigest()
        if (stage.manifest.image_size != len(current)
                or stage.manifest.image_sha256 != current_sha256):
            raise IntegrationError(
                f'sequential stage {stage.name!r} input is not the exact '
                f'output of stage {index}'
            )
        region_start = stage.manifest.region_start - image_base
        region_end = stage.manifest.region_end_exclusive - image_base
        compaction = compact_code_region(
            current[region_start:region_end],
            base_address=stage.manifest.region_start,
            config=stage.compaction_config,
        )
        integration = integrate_whole_image(
            current, stage.manifest, compaction
        )
        if integration.unauthorized_changed_addresses:
            raise AssertionError('strict V2 returned unauthorized stage changes')
        stage_results.append(SequentialStageResult(
            stage.name, current_sha256, integration.output_sha256,
            compaction, integration,
        ))
        total_reclaimed += integration.reclaimed_bytes
        current = integration.integrated

    if len(original) - len(current) != total_reclaimed:
        raise AssertionError('sequential reclaimed-byte ledger does not balance')
    image_end = image_base + len(original)
    final_end = image_base + len(current)
    changed_addresses = tuple(
        address for address in range(image_base, image_end)
        if original[address - image_base] != (
            current[address - image_base] if address < final_end else None
        )
    )
    return SequentialIntegrationResult(
        original, current, tuple(stage_results), total_reclaimed,
        changed_addresses, len(changed_addresses), sha256(current).hexdigest(),
    )
