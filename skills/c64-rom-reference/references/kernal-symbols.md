# C64 KERNAL ROM Symbols — `$E000-$FFFF`

Reference for 6502 disassembly of Commodore 64 software that calls into, hooks, or reuses routines in the KERNAL ROM.

Primary construction source:

- Michael Steil, *Ultimate Commodore 64 Reference — ROM Disassembly*: https://www.pagetable.com/c64ref/c64disasm/
- Corresponding BSD-2-Clause source repository, pinned at commit `7cae8b91d5317d1d18ae8cdcaac03533389e6032`: https://github.com/mist64/c64ref/tree/7cae8b91d5317d1d18ae8cdcaac03533389e6032

The pagetable.com disassembly presents several commentary sources side-by-side. This table is a condensed analysis reference constructed primarily from the **Microsoft/Commodore Source** and **Lee Davison** commentary. See [`SOURCES.md`](SOURCES.md) and the retained BSD notice for provenance and terms.

## Scope

This file follows the **physical KERNAL ROM address range**:

- Included here: `$E000-$FFFF`
- This includes BASIC-related code at approximately `$E000-$E39F`.

That BASIC continuation is intentionally kept here rather than in `basic-symbols.md`.

## Disassembly guidance

- `$FF81-$FFF3` is the documented KERNAL jump table and is the most stable interface.
- Calls to internal addresses below `$FF81` may depend on undocumented state and ROM revision.
- Screen editor, IEC serial, cassette, RS-232, IRQ, and initialization code all share zero-page/page-2/page-3 workspace.
- Use `c64-io-symbols.md` for hardware register semantics.
- Use `c64-rom-workspace.md` for RAM workspace semantics.

---

# BASIC continuation inside KERNAL ROM — `$E000-$E39F`

These routines are functionally part of BASIC V2 even though they physically reside in the KERNAL ROM.

| Address | Suggested symbol | Meaning |
|---|---|---|
| `$E000` | `EXP_CONT` | Continuation of EXP() from BASIC ROM `$BFFD` |
| `$E043` | `POLYX` / exponential polynomial helper | Evaluate an even/odd polynomial form used by EXP() |
| `$E059` | `POLY` / polynomial-series helper | Evaluate a coefficient series using FAC arithmetic |
| `$E097` | `RND` | BASIC RND() implementation; dispatch by FAC sign/zero |
| `$E0F9` | `BASIC_IO_ERROR` | Convert KERNAL status/errors into BASIC errors |
| `$E10C` | `OUTDO` / output helper | BASIC output through KERNAL |
| `$E12A` | `SYS` | BASIC SYS command |
| `$E156` | `SAVE_BASIC` | BASIC SAVE command |
| `$E165` | `VERIFY_BASIC` | BASIC VERIFY command |
| `$E168` | `LOAD_BASIC` | BASIC LOAD command |
| `$E1BE` | `OPEN_BASIC` | BASIC OPEN command |
| `$E1C7` | `CLOSE_BASIC` | BASIC CLOSE command |
| `$E1D4` | `SLPARA` | Parse logical file/device/secondary-address parameters |
| `$E206` | `COMBYT` | Parse comma followed by byte expression |
| `$E20E` | `GET_BASIC` | BASIC GET statement |
| `$E219` | `GETIN_BASIC` | GET input path |
| `$E264` | `COS` | Cosine; BASIC function vector at `$A066` |
| `$E26B` | `SIN` | Sine; BASIC function vector at `$A068` |
| `$E2B4` | `TAN` | Tangent; BASIC function vector at `$A06A` |
| `$E2E0` | `PI_OVER_TWO` | Five-byte floating constant; `$E2E3` lies inside this data, not an initialization entry |
| `$E30E` | `ATN` | Arctangent; BASIC function vector at `$A06C` |
| `$E37B` | `BASIC_WARM_START` | BASIC warm start |
| `$E394` | `BASIC_COLD_START` | BASIC cold start |

### Agent note

A call to `$E12A`, `$E156`, `$E168`, `$E1BE`, etc. is a call to a **BASIC statement implementation**, not directly to the documented KERNAL API.

For example, `$E168` performs BASIC LOAD statement processing and eventually invokes the KERNAL LOAD facilities; it is not equivalent to calling `$FFD5`.

---

# Screen editor and keyboard — roughly `$E400-$ECFF`

This region contains the screen editor, keyboard scan/decode, cursor handling, screen scrolling, and much of the normal IRQ housekeeping.

| Address | Suggested symbol | Meaning |
|---|---|---|
| `$E422` | `CLRSCR`-related | Initialize/clear screen state |
| `$E4DA` | `GETIN_SCREEN` | Keyboard/screen GETIN path |
| `$E505` | `CHRIN_SCREEN` | Screen/keyboard CHRIN |
| `$E544` | `SCREEN_INPUT` | Read logical line / editor input |
| `$E566` | `SCREEN_GET_CHAR` | Character fetch from screen line |
| `$E5B4` | `SCREEN_PUT_CHAR` | Screen character output/editing path |
| `$E632` | `NEWLINE` / line advance | Move to next logical/physical line |
| `$E6B6` | `SCROLL` | Scroll screen |
| `$E701` | `OPEN_SPACE` | Insert/open screen line or character space |
| `$E716` | `MOVE_LINE` | Screen line copy/move helper |
| `$E87C` | `PLOT_INTERNAL` | Cursor position helper |
| `$E8EA` | `SET_SCREEN_PTR` | Compute screen/color pointers for current row |
| `$E965` | `SET_COLOR_PTR` | Color/screen pointer helper |
| `$E9F0` | `PRINT_SCREEN` | CHROUT screen-device path |
| `$EA13` | `SCREEN_CONTROL` | PETSCII control-character handling |
| `$EA31` | `IRQ_HOUSEKEEPING` | Normal KERNAL IRQ entry/housekeeping |
| `$EA61` | `KEYBOARD_SCAN` | Scan keyboard matrix / key decode |
| `$EA7E` | `IRQ_CONTINUE` | IRQ continuation after keyboard scan |
| `$EA81` | `IRQ_EXIT` | IRQ exit path |
| `$EB48` | `KEY_DECODE` | Keyboard table/decode handling |
| `$EB79` | `KEY_TABLES` | Keyboard translation tables / related data |
| `$EC44` | `SCREEN_LINES` / editor tables | Screen editor lookup data |

## `$EA31` significance

The stock IRQ normally handles:

- keyboard scanning/repeat,
- jiffy clock update,
- cursor/editor housekeeping,
- then returns through the KERNAL interrupt path.

Custom IRQ routines commonly:

- replace RAM vector `$0314/$0315`,
- chain to `$EA31`,
- chain later to `$EA7E` or `$EA81`,
- or bypass KERNAL housekeeping entirely.

Do not assume keyboard/jiffy-clock updates continue after a custom IRQ is installed.

---

# IEC serial bus and general I/O — roughly `$ED00-$F0FF`

| Address | Suggested symbol | Meaning |
|---|---|---|
| `$ED0C` | `TALK_INTERNAL` | Send TALK device command |
| `$ED09` | `LISTEN_INTERNAL` | Send LISTEN device command |
| `$EDB9` | `SECND_INTERNAL` | Send secondary address after LISTEN |
| `$EDC7` | `TKSA_INTERNAL` | Send secondary address after TALK |
| `$EDDD` | `CIOUT_INTERNAL` | Output byte to IEC bus |
| `$EE13` | `IEC_BIT_OUT` | Serial output timing/bit loop |
| `$EE85` | `ACPTR_INTERNAL` | Receive byte from IEC bus |
| `$EF06` | `UNTLK_INTERNAL` | Send UNTALK |
| `$EF23` | `UNLSN_INTERNAL` | Send UNLISTEN |
| `$EF4A` | `IEC_CLOCK_DATA` | IEC handshake/line-control helper |
| `$EF84` | `IEC_TIMEOUT` | IEC timeout/handshake path |
| `$F0A4` | `IEC_STATUS` / message helper | Serial status/error handling |
| `$F0BD` | `KERNAL_IO_MESSAGES` | KERNAL I/O message text table |

### Important caution

Fastloaders often bypass the public KERNAL serial API and manipulate CIA2 `$DD00` directly. A game doing direct `$DD00` timing should not be described as using these normal IEC routines unless control flow actually reaches them.

---

# KERNAL I/O messages

At approximately `$F0BD`, the ROM contains messages such as:

- `I/O ERROR #`
- `SEARCHING`
- `FOR`
- `PRESS PLAY ON TAPE`
- `PRESS RECORD & PLAY ON TAPE`
- `LOADING`
- `SAVING`
- `VERIFYING`
- `FOUND`
- `OK`

These strings may appear in ROM-data searches and should not be mistaken for executable code.

---

# Channel I/O and file management — roughly `$F100-$F6FF`

| Address | Suggested symbol | Meaning |
|---|---|---|
| `$F13E` | `GETIN_INTERNAL` | KERNAL GETIN implementation |
| `$F157` | `CHRIN_INTERNAL` | KERNAL CHRIN implementation |
| `$F1CA` | `CHROUT_INTERNAL` | KERNAL CHROUT implementation |
| `$F20E` | `CHKIN_INTERNAL` | Set input channel |
| `$F250` | `CHKOUT_INTERNAL` | Set output channel |
| `$F291` | `CLOSE_INTERNAL` | CLOSE implementation |
| `$F2C7` | `FIND_FILE` | Search open logical-file table |
| `$F30F` | `CLOSE_IEC` / channel close helper | Device-specific close path |
| `$F32F` | `CLALL_INTERNAL` | Close all files/channels |
| `$F333` | `CLRCHN_INTERNAL` | Restore default I/O channels |
| `$F34A` | `OPEN_INTERNAL` | OPEN implementation |
| `$F3D5` | `OPEN_IEC` | Serial-device OPEN path |
| `$F409` | `OPEN_TAPE` | Cassette OPEN path |
| `$F49E` | `LOAD_SETUP` | LOAD preparation |
| `$F4A5` | `LOAD_INTERNAL` | LOAD implementation |
| `$F5AF` | `LOAD_TAPE` | Cassette LOAD path |
| `$F5ED` | `SAVE_INTERNAL` | SAVE implementation |
| `$F68F` | `SAVE_TAPE` | Cassette SAVE path |
| `$F6ED` | `STOP_INTERNAL` | STOP-key test implementation |
| `$F6FB` | `ERROR9` / I/O error path | I/O status/error helper |

---

# Cassette / datasette routines — roughly `$F700-$FCFF`

The cassette code uses substantial shared workspace, including `$033C-$03FB`.

| Address | Suggested symbol | Meaning |
|---|---|---|
| `$F72C` | `TAPE_FIND_HEADER` | Find/read cassette header |
| `$F76A` | `TAPE_READ_BLOCK` | Cassette block input |
| `$F7EA` | `TAPE_SETUP_READ` | Setup tape input timing/state |
| `$F817` | `TAPE_READ_BIT` | Cassette bit/pulse decode path |
| `$F8E2` | `TAPE_STORE_CHAR` | Store decoded tape byte / checksum path |
| `$F92C` | `TAPE_SYNC` | Tape synchronization logic |
| `$FA60` | `TAPE_WRITE_SETUP` | Cassette output setup |
| `$FBA6` | `TAPE_WRITE_BIT` | Cassette pulse/bit output |
| `$FC57` | `TAPE_IRQ` | Cassette-related IRQ/timing path |
| `$FC93` | `TAPE_MOTOR_OFF` | Datasette motor/control cleanup |

### Disassembly caution

An access to cassette workspace does **not** prove that the program is doing tape I/O. Verify calls into these routines or direct manipulation of the datasette bits on `$0001`.

---

# Clock, STOP, IRQ/NMI, and reset support

| Address | Suggested symbol | Meaning |
|---|---|---|
| `$F6ED` | `STOP_INTERNAL` | Check STOP key |
| `$F69B` | `UDTIM_INTERNAL` | Update jiffy clock |
| `$FE43` | `NMI_ENTRY` | Hardware NMI entry path |
| `$FE47` | `NMI_DEFAULT` | Default RAM NMI vector target |
| `$FE66` | `BRK_DEFAULT` | Default BRK vector target |
| `$FE72` | `NMI_RS232` | NMI/RS-232 dispatch |
| `$FEBC` | `IRQ_ENTRY` | Hardware IRQ/BRK entry |
| `$FF48` | `IRQ_RETURN` | Restore registers and RTI |
| `$FCE2` | `RESET_CHECK` | Reset/startup preparation |
| `$FD02` | `CHECK_ROM` | ROM/signature/startup checks |
| `$FD15` | `RESTOR_INTERNAL` | Restore default RAM vectors |
| `$FD1A` | `VECTOR_INTERNAL` | Read/set RAM vectors |
| `$FD50` | `RAMTAS_INTERNAL` | Test/clear RAM and set memory bounds |
| `$FDA3` | `IOINIT_INTERNAL` | Initialize I/O chips |
| `$FDF9` | `SETNAM_INTERNAL` | Set filename parameters |
| `$FE00` | `SETLFS_INTERNAL` | Set logical file/device/secondary address |
| `$FE07` | `READST_INTERNAL` | Read I/O status |
| `$FE18` | `SETMSG_INTERNAL` | Set KERNAL message-control flags |
| `$FE25` | `SETTMO_INTERNAL` | Set IEEE/serial timeout behavior |
| `$FE34` | `MEMTOP_INTERNAL` | Read/set top of memory |
| `$FE66` | `BRK_HANDLER` | Default BRK handler |
| `$FE87` | `MEMBOT_INTERNAL` | Read/set bottom of memory |

---

# Default RAM-vector table in ROM

The table near `$FD30` is copied into RAM `$0314-$0333` by RESTOR.

Important default targets include:

```text
$0314 IRQ       -> $EA31
$0316 BRK       -> $FE66
$0318 NMI       -> $FE47

$031A OPEN      -> $F34A
$031C CLOSE     -> $F291
$031E CHKIN     -> $F20E
$0320 CHKOUT    -> $F250
$0322 CLRCHN    -> $F333
$0324 CHRIN     -> $F157
$0326 CHROUT    -> $F1CA
$0328 STOP      -> $F6ED
$032A GETIN     -> $F13E
$032C CLALL     -> $F32F
$032E USRCMD    -> $FE66
$0330 LOAD      -> $F4A5
$0332 SAVE      -> $F5ED
```

These RAM vectors are extremely useful during disassembly because software commonly hooks them.

---

# Public KERNAL jump table — `$FF81-$FFF3`

These are the documented stable entry points. Prefer these names whenever calls target the jump table.

| Address | Symbol | Purpose |
|---|---|---|
| `$FF81` | `CINT` | Initialize screen editor |
| `$FF84` | `IOINIT` | Initialize I/O devices/chips |
| `$FF87` | `RAMTAS` | RAM test / initialize memory pointers |
| `$FF8A` | `RESTOR` | Restore default system vectors |
| `$FF8D` | `VECTOR` | Read/set RAM vectors |
| `$FF90` | `SETMSG` | Control KERNAL messages |
| `$FF93` | `SECND` | Send secondary address after LISTEN |
| `$FF96` | `TKSA` | Send secondary address after TALK |
| `$FF99` | `MEMTOP` | Read/set top of RAM |
| `$FF9C` | `MEMBOT` | Read/set bottom of RAM |
| `$FF9F` | `SCNKEY` | Scan keyboard |
| `$FFA2` | `SETTMO` | Set serial timeout |
| `$FFA5` | `ACPTR` | Receive byte from IEC serial bus |
| `$FFA8` | `CIOUT` | Send byte to IEC serial bus |
| `$FFAB` | `UNTLK` | Send UNTALK |
| `$FFAE` | `UNLSN` | Send UNLISTEN |
| `$FFB1` | `LISTEN` | Command device to LISTEN |
| `$FFB4` | `TALK` | Command device to TALK |
| `$FFB7` | `READST` | Read I/O status byte |
| `$FFBA` | `SETLFS` | Set logical file/device/secondary address |
| `$FFBD` | `SETNAM` | Set filename/address |
| `$FFC0` | `OPEN` | Open logical file |
| `$FFC3` | `CLOSE` | Close logical file |
| `$FFC6` | `CHKIN` | Select input channel |
| `$FFC9` | `CHKOUT` | Select output channel |
| `$FFCC` | `CLRCHN` | Restore default I/O channels |
| `$FFCF` | `CHRIN` | Read character from current input |
| `$FFD2` | `CHROUT` | Output character to current output |
| `$FFD5` | `LOAD` | LOAD or VERIFY |
| `$FFD8` | `SAVE` | SAVE |
| `$FFDB` | `SETTIM` | Set jiffy clock |
| `$FFDE` | `RDTIM` | Read jiffy clock |
| `$FFE1` | `STOP` | Test STOP key |
| `$FFE4` | `GETIN` | Get character from current input device |
| `$FFE7` | `CLALL` | Close all channels/files |
| `$FFEA` | `UDTIM` | Update jiffy clock |
| `$FFED` | `SCREEN` | Return screen rows/columns |
| `$FFF0` | `PLOT` | Read/set cursor position |
| `$FFF3` | `IOBASE` | Return base address of I/O devices |

### High-value calling conventions

#### SETLFS `$FFBA`

Typical:

```asm
LDA #logical_file
LDX #device
LDY #secondary_address
JSR $FFBA
```

#### SETNAM `$FFBD`

Typical:

```asm
LDA #filename_length
LDX #<filename
LDY #>filename
JSR $FFBD
```

#### LOAD `$FFD5`

Typical:

- A = `0` for LOAD, nonzero for VERIFY
- X/Y = destination address when secondary address semantics request caller-specified load address
- carry/status indicates result according to KERNAL convention

Inspect SETLFS/SETNAM state and secondary address before deciding exactly how a call behaves.

#### CHROUT `$FFD2`

A contains PETSCII/control code to send to current output device.

If output device is the screen, control characters can change cursor position, colors, reverse mode, clear/insert/delete, etc.

#### PLOT `$FFF0`

Carry distinguishes read versus set operation. Do not assume every call simply sets the cursor.

---

# Hardware vectors at top of ROM

| Address | Meaning |
|---|---|
| `$FFFA-$FFFB` | 6510 NMI vector |
| `$FFFC-$FFFD` | RESET vector |
| `$FFFE-$FFFF` | IRQ/BRK vector |

These hardware vectors point into KERNAL entry code, which then usually dispatches through the RAM vectors in page 3.

---

# High-value KERNAL symbols for disassembly

```text
BASIC-IN-KERNAL:
$E000 EXP continuation
$E059 POLY / polynomial-series helper
$E097 RND
$E12A SYS
$E156 SAVE statement
$E165 VERIFY statement
$E168 LOAD statement
$E1BE OPEN statement
$E1C7 CLOSE statement
$E20E GET statement
$E37B BASIC warm start
$E394 BASIC cold start

SCREEN / IRQ:
$E4DA GETIN screen path
$E505 CHRIN screen path
$E6B6 screen scroll
$E9F0 screen CHROUT path
$EA31 normal IRQ housekeeping
$EA61 keyboard scan
$EA7E IRQ continuation
$EA81 IRQ exit

IEC:
$ED09 LISTEN internal
$ED0C TALK internal
$EDB9 SECND internal
$EDC7 TKSA internal
$EDDD CIOUT internal
$EE85 ACPTR internal
$EF06 UNTLK internal
$EF23 UNLSN internal

I/O:
$F13E GETIN internal
$F157 CHRIN internal
$F1CA CHROUT internal
$F20E CHKIN internal
$F250 CHKOUT internal
$F291 CLOSE internal
$F32F CLALL internal
$F333 CLRCHN internal
$F34A OPEN internal
$F4A5 LOAD internal
$F5ED SAVE internal
$F6ED STOP internal

SYSTEM:
$FD15 RESTOR internal
$FD1A VECTOR internal
$FD50 RAMTAS internal
$FDA3 IOINIT internal
$FE47 NMI default
$FE66 BRK default
$FEBC IRQ entry
$FF48 IRQ return
```

---

# Interpretation cautions

1. **Use the jump table when identifying documented APIs.** A call to `$FFD2` is unambiguously KERNAL CHROUT; a call to `$F1CA` is an internal implementation entry and may intentionally bypass vectoring.

2. **Direct internal calls can bypass hooks.** Software calling `$F1CA` instead of `$FFD2` may be deliberately bypassing the RAM CHROUT vector at `$0326/$0327`.

3. **Screen I/O is stateful.** KERNAL editor routines depend heavily on zero-page cursor, quote, reverse, line-link, and screen-pointer variables.

4. **IEC internals are timing-sensitive.** Exact bit-level behavior depends on CIA2 and device handshakes.

5. **Custom IRQ code may chain at several points.** `$EA31`, `$EA7E`, and `$EA81` have materially different effects.

6. **Cassette routines reuse substantial RAM.** The cassette buffer and several zero-page variables may be overwritten during tape operations.

7. **BASIC statement code lives here too.** Do not label `$E168` simply `KERNAL_LOAD`; the documented KERNAL LOAD API is `$FFD5`, while `$E168` is BASIC's LOAD statement implementation.

8. **ROM revision can matter for internal addresses.** This reference targets the standard C64 KERNAL layout associated with the common 901227-series ROM, especially revision 3. Public jump-table addresses are far more stable than internal entry points.

---

# Source

Michael Steil, **C64 BASIC & KERNAL ROM Disassembly**:
https://www.pagetable.com/c64ref/c64disasm/

The source page identifies its side-by-side commentary sources, including the original Microsoft BASIC / Commodore KERNAL source and Lee Davison's commented C64 ROM disassembly. citeturn906287view0

This file intentionally condenses those sources into high-value symbols and semantic summaries for reverse engineering rather than reproducing line-by-line commentary.
