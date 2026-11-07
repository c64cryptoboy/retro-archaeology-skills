---
name: pcode-disassembly
description: Reconstruct and disassemble BLITZ!, Austro-Speed, INPUT64 Speedcompiler, PETSpeed, BASIC-64, DTL BASIC/Jetpack and other 6502-hosted p-code VMs using profile-driven deterministic decoding and evidence-backed static, compiler-assisted, source-correlated and runtime analysis. Use for compiler-family identification, corpus searches across file systems and storage layouts, binary-only BASIC-like reconstruction, small compiler probes, fetch/dispatch mapping, operand grammar recovery, BASIC-above-p-code listings, CFGs, trace validation, explicitly compiler-free freezes and cross-program validation. Not a universal compiled-BASIC decompiler.
compatibility: Python 3.10+; optional C64 debugger for runtime evidence.
---

# BASIC-compiler and 6502-hosted p-code disassembly

Use the canonical deterministic decoders and external profiles. Analysis discovers architecture/semantics; code reproduces **explicit, evidenced grammar** and refuses unknown lengths. This is not a universal compiled-BASIC decompiler. Bundled offline tools use Python 3.10+ and the standard library; no agent harness, compiler installation or emulator is needed for established offline decoding.

## Choose the task before loading detail

| Task | Read before acting | Output / gate |
|---|---|---|
| Look up known compiled software, editions, or component roles | [Known software catalog](references/known-compiled-software.md) | Qualified compiler/company/title/year/part/encoding facts; not a filename-based detector or a whole-game claim |
| Search a corpus for compiler use, including unreadable directories or custom storage | [Corpus search and storage coverage](references/corpus-search.md) | Separate containers, file systems/loader layouts, and physical encodings; validated partial-component evidence and explicit coverage gaps |
| Identify a binary or produce source-free BASIC-like reading | [Reconstruction tools](references/reconstruction-tools.md) | Signature/role evidence and independent layout result; partial reconstruction with explicit gaps |
| Produce or revise reader-facing BASIC, for any family | [BASIC reading quality](references/basic-reading-quality.md), then the family guide | Structured precedence, evidenced Boolean simplification, short target-proved literals, justified captures, and inspection of the actual human-facing file |
| Export a separately admitted, fully known BASIC snippet as a PRG | [Known-snippet export contract](references/basic-prg-export.md) | Structured admission, decimal labels <=63999, typed aliases, exact PETSCII, independent byte/metadata checks; not a whole-reading executable claim |
| Select an existing family decoder | Relevant family row below; [scope/tool overview](references/scope-and-tool-routing.md) if unsure | Correct family/revision/mode, profile and CLI; no new VM archaeology by default |
| Recover a new VM/profile, decode unknown operands or instrument a fetch loop | [Profile recovery](references/profile-recovery.md) | Entry/fetch/dispatch and region map; explicit widths, targets, confidence and refusing decoder |
| Choose static analysis versus an authorized compiler/runtime probe | [Compiler-assisted discovery](references/compiler-assisted-discovery.md#when-to-pivot-between-static-and-active-evidence) | Explicit uncertainty, rival predictions, smallest discriminating observation, runtime identity, and a stop criterion |
| Analyze BLITZ semantic differences or compiler artifacts | [BLITZ semantics](references/blitz-semantics.md) | Scope-qualified hypotheses checked against bytes/probes; obey any compiler-free oracle gate |
| Freeze, compare with source, claim generalization or report reconstruction | [Evidence and reconstruction](references/evidence-and-reconstruction.md) | Preserved first outcomes; separate replay, mutation, new-program and new-revision evidence |

Read the applicable reference **before** using its workflow; do not load every family guide for one object. Resolve relative script paths from this skill directory unless a command explicitly changes directory.

## Existing family routes

| Family | Guide / implementation |
|---|---|
| BLITZ! | [Profile recovery](references/profile-recovery.md) for CLI examples; [scripts/blitz/](scripts/blitz/). Supply an independently evidenced profile; no title-specific profile is bundled. |
| Austro-Speed / INPUT64 Speedcompiler | [Family contracts/tools](references/austrospeed-speedcompiler-tools.md). Distinct identities; Austro reuses audited BLITZ grammar, Speedcompiler has a separate decoder/state adapter. |
| PETSpeed | [PETSpeed tools](references/petspeed-tools.md); [scripts/petspeed/](scripts/petspeed/). |
| BASIC-64 | [BASIC-64 tools](references/basic64-tools.md); [scripts/basic64/](scripts/basic64/). Tested optimizer-I/II p-code scope, not automatic native/mixed-mode support. |
| DTL BASIC / Jetpack64.4 | [DTL tools](references/dtl-tools.md); [scripts/dtl/](scripts/dtl/). Structural/profile decoding and supplied-source annotation; source-free reconstruction is separately best-effort. |

For a **corpus search**, read [storage coverage and partial-component identification](references/corpus-search.md) before choosing inputs.  Directory-extracted PRGs alone miss nonstandard file systems, boot/loader layouts, and supported custom encodings.  Complete file recovery is not required; retain compiler-specific evidence, and establish title/component association before making title-level claims.

Start simple when the task is identification:

```bash
python3 scripts/reconstruct/identify.py program.prg
```

Treat **native structural candidates** separately from exact runtime signatures.  Identification does not establish decoder support or historical producer attribution.  Route native structure and semantics to `6502-disassembly` / `6502-commenting`, not guessed VM opcodes.

## Non-negotiable contracts

- Hash/preserve original source, PRG, disk, snapshot and runtime inputs; distinguish original, reconstructed and approximate source. Keep commercial inputs, traces, title-specific profiles and specimen-specific operational reports outside distributable skills. The curated software catalog contains portable factual summaries, not those private artifacts.
- Declare **compiler-assisted versus explicitly compiler-free** scope before discovery. Only the latter imposes its pre-oracle freeze before consulting compiler/manual/opcode-table/third-party-decoder evidence. Preserve the freeze and first results when scope later changes.
- **Source-blind is different:** the process receives no source/maps/annotated reports; a genuinely blind evaluation also withholds source from the analyst and reserves an unseen target before the first run. Known objects and authored probes remain development fixtures.
- Identify container and output representation first. A PRG suffix is not proof of compiled code; a matching runtime/bootstrap is not historical producer attribution, execution proof or full decoder support. DTL may load an external runtime; BASIC-64 modes differ.
- Do not share operand grammar, stack order, integer/float semantics or target byte order merely because VMs are related. Native dispatcher candidates establish a shape, not product identity or operand widths.
- Unknown instruction length, truncated variable-length forms, overlapping boundaries or invalid targets must remain refusals/open gaps. `--allow-hash-mismatch` is compatibility research, not proof of compatibility.
- Keep encoded targets, structurally inferred targets and runtime-indirect edges separate. Use neutral `OP_1D`-style names until semantics are evidenced.
- Accept different evidence forms at their proper scope: bytes, source, manuals, observed execution, and firsthand user observations.  Missing static mechanism analysis does not negate a directly observed visible outcome.  Record provenance and context; distinguish an established outcome from an untraced implementation, and do not present a reported observation as an agent replay.
- Validate exact region coverage, strings/ON forms, target starts, trace transitions and deterministic replay. A successful decode is not behavioral equivalence or proof of reachable source statements.
- In BASIC-like lifting, distinguish embedded BASIC from inferred statements, capture effects once, invalidate facts at joins/calls and preserve compiler evaluation order. Never replace zero-test semantics with bitwise BASIC `NOT`.
- **Prefer idiomatic BASIC operand presentation where safe:** base address before literal offset (`POKE BASE + 1, VALUE`), and assigned variable first in a simple self-update (`COUNT = COUNT + 1`).  Preserve target numeric/error behavior and effects; retain exact VM order in evidence, and do not swap effectful reads or calls merely for style.  See the [reading-quality gate](references/basic-reading-quality.md#idiomatic-operand-presentation).
- **Omit redundant default `STEP 1` in reader-facing FOR headers.** Retain its exact evidence; never drop an effectful step expression merely because its value is one.  Unknown output-channel state is not evidence of a source `PRINT#`; distinguish primitive output, selected logical file, and device routing using the [reading-quality gate](references/basic-reading-quality.md).
- **Readable BASIC must pass the cross-family [reading-quality gate](references/basic-reading-quality.md).** Keep exact constants and canonical expressions in evidence, not necessarily in the reader-facing spelling.  Use structured precedence, simplify proved comparison false tests, prefer shorter target-round-tripping decimals, and inspect the final listing for binary-decimal tails, redundant wrappers, and internal scaffolding.  A DTL-only implementation boundary is not permission to forget these lessons when revisiting another family; do not borrow its ABI or silently round literals.
- **Synthetic temporaries in BASIC-only listings require a high bar of justification.** Keep lifter bookkeeping internal by default; prefer faithful whole expressions and BASIC constructs. Mere RND/PEEK/TI/FN use, hypothetical interrupts or a failed local substitution are not justification. Any retained temporary needs a concrete, address-backed reason after whole-expression reconstruction is considered; distinguish a tool limitation from an original source assignment. See [BASIC-only temporary policy](references/evidence-and-reconstruction.md#basic-only-temporary-policy).
- Across compiler families, assume a recognized SYS returns to the following BASIC statement when reading and explaining control flow. Require concrete evidence in the BASIC (embedded or reconstructed) before discussing abnormal SYS flow; an uninspected native callee or theoretical machine-code capability is not evidence. Do not require callee disassembly for normal continuation or repeat blanket return warnings. Keep state/effect analysis separate; see the [SYS normal-return reading default](references/evidence-and-reconstruction.md#sys-normal-return-reading-default).
- Runtime traces require declared state/patches, correct pre-increment IP and byte comparison. Do not corrupt live VM zero page. On affected Retro Debugger C64 snapshot APIs, pausing during snapshot capture can deadlock; follow the backend's validated snapshot procedure and preserve trace bytes first.

## Stop and hand off

For new recovery, retain input identities, VM/region map, profile and decoder versions, low-level bytes/instructions, supported/unknown forms, confidence, provenance and the smallest next discriminating question. Use `c64-rom-reference` for exact ROM/banking/workspace dependencies and the disk-preservation skill when protected media gates intake.

For default reconstruction, deliver a qualified reading aid—not executable BASIC, recovered names/line numbers or a claimed original expression tree. A separately requested, independently admitted known-snippet PRG follows the [export contract](references/basic-prg-export.md); it does not promote the whole reading to runnable source or imply a distributed standalone exporter. Do not silently weaken a decoder to make a report look complete. Preserve first refusals; later corrections belong in separately versioned evidence. Independently reserve/freeze a new object before claiming generalization beyond known-corpus tests.
