# Recognition-only candidate and attribution

This helper keeps unsupported payload recovery from being mistaken for a successful decode.  It reports a narrowly defined raw record shape, a four-byte header projection, and the pinned source's candidate integrity relation; it never emits payload bytes.

## Source and licensing

The header projection and encoded-byte integrity relation are adapted into Python from DarylKrans/ReMaster-Utility, pinned commit `f30688de7fede5cef20c0a0d163ec13ec6ef7513`:

- [V-Max Tool/RapidLok.cs, lines 190 and 438–456](https://github.com/DarylKrans/ReMaster-Utility/blob/f30688de7fede5cef20c0a0d163ec13ec6ef7513/V-Max%20Tool/RapidLok.cs#L438-L456): fixed 583-byte candidate starting at `6B`.
- [V-Max Tool/RapidLok.cs, lines 389–409](https://github.com/DarylKrans/ReMaster-Utility/blob/f30688de7fede5cef20c0a0d163ec13ec6ef7513/V-Max%20Tool/RapidLok.cs#L389-L409): verification search requires more than 24 sync ones.
- [V-Max Tool/Functions.cs, lines 1093–1116](https://github.com/DarylKrans/ReMaster-Utility/blob/f30688de7fede5cef20c0a0d163ec13ec6ef7513/V-Max%20Tool/Functions.cs#L1093-L1116), and lines 1345–1352: MSB-first byte extraction and reversal before C# BitArray storage.
- [V-Max Tool/RapidLok.cs, lines 508–526](https://github.com/DarylKrans/ReMaster-Utility/blob/f30688de7fede5cef20c0a0d163ec13ec6ef7513/V-Max%20Tool/RapidLok.cs#L508-L526): six encoded header bytes become four bytes; their XOR must be zero.  Header semantics are deliberately not assigned.
- [V-Max Tool/GCR.cs, lines 459–467](https://github.com/DarylKrans/ReMaster-Utility/blob/f30688de7fede5cef20c0a0d163ec13ec6ef7513/V-Max%20Tool/GCR.cs#L459-L467): a 583-byte marker-included candidate with byte 196 = `A4` takes the v2–7 branch; everything else takes the v1 fallback.  That fallback is not positive identification.
- [V-Max Tool/GCR.cs, lines 529–550](https://github.com/DarylKrans/ReMaster-Utility/blob/f30688de7fede5cef20c0a0d163ec13ec6ef7513/V-Max%20Tool/GCR.cs#L529-L550): integrity functions.  This helper implements only the v1 encoded-byte relation, not the v2–7 payload transform.

No tracked LICENSE, COPYING, or NOTICE file was found at this revision.  The pinned [`V-Max Tool/Properties/About.txt`](https://github.com/DarylKrans/ReMaster-Utility/blob/f30688de7fede5cef20c0a0d163ec13ec6ef7513/V-Max%20Tool/Properties/About.txt) states “No rights reserved” and acknowledges Bangui Bob’s RapidLok documentation and patching.  The README supplies the development-source warning, not that waiver or credit.  This is meaningful permission evidence, but a source copyright notice remains, and the waiver’s scope and third-party coverage are uncertain.  Retain those credits; do not infer a specific license.  The source itself warns that development revisions may be buggy or incomplete.  The implementation follows code, not an inconsistent parity-bit-order comment.  The source attribution and uncertainty accompany this package.  No broader license grant is inferred.  See the [repository notices](../../../../THIRD_PARTY_NOTICES.md).

## Separate explicit record decoder

`rapidlok_v1_record.py` additionally adapts the pinned `V-Max Tool/GCR.cs:459-585` transform and the canonical encoding constraints at `V-Max Tool/GCR.cs:618-625`.  Its [separate record profile](RECORD-PROFILE.md) requires explicit selection, preserves opaque auxiliary bytes, and does not identify historical revisions or files.  That profile accepts independently observed 24/25-one data syncs; the recognition-only contract below is unchanged.  The same attribution, third-party-credit uncertainty, and release considerations apply to both helpers.

## Narrow recognition-only contract

- Input is one represented raw track, a known `6B` bit position, and optional single-revolution circular reading.  It is not a general G64 parser or automatic family identifier.
- All bits are physical MSB-first.  Coordinates are relative to track byte zero, and ends are exclusive.  Circular output coordinates are unwrapped; callers map them modulo the represented track length.
- Require at least 25 data-sync ones, one valid seven-byte `75` header at exactly 152 or 160 bits before the marker, and 772 six-bit symbols beginning nine bits after the marker.  The 16-value alphabet and header distances describe an observed layout, not all RapidLok revisions.
- The 583-byte interval is the pinned source's **candidate extraction window**, not a proved payload boundary.  Recognizing the six-bit field does not establish a symbol-to-payload mapping.
- This observed-layout recognizer cannot accept the source's v2–7 hint: byte 196 = `A4` forces six-bit symbol 260 to `12`, outside its alphabet.  The standalone `source_integrity_probe` can report that hint diagnostically; full `inspect_record` must reject it.  Do not relax the alphabet to manufacture support.
- `require_source_hint` rejects a conflicting source discriminator, but even a matching hint leaves `variant_established` false and `payload_recovery` refused.  A checksum match is only a relation match.  Payload checksum mismatch is reported explicitly, not promoted to recovery success.
- Malformed framing, bad projected header XOR, corrupt six-bit symbols, and truncation raise `RecognitionError`.  Header projection does not validate every unused encoding bit.  XOR integrity is collision-prone, and changing two bytes can preserve it.

## Independent synthetic checks

Run `PYTHONDONTWRITEBYTECODE=1 python3 test_rapidlok_recognize.py` from this directory.  These tests contain no commercial bytes and use no encoder.

The hand vector `75 48 90 D8 45 10 00` projects to `A5 3C 99 00`, whose XOR is zero.  The eight one-hot parity vectors independently check each selected tail bit.  The repeated literal `92 49 24` supplies four `001001` symbols at the observed one-bit offset; 193 repetitions supply 772.  A following `FF` both supplies the last selected bit and cancels the odd-triple XOR.  Tail `A4 A4` contributes zero selected parity bits.  This is a synthetic shape/checksum fixture, **not** a claim of a valid hardware sector.

Controls cover changed header data, bad marker/sync/header framing, corrupt symbol, truncation, mismatched source hints in both directions, MSB-first unaligned/circular reading, and an XOR collision that still cannot admit payload recovery.

CLI: `python3 rapidlok_recognize.py RAW-TRACK.bin MARKER-BIT [--circular]`.  JSON goes to stdout; rejection exits 2.  No input is modified.  Python 3.10+ and its standard library suffice.
