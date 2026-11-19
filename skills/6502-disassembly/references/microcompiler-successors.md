# Same 24 bytes: skip a THEN clause, or update a loop counter?

`BCS +11` skips a three-byte `JMP` in both of these Micro Compiler objects.  In the `IF` object it selects the next source line.  In the `FOR` object it selects the counter update.  To tell them apart, identify the block on each end of the edge, not just its direction, displacement, or compare opcode.

These are separate authored inputs at load address `$C000`; the addresses below exclude the file's two-byte load prefix.

| Line | IF object | FOR object |
| ---: | --- | --- |
| 10 | `I=258` | `FOR I=258 TO 258` |
| 20 | `IF I>258 THEN GOTO 40` | `A=1` |
| 30 | `A=1` | `NEXT I` |
| 40 | `END` | `END` |

### Read the common block before naming it

The following 24 bytes match exactly at `$C010` in IF and `$C00D` in FOR.  The first pair of loads fetches I; `$22/$23` then holds its low and high bytes.  The immediate pair loads the right operand, `$0102`.  Read `CPX $23` as **limit high compared with I high**, not the reverse.

```text
AD B8 02 AE B9 02  LDA $02B8; LDX $02B9
85 22 86 23        STA $22; STX $23
A9 02 A2 01        LDA #$02; LDX #$01
E4 23 F0 04        CPX $23; BEQ low_compare
B0 0B 90 06        BCS +11; BCC +6
C5 22              low_compare: CMP $22
```

Equal high bytes go to `CMP $22`.  With unequal high bytes, carry set means the limit's high byte is greater, so I is below the limit in unsigned order.  What that fact *does* depends on the successor:

| Unsigned relation at the test | IF object | FOR object on return from NEXT |
| --- | --- | --- |
| I below limit | Next source line at `$C02F` (`A=1`). | Update at `$C02C`; add one, store I at `$C03B`, then enter the body at `$C041`. |
| I equal to limit | `$C028: BCS $C02F` selects `A=1`. | `$C025: BEQ $C029` selects `JMP $C04E`, the exit.  No increment on this edge. |
| I above limit | THEN at `$C02C`: `JMP $C039` selects `END`. | `$C029: JMP $C04E` selects `END`. |

Those are predicate cases, not three observed runs.  In IF the low-byte branch pair is `B0 05 F0 03`; the `BEQ` cannot be taken after that `BCS` falls through, since equality would have set carry.  In FOR it is `F0 02 B0 03`; equality is dispatched **before** the carry test.  Removing or reordering the first low-byte branch would change the loop decision.

**Which iteration is tested?**  FOR's `$C00A: JMP $C03B` takes the initial value directly to the counter store and body, bypassing both comparison and addition.  `$C04B: JMP $C00D` from NEXT goes back to load the *current* I, not to initialize it.  For this equal-start/limit input and stable memory, the body therefore precedes the equality exit.  A rendering as a pre-tested loop, or as increment-then-test, would put an operation on the wrong path.  The IF object has no back edge.

### Two controls

1. Change only IF's `GOTO 40` to `A=2`.  The THEN payload grows from three to ten bytes.  Inside the 24-byte window only `B0 0B` becomes `B0 12`.  It still skips the THEN payload to the next line.  The *exact* displacement match with FOR depended on layout, not on both sources using a loop.
2. In a copy of the FOR bytes, redirect NEXT to `$C006` (initialization) instead of `$C00D` (compare).  The 24-byte window still matches, but the back-edge check rejects the copy.  A prefix-only test would accept it.

**Reproduce:** with the pinned Python translation already available, from this skill directory run `python3 -B scripts/check_successors.py /path/to/microcompiler/python/mc.py`.  The checker creates temporary files, compiles the three inputs, decodes relative targets against a separate table of expected addresses, and checks the surrounding instructions and the negative control.  It does not execute emitted code.  The compare deductions assume ordinary 6502 flag semantics and entry from the shown blocks; the binary-add interpretation assumes decimal mode clear.  None of these observations establishes provenance in an unknown binary or full BASIC loop semantics.

**Source:** Vic Cortes's Micro Compiler, translated to Python by EgonOlsen71 using MOSpeed, commit `71551d432255f3eda552fa1c1e3b3335a3c11e41`: [IF emitter](https://github.com/EgonOlsen71/microcompiler/blob/71551d432255f3eda552fa1c1e3b3335a3c11e41/python/mc.bas#L107-L119), [next-line fixup](https://github.com/EgonOlsen71/microcompiler/blob/71551d432255f3eda552fa1c1e3b3335a3c11e41/python/mc.bas#L64-L67), and [FOR and NEXT emitters](https://github.com/EgonOlsen71/microcompiler/blob/71551d432255f3eda552fa1c1e3b3335a3c11e41/python/mc.bas#L154-L170).  FOR saves the pending IF fixup, calls BASIC line 1090 with `w=177`, restores the fixup, then rewrites offsets and branch opcodes for its own successors.  This explains the resemblance without making the two generated tests interchangeable.
