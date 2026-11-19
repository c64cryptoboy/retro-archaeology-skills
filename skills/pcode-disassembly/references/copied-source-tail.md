# Reblitz64: valid instructions after `END` do not prove a source statement

Two distinct tokenized inputs can produce the **same complete compiled PRG**.  In this [Reblitz64 revision](https://github.com/c1570/Reblitz64/blob/4c3f9da453b53fd5cbe898f85a99b1d914efb117/docs/reblitz64.js#L1922-L1944), pass 2 appends an `END` (`$4F`) and [carries bytes after the input's final BASIC link into the output](https://github.com/c1570/Reblitz64/blob/4c3f9da453b53fd5cbe898f85a99b1d914efb117/docs/reblitz64.js#L2976-L2987).  In the tested layout, those bytes are **before** the scalar table, inside the reader's candidate main p-code extent.  Looking for extra bytes *after* the table will not find them.

| One-line source | Bytes after the final zero link | End of candidate main region |
|---|---|---|
| `10 A=0:END:PRINT7` | None | `4F B7 3E 4F` |
| `10 A=0` | `B7 3E 4F` | `4F B7 3E 4F` |

In the first input `PRINT 7` is an actual, albeit unreachable, source statement.  In the second, the compiler never saw such a statement: the three copied bytes just decode as a small literal, `PRINT`, and `END`.  Changing the copied literal to `$B8` changes the reading to `PRINT 8`.  Neither object was executed.

**Reproduce:** from the skill root, run `python3 -B scripts/blitz/check_tail_collision.py /path/to/pinned/docs/reblitz64.js scripts/reconstruct/reconstruct.py`.  The authored test checks both complete objects and changes or removes the three-byte tail as controls.  No target is run.

**Reading rule:** distinguish a byte-valid instruction reading from its source provenance.  Do not truncate at the first `END`, since that can discard actual compiled statements.  Do not attribute every valid instruction before the scalar table to BASIC source, either.  If the reader refuses an unknown opcode there, preserve the refusal; neither printable text nor an earlier `END` establishes the boundary.  With separately supplied tokenized source, walk the line links to the final zero link, and compare the remaining bytes and their position in the output.  Without that evidence, these two origins are indistinguishable in the example.  This is a producer-specific ambiguity, not a change to the BLITZ opcode grammar or evidence about historical compilers generally.
