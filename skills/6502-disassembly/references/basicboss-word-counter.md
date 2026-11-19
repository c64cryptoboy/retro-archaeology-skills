# BASIC-BOSS FASTFOR: a low-byte rollover is not a loop exit

A byte store in a loop body does not tell you the width of its counter.  Two BASIC-BOSS FASTFOR loops both load one byte and store it at `$0400`.  Change only the declaration from BYTE to WORD, and the code after that store distinguishes an ordinary low-byte rollover from overflow of the whole counter.

The starting point is the existing BASIC-BOSS directive comparison: `FOR I=1 TO 3`, `POKE 1024,I`, `NEXT I`, then `END`, with `£PROTOCOL` and `£FASTFOR`.  Keep FASTFOR, the implicit step, and all executable statements fixed.  In the saved BYTE build, `INC` followed by a zero test can exit immediately on byte wrap.  In the WORD build, the program grows from 73 to 86 bytes; the preceding routines and data stay byte-identical.  The protocol reserves two bytes instead of one for `I`, **after** the saved program, not inside the PRG.  These are compiler-assisted findings for the [pinned wrapper and compiler image](https://github.com/mbergmann-sh/basicbossGUI/tree/d27331c334003b63554139a7aead82236f823c6b/bbcompiler-src), not an instruction signature.

### Follow the two flags separately

In the WORD object the initializer stores `$01` at `$0B3B` (low) and `$00` at `$0B3C` (high).  This is the loop, starting at the `POKE` source anchor.  Addresses are load addresses, not file offsets.

```text
0B0F  AD 3B 0B  LDA $0B3B      ; body consumes low byte only
0B12  8D 00 04  STA $0400
0B15  EE 3B 0B  INC $0B3B
0B18  D0 03     BNE $0B1D      ; if low != 0, skip high INC, not the BEQ
0B1A  EE 3C 0B  INC $0B3C
0B1D  F0 0C     BEQ $0B2B      ; exit on full wrap
0B1F  A9 03     LDA #$03       ; limit.low
0B21  CD 3B 0B  CMP $0B3B      ; C = no borrow on limit.low - counter.low
0B24  A9 00     LDA #$00       ; limit.high; leaves C alone
0B26  ED 3C 0B  SBC $0B3C      ; subtract counter.high and incoming borrow
0B29  B0 E4     BCS $0B0F      ; no final borrow: repeat, including equality
                               ; otherwise fall through to $0B2B
```

- **Increment uses Z, not C.**  At `$0B1D`, Z comes from the low `INC` on the taken `BNE` path and must be clear.  On the other path, low has become zero and Z comes from the high `INC`.  Thus `$00FF` becomes `$0100` and goes on to the comparison; `$FFFF` becomes `$0000` and exits *before* the comparison.  The latter is a property of the emitted path, not a state reached by these small limits on normal entry.
- **Comparison uses C, not Z.**  The subtraction is **limit minus updated counter**, not the reverse.  On a 6510 in binary arithmetic mode the final carry means `updated_counter <= limit` unsigned.  For example, at equality the low comparison sets C; subtracting equal high bytes with no incoming borrow leaves C set.  The branch goes back to the body load, not the initializer.  This is a post-body test, not evidence for an extra source-level entry check.

### One discriminating control

With a limit of 3, the high immediate in `LDA #$00` might look like a fixed zero.  Change only `TO 3` to `TO 259` (`$0103`): of all 828 saved bytes, **only `$0B25` changes**, from `$00` to `$01`.  The immediate low byte stays `$03` and all three branch destinations stay fixed.  For the latter bound, the code predicts repetition at `$00FF` despite a low-byte borrow (`$03 < $FF`): the high subtraction is `$01 - $00 - 1`, with no final borrow.  It predicts repetition at `$0103` and exit at `$0104`.  No target execution was needed or performed.

**What transfers:** use the body's stable store to locate the site, then recover counter width, wrap handling, operand order, and inclusivity from *all incoming flag definitions and branch targets*.  The two WORD objects support that reading at two positive constant limits with default unit step.  They do not establish one lowering for arbitrary bounds, steps, types, or nested loops; nor do they identify BASIC-BOSS or the source declaration in an unfamiliar binary.  The [manual describes a wider FASTFOR contract](https://github.com/mbergmann-sh/basicbossGUI/blob/d27331c334003b63554139a7aead82236f823c6b/bbcompiler-src/BasicBoss.txt#L659-L674), not a guarantee of this instruction sequence.  The [component rights notice](https://github.com/mbergmann-sh/basicbossGUI/blob/d27331c334003b63554139a7aead82236f823c6b/bbcompiler-src/readme.txt#L13-L22) distinguishes the wrapper from BASIC-BOSS and its manual; this exercise does not require redistributing any compiler image or linked object.

### Descending WORD: the two branches read different carries

A `BCS` back to the body does **not** tell you which way the counter runs.  The ascending WORD example subtracts the updated counter from the limit.  In an authored `FOR I=257 TO 3 STEP -1` with the same WORD declaration, FASTFOR directive, `POKE 1024,I`, and `NEXT I`, the backedge is still `BCS`, but the subtraction is **updated counter minus limit**.  The [pinned manual](https://github.com/mbergmann-sh/basicbossGUI/blob/d27331c334003b63554139a7aead82236f823c6b/bbcompiler-src/BasicBoss.txt#L659-L674) permits a negative literal step; the following is evidence from one saved object, not a template for all negative steps.

The initializer at `$0B05` writes `$0101` into the two-byte counter at `$0B44`.  The body at `$0B0F` copies its low byte to `$0400`.  From the instruction immediately after that store:

```text
0B15  CLC
0B16  LDA $0B44
0B19  ADC #$FF
0B1B  STA $0B44
0B1E  LDA $0B45       ; preserves low addition's C
0B21  ADC #$FF
0B23  STA $0B45
0B26  BCC $0B34       ; exit on whole-word underflow, before comparing
0B28  LDA $0B44
0B2B  CMP #$03        ; replaces update carry with low comparison carry
0B2D  LDA $0B45
0B30  SBC #$00        ; high difference includes borrow from CMP
0B32  BCS $0B0F       ; no final borrow: repeat, including equality
```

Assuming binary arithmetic and ordinary counter RAM, the update adds `$FFFF`.  At `$0100`, the low addition produces `$FF` with C clear; the high addition is then `$01 + $FF + 0`, giving `$00` **with C set**.  The result `$00FF` goes to the comparison, not the exit.  Only old `$0000` lacks a carry out of the full addition; the stored `$FFFF` then bypasses the comparison.  That edge is encoded but not reached from 257 with limit 3 on normal iteration.

A separate check distinguishes the *second* carry: at updated `$0100`, `CMP #$03` borrows on the low byte, but high `$01 - $00 - 1` does not borrow, so the backedge is taken.  At updated `$0003` equality repeats; at `$0002` it falls through.  These are static predictions, not a target trace.  When reading similar loops, identify the producer of C at **each** branch before translating it into a source-level relation.
