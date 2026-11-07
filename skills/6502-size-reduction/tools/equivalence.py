#!/usr/bin/env python3
"""Contract-driven differential equivalence for bounded 6502 routine runs."""

from dataclasses import dataclass
from enum import Enum

from routine_runner import RunResult, Termination


class EquivalenceConfigurationError(ValueError):
    """An observation contract is ambiguous or invalid."""


class MemoryPolicy(str, Enum):
    """How writes and final values in corresponding memory ranges are observed."""

    FINAL_STATE = "final_state"
    ORDERED_EVENTS = "ordered_events"
    IGNORED = "ignored"


@dataclass(frozen=True)
class MemoryRule:
    """Map equal-length left/right address ranges to one observation policy.

    Ranges are half-open: `[start, start + length)`. ORDERED_EVENTS compares the
    ordered `(relative offset, new value)` stream. FINAL_STATE compares only the
    completed bytes. IGNORED permits arbitrary final values and writes.
    """

    name: str
    left_start: int
    right_start: int
    length: int
    policy: MemoryPolicy

    def __post_init__(self):
        if not self.name:
            raise EquivalenceConfigurationError("memory rule name must not be empty")
        if self.length <= 0:
            raise EquivalenceConfigurationError(f"memory rule {self.name!r} has non-positive length")
        for side, start in (("left", self.left_start), ("right", self.right_start)):
            if not 0 <= start <= 0xFFFF:
                raise EquivalenceConfigurationError(
                    f"{side} start for memory rule {self.name!r} is out of range"
                )
            if start + self.length > 0x10000:
                raise EquivalenceConfigurationError(
                    f"{side} range for memory rule {self.name!r} extends beyond 64 KiB"
                )
        if not isinstance(self.policy, MemoryPolicy):
            try:
                object.__setattr__(self, "policy", MemoryPolicy(self.policy))
            except ValueError as exc:
                raise EquivalenceConfigurationError(
                    f"unknown policy for memory rule {self.name!r}: {self.policy!r}"
                ) from exc

    def contains_left(self, address):
        return self.left_start <= address < self.left_start + self.length

    def contains_right(self, address):
        return self.right_start <= address < self.right_start + self.length


@dataclass(frozen=True)
class EntryEventRule:
    """Compare ordered CPU-state events on entry to corresponding PCs."""

    name: str
    left_pc: int
    right_pc: int
    registers: frozenset[str] = frozenset(("a", "x", "y", "sp"))
    flags_mask: int = 0xFF

    def __post_init__(self):
        if not self.name:
            raise EquivalenceConfigurationError("entry-event rule name must not be empty")
        if not 0 <= self.left_pc <= 0xFFFF or not 0 <= self.right_pc <= 0xFFFF:
            raise EquivalenceConfigurationError(
                f"entry-event PCs for {self.name!r} must be 16-bit"
            )
        object.__setattr__(self, "registers", frozenset(self.registers))
        unknown = self.registers - {"a", "x", "y", "sp"}
        if unknown:
            raise EquivalenceConfigurationError(
                f"unknown entry-event registers for {self.name!r}: {sorted(unknown)}"
            )
        if not 0 <= self.flags_mask <= 0xFF:
            raise EquivalenceConfigurationError(
                f"entry-event flags mask for {self.name!r} must be a byte"
            )


@dataclass(frozen=True)
class ObservationContract:
    """Authoritative definition of what two routine executions must preserve."""

    registers: frozenset[str] = frozenset(("a", "x", "y", "sp"))
    flags_mask: int = 0xFF
    exit_pairs: frozenset[tuple[int, int]] = frozenset()
    memory_rules: tuple[MemoryRule, ...] = ()
    entry_event_rules: tuple[EntryEventRule, ...] = ()
    reject_unspecified_writes: bool = True
    max_differences: int = 100

    def __post_init__(self):
        object.__setattr__(self, "registers", frozenset(self.registers))
        object.__setattr__(self, "exit_pairs", frozenset(self.exit_pairs))
        object.__setattr__(self, "memory_rules", tuple(self.memory_rules))
        object.__setattr__(self, "entry_event_rules", tuple(self.entry_event_rules))

        unknown = self.registers - {"a", "x", "y", "sp"}
        if unknown:
            raise EquivalenceConfigurationError(f"unknown observed registers: {sorted(unknown)}")
        if not 0 <= self.flags_mask <= 0xFF:
            raise EquivalenceConfigurationError("flags_mask must be a byte")
        if not self.exit_pairs:
            raise EquivalenceConfigurationError("at least one equivalent exit pair is required")
        for left, right in self.exit_pairs:
            if not 0 <= left <= 0xFFFF or not 0 <= right <= 0xFFFF:
                raise EquivalenceConfigurationError("exit-pair addresses must be 16-bit")
        if self.max_differences <= 0:
            raise EquivalenceConfigurationError("max_differences must be positive")

        names = [rule.name for rule in self.entry_event_rules]
        if len(set(names)) != len(names):
            raise EquivalenceConfigurationError(
                "entry-event rule names must be unique"
            )
        self._validate_non_overlapping_rules("left")
        self._validate_non_overlapping_rules("right")

    def _validate_non_overlapping_rules(self, side):
        ranges = []
        for rule in self.memory_rules:
            start = rule.left_start if side == "left" else rule.right_start
            ranges.append((start, start + rule.length, rule.name))
        ranges.sort()
        for previous, current in zip(ranges, ranges[1:]):
            if current[0] < previous[1]:
                raise EquivalenceConfigurationError(
                    f"{side} memory rules {previous[2]!r} and {current[2]!r} overlap"
                )


@dataclass(frozen=True)
class Difference:
    """One inspectable reason two bounded executions are not equivalent."""

    category: str
    message: str
    rule: str | None = None
    left: object = None
    right: object = None


@dataclass(frozen=True)
class ComparisonResult:
    equivalent: bool
    differences: tuple[Difference, ...]
    truncated: bool


class _DifferenceCollector:
    def __init__(self, limit):
        self.limit = limit
        self.items = []
        self.truncated = False

    def add(self, difference):
        if len(self.items) < self.limit:
            self.items.append(difference)
        else:
            self.truncated = True


def _relative_write_events(result, start, length):
    end = start + length
    return tuple(
        (address - start, new_value)
        for address, _old_value, new_value in result.access.write_trace
        if start <= address < end
    )


def _entry_event_stream(result, rule, side):
    pc = rule.left_pc if side == "left" else rule.right_pc
    return tuple(
        tuple(getattr(event, register) for register in sorted(rule.registers))
        + ((event.flags & rule.flags_mask,) if rule.flags_mask else ())
        for event in result.entry_events
        if event.pc == pc
    )


def _covered_write_addresses(result, rules, side):
    covered = set()
    for rule in rules:
        start = rule.left_start if side == "left" else rule.right_start
        end = start + rule.length
        covered.update(address for address in result.access.written_addresses if start <= address < end)
    return covered


def compare_runs(left: RunResult, right: RunResult,
                 contract: ObservationContract) -> ComparisonResult:
    """Compare two run results using only observations declared by `contract`."""
    differences = _DifferenceCollector(contract.max_differences)

    if left.termination is not Termination.EXIT_PC:
        differences.add(Difference(
            "left_termination",
            "left execution did not reach a legal exit",
            left=(left.termination.value, left.exception_type, left.exception_message),
        ))
    if right.termination is not Termination.EXIT_PC:
        differences.add(Difference(
            "right_termination",
            "right execution did not reach a legal exit",
            right=(right.termination.value, right.exception_type, right.exception_message),
        ))
    if (left.final.pc, right.final.pc) not in contract.exit_pairs:
        differences.add(Difference(
            "exit",
            "final PCs are not an allowed equivalent exit pair",
            left=left.final.pc,
            right=right.final.pc,
        ))

    for register in sorted(contract.registers):
        left_value = getattr(left.final, register)
        right_value = getattr(right.final, register)
        if left_value != right_value:
            differences.add(Difference(
                "register",
                f"register {register.upper()} differs",
                left=left_value,
                right=right_value,
            ))

    left_flags = left.final.flags & contract.flags_mask
    right_flags = right.final.flags & contract.flags_mask
    if left_flags != right_flags:
        differences.add(Difference(
            "flags",
            f"observed flags differ under mask ${contract.flags_mask:02X}",
            left=left_flags,
            right=right_flags,
        ))

    for rule in contract.entry_event_rules:
        left_events = _entry_event_stream(left, rule, "left")
        right_events = _entry_event_stream(right, rule, "right")
        if left_events != right_events:
            differences.add(Difference(
                "entry_events",
                "ordered entry-event CPU states differ",
                rule=rule.name,
                left=left_events,
                right=right_events,
            ))

    for rule in contract.memory_rules:
        left_start = rule.left_start
        right_start = rule.right_start
        if rule.policy is MemoryPolicy.FINAL_STATE:
            for offset in range(rule.length):
                left_value = left.final.memory[left_start + offset]
                right_value = right.final.memory[right_start + offset]
                if left_value != right_value:
                    differences.add(Difference(
                        "memory_final",
                        f"final byte differs at relative offset ${offset:04X}",
                        rule=rule.name,
                        left=left_value,
                        right=right_value,
                    ))
        elif rule.policy is MemoryPolicy.ORDERED_EVENTS:
            left_events = _relative_write_events(left, left_start, rule.length)
            right_events = _relative_write_events(right, right_start, rule.length)
            if left_events != right_events:
                differences.add(Difference(
                    "memory_ordered_events",
                    "ordered write events differ",
                    rule=rule.name,
                    left=left_events,
                    right=right_events,
                ))
        elif rule.policy is MemoryPolicy.IGNORED:
            pass
        else:  # Defensive if an Enum grows without comparator support.
            raise EquivalenceConfigurationError(f"unsupported memory policy {rule.policy}")

    if contract.reject_unspecified_writes:
        left_covered = _covered_write_addresses(left, contract.memory_rules, "left")
        right_covered = _covered_write_addresses(right, contract.memory_rules, "right")
        left_unexpected = sorted(left.access.written_addresses - left_covered)
        right_unexpected = sorted(right.access.written_addresses - right_covered)
        if left_unexpected:
            differences.add(Difference(
                "left_unspecified_writes",
                "left execution wrote outside all declared memory rules",
                left=tuple(left_unexpected),
            ))
        if right_unexpected:
            differences.add(Difference(
                "right_unspecified_writes",
                "right execution wrote outside all declared memory rules",
                right=tuple(right_unexpected),
            ))

    return ComparisonResult(
        equivalent=not differences.items and not differences.truncated,
        differences=tuple(differences.items),
        truncated=differences.truncated,
    )
