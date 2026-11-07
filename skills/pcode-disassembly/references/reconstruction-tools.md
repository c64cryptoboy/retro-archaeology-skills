# Compiler-family identification and binary-only BASIC-like reconstruction

These are separate, conservative capabilities. Python 3.10+, standard library;
keep the bundled decoder/profile directories and `scripts/reconstruct/` together. No
emulator, compiler installation, source file or line map is required.

## Corpus searches

This CLI analyzes supplied PRG or mapped raw-image bytes; it is not a disk-image or filesystem walker.  For a corpus search, first follow [storage coverage and partial-component identification](corpus-search.md): inspect different file systems, directory/boot/loader layouts, and supported physical encodings instead of stopping at normally extracted PRGs.  Partial evidence can identify a component without recovering a complete file; it must not be given a fabricated PRG header or load address, or treated as automatic decoder admission.

## Commands

From the skill directory:

```sh
python3 scripts/reconstruct/identify.py program.prg
python3 scripts/reconstruct/reconstruct.py program.prg \
  --json-output reconstruction.json --text-output reconstruction.txt
python3 scripts/reconstruct/reconstruct.py dtl-object.prg \
  --json-output dtl.json --text-output dtl-full.txt --basic-output dtl.basic.txt
python3 scripts/reconstruct/identify.py payload.bin --raw-base 0x0801
(cd scripts/reconstruct && python3 -m unittest -v)
```

Output files are created exclusively: choose new names rather than overwriting
previous evidence. No input is executed or modified. The reconstruction CLI
intentionally has **no source, map, annotation or expected-statement option**.
The primary library entry point is `reconstruct.reconstruct(binary_bytes)`;
`symbolic.lift` is an internal adapter for newly generated decoder records, not
an annotated-report import interface.

## Identifier contract

`identities.json` contains hashes and address windows, not commercial runtime
bytes. Recognition covers distinct evidenced BLITZ, Austro-Speed, INPUT64
Speedcompiler, PETSpeed and BASIC-64 runtime signatures, DTL/Jetpack object
bootstrap, and original-header DTL runtime-library PRG. It does not identify arbitrary
relocated runtime dumps or all revisions of these products.

Results are `identified`, `ambiguous` or `unknown`, with family, matched role,
confidence qualification, exact hash evidence and independent layout result.
A fingerprint may also name a distinct `decoderFamily` when an evidenced runtime
revision retains one product identity but uses another already-audited VM contract;
the reconstruction keeps those identities separate. A known library or malformed
object can be identified without being decodable.
A match is evidence of included implementation bytes, **not historical
compiler authorship, runtime reachability or version detection**.

Exact signatures are deliberately narrow. Patched, packed/encrypted, detached,
native/mixed or unfamiliar output may be unknown. **No match is not proof that
no BASIC compiler was used.** Renaming a file cannot change the result.

## Optional runtime-region catalogs

`runtime_signatures.RuntimeCatalog(catalog).match(binary_bytes, raw_base=None)` recognizes additional reviewed runtime components without changing the default identifier or decoder gates.  The module has no default catalog or private dependencies.  Catalog schema `basic-runtime-regions-v1` contains `entries`, each with a unique `id`, `family`, optional `loadAddress`, and nonoverlapping `windows` containing `start`, exclusive `end`, and `sha256`.  Every window in an entry must match at its mapped address; the PRG header is excluded from window hashes.  An explicit `raw_base` supports headerless memory images.

Use separated, coherent native-code witnesses when supported by prior analysis, preserving literal operands and connected references.  Do not replace missing evidence with generic opcode shapes or uncalibrated fuzzy thresholds.  This matcher performs no address masking, relocation, unpacking, or decryption.  Provenance fields are inert metadata, not file dependencies or whole-input recognition rules.

Matches have role `runtime-component`, `layoutValid: null`, and `decoderAdmitted: false`.  They prove only that the required regions are present, not that unmatched bytes are intact or reachable.  Keep these results separate from exact decoder contracts, source attribution, and complete-game claims.  Caller-side aggregation must preserve conflicting families and candidate-only evidence.  Test with `python3 -m unittest -v test_runtime_signatures` from `scripts/reconstruct/`.

## Reconstruction contract

Read the mandatory cross-family [BASIC reading-quality gate](basic-reading-quality.md) before generating or revising a human-facing listing.  Exact evidence and readable presentation are separate deliverables: structured precedence, proved Boolean simplification, and short target-proved literals belong in every family's revised reading, not only DTL.  Built-in adapter limitations below describe current tooling, not an exemption from that quality gate.

The goal is an **“Occam's BASIC preimage”**: a simple, readable representative
consistent with the compiled behavior and evidenced compiler/runtime semantics,
not the author's exact original expressions. Many-to-one compilation is normal,
not a reconstruction defect. Prefer clear code and few unsupported assumptions,
not code golf. Equivalent source choices are distinct from uncertainty about
behavior; validation should compare semantics rather than textual identity.
Byte-identical recompilation is a separate claim requiring a round-trip check.
The current partial reading aid is a step toward that goal, not a claim that
all emitted headings already constitute a validated BASIC preimage.

For BASIC-only output, apply the [high-bar temporary policy](evidence-and-reconstruction.md#basic-only-temporary-policy):
prefer complete expressions and faithful BASIC constructs over visible synthetic
assignments. Internal captures are not recovered source variables; retaining one
requires a specific evidenced justification, not a blanket claim of safer order.
This policy does not claim all existing emitters already implement that projection.

For BASIC-level SYS control-flow reading, use the ordinary next-statement return
contract across compiler families. Discuss abnormal flow only when the BASIC
itself supplies concrete evidence; an uninspected callee is not a reason to
withhold normal continuation or repeat return warnings. See the shared
[SYS reading policy](evidence-and-reconstruction.md#sys-normal-return-reading-default).
This is an analysis/presentation policy, not a claim that existing decoder output
has already been revised; normal return and native state effects remain separate.

The frontend identifies a supported object, derives its layout from binary
fields, invokes its existing refusing decoder, then runs a family-specific
symbolic adapter. Unknown operand lengths still stop reconstruction; unknown
*semantics of a known-length instruction* remain visible as unresolved groups.
This is not a universal decompiler or a claim that a recognized revision's
entire output space is supported.

- BLITZ and DTL have separate logical-expression-stack adapters.
- Austro-Speed reuses audited BLITZ grammar but has distinct identity and runtime
  contracts. The supplied `$1F79` runtime's multiplication defect is not silently
  translated into ordinary `*`; a separately evidenced older `$1F93` runtime
  explicitly selects the byte-compatible BLITZ contract instead.
- Speedcompiler has a separate integer-stack, lazy floating-stack and three-string-
  frame model in `speedcompiler_lift.py`. Read the [scope guide](austrospeed-speedcompiler-tools.md).
- PETSpeed models FAC/ARG and its typed spill stack, with explicit asymmetric
  subtraction/division/string operand order.
- BASIC-64 models floating FAC/ARG, integer value/ARG, alternate values and
  string descriptors separately. The selected optional native-expanded profile
  adds twelve evidenced operand contracts without modifying the original profile.
- Simple symbolic contracts live in `semantics.json`; complex array, loop,
  interpreter-bridge and statement adapters are explicit in `symbolic.py`.
  There is no common assumed opcode encoding or universal postfix renderer.

The text places BASIC-like headings above owned p-code spans. JSON retains
instruction operands, evidence addresses, generated/retained symbol provenance,
coverage categories, all loaded-region boundaries/hashes and retained DATA.
Every decoded instruction is owned once; a value can depend on earlier groups.
Profile hashes describe normalized selected profiles, including binary-derived
BLITZ layout; retain file hashes separately when freezing implementations.

Group kinds are **inferred**, **embedded**, **structural**, **partial** and
**unresolved**. Coverage counts owned instructions in those categories—not
correctness percentages or numbers of recovered original source lines.

### DTL expression presentation

Generated DTL headings use structured expression nodes to remove redundant
parentheses, rather than rewriting emitted BASIC with regular expressions.
For example, `A = (1 + INT((X * 20)))` reads as `A = 1 + INT(X * 20)`.
A false branch whose complete root is a comparison uses its opposite relation:
`IF ((A > B)) = 0 THEN ...` reads as `IF A <= B THEN ...` (also `= ↔ <>`
and `< ↔ >=`). Arbitrary numeric predicates still test against zero; they are
not replaced by bitwise `NOT`. Unknown expressions do not gain inferred facts.

Parentheses preserve the **evaluation tree**, not just algebraic equivalence:
`A + (B + C)`, `A / (B * C)`, nested comparisons, powers and unary/logical edge
cases retain necessary grouping. The detailed headings do not reassociate, fold
constants, duplicate effects or remove evaluation-site temporaries. Their embedded
BASIC, quoted contents and native SYS tails are untouched. Canonical expression text
and all navigation/provenance metadata retain their earlier explicit forms;
only generated headings become less cluttered. Other built-in VM adapters retain their
existing presentation; a revised reading for those families must still apply the
shared quality gate using their own evidenced nodes and contracts. An internal explicit-display path supports regression
checking; this does not add a public CLI mode or make the readings runnable.

### Optional idiomatic DTL reading

`--basic-output` writes a separate compact view, also retained as the additive
`readingView` JSON field. `reading_projection.render_reading(report)` is the
portable library renderer. The default detailed text, original groups, rows,
coverage, warnings and all existing indexes remain unchanged. Each projected line
lists its original group/instruction ownership, transformation actions and modeled
evaluation identities; retained temporaries and refusals remain inspectable.
Other compiler families currently refuse this optional output rather than borrowing
DTL semantics. Output files still use exclusive creation.

The current DTL adapter can inline an adjacent, single-use RND/PEEK/FRE/POS temporary only
when the substituted structured expression preserves the **original instruction
order** of reads and operations, including arithmetic/error timing. It never uses
regular-expression replacement of BASIC text or compares only printed ordering.
Repeated uses, reordered operands, opaque calls, explicit interior entries, region
gaps and unsupported corridors refuse. Synthetic captures around descriptor FN
calls are not declared safe merely because their names resemble ordinary temps.

A uniquely typed, already-associated initializer may be fused into its FOR reading
when that same ordered-corridor check passes. Initialization still precedes bound
and step evaluation. Only an encoded default unit step is omitted; an explicit
STEP expression, even literal 1, remains. Named NEXT and loop pairing are unchanged.
Embedded keyword spacing is based on token bytes and quote/REM/DATA state. **No
PRINT semicolons or other separators are inserted**; existing separators, quoted
bytes and native SYS tails retain their spelling. This projection remains a
qualified local reading, not original/runnable BASIC, asynchronous timing or hidden
native-entry equivalence.

A recognized definition with one complete result expression may read as
`DEF FN F(X) = expression`. Its body remains **deferred until a call**, with
separate definition/body evaluation identities. Within that body, single-use
results—including nested FN calls and captured earlier reads—can be substituted
only when the complete read/call/arithmetic/return order remains exact. This moves
an expression into its use, not the called function's implementation: calls still
occur once, in order, and need not be pure. Ordinary outside-function FN temporary
policy is unchanged. Repeated uses, reordered operations, opaque operations,
non-expression statements and incomplete or ambiguous bodies stay explicit.

Only after independent p-code recovery, an immediately adjacent embedded DEF FN
may share that reading line when the complete decoded spelling matches apart
from spaces outside quoted strings, and no foreign explicit edge enters the
embedded statement. Different spelling/parenthesization stays separate; embedded
text never supplies a missing inferred expression. `definitionRepresentations`
records both inferred and embedded sites, `definitionEvaluationOrder` retains
both setup sites, and original group/instruction ownership remains exact. This
coalesces a display, not execution or provenance. Redundant header/temporary/return
bookkeeping comments move to `detailWarnings` and the unchanged detailed listing;
meaningful arithmetic/conversion limits remain visible. Neither purity nor dynamic
descriptor binding is proved. Complete comparison-only AND/OR predicates may
use Boolean duality in a false branch, preserving eager operand order and tree
shape. Arbitrary numeric bitwise operands still use the explicit zero test;
chained control is not converted into eager logic. Exact decimal spellings are
not shortened without an evidenced target parser/round-trip contract.  Once that
contract is available, use it rather than treating binary-decimal expansions as
mandatory readable text; retain exact values in evidence.  The shared
[short-literal procedure](basic-reading-quality.md#short-numeric-spellings)
covers candidate generation, full target parsing/packing, exact equality, and
refusal/provenance.

The neutral expression/statement machinery is shared; admission remains DTL-only.
See the [cross-compiler lessons](evidence-and-reconstruction.md#idiomatic-reading-lessons-across-vm-families)
before enabling another family rather than copying these ABI assumptions.

### DTL function bodies and cross-references

For DTL, JSON includes `functionIndex` and text includes a function index ahead
of the owned p-code listing. Names and formals come from uniquely typed binary
scalar records. The evidenced association is
`FN_CALL.value == DEF_FN.descriptorOffset + 3`, not a name match. Each definition
records its header, body entry, continuation, formal, static call sites and
recognition/refusal reasons; calls retain **all** matching definition candidates.
Embedded BASIC definitions remain separately labeled and are not converted into
p-code descriptor links.

A contiguous inline body with a final FN_RETURN, consistent bounds/targets and
no foreign explicit entry, nested/overlapping declaration or unsupported control
can display `DEF FN name(formal)` and `RETURN FN name = expression` headings.
These are reading blocks, not runnable BASIC syntax or a forced one-line original
expression. Effectful operations keep their evaluation-site temporaries and
warnings. Unknown expressions remain partial even in a recognized block.

The index is **static navigation, not runtime binding or purity proof**. A call
before a definition, multiple definitions, embedded BASIC or native mutation can
change whether/which descriptor is installed. One candidate does not prove it
executes. Recursive/inter-function calls are indexed but never inlined. Refused
bodies retain the old placeholder and explicit reasons. Other VM families do not
inherit DTL's offset, call or body contracts.

### DTL whole-object array associations

DTL JSON includes `arrayIndex`: retained DIM declarations, descriptor registration
sites, typed array access sites, accepted associations and refusal reasons. A
whole-object prepass pairs **contiguous, same-region** DIM islands with their
complete following registration bundle (delimiters allowed). Names and ranks
come from the binary's DIM syntax; bounds are not evaluated. Code physically
before a declaration can therefore use its unambiguous static name/rank.

Missing/interrupted registration bundles, foreign explicit entries into a
pairing corridor, conflicting declarations and typed-use mismatches refuse
association rather than guessing the number of subscripts. Consistent repeated
declarations remain indexed, not assumed to execute successfully. Forward-use
headings carry an explicit initialization caveat. The index is **not proof that
DIM executed, storage is initialized, bounds are valid, or native code cannot
change descriptors**. Unknown expression operands and control/effect barriers
remain intact. No external source/map or other family's array ABI is used.

### DTL variable and subroutine navigation

DTL `staticIndex` records typed scalar/array reads and writes by **storage
namespace plus byte offset**, with copied instruction operands, bytes, address
and region. Scalar names come from unique typed binary table records; array
names/ranks reuse `arrayIndex`. Missing/ambiguous names remain unnamed, and typed
operand mismatches are flagged rather than normalized. Retained scalar records
without indexed uses are not declared dead.

Loop setup references, named NEXT implicit read/write, descriptor reads/writes,
and DEF formal references have separate roles—not invented ordinary assignments.
Unnamed NEXT and FN_RETURN effects remain runtime-selected. Embedded BASIC,
SYS/USR, PEEK/POKE and runtime setup sites are separately visible; their effects
are not expanded into named-variable references. READ/RESTORE cursor locations
and TI/TI$/ST selector accesses are navigation only, not DATA-field matching or
complete state analysis. Names appearing inside embedded statements are not
silently counted as decoded operand accesses.

`callSites` and `subroutineTargets` retain explicit GOSUB and ON-GOSUB targets,
callers, both regions and ON-table entry positions (including repeated targets).
Malformed target/table shapes remain refusals. GOTO and descriptor FN calls are
not conflated with these edges; FN associations stay in `functionIndex`. RETURN
sites are listed **without pairing them to calls or inventing routine extents**.
JSON and the readable index explicitly disclaim reachability and completeness.
This metadata pass does not alter symbolic headings, byte ownership, targets or
effect order, and is DTL-only.

### DTL runtime descriptions and SYS navigation

DTL `runtimeIndex` describes validated DIRECTIVE selectors using their existing
profile operation names. Headings expose those names instead of just `REM VM
DIRECTIVE`; inconsistent authored records retain a generic refused description.
This is **not propagation of STOP/POKE modes** or proof of later runtime behavior.

VARIABLE_FILE headings retain the counted filename with explicit JSON display
escapes, not executable BASIC quoting. Only a complete recognized saved header,
consistent header/data extent, loaded-end word and trailer permit a saved-mode
annotation. A nonzero flag at object base + `$85` selects the inline-table branch
on the evidenced normal handler path; zero merely makes the external-load branch
eligible if live skip/reuse flags do not bypass it. Missing/malformed context stays
unclassified. Saved bytes do not prove live flags, initialization, runtime identity
or availability/necessity of an external file. This does **not** add external VL
layout support or bypass a runtime fingerprint gate. The header/trailer provenance
is copied into JSON. These two description passes run after semantic replay.

DTL `nativeCallIndex` captures every SYS argument expression, its dependencies,
producer evidence, exact SYS tail and callee-controlled cursor/return caveat at
the existing expression-consumption site. It groups **literal-address candidates**
only: a single complete supported integer/packed-real literal with an exact
integral value in `0..65535`. Signed words retain their sign; fractional,
negative/out-of-range and malformed values do not silently wrap or round. Variables,
aliases, arithmetic, conversions, unknown values and effect temporaries remain
ungrouped with their expressions/reasons. No rendered BASIC is parsed to resolve
an address. Duplicate callers and their regions remain separate; targets are
sorted only for navigation. SYS headings/effects and the older opaque-site index
are unchanged. There are no native routine names, routine extents, complete call
graph, effective runtime binding, reachability or return-pairing claims. Other
VM families do not receive either index. The retained cursor/return caveat is
static-analysis metadata, not evidence of abnormal BASIC flow; apply the shared
normal-return reading policy rather than promoting it into repeated commentary.

DTL `nativeVariableIndex` separately groups SYS **input-variable references**, not
addresses. It requires a warning-free consumed expression with one immediately
adjacent, same-region short/long numeric scalar-load producer. Encoded opcode,
width/offset, unique scalar record, raw name/type and consumed expression must
agree. Identity is object-local scalar namespace/type/offset, not name alone.
Caller/producer provenance and the scalar record are copied; repeated callers
remain ordered. Arithmetic, array/string/function/effect results, missing or
ambiguous records and join-cleared facts stay unassociated. Assignments are not
followed: a fresh load identifies its variable, never its assigned value or alias.
A mutable variable may hold different values at different calls. This post-replay
navigation leaves every old heading, warning and index unchanged, including the
unresolved numeric target and reasons in `nativeCallIndex`. It proves neither
initialization, numeric conversion, actual callee, reachability nor return pairing.

### DTL FOR initializer provenance and zero-limit recovery

DTL `forIndex` links a FOR to the immediately preceding emitted same-offset,
same-type scalar assignment when typed binary identity, exact operand encoding,
contiguity, region and no-interior-entry checks agree. The heading receives an
address annotation; the assignment stays separate and is **not repeated or moved
after limit/step evaluation**. Intervening effect-temporary groups are not skipped.
Refused links retain reasons. This is local provenance, not original source syntax,
a global reaching-definition graph, execution proof or FOR/NEXT pairing.

One separate rule recovers an otherwise missing limit of zero through the exact
`INTEGER_SMALL 0` (`80`), long real scalar store (`D4`), same-variable unit real
FOR (`42`) sequence. It requires a lone complete zero producer before the destructive
store, an empty expression state at FOR, unique real scalar identity and no
alternate entry, intervening instruction or region change. A single-successor
proof marker is separate from the expression stack: **ordinary stores still kill
symbolic facts**. Source literal/store sites remain in the group's evidence and
index. This assumes completed initialization and the evidenced RTL's normal local
path; it does not prove hidden native/asynchronous behavior or which external RTL
will load. Zero magnitude survives these specifically checked conversion/store
handlers; arbitrary stored expressions do not inherit that property.

Short stores, alternate/computed zero encodings, nonzero values, integer/array
stores, integer/explicit-STEP FORs and extra lower expression values do not qualify
for zero recovery. Some can still receive initializer provenance independently.
Assignments, temporaries, original bytecode targets and NEXT headings are unchanged;
no structured-loop rewrite or runtime frame matching is performed. Other VM
families do not inherit either rule.

### DTL repeated false tests

DTL JSON also includes `falseTestJoins`. On the evidenced runtime's ordinary
no-STOP path, IF_SKIP_FALSE leaves a false typed value intact. A false edge that
lands directly on another such test therefore takes that test's false edge.
For a narrowly validated join, the **reading view** forwards those incoming false
edges, while displaying the separately computed fallthrough predicate normally.
Encoded targets and all instruction records stay unchanged; the index and group
warnings show `encodedTarget`, `readingTarget` and every test traversed.

Recovery requires same-region, well-formed, strictly forward tests; only IF-false
explicit incoming edges; a contiguous fallthrough producer; and exactly one
complete local predicate. Other stack/register/I/O facts are still cleared. A
separate discovery/replay follows FN value-capture analysis. Mixed incoming
control, malformed/looping edges, opaque producers, missing values and extra
stack values remain unresolved. Effects retain their evaluation-site temporaries:
this is **not eager BASIC AND**, general SSA, executable bytecode optimization,
or proof about hidden native entries, timing, STOP polling or asynchronous state.
Other VM families do not inherit this rule.

### Important limitations

- Output is a reading aid, **not runnable BASIC, exact original source, or
  proven equivalent stock BASIC**. Original spacing, grouping and line numbers
  generally cannot be recovered. `L_`, `V_`, `AR_`, `MEM_` and `T_` names are
  generated; they are not legal, mutually distinct stock-C64 variable names.
- Embedded tokenized BASIC is labeled separately. Control bytes appear as
  display escapes or `CHR$` expressions; display escaping is not original text.
- Joins, loop entries, calls and unsupported effects discard symbolic facts.
  Unknown output-channel state remains explicit rather than guessed as console.
- The detailed lifter materializes effectful expressions such as RND/PEEK/USR
  and clock reads once at their evaluation site. These internal captures record
  evaluation identities, **not actual memory layout/allocation or
  machine-code-observable behavior**. They do not justify synthetic assignments
  in BASIC-only output by themselves; apply the high-bar policy linked above.
- False branches use `expression = 0`, not BASIC's bitwise `NOT expression`;
  DTL direct comparison roots may instead use the opposite relation as above.
  PETSpeed FOR limit/step capture precedes its later loop-variable initialization.
- `VM_INT` and `VM_ROUND` denote runtime operations, not stock BASIC functions.
  Integer overflow, conversion, empty strings, errors, input retries, printing
  and function-parameter behavior can differ from interpreted BASIC.
- BASIC-64 array ranks/bounds come from binary descriptors; DTL uses the guarded
  whole-object DIM/registration associations above for static names/ranks. BLITZ/PETSpeed flattened
  indexes may be displayed as `ELEM_...` instead of invented original subscripts.
- Arbitrary function definitions and INPUT grouping remain partial; DTL's bounded
  named blocks/index above do not provide whole-function summaries. DTL descriptor FN calls retain
  earlier constant-derived or materialized values under the evidenced normal-return
  stack contract. A discovery pass identifies mutable lower-stack expressions that
  would be lost; a second pass selectively captures known values as `T_VALUE_...`
  **at their original producing instructions, before subsequent argument evaluation**.
  This preserves early scalar/formal/array reads without rereading them after a call
  or declaring the function pure. Uncaptured/unknown values, joins and opaque USR
  effects still invalidate facts; other families do not inherit DTL's stack ABI.
  These are display-level values, not actual target allocations, whole-function
  summaries or guarantees about arbitrary native, alias, DATA or I/O behavior.
  PETSpeed ordinary combined
  READ/GET/INPUT-to-element forms use the prepared destination with an index
  captured before input; integer-store conversion remains explicit. INPUT fields
  retain prompt/grouping/retry uncertainty. Unknown or mismatched destinations
  stay partial/unresolved; string READ with an integer descriptor-byte store is
  not normalized into an ordinary string READ. Post-input facts are discarded
  conservatively. Native/mixed-code lifting, external-variable/overlay layouts,
  arbitrary self-modification, path merging and whole-program I/O/function
  summaries are not implemented.
- DTL objects load an external RTL. Object-only reconstruction explicitly assumes
  the evidenced runtime associated with the recognized bootstrap; it does not
  establish which library would actually be loaded on a user's drive.
- DATA recovery is conservative: BLITZ retained field text is normalized with
  original quoting/grouping potentially lost; BASIC-64/DTL accept only the
  evidenced strict text envelopes. Speedcompiler preserves typed records, including
  numeric-looking strings as strings. Its numeric READ post-state remains unknown
  without a proved DATA tag/cursor. Other DATA remains opaque.
- A small observed BLITZ empty-variable-table form permits exactly seven
  appended zero bytes, retained as opaque rather than counted as a variable.

## Evidence and validation

Synthetic tests cover asymmetric arithmetic/string order, explicit numeric
conversion, unknown-state barriers, I/O joins, call/effect ordering, input
rejection, contextual input stores, pre-input destination capture, selective DTL
pre-FN value capture (including nested/formal/array aliases and refusal across
unknown effects/joins), DTL named-body/index recognition and refusal (typed offsets,
redefinition/recursion, foreign edges, effects, malformed boundaries and retained
embedded provenance), whole-object array association/conflict refusal, static
variable-role and GOSUB navigation (duplicate table entries, opaque effects,
refused links and other-family isolation), bounded FOR initializer provenance and
zero-only carryover (typed/encoding/entry/effect/stack-state refusals), directive/header
annotation guards, literal SYS navigation (signed/real encodings, unresolved expressions,
tails, effects, joins, regions and malformed evidence), numeric-scalar SYS input
navigation (short/long real/integer loads, raw type/name identity, relocation,
mutable/alias refusals and old-index preservation), structured DTL display
(independently parsed expression trees, comparison duality, grouping/precedence,
effects, opaque/quoted leaves and other-family isolation), typed-spill expression
order, array order, literal escaping, strict DATA envelopes, identifier
ambiguity/negatives and the bounded BLITZ trailing form. Known retained binaries
from six families exercise the complete binary-only CLI path. These are
**development tests**, not independently source-blind holdouts.

No original-source text is consulted by the reconstruction process, but that
alone does not prove semantic accuracy. For independent validation, select a
truly unseen target, withhold its source from both analyst and process, freeze
core/profiles and the **first** output, then reveal and compare. Previously
inspected programs and self-authored probes do not qualify. Keep successes,
refusals and corrections distinct. Source-blind is not compiler-free.
