"""Strict, explicit-profile later Vorpal record candidate.  See CONTRACT.md.

No scanning, G64 parsing, wrapping, file recovery, repair, or target execution.
Only payload bytes are covered by the format's XOR8 check, not the sector ID.
"""
from dataclasses import dataclass

PROFILE = "vorpal-later-128-xor-7faa-v1"
RECORD_BITS = 16 + 1280 + 10 + 9

# ReMaster f30688de, GCR.cs:93-99.  None means REFUSE, never substitute.
_NIBBLE = (
    None, None, None, None, None, 14, 15, None,
    None, 0, 1, 2, 5, 3, 4, 5,
    None, None, 6, 7, 10, 8, 9, 10,
    None, 11, 12, 13, None, 14, 15, None,
)


class RecordError(ValueError):
    """The requested record was refused; no payload result is returned."""

    def __init__(self, code: str, detail: str):
        self.code = code
        super().__init__(f"{code}: {detail}")


@dataclass(frozen=True)
class DecodedRecord:
    profile: str
    marker_bit: int
    payload_bit: int
    checksum_bit: int
    sector_id_bit: int
    end_bit_exclusive: int
    raw_packed: bytes
    raw_bit_length: int
    payload: bytes
    sector_id: int
    sector_id_raw: int
    stored_checksum: int
    calculated_checksum: int
    integrity: str


def decode_record(track: bytes, *, profile: str, marker_bit: int,
                  bit_length: int) -> DecodedRecord:
    """Decode one caller-located linear record, using zero-based MSB-first bits.

    bit_length excludes any transport padding.  A returned record passed legal
    symbols and payload XOR8; this is neither authentication nor header integrity.
    Raises RecordError on unsupported profile, invalid input, truncated record,
    bad marker, illegal symbol, unsupported ID, or checksum mismatch.
    """
    if profile != PROFILE:
        raise RecordError("unsupported-profile", repr(profile))
    if not isinstance(track, bytes):
        raise RecordError("invalid-input", "track must be immutable bytes")
    if (type(bit_length) is not int or type(marker_bit) is not int
            or not 0 <= bit_length <= len(track) * 8 or marker_bit < 0):
        raise RecordError("invalid-input", "invalid bit length or marker coordinate")
    end = marker_bit + RECORD_BITS
    if end > bit_length:
        raise RecordError("truncated", f"need bits [{marker_bit}, {end}), have {bit_length}")

    def value(start: int, width: int) -> int:
        result = 0
        for p in range(start, start + width):
            result = (result << 1) | ((track[p // 8] >> (7 - p % 8)) & 1)
        return result

    if value(marker_bit, 16) != 0x7FAA:
        raise RecordError("bad-marker", f"expected 7faa at bit {marker_bit}")
    payload_bit = marker_bit + 16
    decoded = bytearray()
    for i in range(129):  # 128 payload bytes, then the encoded XOR8 value.
        pair = []
        for j in range(2):
            position = payload_bit + i * 10 + j * 5
            symbol = value(position, 5)
            nibble = _NIBBLE[symbol]
            if nibble is None:
                raise RecordError("illegal-symbol", f"{symbol:02x} at bit {position}")
            pair.append(nibble)
        decoded.append((pair[0] << 4) | pair[1])
    payload, stored = bytes(decoded[:128]), decoded[128]
    calculated = 0
    for b in payload:
        calculated ^= b
    if stored != calculated:
        raise RecordError("checksum-mismatch", f"stored {stored:02x}, calculated {calculated:02x}")
    sector_id_bit = payload_bit + 1290
    sector_id = 0
    for position in (0, 2, 3, 5, 6, 8):
        sector_id = (sector_id << 1) | value(sector_id_bit + position, 1)
    if sector_id > 46:
        raise RecordError("unsupported-id", f"{sector_id} is outside profile range 0..46")

    raw = bytearray((RECORD_BITS + 7) // 8)
    for i in range(RECORD_BITS):
        raw[i // 8] |= value(marker_bit + i, 1) << (7 - i % 8)
    return DecodedRecord(
        profile=PROFILE, marker_bit=marker_bit, payload_bit=payload_bit,
        checksum_bit=payload_bit + 1280, sector_id_bit=sector_id_bit,
        end_bit_exclusive=end, raw_packed=bytes(raw), raw_bit_length=RECORD_BITS,
        payload=payload, sector_id=sector_id, sector_id_raw=value(sector_id_bit, 9),
        stored_checksum=stored, calculated_checksum=calculated,
        integrity="xor8-payload-only",
    )
