#!/usr/bin/env python3
"""Guarded packed-region compaction for documented 6502 code.

This module consumes the read-only CFG scanner's candidates, selects only
explicitly enabled non-overlapping transformations, lays the complete declared
code region out at final addresses, and regenerates direct control references.
It deliberately refuses mixed code/data, unresolved discovery, and incomplete
region/reference assertions.
"""

from __future__ import annotations

from dataclasses import dataclass

from dataflow6502 import ARCH_RESOURCES
from cfg_reduction6502 import (  # noqa: E402
    CFGScanConfig, CFGScanError, ReductionCandidate, scan_cfg_candidates,
)


class CompactionError(ValueError):
    """The packed-region contract or final layout is unsupported or unsafe."""


_BRANCHES = frozenset({'BCC', 'BCS', 'BEQ', 'BMI', 'BNE', 'BPL', 'BVC', 'BVS'})
_BRANCH_NAME_BY_OPCODE = {
    0x90: 'BCC', 0xB0: 'BCS', 0xF0: 'BEQ', 0x30: 'BMI',
    0xD0: 'BNE', 0x10: 'BPL', 0x50: 'BVC', 0x70: 'BVS',
}
_CONTROL_RULES = frozenset({
    'tail-call-jsr-rts',
    'known-flag-short-jump',
    'never-taken-branch-deletion',
    'branch-to-fallthrough-deletion',
    'redundant-zero-compare-after-load',
    'masked-bit-test-via-shift',
    'compare-zero-unsigned-branch-fold',
    'control-only-loop-reversal',
    'compare-immediate-via-index-step',
    'compare-two-via-lsr',
    'zero-compare-select-via-rehome',
    'duplicate-transfer',
    'duplicate-idempotent-operation',
})


@dataclass(frozen=True)
class SmcOperandContract:
    instruction_address: int
    operand_offset: int
    width: int

    def __post_init__(self):
        if not 0 <= self.instruction_address <= 0xFFFF:
            raise CompactionError('SMC instruction address must be 16-bit')
        if self.operand_offset not in {1, 2} or self.width not in {1, 2}:
            raise CompactionError('SMC operand offset/width must be 1 or 2')


@dataclass(frozen=True)
class CompactionConfig:
    entries: tuple[int, ...]
    entry_facts: tuple[tuple[str, int], ...] = ()
    terminal_live: frozenset[str] = frozenset(ARCH_RESOURCES)
    timing_policy: str = 'ordinary'
    cpu_profile: str = 'nmos6502'
    max_instructions: int = 10000
    external_calls_preserve_decimal: bool = False
    enabled_rules: frozenset[str] = _CONTROL_RULES
    assert_complete_code_region: bool = False
    assert_all_incoming_references_repairable: bool = False
    assert_no_code_as_data: bool = False
    assert_no_self_modifying_code: bool = False
    declared_smc_operand_fields: tuple[SmcOperandContract, ...] = ()
    assert_no_undeclared_self_modifying_code: bool = False
    assert_standard_jsr_rts: bool = False

    def __post_init__(self):
        object.__setattr__(self, 'entries', tuple(dict.fromkeys(self.entries)))
        object.__setattr__(self, 'enabled_rules', frozenset(self.enabled_rules))
        object.__setattr__(self, 'declared_smc_operand_fields', tuple(
            item if isinstance(item, SmcOperandContract)
            else SmcOperandContract(*item)
            for item in self.declared_smc_operand_fields
        ))
        if (self.assert_no_self_modifying_code
                and self.declared_smc_operand_fields):
            raise CompactionError(
                'no-SMC assertion conflicts with declared SMC operand fields'
            )
        if (self.declared_smc_operand_fields
                and not self.assert_no_undeclared_self_modifying_code):
            raise CompactionError(
                'declared SMC fields require no-undeclared-SMC assertion'
            )
        unknown = self.enabled_rules - _CONTROL_RULES
        if unknown:
            raise CompactionError(f'unknown compaction rules: {sorted(unknown)}')


@dataclass(frozen=True)
class AppliedCompaction:
    rule: str
    original_start: int
    original_end_exclusive: int
    final_start: int
    final_end_exclusive: int
    original_bytes: bytes
    final_bytes: bytes
    byte_delta: int
    nominal_cycle_delta: int
    proof: str


@dataclass(frozen=True)
class ReferenceRepair:
    mnemonic: str
    kind: str
    original_source: int
    final_source: int
    original_target: int
    final_target: int
    original_bytes: bytes
    final_bytes: bytes
    taken_page_cross_delta: int


@dataclass(frozen=True)
class ProvenanceSpan:
    original_start: int
    original_end_exclusive: int
    final_start: int
    final_end_exclusive: int
    kind: str


@dataclass(frozen=True)
class CompactionResult:
    original: bytes
    compacted: bytes
    base_address: int
    entries: tuple[int, ...]
    relocated_entries: tuple[tuple[int, int], ...]
    address_map: tuple[tuple[int, int], ...]
    applied: tuple[AppliedCompaction, ...]
    reference_repairs: tuple[ReferenceRepair, ...]
    provenance: tuple[ProvenanceSpan, ...]
    warnings: tuple[str, ...]
    timing_policy: str
    scanner_candidate_count: int
    declared_smc_operand_fields: tuple[SmcOperandContract, ...]

    @property
    def byte_delta(self):
        return len(self.compacted) - len(self.original)


@dataclass(frozen=True)
class _LayoutItem:
    original_start: int
    original_end_exclusive: int
    instructions: tuple
    candidate: ReductionCandidate | None
    final_start: int
    final_length: int


_RULE_FINAL_LENGTH = {
    'tail-call-jsr-rts': 3,
    'redundant-zero-compare-after-load': 0,
    'known-flag-short-jump': 2,
    'never-taken-branch-deletion': 0,
    'branch-to-fallthrough-deletion': 0,
}


def _inside(address: int, base: int, end: int) -> bool:
    return base <= address < end


def _branch_bytes(opcode: int, source: int, target: int) -> bytes:
    raw = (target - ((source + 2) & 0xFFFF)) & 0xFFFF
    if raw <= 0x7F:
        displacement = raw
    elif raw >= 0xFF80:
        displacement = raw - 0x10000
    else:
        raise CompactionError(
            f'final relative branch from ${source:04X} to ${target:04X} is out of range'
        )
    return bytes((opcode, displacement & 0xFF))


def _page_cross(source: int, target: int) -> bool:
    return (((source + 2) & 0xFF00) != (target & 0xFF00))


def _require_contract(config: CompactionConfig):
    required = (
        ('assert_complete_code_region', config.assert_complete_code_region,
         'caller must assert that every region byte is documented code'),
        ('assert_all_incoming_references_repairable',
         config.assert_all_incoming_references_repairable,
         'caller must assert that all incoming references are known and repairable'),
        ('assert_no_code_as_data', config.assert_no_code_as_data,
         'caller must assert that the region is not read as data'),
        ('self_modification_contract',
         config.assert_no_self_modifying_code
         or (bool(config.declared_smc_operand_fields)
             and config.assert_no_undeclared_self_modifying_code),
         'caller must assert the region is not self-modifying, or declare every SMC operand field and assert no undeclared SMC'),
    )
    for _name, value, message in required:
        if not value:
            raise CompactionError(message)
    if config.timing_policy == 'cycle-exact':
        raise CompactionError('cycle-exact policy forbids packed compaction')


def _select_candidates(candidates, config: CompactionConfig):
    eligible = []
    warnings = []
    for candidate in candidates:
        if candidate.rule not in config.enabled_rules:
            continue
        if not candidate.timing_admissible:
            warnings.append(
                f'${candidate.start:04X} {candidate.rule} skipped by timing policy'
            )
            continue
        if candidate.rule == 'tail-call-jsr-rts' and not config.assert_standard_jsr_rts:
            warnings.append(
                f'${candidate.start:04X} tail call skipped without standard JSR/RTS assertion'
            )
            continue
        eligible.append(candidate)

    # Weighted interval selection maximizes bytes first and cycle savings second.
    ordered = sorted(eligible, key=lambda item: (item.end_exclusive, item.start))
    best: list[tuple[tuple[int, int], tuple[int, ...]]] = [((0, 0), ())]
    for index, candidate in enumerate(ordered):
        predecessor = 0
        for prior in range(index - 1, -1, -1):
            if ordered[prior].end_exclusive <= candidate.start:
                predecessor = prior + 1
                break
        prior_score, prior_selection = best[predecessor]
        take_score = (prior_score[0] - candidate.byte_delta,
                      prior_score[1] - candidate.nominal_cycle_delta)
        take = (take_score, prior_selection + (index,))
        skip = best[-1]
        best.append(take if take[0] > skip[0] else skip)
    selected_indexes = set(best[-1][1])
    selected = tuple(sorted(
        (candidate for index, candidate in enumerate(ordered)
         if index in selected_indexes),
        key=lambda item: (item.start, item.end_exclusive),
    ))
    for candidate in eligible:
        if candidate not in selected and any(
                candidate.start < kept.end_exclusive
                and kept.start < candidate.end_exclusive for kept in selected):
            warnings.append(
                f'${candidate.start:04X} {candidate.rule} skipped in favor of a better overlapping selection'
            )
    return selected, warnings


def _layout(instructions, selected, base):
    by_start = {candidate.start: candidate for candidate in selected}
    covered = set()
    items = []
    final_pc = base
    index = 0
    while index < len(instructions):
        instruction = instructions[index]
        if instruction.pc in covered:
            index += 1
            continue
        candidate = by_start.get(instruction.pc)
        if candidate is None:
            item_instructions = (instruction,)
            original_end = instruction.pc + instruction.length
            final_length = instruction.length
        else:
            item_instructions = tuple(
                item for item in instructions
                if candidate.start <= item.pc < candidate.end_exclusive
            )
            if not item_instructions or item_instructions[0].pc != candidate.start:
                raise CompactionError(f'candidate at ${candidate.start:04X} lacks instructions')
            original_end = candidate.end_exclusive
            if item_instructions[-1].pc + item_instructions[-1].length != original_end:
                raise CompactionError(
                    f'candidate at ${candidate.start:04X} does not end on an instruction boundary'
                )
            final_length = (
                len(candidate.replacement_bytes)
                if candidate.rule in {
                    'masked-bit-test-via-shift',
                    'compare-zero-unsigned-branch-fold',
                    'control-only-loop-reversal',
                }
                else (len(candidate.original_bytes) - 1
                      if candidate.rule in {'compare-immediate-via-index-step',
                                            'compare-two-via-lsr',
                                            'zero-compare-select-via-rehome'}
                      else (item_instructions[0].length
                            if candidate.rule in {'duplicate-transfer',
                                                  'duplicate-idempotent-operation'}
                            else _RULE_FINAL_LENGTH[candidate.rule]))
            )
            covered.update(item.pc for item in item_instructions)
        items.append(_LayoutItem(
            instruction.pc, original_end, item_instructions, candidate,
            final_pc, final_length,
        ))
        final_pc += final_length
        index += len(item_instructions)
    return tuple(items)


def _address_map(items):
    mapping = {}
    for item in items:
        if item.candidate is None:
            mapping[item.original_start] = item.final_start
            continue
        for index, instruction in enumerate(item.instructions):
            if instruction.pc == item.original_start:
                mapping[instruction.pc] = item.final_start
            elif item.candidate.rule in {'compare-immediate-via-index-step',
                                         'compare-two-via-lsr'}:
                load_length = item.instructions[0].length
                mapping[instruction.pc] = (item.final_start + load_length
                                           + (1 if index == 2 else 0))
            elif item.candidate.rule == 'compare-zero-unsigned-branch-fold':
                for folded in item.instructions[1:]:
                    mapping[folded.pc] = item.final_start
            elif item.candidate.rule == 'masked-bit-test-via-shift':
                mapping[item.instructions[1].pc] = (
                    item.final_start + item.instructions[0].length
                )
                mapping[item.instructions[2].pc] = (
                    item.final_start + item.final_length - 2
                )
            elif item.candidate.rule == 'control-only-loop-reversal':
                compare_index = len(item.instructions) - 2
                if index < compare_index:
                    mapping[instruction.pc] = (
                        item.final_start
                        + instruction.pc - item.original_start
                    )
                else:
                    mapping[instruction.pc] = (
                        item.final_start + item.final_length - 2
                    )
            elif item.candidate.rule == 'zero-compare-select-via-rehome':
                first_load_length = item.instructions[0].length
                alternate_load_length = item.instructions[3].length
                offsets = (
                    0,
                    first_load_length,
                    first_load_length + 1,
                    first_load_length + 3,
                    first_load_length + 3 + alternate_load_length,
                )
                mapping[instruction.pc] = item.final_start + offsets[index]
            elif item.final_length == 0:
                mapping[instruction.pc] = item.final_start
            else:
                mapping[instruction.pc] = item.final_start + item.final_length
    return mapping


def compact_code_region(data: bytes, *, base_address: int,
                        config: CompactionConfig) -> CompactionResult:
    """Compact one complete declared code region and repair direct control flow."""
    _require_contract(config)
    data = bytes(data)
    scan_config = CFGScanConfig(
        entries=config.entries, entry_facts=config.entry_facts,
        terminal_live=config.terminal_live,
        timing_policy=config.timing_policy, cpu_profile=config.cpu_profile,
        max_instructions=config.max_instructions,
        external_calls_preserve_decimal=config.external_calls_preserve_decimal,
    )
    try:
        scan = scan_cfg_candidates(data, base_address=base_address, config=scan_config)
    except CFGScanError as exc:
        raise CompactionError(str(exc)) from exc
    if scan.limit_reached or scan.issues:
        details = '; '.join(scan.issues) or 'instruction limit reached'
        raise CompactionError(f'CFG discovery is incomplete: {details}')

    instructions = tuple(sorted(scan.instructions, key=lambda item: item.pc))
    by_pc = {item.pc: item for item in instructions}
    occupied_smc_bytes = set()
    for field in config.declared_smc_operand_fields:
        instruction = by_pc.get(field.instruction_address)
        if instruction is None:
            raise CompactionError(
                f'declared SMC instruction ${field.instruction_address:04X} is not decoded'
            )
        if field.operand_offset + field.width > instruction.length:
            raise CompactionError(
                f'declared SMC field exceeds instruction at ${field.instruction_address:04X}'
            )
        addresses = set(range(
            field.instruction_address + field.operand_offset,
            field.instruction_address + field.operand_offset + field.width,
        ))
        if occupied_smc_bytes & addresses:
            raise CompactionError('declared SMC operand fields overlap')
        occupied_smc_bytes |= addresses
    cursor = base_address
    for instruction in instructions:
        if instruction.pc != cursor:
            raise CompactionError(
                f'complete-code assertion failed: uncovered byte at ${cursor:04X}'
            )
        cursor += instruction.length
    if cursor != base_address + len(data):
        raise CompactionError(
            f'complete-code assertion failed: uncovered byte at ${cursor:04X}'
        )

    selected, warnings = _select_candidates(scan.candidates, config)
    items = _layout(instructions, selected, base_address)
    mapping = _address_map(items)
    end = base_address + len(data)
    for entry in config.entries:
        if entry not in mapping:
            raise CompactionError(f'entry ${entry:04X} has no final address')

    output = bytearray()
    applied = []
    repairs = []
    provenance = []

    def mapped_target(target):
        if _inside(target, base_address, end):
            if target not in mapping:
                raise CompactionError(
                    f'internal control target ${target:04X} has no instruction mapping'
                )
            return mapping[target]
        return target

    for item in items:
        instruction = item.instructions[0]
        candidate = item.candidate
        final = b''
        cycle_delta = 0
        if candidate is not None:
            if candidate.rule == 'tail-call-jsr-rts':
                target = mapped_target(instruction.operand)
                final = bytes((0x4C, target & 0xFF, (target >> 8) & 0xFF))
                cycle_delta = -9
                repairs.append(ReferenceRepair(
                    'JMP', 'tail-call-target', instruction.pc, item.final_start,
                    instruction.operand, target, instruction.data, final, 0,
                ))
            elif candidate.rule == 'known-flag-short-jump':
                target = mapped_target(instruction.operand)
                final = _branch_bytes(candidate.replacement_bytes[0], item.final_start, target)
                cross_delta = int(_page_cross(item.final_start, target))
                cycle_delta = cross_delta
                if config.timing_policy == 'interrupt' and cross_delta > 0:
                    raise CompactionError(
                        f'interrupt policy: final short jump at ${item.final_start:04X} crosses a page'
                    )
                repairs.append(ReferenceRepair(
                    _BRANCH_NAME_BY_OPCODE[candidate.replacement_bytes[0]],
                    'known-flag-short-jump', instruction.pc, item.final_start,
                    instruction.operand, target, instruction.data, final,
                    cross_delta,
                ))
            elif candidate.rule in {'compare-immediate-via-index-step',
                                    'compare-two-via-lsr'}:
                branch = item.instructions[2]
                target = mapped_target(branch.operand)
                branch_source = item.final_start + instruction.length + 1
                replacement_branch_opcode = candidate.replacement_bytes[instruction.length + 1]
                final_branch = _branch_bytes(replacement_branch_opcode, branch_source, target)
                final = (candidate.replacement_bytes[:instruction.length + 1]
                         + final_branch)
                old_cross = int(_page_cross(branch.pc, branch.operand))
                new_cross = int(_page_cross(branch_source, target))
                cross_delta = new_cross - old_cross
                if config.timing_policy == 'interrupt' and cross_delta > 0:
                    raise CompactionError(
                        f'interrupt policy: lowered compare branch at ${branch_source:04X} adds a page-cross cycle'
                    )
                repairs.append(ReferenceRepair(
                    _BRANCH_NAME_BY_OPCODE[replacement_branch_opcode],
                    'compare-lowering-branch', branch.pc,
                    branch_source, branch.operand, target, branch.data,
                    final_branch, cross_delta,
                ))
                cycle_delta = 0
            elif candidate.rule == 'compare-zero-unsigned-branch-fold':
                branch = item.instructions[1]
                if candidate.replacement_bytes:
                    target = mapped_target(branch.operand)
                    final = bytes((0x4C, target & 0xFF, target >> 8))
                    repairs.append(ReferenceRepair(
                        'JMP', 'compare-zero-always-branch', branch.pc,
                        item.final_start, branch.operand, target,
                        branch.data, final, 0,
                    ))
                else:
                    final = b''
                cycle_delta = candidate.nominal_cycle_delta
            elif candidate.rule == 'control-only-loop-reversal':
                initializer = item.instructions[0]
                compare = item.instructions[-2]
                branch = item.instructions[-1]
                target = mapped_target(branch.operand)
                branch_source = item.final_start + item.final_length - 2
                final_branch = _branch_bytes(
                    branch.opcode, branch_source, target
                )
                final = candidate.replacement_bytes[:-2] + final_branch
                trip_count = (compare.operand - initializer.operand) & 0xFF
                old_cross = int(_page_cross(branch.pc, branch.operand))
                new_cross = int(_page_cross(branch_source, target))
                cross_delta = new_cross - old_cross
                cycle_delta = (-2 * trip_count
                               + cross_delta * (trip_count - 1))
                if config.timing_policy == 'interrupt' and cycle_delta > 0:
                    raise CompactionError(
                        f'interrupt policy: reversed loop at ${item.final_start:04X} is slower'
                    )
                repairs.append(ReferenceRepair(
                    'BNE', 'control-only-loop-back-edge', branch.pc,
                    branch_source, branch.operand, target, branch.data,
                    final_branch, cross_delta,
                ))
            elif candidate.rule == 'masked-bit-test-via-shift':
                branch = item.instructions[2]
                target = mapped_target(branch.operand)
                branch_source = item.final_start + item.final_length - 2
                replacement_branch_opcode = candidate.replacement_bytes[-2]
                final_branch = _branch_bytes(
                    replacement_branch_opcode, branch_source, target
                )
                final = candidate.replacement_bytes[:-2] + final_branch
                old_cross = int(_page_cross(branch.pc, branch.operand))
                new_cross = int(_page_cross(branch_source, target))
                cross_delta = new_cross - old_cross
                if config.timing_policy == 'interrupt' and cross_delta > 0:
                    raise CompactionError(
                        f'interrupt policy: masked bit-test branch at ${branch_source:04X} adds a page-cross cycle'
                    )
                repairs.append(ReferenceRepair(
                    _BRANCH_NAME_BY_OPCODE[replacement_branch_opcode],
                    'masked-bit-test-branch', branch.pc, branch_source,
                    branch.operand, target, branch.data, final_branch,
                    cross_delta,
                ))
                cycle_delta = candidate.nominal_cycle_delta
            elif candidate.rule == 'zero-compare-select-via-rehome':
                branch = item.instructions[2]
                target = mapped_target(branch.operand)
                branch_offset = instruction.length + 1
                branch_source = item.final_start + branch_offset
                replacement_branch_opcode = candidate.replacement_bytes[branch_offset]
                final_branch = _branch_bytes(replacement_branch_opcode, branch_source, target)
                final = (candidate.replacement_bytes[:branch_offset]
                         + final_branch
                         + candidate.replacement_bytes[branch_offset + 2:])
                old_cross = int(_page_cross(branch.pc, branch.operand))
                new_cross = int(_page_cross(branch_source, target))
                cross_delta = new_cross - old_cross
                if config.timing_policy == 'interrupt' and cross_delta > 0:
                    raise CompactionError(
                        f'interrupt policy: rehomed select branch at ${branch_source:04X} adds a page-cross cycle'
                    )
                repairs.append(ReferenceRepair(
                    _BRANCH_NAME_BY_OPCODE[replacement_branch_opcode],
                    'rehome-composed-branch', branch.pc,
                    branch_source, branch.operand, target, branch.data,
                    final_branch, cross_delta,
                ))
                cycle_delta = 0
            elif candidate.rule in {'duplicate-transfer',
                                    'duplicate-idempotent-operation'}:
                final = instruction.data
                cycle_delta = candidate.nominal_cycle_delta
            elif candidate.rule in {
                    'never-taken-branch-deletion',
                    'branch-to-fallthrough-deletion',
                    'redundant-zero-compare-after-load'}:
                final = b''
                cycle_delta = candidate.nominal_cycle_delta
            else:
                raise CompactionError(f'unsupported selected rule {candidate.rule}')
            applied.append(AppliedCompaction(
                candidate.rule, item.original_start, item.original_end_exclusive,
                item.final_start, item.final_start + len(final),
                candidate.original_bytes, final, len(final) - len(candidate.original_bytes),
                cycle_delta, candidate.proof,
            ))
            if candidate.rule == 'control-only-loop-reversal':
                compare_pc = item.instructions[-2].pc
                branch_pc = item.instructions[-1].pc
                initializer_pc = item.instructions[0].pc
                step_pc = item.instructions[-3].pc
                for transformed in item.instructions:
                    if transformed.pc < compare_pc:
                        final_start = mapping[transformed.pc]
                        kind = ('copied-instruction'
                                if transformed.pc not in {initializer_pc, step_pc}
                                else candidate.rule)
                        provenance.append(ProvenanceSpan(
                            transformed.pc,
                            transformed.pc + transformed.length,
                            final_start, final_start + transformed.length,
                            kind,
                        ))
                    elif transformed.pc == compare_pc:
                        provenance.append(ProvenanceSpan(
                            transformed.pc,
                            transformed.pc + transformed.length,
                            mapping[transformed.pc], mapping[transformed.pc],
                            candidate.rule,
                        ))
                    else:
                        provenance.append(ProvenanceSpan(
                            branch_pc, branch_pc + transformed.length,
                            mapping[branch_pc],
                            mapping[branch_pc] + transformed.length,
                            candidate.rule,
                        ))
            else:
                provenance.append(ProvenanceSpan(
                    item.original_start, item.original_end_exclusive,
                    item.final_start, item.final_start + len(final), candidate.rule,
                ))
        else:
            final = instruction.data
            if instruction.mnemonic in _BRANCHES:
                target = mapped_target(instruction.operand)
                final = _branch_bytes(instruction.opcode, item.final_start, target)
                old_cross = int(_page_cross(instruction.pc, instruction.operand))
                new_cross = int(_page_cross(item.final_start, target))
                cross_delta = new_cross - old_cross
                if config.timing_policy == 'interrupt' and cross_delta > 0:
                    raise CompactionError(
                        f'interrupt policy: branch moved to ${item.final_start:04X} adds a page-cross cycle'
                    )
                if final != instruction.data or item.final_start != instruction.pc:
                    repairs.append(ReferenceRepair(
                        instruction.mnemonic, 'relative-control', instruction.pc,
                        item.final_start, instruction.operand, target,
                        instruction.data, final, cross_delta,
                    ))
            elif instruction.mnemonic in {'JSR', 'JMP'} and instruction.mode == 'abs':
                target = mapped_target(instruction.operand)
                final = bytes((instruction.opcode, target & 0xFF, (target >> 8) & 0xFF))
                if final != instruction.data or item.final_start != instruction.pc:
                    repairs.append(ReferenceRepair(
                        instruction.mnemonic, 'absolute-control', instruction.pc,
                        item.final_start, instruction.operand, target,
                        instruction.data, final, 0,
                    ))
            provenance.append(ProvenanceSpan(
                item.original_start, item.original_end_exclusive,
                item.final_start, item.final_start + len(final), 'copied-instruction',
            ))
        if len(final) != item.final_length:
            raise AssertionError('final encoding length differs from planned layout')
        output.extend(final)

    compacted = bytes(output)
    byte_delta = len(compacted) - len(data)
    if byte_delta != sum(item.byte_delta for item in applied):
        raise AssertionError('compaction byte ledger does not balance')
    if len(compacted) >= len(data) and applied:
        raise AssertionError('selected reductions did not shorten the region')
    relocated_entries = tuple((entry, mapping[entry]) for entry in config.entries)
    if any(old != new for old, new in relocated_entries):
        warnings.append('one or more declared entries moved; repair every external incoming reference')
    if any(item.mnemonic == 'NOP' for item in instructions):
        warnings.append('NOP instructions were preserved')
    return CompactionResult(
        data, compacted, base_address, config.entries, relocated_entries,
        tuple(sorted(mapping.items())), tuple(applied), tuple(repairs),
        tuple(provenance), tuple(dict.fromkeys(warnings)), config.timing_policy,
        len(scan.candidates), config.declared_smc_operand_fields,
    )
