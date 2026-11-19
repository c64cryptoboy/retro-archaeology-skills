# BASIC-BOSS: distinguish a compiler directive from a loop signature

A 603-byte change in a BASIC-BOSS object need not mean that a loop body grew by 603 bytes.  Separate linked routines from the generated program, find the same source operation in both, and compare the instructions that control it.  This is a native 6502 emission probe, not p-code decoding.

## Compile-only comparison

1. Pin the producer.  At [basicbossGUI revision d27331c](https://github.com/mbergmann-sh/basicbossGUI/tree/d27331c334003b63554139a7aead82236f823c6b), the GUI is not the compiler.  The [C wrapper](https://github.com/mbergmann-sh/basicbossGUI/blob/d27331c334003b63554139a7aead82236f823c6b/bbcompiler-src/bbcompiler.c) runs the compiler from an [embedded RAM/ROM image](https://github.com/mbergmann-sh/basicbossGUI/blob/d27331c334003b63554139a7aead82236f823c6b/bbcompiler-src/boss_abbild.inc).  The [wrapper notes](https://github.com/mbergmann-sh/basicbossGUI/blob/d27331c334003b63554139a7aead82236f823c6b/bbcompiler-src/readme.txt) identify wrapper v0.2.2 and BASIC-BOSS V2.4.  This is not independent reimplementation evidence.
2. Author the source below twice.  Replace only `SLOWFOR` with `FASTFOR` in the second copy.  Declare `I` as `BYTE` in both; changing its type as well would confound the comparison.  Keeping the same line numbers and directive length preserves the line links.

   ```basic
   0 REM@ £PROTOCOL
   5 REM@ £BYTE I: £SLOWFOR
   10 FOR I=1 TO 3
   20 POKE 1024,I
   30 NEXT I
   40 END
   ```

3. Write a tokenized `$0801` PRG, not this listing as UTF-8.  For exact reproduction, use a two-byte little-endian load address, and for each line write the next record's RAM address and line number (both little-endian words), body, and `$00`.  Append a `$0000` link.  Encode lines 0 and 5 as `$8F` (REM), `@`, one space, then the uppercase literal tail shown, with `£` as PETSCII `$5C`.  Omit spaces after line numbers and outside REM tails.  The remaining bodies in order are `81 49 B2 31 A4 33`, `97 31 30 32 34 2C 49`, `82 49`, and `80`.  Walk the links back before compiling; reject plain text, broken links, or a missing line-zero protocol.  The [demo listing](https://github.com/mbergmann-sh/basicbossGUI/blob/d27331c334003b63554139a7aead82236f823c6b/bbcompiler-src/demo.txt#L1-L3) uses a backslash to display the pound byte.  Do not tokenize the `FOR` *inside the REM tail*.
4. If authorized to use the compiler image, build only the reviewed C wrapper locally.  Use a fresh isolated directory per arm, one tiny known input, fixed short input/output names, capped time and output, and no launch of generated code.  The underlying CLI is `bbcompiler input.prg object.prg`.  Keep stdout/stderr and both PRGs.  Require clean diagnostics, pass 2, a region map, and an output that fits the map.  A file and exit status zero are not success criteria.
5. Use `PROGRAMM` for the generated program and `ROUTINEN` for the linked routines/stub.  For these single-file objects, file offset = `2 + address - $0801`; ends in the protocol are exclusive.  Both have `SYS 2085` and a native `JMP` at `$0825` to their respective `PROGRAMM` starts.  Do not linear-sweep their header, startup parameters, or bytes after calls as though all were code.

## What the saved bytes establish

| Directive | File bytes including prefix | Routines / data / program bytes | Program start | Counter address |
|---|---:|---:|---:|---:|
| SLOWFOR | 1,418 | 1,335 / 6 / 75 | `$0D3E` | `$0D89` |
| FASTFOR | 815 | 734 / 6 / 73 | `$0AE5` | `$0B2E` |

The stable anchor is the assignment to `$0400` (source `POKE 1024,I`).  In the slow object `$0D5E` initializes `$0D89` to 1, then `$0D63` calls `$0A67`.  At `$0D6D`, `AD 89 0D 8D 00 04` copies that counter to `$0400`; immediately afterward `$0D73` calls `$0B05`.  Treat the intervening bytes after the first call as a separate region pending callee/return analysis.  A static call pattern alone does not specify a loop-frame ABI.

In the fast object `$0B05` initializes `$0B2E` to 1.  Here the loop control can be read directly:

```text
0B0A  AD 2E 0B  LDA $0B2E     ; body
0B0D  8D 00 04  STA $0400
0B10  EE 2E 0B  INC $0B2E
0B13  AD 2E 0B  LDA $0B2E
0B16  F0 06     BEQ $0B1E     ; zero after increment exits
0B18  C9 03     CMP #$03
0B1A  90 EE     BCC $0B0A     ; below limit: repeat
0B1C  F0 EC     BEQ $0B0A     ; equal: repeat; above: fall through
```

The backward displacements are relative to the following instruction, not the branch opcode.  Both reach the load at `$0B0A`.  Thus this particular directive change selected inline increment/compare control in place of a call-based form.  Of the net 603 bytes saved, 601 came from the routines region, and two from the program region.  The bytes predict the fast loop's behavior when entered normally; neither target was run, and no speedup or whole-program equivalence was measured.

For a separately compiled WORD counter, see [low-byte wrap versus whole-counter wrap](basicboss-word-counter.md).  Changing only bit 8 of the upper bound identifies the high immediate without guessing from a zero.

## Counterexamples and transfer limits

- Delete only line 30 from the fast source.  In the observed compile the wrapper exited zero and wrote 801 bytes, **but both passes reported** `21/FOR OHNE NEXT (_FASTFOR)` at reported line `65535`.  Refuse that object.  Separately, the wrapper notes warn that a non-BASIC input can yield an empty shell without a diagnostic -- reject it at input validation rather than trying to disassemble the shell.
- The [manual, FASTFOR/SLOWFOR section](https://github.com/mbergmann-sh/basicbossGUI/blob/d27331c334003b63554139a7aead82236f823c6b/bbcompiler-src/BasicBoss.txt#L659-L674) limits the fast form to byte or word counters, ordered paired `FOR`/`NEXT`, and a literal step if supplied.  It describes fallback for other counter types and warns about a changing end variable.  These are documentation claims, not additional tested cases.  A directive can be switched off later in the same program; neither its presence nor one matching `INC`/branch sequence identifies an unfamiliar loop, compiler, or original source spelling.
- Rights are component-specific.  The [GUI README](https://github.com/mbergmann-sh/basicbossGUI/blob/d27331c334003b63554139a7aead82236f823c6b/README.md) describes Michael Bergmann's interface as public domain *with restrictions*, mentions Qt licensing separately, and makes a broader historical acknowledgement.  The [component readme](https://github.com/mbergmann-sh/basicbossGUI/blob/d27331c334003b63554139a7aead82236f823c6b/bbcompiler-src/readme.txt) limits “freeware” to Marco Timm's `bbcompiler.c` emulator and attributes rights in Thilo Herrmann's original BASIC-BOSS and its manual to WEKA, successor to Markt & Technik.  Do not infer a blanket redistribution grant for the compiler image, disk, manual, ROMs, or bundled executables.  This method requires none of those materials to accompany the reference.
