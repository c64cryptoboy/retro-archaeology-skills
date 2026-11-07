#!/usr/bin/env python3
"""Read-only CFG discovery and code-size reduction candidate scanning.

The scanner establishes documented-NMOS instruction boundaries by conservative
recursive descent.  It reports mechanically recognizable candidates but never
changes bytes or claims that image entries/references are complete.
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Iterable, Mapping

from cpu6502 import cpucycles_table
from dataflow6502 import (  # noqa: E402
    ARCH_RESOURCES, FLAGS, CallSummary, FlowEdge, FlowInstruction,
    analyze_known_state, analyze_liveness, decode_at, instruction_effects,
)
from isa6502 import OPS


class CFGScanError(ValueError):
    """The image or scan contract is malformed."""


_BRANCHES = frozenset({'BCC', 'BCS', 'BEQ', 'BMI', 'BNE', 'BPL', 'BVC', 'BVS'})
_TERMINATORS = frozenset({'BRK', 'RTI', 'RTS'})
_BRANCH_FOR_FACT = {
    ('F:Z', 0): (0xD0, 'BNE'), ('F:Z', 1): (0xF0, 'BEQ'),
    ('F:C', 0): (0x90, 'BCC'), ('F:C', 1): (0xB0, 'BCS'),
    ('F:N', 0): (0x10, 'BPL'), ('F:N', 1): (0x30, 'BMI'),
    ('F:V', 0): (0x50, 'BVC'), ('F:V', 1): (0x70, 'BVS'),
}
_FACT_ORDER = ('F:Z', 'F:C', 'F:N', 'F:V')
_ALLOCATABLE_REGISTERS = frozenset({'A', 'X', 'Y'})
_ALLOCATABLE_FLAGS = frozenset(FLAGS - {'F:I'})
_OPCODE_BY_NAME_MODE = {
    (mnemonic, mode): opcode
    for opcode, (mnemonic, mode, _length) in OPS.items()
}
_COMPARE_REGISTER = {'CMP': 'A', 'CPX': 'X', 'CPY': 'Y'}
_LOAD_REGISTER = {'LDA': 'A', 'LDX': 'X', 'LDY': 'Y'}
_STORE_REGISTER = {'STA': 'A', 'STX': 'X', 'STY': 'Y'}
_IDEMPOTENT_DUPLICATES = frozenset({
    ('AND', 'imm'), ('ORA', 'imm'),
    ('CMP', 'imm'), ('CPX', 'imm'), ('CPY', 'imm'),
    ('LDA', 'imm'), ('LDX', 'imm'), ('LDY', 'imm'),
    ('TSX', 'imp'), ('TXS', 'imp'),
    ('CLC', 'imp'), ('SEC', 'imp'), ('CLD', 'imp'), ('SED', 'imp'),
    ('CLI', 'imp'), ('SEI', 'imp'), ('CLV', 'imp'),
})
_STEP_OPCODE = {
    ('X', 0xFF): (0xE8, 'INX'), ('Y', 0xFF): (0xC8, 'INY'),
    ('X', 0x01): (0xCA, 'DEX'), ('Y', 0x01): (0x88, 'DEY'),
}
_ZERO_COMPARE_TRANSFER = {
    'X': (0x8A, 'TXA', 'Y'),
    'Y': (0x98, 'TYA', 'X'),
}
_CONTROL_LOOP_REGISTER = {'LDX': 'X', 'LDY': 'Y'}
_CONTROL_LOOP_STEP = {'X': ('INX', 'DEX', 0xCA), 'Y': ('INY', 'DEY', 0x88)}
_CONTROL_LOOP_COMPARE = {'X': 'CPX', 'Y': 'CPY'}
_MASKED_BIT_TESTS = {
    # mask: (optional accumulator shift, BEQ replacement, BNE replacement,
    #        resources whose final values may differ)
    0x01: ('LSR', 'BCC', 'BCS', frozenset({'A', 'F:C', 'F:Z'})),
    0x40: ('ASL', 'BPL', 'BMI', frozenset({'A', 'F:C', 'F:N', 'F:Z'})),
    0x80: (None, 'BPL', 'BMI', frozenset({'A', 'F:Z'})),
}


@dataclass(frozen=True)
class CFGScanConfig:
    entries: tuple[int, ...]
    entry_facts: tuple[tuple[str, int], ...] = ()
    terminal_live: frozenset[str] = frozenset(ARCH_RESOURCES)
    timing_policy: str = 'ordinary'
    cpu_profile: str = 'nmos6502'
    max_instructions: int = 10000
    external_calls_preserve_decimal: bool = False

    def __post_init__(self):
        object.__setattr__(self, 'entries', tuple(dict.fromkeys(self.entries)))
        if not self.entries:
            raise CFGScanError('at least one entry is required')
        object.__setattr__(self, 'terminal_live', frozenset(self.terminal_live))
        unknown_live = self.terminal_live - ARCH_RESOURCES
        if unknown_live:
            raise CFGScanError(f'unknown terminal-live resources: {sorted(unknown_live)}')
        if self.timing_policy not in {'ordinary', 'interrupt', 'cycle-exact'}:
            raise CFGScanError('timing_policy must be ordinary, interrupt, or cycle-exact')
        if self.cpu_profile not in {'nmos6502', '6510', '2a03'}:
            raise CFGScanError('cpu_profile must be nmos6502, 6510, or 2a03')
        if self.max_instructions <= 0:
            raise CFGScanError('max_instructions must be positive')
        facts = dict(self.entry_facts)
        if len(facts) != len(self.entry_facts):
            raise CFGScanError('entry facts must be unique')
        unknown = set(facts) - ARCH_RESOURCES
        if unknown:
            raise CFGScanError(f'unknown entry-fact resources: {sorted(unknown)}')
        for resource, value in facts.items():
            limit = 1 if resource.startswith('F:') else 255
            if not isinstance(value, int) or not 0 <= value <= limit:
                raise CFGScanError(f'invalid entry fact {resource}={value}')


@dataclass(frozen=True)
class ScanEdge:
    source: int
    target: int
    kind: str
    internal: bool


@dataclass(frozen=True)
class BasicBlock:
    start: int
    end_exclusive: int
    instruction_pcs: tuple[int, ...]
    successors: tuple[int, ...]


@dataclass(frozen=True)
class ReductionCandidate:
    rule: str
    start: int
    end_exclusive: int
    original_bytes: bytes
    replacement_bytes: bytes
    byte_delta: int
    nominal_cycle_delta: int
    timing_admissible: bool
    proof: str
    requirements: tuple[str, ...]
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class RegisterRehomeOption:
    original_register: str
    replacement_register: str
    producer: int
    consumer: int
    interval_end_exclusive: int
    original_producer_bytes: bytes
    replacement_producer_bytes: bytes
    original_consumer_bytes: bytes
    replacement_consumer_bytes: bytes
    byte_delta: int
    nominal_cycle_delta: int
    proof: str


@dataclass(frozen=True)
class IndexedTraversalReversalOption:
    register: str
    strategy: str
    start: int
    end_exclusive: int
    start_value: int
    terminal_value: int
    trip_count: int
    body_instruction_pcs: tuple[int, ...]
    index_use_pcs: tuple[int, ...]
    original_bytes: bytes
    replacement_bytes: bytes
    byte_delta: int
    nominal_cycle_delta: int
    timing_admissible: bool
    proof: str
    semantic_requirements: tuple[str, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class CFGScanResult:
    data: bytes
    base_address: int
    entries: tuple[int, ...]
    instructions: tuple[FlowInstruction, ...]
    edges: tuple[ScanEdge, ...]
    blocks: tuple[BasicBlock, ...]
    candidates: tuple[ReductionCandidate, ...]
    register_rehomes: tuple[RegisterRehomeOption, ...]
    indexed_traversal_reversals: tuple[IndexedTraversalReversalOption, ...]
    stops: tuple[tuple[int, str], ...]
    issues: tuple[str, ...]
    limit_reached: bool
    decimal_policy: str
    decimal_clear_invariant: bool
    known_facts_in: tuple[tuple[int, tuple[tuple[str, int], ...]], ...]
    branch_outcomes: tuple[tuple[int, str], ...]
    live_in: tuple[tuple[int, tuple[str, ...]], ...]
    live_out: tuple[tuple[int, tuple[str, ...]], ...]
    available_in: tuple[tuple[int, tuple[str, ...]], ...]
    available_out: tuple[tuple[int, tuple[str, ...]], ...]
    available_flags_in: tuple[tuple[int, tuple[str, ...]], ...]
    available_flags_out: tuple[tuple[int, tuple[str, ...]], ...]
    known_iterations: int
    liveness_iterations: int

    @property
    def end_address_exclusive(self):
        return self.base_address + len(self.data)


def _inside(address: int, base: int, end: int) -> bool:
    return base <= address < end


def _relative_displacement(source: int, target: int) -> int | None:
    raw = (target - ((source + 2) & 0xFFFF)) & 0xFFFF
    if raw <= 0x7F:
        return raw
    if raw >= 0xFF80:
        return raw - 0x10000
    return None


def _discover(data: bytes, base: int, config: CFGScanConfig):
    end = base + len(data)
    memory = bytearray(65536)
    memory[base:end] = data
    queue = deque(config.entries)
    queued = set(config.entries)
    instructions: dict[int, FlowInstruction] = {}
    byte_owner: dict[int, int] = {}
    edges: list[ScanEdge] = []
    stops: list[tuple[int, str]] = []
    issues: list[str] = []
    limit_reached = False

    def enqueue(address: int):
        if _inside(address, base, end) and address not in queued:
            queue.append(address); queued.add(address)

    def edge(source: int, target: int, kind: str):
        internal = _inside(target, base, end)
        edges.append(ScanEdge(source, target, kind, internal))
        if internal:
            enqueue(target)

    while queue:
        pc = queue.popleft()
        while _inside(pc, base, end) and pc not in instructions:
            if len(instructions) >= config.max_instructions:
                limit_reached = True
                issues.append(f'instruction limit {config.max_instructions} reached')
                queue.clear()
                break
            owner = byte_owner.get(pc)
            if owner is not None and owner != pc:
                raise CFGScanError(
                    f'control target ${pc:04X} enters instruction at ${owner:04X}'
                )
            try:
                instruction = decode_at(bytes(memory), pc)
            except Exception as exc:
                issues.append(str(exc)); stops.append((pc, 'invalid-opcode'))
                break
            if pc + instruction.length > end:
                issues.append(f'truncated {instruction.mnemonic} at ${pc:04X}')
                stops.append((pc, 'truncated-instruction'))
                break
            for address in range(pc, pc + instruction.length):
                owner = byte_owner.get(address)
                if owner is not None and owner != pc:
                    raise CFGScanError(
                        f'instruction at ${pc:04X} overlaps instruction at ${owner:04X}'
                    )
            instructions[pc] = instruction
            for address in range(pc, pc + instruction.length):
                byte_owner[address] = pc

            next_pc = pc + instruction.length
            if instruction.mnemonic in _BRANCHES:
                edge(pc, instruction.operand, 'branch')
                edge(pc, next_pc, 'fallthrough')
                break
            if instruction.mnemonic == 'JSR':
                edge(pc, instruction.operand, 'call')
                edge(pc, next_pc, 'fallthrough')
                break
            if instruction.mnemonic == 'JMP':
                if instruction.mode == 'abs':
                    edge(pc, instruction.operand, 'jump')
                else:
                    stops.append((pc, 'unresolved-indirect-jump'))
                    issues.append(f'unresolved indirect JMP at ${pc:04X}')
                break
            if instruction.mnemonic in _TERMINATORS:
                stops.append((pc, instruction.mnemonic.lower()))
                break
            if not _inside(next_pc, base, end):
                stops.append((pc, 'falls-outside-image'))
                break
            pc = next_pc

    # Stable deduplication matters when multiple discovery paths emit an edge.
    unique_edges = tuple(
        ScanEdge(*item) for item in sorted({
            (edge.source, edge.target, edge.kind, edge.internal) for edge in edges
        })
    )
    return instructions, unique_edges, tuple(stops), tuple(dict.fromkeys(issues)), limit_reached


def _basic_blocks(instructions: Mapping[int, FlowInstruction], edges: Iterable[ScanEdge],
                  entries: Iterable[int]) -> tuple[BasicBlock, ...]:
    if not instructions:
        return ()
    leaders = {entry for entry in entries if entry in instructions}
    for edge in edges:
        if edge.internal and edge.target in instructions:
            leaders.add(edge.target)
    assigned: set[int] = set()
    blocks = []
    outgoing = defaultdict(set)
    for edge in edges:
        if edge.internal:
            outgoing[edge.source].add(edge.target)

    for leader in sorted(leaders):
        if leader in assigned:
            continue
        pcs = []
        pc = leader
        while pc in instructions and pc not in assigned:
            instruction = instructions[pc]
            pcs.append(pc); assigned.add(pc)
            if (instruction.mnemonic in _BRANCHES or instruction.mnemonic in _TERMINATORS
                    or instruction.mnemonic in {'JMP', 'JSR'}):
                break
            next_pc = pc + instruction.length
            if next_pc in leaders:
                break
            pc = next_pc
        last = instructions[pcs[-1]]
        successors = set(outgoing.get(last.pc, ()))
        sequential = last.pc + last.length
        if not successors and last.mnemonic not in _TERMINATORS | {'JMP'}:
            if sequential in instructions:
                successors.add(sequential)
        blocks.append(BasicBlock(
            leader, last.pc + last.length, tuple(pcs), tuple(sorted(successors))
        ))

    # Defensive coverage for a sequentially discovered island not named by an edge.
    for pc in sorted(set(instructions) - assigned):
        instruction = instructions[pc]
        blocks.append(BasicBlock(pc, pc + instruction.length, (pc,), ()))
    return tuple(sorted(blocks, key=lambda block: block.start))


def _decimal_contract(instructions: Mapping[int, FlowInstruction], edges: Iterable[ScanEdge],
                      issues: Iterable[str], config: CFGScanConfig):
    if config.cpu_profile == '2a03':
        return '2A03 decimal arithmetic disabled', True
    if dict(config.entry_facts).get('F:D') == 1:
        return 'explicit entry fact sets D=1', False
    setters = [item.pc for item in instructions.values() if item.mnemonic in {'SED', 'PLP'}]
    external_calls = [edge.target for edge in edges if edge.kind == 'call' and not edge.internal]
    complete = not tuple(issues)
    invariant = (not setters and complete
                 and (not external_calls or config.external_calls_preserve_decimal))
    if invariant:
        return 'assumed D=0 at entry; no reachable decimal setter/import', True
    reasons = []
    if setters:
        reasons.append('reachable ' + ', '.join(f'${pc:04X}' for pc in setters))
    if external_calls and not config.external_calls_preserve_decimal:
        reasons.append('external calls lack a D-preservation contract')
    if not complete:
        reasons.append('reachable-code discovery is incomplete')
    return '; '.join(reasons) or 'local D-state analysis required', False


def _register_rehome_scan(instructions: Mapping[int, FlowInstruction],
                          blocks: tuple[BasicBlock, ...], liveness,
                          call_summaries):
    """Report equal-cost simple load-to-store live ranges movable to A/X/Y."""
    result = []
    for block in blocks:
        block_instructions = [instructions[pc] for pc in block.instruction_pcs]
        for producer_index, producer in enumerate(block_instructions):
            source = _LOAD_REGISTER.get(producer.mnemonic)
            if source is None or producer.mode not in {'imm', 'zp', 'abs'}:
                continue
            for consumer_index in range(producer_index + 1,
                                        min(len(block_instructions), producer_index + 9)):
                consumer = block_instructions[consumer_index]
                if (_STORE_REGISTER.get(consumer.mnemonic) == source
                        and consumer.mode in {'zp', 'abs'}):
                    interval = block_instructions[producer_index + 1:consumer_index]
                    for target in sorted(_ALLOCATABLE_REGISTERS - {source}):
                        load_opcode = _OPCODE_BY_NAME_MODE.get(('LD' + target, producer.mode))
                        store_opcode = _OPCODE_BY_NAME_MODE.get(('ST' + target, consumer.mode))
                        if load_opcode is None or store_opcode is None:
                            continue
                        if (target in liveness.live_in[producer.pc]
                                or source in liveness.live_out[consumer.pc]
                                or target in liveness.live_out[consumer.pc]):
                            continue
                        if any(target in (instruction_effects(item, call_summaries).reads
                                          | instruction_effects(item, call_summaries).writes)
                               for item in interval):
                            continue
                        if (OPS[load_opcode][2] != producer.length
                                or OPS[store_opcode][2] != consumer.length
                                or cpucycles_table[load_opcode] != cpucycles_table[producer.opcode]
                                or cpucycles_table[store_opcode] != cpucycles_table[consumer.opcode]):
                            continue
                        replacement_producer = bytes((load_opcode,)) + producer.data[1:]
                        replacement_consumer = bytes((store_opcode,)) + consumer.data[1:]
                        result.append(RegisterRehomeOption(
                            source, target, producer.pc, consumer.pc,
                            consumer.pc + consumer.length, producer.data,
                            replacement_producer, consumer.data, replacement_consumer,
                            0, 0,
                            f'{target} is available across the simple {source} load→store live range; matching modes preserve memory, N/Z, bytes, and cycles',
                        ))
                    break
                effects = instruction_effects(consumer, call_summaries)
                if source in effects.reads or source in effects.writes:
                    break
    return tuple(result)


def _indexed_traversal_reversal_scan(
        data: bytes, base: int, instructions: Mapping[int, FlowInstruction],
        edges: tuple[ScanEdge, ...], liveness, config: CFGScanConfig,
) -> tuple[IndexedTraversalReversalOption, ...]:
    """Report canonical reverse-order loops for semantic review only."""
    predecessors = defaultdict(set)
    for edge in edges:
        if edge.internal:
            predecessors[edge.target].add((edge.source, edge.kind))
    entry_set = set(config.entries)
    control_targets = {
        edge.target for edge in edges if edge.internal
    } | entry_set
    ending_at = {
        item.pc + item.length: item for item in instructions.values()
    }
    result = []
    for branch in instructions.values():
        if branch.mnemonic != 'BNE' or branch.mode != 'rel':
            continue
        compare = ending_at.get(branch.pc)
        step = ending_at.get(compare.pc) if compare is not None else None
        header = branch.operand
        initializer = ending_at.get(header)
        register = (_CONTROL_LOOP_REGISTER.get(initializer.mnemonic)
                    if initializer is not None and initializer.mode == 'imm'
                    else None)
        if (register is None or compare is None or step is None
                or compare.mnemonic != _CONTROL_LOOP_COMPARE[register]
                or compare.mode != 'imm'
                or step.mnemonic != _CONTROL_LOOP_STEP[register][0]
                or step.mode != 'imp'
                or not initializer.pc < header <= step.pc
                or header in entry_set
                or predecessors.get(header, set()) != {(branch.pc, 'branch')}
                or any(pc in control_targets for pc in (
                    step.pc, compare.pc, branch.pc
                ))):
            continue
        body = []
        body_pc = header
        while body_pc < step.pc:
            item = instructions.get(body_pc)
            if item is None:
                body = []
                break
            body.append(item)
            body_pc += item.length
        if (not body or body_pc != step.pc
                or any(item.pc != header and item.pc in control_targets
                       for item in body)
                or any(item.mnemonic in _BRANCHES | _TERMINATORS | {'JMP', 'JSR'}
                       for item in body)):
            continue
        effects = tuple(instruction_effects(item, None) for item in body)
        if any(register in effect.writes for effect in effects):
            continue
        index_uses = tuple(
            item.pc for item, effect in zip(body, effects)
            if register in effect.reads
        )
        if not index_uses:
            continue

        start_value = initializer.operand
        terminal_value = compare.operand
        trip_count = (terminal_value - start_value) & 0xFF
        if trip_count == 0:
            continue
        if start_value == 1:
            strategy = 'one-based-decrement-bne'
            initial_value = (terminal_value - 1) & 0xFF
            replacement_branch_opcode = branch.opcode
            exit_changed = {'F:C'}
            header_changed = {'F:N', 'F:C'}
        elif start_value == 0 and 1 <= terminal_value <= 0x80:
            strategy = 'zero-based-decrement-bpl'
            initial_value = terminal_value - 1
            replacement_branch_opcode = _OPCODE_BY_NAME_MODE[('BPL', 'rel')]
            exit_changed = {'F:N', 'F:Z', 'F:C'}
            header_changed = {'F:N', 'F:Z', 'F:C'}
        else:
            continue
        exit_pc = branch.pc + branch.length
        exit_live = (liveness.live_in[exit_pc]
                     if exit_pc in instructions else config.terminal_live)
        if ({register} | exit_changed) & exit_live:
            continue
        if header_changed & liveness.live_in[header]:
            continue

        new_branch_pc = branch.pc - compare.length
        displacement = _relative_displacement(new_branch_pc, header)
        if displacement is None:
            continue
        original_start = initializer.pc
        original_end = branch.pc + branch.length
        body_bytes = data[header - base:step.pc - base]
        decrement_opcode = _CONTROL_LOOP_STEP[register][2]
        replacement = (
            bytes((initializer.opcode, initial_value)) + body_bytes
            + bytes((decrement_opcode, replacement_branch_opcode,
                     displacement & 0xFF))
        )
        original = data[original_start - base:original_end - base]
        old_cross = int(((branch.pc + 2) & 0xFF00)
                        != (header & 0xFF00))
        new_cross = int(((new_branch_pc + 2) & 0xFF00)
                        != (header & 0xFF00))
        cycle_delta = (-2 * trip_count
                       + (new_cross - old_cross) * (trip_count - 1))
        warnings = [
            'analysis-only semantic option; the compactor will not apply it',
        ]
        if any(item.mode in {'zpx', 'zpy', 'abx', 'aby', 'izx', 'izy'}
               for item in body):
            warnings.append(
                'indexed memory order reverses; classify RAM, overlap, aliases, I/O, and observers'
            )
        result.append(IndexedTraversalReversalOption(
            register, strategy, original_start, original_end,
            start_value, terminal_value, trip_count,
            tuple(item.pc for item in body), index_uses,
            original, replacement, -2, cycle_delta,
            config.timing_policy != 'cycle-exact',
            f'{strategy} visits the same {trip_count} index values in reverse order; '
            f'byte/cycle savings are mechanical but behavioral equivalence is not',
            (
                'establish exact or specification equivalence for reversed iteration order',
                'prove memory ranges and aliases; reject overlap-dependent recurrences',
                'classify every access as ordinary RAM, visible screen/raster state, or hardware I/O',
                'exclude order-sensitive reads/writes, early exits, SMC, and asynchronous observers',
                f'confirm final {register} and changed flags are unobserved under the complete caller contract',
                'perform final-address compaction and connected differential validation before application',
            ), tuple(warnings),
        ))
    return tuple(result)


def _candidate_scan(data: bytes, base: int, instructions: Mapping[int, FlowInstruction],
                    edges: tuple[ScanEdge, ...], known, liveness,
                    config: CFGScanConfig):
    predecessors = defaultdict(set)
    for edge in edges:
        if edge.internal:
            predecessors[edge.target].add((edge.source, edge.kind))
    entry_set = set(config.entries)
    control_targets = {
        edge.target for edge in edges if edge.internal
    } | entry_set
    result = []

    # Reverse a simple fixed-trip incrementing control counter when its value
    # is not part of the loop computation.  This is deliberately limited to a
    # single linear body with one back edge; indexed traversal is semantic and
    # remains outside this deterministic rule.
    ending_at = {
        item.pc + item.length: item for item in instructions.values()
    }
    for branch in instructions.values():
        if branch.mnemonic != 'BNE' or branch.mode != 'rel':
            continue
        compare = ending_at.get(branch.pc)
        step = ending_at.get(compare.pc) if compare is not None else None
        header = branch.operand
        initializer = ending_at.get(header)
        register = (_CONTROL_LOOP_REGISTER.get(initializer.mnemonic)
                    if initializer is not None and initializer.mode == 'imm'
                    else None)
        if (register is None or compare is None or step is None
                or compare.mnemonic != _CONTROL_LOOP_COMPARE[register]
                or compare.mode != 'imm'
                or step.mnemonic != _CONTROL_LOOP_STEP[register][0]
                or step.mode != 'imp'
                or not initializer.pc < header <= step.pc
                or header in entry_set
                or predecessors.get(header, set()) != {(branch.pc, 'branch')}
                or any(pc in control_targets for pc in (
                    step.pc, compare.pc, branch.pc
                ))):
            continue
        body = []
        body_pc = header
        while body_pc < step.pc:
            item = instructions.get(body_pc)
            if item is None:
                body = []
                break
            body.append(item)
            body_pc += item.length
        if body_pc != step.pc:
            continue
        if any(item.pc != header and item.pc in control_targets for item in body):
            continue
        if any(item.mnemonic in _BRANCHES | _TERMINATORS | {'JMP', 'JSR'}
               for item in body):
            continue
        if any(register in (
                instruction_effects(item, None).reads
                | instruction_effects(item, None).writes
        ) for item in body):
            continue
        trip_count = (compare.operand - initializer.operand) & 0xFF
        if trip_count == 0:
            continue
        exit_pc = branch.pc + branch.length
        exit_live = (liveness.live_in[exit_pc]
                     if exit_pc in instructions else config.terminal_live)
        header_live = liveness.live_in[header]
        initial_z_changes = (initializer.operand == 0) != (trip_count == 0)
        if ({register, 'F:C'} & exit_live
                or {'F:N', 'F:C'} & header_live
                or (initial_z_changes and 'F:Z' in header_live)):
            continue
        decrement_opcode = _CONTROL_LOOP_STEP[register][2]
        new_branch_pc = branch.pc - compare.length
        displacement = _relative_displacement(new_branch_pc, header)
        if displacement is None:
            continue
        original_start = initializer.pc
        original_end = branch.pc + branch.length
        original = data[original_start - base:original_end - base]
        body_bytes = data[header - base:step.pc - base]
        replacement = (
            bytes((initializer.opcode, trip_count)) + body_bytes
            + bytes((decrement_opcode, branch.opcode, displacement & 0xFF))
        )
        old_cross = int(((branch.pc + 2) & 0xFF00)
                        != (header & 0xFF00))
        new_cross = int(((new_branch_pc + 2) & 0xFF00)
                        != (header & 0xFF00))
        cycle_delta = (-2 * trip_count
                       + (new_cross - old_cross) * (trip_count - 1))
        timing_ok = config.timing_policy != 'cycle-exact'
        result.append(ReductionCandidate(
            'control-only-loop-reversal', original_start, original_end,
            original, replacement, -2, cycle_delta, timing_ok,
            f'{register} is a control-only fixed-trip counter: reverse '
            f'{initializer.operand}→{compare.operand} into '
            f'{trip_count}→0 and remove {compare.mnemonic}; '
            f'{trip_count} iterations are preserved',
            (
                'assert complete loop entries, direct flow, and terminal liveness',
                f'assert {register} is unused by the body and dead after loop exit',
                'assert changed carry/N intermediates and any changed initial Z are unobserved',
                'repair the final back-edge displacement and all shifted references',
            ), (() if timing_ok else (
                'cycle-exact policy forbids transformation',
            )),
        ))

    for pc in sorted(instructions):
        instruction = instructions[pc]
        next_pc = pc + instruction.length

        unsigned_branch = instructions.get(next_pc)
        if (instruction.mnemonic in _COMPARE_REGISTER
                and instruction.mode == 'imm' and instruction.operand == 0
                and unsigned_branch is not None
                and unsigned_branch.mnemonic in {'BCC', 'BCS'}
                and unsigned_branch.pc not in control_targets
                and not {'F:C', 'F:N', 'F:Z'}
                & liveness.live_out[unsigned_branch.pc]):
            always_taken = unsigned_branch.mnemonic == 'BCS'
            if always_taken:
                replacement = bytes((
                    0x4C, unsigned_branch.operand & 0xFF,
                    unsigned_branch.operand >> 8,
                ))
                crosses = int(
                    ((unsigned_branch.pc + 2) & 0xFF00)
                    != (unsigned_branch.operand & 0xFF00)
                )
                cycle_delta = -2 - crosses
                proof_action = 'BCS is always taken and lowers to JMP'
            else:
                replacement = b''
                cycle_delta = -4
                proof_action = 'BCC is never taken and both instructions delete'
            timing_ok = config.timing_policy != 'cycle-exact'
            result.append(ReductionCandidate(
                'compare-zero-unsigned-branch-fold', instruction.pc,
                unsigned_branch.pc + unsigned_branch.length,
                instruction.data + unsigned_branch.data,
                replacement, len(replacement) - 4, cycle_delta, timing_ok,
                f'{instruction.mnemonic} #$00 always sets C=1 for an 8-bit '
                f'operand, so {proof_action}; compare N/Z/C are dead afterward',
                (
                    'assert complete entries and honest terminal liveness/call summaries',
                    'assert no external entry or code-as-data reference targets the branch inside the folded pair',
                    'repair final layout and the JMP target when present',
                ), (() if timing_ok else ('cycle-exact policy forbids transformation',)),
            ))

        source_register = _LOAD_REGISTER.get(instruction.mnemonic)
        compare = instructions.get(next_pc)
        branch = (instructions.get(next_pc + compare.length)
                  if compare is not None else None)

        # A matching load has already established exactly the N/Z needed for
        # CMP/CPX/CPY #0.  The compare additionally forces C=1, so remove it
        # only when no modeled successor observes C before overwrite.  Keep
        # the branch as an ordinary instruction so final packing can repair it.
        if (source_register is not None and compare is not None and branch is not None
                and _COMPARE_REGISTER.get(compare.mnemonic) == source_register
                and compare.mode == 'imm' and compare.operand == 0
                and branch.mnemonic in {'BEQ', 'BNE'}
                and compare.pc not in control_targets
                and 'F:C' not in liveness.live_out[branch.pc]):
            timing_ok = config.timing_policy != 'cycle-exact'
            result.append(ReductionCandidate(
                'redundant-zero-compare-after-load', compare.pc,
                compare.pc + compare.length, compare.data, b'', -2, -2,
                timing_ok,
                f'{instruction.mnemonic} already establishes the same N/Z as '
                f'{compare.mnemonic} #$00 for {source_register}; the compare-only '
                'C=1 result is dead after the equality branch',
                (
                    'assert complete entries and honest terminal liveness/call summaries',
                    'assert no external entry or code-as-data reference targets the retired compare',
                    'repair the retained equality branch and every shifted reference after packing',
                ), (() if timing_ok else ('cycle-exact policy forbids transformation',)),
            ))

        if (source_register is not None and compare is not None and branch is not None
                and _COMPARE_REGISTER.get(compare.mnemonic) == source_register
                and compare.mode == 'imm' and compare.operand in {0x01, 0xFF}
                and branch.mnemonic in {'BEQ', 'BNE'}
                and compare.pc not in control_targets
                and branch.pc not in control_targets
                and 'F:C' not in liveness.live_out[branch.pc]
                and source_register not in liveness.live_out[branch.pc]):
            target_registers = ((source_register,) if source_register in {'X', 'Y'}
                                else ('X', 'Y'))
            for target_register in target_registers:
                target_load = _OPCODE_BY_NAME_MODE.get(
                    ('LD' + target_register, instruction.mode)
                )
                step = _STEP_OPCODE.get((target_register, compare.operand))
                if (target_load is None or step is None
                        or target_register in liveness.live_out[branch.pc]
                        or OPS[target_load][2] != instruction.length
                        or cpucycles_table[target_load] != cpucycles_table[instruction.opcode]):
                    continue
                step_opcode, step_mnemonic = step
                replacement = (bytes((target_load,)) + instruction.data[1:]
                               + bytes((step_opcode,)) + branch.data)
                timing_ok = config.timing_policy != 'cycle-exact'
                result.append(ReductionCandidate(
                    'compare-immediate-via-index-step', pc,
                    branch.pc + branch.length,
                    instruction.data + compare.data + branch.data,
                    replacement, -1, 0, timing_ok,
                    f'{compare.mnemonic} #${compare.operand:02X} and {step_mnemonic} produce identical N/Z for the loaded value; C, {source_register}, and {target_register} are dead after the equality branch',
                    (
                        'assert complete entries and honest terminal liveness/call summaries',
                        'recompute the retained branch displacement and page crossing after final compaction',
                        'the changed register and carry intermediates must remain unobserved until overwrite',
                    ), (() if timing_ok else ('cycle-exact policy forbids transformation',)),
                ))
                break

        masked_and = compare
        masked_branch = branch
        masked = (_MASKED_BIT_TESTS.get(masked_and.operand)
                  if masked_and is not None
                  and masked_and.mnemonic == 'AND'
                  and masked_and.mode == 'imm' else None)
        if (instruction.mnemonic == 'LDA' and masked is not None
                and masked_branch is not None
                and masked_branch.mnemonic in {'BEQ', 'BNE'}
                and masked_and.pc not in control_targets
                and masked_branch.pc not in control_targets):
            shift_mnemonic, zero_branch, nonzero_branch, changed = masked
            replacement_branch_mnemonic = (
                zero_branch if masked_branch.mnemonic == 'BEQ'
                else nonzero_branch
            )
            replacement_branch_opcode = _OPCODE_BY_NAME_MODE[
                (replacement_branch_mnemonic, 'rel')
            ]
            shift_bytes = (b'' if shift_mnemonic is None else bytes((
                _OPCODE_BY_NAME_MODE[(shift_mnemonic, 'acc')],
            )))
            if not changed & liveness.live_out[masked_branch.pc]:
                replacement = (instruction.data + shift_bytes
                               + bytes((replacement_branch_opcode,
                                        masked_branch.data[1])))
                byte_delta = len(replacement) - (
                    instruction.length + masked_and.length
                    + masked_branch.length
                )
                cycle_delta = (-2 if shift_mnemonic is None else 0)
                timing_ok = config.timing_policy != 'cycle-exact'
                result.append(ReductionCandidate(
                    'masked-bit-test-via-shift', instruction.pc,
                    masked_branch.pc + masked_branch.length,
                    instruction.data + masked_and.data + masked_branch.data,
                    replacement, byte_delta, cycle_delta, timing_ok,
                    f'{masked_and.mnemonic} #${masked_and.operand:02X} equality '
                    f'test lowers to '
                    f'{shift_mnemonic + "; " if shift_mnemonic else ""}'
                    f'{replacement_branch_mnemonic}; changed '
                    f'{", ".join(sorted(changed))} are dead after the branch',
                    (
                        'assert complete entries and honest terminal liveness/call summaries',
                        'assert no external entry or code-as-data reference enters the load/test/branch sequence',
                        'recompute the replacement branch and page crossing after final compaction',
                    ), (() if timing_ok else ('cycle-exact policy forbids transformation',)),
                ))

        # A small conditional select can expose an accumulator-clobbering
        # compare lowering only after its selected value is rehomed.  Keep this
        # deliberately narrower than general register allocation: two loads,
        # one private equality branch to their shared store, and no joins from
        # outside the modeled diamond.
        alternate_load = (instructions.get(branch.pc + branch.length)
                          if branch is not None else None)
        select_store = (instructions.get(alternate_load.pc + alternate_load.length)
                        if alternate_load is not None else None)
        transfer = (_ZERO_COMPARE_TRANSFER.get(_COMPARE_REGISTER.get(compare.mnemonic))
                    if compare is not None else None)
        if (instruction.mnemonic == 'LDA' and instruction.mode in {'imm', 'zp', 'abs'}
                and compare is not None and compare.mode == 'imm'
                and compare.operand == 0 and transfer is not None
                and branch is not None and branch.mnemonic in {'BEQ', 'BNE'}
                and alternate_load is not None and alternate_load.mnemonic == 'LDA'
                and alternate_load.mode in {'imm', 'zp', 'abs'}
                and select_store is not None and select_store.mnemonic == 'STA'
                and select_store.mode in {'zp', 'abs'}
                and branch.operand == select_store.pc
                and compare.pc not in control_targets and branch.pc not in control_targets
                and predecessors.get(alternate_load.pc, set()) == {(branch.pc, 'fallthrough')}
                and predecessors.get(select_store.pc, set()) == {(branch.pc, 'branch')}
                and alternate_load.pc not in entry_set
                and select_store.pc not in entry_set):
            transfer_opcode, transfer_mnemonic, target_register = transfer
            first_load_opcode = _OPCODE_BY_NAME_MODE.get(
                ('LD' + target_register, instruction.mode)
            )
            alternate_load_opcode = _OPCODE_BY_NAME_MODE.get(
                ('LD' + target_register, alternate_load.mode)
            )
            store_opcode = _OPCODE_BY_NAME_MODE.get(
                ('ST' + target_register, select_store.mode)
            )
            changed = {'A', target_register, 'F:C'}
            if (first_load_opcode is not None and alternate_load_opcode is not None
                    and store_opcode is not None
                    and target_register not in liveness.live_in[instruction.pc]
                    and not changed & liveness.live_out[select_store.pc]
                    and OPS[first_load_opcode][2] == instruction.length
                    and OPS[alternate_load_opcode][2] == alternate_load.length
                    and OPS[store_opcode][2] == select_store.length
                    and cpucycles_table[first_load_opcode] == cpucycles_table[instruction.opcode]
                    and cpucycles_table[alternate_load_opcode] == cpucycles_table[alternate_load.opcode]
                    and cpucycles_table[store_opcode] == cpucycles_table[select_store.opcode]):
                replacement = (
                    bytes((first_load_opcode,)) + instruction.data[1:]
                    + bytes((transfer_opcode,)) + branch.data
                    + bytes((alternate_load_opcode,)) + alternate_load.data[1:]
                    + bytes((store_opcode,)) + select_store.data[1:]
                )
                timing_ok = config.timing_policy != 'cycle-exact'
                result.append(ReductionCandidate(
                    'zero-compare-select-via-rehome', pc,
                    select_store.pc + select_store.length,
                    instruction.data + compare.data + branch.data
                    + alternate_load.data + select_store.data,
                    replacement, -1, 0, timing_ok,
                    f'the two-path A value is rehomed to dead {target_register}; {transfer_mnemonic} then replaces {compare.mnemonic} #$00 with identical equality N/Z, while A, {target_register}, and changed C are dead after the shared store',
                    (
                        'assert complete entries, branch predecessors, and honest terminal liveness/call summaries',
                        'assert no external entry or code-as-data reference enters the selected diamond or shared store',
                        'recompute the retained equality branch after final compaction',
                    ), (() if timing_ok else ('cycle-exact policy forbids transformation',)),
                ))

        if (instruction.mnemonic == 'LDA' and compare is not None and branch is not None
                and compare.mnemonic == 'CMP' and compare.mode == 'imm'
                and compare.operand == 0x02 and branch.mnemonic in {'BCC', 'BCS'}
                and compare.pc not in control_targets and branch.pc not in control_targets
                and not {'A', 'F:C', 'F:N', 'F:Z'} & liveness.live_out[branch.pc]):
            replacement_branch = 0xF0 if branch.mnemonic == 'BCC' else 0xD0
            replacement = instruction.data + bytes((0x4A, replacement_branch, branch.data[1]))
            timing_ok = config.timing_policy != 'cycle-exact'
            result.append(ReductionCandidate(
                'compare-two-via-lsr', pc, branch.pc + branch.length,
                instruction.data + compare.data + branch.data,
                replacement, -1, 0, timing_ok,
                f'LSR makes Z=1 exactly for loaded values below 2, so {branch.mnemonic} lowers to {"BEQ" if branch.mnemonic == "BCC" else "BNE"}; A/C/N/Z are dead after the branch',
                (
                    'assert complete entries and honest terminal liveness/call summaries',
                    'recompute the replacement branch and page crossing after final compaction',
                ), (() if timing_ok else ('cycle-exact policy forbids transformation',)),
            ))

        if (instruction.mnemonic, instruction.mode) in _IDEMPOTENT_DUPLICATES:
            following_idempotent = instructions.get(next_pc)
            if (following_idempotent is not None
                    and following_idempotent.data == instruction.data
                    and following_idempotent.pc not in control_targets):
                timing_ok = config.timing_policy != 'cycle-exact'
                result.append(ReductionCandidate(
                    'duplicate-idempotent-operation', pc,
                    following_idempotent.pc + following_idempotent.length,
                    instruction.data + following_idempotent.data,
                    instruction.data, -instruction.length,
                    -cpucycles_table[following_idempotent.opcode], timing_ok,
                    f'adjacent identical {instruction.mnemonic} is idempotent over architectural state and has no modeled memory/I/O effect',
                    ('assert complete entries and no code-as-data reference to the retired operation',),
                    (() if timing_ok else ('cycle-exact policy forbids transformation',)),
                ))

        if instruction.mnemonic in {'TAX', 'TAY', 'TXA', 'TYA'}:
            following_transfer = instructions.get(next_pc)
            if (following_transfer is not None
                    and following_transfer.mnemonic == instruction.mnemonic
                    and following_transfer.pc not in control_targets):
                timing_ok = config.timing_policy != 'cycle-exact'
                result.append(ReductionCandidate(
                    'duplicate-transfer', pc,
                    following_transfer.pc + following_transfer.length,
                    instruction.data + following_transfer.data,
                    instruction.data, -1, -2, timing_ok,
                    f'adjacent {instruction.mnemonic} repeats the same register value and N/Z established by the first transfer',
                    ('assert complete entries and no code-as-data reference to the retired transfer',),
                    (() if timing_ok else ('cycle-exact policy forbids transformation',)),
                ))

        if instruction.mnemonic == 'JSR':
            following = instructions.get(next_pc)
            if following and following.mnemonic == 'RTS':
                incoming = predecessors.get(next_pc, set())
                private_rts = incoming == {(pc, 'fallthrough')} and next_pc not in entry_set
                if private_rts:
                    timing_ok = config.timing_policy != 'cycle-exact'
                    result.append(ReductionCandidate(
                        'tail-call-jsr-rts', pc, next_pc + 1,
                        instruction.data + following.data,
                        bytes((0x4C, instruction.operand & 0xFF,
                               (instruction.operand >> 8) & 0xFF)),
                        -1, -9, timing_ok,
                        'adjacent JSR/RTS with no other discovered control predecessor to the RTS',
                        (
                            'assert conventional JSR/RTS return-stack semantics and that the callee does not inspect this discarded frame',
                            'assert complete entries/control references and no code-as-data reference to the retired RTS',
                            'recompute all addresses and references during final compaction',
                        ),
                        (() if timing_ok else ('cycle-exact policy forbids transformation',)),
                    ))

        if instruction.mnemonic == 'JMP' and instruction.mode == 'abs':
            facts = known.facts_in(pc)
            selected = next((resource for resource in _FACT_ORDER if resource in facts), None)
            displacement = _relative_displacement(pc, instruction.operand)
            if selected is not None and displacement is not None:
                opcode, mnemonic = _BRANCH_FOR_FACT[(selected, facts[selected])]
                crosses = (((pc + 2) & 0xFF00) != (instruction.operand & 0xFF00))
                cycle_delta = int(crosses)
                timing_ok = (config.timing_policy == 'ordinary'
                             or (config.timing_policy == 'interrupt' and not crosses))
                if config.timing_policy == 'cycle-exact':
                    timing_ok = False
                warnings = []
                if crosses:
                    warnings.append('taken relative branch crosses a page and costs one cycle more than JMP')
                if not timing_ok:
                    warnings.append(f'{config.timing_policy} timing policy forbids this candidate')
                result.append(ReductionCandidate(
                    'known-flag-short-jump', pc, pc + 3, instruction.data,
                    bytes((opcode, displacement & 0xFF)), -1, cycle_delta, timing_ok,
                    f'{selected}={facts[selected]} on every modeled incoming path makes {mnemonic} unconditionally taken',
                    (
                        'assert all entries and incoming control paths are represented',
                        'recompute signed displacement and page crossing after final compaction',
                    ), tuple(dict.fromkeys(warnings)),
                ))

        if instruction.mnemonic in _BRANCHES:
            outcome = known.branch_outcomes.get(pc)
            if outcome == 'never-taken':
                timing_ok = config.timing_policy != 'cycle-exact'
                result.append(ReductionCandidate(
                    'never-taken-branch-deletion', pc, pc + 2, instruction.data,
                    b'', -2, -2, timing_ok,
                    'branch condition is false on every modeled incoming path',
                    (
                        'assert all entries and incoming control paths are represented',
                        'repair final layout and every shifted reference',
                    ), (() if timing_ok else ('cycle-exact policy forbids transformation',)),
                ))
            elif outcome == 'always-taken' and instruction.operand == next_pc:
                timing_ok = config.timing_policy != 'cycle-exact'
                result.append(ReductionCandidate(
                    'branch-to-fallthrough-deletion', pc, pc + 2,
                    instruction.data, b'', -2, -3, timing_ok,
                    'the guaranteed-taken branch targets its own fallthrough instruction',
                    (
                        'assert all entries and incoming control paths are represented',
                        'repair final layout and every shifted reference',
                    ), (() if timing_ok else ('cycle-exact policy forbids transformation',)),
                ))
    return tuple(result)


def scan_cfg_candidates(data: bytes, *, base_address: int,
                        config: CFGScanConfig) -> CFGScanResult:
    """Discover reachable code and return reduction candidates without mutation."""
    data = bytes(data)
    if not data:
        raise CFGScanError('image must not be empty')
    if not 0 <= base_address <= 0xFFFF or base_address + len(data) > 0x10000:
        raise CFGScanError('image does not fit in the 16-bit address space')
    end = base_address + len(data)
    for entry in config.entries:
        if not _inside(entry, base_address, end):
            raise CFGScanError(f'entry ${entry:04X} is outside the image')

    by_pc, edges, stops, issues, limit_reached = _discover(data, base_address, config)
    instructions = tuple(by_pc[pc] for pc in sorted(by_pc))
    if not instructions:
        raise CFGScanError('no documented instructions were discovered')
    decimal_policy, decimal_invariant = _decimal_contract(by_pc, edges, issues, config)

    entry_facts = dict(config.entry_facts)
    entry_states: dict[int, dict[str, int]] = {}
    for entry in config.entries:
        if entry in by_pc:
            facts = dict(entry_facts)
            facts.setdefault('F:D', 0)
            entry_states[entry] = facts
    for edge in edges:
        if edge.kind == 'call' and edge.internal and edge.target in by_pc:
            facts = entry_states.setdefault(edge.target, {})
            if decimal_invariant:
                facts.setdefault('F:D', 0)

    call_summaries = None
    if decimal_invariant:
        preserves_d = CallSummary(ARCH_RESOURCES, ARCH_RESOURCES - {'F:D'})
        call_summaries = {
            edge.target: preserves_d for edge in edges if edge.kind == 'call'
        }
    flow_edges = tuple(
        FlowEdge(edge.source, edge.target, edge.kind)
        for edge in edges if edge.internal
    )
    known = analyze_known_state(
        instructions, flow_edges, entries=entry_states, call_summaries=call_summaries
    )
    liveness = analyze_liveness(
        instructions, flow_edges, terminal_live=config.terminal_live,
        call_summaries=call_summaries,
    )
    blocks = _basic_blocks(by_pc, edges, config.entries)
    candidates = _candidate_scan(
        data, base_address, by_pc, edges, known, liveness, config
    )
    register_rehomes = _register_rehome_scan(
        by_pc, blocks, liveness, call_summaries
    )
    indexed_traversal_reversals = _indexed_traversal_reversal_scan(
        data, base_address, by_pc, edges, liveness, config
    )
    live_in = tuple((pc, tuple(sorted(values)))
                    for pc, values in sorted(liveness.live_in.items()))
    live_out = tuple((pc, tuple(sorted(values)))
                     for pc, values in sorted(liveness.live_out.items()))
    available_in = tuple((pc, tuple(sorted(_ALLOCATABLE_REGISTERS - values)))
                         for pc, values in sorted(liveness.live_in.items()))
    available_out = tuple((pc, tuple(sorted(_ALLOCATABLE_REGISTERS - values)))
                          for pc, values in sorted(liveness.live_out.items()))
    available_flags_in = tuple((pc, tuple(sorted(_ALLOCATABLE_FLAGS - values)))
                               for pc, values in sorted(liveness.live_in.items()))
    available_flags_out = tuple((pc, tuple(sorted(_ALLOCATABLE_FLAGS - values)))
                                for pc, values in sorted(liveness.live_out.items()))
    return CFGScanResult(
        data, base_address, config.entries, instructions, edges, blocks,
        candidates, register_rehomes, indexed_traversal_reversals,
        stops, issues, limit_reached, decimal_policy,
        decimal_invariant, tuple(sorted(known.state_in.items())),
        tuple(sorted(known.branch_outcomes.items())), live_in, live_out,
        available_in, available_out, available_flags_in, available_flags_out,
        known.iterations, liveness.iterations,
    )
