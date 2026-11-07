# Reusable compiler-assisted p-code discovery

Use this workflow when a compiler is available and its use is authorized. These are cross-compiler methods, not a shared opcode table. A second compiler is evidence against importing the first compiler's architecture unchanged.

## 1. Record the evidence mode before work

Choose explicitly between compiler-assisted discovery and an intentionally compiler-free reconstruction. A compiler-free freeze is a research control, not a universal prerequisite. If authorization changes, record the transition without rewriting earlier frozen results. Manuals, compiler output, source, traces and third-party decompilers must retain their provenance.

Keep the internal discovery skill separate from final distribution decisions. Reuse existing deterministic readers, tokenizers, decode primitives and renderers where their contracts fit. Put discoveries into external profiles/evidence rather than hardcoded heuristics. Do not force distinct register/FAC and postfix-stack VMs into the same semantic renderer, or refactor a proven decoder merely to claim one abstraction. A shared primitive should have one implementation when actually extracted; keep CLI and skill adapters thin.

## 2. Establish one end-to-end compiler path first

Start with END and a short literal PRINT, not a useful application or a large opcode omnibus. Establish:

1. Exact authored source and tokenized-input bytes.
2. Compiler/revision, settings and original media hash.
3. A fresh working copy that preserves original logical files.
4. Actual filename/pass/error prompts and successful completion.
5. Closed output files, types, hashes, runtime identity and any sidecars.
6. A compiled run with expected output and the actual exit/error state.
7. Complete, refusing decode of just that small program.

Compilation, execution and decoding are separate gates. READY alone proves neither that compilation was error-free nor that an output file is complete. Model the compiler's actual prompt state: its own READY may be a single-key acknowledgment leading back to a menu, not BASIC direct mode. A completion banner can also precede the final output-file close; verify closed files and preserved bytes before classifying success. Conversely, a compiler error can stop at an acknowledgment prompt without ever reaching BASIC READY: a wait timeout is not proof of a hang. Inspect the actual screen before recovery; distinguish busy pass/loading screens, allocation questions, explicit diagnostics and completion. Use bounded status observations rather than increasing waits blindly. Capture a screenshot for failures or attribute/graphics-dependent warnings, retaining matrix text as searchable evidence; warnings shown in reverse video can be lost by plain-text-only rendering. Preserve reported line numbers verbatim, including any preceding-line qualification. Never automatically RUN leftover output after an error. Some compilers continue after errors, omit lines, autoload output, or autostart when mounted. Inspect state before RUN. Never overwrite a working disk after it has acquired compiler outputs; capture it before another test.

Keep fixture preparation and output capture deterministic and overwrite-refusing. Capture a failed disk and remaining intermediate files separately from successful outputs; do not scratch them as mere garbage, because they may expose parse trees, partial p-code and layout tables. A failed formulation plus a minimal successful workaround is a useful paired fixture, but is not a complete characterization of that feature. Validate the tokenizer's contract: DATA/REM tails, quoted PETSCII, statement separators, keyword matching and line links are common traps. Re-extract and compare the compiler input, not just its filename. A convenient one-sector fixture writer must refuse growth beyond its supported size rather than silently truncate.

## 3. Design small probes that discriminate hypotheses

State the unresolved question before each new compile or runtime experiment. Prefer static handler analysis when it directly resolves that question. Dynamic tests should discriminate alternatives, not simply repeat an already passing path.

| Question | Useful small distinction |
|---|---|
| Opcode versus inline data | Same operation, changed literal/length |
| Operand/register order | Unequal variables under subtraction and division |
| String concatenation order | Different left/right strings |
| Multi-argument string roles | Different start and length, with distinguishable characters |
| Constant folding | Literals versus variables, one operation changed |
| Variable slot allocation | Declaration/use order and frequency changed separately |
| Integer/float/string representation | One type change while keeping statement structure |
| Array address lowering | Constant subscript versus variable subscript |
| Loop encoding | Default versus explicit STEP; unnamed versus named NEXT |
| Loop frame search | One nested loop; named NEXT selects a particular variable |
| DATA versus code | DATA-only source line followed by READ; then RESTORE/re-read |
| Source grouping | Colon-separated statements versus separate lines |

Equal arguments and commutative operators can conceal reversed operands. If a prior probe used equal arguments, resolve roles from pointer arithmetic/copy length or a discriminating follow-up; do not pretend the symmetric test establishes the roles. Printed decimals can conceal representation/rounding differences: capture exact values/selected addresses when those are the claim.

Broaden one dimension at a time. Test documented syntax limits only after the ordinary compile/run/decode pipeline works; historical edition-specific complaints are leads, not measured limits. A RAM-only mutation can exercise another branch economically, but label it as a known mutation, restore it, and do not count it as an independent compilation or holdout.

### When to pivot between static and active evidence

Choose the method that can settle the remaining uncertainty, not the method already in progress.  Before another experiment or static-analysis pass, record: the question, competing hypotheses, their distinct predicted observations, the smallest safe fixture, required starting state/identity, and the stop criterion.  Repeated speculation without new discriminating evidence is a reason to change method, not to repeat a larger analysis.

| Remaining uncertainty | Prefer next | Required distinction |
|---|---|---|
| Bytes directly establish operand width, dispatch target, constant folding, or producer tag | Focused static/dataflow inspection | Explain the exact instruction path and boundaries; avoid a redundant compile |
| Which source form emits an operation, whether it is folded, or how typed operands are lowered | Small authorized compiler probe | Change one construct/type, keep asymmetric values, and preserve emitted bytes |
| Which representation or branch actually reaches a handler, or whether runtime/ROM state changes the result | Bounded active execution with targeted checkpoints | Capture relevant tag/register/input and result, not merely a plausible printed number |
| Emulator/compiler unavailable, unsafe input, or no authorization | Preserve a prepared fixture and explicit blocker | Tokenization, simulation, and static prediction are not compilation or target execution |
| A probe resolves lowering/branch identity but leaves a small native question | Return to static inspection of that exact path | Do not expand into a matrix after the discriminating question is answered |

For a sign/representation question, a useful tiny comparison includes negative, zero, and positive integers, fractional values of both signs, and variable-load versus literal forms.  State the language-level sign result independently.  Check whether the compiler removed the operation or changed representation; `0.0` spelling alone does not prove a floating runtime zero.  Observe the representation at the operation only when that distinction remains unresolved.  Avoid an omnibus, and add producer-specific probes only if existing lowering does not settle them.

**Compare emitted runtime identity before transferring results to a target.** An available compiler may emit a different handler or runtime revision from the program under study.  A successful ordinary-runtime probe does not validate a changed target handler.  Keep the source/interpreter expectation, actual compiler output, selected native path, observed execution, and narrow compatibility conclusion separate.  Preserve the first result, including failures or folding that makes a proposed probe nondiscriminating; do not patch the target or increase test scope merely to obtain the expected answer.

Compiler-free freezes remain intact.  If compiler assistance becomes authorized later, record that scope transition separately rather than rewriting the earlier experiment.  Active work must use preserved media copies and owned fixtures, not an original application merely because it contains the operation of interest.

### Preimage coverage is not behavioral conformance

A **BASIC preimage suite** exists to present documented source forms to a compiler and observe acceptance, diagnostics, sidecars and exact emitted bytes. Its primary results are source → compiler outcome → output identity/grammar. It is not automatically a stock-BASIC-versus-compiled behavioral test:

- valid BASIC rejected by an old compiler is a compiler restriction to record, not a defect this work must fix;
- accepted output need not be run merely to count an emitted form, especially for `LOAD`, `SAVE`, `NEW`, file I/O, blocking input, hardware writes, `SYS`, `USR` or `WAIT`;
- do not rewrite a broad preimage until it compiles and then silently claim the original form was supported—retain the rejection and any workaround as separate fixtures;
- do not patch the compiler/runtime or demand interpreted equivalence unless behavioral compatibility is a separately stated research question;
- compiler acceptance does not prove runtime correctness, and a semantic opcode name may still require static-handler evidence or a small discriminating execution test.

Prefer several bounded thematic files over one omnibus when that localizes diagnostics and survives per-file compiler limits. Keep each source line attributable to a language form, and isolate destructive/direct-mode forms in never-run compile-only files. First preserve the complete preimage and its compiler result; derive smaller one-feature probes only when needed to resolve an encoding ambiguity.

### Efficiently isolate failures in an omnibus

Keep a compiler-neutral baseline immutable. Derive named, hashed compiler-specific inputs with an exact change ledger; do not carry another compiler's exclusions forward. Accept documentation-authoritative restrictions when that is the agreed policy: exclude those forms before the first broad run, without spending negative trials rediscovering them. Record edition/option scope and contradictory documentation explicitly.

Before each retry, write the suspected cause, one discriminating edit and the expected evidence. Use this order:

1. **Reuse existing outcomes.** A passing prefix and a longer failing prefix implicate the added statements or their interactions with retained context—not the whole source again. Preserve stable source line numbers and compare exact deltas. Cached results require the same compiler/settings/input and relevant starting state; they are not universal facts about a filename.
2. **Prefer one evidence-backed subtraction over blind bisection.** A diagnostic, native failure gate or newly introduced construct may nominate a specific statement. Remove only that form and retry the implicated input. Source progress displays can lag; a final END/pass line is not proof that END failed.
3. **If no strong candidate exists, split the newly implicated region**, not every line accumulated so far. Preserve FOR/NEXT pairs, branch/subroutine targets, definitions/calls and required declarations. Record any scaffold or dependency edits separately. Do not assume failure is monotone as lines are added; layout, resource limits and feature interactions can defeat ordinary binary search.
4. **Classify progress by failure signature and compiler phase.** Passing an earlier reset and reaching a later syntax diagnostic resolves the earlier gate only. Keep reset, diagnostic, allocation question, incomplete SAVE, acknowledgment prompt, successful closed output and harness failure distinct. A generic failure status or timeout alone is not a useful isolation predicate.
5. **Use cheap negative controls only when they change the conclusion.** A whitespace-only rewrite can distinguish spelling/token-boundary claims from a naming restriction; removing a preceding line can test delayed attribution. Do not launch a matrix of controls once static evidence or one subtraction answers the question.
6. **Return to the full retained source after local resolution.** Continue from the next distinct failure. A companion read/call removed with a declaration or assignment is a dependency exclusion, not an independently measured rejection. Preserve every failed version, diagnostic, disk and intermediate file; never overwrite the failure with its workaround.

Successful compilation can conceal **silent omissions**. Audit zero-width source-map groups: they are normal for some declarations/comments, but suspicious for executable statements. When several suspect forms emit nothing, one grouped removal followed by whole-output byte comparison can establish whether that group affects generated code; split further only if the output changes or attribution remains ambiguous. Do not call a silently omitted statement supported merely because its token was accepted or its line appears in a map. Keep this category separate from syntax rejection and from legitimate hoisting/constant folding.

The ledger should record parent/input hashes, compiler options, exact removed/replaced lines, dependent edits, verbatim diagnostic/progress text, pass reached, output closure/hashes and the narrow conclusion. Compile-through success is not support for removed forms, nor behavioral equivalence. Unexpected lowering (for example, one source construct becoming several independent calls) belongs in the semantic findings, not merely the accepted-syntax column.

## 4. Reconstruct dispatch and operand contracts anew

For every new VM establish the entry, IP, fetch convention, dispatch classes, operand readers, state representation and image regions. A failed split-table recognizer is only a failed shape match—not proof of absent p-code. Look for interleaved pointer tables, compact variable classes, branch-offset/JMP stubs, switches and context-dependent secondary dispatch. A fetch can write the opcode directly into an indirect-JMP operand byte rather than indexing separate low/high tables.

Do not collapse opcode identities just because two entries point to the same handler. Incoming A/X/Y, carry/flags, self-modified operands or a secondary selector may distinguish load from store or operand width. Follow that context through the handler.

A runtime may deliberately ship with a nonfunctional fetch opcode or encoded initialization region. Reconstruct setup writes, capture one post-setup checkpoint, and compare exact bytes before analyzing the initialized VM. A raw disassembly is not the live architecture. Keep the original image, predicted transform and captured result separate; this does not authorize patching the runtime to make an experiment pass.

Track IP positions explicitly:

- header pointer versus first executable byte;
- increment-before-fetch versus fetch-then-increment;
- handler return to incrementing fetch versus direct fetch;
- saved call/loop cursor versus resumed opcode address;
- relative-target base and bias;
- inline bytes skipped by context-dependent/fused handlers.

Secondary selector bytes need their own known operand grammar and unknown-selector refusal; recognizing the primary opcode does not establish every variant's length. Some handlers consume a following marker directly instead of returning to central dispatch. Model such a marker as a contextual modifier/fused instruction, not as a universally valid standalone opcode. Verify each consumer's exact recognized set: superficially similar READ and INPUT handlers may use different tails and accept different modifiers. Include it in byte ownership and reject static targets or source anchors into its interior.

Do not assume one universal extra increment. Record width, signedness and endianness **per operand form**, even within one VM. A code address, variable address and descriptor pointer can have different byte order. Static control targets must hit decoded instruction boundaries; validate every entry of a target table, not just its first destination. A function-definition header may contain a descriptor pointer, body entry and skip-over-body target with different roles. Decode embedded function bodies separately and retain descriptor-indirect calls as indirect unless dataflow resolves them. A STOP/error-report operand may be a source line number rather than an address. Data pointers must not be misvalidated as branch destinations. Calls, returns and loop-frame destinations are distinct control classes.

A native-call argument tail can have a recoverable encoded boundary without a guaranteed runtime continuation: arbitrary callees may consume or modify the interpreter text cursor before returning. Preserve the tail and classify that return as dynamic; do not turn compiler acceptance or a lexical delimiter into a behavioral-equivalence claim.

An interpreter island is not necessarily one source line. The VM may leave its terminating colon/zero for central dispatch, or let a handler consume that marker itself; a final zero can also belong to the following metadata separator. Establish exact byte ownership from the bridge/return path. Retain tokenized BASIC statements explicitly instead of falsely inventing one p-code opcode per BASIC keyword.

A FAC/ARG runtime need not evaluate in source order or behave like a postfix stack. Comment register roles before imposing algebraic names. In particular, one arithmetic opcode may compute ARG minus FAC while another computes FAC divided by ARG. Variable slots may be frequency-ranked, not ordered by first declaration. Compact and extended variable tables can use different record strides; a compact-slot threshold is not the compiler's maximum variable count. Test across that threshold and inspect address arithmetic rather than extrapolating the first table. Recovering a slot number is not recovering the original variable name.

A successful typed READ path need not have one universal stack effect: empty-string, numeric and conversion paths can write the same value register while updating depth differently. If the DATA tag/cursor is unproved, discard post-state facts rather than assuming a normal push. Keep numeric-looking strings as their encoded DATA type.

Closely related runtimes can share operand grammar while differing semantically. Audit changed flag producers, not just relocated addresses: a seemingly harmless inserted increment can change which condition a following branch tests. Preserve evidenced defects with partial VM operations; do not reconstruct the compiler's apparent source intent as if it were actual behavior.

Constant array indices can become direct element-address operands, while variable indices select a base and compute an address. Array loads/stores can share general typed-value stack primitives with loop setup. Reuse semantic primitives only after their native contracts agree.

## 5. Treat source maps as evidence, not authoritative source recovery

Inspect the actual disk file type. A line-map sidecar may be SEQ text/binary data with no PRG load header even if a generic extractor gives it a `.prg` filename. Conversely, an address-list PRG can use tokenized BASIC records with dummy on-disk link words; establish the actual record/consumer contract instead of blindly traversing those words as memory pointers.

Verify headers independently against native startup and loaded-image bounds. Test whether an endpoint is inclusive, exclusive, one-past an internal cursor, or merely a compiler bookkeeping value. Cross-check map offsets against decoded boundaries; never use a plausible source line to guess an unknown instruction's length.

Preserve:

- repeated line numbers and repeated offsets;
- lines that emit no main-p-code bytes (DATA, DIM, REM, empty constructs);
- compiler-appended instructions and repeated final-line anchors;
- unknown tails, padding and footer bytes.

A loaded runtime buffer can contain stale compiler or target-source text. Keep it opaque unless execution or the writer proves a role; do not covertly use it as source evidence in a binary-only frontend. Pin stable runtime windows rather than buffers, and test independence by mutating the unused residue while requiring unchanged lifted semantics.

One zero footer is not proof of a sentinel. Multiple output examples may expose variable or stale bytes; retain them opaque until the writer/reader establishes their meaning. A matched map aligns supplied source but cannot authenticate it as the original. Keep that qualification visible in text/JSON. Do not attribute DATA, initialization or descriptors to the main instruction stream merely to get complete byte coverage.

For the requested presentation, print the supplied BASIC line above its instruction group, with exact addresses/bytes, neutral mnemonic and useful semantic comments. Mark extra map records rather than silently discarding them. Keep source grouping separate from reachability and CFG construction.

## 6. Promote discoveries only with narrow regression evidence

For each form retain: opcode/class, incoming dispatch context, operand grammar, IP update, native handler evidence, source/probe correspondence, semantic confidence and open cases. Curated ROM-symbol references can themselves be wrong: where a label conflicts with source/handler behavior, verify the pinned ROM's function vectors and code/data bytes before assigning semantics; correct the reusable reference rather than perpetuating the label. Add a regression for each new grammar hazard—not a redundant runtime test for every spelling.

The deterministic gate should cover unknown/truncated operands, byte coverage, map anchors, typed control targets, duplicate mappings, mixed endianness and repeatable JSON/text. Use synthetic fixtures for parser/refusal behavior so tests need no commercial runtime. Preserve actual compiler outputs privately as integration evidence and fingerprint the exact supported runtime family.

Report separately:

- bytes/instructions decoded in each fixture;
- forms actually emitted and executed;
- forms accepted from static-handler evidence only;
- synthetic parser tests;
- native observations/traces and declared instrumentation;
- known mutations, independent programs and different runtime revisions.

Compact variable aliases are not dozens of independently tested language features. Full coverage of tiny programs does not imply arbitrary-program support. A successful visible result does not validate every intermediate fetch; instrument a central fetch only when needed to settle a concrete control/length uncertainty, and account for direct/fused handler transitions. After corpus-driven expansion, freeze the decoder/profile before obtaining a fresh compiled output; vary a structural parameter (such as table arity) rather than just replaying the development example. Label an authored smoke holdout as such, preserve its first result, and distinguish later annotation-only corrections from grammar changes.

## Binary-only reconstruction is a separate gate

A source-correlated listing is not an independent reconstruction. A binary-only
frontend must not accept the target preimage, source-derived annotations or
expected statements. Previously learned compiler grammars and binary-retained
names are legitimate. Distinguish embedded BASIC from inferred BASIC-like text,
and preserve low-level instructions, opaque regions and generated names.

Use family-specific accumulator/stack contracts; symmetric tests can conceal
wrong noncommutative operand order. A false branch is `expression = 0`, not
necessarily BASIC's bitwise `NOT expression`. Preserve compiler evaluation
order around loop-variable initialization and snapshot side-effectful calls
rather than duplicating expressions. Unknown effects and control joins must
invalidate I/O state as well as arithmetic registers. Typed stores and native
arithmetic helpers need not preserve old accumulator facts.

File-access audits establish process input independence, not semantic accuracy.
Previously inspected and self-authored programs remain development evidence.
For independent blind validation, withhold a genuinely unseen target's source
from both analyst and process, freeze the first output, then reveal it. Keep
native-only operand discoveries distinct from fresh emission/runtime results.

## C64 live-input efficiency note

At a confirmed stock KERNAL line-input prompt, a short exact command can be queued while paused: arm the expected completion wait, require an empty ten-byte keyboard buffer, write command plus RETURN, then count, resume and inspect the result. Use warp for slow compilation and restore it afterward. Physical repeat-capable keys held across tool round trips can accumulate input much faster under warp. Do not generalize stock line-input behavior to custom GET/PEEK editors. Keep harness failures separate from compiler failures; do not turn compiler discovery into a debugger investigation without authorization.
