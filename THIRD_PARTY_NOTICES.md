# Third-party materials and provenance

The repository [MIT license](LICENSE) covers original authored material.  It does not automatically relicense third-party inputs, adapted code, mechanically derived code, or upstream reference material.  Availability online is not a license grant.

## Commodore/Microsoft ROM identities and generated specializations

**No ROM images are included.**  The [ROM manifest](skills/c64-rom-reference/references/rom-manifest.md) records exact revisions, source URLs, sizes, and hashes for separately supplied images.  The optional downloader runs only when explicitly invoked; a technical acquisition path is not a redistribution permission.

The cited archive does not establish a blanket redistribution license for these exact C64/1541 images.  Microsoft's MIT-licensed historical BASIC-M6502 source release is a lineage reference, not proof of licensing for these particular binaries.

The following included C files mechanically specialize hash-pinned ROM control flow:

- `skills/c64-basic-v2-rnd-analysis/analysis/generated_rnd_cycle.c`
- `skills/c64-basic-v2-rnd-analysis/analysis/scratch/generated_fin.c`

They retain the ROM-source provenance and licensing uncertainty; the repository MIT license is **not** a new license grant for them.  Their generators, input identities, and validation methods are retained so the derivation can be inspected.  Removing the ROM images does not by itself clear the generated files for redistribution.

## ChiptuneSAK

`shared/6502/cpu6502.py` derives from ChiptuneSAK's MIT-licensed 6502 emulator.  Its source header retains attribution, and the [full MIT notice](shared/6502/CHIPTUNESAK_LICENSE.txt) accompanies it.  Reduction and RND tools use this shared implementation.

## ROM, I/O, and workspace reference tables

The condensed reference tables retain their [construction sources and qualifications](skills/c64-rom-reference/references/SOURCES.md).

- Michael Steil's `mist64/c64ref` uses BSD-2-Clause; its [license notice](licenses/c64ref-BSD-2-Clause.txt) is included.
- The cited `Esshahn/mem64` revision has no verified declared license.
- The cited Joe Forster/STA 1541 memory-map mirror does not state verified reuse terms.

These sources provide address, register, workspace, and routine facts.  Citation and new organization do not imply that upstream material is MIT-licensed.  Preserve the source-specific qualifications when reusing the tables.

## RapidLok and Vorpal helpers

The included RapidLok and later-Vorpal helpers adapt selected tables and logic from Daryl Krans's [ReMaster-Utility](https://github.com/DarylKrans/ReMaster-Utility), pinned at commit `f30688de7fede5cef20c0a0d163ec13ec6ef7513`.  Exact source locations, behavior differences, and scope are retained in the [RapidLok attribution](skills/c64-disk-preservation-cracking/scripts/rapidlok/ATTRIBUTION.md) and [Vorpal attribution](skills/c64-disk-preservation-cracking/scripts/vorpal/ATTRIBUTION.md).

The pinned About text says “No rights reserved,” while a source copyright notice remains and no tracked LICENSE, COPYING, or NOTICE file was found at that revision.  This is permission evidence, not an inferred standard license or a universal waiver; its scope and coverage of third-party contributions remain uncertain.

Retain the relevant credits: Daryl Krans; Bangui Bob for RapidLok documentation and patching; Luigi Di Fraia for Vorpal GCR encoding documentation; and Pete Rittwage, author of Nibtools.  The detailed attribution documents remain part of the helpers' distribution.

## Analyzed formats and signatures

The p-code tools include bounded compiler/runtime recognition data and format knowledge, not complete compiler distributions.  A matching signature is evidence within its stated contract, not proof of ownership, a license grant for the recognized program, or permission to redistribute a supplied input.

Commercial games, compiler media, private captures, and private corpus evidence are not supplied merely because these tools can analyze them.  Use your own authorized inputs and preserve relevant rights and notices in any derived delivery.
