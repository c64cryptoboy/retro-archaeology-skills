# Regional implementation-evidence pilot

This pilot makes a supplied stream interpretation inspectable without turning matching bytes into compiler or authorship claims.  It answers one question: **are the selected stream boundaries consistent with the supplied, byte-pinned consumer contract?**

This is a bounded helper within the disassembly skill, not an authorship classifier, new skill, or plugin framework.  It uses Python's standard library and two unchanged public helpers.  No target bytes are executed.

## Files

- `region_evidence.py`: bounded checker and JSON CLI.
- `WORKSHEET.md`: evidence contract and interpretation rules.
- `synthetic_fixture.py`, `synthetic-consumers.asm`: reproducible synthetic bytes and annotated consumer correspondence; neither assembly nor target execution is performed.
- `examples/`: three complete input/worksheet/report pairs, including identical address cells with different consumers.
- `tests/`: synthetic boundary, schema, import-provenance, and refusal controls.

## Run

From this directory, point `--public-root` at a trusted copy of the public toolkit containing `skills/pcode-disassembly/scripts/` and `shared/6502/`.  There are no private-corpus or private-identifier dependencies.  Keep the complete public p-code scripts tree: known identities can lazily load family decoders and profiles, even though the synthetic unknown examples do not need them.  Imports fail closed if another toolkit root's dependencies are already cached; use a fresh Python process for another root.

```sh
python3 -B region_evidence.py examples/vm.bin examples/vm.json --public-root ../../../..
PUBLIC_TOOLKIT_ROOT=../../../.. python3 -B -m unittest discover -s tests -v
```

JSON goes to stdout.  Optional `--output new-report.json` creates a new file exclusively; an existing output, including an input alias, is not overwritten.  `python3 -B synthetic_fixture.py new-examples` creates fresh synthetic fixtures, refusing existing fixture filenames.  No package installation is needed.

Successful report creation exits 0, including a report whose boundary result is `unknown`, `partial`, or `refused`.  Exit 2 means invalid input/schema, a mismatched input identity, or an I/O failure.  Consumers must inspect the JSON result, not treat exit 0 as classification acceptance.

## Evidence separation

| Field | Meaning |
|---|---|
| `componentIdentity.publicBaseline` | Existing public exact-region identifier output, with signature confidence wording omitted.  Exact matches and `layoutValid` remain separate. |
| `componentIdentity.suppliedPins` | Exact bytes match a manually supplied digest.  A supplied component label is not authenticated. |
| `mechanism.stream` | Fixed-width record and edge checks under the supplied consumer contract.  Records include bytes, bounds, successor addresses, and supplied rule references. |
| `mechanism.representationCandidate` | Conditional VM/threaded-cell candidate only if the whole selected region is boundary-consistent.  Otherwise `unknown`. |
| `mechanism.actualReachability` | Always `unknown`; neither a static CFG nor a manual assertion is promoted to observed execution. |
| `generationEvidence` | Always `none-established` in this pilot.  Calls, templates, and runtime inclusion do not establish application generation. |
| `historicalAuthorship` | Always `unresolved`.  No handwritten default or percentage confidence. |

The public CFG is included only when native entries are supplied.  It follows possible official-6502 paths, caps at 512 instructions, and preserves unresolved-indirect stops and its limit indicator.  It does **not** verify the consumer contract or recover threaded handlers automatically.

## Boundary checks and stopping rule

The checker follows a worklist from supplied stream entries, never a blind whole-image linear sweep.  Supported records have a one- or two-byte little-endian token, zero through 16 operand bytes, and `next`, `stop`, absolute-16-bit `jump`, or `branch` flow.  Targets are stream addresses, not handler addresses.  Unknown tokens, truncated records, overlapping interpretations, operand-entry targets, and out-of-region edges refuse the interpretation.  Unvisited bytes remain explicit unknown ranges.

A structurally consistent loop need not terminate.  Hash pins prove byte agreement, not the truth of the source description.  A deliberately false dispatch assertion can pass boundary checks; a dedicated test preserves this trust boundary.  Review the supplied evidence rather than interpreting `consistent` as verified semantics.

## Demonstrated results

- VM example: `$1040-$1046` end-exclusive, three records, six covered bytes, conditional `vm-opcodes` candidate.
- Generic address-cell example: `$1040-$1044`, two records, four covered bytes, conditional `threaded-cells` candidate.
- Ordinary pointer-data reader: **the same four region bytes**, but no stream interpretation because its supplied consumer performs data reads, not dispatch.
- All three public exact-identifier results: `unknown`, correctly not converted into handwritten results.

Only synthetic examples were evaluated.  No real-program validation, native producer convention, held-out accuracy, compiler execution, emulator session, or Forth implementation is included.  Forth recognition is not supported by this helper.  Packed, banked, relocated, self-modifying, variable-length, overlapping code/data, and external-consumer cases are outside this pilot's admission contract.  Stop at unknown rather than extending this into a prerequisite campaign.
