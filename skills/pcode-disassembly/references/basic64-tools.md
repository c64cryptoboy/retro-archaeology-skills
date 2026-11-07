# BASIC-64 tools (Abacus / Data Becker)

From the skill directory:

```sh
python3 -X utf8 scripts/basic64/basic64.py P-PROGRAM \
  --map Z-PROGRAM --source PROGRAM.bas \
  --json-output NEW-report.json --text-output NEW-listing.txt
python3 -X utf8 -m unittest discover -s scripts/basic64 -q
```

Only the decoder and adjacent `basic64_profile.json` are needed. The tests use synthetic bytes. No compiler, runtime, disk image, emulator or network access is needed for the test suite; decoding real software requires your own input.

Use `-X utf8`, especially on Windows: supplied BASIC annotations can contain π. Compare parsed JSON across hosts rather than assuming identical newline conventions.

## Scope

The evidenced configuration is v1.0.3, optimizers I/II, **P-code**, attached runtime, default code-start 7577. The exact on-disk runtime fingerprint is required. Self-modified live RAM is not interchangeable. Native/mixed/overlay/runtime-less/relocated builds are separate scope.

Regions distinguish runtime/stub/tables, native bootstrap, configuration, array descriptors, DATA, native p-code bridge, main code and the compiler's two-byte non-code trailer. Z maps retain dummy links, duplicates and opaque footer bytes. Array type/stride comes from the consuming opcode, not an invented descriptor type field.

The decoder validates encoded control targets and source anchors. Unknown/truncated encodings, invalid boundaries and unsupported ON-count wrap refuse; it never guesses a resynchronization point. Full main-code decoding is not full DATA reconstruction, reachability proof or semantic equivalence.

Map/source arguments are optional; source requires a map. Supplied source is annotation, not reconstructed or authenticated BASIC. Output paths must be fresh. Exit 0 means complete declared-main-code decoding; exit 2 means refusal, with partial evidence retained.

`profileSha256` hashes canonical JSON, whereas a file checksum hashes exact profile bytes. These are different representations, not contradictory identities.

## Source names and optional symbol files

Address-based `V_`/`AR_` labels are generated names, not evidence that original names were searched for and lost.  Distinguish the compiled object from the compiler's optional, separate `S-` symbol file.  The distribution's `SYMBOL` utility reads that file as numeric name/address records, including scalar, array, and function names.  A `Z-` line-address map is a different file and is not a source-name table.

For V1.03, Optimizer I, attached P-code, a compile-only alpha-renaming pair and a symbol-save control established byte-identical complete objects despite different significant source names, while the separate symbol file retained names and addresses.  Those original names cannot be recovered uniquely from the object alone in that configuration.  Do not generalize the active result to another version, generator, or option set without evidence, or substitute failed ASCII searches for the paired test.  An optional symbol file is not complete source recovery; formal-parameter spellings need not have separate saved records.

The current decoder does not import `S-` symbol files.  Check for a compatible companion before allocating replacement names, preserve it as independent evidence, and validate its schema and address mapping before using it.  Do not pass it as `--map`, which expects the separate line-address format.

## Optional native-expanded profile

`basic64_profile-extended.json` preserves all 156 original contracts and adds
12 native-CFG-evidenced forms (168/172 primary slots modeled): absolute integer
and string load/store forms, alternate integer pop, fixed interpreter-result
loads, string argument marshalling and integer doubling. The remaining slots
are the null entry and three bootstrap/native transition entries; no native
block lifting is implied.

Select it with `--profile scripts/basic64/basic64_profile-extended.json`.
The default profile and historical freezes are unchanged. Six additive synthetic
tests check exact widths, truncation, fixed-versus-inline addresses and continued
refusal of excluded transitions. These additions are **native structural
research**, not a claim of fresh compiler emission or new execution validation.

The shared [binary-only reconstruction frontend](reconstruction-tools.md) selects
this expanded profile and renders BASIC-like inferences without supplied source.
It remains distinct from this decoder's optional map/source annotation mode.

## Optional native-runtime inspector

For an already identified compatible BASIC-64 runtime PRG:

```sh
python3 scripts/basic64/inspect_runtime.py RUNTIME.prg \
  --op 37 --span 70 --output NEW-native-cfg.json
```

This optional helper uses the repository's `shared/6502/` CFG tools; it has no
workspace/private imports. It is not a runtime-family identifier. It adds the
profile's known handler roots, refuses conflicting instruction boundaries except
explicitly approved overlaps, and distinguishes `--view` display windows from
new `--entry` roots. Opcode/entry/view arguments are hexadecimal; span is decimal.
Native CFG coverage does not establish full p-code semantics. Output must be new.

## Safe compiler-assisted analysis

Compilation, decoding and execution are separate gates. Never execute broad preimage/omnibus programs containing media, hardware, blocking input or native-call forms. Use independently scoped harmless execution probes.

The compiler's READY acknowledgment is not BASIC direct mode. Verify closed output files rather than relying on completion banners. Audit and preserve protected disk sectors/error metadata before staging probes; do not format, normalize or DOS-validate away protection. The optional native inspector is separate from decoding; workspace media preparation and specimen-specific capture/discovery remain outside this portable skill.
