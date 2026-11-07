# 6502 code-size reduction effort

Date:
Status: planning

## Capability

- [x] Internal LLM-assisted capability
- [ ] Standalone external product (requires separate decision)

## Objective and identity

Goal:

| Artifact | Path | Size | SHA-256 | Mapping |
|---|---|---:|---|---|
| Original | | | | |

CPU/platform:

Exact size/base/container constraints:

## Timing policy

- [ ] Ordinary
- [ ] Interrupt: every affected path must be no slower
- [ ] Cycle-exact: preserve/refuse automatic rewriting

Unrolled regions to preserve:

NOP/padding/balanced-path/timed-I/O regions:

Interrupt/NMI/DMA/async assumptions:

## Evidence map

### Confirmed

-

### Hypotheses

-

### Unknown/opaque

-

## Candidate ledger

| Candidate/range | Contract/domain | Rule or semantic idea | Bytes delta | Cycle delta/path | Risks | Decision |
|---|---|---|---:|---|---|---|
| | | | | | | |

## Integration

Final placement/repacking:

References requiring repair:

Source-retirement conditions:

Authorized changed ranges:

## Verification

- [ ] Hash/mapping/boundary guards
- [ ] Rule positive and negative evidence
- [ ] Local differential cases
- [ ] Connected final-address execution
- [ ] Whole-image change audit
- [ ] Required emulator/hardware timing checks
- [ ] Cleanup/restoration

## Acceptance

- [ ] Bytes are reduced after complete scaffold/integration costs
- [ ] Timing policy passes on every required path
- [ ] Deliberate unrolling and cycle-exact islands are preserved
- [ ] References/layout/container are valid
- [ ] Semantic/domain contracts pass
- [ ] Final artifact and evidence reproduce from fresh input

## Outputs

Reducer/integration script:

Contracts/tests:

Report:

Artifact:

Reproduction command:
