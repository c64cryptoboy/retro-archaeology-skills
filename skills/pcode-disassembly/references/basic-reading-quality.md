# Readable BASIC is a separate deliverable

A readable listing should explain the program, not force its reader to decode the lifter's notation.  Apply this gate whenever producing or revisiting BASIC-like output, for **every compiler family**, including a title-local adapter.  Family-specific operand, conversion, loop, and call contracts still require their own evidence.

## Preserve two views

Keep exact bytes, rational/decimal values, canonical expression trees, targets, instruction ownership, and unresolved semantics in immutable detailed evidence.  Produce a separately traceable reader-facing projection.  Preserving evidence does not require printing every binary floating-point digit, redundant parenthesis, internal capture, or bookkeeping warning in that projection.

A cleaner projection adds no decoded coverage and does not recover the author's original spelling, names, line numbers, or expression tree.  Preserve old milestones, and identify which view a validation claim covers.

## Evidence forms and scope

Use static code, source, documentation, observed execution, and firsthand user observations together, with their provenance and limits.  A directly observed screen message establishes that visible output for the observed case even if native channel setup has not been traced.  Describe the mechanism as untraced, not the visible outcome as unproven.  Conversely, screen-looking strings alone are not an observation, and one observed sequence does not establish every output path.  Do not demand a new screenshot or trace merely to disregard a credible firsthand observation; distinguish the user's observation from an agent-performed replay.

## Expressions and branches

- Render **structured expressions**, not regular-expression parenthesis deletion.  Use precedence to omit redundant grouping while preserving the exact evaluation tree.  `1 + INT(X * 20)` needs no wrappers around the addition, multiplication, or function argument.
- Keep necessary grouping: `A + (B + C)`, `A / (B * C)`, nested comparisons, powers, and unary edge cases must not be reassociated merely because an algebraic identity looks attractive.  Floating-point rounding, overflow, string operations, and error timing can make reassociation observable.
- A proved comparison's false branch can use its opposite relation: `IF ((A > B)) = 0 THEN ...` can read `IF A <= B THEN ...`.  Preserve operands and their order.  Comparison-only Boolean-tree duality needs its own eager-evaluation proof; do not turn conditional paths into eager expressions.
- An arbitrary numeric predicate still needs its zero test: `IF PEEK(P) = 0 THEN ...`.  BASIC's bitwise `NOT` is not logical truth negation.
- The neutral `scripts/reconstruct/expression_display.py` mechanism is reusable.  An existing DTL-only frontend admission is an implementation boundary, **not an exemption from these presentation requirements** when another family's reading is revised.  Supply nodes from that family's evidenced operations, and retain opaque leaves rather than guessing their structure.

## Idiomatic operand presentation

Prefer familiar BASIC source conventions across all compiler families, rather than exposing an incidental VM operand arrangement:

- Put the base address before a literal offset: prefer `POKE BASE + 1, VALUE` over `POKE 1 + BASE, VALUE`.
- Put the assigned variable first in a simple self-update: prefer `COUNT = COUNT + 1` over `COUNT = 1 + COUNT`.

Apply these as reader-facing defaults when the operands are known numeric and the reordering preserves target values, rounding, error behavior, and effects.  A literal and a plain variable are the intended common case; do not generalize this into arbitrary commutation or reassociation.  Do not reorder PEEK, RND, function calls, indexed reads, string expressions, or unknown/effectful computations without separate proof.  Keep the exact VM expression and evaluation order in detailed evidence, record any display reordering, and validate it independently.  This is an idiomatic projection, not a claim to recover the author's original spelling.  A newly recorded preference does not require regenerating an already delivered title unless requested.

## Short numeric spellings

Prefer a conventional short decimal in the reading when it reproduces the exact target value.  For example, a five-byte encoded value whose exact expansion is `0.80000000004656612873077392578125` may read `0.8` **after** a target-parser check; a neighboring encoded value must not inherit that spelling.

1. Recover the exact value and encoding from the actual literal operands.  Account for packed versus unpacked formats, sign, normalization, precision, and any conversion at use.
2. Generate bounded candidate spellings with exact decimal/rational arithmetic, not host binary-float rounding.  Search for a short conventional representation; do not claim a bounded search proves the globally shortest spelling.
3. Parse each proposed replacement using the evidenced target parser and storage/rounding path, or an independently validated exact equivalent.  Require full input consumption and exact value/encoding equality, not an epsilon or a chosen number of significant digits.
4. Retain original bytes, exact value/text, chosen spelling, literal sites, parser identity, and check result in a sidecar.  Immutable literals may be carried into later groups; preserve numeric identity rather than restricting a structured leaf to its current group's loads.
5. If no replacement passes, retain the exact form and record the refusal.  A likely original spelling may be discussed as a clearly labeled hypothesis, but must not be silently substituted as exact.  The original long rational expansion itself need not round-trip through the target's staged decimal arithmetic; the equality requirement applies to every **accepted replacement**.

The neutral `scripts/reconstruct/presentation_values.py` provides `decimal_candidates(exact_text)` and `select_decimal(exact_text, encoded, parse_to_encoded)`.  The callback owns the validated target parser and packing contract; the selector admits only exact byte equality, retains rejected attempts, and does not swallow parser failures.  It has no private-data or emulator dependency.  A mathematically nearest decimal, a familiar-looking constant, and a desired example are not substitutes for that check.

For stock C64 BASIC, one established check enters FIN through real CHRGOT character/carry classification, then uses MOVMF to round and store all five packed bytes.  A wrapper that forces carry set or compares raw FAC bytes without their sign/packing is not that check.  Pin the actual ROM revision and wrapper; consult the [ROM reference](../../c64-rom-reference/SKILL.md).  Reusing that value representation does not prove another compiler's historical parsing algorithm or recover original typography.  Other targets need their own parser contract.  The public skill does not depend on a private oracle or a live emulator.

Distinguish a display-value proof from producer attribution: once the literal's representation and use are established, a validated parser for that representation may prove a reader-facing spelling without reproducing the original compiler's decimal parser.  Do not refuse solely because that compiler version has no dedicated decimal oracle.  Conversely, matching format names alone are not representation proof.  A blanket `unchanged-exact` inventory with no candidate checks records missing work, not successful application of this readability requirement; retain the evidence, and report that part of the reading as incomplete.

### Explicitly approximate reader decimals

If exact-parser shortening refuses a requested familiar spelling, do not change the parser, expected bytes, or strict acceptance gate.  A user may instead explicitly choose a **nominal reader view**, alongside an exact-number companion and a per-literal address/encoding ledger.  State that this view is not round-trip-exact source; the companion's full mathematical decimal expansions likewise do not imply that parsing their text reproduces the stored value.

For that separate contract, `select_nominal_decimal(exact_text, lower, upper)` can choose a short decimal strictly inside an adapter-proved nearest-storage cell.  The adapter must derive the exact adjacent values and midpoint bounds for the actual format, reject ties and wrong-neighbor displays, and validate the resulting human file independently.  Its `nominalProof` explicitly says `parserRoundTrip: false`; preserve strict parser successes, refusals, and observed bytes separately.  Do not promote the display choice into a claim about the original compiler's parsing, original spelling, or executable equivalence.  Without explicit authority for this different view, the strict default above remains unchanged.

## Source-level structure, not bookkeeping

- Apply the [whole-expression temporary policy](evidence-and-reconstruction.md#basic-only-temporary-policy) before accepting visible synthetic assignments.  A failed greedy substitution is not proof that a complete expression cannot be reconstructed.  Preserve read/call/operation order, count, typed stores, and control entries.
- Use the relevant family's proved FOR, ON, and deferred-function contracts; do not copy DTL's ABI or initialization order.  A simple display is not permission to change loop evaluation or function binding.
- Put display-only capture/provenance bookkeeping in detailed metadata where possible.  Keep meaningful partial/unknown/conversion qualifications visible, and preserve labels that are still referenced.
- Protect embedded BASIC, quoted contents, DATA, REM, and native SYS tails.  Do not invent PRINT separators, rewrite opaque text as expressions, or infer purity from a normal SYS return.  State the [normal-return reading default](evidence-and-reconstruction.md#sys-normal-return-reading-default) once, rather than at every call.

### Compiler-split FOR initializers

When a compiler separates the counter assignment from loop setup, recover a direct header such as `FOR I = 0 TO 7` instead of presenting `I = 0` followed by `FOR I = I TO 7`, where the family's lowering and control flow justify the merge.  This applies across families, not just to synthetic `T_` assignments.  Establish the same counter identity, reaching initializer, evaluation order, conversions, aliases, intervening effects, and absence of alternate entry that bypasses the initializer.  Preserve the first contributing label and both ownership spans.  Include a direct constant-initializer case and rejecting alternate-entry, counter-dependent-bound, and intervening-effect cases.  If association is unproved, keep the statements separate, and explain the specific limitation.

### Runtime conversions, addresses, and generated symbols

- Keep VM bookkeeping distinct from source operations.  A pack/round-to-target-precision step is not a source-level integer-rounding function.  Omit identity conversions on proved constants, and express ordinary implicit BASIC precision/coercion idiomatically where the family's actual behavior permits it.  Retain significant precision boundaries, conversion errors, and signedness in detailed evidence; do not blanket-delete wrappers from unknown expressions or change evaluation trees.
- An internal float-to-word conversion is not evidence that the author wrote `INT()`.  Preserve source-semantic `INT` operations separately.  At a statement such as SYS, an already integral, valid address need not read `SYS VM_INT(58640)`; prove that the conversion adds no observable behavior before hiding it.  Unknown or materially different conversions still need a visible qualification.
- Render a word consumed as a raw 16-bit address with its unsigned address interpretation.  For example, the word `$D020` reads `53280` in POKE, not the signed integer `-12256`.  Apply the consumer's evidenced address contract, not a global replacement of negative numbers or modulo masking of genuinely invalid source arguments.  Keep the encoded word and any signed arithmetic interpretation in evidence.
- Explain generated symbols at first use or in a visible legend.  Mark an array as an array, with its evidenced element type, rank, and bounds where known; do not leave `AR_...(...)` looking like an unidentified function.  Distinguish array element stores from calls, generated names from recovered names, and unknown dimensions from proved declarations.
- Preserve genuinely retained names, and check documented companion symbol files before declaring names lost.  The neutral `short_names(identities, occupied=..., excluded=...)` helper in `scripts/reconstruct/presentation_values.py` allocates unique bases in stable caller-supplied identity order.  Supply target keywords and system names explicitly, and prove storage types and aliases in the family adapter; the helper does not infer either.  If names are unavailable, prefer deterministic one- or two-letter BASIC aliases in the reader view over address-heavy names: `A` through `Z`, then `AA`, `AB`, and so on, excluding target keywords, system variables, and existing names.  Reserve `I`, `J`, and `K` for clear loop counters only when their identity and uses justify it.  Use a collision-free base-name allocation across scalars and arrays, respect the target's significant-character rules, and append `$` or `%` only for proved string or integer storage types.  Parentheses and an evidenced declaration/legend identify arrays.  Keep the alias-to-storage map, type evidence, recovered/generated status, and exact address-based identities in detailed evidence.  Rename structured symbol references consistently, not quoted strings, opaque BASIC/native fragments, or arbitrary text, and do not split aliases of the same storage into invented independent variables.  This is an alias policy, not recovery of original source names.

### Inline captured FOR bounds

Prefer a direct `FOR ... TO expression` over an adjacent, single-use internal limit capture.  For example, this synthetic bookkeeping:

```basic
L_1000: REM VM_CAPTURE T_LIMIT_1001 = LIMIT
L_1002: FOR I = 1 TO T_LIMIT_1001
```

should normally read:

```basic
L_1000: FOR I = 1 TO LIMIT
```

Do not restrict this improvement to literal bounds: a plain variable or a complete proved expression can belong directly in the header.  Keep the capture in detailed evidence, not as an invented source assignment in the human-facing listing.

- Preserve the bound's once-only evaluation, value/conversions, error timing, and order relative to initialization, step evaluation, and counter assignment.  Compare with the family's actual lowering, not another VM's loop ABI.
- Check aliases, intervening effects, additional uses, and alternate entries.  A captured old counter value cannot become a fresh read after the initializer overwrites it.  Single use and adjacency alone do not prove equivalence; conversely, do not retain a temporary merely because the bound is nonliteral.
- Label the merged reading at its first contributing instruction and retain the full merged ownership span, plus the original capture/header ranges, in provenance.  Do not silently discard a referenced label or a control entry that bypasses the capture.
- Inspect the actual final FOR header.  Include positive variable/expression-bound cases and negative counter-dependent, reordered-effect, alternate-entry, and repeated-use controls when implementing this projection.  If folding is blocked, record the concrete reason rather than a generic capture warning.

This records a cross-family presentation preference, not a claim that existing emitters implement it or permission to regenerate an already delivered reading.

## Defaults and output-channel notation

- Omit redundant literal `STEP 1` from reader-facing FOR headers; BASIC's default positive unit step expresses the same loop.  Keep the encoded/default step and its provenance in detailed evidence.  Preserve non-default steps, unknown steps, and any expression whose evaluation has effects or observable errors -- proving that its value is one does not permit deleting its evaluation.  Change only structured FOR headers, never quoted text, DATA, REM, or an opaque statement by a global replacement.
- A compiler can lower ordinary PRINT and selected-file PRINT to the same string, numeric, TAB, or newline primitives.  Their names are not proof of a source `PRINT#` statement.  Unknown channel knowledge after a join or opaque call is likewise not proof of logical-file selection.
- Track three things separately: the output primitive, explicit logical-file selection/restoration, and actual device routing.  A logical file number is not automatically a device number.  Screen-looking strings, PETSCII controls, and TAB alone do not prove screen ownership; an actual observed screen outcome is separate affirmative evidence and must not be discarded because its mechanism is untraced.
- Preserve genuinely selected-file output.  When only the ambient current channel is unknown, do not fabricate `PRINT#<?>` as though a logical-file selection occurred.  A reading may use `PRINT` as explicitly qualified **current-channel output notation**, not a claim of confirmed screen routing or recovered source syntax.  Keep the partial/channel qualification and evidence visible; use neutral output notation if that convention would be ambiguous.
- Preserve fragment order, separators, absent/present newlines, and ownership.  Several output primitives do not necessarily recover several original PRINT statements.  Include controls for explicit known/unknown file selection, restoration, unknown ambient channels, and screen-like text directed to a file.

## Acceptance must inspect the human-facing file

A byte/ownership-preserving dump is not automatically a readable listing.  Before delivery:

- Inspect representative arithmetic, comparisons, decimals, loops, functions, partial statements, and the user's motivating examples in the actual final BASIC file, not just JSON or a test summary.
- Check for binary-decimal tails, redundant wrappers or default `STEP 1`, compiler-split self-initializing FOR headers, signed rendering of raw addresses, unexplained array/function notation, invented file-output syntax from lost channel knowledge, leaked scaffolding, and unjustified synthetic captures.  Record actual formatting/refusal coverage without treating cosmetic counts as semantic correctness.  A test that merely requires all literals to remain unchanged or accepts every VM wrapper cannot establish that the reading passed these checks.
- Validate tree shape and ordered evaluation identities with an independent parser/tree oracle, and literal substitutions with the independent target-value check.  Comparing an emitter with another call to itself is not an independent semantic gate.
- Include adversarial controls for wrong constants, adjacent encodings, reassociation, reversed reads, Boolean-versus-bitwise tests, opaque syntax, changed targets, and lost ownership.  Preserve first failures; do not change expected results merely to obtain a pass.
- Verify that detailed evidence, original bytes, warnings, captures, and historical deliveries remain intact, except for explicitly authorized additive presentation metadata.  Label the new reading's scope and unresolved limits honestly.

Read this checklist before implementing a new reading adapter or porting a presentation improvement.  Do not wait for a reader to identify the same formatting defect in the next compiler family.
