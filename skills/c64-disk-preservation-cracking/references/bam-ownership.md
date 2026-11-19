# When a BAM-used sector has no file chain

A used bit says that a sector is not advertised as free.  It does not say who owns the sector, what its bytes mean, or whether a program reads it.

For the identified DOS format, record the sector coordinates marked used in the block availability map (BAM).  Alongside them record **why** each known sector is claimed: header and directory links, fixed DOS allocations for that format, active file chains, and file-type-specific structures such as 1541 REL side sectors.  Subtract the union of those claims, not just the ordinary file chains.  Keep conflicting claims or claimed-but-free sectors as inconsistencies; if links are unreadable or an entry type is unsupported, report incomplete coverage.  The remainder is **allocated with no identified DOS reference**, not a list of hidden files.

## Worked control: seven used sectors, two residuals

The companion `check_bam.py` uses only original in-memory sectors from a stipulated unpartitioned 1581 layout.  Coordinates are decimal `track/sector`.  No full disk is supplied or required.

| BAM-used sectors | Independent structural evidence | Classification |
|---|---|---|
| `40/0`, `40/3` | The header points to the directory at `40/3`. | Header and directory metadata |
| `40/1`, `40/2` | The 1581 profile places its two bitmap blocks here, outside that chain. | DOS allocations, not lost file data |
| `1/7` | An active SEQ slot points here. | Directory-owned index file |
| `41/8`, `41/9` | Neither has an active DOS reference.  Their 256 bytes are identical. | Two residuals; purpose not determined by subtraction |

Two one-byte controls show what additional evidence buys:

- **Previous ownership:** in the paired earlier directory, the second slot is active and points at `41/8`; in the later directory its type is zero.  Nothing else changes, including either BAM.  The extra residual is therefore attributable to a lost directory claim in this constructed history.  An inactive slot in a lone image would be a lead, not this proof.  This does not simulate a normal DOS scratch operation.
- **Application reference:** the authored index format is the three bytes `IDX` followed by a binary track and sector.  Changing only its target from `41/9` to `41/8` leaves both residuals and their bytes unchanged.  The index, not the BAM, distinguishes the statically referenced coordinate.  A sector can have both a former DOS owner and a current application reference.  Finding two coordinate-shaped bytes without a justified interpretation would not establish that reference, and even this known record does not prove a read occurred.

From this skill directory run `python3 -I -B scripts/check_bam.py -v` (Python 3.10 or newer).  It takes no input paths and does not mount, repair, or write a disk.  It exercises only the structures above; it is not a general disk validator.

Source: [c64-re-tools DOS allocation accounting](https://github.com/henols/c64-re-tools/blob/2339d4aea09141af178263e7796fe875154c83d4/src/host/tools/c1541.ts#L270-L288), independently checked against [VICE 1581 layout constants](https://github.com/slajerek/RetroDebugger/blob/778ef3a1b3e86737cbf81cc13b66fe622f544b6d/vice-3.10/src/diskconstants.h#L115-L129).  The sample sectors and index are authored for this exercise.
