# Explicit v1-compatible record decoding

This decoder exposes inspectable record bytes without pretending that a source-code fallback identifies a historical disk revision or recovers a file.  It is a separate capability from the unchanged recognition-only helper.

## Usage and scope

```sh
python3 rapidlok_v1_record.py raw-track.bin 224 --profile remaster-v1-compatible
python3 rapidlok_v1_record.py raw-track.bin 224 --profile remaster-v1-compatible --circular
python3 rapidlok_v1_record.py raw-track.bin 232 --profile remaster-v1-compatible-168
python3 -B test_rapidlok_v1_record.py
python3 -B test_rapidlok_v1_record_168.py
```

Input is a represented raw track and a **known** marker position, not a G64 container.  The explicit profile is required; there is no automatic detection or fallback.  JSON goes to stdout.  Rejection exits 2.  The program does not write files, execute payloads, repair bytes, normalize tracks, or encode media.  Python 3.10+ and the adjacent `rapidlok_recognize.py` suffice.

`decode_record(track: bytes, marker_bit: int, *, profile: str, circular: bool = False) -> dict` returns the 583 encoded bytes, projected header bytes, a 384-byte decoded body, two separately retained opaque auxiliary bytes, encoded integrity, hashes, and bit intervals.  All coordinates are MSB-first, relative to track byte zero, and exclusive at the end.  Circular coordinates are unwrapped.  The header-through-record span must fit within one represented revolution.

The claim is **decoded under the pinned v1-compatible profile**.  Historical revision, logical sector numbering/ordering, files, load addresses, and executable reconstruction remain unestablished.  No loader-runtime comparison has been performed.  The two auxiliary bytes have unknown meaning and are not silently dropped.

## Admission contract

- `6B` at the supplied marker; exactly 583 bytes in its candidate window.
- A seven-byte `75` header exactly 160 bits earlier for `remaster-v1-compatible`, or exactly 168 bits earlier for `remaster-v1-compatible-168`, with at least 10 preceding sync ones.
- At least 24 immediately preceding data-sync ones.  Independent preserved-record observations found both 24 and 25.  The reference application's `>24` search skips 24-one records and can associate a header with later data; this decoder never performs that search.  The older recognition-only helper still requires 25 and retains all its original rejection tests.
- Strong header fingerprint: `(H[1] & 90) == 90`, `(H[2] & 09) == 09`, `H[4] == D6`, and `H[5] == ED`.  Byte values and bit masks are hexadecimal; lengths, offsets, array indices, shift counts, and bit numbers are decimal.
- Canonical encoding rules below for both header triples and all body triples.  Four projected header bytes must XOR to zero.
- Byte 196 must not equal `A4`; that source discriminator belongs to the unsupported v2–7 branch.  The opposite result is not proof of v1.
- Canonical tail encoding and the encoded-byte integrity relation must both pass.  Invalid inputs are refused, not salvaged.

This is deliberately a **narrow source-compatible encoding profile**, not a complete historical format specification.  A different fingerprint, spacing, or encoding can be unsupported without being damaged.  The previous 772-symbol recognition alphabet is neither used nor generalized here.

## Separate fixed 168-bit framing

Select `remaster-v1-compatible-168` explicitly to admit this other spacing without relaxing the existing 160-bit profile.  `PROFILE`, `HEADER_DISTANCE = 160`, the required `profile` argument, all codec and integrity gates, and the recognition-only helper remain unchanged.  There is no distance search or cross-profile fallback.  The profile name describes compatible encoding and framing, not a historical revision.

For a supplied marker bit `m`, the new profile requires the header at `[m−168, m−112)` and its 112-bit following gap at `[m−112, m)`.  The complete header-through-record span is 4,832 bits (604 bytes), which must fit within one represented revolution; the old profile retains its 4,824-bit (603-byte) bound.  Body, auxiliary, and integrity offsets within the 583-byte record are identical in both profiles.

Only the new profile also requires the terminal data sync to be the first sync encountered after the header: refuse a run of at least ten ones within the gap before that terminal run, or a terminal run longer than the 112-bit gap.  This bounded barrier check does not search for another header or data marker.  Nine intervening ones are below its threshold.  The terminal run still requires at least 24 ones.  Circular reading applies the same check across track byte zero.

The separate synthetic tests reuse the unchanged hand vectors and retain the 39 diagnostic controls for this spacing, with additional boundary, CLI, encoding, and legacy-behavior checks.  They require no private image, resident artifact, source checkout, or installed package.  Static consumer compatibility does not prove successful loading, startup state, or authentication.  No half-track substitution, mapping inference, file extraction, or payload repair is performed.

## Audited transform

Source: DarylKrans/ReMaster-Utility, commit `f30688de7fede5cef20c0a0d163ec13ec6ef7513`, [GCR.cs lines 459–585](https://github.com/DarylKrans/ReMaster-Utility/blob/f30688de7fede5cef20c0a0d163ec13ec6ef7513/V-Max%20Tool/GCR.cs#L459-L585), [adjustments at lines 618–625](https://github.com/DarylKrans/ReMaster-Utility/blob/f30688de7fede5cef20c0a0d163ec13ec6ef7513/V-Max%20Tool/GCR.cs#L618-L625), and [RapidLok.cs lines 491–523](https://github.com/DarylKrans/ReMaster-Utility/blob/f30688de7fede5cef20c0a0d163ec13ec6ef7513/V-Max%20Tool/RapidLok.cs#L491-L523).  See [source attribution and licensing uncertainty](ATTRIBUTION.md).

For three encoded bytes `a,b,c`:

```text
P0(a,b) = ((a & 60) << 1) | ((a & 0C) << 2) | ((a & 01) << 3)
        | ((b & 80) >> 5) | ((b & 30) >> 4)
P1(b,c) = ((b & 06) << 5) | ((c & C0) >> 2) | ((c & 18) >> 1) | (c & 03)
T(b,a)  = ((b & 18) << 3) | ((b & 03) << 4) | ((a & 18) >> 1) | (a & 03)
```

For marker-inclusive record `R`:

| Encoded interval | Interpretation |
|---|---|
| `R[0:1]` | `6B` marker |
| `R[1:577]` | 192 triples; each yields `P0 XOR FF`, then `P1 XOR FF` |
| `R[577:581]` | Two opaque bytes `T(R[577],R[578])`, `T(R[579],R[580])`, without complement |
| `R[581:583]` | Stored integrity `T(R[581],R[582])` |

Require `XOR(R[1:581]) == T(R[581],R[582])`.  Integrity includes the original encoding bits and auxiliary encoding, not decoded bytes.  Follow the executable expression rather than the source's inconsistent parity-bit-order comment.  Header projection uses `P0,P1` without complement.

Canonical triple rules, derived from the reference encoder and its adjustments without implementing an encoder:

| Field | Rule |
|---|---|
| `a` bits 7 and 1 | Set |
| `a` bit 4 | Clear exactly when `(a & 68) == 68` |
| `b` bit 3 | Set |
| `b` bit 6 | Clear exactly when `a` bit 0 is set and `(b & A0) == A0` |
| `b` bit 0 | Clear exactly when `c` bit 7 is set and `(b & 06) == 06` |
| `c` bit 5 | Set |
| `c` bit 2 | Clear exactly when `(c & 1A) == 1A` |

Each of the six tail bytes `t` requires `(t & E0) == A0`; bit 2 is clear exactly when `(t & 1A) == 1A`.

## Independent hand vectors and limits

Literal header `75 92 59 24 D6 ED 6F` projects to `01 00 96 97`, XOR zero.

```text
6B || 96 69 EC || (92 49 24) repeated 191 times || A5 AC A4 A5 BA AC
```

This 583-byte vector gives body `ED CB` followed by 382 `FF` bytes, auxiliary `14 01`, and encoded/stored integrity `E4`.  A second literal vector, `6B || (EF BE FB) repeated 192 times || A4 A4 A4 A4 A4 A4`, gives a zero-filled 384-byte body, zero auxiliary bytes, and zero integrity.  Fixtures are hand-derived, not generated by a matching encoder.

Tests preserve the old recognizer's 24-one refusal and cover the new profile's framing, fixed and adjusted encoding bits, checksum corruption, a checksum-compensated illegal encoding, header corruption, wrong profile/marker/orientation, truncation, all eight bit phases, bounded circular reading, CLI refusal, and unchanged input bytes.

XOR is collision-prone.  Changing vector bytes 1 and 4 by `XOR 04` preserves canonical encoding and integrity while changing the decoded body.  A limitation test explicitly preserves that fact; no claim is made that every corruption is detectable.  Commercial records and case-specific validation remain private and are not dependencies of this package.
