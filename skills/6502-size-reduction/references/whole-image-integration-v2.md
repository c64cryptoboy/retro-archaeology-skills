# Strict whole-image integration V2

## Claim

V2 integrates one shorter, complete all-code region located anywhere in a
contiguous 16-bit image. Every byte after the region must be partitioned into
hash-guarded shifted ranges classified as `code`, `data`, `mixed`, or `opaque`.
The suffix moves earlier by exactly the compaction delta.

It patches declared references whose source and/or target moves:

- `abs16-le` callers, vectors, and pointers;
- paired `low8`/`high8` split pointers;
- `rel8` displacement bytes using the final source and target;
- direct writers of declared self-modifying operand fields.

It emits relocated entries, reference patches, moved ranges, SMC-field maps,
fixed-anchor checks, change-authorization spans, every changed address, the
unauthorized-change result, reclaimed bytes, and the final hash.

## Mandatory manifest assertions

All must be literal JSON `true` values:

- `assertCompactedRegionAllCode`
- `assertNoRegionCodeAsData`
- `assertShiftedRangesComplete`
- `assertAllReferencesDeclared`
- `assertFixedAnchorsComplete`
- `assertNoUndeclaredSmc`
- `assertWholeImageChangesAuthorized`

These are evidence contracts, not automatic discovery claims. The integrator
verifies their mechanical consequences and refuses malformed, incomplete, or
mismatched declarations.

## Shifted ranges and mixed data

`shiftedRanges` must contiguously cover exactly
`[regionEndExclusive, imageEnd)`, with no gap or overlap. Each range has a
unique name, kind, and SHA-256 over its original bytes. Mixed and opaque ranges
are never decoded or rewritten except at separately declared reference source
bytes; otherwise they move byte-for-byte.

The compacted region itself remains all code. V2 does not compact through
embedded data or weaken the compactor's complete-byte coverage gate.

## References

Each reference declares a unique name, source byte address, original target,
encoding, exact expected source bytes, and kind:

- `caller`
- `vector`
- `pointer`
- `split-pointer`
- `smc-writer`
- `other`

Split pointers require one matching `low8` and `high8` member with the same
group and target. Reference source ranges may not overlap. Sources may be in
the fixed prefix, copied instructions in the compacted region, or shifted
ranges. For a retained compacted-region control operand, the manifest's
expected bytes guard the original image, the compactor repair ledger guards
its intermediate bytes, and V2 then writes the final whole-image target. A
source inside a shortened/replaced transformation without stable byte
provenance refuses.

## Self-modification

SMC is permitted only for declared one- or two-byte operand fields. A field may
be inside the compacted region or wholly inside one hash-guarded shifted range
classified as `code`; prefix, mixed, data, opaque, and cross-boundary fields
refuse. The compactor receives the matching contracts for fields in its own
region plus an assertion that no other regional SMC exists. The whole-image
manifest guards every old field byte and declares every direct writer target.
Writers to any byte within a declared field are accepted; undeclared writer
targets refuse. Both writer operands and fields are patched through final
provenance.

## Fixed anchors

A fixed anchor has a name, absolute address, and exact bytes. It must retain
both address and bytes after all patches. An anchor after a genuinely shortened
non-tail region would move and therefore refuses. V2 does not silently insert
padding, because that would consume the claimed size saving and alter the
layout contract.

## Whole-image authorization audit

Output construction is limited to:

1. copied prefix bytes;
2. guarded compaction output;
3. hash-guarded shifted ranges;
4. declared reference patches;
5. exact tail truncation equal to the compaction saving.

The result records authorization spans and every address whose old/final byte
differs (including truncated addresses). Any changed prefix byte not belonging
to a declared final reference source refuses.

## Hash-chained sequential stages

`integrate_whole_image_sequence` safely composes multiple complete V2 stages in
memory. Every stage carries its own `WholeImageManifest` and
`CompactionConfig`, and its manifest must name the exact size and SHA-256 of the
preceding output. The sequence refuses empty or duplicate stage names, image
base changes, broken size/hash chains, any ordinary V2 refusal, and cumulative
reclaimed-byte ledger mismatches. No intermediate artifact is required.

This is sequential strict integration, not a weakened multi-region manifest.
Addresses, references, SMC fields, shifted ranges, and expected bytes in each
later manifest are expressed in that stage's current layout. Every stage emits
a complete ordinary V2 result; the sequence additionally records input/output
hashes, cumulative changed addresses, total reclaimed bytes, and the final
hash. Opportunity bytes receive combined credit only after appearing in this
single hash chain.

## CLI

```bash
python3 tools/integrate_whole6502.py \
  INPUT.bin OUTPUT.bin \
  --manifest MANIFEST.json --report REPORT.json \
  --timing-policy ordinary --cpu-profile nmos6502 \
  --assert-standard-jsr-rts
```

Output and report paths must be fresh. The CLI performs compaction and
integration in one guarded operation and emits
`6502-whole-image-integration-report-v2`.

## Validation

Focused fixtures cover:

- a non-tail region with shifted code/data/mixed ranges;
- external callers, absolute pointers, split low/high pointers, rel8, and a
  vector;
- fixed prefix anchors and refusal of a suffix anchor that would move;
- declared two-byte SMC fields in both compacted and shifted code, with low-
  and high-byte writer targets;
- exact changed-address authorization and fresh CLI output;
- connected final-address execution of original versus integrated images;
- malformed ranges, hashes, expected bytes, split groups, assertions, unknown
  fields, SMC contracts, and fixed-anchor refusals.

Each V2 stage remains bounded to exactly one complete all-code compacted
region. Multiple regions can be composed only as exact hash-chained stages;
a single relaxed multi-region manifest, padding around fixed suffix anchors,
and compaction of mixed code/data regions remain unsupported.
