#!/usr/bin/env python3
"""Conservative register/flag liveness and known-state analysis for 6502 CFGs.

This module analyzes already established documented-instruction boundaries. It
is not a disassembler, alias analyzer, function finder, or equivalence proof.
Unknown operations/calls lose facts conservatively; callers supply call summaries
when they need stronger interprocedural evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from isa6502 import OPS

REGISTERS = frozenset(('A', 'X', 'Y', 'SP'))
FLAGS = frozenset(('F:N', 'F:V', 'F:D', 'F:I', 'F:Z', 'F:C'))
ARCH_RESOURCES = REGISTERS | FLAGS


class DataflowError(ValueError):
    """The supplied instruction/CFG model is inconsistent or unsupported."""


@dataclass(frozen=True)
class FlowInstruction:
    pc: int
    opcode: int
    mnemonic: str
    mode: str
    length: int
    data: bytes
    operand: int | None


@dataclass(frozen=True)
class FlowEdge:
    source: int
    target: int
    kind: str


@dataclass(frozen=True)
class CallSummary:
    reads: frozenset[str]
    writes: frozenset[str]

    def __post_init__(self):
        object.__setattr__(self, 'reads', frozenset(self.reads))
        object.__setattr__(self, 'writes', frozenset(self.writes))
        unknown = (self.reads | self.writes) - ARCH_RESOURCES
        if unknown:
            raise DataflowError(f'unknown call-summary resources: {sorted(unknown)}')


@dataclass(frozen=True)
class ResourceEffects:
    reads: frozenset[str]
    writes: frozenset[str]


@dataclass(frozen=True)
class LivenessResult:
    live_in: Mapping[int, frozenset[str]]
    live_out: Mapping[int, frozenset[str]]
    iterations: int


@dataclass(frozen=True)
class KnownStateResult:
    state_in: Mapping[int, tuple[tuple[str, int], ...]]
    state_out: Mapping[int, tuple[tuple[str, int], ...]]
    branch_outcomes: Mapping[int, str]
    iterations: int

    def facts_in(self, pc: int) -> dict[str, int]:
        return dict(self.state_in.get(pc, ()))

    def facts_out(self, pc: int) -> dict[str, int]:
        return dict(self.state_out.get(pc, ()))


_UNKNOWN_CALL = CallSummary(ARCH_RESOURCES, ARCH_RESOURCES)
_BRANCH_FLAG = {
    'BPL': ('F:N', 0), 'BMI': ('F:N', 1),
    'BVC': ('F:V', 0), 'BVS': ('F:V', 1),
    'BCC': ('F:C', 0), 'BCS': ('F:C', 1),
    'BNE': ('F:Z', 0), 'BEQ': ('F:Z', 1),
}


def _operand(mode: str, data: bytes, pc: int) -> int | None:
    if mode in {'zp', 'zpx', 'zpy', 'izx', 'izy', 'imm'}:
        return data[1]
    if mode in {'abs', 'abx', 'aby', 'ind'}:
        return data[1] | (data[2] << 8)
    if mode == 'rel':
        displacement = data[1] - 0x100 if data[1] & 0x80 else data[1]
        return (pc + 2 + displacement) & 0xFFFF
    return None


def decode_at(memory: bytes, pc: int) -> FlowInstruction:
    if len(memory) != 0x10000:
        raise DataflowError('decode memory must contain exactly 64 KiB')
    if not 0 <= pc <= 0xFFFF:
        raise DataflowError('instruction PC must be 16-bit')
    opcode = memory[pc]
    if opcode not in OPS:
        raise DataflowError(f'unknown/undocumented opcode ${opcode:02X} at ${pc:04X}')
    mnemonic, mode, length = OPS[opcode]
    if pc + length > 0x10000:
        raise DataflowError(f'truncated {mnemonic} at ${pc:04X}')
    data = bytes(memory[pc:pc + length])
    return FlowInstruction(pc, opcode, mnemonic, mode, length, data,
                           _operand(mode, data, pc))


def decode_pcs(memory: bytes, pcs: Iterable[int]) -> tuple[FlowInstruction, ...]:
    result = tuple(decode_at(memory, pc) for pc in sorted(set(pcs)))
    if not result:
        raise DataflowError('at least one instruction PC is required')
    return result


def _memory_resource(instruction: FlowInstruction) -> str | None:
    if instruction.mode in {'zp', 'abs'} and instruction.operand is not None:
        return f'M:{instruction.operand:04X}'
    if instruction.mode in {'zpx', 'zpy', 'abx', 'aby', 'izx', 'izy', 'ind'}:
        return 'M:*'
    return None


def instruction_effects(instruction: FlowInstruction,
                        call_summaries: Mapping[int, CallSummary] | None = None) -> ResourceEffects:
    """Return conservative register/flag/direct-memory effects."""
    summaries = call_summaries or {}
    mnem, mode = instruction.mnemonic, instruction.mode
    reads: set[str] = set()
    writes: set[str] = set()
    memory = _memory_resource(instruction)

    if mode in {'zpx', 'abx', 'izx'}:
        reads.add('X')
    if mode in {'zpy', 'aby', 'izy'}:
        reads.add('Y')

    if mnem in {'LDA', 'LDX', 'LDY'}:
        if mode != 'imm' and memory:
            reads.add(memory)
        writes.update((mnem[-1], 'F:N', 'F:Z'))
    elif mnem in {'STA', 'STX', 'STY'}:
        reads.add(mnem[-1])
        if memory:
            writes.add(memory)
    elif mnem in {'ORA', 'AND', 'EOR'}:
        reads.add('A')
        if mode != 'imm' and memory:
            reads.add(memory)
        writes.update(('A', 'F:N', 'F:Z'))
    elif mnem in {'ADC', 'SBC'}:
        reads.update(('A', 'F:C', 'F:D'))
        if mode != 'imm' and memory:
            reads.add(memory)
        writes.update(('A', 'F:N', 'F:V', 'F:Z', 'F:C'))
    elif mnem in {'CMP', 'CPX', 'CPY'}:
        reads.add({'CMP': 'A', 'CPX': 'X', 'CPY': 'Y'}[mnem])
        if mode != 'imm' and memory:
            reads.add(memory)
        writes.update(('F:N', 'F:Z', 'F:C'))
    elif mnem == 'BIT':
        reads.add('A')
        if memory:
            reads.add(memory)
        writes.update(('F:N', 'F:V', 'F:Z'))
    elif mnem in {'ASL', 'LSR', 'ROL', 'ROR'}:
        target = 'A' if mode == 'acc' else memory
        if target:
            reads.add(target); writes.add(target)
        if mnem in {'ROL', 'ROR'}:
            reads.add('F:C')
        writes.update(('F:N', 'F:Z', 'F:C'))
    elif mnem in {'INC', 'DEC'}:
        if memory:
            reads.add(memory); writes.add(memory)
        writes.update(('F:N', 'F:Z'))
    elif mnem in {'INX', 'DEX', 'INY', 'DEY'}:
        register = mnem[-1]
        reads.add(register)
        writes.update((register, 'F:N', 'F:Z'))
    elif mnem in {'TAX', 'TAY', 'TXA', 'TYA'}:
        source, target = {
            'TAX': ('A', 'X'), 'TAY': ('A', 'Y'),
            'TXA': ('X', 'A'), 'TYA': ('Y', 'A'),
        }[mnem]
        reads.add(source); writes.update((target, 'F:N', 'F:Z'))
    elif mnem in {'CLC', 'SEC'}:
        writes.add('F:C')
    elif mnem in {'CLD', 'SED'}:
        writes.add('F:D')
    elif mnem in {'CLI', 'SEI'}:
        writes.add('F:I')
    elif mnem == 'CLV':
        writes.add('F:V')
    elif mnem in _BRANCH_FLAG:
        reads.add(_BRANCH_FLAG[mnem][0])
    elif mnem == 'JSR':
        summary = summaries.get(instruction.operand, _UNKNOWN_CALL)
        reads.update(summary.reads); writes.update(summary.writes)
    elif mnem in {'PHA', 'PHP'}:
        if mnem == 'PHA':
            reads.add('A')
        else:
            reads.update(FLAGS)
        reads.add('SP'); writes.update(('SP', 'M:*'))
    elif mnem in {'PLA', 'PLP'}:
        reads.update(('SP', 'M:*')); writes.add('SP')
        if mnem == 'PLA':
            writes.update(('A', 'F:N', 'F:Z'))
        else:
            writes.update(FLAGS)
    elif mnem == 'TXS':
        reads.add('X'); writes.add('SP')
    elif mnem == 'TSX':
        reads.add('SP'); writes.update(('X', 'F:N', 'F:Z'))
    elif mnem in {'RTS', 'RTI'}:
        reads.update(('SP', 'M:*'))
        if mnem == 'RTI':
            writes.update(FLAGS)
    elif mnem in {'JMP', 'NOP', 'BRK'}:
        pass
    else:
        # OPS contains only documented instructions; fail if this effect model lags.
        raise DataflowError(f'effect semantics missing for {mnem} at ${instruction.pc:04X}')
    return ResourceEffects(frozenset(reads), frozenset(writes))


def _normalized_edges(edges: Iterable[FlowEdge], instructions: Mapping[int, FlowInstruction]):
    """Combine explicit control edges with implicit sequential instruction flow."""
    edge_set: set[tuple[int, int, str]] = set()
    for edge in edges:
        if edge.kind == 'call':
            continue
        if edge.source not in instructions:
            raise DataflowError(f'edge source ${edge.source:04X} is not an instruction')
        if edge.target in instructions:
            edge_set.add((edge.source, edge.target, edge.kind))
    branches = set(_BRANCH_FLAG)
    for instruction in instructions.values():
        pc, fallthrough = instruction.pc, instruction.pc + instruction.length
        if instruction.mnemonic in branches:
            if instruction.operand in instructions:
                edge_set.add((pc, instruction.operand, 'branch'))
            if fallthrough in instructions:
                edge_set.add((pc, fallthrough, 'fallthrough'))
        elif instruction.mnemonic == 'JMP':
            if instruction.mode == 'abs' and instruction.operand in instructions:
                edge_set.add((pc, instruction.operand, 'jump'))
        elif instruction.mnemonic not in {'RTS', 'RTI', 'BRK'}:
            if fallthrough in instructions:
                edge_set.add((pc, fallthrough, 'fallthrough'))
    result = defaultdict(list)
    for source, target, kind in sorted(edge_set):
        result[source].append(FlowEdge(source, target, kind))
    return result


# Imported late only to keep the public module namespace focused.
from collections import defaultdict  # noqa: E402


def analyze_liveness(instructions: Iterable[FlowInstruction], edges: Iterable[FlowEdge], *,
                     terminal_live: Iterable[str] = (),
                     call_summaries: Mapping[int, CallSummary] | None = None) -> LivenessResult:
    by_pc = {item.pc: item for item in instructions}
    if not by_pc:
        raise DataflowError('liveness requires instructions')
    successors = _normalized_edges(edges, by_pc)
    terminal = frozenset(terminal_live)
    unknown = terminal - ARCH_RESOURCES
    if unknown:
        raise DataflowError(f'unknown terminal-live resources: {sorted(unknown)}')
    effects = {pc: instruction_effects(item, call_summaries) for pc, item in by_pc.items()}
    live_in = {pc: frozenset() for pc in by_pc}
    live_out = {pc: frozenset() for pc in by_pc}
    iterations = 0
    changed = True
    while changed:
        iterations += 1
        if iterations > len(by_pc) * 20 + 100:
            raise DataflowError('liveness did not converge')
        changed = False
        for pc in sorted(by_pc, reverse=True):
            outgoing = successors.get(pc, ())
            new_out = frozenset().union(*(live_in[edge.target] for edge in outgoing)) if outgoing else terminal
            effect = effects[pc]
            new_in = effect.reads | (new_out - effect.writes)
            if new_out != live_out[pc] or new_in != live_in[pc]:
                live_out[pc] = frozenset(new_out)
                live_in[pc] = frozenset(new_in)
                changed = True
    return LivenessResult(live_in, live_out, iterations)


def _nz(value: int) -> dict[str, int]:
    value &= 0xFF
    return {'F:N': (value >> 7) & 1, 'F:Z': int(value == 0)}


def _set_or_forget(state: dict[str, int], updates: Mapping[str, int], writes: Iterable[str]):
    for resource in writes:
        if resource in ARCH_RESOURCES:
            state.pop(resource, None)
    for resource, value in updates.items():
        state[resource] = value


def _transfer_known(instruction: FlowInstruction, incoming: Mapping[str, int],
                    call_summaries: Mapping[int, CallSummary] | None) -> dict[str, int]:
    state = dict(incoming)
    effect = instruction_effects(instruction, call_summaries)
    mnem, mode, operand = instruction.mnemonic, instruction.mode, instruction.operand
    updates: dict[str, int] = {}

    if mnem in {'LDA', 'LDX', 'LDY'} and mode == 'imm':
        register = mnem[-1]; updates[register] = operand
        updates.update(_nz(operand))
    elif mnem in {'CLC', 'SEC'}:
        updates['F:C'] = int(mnem == 'SEC')
    elif mnem in {'CLD', 'SED'}:
        updates['F:D'] = int(mnem == 'SED')
    elif mnem in {'CLI', 'SEI'}:
        updates['F:I'] = int(mnem == 'SEI')
    elif mnem == 'CLV':
        updates['F:V'] = 0
    elif mnem in {'TAX', 'TAY', 'TXA', 'TYA'}:
        source, target = {
            'TAX': ('A', 'X'), 'TAY': ('A', 'Y'),
            'TXA': ('X', 'A'), 'TYA': ('Y', 'A'),
        }[mnem]
        if source in state:
            updates[target] = state[source]; updates.update(_nz(state[source]))
    elif mnem in {'INX', 'DEX', 'INY', 'DEY'}:
        register = mnem[-1]
        if register in state:
            delta = 1 if mnem in {'INX', 'INY'} else -1
            value = (state[register] + delta) & 0xFF
            updates[register] = value; updates.update(_nz(value))
    elif mnem in {'ORA', 'AND', 'EOR'} and mode == 'imm' and 'A' in state:
        operation = {'ORA': lambda a, b: a | b, 'AND': lambda a, b: a & b,
                     'EOR': lambda a, b: a ^ b}[mnem]
        value = operation(state['A'], operand) & 0xFF
        updates['A'] = value; updates.update(_nz(value))
    elif mnem in {'ASL', 'LSR'} and mode == 'acc' and 'A' in state:
        original = state['A']
        if mnem == 'ASL':
            value = (original << 1) & 0xFF; carry = (original >> 7) & 1
        else:
            value = original >> 1; carry = original & 1
        updates.update({'A': value, 'F:C': carry}); updates.update(_nz(value))
    elif mnem in {'CMP', 'CPX', 'CPY'} and mode == 'imm':
        register = {'CMP': 'A', 'CPX': 'X', 'CPY': 'Y'}[mnem]
        if register in state:
            value = state[register]
            result = (value - operand) & 0xFF
            updates.update({'F:C': int(value >= operand),
                            'F:Z': int(value == operand),
                            'F:N': (result >> 7) & 1})
    elif mnem in {'ADC', 'SBC'} and mode == 'imm':
        if all(resource in state for resource in ('A', 'F:C', 'F:D')) and state['F:D'] == 0:
            a, carry = state['A'], state['F:C']
            if mnem == 'ADC':
                total = a + operand + carry; value = total & 0xFF
                updates['F:C'] = int(total > 0xFF)
                updates['F:V'] = int((~(a ^ operand) & (a ^ value) & 0x80) != 0)
            else:
                total = a - operand - (1 - carry); value = total & 0xFF
                updates['F:C'] = int(total >= 0)
                updates['F:V'] = int(((a ^ operand) & (a ^ value) & 0x80) != 0)
            updates['A'] = value; updates.update(_nz(value))
    _set_or_forget(state, updates, effect.writes)
    return state


def _merge_known(existing: dict[str, int] | None, incoming: Mapping[str, int]) -> tuple[dict[str, int], bool]:
    if existing is None:
        result = dict(incoming)
        return result, True
    result = {resource: value for resource, value in existing.items()
              if incoming.get(resource) == value}
    return result, result != existing


def analyze_known_state(instructions: Iterable[FlowInstruction], edges: Iterable[FlowEdge], *,
                        entries: Mapping[int, Mapping[str, int]],
                        call_summaries: Mapping[int, CallSummary] | None = None) -> KnownStateResult:
    by_pc = {item.pc: item for item in instructions}
    if not by_pc:
        raise DataflowError('known-state analysis requires instructions')
    successors = _normalized_edges(edges, by_pc)
    for pc, facts in entries.items():
        if pc not in by_pc:
            raise DataflowError(f'entry ${pc:04X} is not an instruction')
        unknown = set(facts) - ARCH_RESOURCES
        if unknown:
            raise DataflowError(f'unknown entry resources: {sorted(unknown)}')
    state_in: dict[int, dict[str, int] | None] = {pc: None for pc in by_pc}
    worklist = []
    for pc, facts in sorted(entries.items()):
        state_in[pc] = dict(facts); worklist.append(pc)
    state_out: dict[int, dict[str, int]] = {}
    iterations = 0
    while worklist:
        pc = worklist.pop(0); iterations += 1
        if iterations > len(by_pc) * 100 + 1000:
            raise DataflowError('known-state analysis did not converge')
        incoming = state_in[pc]
        if incoming is None:
            continue
        outgoing_state = _transfer_known(by_pc[pc], incoming, call_summaries)
        state_out[pc] = outgoing_state
        instruction = by_pc[pc]
        branch = _BRANCH_FLAG.get(instruction.mnemonic)
        for edge in successors.get(pc, ()):
            propagated = dict(outgoing_state)
            if branch and edge.kind in {'branch', 'fallthrough'}:
                flag, taken_value = branch
                propagated[flag] = taken_value if edge.kind == 'branch' else 1 - taken_value
            merged, changed = _merge_known(state_in[edge.target], propagated)
            if changed:
                state_in[edge.target] = merged
                if edge.target not in worklist:
                    worklist.append(edge.target)
    outcomes = {}
    for pc, instruction in by_pc.items():
        branch = _BRANCH_FLAG.get(instruction.mnemonic)
        incoming = state_in[pc]
        if not branch or incoming is None or branch[0] not in incoming:
            continue
        outcomes[pc] = 'always-taken' if incoming[branch[0]] == branch[1] else 'never-taken'
    frozen_in = {pc: tuple(sorted((state or {}).items())) for pc, state in state_in.items()}
    frozen_out = {pc: tuple(sorted(state_out.get(pc, {}).items())) for pc in by_pc}
    return KnownStateResult(frozen_in, frozen_out, outcomes, iterations)
