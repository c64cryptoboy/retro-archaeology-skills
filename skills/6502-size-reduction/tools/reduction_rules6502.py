#!/usr/bin/env python3
"""Conservative deterministic size reductions for straight-line NMOS-6502 blocks.

This module owns signature-based reductions.  It deliberately does not discover
functions, restructure loops, repair external references, or decide that timing
is unimportant.  Callers supply the block boundary, entry facts, terminal
liveness, and timing policy; image integration remains a separate guarded step.
"""

from __future__ import annotations

from dataclasses import dataclass

from cpu6502 import cpucycles_table
from dataflow6502 import (  # noqa: E402
    ARCH_RESOURCES, analyze_known_state, analyze_liveness, decode_at,
)
from isa6502 import OPS


class ReductionError(ValueError):
    """The block or declared reduction contract is unsupported or unsafe."""


@dataclass(frozen=True)
class ReductionConfig:
    timing_policy: str = 'ordinary'
    terminal_live: frozenset[str] = frozenset(ARCH_RESOURCES)
    entry_facts: tuple[tuple[str, int], ...] = ()
    enabled_rules: frozenset[str] = frozenset({
        'known-state-redundancy',
        'duplicate-flag-setter',
        'transfer-roundtrip',
        'dead-source-load-transfer-fusion',
        'zero-page-operand-narrowing',
        'known-carry-immediate-adjustment',
    })
    assert_no_interior_entries: bool = False
    assert_no_code_as_data: bool = False

    def __post_init__(self):
        if self.timing_policy not in {'ordinary', 'interrupt', 'cycle-exact'}:
            raise ReductionError('timing_policy must be ordinary, interrupt, or cycle-exact')
        object.__setattr__(self, 'terminal_live', frozenset(self.terminal_live))
        object.__setattr__(self, 'enabled_rules', frozenset(self.enabled_rules))
        unknown = self.terminal_live - ARCH_RESOURCES
        if unknown:
            raise ReductionError(f'unknown terminal-live resources: {sorted(unknown)}')
        facts = dict(self.entry_facts)
        if len(facts) != len(self.entry_facts):
            raise ReductionError('entry facts must be unique')
        if set(facts) - ARCH_RESOURCES:
            raise ReductionError(f'unknown entry-fact resources: {sorted(set(facts) - ARCH_RESOURCES)}')
        for resource, value in facts.items():
            limit = 1 if resource.startswith('F:') else 255
            if not isinstance(value, int) or not 0 <= value <= limit:
                raise ReductionError(f'invalid entry fact {resource}={value}')
        supported = {
            'known-state-redundancy', 'duplicate-flag-setter',
            'transfer-roundtrip', 'dead-source-load-transfer-fusion',
            'zero-page-operand-narrowing',
            'known-carry-immediate-adjustment',
        }
        if self.enabled_rules - supported:
            raise ReductionError(f'unknown reduction rules: {sorted(self.enabled_rules - supported)}')


@dataclass(frozen=True)
class _Token:
    data: bytes
    original_start: int
    original_end: int


@dataclass(frozen=True)
class ReductionLedgerEntry:
    rule: str
    original_start: int
    original_end: int
    original_bytes: bytes
    replacement_bytes: bytes
    byte_delta: int
    cycle_delta: int
    proof: str


@dataclass(frozen=True)
class ReductionResult:
    original: bytes
    reduced: bytes
    base_address: int
    original_cycles: int
    reduced_cycles: int
    ledger: tuple[ReductionLedgerEntry, ...]
    warnings: tuple[str, ...]
    timing_policy: str

    @property
    def byte_delta(self):
        return len(self.reduced) - len(self.original)

    @property
    def cycle_delta(self):
        return self.reduced_cycles - self.original_cycles


_FLAG_SETTERS = {
    'CLC': ('F:C', 0), 'SEC': ('F:C', 1),
    'CLD': ('F:D', 0), 'SED': ('F:D', 1),
    'CLI': ('F:I', 0), 'SEI': ('F:I', 1),
    'CLV': ('F:V', 0),
}

# (load mnemonic, transfer mnemonic, mode) -> (fused opcode, dead source)
_FUSIONS = {
    ('LDA', 'TAX', 'imm'): (0xA2, 'A'),
    ('LDA', 'TAX', 'zp'):  (0xA6, 'A'),
    ('LDA', 'TAX', 'abs'): (0xAE, 'A'),
    ('LDA', 'TAX', 'aby'): (0xBE, 'A'),
    ('LDA', 'TAY', 'imm'): (0xA0, 'A'),
    ('LDA', 'TAY', 'zp'):  (0xA4, 'A'),
    ('LDA', 'TAY', 'abs'): (0xAC, 'A'),
    ('LDA', 'TAY', 'abx'): (0xBC, 'A'),
    ('LDX', 'TXA', 'imm'): (0xA9, 'X'),
    ('LDX', 'TXA', 'zp'):  (0xA5, 'X'),
    ('LDX', 'TXA', 'abs'): (0xAD, 'X'),
    ('LDX', 'TXA', 'aby'): (0xB9, 'X'),
    ('LDY', 'TYA', 'imm'): (0xA9, 'Y'),
    ('LDY', 'TYA', 'zp'):  (0xA5, 'Y'),
    ('LDY', 'TYA', 'abs'): (0xAD, 'Y'),
    ('LDY', 'TYA', 'abx'): (0xBD, 'Y'),
}

_CARRY_ADJUSTMENT = {
    ('CLC', 'ADC'): 1,  # incoming carry; ADC #(k-1) then adds it back
    ('SEC', 'SBC'): 0,  # incoming borrow; SBC #(k-1) consumes it
}

_ROUNDTRIPS = {
    ('TAX', 'TXA'), ('TAY', 'TYA'),
    ('TXA', 'TAX'), ('TYA', 'TAY'),
}

_OPCODE_BY_NAME_MODE = {
    (mnemonic, mode): opcode
    for opcode, (mnemonic, mode, _length) in OPS.items()
}
_ZERO_PAGE_MODE = {'abs': 'zp', 'abx': 'zpx', 'aby': 'zpy'}

_FORBIDDEN_CONTROL = frozenset({
    'BCC', 'BCS', 'BEQ', 'BMI', 'BNE', 'BPL', 'BVC', 'BVS',
    'JMP', 'JSR', 'BRK',
})


def _decode_tokens(data: bytes, base_address: int):
    memory = bytearray(65536)
    if not 0 <= base_address <= 0xFFFF or base_address + len(data) > 65536:
        raise ReductionError('block does not fit in the 16-bit address space')
    memory[base_address:base_address + len(data)] = data
    instructions = []
    offset = 0
    while offset < len(data):
        try:
            instruction = decode_at(bytes(memory), base_address + offset)
        except Exception as exc:
            raise ReductionError(str(exc)) from exc
        if offset + instruction.length > len(data):
            raise ReductionError(f'truncated instruction at block offset {offset}')
        instructions.append(instruction)
        offset += instruction.length
    if not instructions:
        raise ReductionError('block must not be empty')
    for index, instruction in enumerate(instructions):
        if instruction.mnemonic in _FORBIDDEN_CONTROL:
            raise ReductionError(
                f'{instruction.mnemonic} at ${instruction.pc:04X} is outside straight-line v1'
            )
        if instruction.mnemonic in {'RTS', 'RTI'} and index != len(instructions) - 1:
            raise ReductionError(f'interior {instruction.mnemonic} at ${instruction.pc:04X}')
    return tuple(instructions)


def _tokenize(data: bytes, base_address: int):
    instructions = _decode_tokens(data, base_address)
    return [
        _Token(instruction.data, instruction.pc - base_address,
               instruction.pc - base_address + instruction.length)
        for instruction in instructions
    ]


def _cycles(data: bytes, base_address: int):
    return sum(cpucycles_table[item.opcode] for item in _decode_tokens(data, base_address))


def _analysis(tokens, base_address, config):
    data = b''.join(token.data for token in tokens)
    instructions = _decode_tokens(data, base_address)
    liveness = analyze_liveness(instructions, (), terminal_live=config.terminal_live)
    known = analyze_known_state(
        instructions, (), entries={base_address: dict(config.entry_facts)}
    )
    return instructions, liveness, known


def _nz(value):
    return (value >> 7) & 1, int(value == 0)


def _entry(rule, selected, replacement, cycle_delta, proof):
    original = b''.join(token.data for token in selected)
    return ReductionLedgerEntry(
        rule=rule,
        original_start=min(token.original_start for token in selected),
        original_end=max(token.original_end for token in selected),
        original_bytes=original,
        replacement_bytes=replacement,
        byte_delta=len(replacement) - len(original),
        cycle_delta=cycle_delta,
        proof=proof,
    )


def _replace(tokens, index, count, replacement):
    selected = tokens[index:index + count]
    if replacement:
        token = _Token(
            bytes(replacement),
            min(item.original_start for item in selected),
            max(item.original_end for item in selected),
        )
        tokens[index:index + count] = [token]
    else:
        del tokens[index:index + count]


def reduce_straight_block(data: bytes, *, base_address=0x8000,
                          config=ReductionConfig()):
    """Reduce one asserted straight-line block and return an exact ledger.

    The caller remains responsible for relocation/reference repair around the
    now-shorter block and for proving that the supplied liveness/facts describe
    every intended entry context.
    """
    data = bytes(data)
    if not config.assert_no_interior_entries:
        raise ReductionError('caller must assert that the block has no interior entries')
    if not config.assert_no_code_as_data:
        raise ReductionError('caller must assert that the block is not read or written as data')
    if config.timing_policy == 'cycle-exact':
        raise ReductionError('cycle-exact policy forbids automatic reduction')
    tokens = _tokenize(data, base_address)
    warnings = []
    if any(OPS[token.data[0]][0] == 'NOP' for token in tokens):
        warnings.append('NOP preserved: it may be intentional cycle padding')
    ledger = []

    while True:
        instructions, liveness, known = _analysis(tokens, base_address, config)
        changed = False
        for index, instruction in enumerate(instructions):
            facts = known.facts_in(instruction.pc)
            token = tokens[index]

            if 'zero-page-operand-narrowing' in config.enabled_rules:
                narrow_mode = _ZERO_PAGE_MODE.get(instruction.mode)
                narrow_opcode = _OPCODE_BY_NAME_MODE.get((instruction.mnemonic, narrow_mode))
                index_register = {'abx': 'X', 'aby': 'Y'}.get(instruction.mode)
                index_safe = (index_register is None or
                              (index_register in facts and
                               instruction.operand + facts[index_register] <= 0xFF))
                if (narrow_opcode is not None and instruction.operand is not None
                        and instruction.operand <= 0xFF and index_safe):
                    replacement = bytes((narrow_opcode, instruction.operand))
                    cycle_delta = (cpucycles_table[narrow_opcode]
                                   - cpucycles_table[instruction.opcode])
                    index_proof = ('' if index_register is None else
                                   f'; known {index_register}={facts[index_register]} proves no zero-page wrap')
                    item = _entry(
                        'zero-page-operand-narrowing', [token], replacement,
                        cycle_delta,
                        f'absolute operand ${instruction.operand:04X} is in zero page{index_proof}',
                    )
                    _replace(tokens, index, 1, replacement); ledger.append(item)
                    changed = True; break

            if 'known-state-redundancy' in config.enabled_rules:
                setter = _FLAG_SETTERS.get(instruction.mnemonic)
                if setter and facts.get(setter[0]) == setter[1]:
                    item = _entry(
                        'known-state-redundancy', [token], b'',
                        -cpucycles_table[instruction.opcode],
                        f'incoming {setter[0]} is already {setter[1]}',
                    )
                    _replace(tokens, index, 1, b''); ledger.append(item)
                    changed = True; break
                if instruction.mnemonic in {'LDA', 'LDX', 'LDY'} and instruction.mode == 'imm':
                    register = instruction.mnemonic[-1]
                    n, z = _nz(instruction.operand)
                    if (facts.get(register) == instruction.operand
                            and facts.get('F:N') == n and facts.get('F:Z') == z):
                        item = _entry(
                            'known-state-redundancy', [token], b'',
                            -cpucycles_table[instruction.opcode],
                            f'incoming {register}, N, and Z already match the immediate load result',
                        )
                        _replace(tokens, index, 1, b''); ledger.append(item)
                        changed = True; break

            if index + 1 >= len(instructions):
                continue
            following = instructions[index + 1]
            following_token = tokens[index + 1]

            carry_adjust = _CARRY_ADJUSTMENT.get(
                (instruction.mnemonic, following.mnemonic)
            )
            if ('known-carry-immediate-adjustment' in config.enabled_rules
                    and carry_adjust is not None and following.mode == 'imm'
                    and facts.get('F:C') == carry_adjust
                    and facts.get('F:D') == 0
                    and following.operand not in {0x00, 0x80}):
                replacement = bytes((following.opcode, (following.operand - 1) & 0xFF))
                old_cycles = (cpucycles_table[instruction.opcode]
                              + cpucycles_table[following.opcode])
                item = _entry(
                    'known-carry-immediate-adjustment',
                    [token, following_token], replacement,
                    cpucycles_table[following.opcode] - old_cycles,
                    f'incoming C={carry_adjust}, D=0; adjusted immediate preserves A/N/V/Z/C exactly',
                )
                _replace(tokens, index, 2, replacement); ledger.append(item)
                changed = True; break

            if ('duplicate-flag-setter' in config.enabled_rules
                    and instruction.mnemonic == following.mnemonic
                    and instruction.mnemonic in _FLAG_SETTERS):
                item = _entry(
                    'duplicate-flag-setter', [following_token], b'',
                    -cpucycles_table[following.opcode],
                    f'preceding {instruction.mnemonic} already establishes the same flag value',
                )
                _replace(tokens, index + 1, 1, b''); ledger.append(item)
                changed = True; break

            if ('transfer-roundtrip' in config.enabled_rules
                    and (instruction.mnemonic, following.mnemonic) in _ROUNDTRIPS):
                item = _entry(
                    'transfer-roundtrip', [token, following_token], token.data,
                    -cpucycles_table[following.opcode],
                    'the second transfer copies back the value and N/Z already established by the first',
                )
                _replace(tokens, index, 2, token.data); ledger.append(item)
                changed = True; break

            fusion = _FUSIONS.get((instruction.mnemonic, following.mnemonic, instruction.mode))
            if ('dead-source-load-transfer-fusion' in config.enabled_rules and fusion):
                opcode, dead_source = fusion
                if dead_source not in liveness.live_out[following.pc]:
                    replacement = bytes((opcode,)) + instruction.data[1:]
                    old_cycles = (cpucycles_table[instruction.opcode]
                                  + cpucycles_table[following.opcode])
                    new_cycles = cpucycles_table[opcode]
                    item = _entry(
                        'dead-source-load-transfer-fusion',
                        [token, following_token], replacement,
                        new_cycles - old_cycles,
                        f'{dead_source} is dead after the transfer; fused load preserves address, value, and final N/Z',
                    )
                    _replace(tokens, index, 2, replacement); ledger.append(item)
                    changed = True; break
        if not changed:
            break

    reduced = b''.join(token.data for token in tokens)
    original_cycles = _cycles(data, base_address)
    reduced_cycles = _cycles(reduced, base_address)
    if sum(item.byte_delta for item in ledger) != len(reduced) - len(data):
        raise AssertionError('byte ledger does not balance')
    if sum(item.cycle_delta for item in ledger) != reduced_cycles - original_cycles:
        raise AssertionError('cycle ledger does not balance')
    if config.timing_policy == 'interrupt' and reduced_cycles > original_cycles:
        raise ReductionError('interrupt policy forbids a cycle-increasing result')
    return ReductionResult(
        data, reduced, base_address, original_cycles, reduced_cycles,
        tuple(ledger), tuple(warnings), config.timing_policy,
    )
