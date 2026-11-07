# Commodore 1541 Symbols and Memory Map

Reference for 6502 disassembly of the Commodore 1541 disk drive.

Primary construction source:

- Joe Forster/STA 1541 memory map, mirrored by Herwig Siebenhofer: https://riff.2ix.at/c64/?dok=1541mem (accessed 2026-08-31)

Supplementary symbol names and interpretations were checked against documented 1541 ROM disassemblies and the pinned ROM identified in [`rom-manifest.md`](rom-manifest.md). This table condenses and reorganizes those factual descriptions for disassembly use. See [`SOURCES.md`](SOURCES.md) for provenance and the upstream licensing caveat.

This file is intended as an **analysis reference**, not as a claim that every RAM location has one immutable meaning in every ROM routine.

## Disassembly guidance

- The 1541 contains its own 6502-family CPU and **2 KiB RAM at `$0000-$07FF`**.
- `$0300-$07FF` are the five standard 256-byte sector/data buffers.
- `$1800-$180F` is VIA #1, primarily the IEC serial-bus interface.
- `$1C00-$1C0F` is VIA #2, primarily disk mechanism / read-write control.
- Standard DOS ROM occupies `$C000-$FFFF`; `$C000-$C0FF` is normally unused in the common 1541 ROM.
- Do not infer semantics from an address name alone. Many zero-page and page-2 locations are reused as temporary workspace by different routines.
- In custom fastloaders or copy-protection code, RAM, buffers, VIA registers, timers, and even normal DOS conventions may be repurposed.
- When analyzing code uploaded to and executed inside the drive, treat accesses to `$0300-$07FF` as application RAM unless runtime evidence shows normal DOS buffer use.
- Prefer established ROM/RAM labels where known. When a location's purpose is uncertain, retain the numeric address or use a neutral temporary label rather than inventing semantics.

---

# RAM: `$0000-$07FF`

## Job queue and disk-controller state: `$0000-$006F`

| Address | Suggested symbol | Meaning / disassembly notes |
|---|---|---|
| `$0000` | `JOBS+0` | Job code for buffer 0 (`$0300`). |
| `$0001` | `JOBS+1` | Job code for buffer 1 (`$0400`). |
| `$0002` | `JOBS+2` | Job code for buffer 2 (`$0500`). |
| `$0003` | `JOBS+3` | Job code for buffer 3 (`$0600`). |
| `$0004` | `JOBS+4` | Job code for buffer 4 (`$0700`). |
| `$0005` | `JOBS+5` | Job code for buffer 5; no normal 1541 RAM buffer exists for it. |
| `$0006-$0007` | `HDRS+0` | Track, sector for job/buffer 0. |
| `$0008-$0009` | `HDRS+2` | Track, sector for job/buffer 1. |
| `$000A-$000B` | `HDRS+4` | Track, sector for job/buffer 2. |
| `$000C-$000D` | `HDRS+6` | Track, sector for job/buffer 3. |
| `$000E-$000F` | `HDRS+8` | Track, sector for job/buffer 4. |
| `$0010-$0011` | `HDRS+10` | Track, sector for job/buffer 5. |
| `$0012-$0013` | `DSKID` | Master disk ID for drive 0. |
| `$0014-$0015` | — | Drive-1 disk ID storage; unused on a normal single-drive 1541. |
| `$0016-$001A` | `HEADER` | Image of most recently read disk header: ID1, ID2, track, sector, checksum/parity. |
| `$001B` | `ACTJOB` | Disk-controller work / historically described as active-job storage; effectively unused in normal DOS use. |
| `$001C` | `WPSW` | Write-protect/disk-change status flag, drive 0. |
| `$001D` | — | Corresponding drive-1 flag; unused on 1541. |
| `$001E` | `LWPT` | Last sensed write-protect state, drive 0. |
| `$001F` | — | Corresponding drive-1 value; unused on 1541. |
| `$0020` | `DRVST` | Drive status: disk readiness, head movement, motor state. |
| `$0021` | — | Drive-1 status; unused on 1541. |
| `$0022` | `DRVTRK` | Current physical track / track under the read-write head. |
| `$0023` | — | 1541/1540 flag: `0` on 1541, nonzero on 1540. |
| `$0024-$002D` | — | Scratch workspace used during GCR / binary conversion. |
| `$002E-$002F` | — | Temporary-storage pointer. |
| `$0030-$0031` | — | Buffer pointer used by disk controller. |
| `$0032` | `TRACK`-related | Active/current track workspace. Do not confuse blindly with `$0080`; verify routine context. |
| `$0033` | `SECTOR`-related | Active/current sector workspace. Verify routine context. |
| `$0034` | — | Pointer/index to last converted byte. |
| `$0035` | — | GCR/decode-error workspace; described as unused in normal flow. |
| `$0036` | — | Byte counter for GCR/BIN conversion. |
| `$0037` | — | Bit-counter workspace; normally unused. |
| `$0038` | — | Constant `$07`, normal data-block ID mark. |
| `$0039` | — | Constant `$08`, normal header-block ID mark. |
| `$003A` | — | Parity/checksum for data buffer. |
| `$003B-$003C` | — | Disk-controller temporary workspace / not directly used. |
| `$003D` | — | Motor/drive flag; drive number, normally `$00` on 1541. |
| `$003E` | — | Active-drive flag; `$FF` when no drive active. |
| `$003F` | — | Buffer/job number for disk controller; previous queue position. |
| `$0040` | — | Byte counter for GCR conversion. |
| `$0041` | — | Next job/work item in queue (`0-5`). |
| `$0042` | — | Destination track for head movement. |
| `$0043` | — | Sectors-per-track value used during formatting. |
| `$0044` | — | Temporary scratch byte. |
| `$0045` | — | Temporary job/work-code storage. |
| `$0046` | — | Unused/reserved. |
| `$0047` | — | Data-block ID character; normally `$07`. Altering it can create nonstandard block IDs. |
| `$0048` | — | Head-motion acceleration/timing counter. |
| `$0049` | — | Temporary stack-pointer storage. |
| `$004A` | — | Head step counter/direction workspace. Values below `$80` and above/equal `$80` encode opposite directions. |
| `$004B` | — | Temporary storage. |
| `$004C` | — | Last-read sector. |
| `$004D` | — | Next sector. |
| `$004E-$004F` | — | Pointer to buffer for GCR-to-binary conversion. |
| `$0050` | — | Format flag: `0` = binary, `1` = GCR. |
| `$0051` | — | Current track while formatting. |
| `$0052-$0055` | — | Four binary bytes being encoded to GCR. |
| `$0056-$005D` | — | Five GCR bytes corresponding to a 4-byte binary group. |
| `$005E` | — | Head-motor acceleration/deceleration step count. |
| `$005F` | — | Acceleration/deceleration factor. |
| `$0060-$0061` | — | Temporary/controller workspace; confirm by ROM context. |
| `$0062-$0063` | — | Pointer to head-movement routine; normally points near `$FA05`. |
| `$0064` | — | Minimum number of head steps. |
| `$0065-$0066` | `UI` vector | User-interface / serial-related vector; commonly initialized near `$EB22`. |
| `$0067` | — | NMI flag. |
| `$0068` | — | Disk initialization flag. Controls automatic initialization after ID mismatch. |
| `$0069` | — | Sector interleave / sector-division step; normal SEQ interleave is `$0A`. |
| `$006A` | — | Number of disk read attempts; normally `5`. |
| `$006B-$006C` | — | Pointer to start of U-command jump table, normally `$FFEA`. |
| `$006D-$006E` | — | Pointer to bitmap/BAM workspace, normally `$0400` in relevant routines. |
| `$006F-$0070` | — | Address pointer used by memory/block commands. |

### Job queue codes

The high nibble of a job byte in `$0000-$0005` identifies the requested disk-controller operation.

| Job code | Meaning |
|---|---|
| `$80` | Read sector |
| `$90` | Write sector |
| `$A0` | Verify sector |
| `$B0` | Seek |
| `$C0` | Bump head toward track 1 |
| `$D0` | Jump to machine code in a buffer |
| `$E0` | Execute code in buffer after drive is ready/up to speed |

After completion, the controller replaces the job with a status/error code. Common results include:

| Result | Meaning |
|---|---|
| `$01` | Job completed successfully |
| `$02` | Header block not found |
| `$03` | SYNC not found |
| `$04` | Data block not found |
| `$05` | Data-block checksum error |
| `$07` | Verify-after-write error |
| `$08` | Write-protect error |
| `$09` | Header checksum error |
| `$0A` | Data block too long |
| `$0B` | Disk ID mismatch |
| `$10` | GCR/byte decoding error |

---

## Interface processor / DOS zero page: `$0071-$00FF`

| Address | Suggested symbol | Meaning / disassembly notes |
|---|---|---|
| `$0071-$0074` | — | General temporary workspace. |
| `$0075-$0076` | — | Indirect pointer, often initialized to `$0100`. |
| `$0077` | — | IEC listener address = device number + `$20`; normally `$28` for device 8. |
| `$0078` | — | IEC talker address = device number + `$40`; normally `$48` for device 8. |
| `$0079` | — | Active-listener flag. |
| `$007A` | — | Active-talker flag. |
| `$007B` | — | Undocumented / context-dependent workspace. |
| `$007C` | — | ATN-received flag. |
| `$007D` | — | ATN-active flag. |
| `$007E` | — | Last handled program/command state. |
| `$007F` | — | Drive number; normally `0` on 1541. |
| `$0080` | `TRACK` | Current/requested logical track number used widely by DOS routines. |
| `$0081` | `SECTOR` | Current/requested logical sector number. |
| `$0082` | — | Channel number / logical index. |
| `$0083` | — | Secondary address. |
| `$0084` | — | Original secondary address. |
| `$0085` | — | Current data byte. |
| `$0086-$008A` | — | Temporary results/workspace. |
| `$008B-$008E` | — | Multiply/divide workspace and result storage. |
| `$008F-$0093` | — | Undocumented/context-dependent workspace. |
| `$0094-$0095` | — | Pointer to current directory buffer, commonly near `$0204`. |
| `$0096-$0098` | — | Undocumented/context-dependent workspace. |
| `$0099-$009A` | — | Pointer to next byte in buffer 0; normally `$0300`. |
| `$009B-$009C` | — | Pointer to next byte in buffer 1; normally `$0400`. |
| `$009D-$009E` | — | Pointer to next byte in buffer 2; normally `$0500`. |
| `$009F-$00A0` | — | Pointer to next byte in buffer 3; normally `$0600`. |
| `$00A1-$00A2` | — | Pointer to next byte in buffer 4; normally `$0700`. |
| `$00A3-$00A4` | — | Pointer to next byte in command buffer; normally `$0200`. |
| `$00A5-$00A6` | — | Pointer to next byte in error-message buffer; normally near `$02D5/$02D6`. |
| `$00A7-$00AD` | — | Per-buffer table of inactive/non-active channel numbers. |
| `$00AE-$00B4` | — | Per-buffer table; exact use depends on DOS context. |
| `$00B5-$00BA` | — | REL-file record/block low-byte table. |
| `$00BB-$00C0` | — | REL-file record/block high-byte table. |
| `$00C1-$00C6` | — | REL-file write pointers / next-record table. |
| `$00C7-$00CC` | — | REL-file record-length table. |
| `$00CD-$00D2` | — | REL-file side-sector table. |
| `$00D3` | — | Undocumented/context-dependent. |
| `$00D4` | `RECPTR` | Pointer/index within REL record. |
| `$00D5` | `SSNUM` | REL side-sector number. |
| `$00D6` | `SSIND` | Index/pointer into REL side-sector data. |
| `$00D7` | `RELPTR` | REL-file pointer. |
| `$00D8-$00DC` | — | Directory-sector table. |
| `$00DD-$00E1` | — | Directory-index table. |
| `$00E2-$00E6` | — | Default-drive table; all normally zero on 1541. |
| `$00E7-$00EB` | — | Filename/pattern type flags: wildcard, replace (`@`), closed-state, etc. |
| `$00EC-$00F1` | — | Per-channel file type. |
| `$00F2-$00F7` | — | Per-channel status/readiness. |
| `$00F8` | `EOIFLG` | Temporary EOI flag. |
| `$00F9` | `JOBNUM` | Current job/buffer number. |
| `$00FA-$00FE` | `LRUTBL` | Least-recently-used / last-used buffer table. |
| `$00FF` | `NODRV+0` | Drive-0 not-ready flag: `$FF` = no disk/not ready, `$00` = ready. |

---

## Stack / drive-state page: `$0100-$01FF`

| Address | Suggested symbol | Meaning / disassembly notes |
|---|---|---|
| `$0100` | `NODRV+1` | Drive-1 not-ready flag; drive 1 does not exist on normal 1541. |
| `$0101` | `DSKVER+0` | DOS/format version byte for drive 0, read from track 18 sector 0. |
| `$0102` | `DSKVER+1` | Drive-1 counterpart; unused on standard 1541. |
| `$0103` | `ZPEND` | Unused/reserved. |
| `$0104-$01FF` | — | CPU stack area in normal DOS operation. Some routines also use portions as scratch/buffer space. |
| near `$0146` | — | Documented as unofficial/context-dependent use. |
| near `$01BA` | — | Temporary GCR-code buffer/work area. |

Do not assume all of page 1 is untouched except for stack pushes/pulls; 1541 DOS routines may use known portions as explicit scratch space.

---

# Page 2: command parser, channels, BAM, directory state

## Command and channel state: `$0200-$0279`

| Address | Suggested symbol | Meaning / disassembly notes |
|---|---|---|
| `$0200-$0229` | `CMDBUF` | Command string received from host, e.g. DOS commands and filenames. |
| `$022A` | — | Parsed command code. |
| `$022B-$022D` | `LINDX` | Logical-index/channel status array. |
| `$022E-$0243` | — | Last byte read/written for channels. |
| `$0244-$0249` | — | Per-channel pointer/index to last character in buffer. |
| `$024A` | — | Type of active file. |
| `$024B` | — | String length. |
| `$024C` | — | Temporary channel / secondary-address value. |
| `$024D` | `CMD` | Current disk-controller command/job workspace. |
| `$024E` | — | Workspace used when finding/selecting best sector. |
| `$024F-$0250` | — | Buffer-allocation state. |
| `$0251` | — | BAM-changed flag, drive 0. |
| `$0252` | — | BAM-changed flag, drive 1. |
| `$0253` | — | Directory-entry-found flag: `$FF` = not found, `$00` = found. |
| `$0254` | — | Directory-output flag. |
| `$0255` | — | Waiting-for-command flag. |
| `$0256` | — | Undocumented/context-dependent. |
| `$0257` | — | Last-used buffer. |
| `$0258` | — | REL record length. |
| `$0259` | — | REL side-sector track. |
| `$025A` | — | REL side-sector sector. |
| `$025B-$025F` | `LSTJOB` | Previous/last job associated with each buffer. |
| `$0260-$0265` | — | Directory-sector table for buffers/channels. |
| `$0266-$026B` | — | File index within directory, per buffer/channel. |
| `$026C` | — | Error-LED flash counter. |
| `$026D` | — | Error-LED state. |
| `$026E` | — | Drive number for last program/operation. |
| `$026F` | — | Sector for last program/operation. |
| `$0270` | — | Write logical index (`LINDX`). |
| `$0271` | — | Read logical index (`LINDX`). |
| `$0272-$0273` | — | Temporary block count. |
| `$0274` | — | Input-line length. |
| `$0275` | — | Character currently being interpreted. |
| `$0276` | — | Index of end of filename in command buffer. |
| `$0277` | — | Undocumented/context-dependent. |
| `$0278` | — | Number of filenames in command. |
| `$0279` | — | Undocumented/context-dependent. |

### LINDX status values

Common values in the logical-index/channel table:

| Value | Meaning |
|---|---|
| `$FF` | Inactive |
| `$81` | Open for writing |
| `$41` | Read/write |
| `$01` | Open for reading |

---

## Filename, directory and BAM state: `$027A-$02FF`

| Address | Suggested symbol | Meaning / disassembly notes |
|---|---|---|
| `$027A-$027F` | — | Pointer table for filenames. |
| `$0280-$0284` | — | File track table. |
| `$0285-$0289` | — | File sector table. |
| `$028A` | — | Wildcard flag. |
| `$028B` | — | Context-dependent/reserved. |
| `$028C` | — | Number of drives to search/use; legacy dual-drive DOS ancestry may be visible here. |
| `$028D` | — | Looking-for-drive flag. |
| `$028E` | — | Drive from last write/open error; used as default drive. |
| `$028F` | — | Found-in-directory flag. |
| `$0290` | — | Current directory sector. |
| `$0291` | — | Sector for first available/free directory/file entry. |
| `$0292` | — | Index within directory for first available entry. |
| `$0293` | — | Last-directory-entry marker/workspace; normally zero in relevant state. |
| `$0294` | — | Current buffer index. |
| `$0295` | — | File counter. |
| `$0296` | — | Filename wildcard-match flag. |
| `$0297` | — | Active operating mode (`R`/`W`). |
| `$0298` | — | Work-return/status flag. |
| `$0299` | — | Re-read-error pointer/index. |
| `$029A` | — | Total track count / maximum-track workspace. |
| `$029B-$029C` | — | Pointer/state for last BAM update. |
| `$029D-$02A0` | — | BAM image-sector state / drive-related pointers. |
| `$02A1-$02B0` | — | BAM image/workspace. |
| `$02B1-$02D4` | — | Directory-output buffer. |
| `$02D5-$02F8` | — | Error-message buffer. |
| `$02F9` | — | Suppress-BAM-write flag; normally reset before/after each command. |
| `$02FA-$02FB` | — | Free-block count low byte for drives 0/1. |
| `$02FC-$02FD` | — | Free-block count high byte for drives 0/1. |
| `$02FE-$02FF` | — | Stepper-motor sequence table/state. |

---

# Standard 256-byte data buffers

| Address | Suggested symbol | Meaning |
|---|---|---|
| `$0300-$03FF` | `BUFFER0` | Data buffer 0 |
| `$0400-$04FF` | `BUFFER1` | Data buffer 1 |
| `$0500-$05FF` | `BUFFER2` | Data buffer 2 |
| `$0600-$06FF` | `BUFFER3` | Data buffer 3 |
| `$0700-$07FF` | `BUFFER4` | Data buffer 4 |

Additional documented use:

| Address | Meaning |
|---|---|
| `$0621-$0622` | Formatting counter/workspace within buffer 3 |

These are ordinary RAM. Uploaded drive code, fastloaders, copy protection, formatters, and custom DOS routines frequently overwrite or execute from these areas.

A common custom-code pattern is:

```asm
; host uploads machine code into a drive buffer
; then DOS executes or jumps into that buffer
```

Therefore, when disassembling custom 1541 code, never assume bytes in `$0300-$07FF` are sector data merely because they lie in a DOS buffer.

---

# VIA #1 — IEC serial-bus interface

Base address: `$1800`

The 6522 has 16 registers. The 1541 uses VIA #1 primarily for host/IEC communication.

| Address | 6522 register | Meaning |
|---|---|---|
| `$1800` | ORB / IRB | Port B data |
| `$1801` | ORA / IRA | Port A data |
| `$1802` | DDRB | Port B data-direction register |
| `$1803` | DDRA | Port A data-direction register |
| `$1804` | T1C-L | Timer 1 counter low |
| `$1805` | T1C-H | Timer 1 counter high |
| `$1806` | T1L-L | Timer 1 latch low |
| `$1807` | T1L-H | Timer 1 latch high |
| `$1808` | T2C-L | Timer 2 counter low |
| `$1809` | T2C-H | Timer 2 counter high |
| `$180A` | SR | Shift register |
| `$180B` | ACR | Auxiliary control register |
| `$180C` | PCR | Peripheral control register |
| `$180D` | IFR | Interrupt flag register |
| `$180E` | IER | Interrupt enable register |
| `$180F` | ORA no-handshake | Port A data, no handshake |

## Disassembly note

Accesses to `$1800-$180F` are strong evidence of IEC/serial communication, handshake timing, or VIA timer/interrupt manipulation. Custom fastloaders often manipulate these registers directly and may use protocols very different from standard Commodore serial routines.

---

# VIA #2 — disk mechanism / read-write controller

Base address: `$1C00`

The second 6522 controls the drive mechanism and low-level disk data path.

| Address | 6522 register | Meaning |
|---|---|---|
| `$1C00` | ORB / IRB | Port B data; disk mechanism control/status |
| `$1C01` | ORA / IRA | Port A data; disk data path |
| `$1C02` | DDRB | Port B data-direction register |
| `$1C03` | DDRA | Port A data-direction register |
| `$1C04` | T1C-L | Timer 1 counter low |
| `$1C05` | T1C-H | Timer 1 counter high |
| `$1C06` | T1L-L | Timer 1 latch low |
| `$1C07` | T1L-H | Timer 1 latch high |
| `$1C08` | T2C-L | Timer 2 counter low |
| `$1C09` | T2C-H | Timer 2 counter high |
| `$1C0A` | SR | Shift register |
| `$1C0B` | ACR | Auxiliary control register |
| `$1C0C` | PCR | Peripheral control register |
| `$1C0D` | IFR | Interrupt flag register |
| `$1C0E` | IER | Interrupt enable register |
| `$1C0F` | ORA no-handshake | Port A data, no handshake |

## Disassembly note

Accesses to `$1C00-$1C0F` are strong evidence of low-level disk activity such as:

- spindle motor control,
- stepper/head movement,
- write-protect sensing,
- byte-ready / disk-data synchronization,
- direct GCR reading or writing,
- VIA timer or interrupt control.

Custom nibblers and copy-protection routines frequently operate directly on VIA #2 instead of using normal DOS sector routines.

---

# ROM layout

For the common Commodore 1541 DOS ROM:

| Address range | Meaning |
|---|---|
| `$C000-$C0FF` | Normally unused ROM area |
| `$C100-$E4FB` | File manager / DOS / interface-processor routines |
| `$E4FC-$F258` | Messages, command-related data and ROM tables |
| `$F259-$FE84` | Low-level floppy disk controller routines |
| `$FE85-$FFE9` | Disk-format constants/tables and related ROM data |
| `$FFEA-$FFFB` | User-command / DOS jump vectors |
| `$FFFC-$FFFF` | 6502 hardware vectors |

The exact boundaries and routines can vary among ROM revisions and compatible drives. Resolve a concrete ROM address against the ROM version being analyzed whenever possible.

---

# User-command vectors: `$FFEA-$FFFB`

The 1541 exposes a small jump/vector area used by DOS "U" commands and related entry points.

When disassembling:

- Treat references through this area as indirect entry points into DOS functionality.
- If custom software patches RAM vectors that eventually feed these entries, follow the runtime target rather than assuming the stock ROM destination.
- Uploaded drive software may bypass this table entirely.

---

# Hardware vectors: `$FFFC-$FFFF`

| Address | Meaning |
|---|---|
| `$FFFC-$FFFD` | RESET vector |
| `$FFFE-$FFFF` | IRQ/BRK vector |

The NMOS 6502 NMI vector is normally at `$FFFA-$FFFB`; on the 1541 this overlaps the upper end of the ROM's vector area and should be interpreted as a hardware vector when fetched by the CPU.

---

# High-value symbols for disassembly

These are especially useful when interpreting unfamiliar 1541 code:

```text
JOBS       $0000   disk-controller job queue
HDRS       $0006   per-job track/sector headers
DSKID      $0012   current/master disk ID
HEADER     $0016   most recently read disk header
WPSW       $001C   write-protect state-change flag
LWPT       $001E   last write-protect state
DRVST      $0020   disk-drive mechanism status
DRVTRK     $0022   physical/current head track

TRACK      $0080   logical/current requested track
SECTOR     $0081   logical/current requested sector
EOIFLG     $00F8   EOI flag
JOBNUM     $00F9   current job/buffer number
LRUTBL     $00FA   buffer recency/usage table
NODRV      $00FF   drive-ready state
DSKVER     $0101   disk DOS/format version

CMDBUF     $0200   command buffer
LINDX      $022B   channel logical-index/status table
CMD        $024D   current disk/job command workspace
LSTJOB     $025B   previous job table

BUFFER0    $0300
BUFFER1    $0400
BUFFER2    $0500
BUFFER3    $0600
BUFFER4    $0700

VIA1       $1800   IEC serial-bus VIA
VIA2       $1C00   disk-controller/mechanism VIA
```

---

# Interpretation cautions for AI-assisted disassembly

1. **Track variables are contextual.** The ROM maintains more than one track/sector-related value. `$0080/$0081` are heavily used logical track/sector variables, while other zero-page locations participate in controller state. Do not merge them automatically.

2. **Many locations retain dual-drive ancestry.** The 1541 DOS descends from Commodore dual-drive DOS designs. Entries labeled "drive 1" may remain in tables despite a standard 1541 having only drive 0.

3. **Page 2 is heavily reused.** Command parsing, channel state, directory operations, BAM handling, REL files, and error reporting overlap temporally. A byte's effective meaning may depend on the active DOS routine.

4. **Buffers are executable RAM.** `$0300-$07FF` are not intrinsically data. Drive-resident utilities and fastloaders commonly execute there.

5. **VIA accesses deserve semantic analysis.** Do not comment `STA $1C00` merely as "write VIA port B." Determine which motor, stepper, density, or disk-control bits are being manipulated if the surrounding code allows it.

6. **Custom loaders may discard DOS conventions.** Once uploaded code takes control, normal zero-page meanings and buffer ownership can change. Prefer runtime observation and local data flow over this reference when they conflict.

7. **ROM revision matters.** Routine addresses inside `$C000-$FFFF` should be matched against the actual 1541 ROM revision before assigning semantic routine names.

---

# Sources

- Joe Forster/STA, **C1541 Floppy Memory Map**, originally at `https://sta.c64.org/cbm1541mem.html`.
- Mirror used for memory-map verification: `https://riff.2ix.at/c64/?dok=1541mem`.
- Supplementary established labels/job-code meanings checked against a commented C1541 ROM disassembly: `https://g3sl.github.io/c1541rom.html`.

This reference intentionally condenses and reorganizes the source material for machine-code analysis rather than reproducing the original page verbatim.
