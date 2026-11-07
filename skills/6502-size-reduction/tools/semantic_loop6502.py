#!/usr/bin/env python3
"""Materialize an explicitly accepted indexed-traversal reversal locally.

The CFG scanner only reports IndexedTraversalReversalOption values. This module
requires a separate semantic contract before producing shorter bytes; it does
not perform whole-image integration or infer that reversed order is harmless.
"""

from __future__ import annotations

from dataclasses import dataclass

from cfg_reduction6502 import (
    CFGScanConfig, IndexedTraversalReversalOption, scan_cfg_candidates,
)


class SemanticLoopError(ValueError):
    pass


@dataclass(frozen=True)
class IndexedTraversalSemanticContract:
    equivalence_kind: str
    assert_same_index_set: bool
    assert_reverse_order_equivalent: bool
    assert_no_alias_or_overlap_dependency: bool
    assert_no_order_sensitive_io: bool
    assert_no_early_exit_or_recurrence: bool
    assert_no_smc_or_asynchronous_observer: bool
    assert_final_index_and_flags_unobserved: bool

    def validate(self):
        if self.equivalence_kind not in {'exact-final-state', 'specification'}:
            raise SemanticLoopError(
                'equivalence_kind must be exact-final-state or specification'
            )
        assertions = {
            name: value for name, value in self.__dict__.items()
            if name.startswith('assert_')
        }
        missing = [name for name, value in assertions.items()
                   if type(value) is not bool or not value]
        if missing:
            raise SemanticLoopError(
                'indexed traversal reversal requires explicit true assertions: '
                + ', '.join(missing)
            )


@dataclass(frozen=True)
class MaterializedIndexedTraversal:
    original: bytes
    compacted: bytes
    base_address: int
    option: IndexedTraversalReversalOption
    contract: IndexedTraversalSemanticContract
    byte_delta: int
    nominal_cycle_delta: int
    changed_order: bool


def materialize_indexed_traversal_reversal(
        data: bytes, *, base_address: int,
        option: IndexedTraversalReversalOption,
        contract: IndexedTraversalSemanticContract,
) -> MaterializedIndexedTraversal:
    """Return local shorter bytes after explicit semantic acceptance."""
    contract.validate()
    data = bytes(data)
    if base_address != option.start:
        raise SemanticLoopError('option start does not match local base address')
    if option.end_exclusive != base_address + len(data):
        raise SemanticLoopError('local region does not exactly match option range')
    if data != option.original_bytes:
        raise SemanticLoopError('local bytes do not match the guarded option')
    if not option.timing_admissible:
        raise SemanticLoopError('option is inadmissible under its timing policy')
    if option.byte_delta >= 0 or len(option.replacement_bytes) >= len(data):
        raise SemanticLoopError('semantic option does not shorten the region')
    if option.strategy not in {
            'one-based-decrement-bne', 'zero-based-decrement-bpl'}:
        raise SemanticLoopError('unsupported indexed traversal strategy')
    if not option.index_use_pcs:
        raise SemanticLoopError('indexed traversal option has no index use')
    canonical = scan_cfg_candidates(
        data, base_address=base_address,
        config=CFGScanConfig(
            entries=(base_address,), terminal_live=frozenset({'SP'}),
            timing_policy='ordinary', cpu_profile='nmos6502',
        ),
    )
    exact = [item for item in canonical.indexed_traversal_reversals
             if item.start == option.start
             and item.end_exclusive == option.end_exclusive
             and item.strategy == option.strategy
             and item.original_bytes == option.original_bytes
             and item.replacement_bytes == option.replacement_bytes
             and item.byte_delta == option.byte_delta
             and item.nominal_cycle_delta == option.nominal_cycle_delta]
    if len(exact) != 1:
        raise SemanticLoopError(
            'option does not match the scanner canonical local rewrite'
        )
    return MaterializedIndexedTraversal(
        data, option.replacement_bytes, base_address, option, contract,
        len(option.replacement_bytes) - len(data),
        option.nominal_cycle_delta, True,
    )
