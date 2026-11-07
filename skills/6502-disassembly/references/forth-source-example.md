# Source-backed FIG-Forth structures in 6502 disassembly

Separating dictionary headers, execution-token cells, inline operands, and native handlers prevents a 6502 disassembler from inventing instructions or call edges inside a Forth thread.  This reference illustrates that separation using one pinned source specimen, not a recognizer or a claim about all Forth systems.

## Specimen and evidence boundary

The specimen is Jeff Tranter's FIG6502 port for the **Ohio Scientific Model 600/Superboard II, not the C64**.  Its [README](https://github.com/jefftranter/6502/blob/325c18c9608f7205833895968b60c7b5c4141030/asm/fig-forth/README.TXT) credits an original download from <https://dwheeler.com/6502>.

- Repository revision: `325c18c9608f7205833895968b60c7b5c4141030`.
- Source: [`asm/fig-forth/fig6502.asm`](https://github.com/jefftranter/6502/blob/325c18c9608f7205833895968b60c7b5c4141030/asm/fig-forth/fig6502.asm), 95,954 bytes, 3,829 lines.
- Source-file SHA-256: `3c93580679ffbd1f3c399806e3f791b680c55a2dd84ed83545bc6f4ee14abdc2`.

All examples below are **source-derived**.  Header hex and relative sizes follow declarations; no assembled image, absolute word address, complete dictionary, or runtime behavior has been validated.

## Three worked records

NFA means name-field address; CFA means code-field address; PFA means parameter-field address.  For these unpadded records, the counted name ends in a high-bit-marked character, followed by a two-byte link, a two-byte code field, and the body.  The links refer to **earlier NFAs**, whereas thread cells refer to **CFAs**.

| Word | Source lines | NFA → previous NFA | CFA → native handler | Declared body | Header hex; link/CFA/PFA offsets from NFA |
| --- | --- | --- | --- | --- | --- |
| `1` | 1135–1138 | `L928` → `L920` (`0`) | `ONE` → `DOCON` | two-byte constant `1` | `81 b1`; +2/+4/+6 |
| `1+` | 1387–1392 | `L1170` → `L1162` (`HLD`) | `ONEP` → `DOCOL` | `ONE`, `PLUS`, `SEMIS` CFA cells | `82 31 ab`; +3/+5/+7 |
| `LFA` | 1576–1582 | `L1339` → `L1328` (`LATEST`) | `LFA` → `DOCOL` | `CLIT`, byte `4`, `SUB`, `SEMIS` | `83 4c 46 c1`; +4/+6/+8 |

These body sizes are respectively two, six, and seven declared bytes.  `LFA` is also the name of a Forth word here; do not confuse that word's CFA symbol with the link-field location in a header.  The selected ordinary header flags are not a description of every dictionary header.

## Follow the consumers, not the pointer's appearance

1. **Dictionary lookup:** [`PFIND`, lines 451–493](https://github.com/jefftranter/6502/blob/325c18c9608f7205833895968b60c7b5c4141030/asm/fig-forth/fig6502.asm#L451-L493), compares names, locates the terminating high-bit character, and follows the next link back to another NFA.  Record this as a dictionary relation, not a native control-flow edge.
2. **Indirect thread dispatch:** [`NEXT`, lines 125–140](https://github.com/jefftranter/6502/blob/325c18c9608f7205833895968b60c7b5c4141030/asm/fig-forth/fig6502.asm#L125-L140), loads a CFA from `(IP)` into `W`, advances `IP` by two, and jumps to `W-1`.  [Initialization, lines 2678–2679](https://github.com/jefftranter/6502/blob/325c18c9608f7205833895968b60c7b5c4141030/asm/fig-forth/fig6502.asm#L2678-L2679), stores opcode `$6C` there, producing an indirect jump through the CFA cell.  Distinguish thread → CFA from CFA → native handler; neither is an ordinary thread-resident `JSR`.
3. **Word kinds:** `DOCON` reads the constant at `W+2` and `W+3` (lines 1082–1087).  `DOCOL` saves `IP` on the hardware stack and starts the body at `W+2` (lines 1044–1056); `SEMIS` restores `IP` and dispatches again (lines 744–751).  This interpretation uses the dispatcher's `Y=0` convention.  Do not model a colon body as native instruction fall-through.
4. **Inline operand:** [`CLIT`, lines 144–150](https://github.com/jefftranter/6502/blob/325c18c9608f7205833895968b60c7b5c4141030/asm/fig-forth/fig6502.asm#L144-L150), consumes one byte and shares `L31`'s one-byte IP advance (lines 110–121).  In `LFA`, body offsets are `CLIT` at +0, inline `4` at +2, `SUB` at +3, and `SEMIS` at +5.  A uniform two-byte-cell scan loses alignment after that operand.

For a structured disassembly, maintain separate native-code, dictionary-link, threaded-call, and inline-data annotations.  Enter native analysis at independently supported handlers, and preserve unknown regions rather than sweeping thread data as opcodes.  Another target requires its own header, dispatcher, operand, address, and execution evidence; this source does not establish C64 applicability.

## Attribution and distribution notice

The retained source identifies FIG Release 1.1 and W. F. Ragsdale's translation, including its original Rockwell System-65 I/O background.  That historical notice does not change the platform of this later Ohio Scientific port.  No modern SPDX license is inferred.  Preserve the original notice when redistributing the source:

```text
;
;                        Through the courtesy of
;
;                         FORTH INTEREST GROUP
;                            P.O. BOX  2154
;                         OAKLAND, CALIFORNIA
;                                94621
;
;
;                             Release 1.1
;
;                        with compiler security
;                                  and
;                        variable length names
;
;    Further distribution must include the above notice.
;    The FIG installation Manual is required as it contains
;    the model of FORTH and glossary of the system.
;    Available from FIG at the above address for **.** postpaid.
;
;    Translated from the FIG model by W.F. Ragsdale with input-
;    output given for the Rockwell System-65. Transportation to
;    other systems requires only the alteration of :
;                 XEMIT, XKEY, XQTER, XCR, AND RSLW
```
