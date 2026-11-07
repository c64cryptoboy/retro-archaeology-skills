# Austro-Speed and INPUT64 Speedcompiler support

These are separately identified attached-runtime variants, not a claim to support
all historical releases or configurations. Commercial media, source fixtures,
whole-image reports and runtime bytes are not bundled.

## Binary-only entry points

From this skill directory:

```sh
python3 scripts/reconstruct/identify.py /path/object.prg
python3 scripts/reconstruct/reconstruct.py /path/object.prg \
  --json-output /new/report.json --text-output /new/listing.txt
```

The frontend accepts no source/map/annotation input and refuses overwriting output.
Identification, layout validity, instruction grammar and semantic reconstruction
are separate gates. Unknown signatures are not proof of uncompiled input.

## Austro-Speed

- Separate family `austrospeed` with explicit runtime fingerprints. The supplied
  AustroSpeed88-style runtime uses `scripts/austrospeed/austrospeed_profile.json`
  and startup table `$1F79`. A separately evidenced older attached runtime retains
  the Austro-Speed identity but selects the byte-compatible BLITZ decoder contract
  and startup table `$1F93`; identity and decoder contract are reported separately.
- Reuses the deterministic BLITZ decoder only after native handler/cursor audit;
  no general claim is made that every Austro-Speed revision is BLITZ-identical.
- Covers init/main p-code, bounded DATA, variables, targets and loaded regions.
- Runtime differences include multiplication, CLR ordering, input and file-I/O
  error handling. This is not an identical-BLITZ-semantics assertion.
- Multiplication lifts as `VM_AUSTRO_MULTIPLY`, not silently as BASIC `*`, because
  the evidenced runtime has an integer-negation defect. A missing array index
  stays `<?>`; reconstruction does not invent the compiler's apparent intent.
- Direct opcode `$58` is operand-free `RETURN_IF_TRUE`; native stack-unwind
  behavior and a post-freeze source reveal independently validate its rendering
  as `IF condition THEN RETURN` for the older runtime. Existing BLITZ limits on
  FN bodies, multidimensional source indices and broader runtime behavior still
  apply. One external source-withheld older-runtime holdout has passed; it does
  not establish support for all Austro-Speed releases.

## INPUT64 Speedcompiler

- Separate family `speedcompiler`, core/profile/tests under
  `scripts/speedcompiler/`.
- Native fetch modifies the low byte of an indirect-JMP operand, selecting an
  interleaved pointer table. This is not the BLITZ split-table VM.
- Decoder models 127 even-byte dispatch entries; odd bytes and the unmodeled
  extension selector `$FE` refuse. Counted/NUL strings, packed floats, targets,
  biased ON counts, initialization, descriptor slots and typed DATA are bounded.
  Static grammar support is not 127 independently executed language features.
- Initial support requires the evidenced attached runtime, default code start,
  ordinary initialization/storage envelope and no external-extension mode.
  Relocated/runtime-less objects and broader revisions are not guessed.
- Whole loaded bytes are partitioned and hashed. Runtime scratch can retain
  source/compiler residue; it is opaque, not an implicit source-recovery channel.
- `scripts/reconstruct/speedcompiler_lift.py` uses distinct integer-stack, lazy
  floating-stack/FAC and three-string-frame contracts, not a shared postfix VM.
- `VM_*` operations preserve integer width, conversions and other runtime-specific
  behavior. Effectful calls get one-time temporaries; joins/unknown effects lose
  facts. These are explanatory names, not guaranteed legal/runnable BASIC.
- Numeric READ has tag-dependent native depth updates: events are visible, but
  unproved post-state/destination dataflow is dropped. Numeric-looking DATA
  strings keep their encoded string type. Input parsing/retries, file I/O,
  FOR/NEXT and FN reconstruction remain partial or unresolved.

Standalone structural decode:

```sh
python3 scripts/speedcompiler/speedcompiler.py /path/object.prg \
  --json-output /new/decode.json
(cd scripts/speedcompiler && python3 -m unittest -q)
(cd scripts/reconstruct && python3 -m unittest -q)
```

## Evidence boundary

Synthetic parser/state tests need no commercial bytes. Private integration checks
cover successful compilation, exact decoding, target boundaries, binary-only
file-access audits, public-only relocation and separately safe execution. All
omnibus outputs remain compile-only. Instruction coverage is not an accuracy
percentage; known development fixtures cannot be relabeled blind holdouts.
