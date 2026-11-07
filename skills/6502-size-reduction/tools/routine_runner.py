#!/usr/bin/env python3
"""Bounded, hardware-free execution of one 6502 routine.

This module is deliberately concerned with execution evidence, not equivalence
policy. A later differential verifier can compare two immutable RunResult
objects according to an analyst-supplied observation contract.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from cpu6502 import Cpu6502Emulator

MEMORY_SIZE = 0x10000


class RoutineConfigurationError(ValueError):
    """The supplied initial state or execution specification is invalid."""


class Termination(str, Enum):
    """Why bounded routine execution stopped."""

    EXIT_PC = "exit_pc"
    CPU_STOP = "cpu_stop"
    INSTRUCTION_LIMIT = "instruction_limit"
    EXCEPTION = "exception"


@dataclass(frozen=True)
class InitialState:
    """Complete deterministic CPU and RAM state at routine entry."""

    memory: bytes
    a: int = 0
    x: int = 0
    y: int = 0
    sp: int = 0xFF
    flags: int = 0x20

    def __post_init__(self):
        if len(self.memory) != MEMORY_SIZE:
            raise RoutineConfigurationError(
                f"initial memory must contain exactly {MEMORY_SIZE} bytes"
            )
        for name in ("a", "x", "y", "sp", "flags"):
            value = getattr(self, name)
            if not 0 <= value <= 0xFF:
                raise RoutineConfigurationError(f"{name} must be a byte, got {value}")


@dataclass(frozen=True)
class RoutineSpec:
    """Control boundary for one bounded execution.

    An exit PC is recognized before executing the instruction at that address.
    CPU_STOP covers BRK and, when enabled, an empty-stack RTS/RTI.
    """

    start_pc: int
    exit_pcs: frozenset[int]
    max_instructions: int = 100_000
    exit_on_empty_stack: bool = False
    observed_pcs: frozenset[int] = frozenset()

    def __post_init__(self):
        object.__setattr__(self, "exit_pcs", frozenset(self.exit_pcs))
        object.__setattr__(self, "observed_pcs", frozenset(self.observed_pcs))
        if not 0 <= self.start_pc <= 0xFFFF:
            raise RoutineConfigurationError("start_pc must be a 16-bit address")
        if not self.exit_pcs:
            raise RoutineConfigurationError("at least one explicit exit PC is required")
        if any(not 0 <= address <= 0xFFFF for address in self.exit_pcs):
            raise RoutineConfigurationError("all exit PCs must be 16-bit addresses")
        if self.max_instructions <= 0:
            raise RoutineConfigurationError("max_instructions must be positive")
        if any(not 0 <= address <= 0xFFFF for address in self.observed_pcs):
            raise RoutineConfigurationError("all observed PCs must be 16-bit addresses")


@dataclass(frozen=True)
class EntryEvent:
    """CPU state observed on entry to one explicitly watched PC."""

    pc: int
    a: int
    x: int
    y: int
    sp: int
    flags: int
    instructions: int
    cycles: int


@dataclass(frozen=True)
class CpuSnapshot:
    """Immutable complete CPU and RAM state at termination."""

    memory: bytes
    pc: int
    a: int
    x: int
    y: int
    sp: int
    flags: int
    cycles: int
    last_instruction: int | None


@dataclass(frozen=True)
class AccessEvidence:
    """Memory effects observed after initialization was cleared from tracking."""

    read_addresses: frozenset[int]
    written_addresses: frozenset[int]
    write_trace: tuple[tuple[int, int, int], ...]


@dataclass(frozen=True)
class RunResult:
    """Bounded execution result suitable for later differential comparison."""

    termination: Termination
    instructions: int
    final: CpuSnapshot
    access: AccessEvidence
    entry_events: tuple[EntryEvent, ...] = ()
    exception_type: str | None = None
    exception_message: str | None = None

    @property
    def reached_legal_exit(self):
        return self.termination is Termination.EXIT_PC


def build_memory(segments: Iterable[tuple[int, bytes]] = ()) -> bytes:
    """Create a zero-filled 64 KiB image populated by non-overlapping segments."""
    memory = bytearray(MEMORY_SIZE)
    occupied = bytearray(MEMORY_SIZE)
    for address, data in segments:
        payload = bytes(data)
        if not 0 <= address < MEMORY_SIZE:
            raise RoutineConfigurationError(f"segment address {address} is out of range")
        end = address + len(payload)
        if end > MEMORY_SIZE:
            raise RoutineConfigurationError(
                f"segment at ${address:04X} extends beyond 64 KiB"
            )
        if any(occupied[address:end]):
            raise RoutineConfigurationError(
                f"segment at ${address:04X} overlaps an earlier segment"
            )
        memory[address:end] = payload
        occupied[address:end] = b"\x01" * len(payload)
    return bytes(memory)


def _snapshot(cpu: Cpu6502Emulator) -> CpuSnapshot:
    return CpuSnapshot(
        memory=bytes(cpu.memory),
        pc=cpu.pc,
        a=cpu.a,
        x=cpu.x,
        y=cpu.y,
        sp=cpu.sp,
        flags=cpu.flags,
        cycles=cpu.cpucycles,
        last_instruction=cpu.last_instruction,
    )


def _access_evidence(cpu: Cpu6502Emulator) -> AccessEvidence:
    return AccessEvidence(
        read_addresses=frozenset(cpu.read_addresses()),
        written_addresses=frozenset(cpu.written_addresses()),
        write_trace=tuple(cpu.write_trace),
    )


def run_routine_on_cpu(spec: RoutineSpec, initial: InitialState,
                       cpu: Cpu6502Emulator) -> RunResult:
    """Execute with a supplied compatible CPU/memory implementation."""
    cpu.memory[:] = initial.memory
    cpu.init_cpu(
        spec.start_pc,
        newa=initial.a,
        newx=initial.x,
        newy=initial.y,
        flags=initial.flags,
    )
    cpu.sp = initial.sp
    cpu.exit_on_empty_stack = spec.exit_on_empty_stack
    cpu.clear_memory_usage()

    instructions = 0
    termination = None
    exception_type = None
    exception_message = None
    entry_events = []

    while termination is None:
        if cpu.pc in spec.exit_pcs:
            if cpu.pc in spec.observed_pcs:
                entry_events.append(EntryEvent(
                    cpu.pc, cpu.a, cpu.x, cpu.y, cpu.sp, cpu.flags,
                    instructions, cpu.cpucycles,
                ))
            termination = Termination.EXIT_PC
            break
        if instructions >= spec.max_instructions:
            termination = Termination.INSTRUCTION_LIMIT
            break
        if cpu.pc in spec.observed_pcs:
            entry_events.append(EntryEvent(
                cpu.pc, cpu.a, cpu.x, cpu.y, cpu.sp, cpu.flags,
                instructions, cpu.cpucycles,
            ))

        try:
            running = cpu.runcpu()
            instructions += 1
            if not running:
                termination = Termination.CPU_STOP
        except Exception as exc:  # Preserve bounded evidence for malformed code.
            termination = Termination.EXCEPTION
            exception_type = type(exc).__name__
            exception_message = str(exc)

    return RunResult(
        termination=termination,
        instructions=instructions,
        final=_snapshot(cpu),
        access=_access_evidence(cpu),
        entry_events=tuple(entry_events),
        exception_type=exception_type,
        exception_message=exception_message,
    )


def run_routine(spec: RoutineSpec, initial: InitialState) -> RunResult:
    """Execute one routine on flat RAM until a bounded stop condition.

    Initialization is copied directly into RAM and then access tracking is
    cleared. Consequently evidence contains execution accesses only, including
    opcode/operand fetches and stack accesses.
    """
    return run_routine_on_cpu(spec, initial, Cpu6502Emulator())
