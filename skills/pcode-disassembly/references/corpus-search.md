# Corpus searches: storage coverage before compiler conclusions

A scan of directory-extracted PRGs is one coverage layer, not a scan of every program on every disk.  **A corpus search must consider different file systems, directory/boot arrangements, and supported physical encodings.**  A directory failure or an unrecognized binary does not establish that compiled BASIC is absent.  Complete file recovery is not required to identify an evidenced compiler component.

## Inventory three independent layers

| Layer | Record separately |
|---|---|
| Container | PRG, D64, G64, or another supplied representation; archive member, image hash, side, and edition |
| File system / loader layout | Ordinary Commodore DOS files; missing, damaged, or looping directories; nonstandard BAM/boot sectors; fixed-sector loaders; unlinked sectors; incomplete chains; multi-stage programs and external runtimes |
| Physical encoding | Standard Commodore GCR, or the exact supported custom-record profile; distinguish a decoded profile from a filename's claimed protection/version |

G64 is a container, not an encoding.  Nonstandard storage can still use standard GCR.  Distinct sides, dumps, and releases may differ; filename labels are selection hints, not compiler or encoding evidence.  Record unsupported containers, encodings, and layouts as **unsearched or unresolved**, never as negative results.

## Search in explicit coverage passes

1. Preserve original input identities and make a coverage ledger.  Record each reader/profile version, interpretation, success, refusal, and unsupported case.  Do not silently omit images whose directory walk fails.
2. Identify normally extracted files with the [binary identification tools](reconstruction-tools.md).  Preserve their exact input bytes, load-address evidence, and results.  Keep extraction success separate from compiler recognition and decoder admission.
3. Search storage gaps: independently verified directory prefixes, valid sectors outside successfully extracted chains, failed-chain prefixes, and evidenced loader-selected regions.  Do not discard every sector of a failed file as already searched.  For standard GCR, preserve the full decoded sector while looking for components; strip DOS links only when that particular file-chain interpretation is established.
4. Use available, validated custom-record readers on remaining relevant images.  Consult the disk skill's [reader contracts](../../c64-disk-preservation-cracking/references/g64-readers.md).  Preserve record coordinates, profile, integrity checks, payload hashes, duplicate observations, and conflicting valid replicas.  Do not guess record order, repair checksums, invent missing bytes, or join unrelated fragments.  A narrow title/profile decoder is not general support for its whole protection family.
5. Review partial-content candidates independently.  Packing, encryption, unsupported encodings, and unfamiliar runtime variants remain coverage gaps.  Broader recovery or new reader development is a separately bounded task, not a reason to hide these gaps or postpone every partial identification.

These are agent workflow steps, **not a promise that the bundled identifier walks disk images or implements all these readers**.  The PRG/raw-image CLI still requires a real PRG header or an independently evidenced `--raw-base`.  Do not feed arbitrary sector bytes to it with a fabricated address.  Separately reviewed fragment matching must retain its own scope, controls, and candidate status; it does not weaken existing exact-signature or decoder gates.

## Promote evidence, not search hits

- Require compiler-specific native context: coherent fetch/dispatch, operand handling, initialization, or an exact reviewed bootstrap.  Prefer functionally independent, nonoverlapping witnesses with evidenced relative spacing.  Repeated or overlapping copies of one helper are not independent evidence.
- Check competing families, stock-ROM routines, and ordinary loader/drive helpers.  A common floating-point/string routine, compiler banner, or filename alone is insufficient.  Where applicable, controls should include missing anchors, wrong spacing, truncation, and forbidden cross-record joins.  Known-reference replay is not blind false-positive calibration.
- Separate **runtime bytes on this image** from **a compiled component associated with this title**.  Establish association through a verified named directory prefix, actual stored links, loader references, or another explicit mechanism.  A standalone library is not automatically a compiled game.  If association is missing, report that narrower finding instead of inventing it.
- A bounded associated prefix can suffice; a complete file, runnable reconstruction, or full p-code decode is not an identification prerequisite.  Conversely, identifying a loader, protection check, menu, or utility does not prove compiled gameplay, exact historical compiler attribution, or execution.
- Compare against all previously accepted software, manual findings, and component roles -- not merely the last presentation list or a file-hash cache.  Distinguish a new title, a new component/family for a known title, and new carrier/encoding evidence for an already known component.

## Report coverage and discoveries precisely

For each finding, record compiler/family, company attribution, title/edition, year evidence, compiled part, actual encoding/layout, input and payload identities, association evidence, and remaining limits.  Keep archive years, component copyright dates, and verified release dates distinct.  Where a task requests live updates, report independently validated discoveries as they are found; do not present raw candidates as discoveries.

Summarize images examined, successful file extraction, unresolved directories/chains, verified sector/record observations, unsupported cases, accepted findings, and rejected or unresolved candidates.  Distinguish physical observations, per-image distinct payloads, global unique payloads, files, components, and titles.  A zero-match result is bounded by the searched bytes, reader profiles, and runtime references -- it is not a corpus-wide proof of no compiled BASIC.

Keep commercial bytes, private paths, raw traces, and scan chronology outside the distributable skill.  Portable catalogs may retain qualified factual summaries and specimen hashes.  Preserve unchanged algorithms, fixtures, and acceptance gates when adding this methodology.
