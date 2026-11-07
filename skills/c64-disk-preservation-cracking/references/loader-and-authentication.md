# Loader, uploaded code, disk behavior and decision path

> Read [SKILL.md](../SKILL.md) first. This is the detailed procedure for the routed phase, not an instruction to expand every task. Commands and inline file paths below are relative to the **skill directory**, unless explicitly stated otherwise; Markdown links resolve from this reference.

## Phase 3 — Identify the loader architecture

Determine whether loading uses:

- normal KERNAL LOAD,
- normal IEC calls with custom protocol layered above them,
- a fastloader,
- custom C64-side bit banging,
- code uploaded into the 1541,
- a combined fastloader/protection system.

For tokenized BASIC/machine-language hybrids, distinguish the linked BASIC chain from physically present trailing records and native data. Do not assume a filename visible in a static listing is the filename used at execution: native setup may rewrite tokenized line bodies immediately before LOAD. Watch for deliberately zeroed line links, copied survival stubs placed outside the next load range, and self-patched operands that make pre-patch disassembly look like calls into data.

Useful C64-side indicators include calls or accesses involving:

- KERNAL LOAD and IEC routines,
- `$DD00` CIA2 IEC lines,
- custom IRQ/NMI timing,
- code copied into unusual RAM before disk activity.

Useful drive-side indicators include:

- RAM writes through DOS memory commands,
- execution of code from drive RAM,
- code appearing in `$0300-$07FF`,
- direct VIA #2 access around `$1C00-$1C0F`,
- direct VIA #1 access around `$1800-$180F`,
- custom GCR decode loops,
- custom head stepping,
- non-ROM disk-read code.

Use the `1541-symbols.md` reference rather than treating drive RAM addresses as C64 addresses.

## Phase 4 — Detect uploaded drive code

One of the highest-value tasks is determining whether the C64 uploads machine code to the 1541.

Look for:

- memory-write commands to the drive,
- repeated transfers of binary blocks,
- DOS commands that execute code in drive RAM,
- sudden execution from `$0300-$07FF`,
- changes to normal job/buffer usage,
- drive code that replaces DOS communication routines.

When drive RAM code is discovered:

1. capture the bytes,
2. record the load address,
3. save a binary copy for analysis,
4. disassemble it as 1541 6502 code,
5. identify entry points,
6. build cross-references,
7. label VIA and DOS workspace accesses,
8. trace communication with the C64.

Do not assume the uploaded code is solely a fastloader. It may also:

- validate protection,
- decode custom GCR,
- read signature tracks,
- generate decryption keys,
- return pass/fail state,
- decrypt another drive routine,
- communicate data needed to decrypt C64 code.

## Phase 5 — Classify disk behavior

Use observed behavior rather than guessing from title/publisher.

Common protection categories include:

### Intentional disk errors

Indicators:

- reads of specific sectors expected to fail,
- DOS status explicitly checked,
- missing data/header blocks,
- checksum errors,
- ID mismatches,
- protection succeeds because a read fails in a particular way.

Ask:

- What track/sector is tested?
- What exact status is expected?
- Is the sector's data relevant, or only the error result?

### Extra tracks

Indicators:

- head movement beyond standard track 35,
- accesses to tracks 36-40,
- custom drive routines bypassing normal DOS limits.

### Half tracks

Indicators:

- individual stepper phases rather than normal full-track movement,
- protection reads between normal track centers,
- signature readable only at an N.5 position.

### Non-standard density / bit rate

Indicators:

- direct changes to drive density/speed-control bits,
- track read succeeds only under unexpected zone configuration,
- density changes during custom read code.

#### Recover the raw-reader assembly contract

Density labels and nominal section lengths are not a complete decoder-input specification.  For a selected raw reader:

1. Pin the code stage, relocation, and entry conditions.  An inferred decoding seed or coherent stage map remains conditional until its producer is established.
2. Record the actual port operations, arithmetic mode, data-direction/input configuration, and byte-ready source.  Distinguish density changes from head-phase updates and a sync level from a sync edge or end.
3. Count every stored and discarded read in execution order, including helper reads and the first store after an index wrap.  Map the complete destination layout, retry behavior, and split buffers.  Check both directions of stack interference: scratch writes can destroy live return addresses, while later calls or interrupts can overwrite unread scratch.
4. Follow that assembled buffer into the actual decoder entry and caller.  Inspect conversion-table behavior, marker/checksum handling, and any rejection branches rather than borrowing an offline extractor's acceptance rules.
5. Follow the resulting bytes or status to their consumer and bound that span.  An outgoing page does not establish an untraced receiver's acceptance, installation, or execution.

Keep a strict offline decoder strict.  Its refusal at specified representation coordinates does not prove that a controller presents the same octets, that a ROM conversion routine rejects them, or that acquisition failed.  A direct caller may use a permissive converter without the surrounding normal validation path.  Conversely, permissive conversion and plausible prefixes do not establish a complete recovered payload.  Stored speed metadata and cross-format bit agreement do not supply missing timing observations or additional density-specific acquisitions.

### Sync manipulation

Indicators:

- custom sync-search loops,
- unusual counts or timing of sync regions,
- tracks with no conventional sync,
- code deliberately measuring or counting sync.

### Duplicate sector IDs

Indicators:

- code deliberately ignores the first matching header,
- searches for a second occurrence of the same track/sector identity,
- raw-track analysis reveals repeated sector IDs.

### Gap or hidden raw-track data

Indicators:

- custom reader consumes bytes outside standard sector payloads,
- key material appears between standard data blocks,
- sector-level image lacks bytes required by loader.

### Long tracks

Indicators:

- custom streaming decoder,
- track data exceeding normal revolution/track assumptions,
- decoder operates byte-by-byte without storing the complete track,
- raw image contains unusually long track data.

### Weak / unstable regions

Indicators:

- same physical location intentionally read multiple times,
- protection expects different results,
- repeated reads vary on original hardware,
- fixed/emulated data causes failure.

Be careful: hardware model can affect unstable-read behavior.

### Custom GCR / custom format

Indicators:

- raw bytes are interpreted by private decode tables,
- standard DOS sector routines are bypassed,
- most tracks are unreadable to CBM DOS but readable by uploaded drive code.

### Angular / timing relationships

Indicators:

- protection depends on rotational timing between track accesses,
- code measures time between signatures,
- data content is correct yet copies fail because physical positioning differs.

#### Validate joint access relationships, not only individual tracks

For an access that uses one track as an anchor before observing another, record an edge-labelled schedule: the verified source event, head movement and service state, destination observation, retry behavior, and the result positions actually consumed.  Pin the relevant drive-code and ROM semantics.  A requested-sector read and the first checksum-valid header encountered after a step are different observations; automatic seek correction, remembered track or disk ID, and interrupt or timer state can affect the relationship.

Test preservation of that joint schedule as well as per-track sector identities, payloads, disk IDs, checksums, and cyclic order.  A bounded representation control can compare a common rotation of the connected tracks with an independent rotation of one track: the latter can preserve each track's decoded contents while changing its incident cross-track relationships.  Express shifts in a consistent coordinate system.  Equal byte shifts imply equal represented phase shifts only under an established length and mapping relationship; unequal track lengths or speeds need separate treatment.  Invariance of selected edges is not proof that every dependency is preserved.

Keep collection separate from consumption.  Establish the predicate's actual index coverage, and use instruction-supported controls to test changed consumed positions and ignored positions.  Comparing an expected vector with a deliberately changed copy is not, by itself, an independent reconstruction of the predicate.  Likewise, validate source coordinates against original encoded data; an expected-byte inequality does not establish the mapping.

These controls establish relationships in the represented data under stated assumptions.  They do not establish original angular registration, mechanical timing, a naturally observed response vector, or a runtime rejection caused by a chosen rotation.  Those stronger claims need appropriate acquisition or execution evidence; aligned stored origins and valid sectors alone do not supply it.

### Runtime code decryption connected to loading

Indicators:

- loaded C64 code initially disassembles as nonsense,
- IRQ/timer routines progressively transform memory,
- loader or drive supplies key material,
- EOR/ADC/SBC/rotate loops modify code before execution.

Use the `6502-disassembly` skill for the actual code/data classification and decryption analysis.

## Phase 6 — Locate the authentication decision

The goal is not merely to understand the disk format.

Determine how the software converts disk behavior into a decision.

Trace from disk-read result toward:

- carry/zero/negative status,
- returned byte,
- checksum,
- key material,
- memory flag,
- branch,
- jump target,
- decryption key,
- watchdog/check routine.

For each candidate protection check, answer:

1. What is measured?
2. Where is it measured?
3. What constitutes success?
4. How precise is the predicate: exact status/value, one decimal digit, masked bits, carry, or merely zero/nonzero?
5. Where is the result stored?
6. How does the C64 learn the result?
7. What happens on failure?
8. What success-only side effects occur before normal execution—link repair, copied code, decryption, vector installation, initialization, or required register state?
9. Is this check performed again later?

Do not replace an authentication branch until the success-only side effects have been inventoried. Forcing “pass” while skipping a required repair/decode stub can produce a broken crack whose failure appears unrelated.

Create meaningful labels such as:

```text
protection_track_read
validate_disk_signature
protection_ok
protection_failed
disk_key
drive_auth_result
```

only when evidence supports them.

