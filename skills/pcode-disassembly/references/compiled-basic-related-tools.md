# What other C64 BASIC tools can verify

A detokenizer turns stored BASIC keyword bytes into text.  A p-code decompiler must additionally recover expressions and statements from VM operations.  A forward compiler can corroborate an encoding without being a decompiler.  Use these tools for the question they actually answer:

| Implementation | What to learn or check |
|---|---|
| [PetspeedDecompy](https://github.com/EgonOlsen71/PetspeedDecompy/tree/3d4360e8b481c2157fccac0458f3556a2d3ea311/bin) | A direct PETSpeed decompiler.  Compare the register/stack-to-expression translation, variable aliases, array extents, control destinations, retained DATA, and generated BASIC V2 tokens.  Its generated line numbers are not recovered source lines.  The bundled alternate reading backend adapts this Unlicense software; agreement between the two is not independent validation. |
| [Reblitz64](https://github.com/c1570/Reblitz64/blob/4c3f9da453b53fd5cbe898f85a99b1d914efb117/docs/reblitz64.js) | A BLITZ!/Austro-Speed **compiler**.  Inspect `p1_for`, `p1_if`, `add_branch_target_to_pcode`, and `pass2` to compare source constructs with emitted operands and patched destinations.  Test against the correct runtime revision; do not infer inverse uniqueness.  No repository license was identified in the surveyed revision; use as a reference rather than importing its code. |
| [VICE PETCAT](https://github.com/VICE-Team/svn-mirror/blob/83095dcbf3a535167fb864fc4801b0c8ef5be517/vice/src/tools/petcat/petcat.c#L2039) | An independent tokenizer/detokenizer, useful for checking BASIC V2 byte export.  Keyword bytes inside quotes, REM, or DATA are not instructions.  A text-format match still cannot establish equivalent runtime behavior. |
| [VS64](https://github.com/rolandshacks/vs64/blob/f9a5dda20a3e2f8e70bb11eb0a55bd1db0df7024/tools/bclib/decompiler.py#L41), [C64ReverseBasic](https://github.com/jojowil/C64ReverseBasic/blob/8a95fb576416fa65b7f839c0c5588173d27ae2b6/src/C64ReverseBasic.java#L164), [basicv2](https://github.com/EgonOlsen71/basicv2/blob/d7f4615affc2d0293cb2482f1ec34fb6ca7908f5/src/main/java/com/sixtyfour/parser/cbmnative/UnTokenizer.java#L116) | Separate examples of tokenized BASIC input, linked lines, dialect tokens, and PETSCII presentation.  Do not count these parsers as independent lifts of compiled PETSpeed, BLITZ!, or DTL p-code. |
| [c64-re-tools](https://github.com/henols/c64-re-tools/blob/2339d4aea09141af178263e7796fe875154c83d4/skills/c64-basic/scripts/basic.ts#L21) | Illustrates separating a BASIC listing from appended machine code and SYS/USR handoffs.  Recognizing a loader does not decode its payload. |

### Reproducing the Reblitz64 `IF` check

The pinned Reblitz64 compiler writes a different BASIC startup line but the same native BLITZ interpreter (from `$081C` up to, but not including, the pointer table at `$1F93`).  The binary-only frontend recognizes this exact bootstrap and runtime.  It does not infer which compiler produced an arbitrary file.

Two five-line programs differ only in `IF A THEN 40` versus `IF A THEN 60`.  With `A` supplied by `INPUT`, the fall-through prints `"MISS"` in both.  The compiler changes one byte: `52 1F B1` becomes `52 1F B8`.  The decompiler follows the first target to `PRINT "LEFT"` and the second to `PRINT "RIGHT"`.  The labels are compiled addresses, not recovered source line numbers.

The offline regression needs only Python.  To repeat the actual compilation, obtain the pinned Reblitz64 revision linked above, install Node if needed, and run this from the skill directory, replacing the path with your local copy:

```bash
REBLITZ64_JS=/path/to/Reblitz64/docs/reblitz64.js python3 -m unittest discover -s scripts/reconstruct -p test_reblitz_if.py -v
```

The test checks the compiler file hash before running it.  It passes only the compiled bytes to the decompiler and does not execute either C64 program.  Without `REBLITZ64_JS`, it still checks both target readings and rejects a target inside a string operand.

For a paired comparison, give each decompiler the same compiled bytes, never its paired source.  Check the outputs against an independently inspected original or native handler: operand order, literal bytes, number of effectful evaluations, array layout, and destination membership make better checks than line counts.  Keep exact-runtime recognition, complete byte decoding, readable output, structurally valid token export, and actual execution equivalence as separate claims.
