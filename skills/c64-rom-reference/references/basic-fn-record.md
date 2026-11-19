# Reading a shared five-byte store: C64 BASIC V2 DEF and FN

A watchpoint on `STA ($4E),Y` cannot tell you whether BASIC is defining a function or restoring a variable.  Identify the incoming path, the most recent writer of the indirect pointer, and the producer of the five stack bytes before naming the write.

| DEF statement, `$B3B3` | FN expression, `$B3F4` |
|---|---|
| `$B3E1` resolves the FN name and leaves its record's value pointer at `$4E/$4F`.  DEF pushes a spare byte (A after the equals check), the formal pointer high/low, and the body pointer high/low. | The same name lookup initially sets the same pointer.  FN obtains the formal pointer from record offsets 2 and 3, pushes the old five-byte formal value from offset 4 down to 0, and temporarily stores the numeric argument in that cell. |
| DEF skips the body, then jumps from `$B3DE` to `$B44F`.  Store order in the **FN record** is body low/high, formal low/high, spare.  Offset 4 is actually written; the evaluation path does not read it as a record field. | After evaluating the body, FN pulls the saved **formal** pointer into `$4E/$4F`.  On a valid body terminator it restores the caller's text pointer and falls through to `$B44F`.  Store order in the **formal cell** is old numeric bytes 0 through 4. |
| RTS resumes the statement interpreter, not the function body. | RTS resumes the expression evaluator.  The body result stays in FAC, not in the restored cell.  A syntax error before the tail is not a normal return. |

**Revision and entry contract.**  Stock C64 BASIC 901226-01 (SHA-256 `89878cea0a268734696de11c4bae593eaaa506465d2029d619c0e0cbccdfa62d`), mapped at `$A000`, with valid BASIC text, workspace, and CPU stack.  In the common tail, `$B452/$B456/$B45A/$B45E/$B462` store the five successive pulls at offsets 0 through 4; `$B464` is RTS.  A bare JSR to `$B44F` puts its own return bytes on top of the stack where payload is required.

**Small distinguishing fixture.**  Use `10 X=123456789:DEF FNF(X)=X+1 :R=FNF(2)`.  On normal return, X must be 123456789, R must be 3, and the FN record must still point at the body and X.  Replace the space immediately before the second colon with an extra `)`: definition still succeeds, but evaluating the malformed body takes the syntax-error path without the five restore stores.  Do not infer post-error recovery from the successful path.

**Sources.**  [Stock BASIC ROM archive](https://www.zimmers.net/anonftp/pub/cbm/firmware/computers/c64/) and [Ultimate Commodore 64 Reference, ROM disassembly](https://www.pagetable.com/c64ref/c64disasm/), especially `$B3B3` through `$B464`.  Addresses are ROM internals, not stable user-callable APIs.
