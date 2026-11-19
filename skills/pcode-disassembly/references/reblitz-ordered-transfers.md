# Checking ordered BLITZ `ON` transfers with Reblitz64

A reader can find every destination and still send selector 1 to the wrong block, or print a jump where the program encodes a call.  Test the **ordered entries, transfer kind, and first instruction after the table** separately.  The following is a compile-only example for [Reblitz64 revision `4c3f9da`](https://github.com/c1570/Reblitz64/tree/4c3f9da453b53fd5cbe898f85a99b1d914efb117), not a cross-family opcode rule.

A different round-trip test asks whether the source statement existed at all: [identical PRGs from a statement or from copied trailing bytes](copied-source-tail.md).

1. Tokenize this authored listing as a linked C64 BASIC V2 PRG loaded at `$0801`.  Keep the selector variable and targets in deliberately non-address order.  The initial `GOSUB 30` makes `RETURN` meaningful in both versions.

   ```basic
   10 INPUT X:GOSUB 30:END
   30 ON X GOTO 70,50,90
   40 RETURN
   50 PRINT "A":RETURN
   70 PRINT "BB":RETURN
   90 PRINT "CCC":RETURN
   ```

2. Make two variants: change only line 30's `GOTO` to `GOSUB`, then change only that call list to `90,50,70`.  Compile each tokenized input with `node docs/reblitz64.js input.prg output.prg` from the pinned checkout, using distinct filenames and retaining stdout.  Check both the error and extension counts are zero.  No C64 execution is needed.  Give the reader only the compiled PRG; consult the source and pass-two log **after** the reading.
3. In [the pass-one `ON` handler](https://github.com/c1570/Reblitz64/blob/4c3f9da453b53fd5cbe898f85a99b1d914efb117/docs/reblitz64.js#L924-L964), each source line number initially occupies two bytes, and each slot gets a relocation.  The size byte counts **the whole instruction**, not entries or target bytes alone.  [Pass two](https://github.com/c1570/Reblitz64/blob/4c3f9da453b53fd5cbe898f85a99b1d914efb117/docs/reblitz64.js#L2128-L2144) writes resolved addresses high byte first.  Decode all slots without sorting or deduplicating them.

| Source transfer | Complete instruction at `$1FAB` | Destination rows, in selector order | Control type |
|---|---|---|---|
| `GOTO 70,50,90` | `1B 08 1F B8 1F B4 1F BD` | `$1FB8` BB, `$1FB4` A, `$1FBD` CCC | `multi_branch` |
| `GOSUB 70,50,90` | `1C 08 1F B8 1F B4 1F BD` | `$1FB8` BB, `$1FB4` A, `$1FBD` CCC | `multi_branch_call` |
| `GOSUB 90,50,70` | `1C 08 1F BD 1F B4 1F B8` | `$1FBD` CCC, `$1FB4` A, `$1FB8` BB | `multi_branch_call` |

The statement starts with the selector load at `$1FAA`; the table starts one byte later.  In all three outputs the first row after it starts at `$1FAB + 8 = $1FB3` (`RETURN`).  Check the reader's actual statement heading as well as the opcode row: `ON X GOSUB L_1FB8, L_1FB4, L_1FBD` should consume `X` once.  The pass-two log independently of the reader locates lines 40, 50, 70, and 90 at decimal 8115, 8116, 8120, and 8125.  These lines are known from the fixture, not recovered from the address labels.

**Negative controls.** A set comparison cannot distinguish the last two call tables.  Swapping the first and last entries changes only the bytes at `$1FAE` and `$1FB2` in the whole PRG.  For a malformed control, change the last byte of the unswapped call table from `BD` to `BE`: the last destination now lands inside `"CCC"`.  The first two entries still pass, but a complete boundary validator must refuse the object.  Neither the row following the table nor its destinations establish observed selector behavior, bounds handling, or actual returns.

### A port's relocation limit need not be the original compiler's limit

Before borrowing a numeric limit, compare three things: the earlier expression, the port's storage type, and a saved object on the far side of the boundary.  The [annotated compiler is explicitly rearranged](https://github.com/c1570/Reblitz64/blob/4c3f9da453b53fd5cbe898f85a99b1d914efb117/README.md#L78-L104); its structured source and generated JavaScript are not independent witnesses.  In the [earlier decompiled listing, line 15139](https://github.com/c1570/Reblitz64/blob/4c3f9da453b53fd5cbe898f85a99b1d914efb117/docs/1_blitz_decomp_compacted.bas.txt#L460), the resolved offset plus base is assigned to a signed `%` temporary.  The port [resolves it as a JS number](https://github.com/c1570/Reblitz64/blob/4c3f9da453b53fd5cbe898f85a99b1d914efb117/docs/reblitz64.js#L2186-L2198); the maintainer documents this as a fix for pass two above `$7FFF`.

The [saved `oversized` output](https://github.com/c1570/Reblitz64/blob/4c3f9da453b53fd5cbe898f85a99b1d914efb117/tests/outp2-oversized.prg) supplies a concrete check: at `$8002` it contains `19 80 05`, a `GOTO` to the instruction start at `$8005`.  To locate the bytes in this `$0801` PRG, use file offset `2 + ($8002 - $0801)`.  Upstream's [test driver](https://github.com/c1570/Reblitz64/blob/4c3f9da453b53fd5cbe898f85a99b1d914efb117/docs/hack.sh#L72-L82) compares compiler output with saved bytes, not with target execution.  **Read the encoded address as unsigned** and validate it against this object's actual code region and instruction starts.  Do not reject a valid high address because an earlier producer had a signed intermediate, or claim the historical compiler successfully emitted it because the port can represent it.
