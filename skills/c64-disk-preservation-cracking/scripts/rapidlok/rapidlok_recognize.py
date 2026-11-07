"""Bounded MSB-first RapidLok-like record recognition, not payload recovery.

The six-bit field is an observed shape, not a known payload alphabet mapping.
Header and v1 integrity formulas are adapted from ReMaster-Utility, commit
f30688de7fede5cef20c0a0d163ec13ec6ef7513.  See ATTRIBUTION.md for source
locations and unresolved licensing.  No encoder, repair, or execution exists.
"""
from functools import reduce
from operator import xor

RECORD_BYTES = 583
FIELD_OFFSET_BITS = 9
FIELD_SYMBOLS = 772
ALPHABET = frozenset((0x09, 0x0B, 0x0D, 0x0F, 0x19, 0x1B, 0x1D, 0x1F,
                      0x29, 0x2B, 0x2D, 0x2F, 0x35, 0x37, 0x39, 0x3B))
SOURCE_V1_HINT = 'v1-fallback'
SOURCE_V2_HINT = 'v2-7-candidate'


class RecognitionError(ValueError):
    """The supplied bytes do not satisfy this narrow recognition contract."""


def read_bits(track: bytes, start: int, length: int, *, circular: bool = False) -> int:
    """Read physical MSB-first bits, with at most one track revolution."""
    total = len(track) * 8
    if length <= 0 or length > total:
        raise RecognitionError('truncated: requested field exceeds represented track')
    if not circular and (start < 0 or start + length > total):
        raise RecognitionError('truncated: field crosses linear track boundary')
    value = 0
    for position in range(start, start + length):
        position %= total
        value = (value << 1) | ((track[position // 8] >> (7 - position % 8)) & 1)
    return value


def read_bytes(track: bytes, start: int, count: int, *, circular: bool = False) -> bytes:
    value = read_bits(track, start, count * 8, circular=circular)
    return value.to_bytes(count, 'big')


def sync_length(track: bytes, marker_bit: int, *, circular: bool = False) -> int:
    count = 0
    for distance in range(1, len(track) * 8 + 1):
        position = marker_bit - distance
        if not circular and position < 0:
            break
        if read_bits(track, position, 1, circular=circular) != 1:
            break
        count += 1
    return count


def decode_header(header: bytes) -> dict:
    """Decode exactly 75 + six encoded bytes; require the four-byte XOR check."""
    if len(header) != 7 or header[0] != 0x75:
        raise RecognitionError('header: expected seven bytes beginning with 75')
    decoded = []
    for position in (1, 4):
        b1, b2, b3 = header[position:position + 3]
        decoded.append(((b1 & 0x60) << 1) | ((b1 & 0x0C) << 2)
                       | ((b1 & 1) << 3) | ((b2 & 0x80) >> 5) | ((b2 & 0x30) >> 4))
        decoded.append(((b2 & 6) << 5) | ((b3 & 0xC0) >> 2)
                       | ((b3 & 0x18) >> 1) | (b3 & 3))
    if reduce(xor, decoded) != 0:
        raise RecognitionError('header: decoded XOR integrity mismatch')
    return {'decoded_hex': bytes(decoded).hex(), 'integrity': 'xor-four-is-zero',
            'integrity_ok': True, 'semantic_labels': 'unassigned'}


def source_integrity_probe(record: bytes, *, require_source_hint: str | None = None) -> dict:
    """Apply the pinned source discriminator and v1 encoded-byte XOR relation.

    A pass does NOT establish a variant or validate recovered payload.  The
    source's v1 label is a fallback.  v2-7 payload integrity is NOT implemented.
    """
    if len(record) != RECORD_BYTES:
        raise RecognitionError('record: expected exactly 583 bytes')
    if record[0] != 0x6B:
        raise RecognitionError('record: expected leading 6B')
    hint = SOURCE_V2_HINT if record[196] == 0xA4 else SOURCE_V1_HINT
    if require_source_hint not in (None, SOURCE_V1_HINT, SOURCE_V2_HINT):
        raise ValueError('unknown source hint')
    if require_source_hint is not None and hint != require_source_hint:
        raise RecognitionError(f'wrong-variant: source discriminator gives {hint}, not {require_source_hint}')
    result = {'source_hint': hint, 'byte196': record[196],
              'variant_established': False, 'payload_recovery': 'refused'}
    if hint == SOURCE_V1_HINT:
        b, a = record[-2:]
        parity = (a & 3) | ((a & 0x18) >> 1) | ((b & 0x18) << 3) | ((b & 3) << 4)
        checksum = reduce(xor, record[1:-2], 0)
        result['v1_encoded_integrity'] = {'xor': checksum, 'tail_parity': parity,
                                          'matches': checksum == parity}
    else:
        result['v2_7_integrity'] = 'not-evaluated: no validated payload transform'
    return result


def inspect_record(track: bytes, marker_bit: int, *, circular: bool = False,
                   require_source_hint: str | None = None) -> dict:
    """Recognize one fixed-layout candidate; return metadata, never payload.

    Requires a >=25-one data sync, a seven-byte 75 header at exactly -152 or
    -160 bits with >=10-one sync and valid XOR, and the observed 772-symbol
    field.  These distances/alphabet are deliberately narrow, not universal.
    End coordinates are exclusive and unwrapped, relative to track byte zero.
    """
    total = len(track) * 8
    if not 0 <= marker_bit < total:
        raise RecognitionError('marker: outside represented track')
    # Read the whole candidate before smaller fields so truncation cannot pass.
    record = read_bytes(track, marker_bit, RECORD_BYTES, circular=circular)
    probe = source_integrity_probe(record, require_source_hint=require_source_hint)
    data_sync = sync_length(track, marker_bit, circular=circular)
    if data_sync < 25:
        raise RecognitionError('record: fewer than 25 sync ones')
    headers = []
    for distance in (152, 160):
        position = marker_bit - distance
        try:
            raw = read_bytes(track, position, 7, circular=circular)
            if raw[0] != 0x75 or sync_length(track, position, circular=circular) < 10:
                continue
            header = decode_header(raw)
        except RecognitionError:
            continue
        headers.append({'start_bit': position, 'end_bit_exclusive': position + 56,
                        'distance_bits': distance, **header})
    if len(headers) != 1:
        raise RecognitionError('header: expected one valid 75 header at -152 or -160 bits')
    symbols = []
    for index in range(FIELD_SYMBOLS):
        position = marker_bit + FIELD_OFFSET_BITS + 6 * index
        symbol = read_bits(track, position, 6, circular=circular)
        if symbol not in ALPHABET:
            raise RecognitionError(f'corrupt-symbol: index {index}, track bit {position}, value {symbol:02x}')
        symbols.append(symbol)
    end = marker_bit + RECORD_BYTES * 8
    return {'status': 'recognition-only', 'orientation': 'MSB-first',
            'marker_bit': marker_bit, 'candidate_end_bit_exclusive': end,
            'candidate_bytes': RECORD_BYTES, 'crosses_track_end': end > total,
            'boundary_status': '583-byte source candidate; not a proved payload boundary',
            'data_sync_ones': data_sync, 'header': headers[0],
            'field': {'start_bit': marker_bit + FIELD_OFFSET_BITS,
                      'end_bit_exclusive': marker_bit + FIELD_OFFSET_BITS + FIELD_SYMBOLS * 6,
                      'symbols': FIELD_SYMBOLS, 'alphabet_ok': True,
                      'distinct_symbols': sorted(set(symbols)), 'payload_mapping': 'unknown'},
            **probe}


def main() -> None:
    import argparse
    import json
    from pathlib import Path
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('track', type=Path, help='raw represented track bytes, not a G64 container')
    parser.add_argument('marker_bit', type=int, help='MSB-first bit index of 6B marker')
    parser.add_argument('--circular', action='store_true', help='allow a field to wrap once')
    parser.add_argument('--require-source-hint', choices=(SOURCE_V1_HINT, SOURCE_V2_HINT))
    args = parser.parse_args()
    try:
        result = inspect_record(args.track.read_bytes(), args.marker_bit,
                                circular=args.circular, require_source_hint=args.require_source_hint)
    except RecognitionError as error:
        parser.exit(2, f'refused: {error}\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
