# Consumer evidence worksheet

Recording the consumer and its uncertainty separately from matching bytes prevents a convenient layout from becoming an unsupported origin claim.  Use `examples/vm.json` as the executable JSON template, and keep the questions below with the analysis.

## Analyst checklist

1. **Identity and mapping:** SHA-256 the complete input.  Declare PRG or raw, the raw base if applicable, the official-6502 subset, and the mapping/phase assumption.  Do not infer bank state from a load address.
2. **One question:** select `[start,end)` and supplied stream entry addresses.  Explain why these bounds and entries are appropriate.  Bytes outside the selected region are outside the boundary question, not automatically code or data.
3. **Consumer:** record the consumer's `[start,end)` and digest, the fetch/cursor/dispatch explanation, and its source or observed evidence.  The consumer must be present in this image and disjoint from the stream for this pilot.
4. **Rules:** document each token's fixed operand width and successor rule.  Cite the consumer operation establishing those facts.  Mere pointer plausibility, repeated calls, or a suggestive label is insufficient.
5. **Reachability:** distinguish a known native entry, a static possible path, a manual assertion, and an actual observation.  This pilot preserves supplied reachability references but never authenticates them or executes the target.
6. **Counterevidence:** could these bytes be pointer data, metadata, an unused component, inline call arguments, or an unfamiliar representation?  Preserve that alternative explicitly in the analyst notes.
7. **Origin:** is there independently authenticated generation/build history?  This pilot does not accept or verify an authorship label.  Document such work separately.

All evidence descriptions in JSON are **supplied, not automatically proved**.  A source path in a description is not opened, executed, or authenticated.  The tool verifies input/pin bytes and boundary constraints, not prose truth.

## JSON fields

| Field | Contract |
|---|---|
| `schema` | Exactly `regional-consumer-worksheet-v1`. |
| `input.sha256` | Digest of the entire file, including the PRG header if present.  A mismatch is an input error. |
| `input.format` | `raw` or `prg`. |
| `input.base` | Required integer for raw; PRG base comes from its two-byte header. |
| `input.cpu` | Exactly `6502`, meaning the official opcode subset for static CFG support. |
| `input.mappingEvidence` | Nonempty supplied explanation of the flat address mapping/phase. |
| `region.start`, `region.end` | Integer CPU addresses, end-exclusive, wholly within the loaded payload. |
| `region.entries` | Nonempty list of supplied stream entries for a dispatch check.  These are not native CPU entries. |
| `region.evidence`, `region.roleEvidence` | Nonempty supplied justification of bounds and role. |
| `componentPins` | Optional list of `{start,end,sha256,label,evidence}` for exact comparison with supplied component claims.  These do not extend the public signature database. |
| `consumer` | `null` or absent means unknown.  Otherwise see below. |

### Consumer object

- `start`, `end`, `sha256`: exact consumer-byte pin.  A missing/mismatched extent yields unknown, not a forced decode.
- `operation`: only `dispatch` admits stream checks.  Descriptions such as `data-read` or `native-calls` cause abstention.
- `representation`: `vm-opcodes` or `threaded-cells` for admitted dispatch contracts.  These are supplied hypotheses, not inferred language families.
- `evidence`: nonempty supplied fetch/advance/dispatch justification.
- `reachabilityEvidence`: optional supplied reference; remains labeled supplied.
- `nativeEntries`: optional native CPU entry addresses for the unchanged public CFG, not automatically identified entry points.  Its graph is separate evidence, not an acceptance gate or proof of dynamic reachability.
- `contract.tokenBytes`: 1 or 2; `contract.byteOrder`: `little`.
- `contract.rules`: unique integer `token`, integer `operandBytes` from 0 through 16, `flow`, and nonempty supplied `evidence` per rule.
- `flow`: `next`, `stop`, `jump`, or `branch`.  Jump/branch rules require `targetOffset`, a zero-based operand offset containing the two-byte little-endian absolute **stream** target.  Branch also follows fallthrough; stop has none.

No commands, Python expressions, plugin paths, or private identity files are accepted in the worksheet.  `--public-root` names trusted Python helper code supplied by the operator, not by an untrusted worksheet.

## Interpretation worksheet

Fill this for a reviewed result:

```text
Input digest / phase:
Selected range / supplied entries:
Exact component matches, independently from layout validity:
Consumer byte pin / source or observation:
Supplied assumptions not authenticated by this run:
Boundary result / records / refused targets:
Unknown ranges / alternatives / counterevidence:
Possible native CFG paths and unresolved stops:
Actual execution evidence (not established by this tool):
Generation evidence (not established by this tool):
Historical authorship (unresolved by this tool):
Stop or next separately authorized question:
```

The supplied synthetic consumer source includes a byte-fetch VM, a generic two-byte address-cell dispatcher, and an ordinary pointer-data reader.  They demonstrate the narrow distinction under review, not a language implementation or producer classifier.
