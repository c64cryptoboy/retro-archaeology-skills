# Later Vorpal record helper

This deterministic helper recovers one explicitly located protected record without treating a checksum failure, guessed format, or incomplete input as data.  Python 3.10+ and its standard library suffice.

## One explicit profile

`vorpal-later-128-xor-7faa-v1` means only the later Vorpal 128-byte record representation described by the pinned ReMaster source.  The suffix is this helper's contract version, not a historical Vorpal revision number.  It is not the early differential 8-to-6-bit format, a family detector, a loader decoder, or a G64 parser.

Input is immutable raw track bytes, the exact `7F AA` marker bit coordinate, the meaningful track bit length, and the explicit profile string.  Bits are zero-based, MSB-first, and intervals are half-open.  The caller must establish applicability; finding the marker alone is not identification.

| Field | Bits relative to marker | Meaning |
|---|---:|---|
| Detector window | `[0, 16)` | `7F AA` |
| Encoded payload | `[16, 1296)` | 256 five-bit symbols -> 128 bytes |
| Encoded XOR8 | `[1296, 1306)` | Two five-bit symbols -> one check byte |
| Encoded sector ID | `[1306, 1315)` | Six selected bits in nine bits |

The profile deliberately begins at ReMaster's 16-bit detector window, not the preceding additional bit used by its 17-bit header writer.  It claims neither complete header semantics nor a constant record-to-record stride.  Adjacent detector windows can share a bit with a preceding ID field.  No scan or stride inference occurs in the helper.

The table admits exactly 20 five-bit symbols.  Four aliases (`05/1D`, `06/1E`, `0C/0F`, and `14/17`) map to nibbles `E`, `F`, `5`, and `A`, respectively.  The other symbols and high/low nibble order follow the pinned source.  All 12 illegal symbols are refused in either payload or checksum, rather than substituted with zero or `FF`.

The ID uses positions `0, 2, 3, 5, 6, 8` of its nine-bit field, in that order from most to least significant.  The source decoder ignores the three intervening filler bits; this helper also preserves them without claiming to validate them.  IDs outside the source's stated `0..46` range are refused.  There is no claim that an ID belongs to a particular track, file, or logical transfer.

## Integrity and refusal

A successful result requires XOR of all 128 decoded payload bytes to equal the decoded check byte.  Mismatch always raises `RecordError`; no partial payload, repair, catch recovery, fallback profile, or permissive substitution is returned.  Invalid input, wrong marker, illegal symbols, incomplete ID, unsupported profile, and unsupported ID are also explicit refusals.

This is **payload-only XOR8**, not authentication.  It does not cover the marker, ID, or ignored filler bits.  Compensating changes can preserve XOR.  SHA-256 in a caller's evidence manifest pins observed input/output identity; it does not strengthen the disk format's check or authenticate an original disk.  Tests explicitly demonstrate these limitations instead of inventing stronger integrity.

Only complete linear records are supported.  No circular wrapping, half-track substitution, weak-bit resolution, repairs, duplicate selection, whole-track recovery, filesystem reconstruction, decompression, boot validation, or target execution is provided.

## Python API

Use the function from a caller that already has a raw track and independently established marker coordinate.  No external binary, private fixture, or third-party Python package is required.

```python
from vorpal_record import PROFILE, RecordError, decode_record

try:
    record = decode_record(
        raw_track,
        profile=PROFILE,
        marker_bit=known_marker_bit,
        bit_length=len(raw_track) * 8,
    )
except RecordError as refusal:
    # Report refusal.code; do not promote this record to recovered payload.
    raise
else:
    # Preserve record.raw_packed, record.payload, and their bit coordinates.
    # A result verifies only the declared symbol and payload-XOR contract.
    payload = record.payload
```

`DecodedRecord.raw_packed` contains exactly 1,315 meaningful record bits in 165 bytes, with five zero transport-padding bits.  `bit_length` excludes caller transport padding.  Raw bits before and after the selected record are not returned; preserve the original track separately for contextual evidence.  The helper performs no file I/O and returns immutable payload/raw bytes.

## Independent synthetic checks

From this helper directory, run `PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest -v test_vorpal_record.py`.

The tests contain only hand-transcribed synthetic symbol vectors, never recovered commercial bytes, and do not import an encoder.  The zero byte is literal `01001 01001`; 129 repetitions provide 128 zero data bytes and check value zero.  The mixed vector begins `01 23 45 67 89 AB CD EF 5A`, followed by 119 zero bytes.  The first eight bytes XOR to zero, so its check value is `5A`.  Both nibble positions for all 20 legal symbols, all eight byte phases, every possible bit truncation of a 1,315-bit record, all illegal symbols in both payload/checksum halves, legal-symbol corruption, wrong marker/alignment, unsupported inputs/IDs/profiles, and explicit nonwrapping are covered.  ID/filler and compensated-XOR cases document the actual integrity boundary.

Synthetic acceptance is a codec/contract test, not proof that a synthetic record would load on original hardware.  See `ATTRIBUTION.md` for immutable source links, hashes, and licensing uncertainty.
