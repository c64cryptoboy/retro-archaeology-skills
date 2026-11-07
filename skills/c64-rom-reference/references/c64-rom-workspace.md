# C64 BASIC/KERNAL RAM Workspace Reference

Reference for 6502 disassembly of Commodore 64 software.

Primary construction source:

- Esshahn, `mem64.json`, pinned at commit `e7e3ec46ce1092a231a72d47fb60ab39c3804dc1`: https://github.com/Esshahn/mem64/blob/e7e3ec46ce1092a231a72d47fb60ab39c3804dc1/mem64.json

This table condenses and reorganizes factual workspace descriptions from that source for disassembly use. See [`SOURCES.md`](SOURCES.md) for provenance and the upstream licensing caveat.

This file covers RAM locations conventionally used by the stock C64 BASIC V2 and KERNAL ROMs.

## Critical disassembly rule

These addresses describe **stock ROM conventions**, not hardware ownership.

A machine-language program may freely repurpose many of these locations when it is not relying on the corresponding BASIC/KERNAL service.

Therefore:

> Do not infer that an access is performing the ROM-defined function merely because it touches a familiar workspace address.

For example, `$033C-$03FB` is the KERNAL cassette buffer, but programs that do not use cassette I/O commonly treat it as 192 bytes of general-purpose RAM.

---

# Zero page — `$0002-$00FF`

Zero page is heavily shared between BASIC, KERNAL, screen editor, serial I/O, cassette I/O, and RS-232.

## BASIC interpreter workspace — approximately `$0002-$008F`

| Address | Common symbol / role | Meaning |
|---|---|---|
| `$0002` | — | Unused by normal BASIC/KERNAL |
| `$0003-$0004` | — | Normally `$B1AA`, BASIC float-to-integer conversion entry |
| `$0005-$0006` | — | Normally `$B391`, BASIC integer-to-float conversion entry |
| `$0007` | — | Search/input digit/temporary integer/FAC byte |
| `$0008` | — | Search/tokenization/temporary integer byte |
| `$0009` | `TRMPOS` | Current column for `TAB()` / `SPC()` |
| `$000A` | `VERCK` | LOAD/VERIFY flag: 0 LOAD, nonzero VERIFY |
| `$000B` | `COUNT` | Tokenization/line/array temporary |
| `$000C` | `DIMFLG` | Array operation called from DIM |
| `$000D` | `VALTYP` | Expression type: numeric vs string |
| `$000E` | `INTFLG` | Numeric expression integer-vs-floating type |
| `$000F` | `GARBFL` | Quote/list/string-GC state |
| `$0010` | `SUBFLG` | Variable-name parsing / integer-variable acceptance |
| `$0011` | `INPFLG` | INPUT / GET / READ selector |
| `$0012` | `TANSGN` | Sign workspace for SIN/TAN |
| `$0013` | `CHANNL` | Current BASIC I/O device |
| `$0014-$0015` | `LINNUM` | Line number or address used by GOTO/GOSUB/RUN/PEEK/POKE/SYS/WAIT |
| `$0016` | `TEMPPT` | Next temporary-string descriptor slot |
| `$0017-$0018` | `LASTPT` | Pointer to previous temporary string |
| `$0019-$0021` | `TEMPST` | Temporary string-descriptor stack |
| `$0022-$0025` | `INDEX` / temp | General BASIC temporary workspace |
| `$0026-$0029` | — | Arithmetic multiply/divide auxiliary register |
| `$002A` | — | Unused normally |
| `$002B-$002C` | `TXTTAB` | Start of BASIC program; normally `$0801` |
| `$002D-$002E` | `VARTAB` | Start of simple variables / byte after BASIC program |
| `$002F-$0030` | `ARYTAB` | Start of arrays |
| `$0031-$0032` | `STREND` | End of arrays |
| `$0033-$0034` | `FRETOP` | Bottom of string storage; strings grow downward |
| `$0035-$0036` | `FRESPC` | Current string-allocation pointer |
| `$0037-$0038` | `MEMSIZ` | Top of BASIC memory; normally `$A000` |
| `$0039-$003A` | `CURLIN` | Current BASIC line; `$FFxx` indicates direct mode |
| `$003B-$003C` | `OLDLIN` | Line number saved for CONT |
| `$003D-$003E` | `OLDTXT` | Program-text pointer saved for CONT |
| `$003F-$0040` | `DATLIN` | DATA line number for READ |
| `$0041-$0042` | `DATPTR` | Pointer to next DATA item |
| `$0043-$0044` | `INPPTR` | Input-result pointer for GET/INPUT/READ |
| `$0045-$0046` | `VARNAM` | Current BASIC variable name/type encoding |
| `$0047-$0048` | `VARPNT` | Pointer to current variable/FN value |
| `$0049-$004A` | `FORPNT` / temp | Variable pointer / WAIT / OPEN/CLOSE/device temporary |
| `$004B-$004C` | — | Saved BASIC text pointer during GET/INPUT/READ |
| `$004D` | `OPPTR` / compare | Comparison operator flags |
| `$004E-$004F` | `DEFFNP` | Current DEF FN function pointer |
| `$0050-$0051` | — | Current string variable during allocation |
| `$0052` | — | Unused normally |
| `$0053` | — | Garbage-collection step size |
| `$0054-$0056` | — | `JMP abs` stub to current BASIC function; operand at `$0055-$0056` |
| `$0057-$005B` | — | Arithmetic register #3 |
| `$005C-$0060` | — | Arithmetic register #4 |
| `$0061-$0065` | `FAC` | BASIC floating-point accumulator |
| `$0066` | `FACSGN` | FAC sign |
| `$0067` | — | Polynomial degree |
| `$0068` | — | Arithmetic temporary |
| `$0069-$006D` | `ARG` | BASIC secondary floating-point register |
| `$006E` | `ARGSGN` | ARG sign |
| `$006F-$0070` | — | Pointer to first string in string comparison |
| `$0071-$0072` | — | Auxiliary array/VAL/polynomial pointer |
| `$0073-$008A` | `CHRGET` | RAM-resident BASIC byte-fetch routine |
| `$0079` | `CHRGOT` | Entry within CHRGET: examine current byte without advancing |
| `$007A-$007B` | `TXTPTR` | Pointer to current BASIC text byte |
| `$008B-$008F` | `RNDX` | Previous `RND()` state/result |

### High-value BASIC workspace

For reverse engineering, these are especially useful:

```text
$002B TXTTAB   BASIC program start
$002D VARTAB   variables start / program end + 1
$002F ARYTAB   arrays start
$0031 STREND   arrays end
$0033 FRETOP   string storage bottom
$0037 MEMSIZ   BASIC memory top
$0039 CURLIN   current BASIC line
$0041 DATPTR   current DATA pointer
$0045 VARNAM   current variable
$0047 VARPNT   current variable value
$0061 FAC      floating-point accumulator
$0069 ARG      second floating-point operand
$0073 CHRGET   BASIC text scanner
$0079 CHRGOT   current-byte scanner
$007A TXTPTR   BASIC program/direct-command text pointer
```

---

# KERNAL I/O workspace — approximately `$0090-$00C4`

| Address | Common symbol | Meaning |
|---|---|---|
| `$0090` | `STATUS` | `ST` device-status byte |
| `$0091` | `STKEY` | STOP-key status |
| `$0092` | — | Cassette timing constant/workspace |
| `$0093` | `VERCK`-related | LOAD/VERIFY flag used by KERNAL |
| `$0094` | `C3PO` | IEC output-buffer dirty flag |
| `$0095` | `BSOUR` | IEC previous/output byte buffer |
| `$0096` | — | Cassette end-of-tape state |
| `$0097` | — | Saved X/Y during cassette/RS-232 I/O |
| `$0098` | `LDTND` | Number of open files |
| `$0099` | `DFLTN` | Current input device; default keyboard 0 |
| `$009A` | `DFLTO` | Current output device; default screen 3 |
| `$009B` | — | Cassette parity workspace |
| `$009C` | — | Cassette byte-ready state |
| `$009D` | `MSGFLG` | KERNAL system/I/O message enable flags |
| `$009E` | — | RS-232/cassette byte and header workspace |
| `$009F` | — | Cassette filename/error-correction counter |
| `$00A0-$00A2` | `TIME` | Jiffy clock / `TI` |
| `$00A3` | — | IEC EOI / cassette bit counter |
| `$00A4` | — | IEC input byte / cassette parity |
| `$00A5` | — | IEC/cassette bit counter |
| `$00A6` | — | Cassette-buffer byte index |
| `$00A7` | — | RS-232 input bit buffer |
| `$00A8` | — | RS-232 input bit counter |
| `$00A9` | — | RS-232 stop-bit state |
| `$00AA` | — | RS-232 input byte |
| `$00AB` | — | RS-232 parity / cassette checksum |
| `$00AC-$00AD` | `SAL` / pointer | SAVE pointer; also screen-scroll pointer |
| `$00AE-$00AF` | `EAL` / pointer | LOAD/SAVE end pointer; also color-scroll pointer |
| `$00B0-$00B1` | — | I/O temporary |
| `$00B2-$00B3` | `TAPE1` | Pointer to cassette buffer; default `$033C` |
| `$00B4` | — | RS-232/cassette bit count |
| `$00B5` | — | RS-232 output bit buffer |
| `$00B6` | — | RS-232 output byte |
| `$00B7` | `FNLEN` | Filename/command length |
| `$00B8` | `LA` | Current logical file number |
| `$00B9` | `SA` | Current secondary address |
| `$00BA` | `FA` | Current device number |
| `$00BB-$00BC` | `FNADR` | Pointer to filename/command |
| `$00BD` | — | RS-232/cassette parity/data byte |
| `$00BE` | — | Cassette block counter |
| `$00BF` | — | I/O temporary |
| `$00C0` | — | Datasette motor state |
| `$00C1-$00C2` | `STAL` | Start address for LOAD/SAVE/cassette/memory test |
| `$00C3-$00C4` | `MEMUSS` | Secondary LOAD start / initialization pointer workspace |

---

# Keyboard and screen-editor zero page — `$00C5-$00F6`

| Address | Common symbol | Meaning |
|---|---|---|
| `$00C5` | `LSTX` | Matrix code of previously pressed key |
| `$00C6` | `NDX` | Number of characters in keyboard buffer |
| `$00C7` | `RVS` | Reverse-video mode |
| `$00C8` | `INDX` | Logical screen-line length during input |
| `$00C9` | `LXSP` | Cursor row when screen input started |
| `$00CA` | `SFDX` | Cursor column when screen input started |
| `$00CB` | `LSTP` | Current keyboard matrix code |
| `$00CC` | `BLNSW` | Cursor visibility/blink enable |
| `$00CD` | `BLNCT` | Cursor blink countdown |
| `$00CE` | `GDBLN` | Character beneath cursor |
| `$00CF` | `BLNON` | Cursor blink phase |
| `$00D0` | `CRSW` | Screen-input/end-of-line state |
| `$00D1-$00D2` | `PNT` | Pointer to current screen line |
| `$00D3` | `PNTR` | Current cursor column |
| `$00D4` | `QTSW` | Quote mode |
| `$00D5` | `LNMX` | Current logical screen-line length minus one |
| `$00D6` | `TBLX` | Current cursor row |
| `$00D7` | `DATA` | Current PETSCII/output byte; also cassette workspace |
| `$00D8` | `INSRT` | Number of pending inserted characters |
| `$00D9-$00F1` | `LDTB1` | High-byte table for 25 screen-line pointers; high bit marks logical-line continuation |
| `$00F2` | — | Screen-scroll temporary |
| `$00F3-$00F4` | `USER` / color pointer | Pointer into Color RAM |
| `$00F5-$00F6` | `KEYTAB` | Pointer to keyboard matrix-to-PETSCII table |

## RS-232 pointers

| Address | Common symbol | Meaning |
|---|---|---|
| `$00F7-$00F8` | `RIBUF` | RS-232 input-buffer pointer |
| `$00F9-$00FA` | `ROBUF` | RS-232 output-buffer pointer |
| `$00FB-$00FE` | — | Normally unused zero-page bytes |
| `$00FF` onward | — | Floating-point-to-string workspace crosses into page 1 |

---

# Page 1 — `$0100-$01FF`

The 6502 hardware stack occupies `$0100-$01FF`.

BASIC also places FOR/GOSUB stack records here.

During cassette input, part of page 1 may hold pointers to bytes that had errors during the first tape pass.

### Disassembly caution

Do not classify page-1 data seen in snapshots as ordinary application variables without considering the current stack pointer and whether BASIC/cassette operations are active.

---

# Page 2 — `$0200-$02FF`

## Input and file tables

| Address range | Common symbol | Meaning |
|---|---|---|
| `$0200-$0258` | `BUF` | Screen/input buffer, 89 bytes |
| `$0259-$0262` | `LAT` | Logical file numbers, 10 entries |
| `$0263-$026C` | `FAT` | Device numbers, 10 entries |
| `$026D-$0276` | `SAT` | Secondary addresses, 10 entries |
| `$0277-$0280` | `KEYD` | Keyboard buffer, normally 10 bytes |

## System/editor configuration

| Address | Common symbol / role | Meaning |
|---|---|---|
| `$0281-$0282` | `MEMSTR` | Start of BASIC RAM after memory test; normally `$0800` |
| `$0283-$0284` | `MEMSIZ`-related | End of BASIC RAM after memory test; normally `$A000` |
| `$0285` | — | Serial timeout workspace / normally unused |
| `$0286` | `COLOR` | Current text/cursor color |
| `$0287` | `GDCOL` | Color of character beneath cursor |
| `$0288` | `HIBASE` | High byte of screen-memory base; normally `$04` for `$0400` |
| `$0289` | `XMAX` | Maximum keyboard-buffer size |
| `$028A` | `RPTFLG` | Keyboard-repeat mode |
| `$028B` | `KOUNT` | Repeat delay/countdown |
| `$028C` | `DELAY` | Initial key-repeat delay |
| `$028D` | `SHFLAG` | Current SHIFT/CTRL/Commodore-key state |
| `$028E` | `LSTSHF` | Previous shift-key state |
| `$028F-$0290` | `KEYLOG` | Keyboard decode-vector pointer |
| `$0291` | `MODE` | Keyboard mode/case state |
| `$0292` | `AUTODN` | Auto-scroll/down state |
| `$0293` | `M51CTR` | RS-232 timing/control |
| `$0294` | `M51CDR` | RS-232 timing/control |
| `$0295-$0296` | `M51AJB` | RS-232 baud/timing workspace |
| `$0297` | `RSSTAT` | RS-232 status |
| `$0298` | `BITNUM` | RS-232 bit count |
| `$0299-$029A` | `BAUDOF` | RS-232 baud timing |
| `$029B` | `RIDBE` | RS-232 input-buffer end index |
| `$029C` | `RIDBS` | RS-232 input-buffer start index |
| `$029D` | `RODBS` | RS-232 output-buffer start index |
| `$029E` | `RODBE` | RS-232 output-buffer end index |
| `$029F-$02A0` | `IRQTMP` | Saved IRQ vector / cassette-I/O state |
| `$02A1` | — | Saved CIA2 interrupt-control state for RS-232 |
| `$02A2` | — | Saved CIA1 timer-A control state for cassette I/O |
| `$02A3-$02A4` | — | I/O temporary |
| `$02A5` | — | Screen-scroll row counter |
| `$02A6` | `TVSFLG` | NTSC/PAL selector used for timing |
| `$02A7-$02FF` | — | Normally unused / available RAM |

### Key disassembly locations

```text
$0200 BUF       BASIC/KERNAL input buffer
$0277 KEYD      keyboard queue
$0286 COLOR     current character color
$0288 HIBASE    screen-memory page high byte
$028A RPTFLG    keyboard repeat behavior
$028D SHFLAG    modifier-key state
$028F KEYLOG    keyboard decode vector
$02A6 TVSFLG    PAL/NTSC timing selector
```

---

# Page 3 vectors and workspace — `$0300-$03FF`

## BASIC vectors

| Address | Common symbol | Default target | Meaning |
|---|---|---|---|
| `$0300-$0301` | `IERROR` | `$E38B` | BASIC error/warm-start vector |
| `$0302-$0303` | `IMAIN` | `$A483` | BASIC main/idle loop |
| `$0304-$0305` | `ICRNCH` | `$A57C` | BASIC tokenizer/crunch vector |
| `$0306-$0307` | `IQPLOP` | `$A71A` | BASIC LIST/token decode vector |
| `$0308-$0309` | `IGONE` | `$A7E4` | BASIC statement execution vector |
| `$030A-$030B` | `IEVAL` | `$AE86` | BASIC expression-evaluation vector |

These vectors are intentionally RAM-resident and can be patched by extensions.

## SYS/USR state

| Address | Symbol / role | Meaning |
|---|---|---|
| `$030C` | `SAREG` | A register for/after SYS |
| `$030D` | `SXREG` | X register for/after SYS |
| `$030E` | `SYREG` | Y register for/after SYS |
| `$030F` | `SPREG` | Processor status for/after SYS |
| `$0310-$0312` | `USRPOK` | `JMP abs` stub for `USR()`; target in `$0311-$0312` |
| `$0313` | — | Normally unused |

## KERNAL interrupt vectors

| Address | Common symbol | Default target | Meaning |
|---|---|---|---|
| `$0314-$0315` | `CINV` | `$EA31` | IRQ vector |
| `$0316-$0317` | `CBINV` | `$FE66` | BRK vector |
| `$0318-$0319` | `NMINV` | `$FE47` | NMI vector |

These are among the most important locations in C64 game/demo disassembly.

A write to `$0314/$0315` commonly installs a custom IRQ routine.

## KERNAL indirect I/O vectors

| Address | Common symbol | Purpose |
|---|---|---|
| `$031A-$031B` | `IOPEN` | OPEN vector |
| `$031C-$031D` | `ICLOSE` | CLOSE vector |
| `$031E-$031F` | `ICHKIN` | CHKIN vector |
| `$0320-$0321` | `ICKOUT` | CHKOUT vector |
| `$0322-$0323` | `ICLRCH` | CLRCHN vector |
| `$0324-$0325` | `IBASIN` | CHRIN vector |
| `$0326-$0327` | `IBSOUT` | CHROUT vector |
| `$0328-$0329` | `ISTOP` | STOP vector |
| `$032A-$032B` | `IGETIN` | GETIN vector |
| `$032C-$032D` | `ICLALL` | CLALL vector |
| `$032E-$032F` | `USRCMD` | User-command vector / unused by normal KERNAL path |
| `$0330-$0331` | `ILOAD` | LOAD vector |
| `$0332-$0333` | `ISAVE` | SAVE vector |

These vectors allow software to intercept standard KERNAL I/O.

## Remaining page-3 system workspace

| Address range | Meaning |
|---|---|
| `$0334-$033B` | KERNAL/tape/I/O workspace; context dependent |
| `$033C-$03FB` | Cassette buffer, 192 bytes |
| `$03FC-$03FF` | Not part of the standard cassette buffer; normally available/context dependent |

### Cassette buffer: `$033C-$03FB`

This region is owned by the KERNAL while cassette operations are active.

It is used for tape header/data handling and related cassette I/O state.

However:

> If software does not use the datasette, `$033C-$03FB` is commonly repurposed as general RAM.

Therefore an instruction such as:

```asm
STA $033C,X
```

does **not** by itself imply cassette activity.

Prefer a neutral interpretation until calls to cassette-related KERNAL functionality or runtime behavior establish that tape I/O is involved.

---

# BASIC program and default screen areas

| Range | Normal use |
|---|---|
| `$0400-$07E7` | Default 40×25 screen RAM |
| `$07E8-$07FF` | Normally free / outside 1000-byte screen matrix |
| `$0800` | BASIC RAM memory-test/start marker convention |
| `$0801+` | Default BASIC program start |
| `$A000` | Default top of BASIC RAM when BASIC ROM is mapped in |

### Screen RAM caveat

`$0400` is only the default screen location.

The VIC-II can display screen memory elsewhere, and the KERNAL's `$0288` (`HIBASE`) records where the screen editor believes screen memory resides.

For determining the **actual VIC display**, inspect `$DD00` and `$D018`; do not rely only on `$0288`.

---

# High-value symbols for disassembly

```text
BASIC:
$002B TXTTAB   BASIC program start
$002D VARTAB   variables start
$002F ARYTAB   arrays start
$0031 STREND   arrays end
$0033 FRETOP   string area bottom
$0037 MEMSIZ   BASIC memory top
$0039 CURLIN   current BASIC line
$0061 FAC      floating-point accumulator
$0069 ARG      second FP register
$0073 CHRGET   BASIC text scanner
$0079 CHRGOT   BASIC current-byte scanner
$007A TXTPTR   current BASIC text pointer

KERNAL I/O:
$0090 STATUS   ST status
$0098 LDTND    number of open files
$0099 DFLTN    current input device
$009A DFLTO    current output device
$00A0 TIME     jiffy clock
$00B2 TAPE1    cassette-buffer pointer
$00B7 FNLEN    filename length
$00B8 LA       logical file
$00B9 SA       secondary address
$00BA FA       device number
$00BB FNADR    filename pointer

SCREEN/KEYBOARD:
$00C6 NDX      keyboard-buffer length
$00D1 PNT      current screen-line pointer
$00D3 PNTR     cursor column
$00D6 TBLX     cursor row
$00D9 LDTB1    screen-line high-byte table
$0200 BUF      input buffer
$0277 KEYD     keyboard buffer
$0286 COLOR    current text color
$0288 HIBASE   screen-memory page for editor
$028D SHFLAG   modifier keys

VECTORS:
$0300 IERROR
$0302 IMAIN
$0304 ICRNCH
$0306 IQPLOP
$0308 IGONE
$030A IEVAL
$0314 CINV     IRQ
$0316 CBINV    BRK
$0318 NMINV    NMI
$031A IOPEN
$031C ICLOSE
$031E ICHKIN
$0320 ICKOUT
$0322 ICLRCH
$0324 IBASIN
$0326 IBSOUT
$0328 ISTOP
$032A IGETIN
$032C ICLALL
$0330 ILOAD
$0332 ISAVE

$033C-$03FB    cassette buffer
```

---

# Interpretation cautions for AI-assisted disassembly

1. **These are conventions, not protected memory.** Application code may repurpose BASIC/KERNAL workspace.

2. **Zero-page locations are heavily multiplexed.** A byte may have different meanings in different BASIC/KERNAL routines.

3. **Do not infer cassette activity from `$033C-$03FB` alone.** It is a popular block of free RAM when tape I/O is not used.

4. **Do not infer display location from `$0288` alone.** `$0288` is the screen editor's screen-page state; the VIC's actual display configuration comes from hardware registers.

5. **RAM vectors are strong semantic evidence.** Reads/writes around `$0300-$0333`, especially `$0314-$0319`, often indicate hooking or restoring BASIC/KERNAL behavior.

6. **A custom IRQ at `$0314` may bypass much of the stock housekeeping IRQ.** Determine whether it chains to `$EA31`, `$EA7E`, `$EA81`, or elsewhere rather than assuming normal keyboard/jiffy-clock processing continues.

7. **BASIC workspace is especially meaningful in BASIC or hybrid BASIC/ML programs.** In a standalone game that banks BASIC out permanently, much of `$0002-$008F` may simply be application zero page.

8. **KERNAL file variables are useful around calls to SETNAM/SETLFS/LOAD/SAVE/OPEN.** Outside those contexts they may be stale or repurposed.

9. **Page 2 contains both persistent configuration and temporary communication buffers.** Distinguish stable variables such as `$0288` from transient contents of `$0200`.

10. **Runtime evidence overrides this table.** If the running program clearly treats a conventional ROM workspace byte as its own variable, describe the program's actual use.

---

# Source

Esshahn, `mem64.json`:
https://github.com/Esshahn/mem64/blob/master/mem64.json

The source memory-map descriptions have been condensed, grouped, and annotated for use during C64 6502 disassembly.
