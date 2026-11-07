"""Linear raw-track inventory for one explicit Vorpal profile; stdlib only.

No G64 parsing, wrapping, repair, ordering, winner selection, or file recovery.
See INVENTORY.md and the unchanged decoder's CONTRACT.md for acceptance limits.
"""
import argparse
from collections import Counter, defaultdict
from hashlib import sha256
import json
from pathlib import Path

from vorpal_record import PROFILE, RECORD_BITS, RecordError, decode_record

MARKER = '0111111110101010'  # 7FAA, MSB first.


def _packed(bits: str) -> bytes:
    """Repack an observed window MSB-first with zero transport tail padding."""
    padded = bits + '0' * (-len(bits) % 8)
    return bytes(int(padded[i:i + 8], 2) for i in range(0, len(padded), 8))


def scan_track(track: bytes, *, profile: str, bit_length: int) -> dict:
    """Inventory every complete 16-bit marker in the supplied linear extent.

    RecordError handles invalid input/profile.  Per-marker decoder refusals are
    retained as evidence, including their exact code/message.  No payload bytes
    are returned.  Candidate list order is source-coordinate order only.
    """
    if profile != PROFILE:
        raise RecordError('unsupported-profile', repr(profile))
    if not isinstance(track, bytes):
        raise RecordError('invalid-input', 'track must be immutable bytes')
    if type(bit_length) is not int or not 0 <= bit_length <= len(track) * 8:
        raise RecordError('invalid-input', 'invalid bit length')

    bits = ''.join(f'{b:08b}' for b in track)[:bit_length]
    candidates = []
    by_id = defaultdict(list)
    start = 0
    while True:
        marker = bits.find(MARKER, start)
        if marker < 0:
            break
        # Advance ONE bit, not RECORD_BITS: valid observed records can overlap.
        start = marker + 1
        end = marker + RECORD_BITS
        observed_end = min(end, bit_length)
        raw = _packed(bits[marker:observed_end])
        item = {
            'marker_bit': marker,
            'requested_end_bit_exclusive': end,
            'observed_end_bit_exclusive': observed_end,
            'raw_bit_length': observed_end - marker,
            'raw_packed_sha256': sha256(raw).hexdigest(),
            'raw_zero_tail_padding_bits': -(observed_end - marker) % 8,
        }
        try:
            record = decode_record(track, profile=profile, marker_bit=marker,
                                   bit_length=bit_length)
        except RecordError as error:
            item.update(status='refused', refusal_code=error.code,
                        refusal_message=str(error))
        else:
            item.update(
                status='accepted', sector_id=record.sector_id,
                sector_id_raw=record.sector_id_raw,
                payload_bit=record.payload_bit, checksum_bit=record.checksum_bit,
                sector_id_bit=record.sector_id_bit,
                payload_bytes=len(record.payload),
                payload_sha256=sha256(record.payload).hexdigest(),
                stored_checksum=record.stored_checksum,
                calculated_checksum=record.calculated_checksum,
                integrity=record.integrity,
            )
            by_id[record.sector_id].append(item)
        candidates.append(item)

    repeated_ids = []
    for sector_id, copies in sorted(by_id.items()):
        if len(copies) < 2:
            continue
        payload_groups = defaultdict(list)
        raw_groups = defaultdict(list)
        for item in copies:
            payload_groups[item['payload_sha256']].append(item['marker_bit'])
            raw_groups[item['raw_packed_sha256']].append(item['marker_bit'])
        repeated_ids.append({
            'sector_id': sector_id,
            'marker_bits': [item['marker_bit'] for item in copies],
            'conflicting_accepted_payloads': len(payload_groups) > 1,
            'payload_groups': dict(sorted(payload_groups.items())),
            'raw_groups': dict(sorted(raw_groups.items())),
        })
    refusals = Counter(item['refusal_code'] for item in candidates
                       if item['status'] == 'refused')
    return {
        'schema': 'vorpal-linear-inventory-v1',
        'profile': profile,
        'source': {'transport_bytes': len(track), 'bit_length': bit_length,
                   'sha256': sha256(track).hexdigest()},
        'coordinates': 'zero-based MSB-first track bits; half-open intervals',
        'boundary_policy': 'linear-only; no wrap, rotation, or boundary completion',
        'raw_hash_policy': 'available window repacked MSB-first, zero tail padding',
        'integrity': 'legal symbols and XOR8 payload only; ID/filler unprotected',
        'candidate_order': 'source-coordinate order, not logical sector order',
        'summary': {
            'candidate_count': len(candidates),
            'accepted_count': sum(len(v) for v in by_id.values()),
            'refused_count': sum(refusals.values()),
            'refusal_counts': dict(sorted(refusals.items())),
            'observed_accepted_ids': sorted(by_id),
            'repeated_id_count': len(repeated_ids),
            'conflicting_id_count': sum(g['conflicting_accepted_payloads']
                                        for g in repeated_ids),
        },
        'candidates': candidates,
        'repeated_ids': repeated_ids,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('track', type=Path, help='raw track bytes, not a G64 image')
    parser.add_argument('--profile', required=True, choices=[PROFILE])
    parser.add_argument('--bit-length', type=int, required=True,
                        help='meaningful linear bits, excluding transport padding')
    args = parser.parse_args()
    try:
        result = scan_track(args.track.read_bytes(), profile=args.profile,
                            bit_length=args.bit_length)
    except (OSError, RecordError) as error:
        parser.exit(2, f'{error}\n')
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
