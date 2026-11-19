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

In its BASIC-like listing, an adjacent literal assignment and FOR setup for the
same counter can read `FOR V_4240 = 2 TO 9`, or include an explicit literal
`STEP`.  Floating setup takes the bound from the alternate stack and the explicit
step from FAC; byte and signed-word FAC literals are exactly representable when
packed.  Integer unit-step setup takes the bound from the integer accumulator;
its absolute counter address must match the page-three store, and both literals
must be bytes.  The header keeps the first label and all instruction evidence.
An interior entry, intervening effect, computed operand, or different counter
leaves the statements separate.  This does not pair NEXTs or identify a build's
optimizer or output mode.

The same listing recovers a single scalar `INPUT V_9ABC` or
`INPUT "NUMBER";V_03F0` when a prompt's empty-line branch lands immediately
after the typed field and matching store.  The prompt runs first; an empty
line bypasses the assignment, and numeric parse errors can retry the prompt.
The destination is a generated storage label, not the original name or type
suffix.  The byte/word address is unsigned even for signed integer input.
The raw rows distinguish a FAC store, a page-three integer store, and a
page-three string descriptor store.  No physical input device is inferred.
When that same branch encloses only repeated string field reads (`$80`), each
immediately followed by a page-three descriptor reference store (`$AB`), the
listing shows one ordered list, e.g., `INPUT V_0350, V_0353`.  This uses the
ambient input route, not `INPUT#`; an initially empty line skips the list.
It does not mean all fields are collected before the first destination changes.
Mixed or numeric multi-field INPUT lists, arrays, explicit files, prompts
requiring escapes, and entries into any field or store are not folded by that rule.

A separate indexed case reads, for example, `INPUT AR_B100%(V_0352),
AR_B104$(V_0352)`.  These are generated array names.  An empty-prompt `$7C`
can enclose an integer element followed by a string element.  An empty line
jumps past both.  Otherwise each field loads its own subscript and saves the
word **before parsing that field**.  A packed floating subscript is converted
to a VM integer at that load, not by an inferred BASIC `INT()` call.  After
numeric parsing and integer conversion, the first store checks the saved
index and writes the element; only then does the second subscript load run.
The string store checks its saved index and installs a descriptor, not a copy
of the characters.  A malformed numeric delimiter can return to the prompt;
the notation does not imply transactional stores or restoration of the stacks.

The rule requires separate rank-one array spans disjoint from the index
storage, direct scalar index loads, and no other entry or effect inside the
prompt interval.  It does not identify a physical device, infer a source-line
boundary, or extend to arbitrary indexed INPUT lists.

`READ V_033F` describes **one DATA string field** and its immediate descriptor
reference store (`$80 $AB xx`), not an original READ statement boundary.  The
listing keeps `$7B` (select DATA) separate and cites its address for each
recovered field.  On successful reads, the runtime advances its DATA cursor;
repeated fields need not repeat the selector.  The proof can cross matching
scalar field/store pairs only.  For a preceding five-byte FAC store it requires
the whole destination in header-bounded RAM above the object and below `$A000`,
not a write that might overwrite input state.  New entry into a field or store,
a region change, a gap, or any other intervening instruction ends this proof.
An entry at `$7B` itself is safe.  Neither `$7C` (ambient prompt) nor `$7D`
(explicit file) selects DATA.  Their listings are unchanged; a bare field, GET,
array store, or string-copy store does not establish a scalar DATA destination.
No original name, DATA literal, or source-line grouping is inferred.

For a numeric prefix after `$7B`, `READ V_9240` likewise identifies **one successful field transfer**, not original syntax.  `$7E/$28` parses numeric text into FAC, accepts a comma or end marker, updates the DATA cursor, and packs FAC into five bytes at the unsigned inline address.  `$7F/$A7` uses that same parser and cursor update, then the runtime's signed-word conversion, then stores low and high bytes at the page-three destination.  This is not a BASIC `INT()` expression or proof that a parse error reached the store.  Each heading owns its field and store and cites the selector separately.

The numeric fold requires the full floating destination in the bounded RAM window described above, or both integer bytes within `$033C` through `$03FB`.  Exact repeated destinations remain separate writes.  A partial overlap with an earlier numeric slot, an unsafe store, a descriptor store with indirect heap bookkeeping, or any break in the selector proof ends the numeric prefix.  Another selector can start a new one.  This narrower numeric rule does not certify or regroup later fields.

For an ungrouped field or GET, distinguish an unknown ambient input route from an explicit file selection whose number is unknown.  `$7A` reads through GETIN; that instruction does not select a logical file.  For example, `REM current-channel GET: T_1234$` means there is no proven selector at that site, whereas `GET#<?>, T_1234$` requires a reaching file selection.  Neither heading promises a keyboard read or successful I/O.

Adjacent current-channel output items ending in `PRINT_NEWLINE` can read as
one line, for example `PRINT "SCORE"; TAB(12); V_4240`.  Each item must load
and immediately print its own operand: inline string, page-three string,
absolute float, page-three integer, or byte-literal TAB/SPC.  Reads and output
stay interleaved in byte order.  The newline keeps its own instruction row;
its normal channel-dependent behavior is not replaced with a literal CR byte.
An unknown ambient channel stays qualified as partial, not inferred screen
output.  The semicolons describe consecutive output, not original punctuation
or source statement boundaries.  Never fold across an interior target, comma
zone, selected-file output, other expression, or intervening statement.  Without
a final newline the fragments remain separate.

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
