# Symbol-table sources and construction

The symbol tables in this directory are condensed analysis aids. They reorganize address, register, workspace, and routine facts around disassembly tasks and add cautions about banking, reused workspace, calling state, and evidentiary limits.

The four stock ROM images identified in [`rom-manifest.md`](rom-manifest.md) are not bundled.  The manifest retains source URLs, revisions, sizes, and hashes for owner-supplied files or explicit user-run acquisition.  Upstream source listings, JSON databases, and web pages are not bundled wholesale.

## Source map

| Reference | Construction sources |
|---|---|
| [`basic-symbols.md`](basic-symbols.md) | Michael Steil's *Ultimate Commodore 64 Reference — ROM Disassembly*, especially its Microsoft/Commodore Source and Lee Davison commentary columns. Website: https://www.pagetable.com/c64ref/c64disasm/; repository pinned at `mist64/c64ref` commit `7cae8b91d5317d1d18ae8cdcaac03533389e6032`: https://github.com/mist64/c64ref/tree/7cae8b91d5317d1d18ae8cdcaac03533389e6032 |
| [`kernal-symbols.md`](kernal-symbols.md) | The same pinned `mist64/c64ref` disassembly and commentary collection. |
| [`c64-io-symbols.md`](c64-io-symbols.md) | Esshahn's `mem64.json`, pinned at commit `e7e3ec46ce1092a231a72d47fb60ab39c3804dc1`: https://github.com/Esshahn/mem64/blob/e7e3ec46ce1092a231a72d47fb60ab39c3804dc1/mem64.json |
| [`c64-rom-workspace.md`](c64-rom-workspace.md) | The same pinned `mem64.json`, reorganized around BASIC/KERNAL workspace use. |
| [`1541-symbols.md`](1541-symbols.md) | Joe Forster/STA 1541 memory map mirrored by Herwig Siebenhofer at https://riff.2ix.at/c64/?dok=1541mem (accessed 2026-08-31), supplemented by documented 1541 ROM-disassembly conventions and verification against the hash-pinned ROM revision. |

## Licensing and attribution status

- The stock Commodore/Microsoft ROM binaries have no verified blanket redistribution license in the cited archive and are not included here.  Online availability is not a license grant.  The historical Microsoft BASIC-M6502 MIT release is a lineage reference, not a license grant for these exact C64 BASIC V2, KERNAL, character, or 1541 binaries.  Resolve this uncertainty before redistributing acquired images.

- `mist64/c64ref` is distributed under BSD-2-Clause. Its notice is retained at [`licenses/c64ref-BSD-2-Clause.txt`](../../../licenses/c64ref-BSD-2-Clause.txt).
- The pinned `Esshahn/mem64` repository does not contain a declared license file. This skill cites it as a construction source for factual address/register descriptions; citation does not imply that the upstream project is MIT-licensed.
- The cited 1541 memory-map mirror does not state reuse terms on the referenced page. This skill cites the page and attributed map rather than treating it as MIT-licensed material.
- Original organization, cautions, and additional analysis are covered by the repository license.  That license does not relicense external source material; see the [repository notices](../../../THIRD_PARTY_NOTICES.md).

These citations identify the material actually consulted. They should remain with the tables if the references are copied or adapted.
