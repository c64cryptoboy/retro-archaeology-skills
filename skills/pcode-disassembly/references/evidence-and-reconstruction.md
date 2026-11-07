# Freezes, generalization and reconstruction boundaries

> Read [SKILL.md](../SKILL.md) first. This is the detailed procedure for the routed phase, not an instruction to expand every task. Commands and inline file paths below are relative to the **skill directory**, unless explicitly stated otherwise; Markdown links resolve from this reference.

### 8. Preserve a milestone; freeze before an oracle only when required

For compiler-assisted work, retain a reproducible milestone without claiming an independent compiler-free reconstruction. For an explicitly compiler-free effort, freeze before consulting the oracle. Record immutable hashes for inputs, core, profile, tests, traces, reports, and canonical JSON/text. Record:

- bytes/instructions covered and unresolved;
- opcode values/forms seen and absent;
- confidence totals;
- overlap and CFG diagnostics;
- runtime validation;
- unsupported behavior.

After the freeze, compiler/manual findings must use a separately labeled profile/output and must not improve the frozen score retroactively.

### 9. Test generalization honestly

Report these levels separately:

1. same binary deterministic reproduction;
2. known mutations (useful, but not a holdout);
3. unseen program from the same compiler/runtime;
4. different runtime revision;
5. unfamiliar compiler/VM discovery.

A fixed profile can succeed at levels 1–3 while offering only heuristic dispatcher candidates at level 5. Semantic/profile discovery remains an LLM/human evidence task.

## Source-blind reconstruction boundary

Use `scripts/reconstruct/reconstruct.py` for binary-only inference, not the supplied-source annotation renderer. It accepts neither source/maps nor annotated-report inputs. Static fingerprints identify families, not full decoding support. Keep embedded BASIC distinct from inferred statements; expose generated names, known-length semantic gaps, runtime conversions and indirect control. Preserve exact low-level instructions and loaded-region boundaries.

Do not substitute bitwise BASIC `NOT` for a zero-test branch. Capture effectful values once; invalidate facts at joins/calls and account for compiler-specific loop evaluation order. Preserve unknown facts rather than maximizing a cosmetic reconstruction percentage. See the [reconstruction guide](../references/reconstruction-tools.md).

An analyst's previously inspected or self-authored programs remain development fixtures even when the executable algorithm reads binary only. Independent blind validation requires a genuinely unseen target, source withheld from analyst and process, and first-output freeze before reveal. Source-blind is not compiler-free.

## BASIC-only temporary policy

Across compiler families, **synthetic temporary assignments in BASIC-only
listings are an exception requiring a high bar of justification**, not the
normal presentation of compiler/lifter bookkeeping. Detailed p-code and internal
representations may retain captures freely; a generated `T_` or `T_VALUE_` name
is not evidence of an original BASIC variable or assignment.

- **Prefer faithful source-level expressions and constructs.** Recover the
  complete expression, ON selection, FOR structure or other evidenced BASIC
  construct before exposing intermediate captures. The aim is to preserve the
  program's evaluation order, not make the original BASIC supposedly "safer".
- **Check the whole expression, not just a greedy intermediate substitution.**
  Several adjacent captures may need substitution together before the complete
  read/call/arithmetic order matches the original instructions. A local refusal
  is not proof that a temporary belongs in the BASIC-only view. Preserve tree
  shape, evaluation count, control flow and provenance; do not remove a capture
  by duplicating effects, reassociating arithmetic or changing actual order.
- **Require a concrete case, not a generic hazard.** RND, PEEK, clock/status
  reads, FN calls and hypothetical interrupts do not by themselves justify
  visible assignments. Identify the capture and uses by instruction address,
  the specific duplication/order/control problem, and why a faithful expression
  or BASIC construct has not resolved it. Compare against the original program's
  semantics, not an incorrectly expanded reconstruction.
- **Label the remaining limitation honestly.** If the current tool cannot
  reconstruct the higher-level form, say so rather than claiming the original
  BASIC needed a temporary. Keep any unavoidable synthetic assignment clearly
  distinguished from recovered source assignments, with its specific reason in
  accompanying evidence. Do not hide an unresolved semantic gap to obtain a
  cosmetically temporary-free listing.

This is a presentation/review policy, not a claim that every existing emitter
already enforces it. Preserve detailed evidence and old freezes; it does not
by itself authorize regenerating previously delivered listings.

## SYS normal-return reading default

Apply this BASIC-level reading policy across compiler families, including when
revisiting BLITZ/Austro-Speed, Speedcompiler, PETSpeed, BASIC-64 and DTL:

- **Use the ordinary documented contract.** A recognized SYS normally resumes at
  the following BASIC statement. Reason about the surrounding statements using
  that continuation, rather than treating every SYS as an opaque control-flow
  barrier. Resolving the target or inspecting its machine code is not a
  prerequisite for this working assumption.
- **Require evidence in the BASIC before discussing abnormal flow.** Embedded
  or reconstructed BASIC must give a concrete reason to question normal
  continuation. An unknown callee, arbitrary machine-code capabilities or the
  mere possibility of a nonlocal transfer do not meet that threshold. Record the
  actual BASIC evidence when an exception warrants investigation.
- **Write useful program commentary, not blanket disclaimers.** Do not repeat
  generic warnings that a SYS might fail to consume arguments or return. Infer
  purpose from coherent call-site usage and qualify that interpretation where
  appropriate. Native analysis can refine argument meanings and effects; it is
  not required simply to justify ordinary sequential reading. Record the normal
  return assumption once in methodology, not as a warning at each call.
- **Keep return flow separate from state effects and byte evidence.** Normal
  continuation does not imply purity or preservation of variables/memory. Retain
  call-effect safeguards for expression movement. Do not guess operand lengths,
  borrow another VM's ABI or relabel an assumed continuation as an encoded target.
- **Carry the lesson forward without rewriting history.** Existing decoder/index
  caveats and frozen listings describe limits of their static analysis; they are
  not positive evidence of abnormal program flow. Apply this policy in analysis
  now and in presentation/tool revisions as each family is revisited. Preserve
  earlier freezes; this guidance alone does not change decoder behavior.

## Idiomatic-reading lessons across VM families

Apply the mandatory [BASIC reading-quality gate](basic-reading-quality.md) to every
new or revised human-facing listing.  The following family-admission boundaries
must not be misread as a reason to retain redundant parentheses, raw binary-decimal
expansions, or unjustified bookkeeping in another family's readable output.

Share mechanisms and refusal tests, **not unproved VM semantics**. The current
optional idiomatic projection is admitted for DTL only; BLITZ/Austro-Speed,
Speedcompiler, PETSpeed and BASIC-64 retain their existing behavior. When revisiting
one of them, use the following as a review checklist rather than silently enabling
DTL's rules:

- **Separate evidence from presentation.** Preserve detailed groups, instruction
  bytes, encoded targets, warnings and indexes; make merged readings an additive
  projection with complete ownership/provenance. A cleaner view is not additional
  decoded coverage, recovered original source or a semantic-accuracy percentage.
- **Use structured trees and semantic identities.** Expression substitution and
  parenthesis removal must not be string replacements. Keep operand nesting:
  floating-point `A + (B + C)` need not equal `(A + B) + C`. Captured temporaries
  are references to already evaluated values, not fresh mutable reads.
- **Single use is necessary, not sufficient.** For
  `T1=RND(1):T2=RND(1):A=T2-T1`, replacing both temps with
  `A=RND(1)-RND(1)` reverses which draw occupies each operand. Compare the proposed
  read/operation order with original VM instructions, not just the printed lines.
  Include arithmetic/error timing and typed stores, not only obviously effectful
  calls. Refuse duplication, changed order, joins, alternate entries and opaque
  effects without the relevant family's stronger proof. This synthetic example
  tests substitution correctness; it does not establish that original BASIC
  needs extra assignments. Apply the [BASIC-only temporary policy](#basic-only-temporary-policy)
  before exposing internal captures in a reading copy.
- **Prove loop order separately.** Some VMs capture a limit/step before a later
  initializer, while a DTL initializer corridor can establish the opposite order.
  A common `FOR` spelling does not prove a common ABI. Preserve conversions and
  intervening effects; omit only an encoded default step, not a computation that
  happens to yield one. Named NEXT and frame search are separate questions.
- **Definitions do not execute their bodies now.** A one-expression DEF FN view
  needs a proved descriptor/formal/skip/return structure and separate deferred-body
  provenance. It does not establish purity or the binding of every indirect call.
  Keep captured, multi-group or ambiguous bodies explicit when those contracts
  have not been proved for the family.
- **Distinguish Boolean values, bitwise operands and control flow.** Negating a
  comparison-only AND/OR tree is a Boolean display identity, preserving eager
  evaluation order. Arbitrary numeric predicates still need a zero test; do not
  use bitwise NOT as truth negation or replace conditional paths with eager AND/OR.
- **Format only evidenced syntax.** Token-aware keyword spacing must preserve
  strings, DATA, REM and opaque native tails. Do not invent PRINT separators.
  Short decimal literals require a target-parser/value-representation exact round-trip
  contract; a host float or prettier decimal is not such a proof.  Once established,
  generate short candidates with exact decimal arithmetic and accept only fully
  consumed, exactly equal target values/encodings.  Include the actual packing and
  rounding step, retain exact originals/sites/parser identity, and preserve refusals
  for neighboring values.  The [shared procedure](basic-reading-quality.md#short-numeric-spellings)
  also covers carried immutable literals and distinguishes equivalent readable
  spellings from historical source-text recovery.
- **Test both admission and refusal.** Use independent expression parsing/tree
  expansion, event-order/entry checks, immutable detailed evidence and replay.
  Include repeated uses, reversed effects, mutable reads, error-order changes,
  deferred bodies, typed loops and quoted-token boundaries. Keep synthetic,
  known-development/corpus and genuinely blind evidence distinct. Passing these
  gates does not prove asynchronous timing or hidden native-entry equivalence.

`expression_display.py` and `reading_projection.py` provide neutral mechanisms;
`dtl_reading.py` supplies the presently evidenced family-specific admission rules.
An additional family needs its own contracts and isolation/regression fixtures,
not a renamed DTL adapter.

## Validation boundary

Bundled tests exercise synthetic decoding, refusal, symbolic and formatting contracts. Successful decoding covers only the declared regions and encodings of the selected profile; it is not universal compiler support or, by itself, source reconstruction, reachability proof or behavioral equivalence. One private external Austro-Speed revision holdout has validated the distinct identity/decoder-contract mechanism, operand-free conditional return and retained DATA; its title-specific evidence is not bundled. Retain real-program validation and frozen holdout evidence separately, with exact input identities and explicit limits.
