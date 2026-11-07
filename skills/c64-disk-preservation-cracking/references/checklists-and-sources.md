# Reconnaissance, platform clues, stop criteria and sources

> Read [SKILL.md](../SKILL.md) first. This is the detailed procedure for the routed phase, not an instruction to expand every task. Commands and inline file paths below are relative to the **skill directory**, unless explicitly stated otherwise; Markdown links resolve from this reference.

## Protection reconnaissance checklist

For an unfamiliar protected disk, investigate roughly in this order:

1. Preserve and hash the original image.
2. Determine D64/G64/NIB/flux fidelity.
3. Audit raw directory records, chains, BAM, aliases, false counts, and error metadata.
4. Boot and record the failure/success path.
5. Determine whether normal KERNAL LOAD is used and whether BASIC text/links are rewritten.
6. Watch for direct CIA2 IEC manipulation.
7. Detect code uploaded into the 1541.
8. Capture and disassemble uploaded drive code.
9. Identify direct VIA accesses.
10. Determine what tracks/regions are read.
11. Classify any non-standard disk behavior.
12. Trace the returned data/status to the C64 and record the exact predicate.
13. Inventory success-only repair/decode/initialization effects.
14. Audit delayed checks, including ordinary file I/O and generated filenames.
15. Use separately hashed one-change controls where practical.
16. Choose the minimum preservation patch.
17. Validate the entire load/use lifecycle.
18. Document both original behavior and patch.

## Drive-code clues

When analyzing uploaded 1541 code, pay particular attention to:

```text
$0000-$0005    DOS job queue
$0300-$07FF    drive RAM / standard buffers, frequently reused for code
$1800-$180F    VIA #1, IEC/parallel communication
$1C00-$1C0F    VIA #2, disk mechanism and raw disk data
$C000-$FFFF    1541 DOS ROM
```

Consult `1541-symbols.md` for detailed meanings.

Direct reads around VIA #2 often indicate low-level disk access.

Direct writes around VIA #2 may manipulate:

- head movement,
- motor state,
- density,
- disk write/read behavior.

Do not infer exact bit semantics without consulting the hardware reference and surrounding code.

## C64-side clues

Pay particular attention to:

```text
$0314-$0315    IRQ vector
$0318-$0319    NMI vector
$DD00          CIA2 IEC + VIC bank
$DC00-$DC0F    CIA1 timers/IRQ
$D011/$D012    raster IRQ timing
```

Disk protection may coexist with:

- custom IRQ loaders,
- runtime decryption,
- self-modifying code,
- bank switching,
- loader code hidden beneath ROM/I/O.

Use the bundled [C64 ROM reference skill](../../c64-rom-reference/SKILL.md): its `c64-io-symbols.md`, `c64-rom-workspace.md`, `basic-symbols.md`, and `kernal-symbols.md` tables provide the relevant reference context. ROM bytes are installed separately, not distributed here.

## Do not confuse preservation image quality with cracking

A disk that fails as D64 but works as G64 may not need a software crack at all.

Likewise, a G64 that still cannot represent a physical signature may need either:

- a higher-fidelity archival representation,
- emulator support,
- or a derived runnable crack.

Always ask:

> Is the failure caused by the original software, the image format, the emulator, or the removed physical medium?

before patching code.

## Historical protection families

Names such as:

- V-MAX!,
- Vorpal,
- RapidLok,
- Para-Protect,
- XEMAG,
- TIMEX,

can provide useful hypotheses, but do not pattern-match blindly.

Different revisions may behave differently, and publishers often layered additional checks around commercial protection systems.

Identify observed mechanics first; name the family second.

## When to stop

The analysis is sufficient when:

- the original image is safely preserved,
- relevant loader architecture is understood,
- C64/drive responsibilities are mapped,
- the protection mechanism is supported by evidence,
- the authentication result is traced,
- any required runtime decoding is understood,
- the minimum patch is identified,
- delayed checks have been investigated,
- the derived image has been validated,
- changes are documented.

Do not require every byte of the loader or drive code to be fully understood if the preservation dependency is already established and the remaining code is unrelated.

## Sources and further reference

High-level historical and technical background:

- CommodoreGames.Net, **The 1541 Drive & GCR Encoding**  
  https://www.commodoregames.net/copyprotection/the-1541-drive.asp

- CommodoreGames.Net, **Protection Methods**  
  https://www.commodoregames.net/copyprotection/protection-methods.asp

- CommodoreGames.Net, **Commercial Duplication**  
  https://www.commodoregames.net/copyprotection/commercial-duplication.asp

- CommodoreGames.Net, **Emulation & Archiving**  
  https://www.commodoregames.net/copyprotection/emulation-archiving.asp

- CommodoreGames.Net, **Copy Tools & Parameters**  
  https://www.commodoregames.net/copyprotection/copy-tools-parameters.asp

These sources are useful for recognizing historical protection categories and understanding why particular physical disk features may or may not survive in common image formats.

Use actual runtime evidence from the disk, C64, 1541, Retro Debugger, and preservation image as the authority for any specific title.
