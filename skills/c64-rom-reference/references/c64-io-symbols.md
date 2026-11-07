# C64 I/O Symbols and Memory-Mapped Hardware

Reference for 6502 disassembly of Commodore 64 software.

Primary construction source:

- Esshahn, `mem64.json`, pinned at commit `e7e3ec46ce1092a231a72d47fb60ab39c3804dc1`: https://github.com/Esshahn/mem64/blob/e7e3ec46ce1092a231a72d47fb60ab39c3804dc1/mem64.json

This table condenses and reorganizes factual register descriptions from that source for disassembly use. See [`SOURCES.md`](SOURCES.md) for provenance and the upstream licensing caveat.

This file focuses on addresses whose meaning comes from C64 hardware rather than BASIC or KERNAL software conventions.

## Critical banking caveat

The CPU address range `$D000-$DFFF` is not always I/O.

What the CPU sees there depends on the 6510 processor port at `$0001`:

- I/O visible: normal configurations with CHAREN set and ROM/RAM banking permitting I/O.
- Character ROM visible: configurations with CHAREN clear and ROM banking enabled.
- RAM visible: configurations that bank out both ROMs/I/O appropriately.

Therefore:

> Do not automatically interpret an access to `$D000-$DFFF` as hardware I/O without considering `$0001` and the program's banking state.

For ordinary C64 programs running with the normal `$0001 = $37` configuration, `$D000-$DFFF` is I/O.

---

# 6510 processor port

| Address | Symbol | Meaning |
|---|---|---|
| `$0000` | `D6510` / `CPU_DDR` | 6510 on-chip processor-port data-direction register |
| `$0001` | `R6510` / `CPU_PORT` | 6510 processor port: memory banking plus datasette signals |

## `$0001` important bits

| Bit | Name / role |
|---|---|
| 0 | LORAM |
| 1 | HIRAM |
| 2 | CHAREN |
| 3 | Datasette write/output |
| 4 | Datasette switch sense |
| 5 | Datasette motor control |

Bits 0-2 determine whether RAM, BASIC ROM, KERNAL ROM, character ROM, or I/O are visible in the banked regions.

---

# VIC-II — `$D000-$D3FF`

The VIC-II's 64-byte register window begins at `$D000`. It is mirrored repeatedly through `$D3FF`.

## Sprite coordinates

| Address | Symbol | Meaning |
|---|---|---|
| `$D000` | `SP0X` | Sprite 0 X low 8 bits |
| `$D001` | `SP0Y` | Sprite 0 Y |
| `$D002` | `SP1X` | Sprite 1 X low 8 bits |
| `$D003` | `SP1Y` | Sprite 1 Y |
| `$D004` | `SP2X` | Sprite 2 X low 8 bits |
| `$D005` | `SP2Y` | Sprite 2 Y |
| `$D006` | `SP3X` | Sprite 3 X low 8 bits |
| `$D007` | `SP3Y` | Sprite 3 Y |
| `$D008` | `SP4X` | Sprite 4 X low 8 bits |
| `$D009` | `SP4Y` | Sprite 4 Y |
| `$D00A` | `SP5X` | Sprite 5 X low 8 bits |
| `$D00B` | `SP5Y` | Sprite 5 Y |
| `$D00C` | `SP6X` | Sprite 6 X low 8 bits |
| `$D00D` | `SP6Y` | Sprite 6 Y |
| `$D00E` | `SP7X` | Sprite 7 X low 8 bits |
| `$D00F` | `SP7Y` | Sprite 7 Y |
| `$D010` | `MSIGX` / `SPXMSB` | Bit 8 of sprite X coordinates; bit n corresponds to sprite n |

## VIC control and raster

| Address | Symbol | Meaning / important bits |
|---|---|---|
| `$D011` | `SCROLY` / `CTRL1` | VIC control register 1: vertical scroll, 24/25 rows, screen enable, bitmap mode, extended-color mode, raster bit 8 |
| `$D012` | `RASTER` | Raster counter low 8 bits; raster IRQ compare low byte when written |
| `$D013` | `LPENX` | Light-pen X |
| `$D014` | `LPENY` | Light-pen Y |
| `$D015` | `SPENA` | Sprite enable bits |
| `$D016` | `SCROLX` / `CTRL2` | VIC control register 2: horizontal scroll, 38/40 columns, multicolor mode |
| `$D017` | `YXPAND` | Sprite Y expansion |
| `$D018` | `VMCSB` / `MEMPTR` | Screen/character/bitmap memory pointers within current VIC bank |
| `$D019` | `VICIRQ` / `IRQFLAG` | VIC interrupt flags / acknowledge |
| `$D01A` | `IRQMSK` | VIC interrupt enable mask |
| `$D01B` | `SPBGPR` | Sprite/background priority |
| `$D01C` | `SPMC` | Sprite multicolor enable |
| `$D01D` | `XXPAND` | Sprite X expansion |
| `$D01E` | `SPSPCL` | Sprite/sprite collision latch |
| `$D01F` | `SPBGCL` | Sprite/background collision latch |

### `$D011` high-value bits

| Bit | Meaning |
|---|---|
| 0-2 | Vertical fine scroll |
| 3 | 24/25-row select |
| 4 | DEN: display enable |
| 5 | BMM: bitmap mode |
| 6 | ECM: extended-color mode |
| 7 | Raster compare bit 8 / raster counter bit 8 |

### `$D016` high-value bits

| Bit | Meaning |
|---|---|
| 0-2 | Horizontal fine scroll |
| 3 | 38/40-column select |
| 4 | MCM: multicolor mode |

### `$D018` memory pointers

For a selected 16 KiB VIC bank:

- Bits 4-7 select screen memory in 1 KiB increments.
- Bits 1-3 select character memory in 2 KiB increments in character modes.
- In bitmap mode, bit 3 participates in bitmap placement.

Always combine `$D018` with CIA #2 `$DD00` bits 0-1 to determine the actual VIC-visible address.

## VIC colors

| Address | Symbol | Meaning |
|---|---|---|
| `$D020` | `EXTCOL` / `BORDERCOLOR` | Border color |
| `$D021` | `BGCOL0` | Background color 0 |
| `$D022` | `BGCOL1` | Extra/background color 1 |
| `$D023` | `BGCOL2` | Extra/background color 2 |
| `$D024` | `BGCOL3` | Extra/background color 3 |
| `$D025` | `SPMC0` | Sprite shared multicolor 0 |
| `$D026` | `SPMC1` | Sprite shared multicolor 1 |
| `$D027` | `SP0COL` | Sprite 0 color |
| `$D028` | `SP1COL` | Sprite 1 color |
| `$D029` | `SP2COL` | Sprite 2 color |
| `$D02A` | `SP3COL` | Sprite 3 color |
| `$D02B` | `SP4COL` | Sprite 4 color |
| `$D02C` | `SP5COL` | Sprite 5 color |
| `$D02D` | `SP6COL` | Sprite 6 color |
| `$D02E` | `SP7COL` | Sprite 7 color |

`$D02F-$D03F` are not useful normal VIC-II registers on the standard C64.

`$D040-$D3FF` contains mirrors of the VIC register block every `$40` bytes.

---

# SID — `$D400-$D7FF`

The SID register set begins at `$D400` and is mirrored every `$20` bytes through `$D7FF`.

## Voice 1

| Address | Symbol | Meaning |
|---|---|---|
| `$D400` | `FRELO1` | Voice 1 frequency low |
| `$D401` | `FREHI1` | Voice 1 frequency high |
| `$D402` | `PWLO1` | Voice 1 pulse-width low |
| `$D403` | `PWHI1` | Voice 1 pulse-width high nibble |
| `$D404` | `VCREG1` | Voice 1 control |
| `$D405` | `ATDCY1` | Voice 1 attack/decay |
| `$D406` | `SUREL1` | Voice 1 sustain/release |

## Voice 2

| Address | Symbol | Meaning |
|---|---|---|
| `$D407` | `FRELO2` | Voice 2 frequency low |
| `$D408` | `FREHI2` | Voice 2 frequency high |
| `$D409` | `PWLO2` | Voice 2 pulse-width low |
| `$D40A` | `PWHI2` | Voice 2 pulse-width high nibble |
| `$D40B` | `VCREG2` | Voice 2 control |
| `$D40C` | `ATDCY2` | Voice 2 attack/decay |
| `$D40D` | `SUREL2` | Voice 2 sustain/release |

## Voice 3

| Address | Symbol | Meaning |
|---|---|---|
| `$D40E` | `FRELO3` | Voice 3 frequency low |
| `$D40F` | `FREHI3` | Voice 3 frequency high |
| `$D410` | `PWLO3` | Voice 3 pulse-width low |
| `$D411` | `PWHI3` | Voice 3 pulse-width high nibble |
| `$D412` | `VCREG3` | Voice 3 control |
| `$D413` | `ATDCY3` | Voice 3 attack/decay |
| `$D414` | `SUREL3` | Voice 3 sustain/release |

## Filter / global SID control

| Address | Symbol | Meaning |
|---|---|---|
| `$D415` | `CUTLO` | Filter cutoff low bits |
| `$D416` | `CUTHI` | Filter cutoff high byte |
| `$D417` | `RESON` | Filter resonance and voice routing |
| `$D418` | `SIGVOL` | Filter mode, voice-3 disconnect, master volume |

## SID read registers

| Address | Symbol | Meaning |
|---|---|---|
| `$D419` | `POTX` | Paddle X |
| `$D41A` | `POTY` | Paddle Y |
| `$D41B` | `RANDOM` / `OSC3` | Voice 3 oscillator output; often read as a pseudo-random/noise source when voice 3 uses noise |
| `$D41C` | `ENV3` | Voice 3 envelope output |

`$D41D-$D41F` are unused on the original SID.

## Voice control bits (`$D404/$D40B/$D412`)

| Bit | Meaning |
|---|---|
| 0 | Gate |
| 1 | Sync |
| 2 | Ring modulation |
| 3 | Test |
| 4 | Triangle |
| 5 | Sawtooth |
| 6 | Pulse |
| 7 | Noise |

### Disassembly caution

A read from `$D41B` often participates in randomization, but do not automatically call every such read a complete PRNG. The result depends on voice-3 oscillator configuration.

---

# Color RAM — `$D800-$DBFF`

| Address range | Symbol | Meaning |
|---|---|---|
| `$D800-$DBE7` | `COLOR_RAM` | 1000 screen-cell color nybbles |
| `$DBE8-$DBFF` | — | Remaining physical color RAM / normally outside the 40×25 screen area |

Only the low four bits are meaningful.

A write to `$D800 + offset` usually changes the foreground color of the corresponding character cell in standard text modes, but screen layout/mode must be considered.

---

# CIA #1 — `$DC00-$DCFF`

CIA #1 primarily handles keyboard, joysticks, paddles, timers, TOD clock, and maskable IRQ generation.

Its 16 registers are mirrored every `$10` bytes through `$DCFF`.

| Address | Symbol | Meaning |
|---|---|---|
| `$DC00` | `CIAPRA` / `CIA1_PRA` | Port A: keyboard matrix columns, joystick port 2, paddle selection |
| `$DC01` | `CIAPRB` / `CIA1_PRB` | Port B: keyboard matrix rows, joystick port 1 |
| `$DC02` | `CIDDRA` / `CIA1_DDRA` | Port A DDR |
| `$DC03` | `CIDDRB` / `CIA1_DDRB` | Port B DDR |
| `$DC04` | `TIMALO` / `CIA1_TALO` | Timer A low |
| `$DC05` | `TIMAHI` / `CIA1_TAHI` | Timer A high |
| `$DC06` | `TIMBLO` / `CIA1_TBLO` | Timer B low |
| `$DC07` | `TIMBHI` / `CIA1_TBHI` | Timer B high |
| `$DC08` | `TODTEN` | TOD tenths |
| `$DC09` | `TODSEC` | TOD seconds |
| `$DC0A` | `TODMIN` | TOD minutes |
| `$DC0B` | `TODHRS` | TOD hours |
| `$DC0C` | `CIASDR` / `CIA1_SDR` | Serial data register |
| `$DC0D` | `CIAICR` / `CIA1_ICR` | Interrupt control/status |
| `$DC0E` | `CIACRA` / `CIA1_CRA` | Timer A control |
| `$DC0F` | `CIACRB` / `CIA1_CRB` | Timer B / TOD alarm control |

## Joystick bits

On `$DC00`, bits 0-4 are joystick port 2:

- bit 0: up
- bit 1: down
- bit 2: left
- bit 3: right
- bit 4: fire

On `$DC01`, bits 0-4 similarly represent joystick port 1.

Inputs are active-low.

## Keyboard scanning

Normal keyboard scanning drives selected columns through CIA1 port A and reads rows through port B.

Do not interpret every access to `$DC00/$DC01` as keyboard activity: games often read joystick ports directly through the same registers.

---

# CIA #2 — `$DD00-$DDFF`

CIA #2 primarily handles the VIC bank, IEC serial bus, RS-232/user-port lines, timers/TOD, and NMI generation.

Its 16 registers are mirrored every `$10` bytes through `$DDFF`.

| Address | Symbol | Meaning |
|---|---|---|
| `$DD00` | `CI2PRA` / `CIA2_PRA` | Port A: VIC bank, IEC serial bus, RS-232 TXD |
| `$DD01` | `CI2PRB` / `CIA2_PRB` | Port B: RS-232/user port |
| `$DD02` | `C2DDRA` / `CIA2_DDRA` | Port A DDR |
| `$DD03` | `C2DDRB` / `CIA2_DDRB` | Port B DDR |
| `$DD04` | `TI2ALO` / `CIA2_TALO` | Timer A low |
| `$DD05` | `TI2AHI` / `CIA2_TAHI` | Timer A high |
| `$DD06` | `TI2BLO` / `CIA2_TBLO` | Timer B low |
| `$DD07` | `TI2BHI` / `CIA2_TBHI` | Timer B high |
| `$DD08` | `TO2TEN` | TOD tenths |
| `$DD09` | `TO2SEC` | TOD seconds |
| `$DD0A` | `TO2MIN` | TOD minutes |
| `$DD0B` | `TO2HRS` | TOD hours |
| `$DD0C` | `CI2SDR` / `CIA2_SDR` | Serial data register |
| `$DD0D` | `CI2ICR` / `CIA2_ICR` | NMI interrupt control/status |
| `$DD0E` | `CI2CRA` / `CIA2_CRA` | Timer A control |
| `$DD0F` | `CI2CRB` / `CIA2_CRB` | Timer B / TOD alarm control |

## `$DD00` VIC-bank selection

Bits 0-1 select the VIC-II's 16 KiB bank, inverted:

| `$DD00 & 3` | VIC-visible bank |
|---|---|
| `%11` / 3 | `$0000-$3FFF` |
| `%10` / 2 | `$4000-$7FFF` |
| `%01` / 1 | `$8000-$BFFF` |
| `%00` / 0 | `$C000-$FFFF` |

The actual VIC screen/character/bitmap address requires both `$DD00` and `$D018`.

## `$DD00` IEC bits

| Bit | Meaning |
|---|---|
| 3 | ATN OUT |
| 4 | CLOCK OUT |
| 5 | DATA OUT |
| 6 | CLOCK IN |
| 7 | DATA IN |

IEC output logic is electrically inverted relative to the logical line state; analyze surrounding code carefully, especially in fastloaders.

---

# Expansion I/O — `$DE00-$DFFF`

| Range | Conventional name | Meaning |
|---|---|---|
| `$DE00-$DEFF` | `IO1` | Cartridge / expansion I/O 1 |
| `$DF00-$DFFF` | `IO2` | Cartridge / expansion I/O 2 |

There is no universal per-register meaning in these ranges.

Interpret accesses according to the attached cartridge/hardware or emulator configuration.

Common uses include:

- cartridge bank switching,
- freezer cartridges,
- REU/ram expansion control,
- networking/storage peripherals,
- custom hardware.

Do not assign semantics to `$DE00` or `$DF00` without identifying the device.

---

# High-value disassembly symbols

```text
$0000  CPU_DDR       6510 processor-port DDR
$0001  CPU_PORT      banking + datasette control

$D011  CTRL1         VIC mode / vertical scroll / raster bit 8
$D012  RASTER        VIC raster
$D016  CTRL2         VIC multicolor / horizontal scroll
$D018  MEMPTR        VIC screen/charset/bitmap pointers
$D019  VIC_IRQ       VIC interrupt flags
$D01A  VIC_IRQ_MASK  VIC interrupt enable
$D020  BORDER
$D021  BACKGROUND

$D400  SID_V1_FREQ
$D404  SID_V1_CTRL
$D407  SID_V2_FREQ
$D40B  SID_V2_CTRL
$D40E  SID_V3_FREQ
$D412  SID_V3_CTRL
$D418  SID_MODE_VOL
$D41B  SID_OSC3
$D41C  SID_ENV3

$D800  COLOR_RAM

$DC00  CIA1_PRA      keyboard / joystick 2
$DC01  CIA1_PRB      keyboard / joystick 1
$DC04  CIA1_TIMER_A
$DC0D  CIA1_ICR
$DC0E  CIA1_CRA
$DC0F  CIA1_CRB

$DD00  CIA2_PRA      VIC bank + IEC
$DD01  CIA2_PRB      RS-232 / user port
$DD0D  CIA2_ICR      NMI source/control
$DD0E  CIA2_CRA
$DD0F  CIA2_CRB

$DE00  IO1
$DF00  IO2
```

---

# Interpretation cautions for AI-assisted disassembly

1. **Check banking before interpreting `$D000-$DFFF`.** The same CPU address may be I/O, character ROM, or RAM.

2. **Hardware register names are not explanations.** Prefer `; enable bitmap mode` over merely `; write VIC CTRL1` when the written bits establish a clear purpose.

3. **Read-modify-write instructions on I/O require care.** Some device registers have read side effects, write-one-to-clear bits, or values on read that differ from the last value written.

4. **CIA interrupt-control registers are asymmetric.** Reading and writing `$DC0D/$DD0D` have different semantics. On writes, bit 7 selects set-vs-clear behavior for interrupt-mask bits.

5. **VIC IRQ acknowledgement is normally by writing set bits back to `$D019`.** Do not interpret this as ordinary state storage.

6. **Sprite coordinates use `$D010` for their ninth X bit.** A routine changing both `$D000+2*n` and `$D010` is probably manipulating a full 9-bit sprite X coordinate.

7. **`$D41B` can be used as an entropy/random source**, but only in conjunction with suitable voice-3 oscillator configuration.

8. **Color RAM contains nybbles, not normal 8-bit RAM.**

9. **`$DE00-$DFFF` is device-specific.** Identify the expansion device before naming registers.

10. **Mirrors may be intentional.** Code sometimes accesses mirrored VIC/SID/CIA addresses; do not automatically normalize them away if the exact bus address may matter.

---

# Source

Esshahn, `mem64.json`:
https://github.com/Esshahn/mem64/blob/master/mem64.json

The source data has been condensed and reorganized for use during 6502 disassembly.
