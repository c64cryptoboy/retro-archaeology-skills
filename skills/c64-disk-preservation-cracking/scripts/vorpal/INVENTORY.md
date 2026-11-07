# Fixed-profile raw-track inventory

Retaining every original marker coordinate lets a caller inspect strict records, refusals, and repeated-ID evidence without silently selecting a winner or inventing a logical order.

This standard-library-only Python 3 helper wraps `vorpal_record.py`.  It requires the explicit profile `vorpal-later-128-xor-7faa-v1`.  The decoder's [CONTRACT.md](CONTRACT.md) and [ATTRIBUTION.md](ATTRIBUTION.md) still govern record interpretation and source limitations.  ReMaster is a provenance lead, not an independent oracle.  The inventory is not a detector of all Vorpal formats.

## API and CLI

```python
from vorpal_inventory import scan_track

result = scan_track(raw_track_bytes,
                    profile="vorpal-later-128-xor-7faa-v1",
                    bit_length=meaningful_linear_bits)
```

```sh
python3 vorpal_inventory.py track.bin --profile vorpal-later-128-xor-7faa-v1 --bit-length 61536 > inventory.json
```

The input is one raw track, **not a G64 container**.  The caller supplies its exact meaningful linear bit extent.  It must also retain the source image identity and original track-data offset when it extracts a track from a container.  Do not redirect output onto the input file.  The CLI itself reads only and writes JSON to stdout.

Run the 13-test record suite and the synthetic inventory tests from this script directory:

```sh
python3 -B -m unittest discover -s . -p 'test_vorpal*.py' -v
```

## Search, coordinates, and boundaries

- Search every bit phase for each complete 16-bit `7FAA` marker within the supplied linear extent.  Advance one bit after a match, not 1315 bits: record observations may overlap, including a shared terminal/initial bit.
- Coordinates are zero-based, MSB-first track bits, with half-open intervals.  Candidate output is in ascending source-coordinate order only, not logical sector or file order.
- Every marker invokes the existing strict decoder with the original bytes and unchanged extent.  A full marker too near the end remains a `truncated` refusal.  A marker split across the end/start boundary is not in linear search coverage.  No circular completion, rotation, bit insertion, symbol replacement, or repeated-ID winner selection is performed.
- `requested_end_bit_exclusive` describes the fixed-profile window, including when it extends beyond the supplied extent.  `observed_end_bit_exclusive` and `raw_bit_length` describe only bits actually present.  This distinction is not repair.
- Container-absolute marker bit = `track_data_byte_offset * 8 + marker_bit`.  This calculation does not identify a physical/angular reference on the original disk.

## Evidence retained

`source.sha256` hashes all input transport bytes, including any unused tail or bytes beyond `bit_length`.  Each candidate's `raw_packed_sha256` hashes its available window repacked MSB-first with zero tail padding.  The meaningful bit length and padding count accompany that hash; a truncated window's hash is not a complete-record hash.

Accepted candidates retain payload SHA-256, payload size, raw ID, decoded ID, checksum values, integrity declaration, and field coordinates.  Refused candidates retain the exact `RecordError.code` and `str(error)` without returning a decoded payload or ID.  A bad-marker location cannot enter the scanner's candidate set; direct decoder bad-marker tests remain important and unchanged.

Repeated-ID groups retain all accepted coordinates, raw-hash groups, and payload-hash groups.  Different accepted payload hashes under the same ID are reported as conflicts; they are not resolved.  Grouping is confined to one caller-supplied track.  Identical IDs or hashes on separate tracks or images are not automatically duplicate logical sectors.  Equality groups are SHA-256 identities, not physical-copy proofs.

`observed_accepted_ids` is an observation set, not a required-coverage bitmap.  The helper does not claim that every track should have all IDs 0..46.  Refusal codes and acceptances describe only this fixed profile, not whether a capture is faithful or corrupted.

## Limits

- XOR8 covers only the 128-byte payload, not the ID or filler.  Legal-symbol/XOR acceptance is not authentication; paired changes can cancel, and source/capture defects can survive.
- Marker hits can be accidental.  The scanner retains overlapping and refused candidates rather than hiding them.
- No raw/payload byte dump, filename, reconstructed file, native destination, sector order, speed-map interpretation, early-Vorpal profile, or mastering/boot proof is provided.
- Memory is linear in input bits and candidate metadata.  This is a raw-track helper, not a streaming whole-image processor.  Callers bound their own input scope and retain source identities.
- All included tests are synthetic.  Original-media replay is separate and is not a dependency of this helper.
