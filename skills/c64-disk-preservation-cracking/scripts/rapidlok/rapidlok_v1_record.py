"""Explicit, narrow v1-compatible RapidLok record decoding, not file recovery.

Adapted from ReMaster-Utility f30688de7fede5cef20c0a0d163ec13ec6ef7513.
See RECORD-PROFILE.md and ATTRIBUTION.md for scope, evidence, and licensing.
No encoder, image writer, repair, heuristic resynchronization, or execution.
"""
import hashlib
from functools import reduce
from operator import xor

from rapidlok_recognize import RecognitionError, read_bytes, sync_length

PROFILE = 'remaster-v1-compatible'
RECORD_BYTES = 583
HEADER_DISTANCE = 160
PROFILE_168 = 'remaster-v1-compatible-168'


class DecodeError(ValueError):
    """Input does not satisfy the explicitly selected bounded profile."""


def _project(a: int, b: int, c: int) -> tuple[int, int]:
    return (
        ((a & 0x60) << 1) | ((a & 0x0C) << 2) | ((a & 1) << 3)
        | ((b & 0x80) >> 5) | ((b & 0x30) >> 4),
        ((b & 6) << 5) | ((c & 0xC0) >> 2) | ((c & 0x18) >> 1) | (c & 3),
    )


def _tail(b: int, a: int) -> int:
    return ((b & 0x18) << 3) | ((b & 3) << 4) | ((a & 0x18) >> 1) | (a & 3)


def _check_triple(a: int, b: int, c: int, location: str) -> None:
    checks = (
        (a & 0x82) == 0x82,
        bool(a & 0x10) == ((a & 0x68) != 0x68),
        bool(b & 8),
        bool(b & 0x40) == (not (a & 1 and (b & 0xA0) == 0xA0)),
        bool(b & 1) == (not (c & 0x80 and (b & 6) == 6)),
        bool(c & 0x20),
        bool(c & 4) == ((c & 0x1A) != 0x1A),
    )
    if not all(checks):
        raise DecodeError(f'encoding: noncanonical triple at {location}')


def _decode_body(record: bytes) -> tuple[bytes, bytes, int]:
    if len(record) != RECORD_BYTES:
        raise DecodeError('record: expected exactly 583 bytes')
    if record[0] != 0x6B:
        raise DecodeError('record: expected leading 6B')
    if record[196] == 0xA4:
        raise DecodeError('profile: v2-7 discriminator is unsupported')
    for position in range(1, 577, 3):
        _check_triple(*record[position:position + 3], f'record byte {position}')
    for position in range(577, 583):
        value = record[position]
        if (value & 0xE0) != 0xA0 or bool(value & 4) != ((value & 0x1A) != 0x1A):
            raise DecodeError(f'encoding: noncanonical tail at record byte {position}')
    encoded_xor = reduce(xor, record[1:581], 0)
    if encoded_xor != _tail(record[581], record[582]):
        raise DecodeError('integrity: encoded-byte XOR mismatch')
    body = bytearray()
    for position in range(1, 577, 3):
        body.extend(value ^ 0xFF for value in _project(*record[position:position + 3]))
    auxiliary = bytes((_tail(record[577], record[578]), _tail(record[579], record[580])))
    return bytes(body), auxiliary, encoded_xor


def decode_record(track: bytes, marker_bit: int, *, profile: str,
                  circular: bool = False) -> dict:
    """Decode one explicitly located record; return raw and projected evidence.

    The whole header-through-record span must fit in one represented revolution.
    Ends are exclusive, track-relative, MSB-first, and unwrapped when circular.
    Require a canonical 75 header at the selected exact 160- or 168-bit distance,
    >=10 header-sync ones, >=24 data-sync ones, and canonical encoded bytes.
    Only the 168-bit profile also refuses an intervening >=10-one gap sync.
    It does not discover markers, assign sector numbers, or establish a revision.
    """
    if profile == PROFILE:
        header_distance = HEADER_DISTANCE
    elif profile == PROFILE_168:
        header_distance = 168
    else:
        raise DecodeError('profile: explicitly select remaster-v1-compatible')
    total = len(track) * 8
    if not 0 <= marker_bit < total:
        raise DecodeError('marker: outside represented track')
    if total < header_distance + RECORD_BYTES * 8:
        raise DecodeError('truncated: header-through-record span exceeds one revolution')
    header_bit = marker_bit - header_distance
    try:
        header = read_bytes(track, header_bit, 7, circular=circular)
        record = read_bytes(track, marker_bit, RECORD_BYTES, circular=circular)
        header_sync = sync_length(track, header_bit, circular=circular)
        data_sync = sync_length(track, marker_bit, circular=circular)
        if profile == PROFILE_168:
            gap = read_bytes(track, header_bit + 56, 14, circular=circular)
            gap_bits = ''.join(f'{byte:08b}' for byte in gap)
    except RecognitionError as error:
        raise DecodeError(str(error)) from error
    if header_sync < 10 or data_sync < 24:
        raise DecodeError('framing: require >=10 header-sync and >=24 data-sync ones')
    if profile == PROFILE_168:
        # The consumer waits for the next sync after the seven-byte header.
        if data_sync > 112 or '1' * 10 in gap_bits[:112 - data_sync]:
            raise DecodeError('framing: next sync is not the supplied data boundary')
    if not (header[0] == 0x75 and (header[1] & 0x90) == 0x90
            and (header[2] & 9) == 9 and header[4:6] == b'\xD6\xED'):
        raise DecodeError('header: unsupported fingerprint')
    projected = bytearray()
    for position in (1, 4):
        triple = header[position:position + 3]
        _check_triple(*triple, f'header byte {position}')
        projected.extend(_project(*triple))
    if reduce(xor, projected, 0):
        raise DecodeError('header: projected XOR mismatch')
    body, auxiliary, encoded_xor = _decode_body(record)
    end = marker_bit + RECORD_BYTES * 8
    return {
        'status': 'decoded-under-explicit-profile', 'profile': profile,
        'historical_revision_established': False, 'logical_mapping': 'not-established',
        'file_recovery': False, 'orientation': 'MSB-first',
        'marker_bit': marker_bit, 'record_end_bit_exclusive': end,
        'crosses_track_end': end > total, 'header_crosses_track_start': header_bit < 0,
        'data_sync_ones': data_sync, 'record_hex': record.hex(),
        'record_sha256': hashlib.sha256(record).hexdigest(),
        'header': {'start_bit': header_bit, 'end_bit_exclusive': header_bit + 56,
                   'sync_ones': header_sync, 'encoded_hex': header.hex(),
                   'projected_hex': bytes(projected).hex(), 'semantic_labels': 'unassigned'},
        'body': {'bytes': len(body), 'hex': body.hex(), 'sha256': hashlib.sha256(body).hexdigest()},
        'auxiliary_hex': auxiliary.hex(), 'auxiliary_meaning': 'unknown',
        'integrity': {'encoded_xor': encoded_xor, 'stored_check': _tail(*record[581:583]),
                      'matches': True, 'collision_resistant': False},
        'encoding': 'pinned-source-canonical-triples-and-tail',
        'spans': {'body_encoding': [marker_bit + 8, marker_bit + 4616],
                  'auxiliary_encoding': [marker_bit + 4616, marker_bit + 4648],
                  'integrity_encoding': [marker_bit + 4648, end]},
    }


def main() -> None:
    import argparse
    import json
    from pathlib import Path
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('track', type=Path, help='raw represented track bytes, not a G64 container')
    parser.add_argument('marker_bit', type=int, help='known MSB-first bit position of 6B')
    parser.add_argument('--profile', required=True, choices=(PROFILE, PROFILE_168))
    parser.add_argument('--circular', action='store_true')
    args = parser.parse_args()
    try:
        result = decode_record(args.track.read_bytes(), args.marker_bit,
                               profile=args.profile, circular=args.circular)
    except (DecodeError, OSError) as error:
        parser.exit(2, f'refused: {error}\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
