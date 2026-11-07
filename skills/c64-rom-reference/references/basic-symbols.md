# C64 BASIC ROM Symbols — `$A000-$BFFF`

Reference for 6502 disassembly of Commodore 64 software that calls into, hooks, or reuses routines in the BASIC V2 ROM.

Primary C64 ROM-disassembly reference:
https://www.pagetable.com/c64ref/c64disasm/

Official historical Microsoft source:
https://github.com/microsoft/BASIC-M6502

Microsoft publishes the complete Microsoft BASIC for 6502 Version 1.1 source under the MIT License. It is the preferred official reference for ancestral algorithms, symbols, and comments, but it is not an exact source tree or direct build recipe for the later stock C64 BASIC V2 ROM. It also does not represent Commodore's separate KERNAL implementation.

The pagetable.com disassembly presents several C64-specific commentary sources side-by-side. This file is a deliberately condensed analysis reference, drawing primarily from the **Microsoft/Commodore Source** and **Lee Davison** commentary while checking historical intent against Microsoft's official repository where applicable. The construction source is pinned at `mist64/c64ref` commit `7cae8b91d5317d1d18ae8cdcaac03533389e6032`; see [SOURCES.md](SOURCES.md) for provenance, terms and the retained BSD notice.

## Scope

This file follows the **physical ROM boundary**, not functional ownership:

- Included here: `$A000-$BFFF`
- Not included here: `$E000-$E39F`, even though that region contains the continuation of BASIC routines and BASIC startup/command support inside the KERNAL ROM.

See `kernal-symbols.md` for all symbols at `$E000-$FFFF`.

## Disassembly guidance

**Audit status:** several legacy labels in this condensed table were disproved by pinned bytes during compiler work (including confusion between arithmetic, rounding, comparison and constant data). The corrected rows identify their evidence; the remaining table has not received an exhaustive entry-by-entry audit. A ROM hash pins the bytes, not the accuracy of every label below. Verify consequential entries against code/data and callers before using their names.

The variable/array rows `$B113`, `$B185`, `$B194`, `$B1D1`, and `$B245`, and the arithmetic/conversion rows `$B8D2`, `$B947`, `$BC49`, `$BC9B` (formerly mislabeled at `$BCA0`), and `$BCB0` have also been checked against BASIC revision `901226-01` and both pinned commentary listings.  Their contracts assume mapped stock ROM, binary arithmetic mode, and valid caller workspace; this is not certification of the remaining table.

The control/line-handling entries `$A408`, `$A435`, `$A474`, `$A483`, `$A49C`, and `$A57C`, and the parameter/conversion entries `$B7EB`, `$B7F7`, `$B80D`, `$BC23`, `$BCCC`, and `$BD0C` have also been checked against the pinned BASIC ROM and both commentary listings.  Stock KERNAL revision `901227-03` establishes the default RAM-vector targets.  `$A483`, `$A57C`, and `$BCCC` retain their correct identities; `$BD0C` is an operand, not an entry.  These are state-dependent internal contracts, not stable APIs or certification of uninspected rows.

- A `JSR` or `JMP` into this ROM is strong evidence that software is reusing BASIC internals, but many entry points are **internal routines**, not stable APIs.
- BASIC heavily depends on zero-page workspace described in `c64-rom-workspace.md`.
- Calls into arithmetic routines usually operate on the BASIC floating-point accumulator (`FAC`) at `$61-$66` and/or secondary accumulator (`ARG`) at `$69-$6E`.
- Many parsing routines expect `TXTPTR` (`$7A/$7B`) and `CHRGET/CHRGOT` state to be valid.
- Do not rename a caller solely from one BASIC call. Interpret the data flow and surrounding calls.

---

# ROM header and dispatch tables

| Address | Symbol | Meaning |
|---|---|---|
| `$A000` | `BASIC_COLD_VECTOR` | Pointer to BASIC cold-start entry (`$E394`) |
| `$A002` | `BASIC_WARM_VECTOR` | Pointer to BASIC warm-start entry (`$E37B`) |
| `$A004` | `CBMBASIC_ID` | `"CBMBASIC"` ROM identification string |
| `$A00C` | `STMDSP` | 35 little-endian handler-minus-one words for statement tokens `$80` through `$A2`; `$A7F9/$A7FD` push high/low bytes, then CHRGET's RTS transfers to the handler.  Data, not an executable entry. |
| `$A052` | `FUNDSP` | 23 little-endian direct function-entry words for tokens `$B4` through `$CA` (SGN through MID$), including USR's RAM stub `$0310`; `$AFD6` copies the selected word to `$55/$56`, then calls the initialized JMP stub at `$0054`.  Unlike STMDSP, entries are not decremented. |
| `$A080` | `OPTAB` | Ten three-byte evaluator records: precedence followed by a little-endian handler-minus-one word.  `$ADF1` reads precedence, and `$AE20` pushes the vector for later RTS dispatch; data, not an executable entry. |
| `$A09E` | `RESLST` | BASIC reserved-word/token text table |
| `$A19E` | `ERRTAB` | BASIC error-message text table |
| `$A328` | `ERRPTR` / error pointer table | Error-message pointer/offset data |

### Statement handler targets

High-value token handlers include:

| Address | Handler |
|---|---|
| `$A65E` | CLR |
| `$A69C` | LIST |
| `$A71A` | token-to-text/list helper |
| `$A742` | FOR |
| `$A7AE` | next-statement interpreter loop (`NEWSTT`; colon/EOL at TXTPTR required) |
| `$A7E4` | execute BASIC statement (`IGONE` default target) |
| `$A81D` | RESTORE |
| `$A82F` | STOP |
| `$A831` | END |
| `$A857` | CONT |
| `$A871` | RUN |
| `$A883` | GOSUB |
| `$A8A0` | GOTO |
| `$A8D2` | RETURN |
| `$A8F8` | DATA |
| `$A928` | IF |
| `$A93B` | REM |
| `$A94B` | ON |
| `$A96B` | line-number parser (`LINGET`; A/carry from CHRGET/CHRGOT required) |
| `$A9A5` | LET |
| `$AA80` | PRINT# |
| `$AA86` | CMD |
| `$AAA0` | PRINT |
| `$ABBF` | INPUT |
| `$ABA5` | INPUT# |
| `$AC06` | READ |
| `$AD1E` | NEXT |
| `$B081` | DIM |
| `$B3B3` | DEF FN |
| `$B824` | POKE |
| `$B82D` | WAIT |

LOAD, SAVE, VERIFY, SYS, OPEN, CLOSE, GET and several other BASIC commands dispatch to routines physically located in the KERNAL ROM; see `kernal-symbols.md`.

---

# BASIC startup, line handling, editing, and execution

| Address | Suggested symbol | Meaning / disassembly use |
|---|---|---|
| `$A408` | `REASON` / check memory | Require address A/Y (low/high) below string-space bottom `$33/$34`; garbage-collect and retry if needed, otherwise enter OUT OF MEMORY error.  Returns A/Y unchanged and C=0 on success; not the error dispatcher |
| `$A435` | `OMERR` / OUT OF MEMORY | Load X=$10, then dispatch through `$A437: JMP ($0300)`; not the READY prompt |
| `$A474` | `READY` | Print READY., enable KERNAL control messages, then dispatch through main-loop vector `$0302` (default `$A483`); not the input-reading body |
| `$A483` | `IMAIN_DEFAULT` | Default RAM-vector target for BASIC main loop |
| `$A49C` | `MAIN1` / numbered-line editing | Internal path after input: parse line number, tokenize, and insert, replace, or delete a stored BASIC line; requires numeric CHRGET/TXTPTR state, not keyboard input |
| `$A533` | `LNKPRG` | Rebuild stored BASIC line links from TXTTAB `$2B/$2C`, scanning NUL-terminated line bodies and rewriting next-line pointers via `$22/$23`; not tokenization |
| `$A57C` | `ICRNCH_DEFAULT` | Default tokenizer vector target |
| `$A613` | `FNDLIN` | Search linked program from TXTTAB for line `$14/$15`; C=1 on exact match, otherwise C=0 with `$5F/$60` at the first greater line or end marker; no error on a miss |
| `$A642` | `NEW` | NEW command; unconditional body at `$A644` clears the program and resets BASIC pointers |
| `$A65E` | `CLR` | Require Z=1 from statement-terminator state; otherwise return unchanged.  Reset variable/array/string allocation pointers, DATA position, and temporary descriptors; invalidate CONT and reset the CPU stack, preserving only the immediate return address.  Call KERNAL CLALL; not a memory wipe or stack-preserving subroutine. |
| `$A68E` | `STXTPT` | Set TXTPTR `$7A/$7B` to TXTTAB `$2B/$2C` minus one in binary mode; does not clear variables, reset the stack, or start execution |
| `$A69C` | `LIST` | Parse an optional line/range using CHRGET-compatible A/C/Z and TXTPTR state, then list tokenized program text through `$0306`.  Accepted arguments discard the interpreter return frame and finish through `$E386`; not a returning text-output helper. |
| `$A6EF` | `PRIT4` / LIST print tail | Restore Y from `$49`, clear bit 7 of character A, print via `$AB47`, then continue LIST; requires active LIST workspace, not a token-to-keyword entry |
| `$A71A` | `IQPLOP_DEFAULT` | Default LIST/token-print vector target |
| `$A742` | `FOR` | FOR statement |
| `$A7AE` | `NEWSTT` | Interpreter next-statement loop: check STOP, save continuation state outside page `$02`, require colon/EOL at TXTPTR, advance line state, and dispatch through `$0308`; BASIC execution/stack state required |
| `$A7E1` | `IGONE_DISPATCH` | `JMP ($0308)` statement-execution trampoline; stock target `$A7E4` advances CHRGET before dispatch, so TXTPTR must precede the next statement, not point at its token |
| `$A7E4` | `IGONE_DEFAULT` | Default statement execution vector target |
| `$A81D` | `RESTORE` | Reset DATA pointer |
| `$A82F` | `STOP` | STOP statement |
| `$A831` | `END` | Require Z=1 from a statement terminator; otherwise return.  Save TXTPTR/current line for CONT in program mode, discard the interpreter return frame, and enter `$E386` without printing BREAK; not an ordinary returning subroutine. |
| `$A857` | `CONT` | Require Z=1 from a statement terminator; otherwise return.  If `$3E=0`, report CAN'T CONTINUE; otherwise restore TXTPTR from `$3D/$3E` and current line from `$3B/$3C`, then RTS into interpreter continuation. |
| `$A871` | `RUN` | Disable KERNAL messages while preserving incoming status for argument selection.  With Z=1, reset TXTPTR and clear BASIC state through `$A659`; otherwise clear through `$A660` before parsing/locating the requested line through `$A897`.  Requires interpreter text/stack state; errors can occur after clearing. |
| `$A883` | `GOSUB` | Interpreter statement entry: stack-check, push TXTPTR `$7A/$7B`, current line `$39/$3A`, and token `$8D` as a five-byte frame; refresh CHRGOT, call GOTO `$A8A0`, then jump to `$A7AE`.  Requires BASIC text/stack state; not an ordinary returning subroutine. |
| `$A8A0` | `GOTO` | Parse target with `$A96B` (A/carry and TXTPTR from CHRGET/CHRGOT required); search linked BASIC lines via `$A617`, set TXTPTR to found header minus one, and RTS into interpreter continuation.  Missing target enters UNDEF'D STATEMENT; not a CPU jump to that line. |
| `$A8D2` | `RETURN` | Require Z=1 from a statement terminator; otherwise RTS.  Discard intervening FOR frames, require a `$8D` GOSUB frame, restore current line/TXTPTR, then skip the saved GOSUB statement via `$A8F8`; missing frame is RETURN WITHOUT GOSUB.  Requires interpreter stack state. |
| `$A8F8` | `DATA` | DATA statement skip/scanner |
| `$A906` | `DATAN` | Scan from TXTPTR without changing it; return Y=offset and A=colon outside quotes or NUL (NUL always stops).  Clobbers X and `$07/$08`; caller advances TXTPTR |
| `$A928` | `IF` | Evaluate with `$AD9E`, accept GOTO or require THEN, and test FAC exponent `$61`.  Zero skips the entire remaining line via REM `$A93B`; nonzero uses GOTO for a numeric line target or statement dispatch `$A7ED`.  Requires evaluator/text/stack state. |
| `$A93B` | `REM` | Scan from TXTPTR to line-ending NUL via `$A909` (colons do not stop), then add returned Y to TXTPTR through `$A8FB` and RTS.  Also the false-IF tail; requires valid BASIC line/text state. |
| `$A94B` | `ONGOTO` | Obtain a byte selector via `$B79E`; require GOTO/GOSUB and count a one-based comma-separated line list in `$65`.  Dispatch the selected token through `$A7EF`, or RTS after exhausting the list; requires interpreter text/stack state, not a native jump table. |
| `$A96B` | `LINGET` | Initialize `$14/$15` and parse decimal digits using A/carry from CHRGET/CHRGOT; leave A/TXTPTR at terminator.  Intended range 0..63999; overflow branches via `$A953`, with a high-byte-$89 exception into ON machinery, not a guaranteed error |

### Agent interpretation notes

Calls to `$A533` rebuild stored BASIC line links; calls to `$A57C` tokenize source through the stock tokenizer body.

Calls to `$A613` or `$A96B` often indicate line-number handling.

Calls to `$A7E4` are especially significant: software may be handing a tokenized statement back to the BASIC interpreter.

---

# Assignment, PRINT, INPUT, READ, and data conversion

| Address | Suggested symbol | Meaning |
|---|---|---|
| `$A9A5` | `LET` | LET / assignment |
| `$AA80` | `PRINTN` | PRINT# |
| `$AA86` | `CMD` | CMD |
| `$AAA0` | `PRINT` | PRINT statement |
| `$AAE8` | `PRINT_COMMA_ZONE` | PRINT comma continuation: read cursor column via `$FFF0`, emit `10-(column MOD 10)` spacing characters via `$AB3B`, then resume PRINT at `$AAA2`; not string output |
| `$AB1E` | `STROUT` | Build a literal-string descriptor from A/Y via `$B487`, then output the string; not a spacing-only helper |
| `$AB3B` | `PRINT_SPACING` | Emit cursor-right `$1D` for console (`$13=0`), otherwise space `$20`; verified against pinned ROM |
| `$AB45` | `OUTQST` | Output literal `?` through `$AB47`; alternate entry within BIT-skip sequence |
| `$AB4D` | `INPUT_ERROR` | Bad INPUT/GET/READ field path, selected by `$11`; INPUT may issue REDO FROM START, other paths report errors |
| `$ABA5` | `INPUTN` | INPUT# |
| `$ABBF` | `INPUT` | INPUT |
| `$ABF9` | `QINLIN` | If `$13=0`, output `?` plus cursor-right, then read a CR-terminated line via `$A560` into `$0200`; return X/Y=$FF/$01, not a converted field |
| `$AC06` | `READ` | READ statement |
| `$ACFC` | `EXIGNT` (data) | Message bytes `?EXTRA IGNORED`, CR, NUL; referenced by `$ACF4-$ACF8` for leftover console INPUT text, not an executable parser |
| `$AD1E` | `NEXT` | NEXT statement |

When interpreting calls in this area, inspect:

- `INPFLG` (`$11`)
- `DATPTR` (`$41/$42`)
- `INPPTR` (`$43/$44`)
- current variable pointer/name
- string-vs-numeric type flags

---

# Expression parser and operators

| Address | Suggested symbol | Meaning |
|---|---|---|
| `$AD8A` | `FRMNUM` | Evaluate expression and require numeric result |
| `$AD9E` | `FRMEVL` | General expression evaluator |
| `$AE83` | `IEVAL_DISPATCH` | `JMP ($030A)` arithmetic-element hook; stock target `$AE86`, called by `$ADB1` with evaluator stack state and TXTPTR before the element |
| `$AE86` | `IEVAL_DEFAULT` | Default expression evaluator vector target |
| `$AEF1` | `PARCHK` | Require opening parenthesis, evaluate expression via `$AD9E`, then require closing parenthesis via `$AEF7` |
| `$AF08` | `SYNTAX_ERROR` | Load error index X=$0B and jump to BASIC error dispatcher `$A437`; parenthesized-expression entry is `$AEF1` |
| `$AF48` | `TI_STRING_VALUE` | Internal TI$ value path: read jiffy clock via `$AF84`, format six HHMMSS digits via `$BE68`, and return a temporary string through `$B46F`; variable parsing starts at `$AF28` |
| `$AF7B` | `READ_TIME_FAC` | Read jiffy clock via `$AF84` / KERNAL RDTIM `$FFDE`, normalize into FAC; not FRE. Pinned bytes verified. |
| `$AFA7` | `ISFUN` / function dispatch | Double function token in A, parse arguments, select vector from `$A052` table via indexed `$9FEA/$9FEB`, and call through `$0054`; not a string type-check entry |
| `$AFE6` | `OR` | Bitwise OR of range-checked signed 16-bit conversions of FAC and ARG; return numeric FAC, not necessarily 0 or −1. |
| `$AFE9` | `AND` | Bitwise AND; same operand/result contract as `$AFE6`. |
| `$B016` | `DOREL` | Relational evaluator: check matching operand types using incoming carry and `$0D`, dispatch numeric/string comparison, and apply `$12` relation mask; return numeric FAC, −1 true or 0 false. |
| `$B01B` | `NUMCMP` | Numeric continuation of `$B016`, bypassing type checking; pack ARG's sign into `$6A`, compare against FAC, and apply `$12`; not a standalone three-way comparator. |
| `$B02E` | `STRCMP` | String continuation of `$B016`: lexicographic byte comparison with length tie-break, temporary-string cleanup, and masked −1/0 numeric result. |
| `$B081` | `DIM` | DIM statement / array creation |

### Parser expectations

Expression routines are not standalone math APIs. They generally expect:

- `TXTPTR` to reference BASIC text,
- CHRGET-compatible parser state,
- BASIC type flags to be valid,
- zero-page variable/string workspace to be available.

---

# Variables and arrays

| Address | Suggested symbol | Meaning |
|---|---|---|
| `$B08B` | `PTRGET` | Parse variable/array reference at BASIC text pointer; return value/descriptor/element pointer (A=low, Y=high); may allocate; missing-scalar handling depends on caller |
| `$B0E7` | `ORDVAR` | Search ordinary variable table |
| `$B113` | `ISLETC` | Test A for `"A"`..`"Z"`: carry set iff letter, with A restored in binary mode; not variable creation |
| `$B185` | `FINPTR` / scalar-value pointer | Return scalar record `$5F/$60` plus two in A/Y and `$47/$48`, skipping its name bytes; not an array path |
| `$B194` | `FMAPTR` / array-data pointer | Form first-element pointer in A/Y and `$58/$59` from descriptor base `$5F/$60` and bounded dimension count `$0B`; no descriptor search |
| `$B1D1` | `ISARY` / array lookup and creation | Parse subscripts or DIM bounds, find or create array, and return element pointer for references, not the separate DIM tail; BASIC parser, workspace, and stack state required |
| `$B245` | `BAD_SUBSCRIPT_ERROR` | Load X=$12 and enter BASIC error dispatcher `$A437` (BAD SUBSCRIPT); not element-offset calculation |
| `$B34C` | `UMULT` | Unsigned 16×16 multiply for arrays: `$71/$72` times descriptor factor low byte at `($5F),Y`, high byte at offset Y−1; return X=low, A=Y=high.  Consumes `$71/$72`; overflow enters OUT OF MEMORY rather than wrapping. |
| `$B37D` | `FRE` | FRE(): evaluated argument; garbage-collect strings, then return free-byte count in FAC via signed 16-bit conversion; may relocate strings |
| `$B391` | `GIVAYF` | Convert signed two's-complement 16-bit integer (A=high, Y=low) to FAC; sets numeric type and overwrites FAC and scratch state |
| `$B39E` | `POS` | POS(): SEC / JSR `$FFF0` reads cursor column into Y, then falls through to `$B3A2` |
| `$B3A2` | `SNGFLT` / unsigned Y to FAC | Set A=0 and branch to `$B391`; converts Y (0..255) to FAC without reading cursor position |
| `$B3B3` | `DEF` | DEF FN |
| `$B3E1` | `GETFNM` | Require FN token, parse numeric function name, and return definition-record pointer in A/Y and `$4E/$4F` (low/high); FN evaluation starts at `$B3F4` |

### Internal-call cautions

`PTRGET` parses through `$7A/$7B`, not an A/Y name pointer.  It requires initialized BASIC parser, variable-table, and stack state; incoming `$10` affects name/array interpretation.  Ordinary scalar/array-element returns set `$47/$48`, but dummy-zero returns do not.  A missing scalar reached with stacked return-address low byte `$2A` returns the dummy pointer `$BF13` instead of allocating; the ROM tests only that low byte, not the full caller address.  TI$ also uses the dummy-pointer tail.  Parsing changes text/type/workspace state, and allocation can move array storage; this is not a pure lookup or a general-purpose standalone API.

`FRE` receives an already evaluated argument, ignores its numeric value, and requires valid descriptor state for a string argument.  Its free-byte count uses signed conversion, so counts with bit 15 set become negative FAC values.  `GIVAYF` takes A=high and Y=low, the reverse register byte order of `PTRGET`'s returned pointer.  These are static contracts for mapped BASIC revision `901226-01`, with valid stock workspace and binary arithmetic mode, not new runtime validation or stable APIs.

Evidence: the pinned [PTRGET paths](https://github.com/mist64/c64ref/blob/7cae8b91d5317d1d18ae8cdcaac03533389e6032/src/c64disasm/c64disasm_ms.txt#L3809-L3972), [array-element return](https://github.com/mist64/c64ref/blob/7cae8b91d5317d1d18ae8cdcaac03533389e6032/src/c64disasm/c64disasm_ms.txt#L4279-L4282), and [FRE/GIVAYF instructions](https://github.com/mist64/c64ref/blob/7cae8b91d5317d1d18ae8cdcaac03533389e6032/src/c64disasm/c64disasm_ms.txt#L4323-L4340).

---

# String handling

| Address | Suggested symbol | Meaning |
|---|---|---|
| `$B465` | `STR` / STR$ | Require numeric FAC, format via `$BDDF` with Y=0, discard function-dispatch return, then construct string descriptor via `$B487` |
| `$B475` | `STRINI` | Save incoming descriptor pointer `$64/$65` in `$50/$51`, allocate A bytes via `$B4F4`, and build descriptor at `$61-$63`; not a literal scan |
| `$B487` | `STRLIT` | Scan literal at A/Y until quote or NUL, construct descriptor, copy utility/input-buffer strings when needed, then enter `$B4CA`; no character output |
| `$B4CA` | `PUTNEW` | Push descriptor from `$61-$63` onto temporary descriptor stack, set string type/pointer, or report STRING TOO COMPLEX; not character-space allocation |
| `$B4F4` | `GETSPA` | Allocate A character bytes downward in string space; may garbage-collect/retry or report OUT OF MEMORY; returns A=length and X/Y=pointer |
| `$B526` | `GARBA2` | Compact live heap strings found through temporary, scalar, and array descriptors; update descriptors and `$33/$34` from initialized BASIC memory tables.  Allocator retry/error wrapper `GARBAG` starts at `$B516` |
| `$B63D` | `CAT` | Expression-evaluator path: `$64/$65` points to left-string descriptor, and TXTPTR points at `+`; evaluate right operand, require string, allocate/copy result, then reenter `$ADB8`.  Length >255 reports STRING TOO LONG; requires evaluator stack/state, not a two-pointer JSR interface |
| `$B67A` | `MOVINS` | Copy characters described by the three-byte descriptor at `$6F/$70` to already allocated `$35/$36`, descending by byte index; advance `$35/$36` by length.  Does not allocate, free, or construct a descriptor |
| `$B6A3` | `FRESTR` | Require string type and descriptor pointer `$64/$65`, or report TYPE MISMATCH; return A=length, X/Y=data pointer (low/high), also `$22/$23`.  Pop only the newest temporary descriptor; reclaim characters only if that descriptor was popped and its data starts at `$33/$34` |
| `$B6DB` | `FRETMS` | Compare descriptor address A/Y (low/high) with `$17/$18`; only on equality set `$16` to its low byte and subtract 3 from `$17`.  Return Z=1 on pop, Z=0 otherwise; does not reclaim character storage |
| `$B6EC` | `CHR` / CHR$ | Convert FAC to byte, allocate one character, store it, and finish through descriptor-stack entry `$B4CA`; BASIC function-dispatch calling state required |
| `$B700` | `LEFT` | LEFT$() entry; argument/descriptor stack setup via `$B761` |
| `$B70D` | `SUBSTRING_COPY_LENGTH` | Internal substring tail: X=length, start offset already pushed, `$50/$51`=descriptor pointer; not CHR$ entry |
| `$B72C` | `RIGHT` | RIGHT$() entry; derive start offset then share LEFT$ tail at `$B706` |
| `$B737` | `MID` | MID$() entry; default length 255, optional length parsing and shared substring-copy tail |
| `$B73D` | `MID_CHRGOT_OPERAND` | Operand byte $00 of JSR `$0079` at `$B73B`; not an instruction/function entry. MID$ starts `$B737`. |
| `$B761` | `PREAM` | LEFT$/RIGHT$/MID$ internal setup: require closing `)` or report SYNTAX ERROR, discard function-dispatch return, and pull pre-stacked byte parameter and descriptor pointer.  Return A=X=byte, Y=0, `$50/$51`=descriptor pointer; requires the exact substring-function CPU-stack layout |
| `$B77C` | `LEN` | LEN() |
| `$B78B` | `ASC` | ASC() |
| `$B79B` | `GTBYTC` | Advance CHRGET, evaluate numeric expression via `$B79E`, range-convert to byte in X via `$B7A1`, then CHRGOT; VAL is `$B7AD` |
| `$B7AD` | `VAL` | VAL(): string descriptor to numeric FAC; empty string yields zero. Nonempty path temporarily NUL-terminates writable string, calls `$BCF3`, then restores terminator and TXTPTR on normal return. |
| `$B7EB` | `GETNUM` | Parse numeric address expression via `$AD8A/$B7F7`, require comma, then parse byte via `$B79E`; returns address in `$14/$15` and byte in X (POKE/WAIT setup) |
| `$B7F7` | `GETADR` | Convert nonnegative FAC <65536 to truncated address in `$14/$15` (low/high), Y=low/A=high; standard FAC/QINT workspace required; negative or >=65536 is ILLEGAL QUANTITY |
| `$B80D` | `PEEK` | PEEK(): convert FAC address via `$B7F7`, read mapped byte, and return unsigned-byte FAC via `$B3A2`; preserves `$14/$15` on normal return |
| `$B824` | `POKE` | POKE |
| `$B82D` | `WAIT` | WAIT |

---

# Numeric input and floating-point conversion

| Address | Suggested symbol | Meaning |
|---|---|---|
| `$B849` | `ADD_HALF_FAC` | Add packed constant 0.5 at `$BF11` to FAC via `$B867`; not text-number input |
| `$B867` | `FADD` | Add packed memory operand at A/Y to FAC; loads ARG via `$BA8C` |
| `$B8D2` | `FADFLT` / carry-controlled normalization | Internal arithmetic/conversion tail: C=0 complements FAC sign and two's-complements mantissa plus `$70` before normalization; C=1 skips negation.  Prepared FAC state required; not numeric-text parsing |
| `$B947` | `NEGFAC` / negate signed mantissa | Complement `$66` and two's-complement `$62-$65` plus extension `$70`; exponent unchanged.  Internal helper, not packed-memory addition or general floating-point unary minus |
| `$B9BC` | `FLOAT_CONSTANT_ONE` | **Data**, packed float 1 (`81 00 00 00 00`); verified against pinned ROM and BASIC-64 FOR consumer. |
| `$B9C2` | `LOG_COEFFICIENT_0` | **Data**, first packed coefficient (`7F 5E 56 CB 79`) following LOG series count at `$B9C1`; not executable FADD |
| `$BA28` | `MULTIPLY_MEMORY_FAC` | Load packed memory operand at A/Y into ARG, set sign workspace and FAC-exponent flags via `$BA8C`, then fall through to `$BA2B` |
| `$BAE2` | `MULTIPLY_FAC_TEN` | Multiply FAC by ten, using rounded FAC-to-ARG copy and exponent/addition steps |
| `$BB0F` | `DIVIDE_MEMORY_BY_FAC` | Load packed memory operand at A/Y into ARG, then enter division at `$BB12`; pinned bytes verified. |
| `$BB8A` | `DIVISION_BY_ZERO_ERROR` | Load X=$14 and jump to BASIC error dispatcher `$A437` |
| `$BC0C` | `MOVAF` / round and copy FAC to ARG | Call `$BC1B`, then copy FAC to ARG via `$BC0F`; historical MOVFA is the reverse transfer at `$BBFC` |
| `$BC0F` | `MOVEF` | Copy FAC to ARG without normal rounding path |
| `$BC1B` | `ROUND_FAC` | Round FAC from extension byte `$70`; verified against pinned ROM. Memory-to-FAC entry is `$BBA2`. |
| `$BC23` | `INCRND` | Unchecked FAC-mantissa increment; skips zero/round-bit tests at `$BC1B`; C=1 required if increment rolls over, then normalize via `$B938` (may OVERFLOW) |
| `$BC49` | `FLOATC` / fixed-to-FAC tail | Clear `$64/$65/$70/$66`, set exponent from X, and normalize prepared `$62/$63` using incoming carry for sign adjustment; C=1 and X=$90 convert an unsigned 16-bit value.  Not arbitrary FAC normalization |
| `$BCCC` | `INT` | INT() |
| `$BCF3` | `FIN` | Parse text number into FAC using CHRGET/TXTPTR and initial character/carry state; entered from `$AE8F` and VAL `$B7DA` |
| `$BDCD` | `LINPRT` | Print unsigned 16-bit integer A=high/X=low: construct FAC, format, then tail-call string output `$AB1E`; not FAC-to-string-only entry |
| `$BDDD` | `FOUT` | Convert FAC to NUL-terminated decimal text at `$0100`; sets Y=1 before `$BDDF` and returns pointer A=$00/Y=$01 |
| `$BF11` | `FLOAT_CONSTANT_HALF` | **Data**, packed 0.5 (`80 00 00 00 00`) at `$BF11-$BF15`, used by `$B849`; not code |

### Important convention

The exact calling convention varies by routine. Before treating one as a reusable API, inspect the source commentary around that entry point and confirm:

- FAC/ARG inputs,
- pointer inputs,
- flags,
- register preservation,
- temporary zero-page requirements.

---

# Multiplication, division, sign, and comparison

| Address | Suggested symbol | Meaning |
|---|---|---|
| `$BA2B` | `MULTIPLY_ARG_FAC` | Multiply prepared ARG by FAC; requires Z to reflect FAC exponent and sign workspace `$6F` prepared. Operator record at `$A086` stores target-minus-one at `$A087-$A088`; memory-input entry is `$BA28`. |
| `$BAE2` | `MULTIPLY_FAC_TEN` | Multiply FAC by ten; not negation |
| `$BB0F` | `DIVIDE_MEMORY_BY_FAC` | Packed memory operand at A/Y divided by FAC; `$BB12` uses prepared ARG/FAC, sign workspace `$6F` and Z reflecting FAC exponent. Not addition. |
| `$BB2B` | `DIVISION_COMPARE_MANTISSAS` | Internal division loop: compare ARG mantissa against FAC, with Y already holding ARG high byte; not a standalone complement helper |
| `$BB7E` | `DIVISION_ROUND_AND_NORMALIZE` | Internal division tail; division workspace and saved status on CPU stack required. Shift A left six times into `$70`, restore status, then tail-call `$BB8F`; `$BB7B` is an immediate operand of LDA #$40 at `$BB7A`, not an entry |
| `$BC2B` | `SIGN` | Return FAC sign in A: $FF negative, $00 zero, $01 positive; does not produce a floating SGN result (that entry is `$BC39`) |
| `$BC5B` | `COMPARE_FAC_MEMORY` | Compare FAC against packed float at A/Y; result -1/0/+1 in A. Verified against pinned ROM. |
| `$BC9B` | `QINT` / FAC to fixed integer | Destructively form fixed-integer bytes `$62-$65` from caller-range-checked FAC; not a normalized floating result or a round-FAC-first operation.  `$BCA0` is internal SBC #$A0 and requires A=nonzero FAC exponent and C=1 |
| `$BCB0` | **Operand, not entry** | Immediate `$61` in `$BCAF: A2 61` (`LDX #$61`), selecting FAC workspace in QINT; not FADD_ONE or a packed floating-point constant |
| `$BD0C` | `FIN_CHRGET_OPERAND` | Operand byte $00 of JSR `$0073` at `$BD0A` within FIN; not an instruction/function entry or decimal-output helper |

Because many internal math labels vary by source, prefer the address plus a descriptive semantic name when exact historical symbol names are uncertain.

---

# BASIC functions and math functions

| Address | Function / routine |
|---|---|
| `$B37D` | FRE() |
| `$B39E` | POS() (cursor-column read; `$B3A2` is only the unsigned-Y conversion tail) |
| `$B6EC` | CHR$() |
| `$B700` | LEFT$() |
| `$B72C` | RIGHT$() |
| `$B737` | MID$() |
| `$B77C` | LEN() |
| `$B78B` | ASC() |
| `$B7AD` | VAL() |
| `$B7EB` | POKE/WAIT parameter parser: address expression, comma, byte expression; `$14/$15`=address and X=byte |
| `$B80D` | PEEK(): FAC address -> mapped byte -> numeric FAC; preserves `$14/$15` on normal return |
| `$B824` | POKE |
| `$B82D` | WAIT |
| `$BCCC` | INT() |
| `$BCF3` | numeric string -> FAC (CHRGET state required) |
| `$BDDD` | FAC -> printable numeric string |

Functions whose implementation is physically in `$E000-$E39F` are intentionally documented in `kernal-symbols.md`.

---

# High-value BASIC entry points for disassembly

```text
$A408 REASON           check A/Y below string space; collect/retry or OUT OF MEMORY
$A435 OMERR            OUT OF MEMORY; X=$10 then error vector $0300
$A474 READY            print READY., then main-loop vector $0302
$A533 LNKPRG           rebuild stored BASIC line links
$A57C ICRNCH_DEFAULT   tokenizer RAM-vector target
$A613 FNDLIN           search $14/$15; C=match, $5F/$60=insertion/end pointer
$A65E CLR
$A69C LIST
$A71A IQPLOP_DEFAULT   LIST/token expansion vector target
$A7E4 IGONE_DEFAULT    statement execution vector target
$A81D RESTORE
$A831 END
$A857 CONT
$A871 RUN
$A883 GOSUB
$A8A0 GOTO
$A8D2 RETURN
$A928 IF
$A96B LINGET           parse line number
$A9A5 LET
$AAA0 PRINT
$ABBF INPUT
$AC06 READ
$AD1E NEXT
$AD9E FRMEVL           expression evaluator
$AE86 IEVAL_DEFAULT    expression evaluator RAM-vector target
$B081 DIM
$B08B PTRGET           find/create variable
$B391 GIVAYF           16-bit integer A/Y -> FAC
$B4F4 GETSPA           allocate string character space
$B526 GARBA2           compact live heap strings; GARBAG retry wrapper is $B516
$B6EC CHR$
$B700 LEFT$
$B72C RIGHT$
$B737 MID$
$B77C LEN
$B78B ASC
$B7AD VAL
$B7EB GETNUM            POKE/WAIT: address, comma, byte; $14/$15=address, X=byte
$B80D PEEK              FAC address -> byte value in FAC; preserves $14/$15
$B824 POKE
$B82D WAIT
$B867 FADD             packed memory operand + FAC
$BCCC INT
$BCF3 FIN              text number -> FAC (CHRGET state required)
$BDDD FOUT             FAC -> printable decimal
```

---

# Interpretation cautions

1. **Internal BASIC routines are not a formal API.** A game may use them because they are convenient, but their calling conventions can be subtle.

2. **Many calls require BASIC zero page to be intact.** Check `c64-rom-workspace.md` before assuming a standalone machine-language caller can safely invoke a routine.

3. **Parser calls imply parser state.** Calls into expression/token routines usually depend on `TXTPTR`, CHRGET, type flags, and BASIC text formatting.

4. **FAC/ARG are global workspaces.** Floating-point calls commonly destroy or transform them.

5. **A BASIC keyword handler may have useful internal entry points.** A call into the middle of PRINT or INPUT does not necessarily mean the BASIC statement itself is being executed.

6. **The ROM continues in `$E000-$E39F`.** Do not treat `$BFFF` as the end of BASIC functionality—only the end of the BASIC ROM chip/address region.

7. **Prefer semantic comments.** For `JSR $B391`, a useful comment is `; convert signed 16-bit A=high/Y=low to BASIC float in FAC`, not merely `; call BASIC ROM`.

---

# Sources

Microsoft, **Microsoft BASIC for 6502 Microprocessor — Version 1.1** (MIT):
https://github.com/microsoft/BASIC-M6502

Michael Steil, **C64 BASIC & KERNAL ROM Disassembly**:
https://www.pagetable.com/c64ref/c64disasm/

C64 commentary used primarily from:

- Microsoft/Commodore Source
- Lee Davison, *The almost completely commented C64 ROM disassembly*

The official Microsoft source establishes historical lineage and intent; the pinned C64 ROM and C64-specific disassembly establish exact C64 bytes, addresses, and behavior.

This file intentionally includes only high-value symbols and summaries useful during reverse engineering.
