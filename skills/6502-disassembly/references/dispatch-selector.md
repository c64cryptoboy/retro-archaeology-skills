# Bound a dispatch table by its selector, not by the next plausible pointer

A fourth pointer can lead to valid code without being a fourth case.  To decide which edges to add to the control-flow graph, work backward from the indirect transfer.  Identify the bytes that supply the target and the value that indexes each read.  Then state the condition **on the edge into those reads**.  The branch may jump *into* the table path, not around it.  Check which register was compared, whether it or the consumed flag changed, and whether another entry bypasses the guard.  Apply any scaling or remapping only after establishing the selector domain.

### Worked bytes: three slots, two destinations

Authored NMOS 6502 example, flat RAM, sole entry `$3600`, arbitrary byte X, stable code and tables, and no interrupt or other writer to the pointer.  The following are separate address regions, not one contiguous file:

```text
3600  E0 03       CPX #$03
3602  90 03       BCC $3607
3604  4C 20 36    JMP $3620
3607  BD 40 36    LDA $3640,X
360A  85 F8       STA $F8
360C  BD 50 36    LDA $3650,X
360F  85 F9       STA $F9
3611  6C F8 00    JMP ($00F8)

3640  74 20 74 B6    low bytes
3650  37 36 37 38    high bytes
3620, 3774, 38B6     each contains 60 (RTS)
```

`CPX #$03` sets carry for unsigned X ≥ 3.  The **taken** `BCC` edge admits X < 3, including zero but excluding three.  Nothing changes X before either load.  Each array advances by **one** byte per selector, not two; the stores assemble the little-endian target at `$F8` and `$F9`.

| Entry X | Bytes read for destination | Transfer site → destination |
|---|---|---|
| 0 | `$3640` = `74`, `$3650` = `37` | `$3611` → `$3774` |
| 1 | `$3641` = `20`, `$3651` = `36` | `$3611` → `$3620` |
| 2 | `$3642` = `74`, `$3652` = `37` | `$3611` → `$3774` |
| 3 through 255 | No table read | `$3604` → `$3620` (default) |

Keep the selector-to-slot mapping even when destinations repeat.  X=1 takes the table path to the same address as the default; collapsing them would hide two pointer writes.  The bytes at `$3643` and `$3653` form `$38B6`, another backed `RTS`, but this entry cannot select them.  That is a bound on **use at this site**, not proof about array allocation, padding, or other callers.

**Check:** from the skill root in this repository, run `PYTHONPATH=../../shared/6502 python3 -B scripts/check_dispatch.py -v` to check every selector on the original path.

**One-byte negative control.**  Change only `$3600` from `E0` to `C0` (`CPY #$03`).  At X=3, Y=0, the branch still reaches the loads, but they now read `$3643` and `$3653` and transfer to `$38B6`.  At X=0, Y=3, the direct default is taken despite X being in the original range.  Without a separate relation between X and Y, report the three-slot bound as unproved.  Do not replace it with a four-slot bound just because four byte pairs were supplied.

**Source of the method, not of these bytes.**  Reko's pinned [branch backwalk](https://github.com/uxmal/reko/blob/b5a4afc2cb85d8a426057b895bdf6be7644cfdb2/src/Decompiler/Scanning/Backwalker.cs#L342-L382) accounts for which branch edge leads to dispatch.  Its [inverted-condition test](https://github.com/uxmal/reko/blob/b5a4afc2cb85d8a426057b895bdf6be7644cfdb2/src/UnitTests/Decompiler/Scanning/BackwalkerTests.cs#L274-L298) expects a comparison, normalized rejection condition, and scale, not a list of recovered machine targets.  Its [unguarded indexed-load test](https://github.com/uxmal/reko/blob/b5a4afc2cb85d8a426057b895bdf6be7644cfdb2/src/UnitTests/Decompiler/Scanning/BackwalkerTests.cs#L235-L245) distinguishes recognizing the transfer shape from finding a guard.  Neither test establishes that Reko recognizes this 6502 sequence.
