# Five bytes that round a byte up to even

This teaching example was written from scratch.  It has one leaf word, no dictionary, and no nested threaded calls.  The names below are editorial.  The model and body are supplied so that the interpretation can be checked without identifying an actual runtime.

## Why this is a thread

In this invented 6502 fragment, a native caller uses `JSR enter`.  On entry, `Y` indexes a valid top byte in a data stack named `cells`.  No operation changes its depth.  The caller permits `A`, `X`, and flags to be clobbered.  The native hardware stack holds the caller's `JSR` return; `RTS` uses it.  There is no evidence here for a separate Forth return stack.

```asm
enter:  CLD                 ; binary arithmetic
        LDX #0              ; X is a byte offset into body
next:   LDA body,X
        INX
        CMP #$C8
        BEQ even_skip
        CMP #$53
        BEQ add_byte
        CMP #$01
        BEQ leave
        JMP reject          ; unsupported token, no next fetch

even_skip:
        LDA cells,Y
        AND #1
        BNE odd
        INX                 ; base is now the offset AFTER the operand
        TXA
        CLC
        ADC body-1,X        ; add the operand byte, modulo 256
        TAX
        JMP next
odd:    INX                 ; consume displacement without branching
        JMP next
add_byte:
        LDA cells,Y
        CLC
        ADC body,X
        STA cells,Y
        INX
        JMP next
leave:  RTS
```

The CPU executes the fragment, not `body`.  `LDA body,X` in `next` fetches a one-byte token; comparisons resolve its native handler.  The same addressing mode in `add_byte` reads a **parameter**, not a token.  Neither a code-field pointer nor a native instruction stream in the body would explain these two consumers.

## Raw ledger

Body offsets are in bytes, starting at zero.  The authored body is `C8 02 53 01 01`.

| Offset | Bytes | Owner, effect, and successor |
|---|---|---|
| +0 | `C8 02` | Token `C8` tests the low bit without popping; `even_skip` owns the inline displacement at +1.  Odd: +2.  Even: (+2 + `02`) modulo 256 = +4. |
| +2 | `53 01` | Token `53` adds its inline unsigned byte at +3 to the top byte, modulo 256; fetch resumes at +4. |
| +4 | `01` | Token `01` returns to the native caller.  No next token in this word. |

**Readable view** (`round-even` is not a recovered spelling): `round-even ( u8 -- u8' )`: if the input is odd (+0), add one (+2); otherwise keep it.  Return (+4).  Both paths retain one cell.  For example, 6 stays 6, 7 becomes 8, and 255 wraps to 0.

## Try to falsify it

From this skill directory run `python3 -B check_example.py`.  The check models only this fixture, with the three operation starts taken independently from its authored layout.  It checks paths as well as values.  Moving the even edge to +3 would appear to return the right value because the byte there also spells return; that byte belongs to `53`, so the path is invalid.  Moving it to +2 hits a *valid* token but changes the even result.  A changed addend is a positive control: the odd result should change without moving either edge.

The test is a static contract check in Python.  It does not assemble or execute the fragment, test an emulator, or validate any historical runtime.
