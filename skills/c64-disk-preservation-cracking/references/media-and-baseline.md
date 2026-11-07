# Media fidelity, baseline and filesystem audit

> Read [SKILL.md](../SKILL.md) first. This is the detailed procedure for the routed phase, not an instruction to expand every task. Commands and inline file paths below are relative to the **skill directory**, unless explicitly stated otherwise; Markdown links resolve from this reference.

## Phase 1 — Establish the preservation source

Before reverse engineering, identify what media/image is being analyzed.

Record:

- original physical disk available: yes/no,
- image format,
- number of sides,
- number of tracks represented,
- error-byte information if present,
- whether half tracks are represented,
- whether raw GCR is represented,
- whether density information is represented,
- whether flux-level capture exists,
- known emulator compatibility.

### Capture ancestry and observation boundary

Record acquisition identity, source disk and side when known, conversion or extraction lineage, and the tool/profile used for each representation.  A G64 and an NBZ with matching filename stems may derive from one capture; separate filenames and hashes do not establish independent acquisitions.  If lineage is unknown, say so.  A second implementation can cross-check a calculation without supplying an independent historical disk observation.

Keep these claims distinct: recovered logical bytes, represented raw geometry, emulator-observed behavior, and physical-drive behavior.  A stored track's bit zero is not automatically a common spindle index across tracks.  Equal logical sectors, identical raw tracks, or a circular rotation match do not by themselves establish physical head position or angular registration.  Conversely, a strict reader's refusal or unrecognized record does not by itself prove that the original disk is bad or that its protection was identified.

### Image format implications

#### D64

D64 represents decoded CBM DOS sectors well, but cannot faithfully represent many physical protection mechanisms.

A normal D64 generally cannot represent:

- half-track content,
- arbitrary tracks beyond its selected geometry,
- raw custom GCR structure,
- exact sync-mark layout,
- long tracks,
- physical weak-bit behavior,
- angular track relationships.

If a protected original has already been reduced to D64, missing protection data may be unrecoverable from that image.

#### G64

G64 stores raw GCR tracks and is usually preferable for protected 1541 disks.

It can represent many cases involving:

- non-standard GCR,
- long tracks,
- unusual sync structures,
- extra tracks,
- half-track positions,
- track-specific density.

It still cannot perfectly represent every physical property of a mastered floppy.

#### NIB

NIB is an older raw-GCR archival representation and may contain protection information absent from D64.

When possible, retain the original NIB and derive G64/D64 as needed rather than discarding the source.

#### Flux capture

Flux-level captures preserve transition timing rather than already-decoded GCR bytes.

Prefer retaining flux captures when the disk uses or may use:

- weak bits,
- unusual timing,
- angular relationships,
- mastering artifacts,
- behavior that G64 cannot faithfully reproduce.

Do not convert the only archival master to a lower-fidelity format and discard the original.

## Phase 2 — Baseline the software

Run the unmodified preservation image under the best available emulator configuration.

Record:

- normal startup path,
- first disk access,
- load time,
- drive-head activity,
- whether the drive resets,
- whether custom code is uploaded,
- whether failure occurs immediately or later,
- exact failure behavior,
- relevant messages,
- emulator/drive model.

If the original image runs correctly, establish a known-good trace before modifying anything.

When testing a suspected dependency, prefer a controlled derivative that changes exactly one relevant byte or representation at a time. Record both hashes and the exact changed-byte count. Keep sector payload changes separate from D64 error-table changes so the experiment identifies which representation matters. Observe the decision point when possible; an eventual crash alone may be several destructive steps removed from the failed check.

If it fails under emulation but works from original hardware/media, suspect an image-format or emulation limitation before assuming the software itself is damaged.

## Phase 2A — Audit the logical filesystem representation

Do not trust a rendered directory listing as the complete filesystem model. For sector-oriented images, inspect and retain where practical:

- raw directory records and nonprintable filename bytes,
- advertised block counts versus traversed chain lengths,
- two or more entries that share the same chain,
- active/deleted chain overlaps and current deleted-chain recoverability,
- BAM sectors marked allocated but not referenced by active files,
- unusual directory-sector links,
- trailing error-table entries separately from sector payloads.

Treat a directory file type as metadata, not proof of content interpretation. A PRG record can be opened and streamed as text; a SEQ extraction can be given a misleading `.prg` host suffix. Derive the intended use from the consumer.

These checks can reveal decoy aliases, false sizes, hidden files with NUL/control-character names, reserved protection regions, and filesystem sentinels that ordinary LOAD/SAVE copying may omit.

