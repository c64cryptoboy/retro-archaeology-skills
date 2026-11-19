# When does an indexed load actually read a saved byte?

Do not label `TSX / LDA $0102,X` “read the older of two pushed bytes” until you know the possible values of X.  On an NMOS 6502 or 6510, the two addresses agree often enough to make that label look convincing.

- **Hardware stack:** S is eight bits.  A push writes at `$0100 + S`, then decrements S modulo 256.  A pull increments S modulo 256 first, then reads at `$0100 + S`.  With two outstanding pushes, the older byte is at `$0100 + ((S + 2) & $FF)`.
- **Absolute indexed load:** TSX copies S into X.  It does not change the addressing mode of the next instruction.  `LDA $0102,X` reads at `$0102 + X`, with carry into the high byte.  This equals the older byte's address only when X is at most `$FD`.  Matching *values* in two locations do not establish matching addresses.

## Seven instructions, no caller required

Use ordinary RAM, no interrupts or intervening writes, entry PC=$4000, A=$35, and the initial S in the table.  Seed [$0200]=$D0 and [$0201]=$D1.  Stop at $400A without fetching the next instruction.

```asm
; Bytes                         Instruction
; 48                            PHA          ; save $35
; A9 C7                         LDA #$C7
; 48                            PHA          ; save $C7
; BA                            TSX
; BD 02 01                      LDA $0102,X  ; record address and A now
; 68                            PLA          ; $C7
; 68                            PLA          ; $35
```

| Initial S | Push addresses, in order | X after TSX | Actual indexed read | Older byte pulled from |
|---|---|---|---|---|
| $00 | $0100, $01FF | $FE | $0200 = $D0 | $0100 |
| $01 | $0101, $0100 | $FF | $0201 = $D1 | $0101 |
| $02 | $0102, $0101 | $00 | $0102 = $35 | $0102 |

The middle row isolates the two effects: neither push **writes** outside the adjacent pair $0101 and $0100, yet the indexed read still reaches page two.  The last row is a positive control where the stack-slot label is correct.  In every row the pulls restore A=$35 and the initial S.  Checking only those final registers misses both the indexed read and any model that pushes and pulls at symmetrically wrong addresses.  Record effective addresses and intermediate values, not just the final accumulator.

The [stack specification](https://github.com/henols/c64-re-tools/blob/2339d4aea09141af178263e7796fe875154c83d4/src/native/decompiler/language/c64rt_6510.slaspec#L329-L332) in the pinned c64-re-tools source operates on a word SP.  Its ordinary mid-page examples do not establish correct page-edge addresses.  That observation about the specification is not a recorded upstream test result.

The table is a hand prediction.  To check it with the bundled offline 6502 helper, put its `shared/6502` directory on `PYTHONPATH` and run `python3 -B scripts/stack_lookback_check.py` from the skill root.  The check uses only these authored bytes and compares data reads, ordered writes, register values, and the stop PC against the table.  It is not a bus-cycle trace or evidence that a historical program entered with any of these stack positions.
