"""Retained DATA for the independently evidenced classic PETSpeed runtime only.

The caller must verify the full runtime fingerprint before passing its hash.
``raw`` is exactly [STARTDATA, ARRAYTAB), including its final opaque byte.
No source, line map, other runtime edition, or memory outside that region is read.
Native READ handlers establish the low-six-bit text length and trailing numeric
bytes; they do not recover source line numbers, grouping, or original quoting.
"""
from decimal import Decimal, InvalidOperation
import re


RUNTIME_SHA256 = 'cee17449b6e9700af4642546477c06dbb42413888fa5e594ebded33014c5dbaf'
CAVEAT = ('Normalized retained DATA item, not original source layout.  Original '
          'line numbers, grouping, and quoting are unavailable.')
_NUMBER = re.compile(r'[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:E[+-]?[0-9]+)?\Z')


def _source_item(payload: bytes, numeric: int | None) -> tuple[str | None, str | None]:
    # Latin-1 is a reversible byte view, not a PETSCII-to-Unicode conversion.
    if any(b < 32 or b > 126 for b in payload):
        return None, 'Control/high PETSCII bytes retained exactly; no guessed source spelling.'
    text = payload.decode('ascii')
    is_number = _NUMBER.fullmatch(text) is not None
    if numeric is not None:
        try:
            matches = is_number and Decimal(text) == numeric
        except InvalidOperation:
            matches = False
        if not matches:
            return None, 'Retained text does not establish the stored numeric value.'
        return text, None
    if is_number:
        return text, None
    if '"' in text:
        return None, 'Quotation marks have no admitted source representation.'
    # Always quote strings, including empty/space/delimiter-bearing fields.
    return '"' + text + '"', None


def decode_data_region(raw: bytes, address: int, *, runtime_sha256: str) -> dict:
    """Decode an already bounded, identity-checked classic DATA region.

    ``status`` distinguishes complete presentation, partial-known-length (all
    records structurally decoded, some source spellings unsupported), and
    structural-refusal (truncated record, unknown tag length, or missing footer).
    On structural refusal *all* source text is withheld, including parsed prefix
    records; exact prefix evidence and the undecoded tail remain available.
    ``completeDataDecode`` means structural completeness, not executable BASIC
    equivalence.  The footer's value/purpose is not validated or interpreted.
    Invalid caller extents and unadmitted runtime identities raise ValueError.
    """
    if runtime_sha256 != RUNTIME_SHA256:
        raise ValueError('unsupported PETSpeed DATA runtime fingerprint')
    if not 0 <= address <= 0xFFFF or address + len(raw) > 0x10000:
        raise ValueError('invalid PETSpeed DATA region extent')
    result = {'address': address, 'end': address + len(raw), 'bytes': raw.hex(),
              'runtimeSha256': runtime_sha256, 'records': [], 'footer': None,
              'status': 'complete', 'completeDataDecode': True, 'error': None,
              'unsupportedPresentationCount': 0, 'caveat': CAVEAT}

    def refuse(offset, reason, expected_size=None):
        result.update(status='structural-refusal', completeDataDecode=False,
                      error={'address': address + offset, 'reason': reason,
                             'expectedSize': expected_size,
                             'lengthKnown': expected_size is not None},
                      undecodedTail={'address': address + offset,
                                     'bytes': raw[offset:max(offset, len(raw) - 1)].hex()})
        for row in result['records']:
            row.update(text=None, kind='opaque',
                       presentationReason='Entire DATA region structurally refused.')
        return result

    if not raw:
        return refuse(0, 'missing opaque DATA footer')
    limit = len(raw) - 1
    result['footer'] = {'address': address + limit, 'bytes': raw[-1:].hex(),
                        'kind': 'opaque', 'text': None,
                        'caveat': 'Final region byte retained; not an asserted $FF terminator.'}
    offset = 0
    while offset < limit:
        tag = raw[offset]
        # $C0..$FE have conflicting numeric/string cursor advancement;
        # $FF is a native out-of-DATA sentinel, not an admitted saved record.
        if tag >= 0xC0:
            return refuse(offset, f'unsupported DATA tag ${tag:02X}')
        length = tag & 0x3F
        extra = tag >> 6
        size = 1 + length + extra
        if offset + size > limit:
            return refuse(offset, 'truncated DATA record before opaque footer', size)
        payload = raw[offset + 1:offset + 1 + length]
        numeric_bytes = raw[offset + 1 + length:offset + size]
        numeric = (int.from_bytes(numeric_bytes, 'little', signed=extra == 2)
                   if extra else None)
        item, reason = _source_item(payload, numeric)
        result['records'].append({
            'address': address + offset, 'size': size, 'bytes': raw[offset:offset + size].hex(),
            'tag': tag, 'textLength': length, 'textHex': payload.hex(),
            'rawTextLatin1': payload.decode('latin-1'),
            'textDisplay': ''.join(chr(b) if 32 <= b <= 126 and b != 92
                                   else f'\\x{b:02X}' for b in payload),
            'numericBytes': numeric_bytes.hex(), 'numericValue': numeric,
            'numericEncoding': ('signed-le16' if extra == 2 else 'unsigned-u8' if extra else None),
            'text': 'DATA ' + item if item is not None else None,
            'kind': 'inferred' if item is not None else 'opaque',
            'presentationReason': reason, 'caveat': CAVEAT})
        if item is None:
            result['unsupportedPresentationCount'] += 1
        offset += size
    if result['unsupportedPresentationCount']:
        result['status'] = 'partial-known-length'
    return result
