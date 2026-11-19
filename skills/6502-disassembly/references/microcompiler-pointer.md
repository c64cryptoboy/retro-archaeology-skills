# Which address does `STA ($22),Y` actually write?

A source listing can identify the intended destination without identifying the address used by the machine code.  At one pinned Micro Compiler revision, `POKE 16385,PEEK(16905)` emits a read **and a write through `$4209`** on its straight-line path, not a copy from `$4209` to `$4001`.  The inner read reuses both bytes of the outer store's address.  No target execution is needed to distinguish the two paths through the data.

## Find the last definition of each pointer byte

This is the complete statement body from the saved object, for a 6502 at requested base `$C000`.  The entry jump at `$C000` skips the three-byte helper slot and enters at `$C006`.  The next source line is `END` (`RTS` at `$C020`).

| Address | Bytes | Instructions in order | What the block establishes |
| --- | --- | --- | --- |
| `$C006` | `A9 01 A2 40 85 22 86 23` | `LDA #$01; LDX #$40; STA $22; STX $23` | `$22/$23` holds `$4001`, the requested POKE address. |
| `$C00E` | `A9 09 A2 42 85 22 86 23` | `LDA #$09; LDX #$42; STA $22; STX $23` | PEEK replaces **both** halves with `$4209`.  Neither old byte reaches the indirect store. |
| `$C016` | `A2 00 A0 00 B1 22` | `LDX #$00; LDY #$00; LDA ($22),Y` | Read the byte at `$4209` into A.  X supplies a zero high byte for the expression result, not for the pointer. |
| `$C01C` | `A0 00 91 22` | `LDY #$00; STA ($22),Y` | Write that byte using the still-current pointer `$4209`.  Reloading Y is not restoring the pointer. |

**Useful comment at `$C01E`:** `; Write the byte just read through the PEEK pointer; the original POKE address was overwritten.`  Prefer a role-neutral name such as `scratch_ptr` for `$22/$23`; naming it `destination` throughout hides the overwrite.  Do not simplify the pair to a no-op: a write is present even if it would put the same value back in ordinary RAM.  These effective-address deductions assume normal straight-line execution from the stated entry, stable code and scratch memory, and no external intervention.  No live memory value, mapped device behavior, or observed write is claimed.

## Four comparison controls

Each row is a separate authored program, followed by `END` on its own line.  The split row has two statements on separate lines.  All use the same host compiler and base.

| Source before `END` | What distinguishes it | Saved bytes |
| --- | --- | ---: |
| `POKE 16385,16905` | Loading `$4209` as a **value** does not rewrite the scratch pointer.  The final store would write its low byte `$09` through `$4001`. | 27 |
| `POKE 16385,PEEK(16905)` | Wrapping the same numeral in `PEEK` installs `$4209` as a **pointer**.  This definition reaches both indirect accesses. | 37 |
| `T=PEEK(16905)` then `POKE 16385,T` | Same intended transfer; the byte is saved in T first.  `$4001` is installed *after* the read, and loading T does not disturb it.  Final store would copy the read byte to `$4001`. | 49 |
| `POKE 17414,PEEK(16905)` | Changing only the requested destination to `$4406` changes both original immediate bytes, and nothing else.  Neither changed byte reaches the final store. | 37 |

In the split and inline cases the final `A0 00 91 22` is **literally identical**.  A code-reuse match on that suffix does not establish matching address provenance or matching copy behavior.  Conversely, changing two literal operands in the fourth case does not change the address at the final store.  Keep the literal differences in the comparison; explain whether each reaches the consumer rather than masking the differences out.  On an unknown binary, redo this check per incoming path and for the actual Y value.  These four known-source builds are a controlled counterexample, not a producer fingerprint or an application-lineage test.

## Reproduce the emission claim

With Python 3 and the pinned upstream source already available, run the authored checker from the skill root:

```sh
python3 -B scripts/check_pointer.py /path/to/microcompiler/python/mc.py
```

It verifies the host compiler's SHA-256 before invoking it, generates the four tokenized inputs in temporary directories, checks for zero reported compiler errors, and compares each complete saved file against an explicit instruction and framing specification.  Sizes include the two-byte load address, the generator's final zero, and one extra byte included by the Python saver.  It neither simulates nor executes any emitted code.

**Source:** Vic Cortes's Micro Compiler as translated by EgonOlsen71 using MOSpeed, commit `71551d432255f3eda552fa1c1e3b3335a3c11e41`: [PEEK expression emitter](https://github.com/EgonOlsen71/microcompiler/blob/71551d432255f3eda552fa1c1e3b3335a3c11e41/python/mc.bas#L36-L42), [POKE statement emitter](https://github.com/EgonOlsen71/microcompiler/blob/71551d432255f3eda552fa1c1e3b3335a3c11e41/python/mc.bas#L175-L180), and [Python host saver](https://github.com/EgonOlsen71/microcompiler/blob/71551d432255f3eda552fa1c1e3b3335a3c11e41/python/mc.py#L6350-L6362).  The verified claim is about the saved bytes of this host translation, not the original magazine compiler, other ports, or arbitrary BASIC programs.
