# Scope, compiler assistance and existing tools

> Read [SKILL.md](../SKILL.md) first. This is the detailed procedure for the routed phase, not an instruction to expand every task. Commands and inline file paths below are relative to the **skill directory**, unless explicitly stated otherwise; Markdown links resolve from this reference.

# BASIC-compiler and 6502-hosted p-code disassembly

Use canonical deterministic decoding with external profiles and thin adapters; reuse established primitives without assuming different VMs share operand grammars or evaluation models. LLM/human reasoning discovers architecture and semantics; the decoder reproduces only explicit profile knowledge and must refuse unsupported lengths.

For authorized compiler-assisted work, **read [Compiler-assisted discovery](../references/compiler-assisted-discovery.md)** before designing probes. It captures reusable cross-compiler lessons: asymmetric tests, non-source evaluation order, handler-entry context, per-form byte order, cursor conventions, opaque source-map tails, non-code regions, and narrowly scoped validation. It also distinguishes broad **preimage coverage** (record compiler acceptance/rejection and emitted bytes; execution often unnecessary) from behavioral conformance testing. It also supplies an efficient omnibus-failure isolation workflow: reuse exact prior deltas, try an evidence-backed subtraction before bisection, preserve structural dependencies, and classify failure phase/signature rather than treating every unsuccessful run alike. Keep compiler-specific addresses, encodings, outputs and chronology in the effort/profile, not that reference.

Bundled tools use Python 3.10+ and the standard library; no particular agent harness or emulator is required for offline decoding.

- **Family identifier and binary-only reconstruction:** [scripts/reconstruct/](../scripts/reconstruct/) recognizes evidenced signatures and emits best-effort BASIC-like statements above p-code for six evidenced families, without source/map inputs. Read the [contract, limitations and CLI guide](../references/reconstruction-tools.md). Known-corpus development checks are not independently blind holdouts. Treat native structural *candidates* separately from exact identifications, and never interpret identification as proof of decoder support or historical producer.
- **Austro-Speed / INPUT64 Speedcompiler:** separate identities and runtime contracts; Austro reuses audited BLITZ grammar, Speedcompiler has a distinct decoder/state adapter. Read the [scope and tools guide](../references/austrospeed-speedcompiler-tools.md), including compiler defects and partial semantics.
- **PETSpeed:** [scripts/petspeed/](../scripts/petspeed/) contains the decoder, runtime profile and synthetic tests. See the [tool guide](../references/petspeed-tools.md).
- **BASIC-64:** [scripts/basic64/](../scripts/basic64/) contains the v1.0.3 decoder, profile and synthetic tests. See the [tool guide](../references/basic64-tools.md) for the tested optimizer-I/II P-code scope.
- **DTL BASIC / Jetpack 64.4:** [scripts/dtl/](../scripts/dtl/) contains a pinned-runtime structural decoder, separate stage-1/omnibus profiles and synthetic tests. See the [tool guide](../references/dtl-tools.md); this core provides structural decode/supplied-source annotation; the separate reconstruction frontend remains explicitly best-effort.
- **BLITZ:** [scripts/blitz/](../scripts/blitz/) contains the profile-driven decoder `blitz_pcode.py`, structural dispatcher finder `discover_dispatch6502.py`, commentary renderer `annotate_listing.py`, BASIC V2 probe builder `build_rounding_microtest.py`, and synthetic tests. Supply an independently evidenced profile for your input; no title-specific profile is bundled.

Compiler/media preparation, native-runtime discovery and capture adapters are separate analysis tasks, not hidden dependencies of these decoders. Keep commercial programs, reconstructed source, whole-image disassemblies, traces and experiment evidence outside the distributable skill.

