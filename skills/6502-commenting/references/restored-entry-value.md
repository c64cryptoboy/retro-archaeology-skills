# When does a routine preserve X?

The [two-exit register test in Reko](https://github.com/uxmal/reko/blob/b5a4afc2cb85d8a426057b895bdf6be7644cfdb2/src/UnitTests/Decompiler/Analysis/TrashedRegisterFinderTests.cs#L731-L761) checks a summary across two returns in x86 IR.  The 6502 example here is independent.  From this skill root, run `PYTHONPATH=../../shared/6502 python3 -B scripts/check_returns.py -v` to check both carry states for all 256 X inputs.

A caller can rely on X only if every reachable normal return delivers the **entry value of X**.  Prove stack balance separately: compare S just before `RTS` with S at callee entry, or compare S after `RTS` with S before `JSR`.  Mixing those boundaries counts the two-byte return address as a discrepancy.

Consider this ordinary 6502 subroutine, with one entry, writable stack RAM, no interrupts, and no other writers:

```asm
save_x: TXA             ; A = entry X
        PHA
        LDX #$3C        ; use X as scratch
        BCS set_arm     ; entry carry survives TXA, PHA, and LDX
        PLA
        TAX
        RTS
set_arm:
        PLA
        TAX             ; control: replace just this TAX with TSX
        RTS
```

Let `x` and `s` denote X and S at callee entry.  `PHA` writes `x` to `$0100 + s`.  On either arm, `PLA` reads the same byte into A and restores S to `s`.  Trace the **last writer of X**, not just the pop:

| Return arm | Last writer of X | X at return | S before RTS |
|---|---|---|---|
| Carry clear, either version | `TAX` reads A | `x` | `s` |
| Carry set, original | `TAX` reads A | `x` | `s` |
| Carry set, altered | `TSX` reads S | `s` | `s` |

The original contract is **X preserved**.  The altered contract is **X preserved on carry clear; on carry set, X receives callee-entry S**.  Both versions return normally, both arms recover the saved byte into A, and both balance the stack.  A test starting with `x = s` even sees X unchanged on the altered arm.  Use distinct values to distinguish restoration from coincidence.  If a relevant return path or stack-slot writer is unresolved in a real routine, report preservation as unproved rather than promoting one observed return to a caller guarantee.
