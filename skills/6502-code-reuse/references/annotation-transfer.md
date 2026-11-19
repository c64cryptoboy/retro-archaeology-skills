# Transfer the address fact, not the name

A relocated routine can still be a good match after its hardware destination changes.  Keep an annotation only if the **target bytes and memory map support that particular claim**.

Here is an authored C64 example.  Assume I/O is visible, and `$C100` and `$C101` are distinct RAM bytes.  The source begins at `$4200`; the positive control starts at `$5300`.  Bytes in the second column are identical in both except where shown.

| Offset | Source bytes → relocated bytes if different | Reading |
|---|---|---|
| +00 | `AD 00 C1` | Load A from `$C100`. |
| +03 | `4D 11 42` → `4D 11 53` | XOR with the byte at entry + `$11`. |
| +06 | `8D 00 C1` | Store back to the byte just read. |
| +09 | `29 0F AA` | Keep the low nibble; copy it to X. |
| +0C | `8D 20 D0` | Write A to the VIC-II border color register. |
| +0F | `18 60` | Clear carry and return. |
| +11 | `01` | Mask byte, not another instruction. |

**Independent controls.**  Each negative changes just the indicated operand in the positive control.  All four retain the same instruction shape.  “Anchor” means an exact public relational match for these eight instructions at the stated entries, not a lineage verdict.

| Target | Anchor? | Annotation decision |
|---|---|---|
| Relocation only | Yes | Keep `xor_mask` at `$5311`, “store back to the byte just read,” and “write border color.”  Each has its own evidence. |
| I/O only: at +0C use `8D 21 D0` | Yes | Keep the mask and in-place update.  Reject `update_border` as an entry name: `$D021` selects background color 0, not the border.  The address still occurs just once, so its change preserves the reference pattern. |
| Alias only: at +06 use `8D 01 C1` | No | Keep the mask and border-write comment.  Replace “store back” with “read `$C100`; write result to `$C101`.”  The same RAM address used twice has become two distinct addresses. |
| Internal target only: at +03 use `4D 10 53` | Yes | Reject the relocated mask reference: `$5310` is the `60` of `RTS`, not the `01` at `$5311`.  A once-used reference can keep its relational token while pointing at the wrong byte. |

**Two different upstream reports.**  In [c64-provenance’s routine library](https://github.com/henols/c64-re-tools/blob/2339d4aea09141af178263e7796fe875154c83d4/skills/c64-provenance/scripts/lib/library.ts), an internal absolute operand marked for relocation must land at its original offset; a variable external operand may differ without vetoing the match.  On these data its rules would reject the wrong internal target, but report the I/O or RAM change in `differing` at the target **instruction**, `$530C` or `$5306`, respectively.

The separate `check` list concerns **proposed comment text**, not operand differences.  For example, “mask at $4211; write border at $D020” becomes “mask at $5311; write border at $D020.”  The external literal stays in the proposed write and is flagged even in the relocation-only control.  Conversely, “write border color” contains no four-digit address literal to flag, even in the I/O negative.  An empty warning list does not clear prose or names for transfer.  Check the actual destination, and preserve any existing target annotation rather than overwriting it on the strength of a match.
