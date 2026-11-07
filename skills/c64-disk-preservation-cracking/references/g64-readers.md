# Read-only G64 helpers

These helpers recover inspectable evidence without rewriting preservation masters or pretending that custom records are ordinary DOS files.  They use Python 3.10+ and its standard library; commands below are relative to the skill directory.

## Standard GCR and DOS files

```sh
python3 scripts/g64_extract.py capture.g64 --json
python3 scripts/g64_extract.py capture.g64 --extract PROGRAM --output recovered/PROGRAM.prg --json
python3 -B -m unittest discover -s scripts/tests -v
```

The reader checks standard GCR framing and checksums, then follows DOS directory and file chains.  Directory-sector evidence preserves traversal order.  Duplicate-sector diagnostics identify the actual selected physical candidate and distinguish identical from conflicting valid payloads.  Conflicting otherwise-valid duplicates use the documented existing first-valid selection; the diagnostic is not a consensus or strict-conflict refusal.  Missing or corrupt required sectors fail rather than becoming zero-filled payloads.

Track records overlapping the G64 header/offset/speed-table area are rejected.  Extraction refuses stable path, symlink, and hardlink aliases of the input image.  This is not race-proof or atomic output: concurrent filesystem changes remain outside the guarantee, and an unrelated existing output file can still be overwritten.  Always choose a fresh derivative destination.  Preserve original captures and hashes before extraction.

Scope remains standard-sector/DOS interpretation, not every container extension, custom filesystem, physical timing effect, or protection format.  Faster loading alone does not imply a different disk encoding.  A standard-reader failure does not establish that no recoverable custom data exists.

## Narrow RapidLok-like recognition

```sh
python3 scripts/rapidlok/rapidlok_recognize.py raw-track.bin 200 --circular
python3 -B scripts/rapidlok/test_rapidlok_recognize.py
```

The first command takes raw represented track bytes and a known marker bit, **not a G64 container**.  It inspects one fixed-layout candidate, its projected header integrity, and a source-derived diagnostic relation.  It never emits decoded payloads or writes the input.  See [attribution and exact contract](../scripts/rapidlok/ATTRIBUTION.md) before interpreting results.

A recognized shape is not a proved RapidLok revision, payload transform, logical sector mapping, file recovery, or runnable reconstruction.  The observed alphabet cannot admit the source's v2–7 discriminator; only the separate probe reports that hint.  Integrity collisions remain possible.  Unknown transforms must stay unknown, not be guessed until text appears.

## Explicit v1-compatible RapidLok record decoding

```sh
python3 scripts/rapidlok/rapidlok_v1_record.py raw-track.bin 224 --profile remaster-v1-compatible
python3 -B scripts/rapidlok/test_rapidlok_v1_record.py
```

This separate decoder requires known record coordinates and explicit profile selection.  It returns 384 decoded body bytes, two separately retained opaque auxiliary bytes, raw encoded evidence, hashes, and bit ranges.  It enforces exact header association, canonical encoded-bit rules, header XOR, and encoded-record integrity.  Its 24/25-one sync contract reflects independent preserved-record observations; the older recognizer and its rejection tests are unchanged.  See the [full profile, source attribution, hand vectors, and limitations](../scripts/rapidlok/RECORD-PROFILE.md).

Passing proves compatibility with this narrow pinned-source profile, not a historical revision, logical sector mapping, recovered file, or runnable program.  There is no auto-detection, fallback, v2–7 decoder, or universal corruption guarantee.  XOR collisions are explicitly tested as a limitation.  The command takes raw track bytes, not a G64 container; it emits JSON to stdout and never writes its input.

Read/extract-only scope excludes encoders, repair, remastering, and protection-preserving writing.  Public tests are synthetic; commercial captures and recovered material must remain private.

## Explicit later Vorpal record decoding

`scripts/vorpal/vorpal_record.py` exposes `decode_record(track, *, profile, marker_bit, bit_length)` for one caller-located linear record under `vorpal-later-128-xor-7faa-v1`.  It checks the 7F AA detector, legal five-bit symbols, 128-byte payload XOR8, complete bit bounds, and the declared ID range.  It returns raw evidence and payload bytes without file I/O.  Unsupported profiles, incomplete records, illegal symbols, and checksum failures raise `RecordError`; there is no scanning, fallback, repair, or circular wrapping.

See the [API and exact profile](../scripts/vorpal/CONTRACT.md) and [pinned source attribution/licensing caveat](../scripts/vorpal/ATTRIBUTION.md).  From the skill directory, run `python3 -B -m unittest discover -s scripts/vorpal -v` for 24 portable synthetic tests: 13 unchanged record tests and 11 inventory tests.  No private corpus or external package is required.

This is not early differential Vorpal support, logical file mapping, decompression, or boot validation.  XOR8 covers payload only, not ID/filler fields, and is not authentication.  The profile suffix versions the helper contract, not a historical format revision.  Preserve exact coordinates and original captures; a recognized marker alone does not establish applicability.

### Linear Vorpal record inventory

`scripts/vorpal/vorpal_inventory.py` adds `scan_track(track, *, profile, bit_length)` above the unchanged decoder.  It finds every complete marker at every bit phase within the supplied linear extent, retaining overlapping observations, exact refusals, hashes, and repeated/conflicting ID groups.  It never chooses a winner, completes an end-of-track record by wrapping, or infers logical order.

```sh
python3 scripts/vorpal/vorpal_inventory.py raw-track.bin --profile vorpal-later-128-xor-7faa-v1 --bit-length 61536
```

The input is raw track bytes, not a G64 container; callers retain original image hashes and track-data offsets.  JSON goes to stdout, so do not redirect it onto the input.  Accepted observations are not authenticated sectors or recovered files.  See the [inventory contract](../scripts/vorpal/INVENTORY.md) for boundary, hash-padding, and per-track conflict semantics.
