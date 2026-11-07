# Separately admitted BASIC PRG snippets

A requested known-snippet PRG can make an independently understood fragment loadable, without claiming that a partial decompiler reading is runnable.  This is a separate, bounded export task, not the default reconstruction output or a distributed standalone decompiler/exporter.

## Admission before encoding

Use structured statement/expression records with evidence references.  Do not accept arbitrary reconstructed text merely because a caller labels it known.  Never strip `REM PARTIAL_READING`, unresolved operands, channels, or annotations generically to manufacture code.  A title-local adapter must separately justify any such presentation and preserve its original evidence.

Declare the supported subset and refuse other forms.  A narrow implementation may support scalar assignments, FOR/NEXT, direct branches, PRINT/PRINT#, POKE, SYS, and RETURN while refusing DATA, REM, alternate/computed branches, arrays, FN, and raw text.  A lexical tokenizer is not a syntax or semantics validator; its unsupported cases must be unreachable through the admitted structure.  This guide does not provide or require a private helper or harness.

## Representation contracts

- Map hexadecimal memory labels mechanically to decimal BASIC line numbers **0..63999**.  Preserve order; reject duplicates, descending rows, ambiguous ownership, absent targets, and branches to omitted comment-only lines.  Do not silently sort, renumber, or invent destinations.
- Use legal, distinct variable aliases under BASIC V2's **first two significant characters and type suffix**.  Preserve `$`/`%` types, reserve existing legal identifiers, and exclude system/keyword identities.  Distinguish original BASIC identifiers from reconstructed symbolic IDs before allocation: COUNT and COUNTER share native identity CO, while two distinct lifted slot IDs need not share an identity merely because their display names start alike.  Canonicalize parsed native names under stock rules, checking full keyword spellings including suffixes.  A system variable such as TI, including a longer native spelling with that significant prefix, is not an ordinary variable to rename silently.  Keep original spellings/evidence and an exact alias table.
- Keep PETSCII payloads as bytes, not UTF-8, Unicode glyph guesses, or screen codes.  Literal NUL/quote cases need an explicitly supported representation or refusal, not escaping conventions invented for BASIC.
- Only literal-integer CHR$ **output-string leaves** may become representable quoted PETSCII.  Preserve zero, quote, out-of-range, computed, non-output, and nested non-output calls.  PRINT#'s channel is not part of its output-string region.  Preserve separators, concatenation/grouping, effect order, and separate newline statements.
- Output no REMs or converted comments.  Omit only an admitted default literal STEP1; retain computed/effectful steps.  Refuse an unsupported omission rather than changing control flow.
- Encode the stock $0801 load header, every forward record link, decimal line field, token body, physical NUL terminator, and final two-byte marker.  Bound both records and total BASIC memory use.  No trailing data or silent truncation.

## Independent acceptance

Author expected token bodies independently of the renderer/tokenizer/sidecar, and verify spellings against a pinned stock ROM token table.  Independently walk physical record boundaries, links, numbers, and exact EOF.  Check the entire inspection listing and sidecar: source/evidence, aliases/types, targets, transformations, byte payloads, hashes, and scope.

Use synthetic known inputs that bypass no title-specific hash gate.  Include invalid labels/targets, two-character collisions, changed suffixes, system aliases, unsupported scaffolding, PRINT# channels, quoted keyword-looking bytes, unrepresentable strings, separator/effect-order changes, and corrupt containers/metadata.  Paired product mutants must demonstrate that the controls detect those defects.  Preserve first outcomes and use fresh deterministic replays.

An encoded snippet is **not necessarily standalone runnable or behaviorally equivalent**.  It may require native SYS code, memory contents, a caller for RETURN, channel state, compiler-specific numeric behavior, or other context.  Record these dependencies, and do not execute an exported fragment without separate authorization and runtime validation.  Keep title-specific sources, examples, evidence, and approvals outside distributable skill material.
