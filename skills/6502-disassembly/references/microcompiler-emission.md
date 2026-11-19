# Worked example: Micro Compiler emits native 6502

Compiler-controlled source changes can explain native-code boundaries and operand roles without executing the resulting program.  This example compares actual saved objects from Vic Cortes's Micro Compiler, as translated to host Python and JavaScript using MOSpeed.  It establishes emission behavior, not target correctness or an automatic compiler signature.

## Identity and scope

Upstream: <https://github.com/EgonOlsen71/microcompiler>, commit `71551d432255f3eda552fa1c1e3b3335a3c11e41`.  Its README credits Vic Cortes and RUN 07/86, describes the MOSpeed translations, and notes modifications to the BASIC sources.  The repository declares the Unlicense.  These observations concern the pinned translated compiler, not demonstrated byte equivalence to the historical `basic/mc.prg`.

The accompanying compiler-suite checkout was pinned at <https://github.com/EgonOlsen71/compsuite>, commit `587bd9cecb76ff027cafd05e7ad831eec129c397`.  It is context, not the compiler used for these objects, and is not needed to reproduce them.

Relevant files, relative to the Micro Compiler repository:

| File | SHA-256 |
| --- | --- |
| `python/mc.bas` | `96d3a2e2b7f72679b5164d4f998e15b0f2492b430c4a3ed2d9098b8040162ce8` |
| `python/mc.py` | `947d6af598bebba5f1e8e26b3b9868db7d5866241835cad2520f8d93c9179ffa` |
| `python/save.py` | `2f18047efdb97cfbc9f4991ced9b3722c5fdce3f76789f95753ca8792d1bb8e4` |
| `js/++mc.js` | `6529b5a52f09e8a67fa5c12118bca7d16f5e6c5f88d8eec1c417c675271dd642` |
| `js/index.html` | `90d5ffff1360116b5b408f91489ef06719b13cc05c285470fbca5d4517e28672` |

Python 3.12.3 and Node v22.23.2 were used.  No compiled C64 object was loaded, simulated, or executed.

## What the source generator does

The [pinned BASIC generator](https://github.com/EgonOlsen71/microcompiler/blob/71551d432255f3eda552fa1c1e3b3335a3c11e41/python/mc.bas) is short enough to inspect before interpreting its output.  Numbers below are BASIC line numbers, not physical text-file lines.

- Lines 590 through 750 stream a tokenized BASIC PRG, discard its load address, read records sequentially, record source-line/output-address associations, and split statements at colon or THEN.  This is direct native emission through POKE, not a target p-code VM or an optimizing intermediate representation.
- Expression lines 100 through 570 use A for the low byte and X for the high byte.  Literals select immediate instructions; variable references select absolute instructions.  Line 560 contains `d=d-65:d=d+d+680`: A occupies `$02A8/$02A9`, B occupies `$02AA/$02AB`, and subsequent first letters select successive two-byte slots.
- Assignment lines 930 through 1020 store that register pair.  Inline arithmetic combines low and high bytes with carry/borrow.  Multiplication and division request a shared appended helper.  The listing supports a restricted 16-bit integer expression model, not full C64 BASIC numeric semantics or ordinary expression precedence.
- Initialization lines 1850 through 1870 emit `JMP start+6`, followed by a three-byte helper slot initially containing `JMP $A474`.  Lines 1980 through 2020 append the arithmetic helper when requested and patch the slot.  There are no saved symbols, relocation records, or source-line tables.
- GOTO/GOSUB lines 1480 through 1490 emit absolute JMP/JSR placeholders.  Lines 1940 through 1970 resolve those operands from the recorded line map.  IF lines 1030 through 1150 emit high-byte/low-byte comparisons and short branches; line 630 patches the false-condition exits to the next source line.
- PRINT string lines 1340 through 1440 embed zero-terminated text behind a carry-cleared BCC.  Such bytes are data even when they decode as plausible opcodes.

These are structural source findings.  A host compilation below checks selected emitted instances, not every supported statement.

## Authored constant-versus-variable pairs

All six inputs use the same requested native base, decimal 49152 (`$C000`).  Each pair changes only the stated expression; both versions initialize the same variables.  Equal source-level values are a control, not a claim that target execution was tested.

**Load pair:**

```basic
10 B=7
20 A=7
30 END
```

The variable member changes only line 20 to `20 A=B`.

**Addition pair:**

```basic
10 B=1
20 A=7
30 A=A+1
40 END
```

The variable member changes only line 30 to `30 A=A+B`.

**Equality pair:**

```basic
10 A=7:B=7
20 IF A=7 THEN A=1
30 END
```

The variable member changes only line 20 to `20 IF A=B THEN A=1`.

Actual Python-saved files include a two-byte little-endian load prefix and the Python saver's extra byte described below:

| Pair | Constant bytes | Variable bytes | Constant SHA-256 | Variable SHA-256 |
| --- | ---: | ---: | --- | --- |
| Load | 31 | 33 | `fa0aabf4b35962e24c216ea4e8d877e9ff5a3971e0eb007821c198759de5b38e` | `7309c60aa6f105dbc5cec12031da5257117d2e39931b696dba32c45d426948a4` |
| Addition | 52 | 54 | `75ee1317b0a656d436c10f64181702ec64475326af057fb5c86631e82d8827fe` | `579bfaab18df1764c628f9aae55f3504d56647182c40b6658ed3b2b2874e9f39` |
| Equality | 69 | 71 | `740caa7054b46d6f5531873cd08cd42e9fd7523b1f663a442d63c26ae8115a22` | `816beb4885da69668ee391524c35cb154cdb755e75c9a87da7e4ee55b36aaab3` |

All six compiler error counters were zero.  Each variable form is two bytes longer: two absolute operands replace two immediate operands.  In particular, initializing B does not cause its subsequent reference to be folded into a literal.

## Saved bytes and supported disassembly

The entire 52-byte addition-constant file is:

```text
00 c0 4c 06 c0 4c 74 a4 a9 01 a2 00 8d aa 02 8e ab 02
      a9 07 a2 00 8d a8 02 8e a9 02 ad a8 02 ae a9 02
      18 69 01 a8 8a 69 00 aa 98 8d a8 02 8e a9 02 60 00 00
```

The prefix `00 c0` is a load address, not instructions.  The generator and source-line boundaries support this classification:

```text
C000  4C 06 C0  JMP $C006       ; entry skips helper slot
C003  4C 74 A4  JMP $A474       ; unused arithmetic slot in this object
C006  A9 01     LDA #$01
C008  A2 00     LDX #$00
C00A  8D AA 02  STA $02AA       ; initialize source B
C00D  8E AB 02  STX $02AB
C010  A9 07     LDA #$07
C012  A2 00     LDX #$00
C014  8D A8 02  STA $02A8       ; initialize source A
C017  8E A9 02  STX $02A9
C01A  AD A8 02  LDA $02A8
C01D  AE A9 02  LDX $02A9
C020  18        CLC            ; independent 16-bit addition, assuming D=0
C021  69 01     ADC #$01
C023  A8        TAY            ; retain low result without changing carry
C024  8A        TXA
C025  69 00     ADC #$00        ; propagate low-byte carry into high byte
C027  AA        TAX
C028  98        TYA
C029  8D A8 02  STA $02A8
C02C  8E A9 02  STX $02A9
C02F  60        RTS            ; source END
C030  00        .byte $00      ; generator's explicit final zero
C031  00        .byte $00      ; additional Python-saved memory byte
```

For the variable addition, `$C021` is `6D AA 02` (`ADC $02AA`), and the high-byte add at `$C026` is `6D AB 02` (`ADC $02AB`).  Subsequent addresses shift accordingly.  The addition clobbers A, X, Y, and arithmetic flags, and stores the result into the two-byte A slot.  The generator does not establish decimal mode here; binary arithmetic interpretation assumes D=0.  No live ROM mapping, caller, interrupt state, or stack contract was tested.

For the load pair, the changed fragment at `$C010` is `A9 07 A2 00` versus `AD AA 02 AE AB 02`.  For equality, the right operand at `$C024` changes from `A9 07 A2 00` to `AD AA 02 AE AB 02`.  The left operand was saved to `$22/$23` first.  The constant form then contains:

```text
C028  E4 23     CPX $23
C02A  F0 04     BEQ $C030
C02C  D0 12     BNE $C040
C02E  D0 06     BNE $C036
C030  C5 22     CMP $22
C032  D0 0C     BNE $C040
C034  D0 0A     BNE $C040
```

`$C036` starts the assignment, and `$C040` is the next source line's RTS.  Some branches are redundant or unreachable in this equality specialization.  Preserve them in the listing rather than silently presenting optimized assembly.  A repeated template can explain these bytes without implying a hand-written algorithm.

## Format discrepancy and controls

The BASIC finalizer, line 2030, is `poke a,0:e=a+1`.  Thus E is one past the explicit final zero.  The Python saver uses `_memory[int(VAR_S):int(VAR_E)+1]`, including the additional byte at E.  The browser exporter in `js/index.html` instead copies E-S bytes, excluding E.  Do not normalize this difference away when recording original saved-file hashes.

Bounded controls gave these results:

- Recompiling the unchanged addition input produced the identical saved SHA-256.
- Changing only `A=A+1` to `A=A+2` changed exactly file offset 36, from `$01` to `$02`, the operand at native `$C022`.  File size remained 52 bytes.
- Compiling the same addition at `$C100` changed exactly file offsets 1 and 4 from `$C0` to `$C1`: the load prefix and entry-JMP high byte.  This tiny object has no other internal absolute references; it is not a general relocation test.
- Seeding only memory[E] to `$A5` immediately before the original Python saver changed the last byte of the load-constant file from `$00` to `$A5`.  This separates generator output from an incidental saved memory byte; it does not change generator logic.
- The unmodified JavaScript compiler core, hosted with `self=null`, a decimal-base prompt, and a bounded `reinit()`/`executeLine(false)` loop, produced identical `[S,E)` bytes for all thirteen cases, including the controls.  Browser-format files were exactly one byte shorter than Python files.  For addition-constant, the 51-byte browser-format SHA-256 was `d7529387abbd1cee525b333dda71f60bf92aa2d86bc4e5f797a52bc2091a72a7`.

The two host translations share the same BASIC generator.  Agreement helps check the Python shim and translation-specific behavior; it is not an independent proof of compiler correctness, original-C64 equivalence, or runtime semantics.

Three additional structural inputs were compiled, without target execution:

| Exact source | Python-saved bytes | Selected observation |
| --- | ---: | --- |
| `10 PRINT "OK":END` | 29 | `$C00E: 90 03` skips `$C010` through `$C012`, bytes `4F 4B 00`; calls encode targets `$AB1E` and `$FFD2` |
| `10 A=6*7` followed by `20 END` | 110 | helper slot becomes `4C 1D C0`; call at `$C013` is `20 03 C0`; helper follows the main RTS |
| `10 GOTO 30`, `20 A=99`, `30 END` | 24 | forward JMP at `$C006` resolves to `$C013`; assignment bytes remain but are bypassed on that path |

These examples distinguish inline data, appended native helpers, and patched native branches from a resident bytecode interpreter.  External call targets are reported as encoded addresses; no live ROM availability or call behavior is asserted.

## Standalone reproduction of the addition pair

Obtain the upstream repository at the pinned commit, without modifying it.  Save the following as `emission_example.py`, outside that checkout, then run:

```bash
python3 emission_example.py microcompiler/python/mc.py
```

It writes inputs, compiler logs, and actual original-saver outputs under `emission-example/`.  It needs Python only, not keyboard hooks, a C64 emulator, or private tools.  The exact PRGs below encode the authored addition listings, including standard BASIC line links and tokens.  The shim removes only the optional keyboard import and final interactive `execute()` invocation, then supplies menu/prompt replies.  Generator functions and the original saver remain unchanged.  Host SYS hooks here are the upstream translation's hooks, not a 6502 execution engine.

```python
import ast
import contextlib
import hashlib
import io
import os
from pathlib import Path
import sys

compiler = Path(sys.argv[1]).resolve()
source = compiler.read_bytes()
assert hashlib.sha256(source).hexdigest() == (
    "947d6af598bebba5f1e8e26b3b9868db7d5866241835cad2520f8d93c9179ffa")
cases = {
    "add_constant": (
        "010809080a0042b231001108140041b237001b081e0041b241aa31002108280080000000",
        "75ee1317b0a656d436c10f64181702ec64475326af057fb5c86631e82d8827fe"),
    "add_variable": (
        "010809080a0042b231001108140041b237001b081e0041b241aa42002108280080000000",
        "579bfaab18df1764c628f9aae55f3504d56647182c40b6658ed3b2b2874e9f39"),
}
root = Path("emission-example").resolve()
for name, (prg, expected) in cases.items():
    tree = ast.parse(source)
    kept, removed = [], []
    for node in tree.body:
        if (isinstance(node, ast.Import)
                and [n.name for n in node.names] == ["keyboard"]):
            removed.append("keyboard")
        elif (isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
              and isinstance(node.value.func, ast.Name)
              and node.value.func.id == "execute"):
            removed.append("execute")
        else:
            kept.append(node)
    assert removed == ["keyboard", "execute"]
    tree.body = kept
    ns = {"__name__": "host_compiler"}
    exec(compile(tree, str(compiler), "exec"), ns)
    replies = iter(["source.prg", "49152", "object.ml"])
    menus = iter(["1", "3"])
    def reply():
        ns["_line"] = ""
        return next(replies)
    original_sys = ns["SYSCALL"]
    def host_sys(address):
        assert address in {"$a717()", "$ffbd()", "$ffba()", "$ffd8()"}
        return original_sys(address)
    ns.update(input=reply, get=lambda: next(menus), SYSCALL=host_sys)
    work = root / name
    work.mkdir(parents=True, exist_ok=True)
    (work / "source.prg").write_bytes(bytes.fromhex(prg))
    log, previous = io.StringIO(), Path.cwd()
    try:
        os.chdir(work)
        with contextlib.redirect_stdout(log):
            ns["reinit"]()
            for _ in range(100000):
                if not ns["running"]:
                    break
                ns["executeLine"]()
            else:
                raise RuntimeError("host compiler step bound")
    finally:
        os.chdir(previous)
    (work / "compiler.log").write_text(log.getvalue())
    assert ns["VAR_ER"] == 0
    saved = (work / "object.ml").read_bytes()
    s, e = int(ns["VAR_S"]), int(ns["VAR_E"])
    assert saved[:2] == b"\x00\xc0"
    assert saved[2:] == bytes(ns["_memory"][s:e+1])
    assert hashlib.sha256(saved).hexdigest() == expected
    print(name, len(saved), expected)
```

For the same store suffix writing through two different pointers, see [which address does the indirect store write?](microcompiler-pointer.md).

For a 24-byte comparison shared by IF and FOR, [follow its successors and the first-entry bypass](microcompiler-successors.md) before choosing a source construct.

## Limitations worth retaining

Source inspection, rather than additional runtime experiments, establishes these cautions at this pin:

- This is a BASIC subset.  Expression parsing is left-to-right; do not import full BASIC precedence, floating-point, array, or string-variable semantics.  Variable reads use first-letter slots; assignment targets have stricter single-letter syntax.
- END, STOP, and RETURN emit RTS.  The saved entry does not clear variable memory; the compiler's separate run-menu path clears it.  Caller setup matters.
- IF has one pending fixup and short relative branches, with no observed long-branch expansion or range check.  A last-line IF has no subsequent line to trigger line 630's fixup.  Do not assume arbitrary nested or long IF bodies work.
- FOR/NEXT retains singleton loop state, not a general nested-loop stack.  It should not be described as full BASIC loop semantics.
- Unresolved GOTO/GOSUB targets can retain `$0000` placeholders without a diagnostic.  Fixed-size fixup/line arrays and the statement buffer do not provide comprehensive overflow protection.
- No runtime claims were tested: integer edge cases, helper arithmetic correctness, screen output, timing, IRQ interaction, banking, and application behavior remain outside scope.  The JavaScript exporter was reproduced from its copy loop, not exercised in a browser download session.

## Standalone sketch for the code-reuse sister skill

**Question:** does matching native code reflect application implementation reuse, shared compiler scaffolding, or a common idiom?

Use the addition pair above as a controlled nuisance example.  Preserve the original PRGs, compiler pin, load prefixes, and saved tails.  Compare code regions separately from the unused helper slot and trailing data.  The identical carry-preserving arithmetic skeleton with changed immediate/absolute operands is expected from the generator even though the source expressions differ.

A useful follow-up reuse audit would retain a separately authored handwritten 16-bit-add example and another compiler as negatives, classify operand roles before masking addresses, and assess broader block order, helpers, constants, and context.  It would keep raw and normalized comparisons distinct and avoid counting the same shared template repeatedly.  That follow-up comparison was not performed here.

The present evidence supports native disassembly and a source-to-emission explanation for known authored inputs.  It does **not** establish a unique producer signature for an unknown binary, application copying, direction of copying, exact compiler version, or authorship.  Do not add an automatic recognition signature from this common template.
