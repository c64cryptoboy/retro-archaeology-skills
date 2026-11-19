# Store both ranges, not the gap

[Two Hops](two-hops.sid) is a playable 232-byte NTSC PSID.  Its init stub copies a 73-byte player to `$2400` and a four-byte pitch table to `$7400`.  The file omits the 20,407 bytes between their original runtime locations.  This original example uses one 8580 SID and a video-field play call.

| Part | In the file (inclusive) | Loaded at | Used at | Bytes |
|---|---|---|---|---:|
| PSID header, explicit load address | `$00` through `$7B` | Not loaded | Host metadata | 124 |
| Entry jumps and install stub | `$7C` through `$9A` | `$1000` | `$1000` | 31 |
| Player and mutable frame counter | `$9B` through `$E3` | `$101F` | `$2400` | 73 |
| Pitch table | `$E4` through `$E7` | `$1068` | `$7400` | 4 |

The [linker configuration](layout.cfg) separates load and run addresses.  On every init at `$1000`, the [stub](two-hops.s) copies both ranges, then enters the player at `$2400`.  Play at `$1003` jumps to `$2418`.  Both calls return to the host.  Neither copy overwrites an unread source, the stub, or the other destination.  The file leaves 108 packed bytes live for repeat init; the two additional RAM copies bring the peak tune footprint to 185 bytes.  That excludes host stack, driver, and SID I/O.

### Leave room for the host

`startPage` and `pageLength` tell the host **where its driver fits**, not where the tune wants to copy itself.  With `$01=$37`, this example uses the ordinary bank-visible driver windows `$0400` through `$9FFF` and `$C000` through `$CFFF`.  Remove pages `$10`, `$24`, and `$74`.  The largest remaining run is `$2500` through `$73FF`, 79 pages; the two header bytes are `$25/$4F`.  Adding one page would put the driver on top of the pitch table.  `0/0` would incorrectly declare the tune clean.  See the [HVSC format specification](https://www.hvsc.c64.org/download/C64Music/DOCUMENTS/SID_file_format.txt).

Use `read_psid(wire, dirty_pages=(0x24, 0x74))` and `write_psid(tune, dirty_pages=(0x24, 0x74))` with [sidfile.py](../../sidfile.py).  Supply page numbers for **all** additional driver RAM used outside the loaded interval, not byte addresses, chip I/O, or the host call stack.  The helper excludes the load pages automatically and computes the largest free run, breaking ties by lowest start address.  Do not use it for different banking assumptions.  The default API and CLI are clean-only and intentionally refuse this example.  An agreement between header and declaration is not evidence that a program obeys that declaration.

### Rebuild and check

From this example directory, with Python and cc65 installed:

```sh
out=$(mktemp -d)
ca65 two-hops.s -o "$out/t.o"
ld65 -C layout.cfg "$out/t.o" -o "$out/t.bin"
python3 -B pack.py "$out/t.bin" "$out/t.sid"
cmp two-hops.sid "$out/t.sid"
```

`python3 -B check.py -v` additionally requires py65.  It executes the shipped bytes, puts the host call on the first declared free page, checks both copies and all SID writes over 65 play calls, damages both destinations, and checks init and two more loops without reloading.  A changed fourth pitch and a claimed driver range that intersects either destination must fail.  This validates the instruction-level contract under the stated mapping, not the sound of every SID model.
