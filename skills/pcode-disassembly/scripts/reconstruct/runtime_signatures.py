"""Exact, conjunctive runtime-region recognition, independent of decoder admission.

Catalogs contain mapped-address windows, not filenames or input-file digests.
All windows in an entry must match.  No masking, relocation, or fuzzy threshold
is implicit.  This module has no default catalog or private dependencies.
"""
from __future__ import annotations

import hashlib
import re


def as_prg(data: bytes, raw_base: int | None = None) -> bytes:
    """Validate a mapped 16-bit image; an empty/short PRG simply has no match."""
    if raw_base is not None:
        if not 0 <= raw_base <= 65535 or raw_base + len(data) > 65536:
            raise ValueError('invalid raw image extent')
        return raw_base.to_bytes(2, 'little') + data
    if len(data) >= 2 and int.from_bytes(data[:2], 'little') + len(data) - 2 > 65536:
        raise ValueError('invalid PRG image extent')
    return data


class RuntimeCatalog:
    """Validated fixed-address runtime signatures; source citations are inert."""

    def __init__(self, catalog: dict):
        if catalog.get('schema') != 'basic-runtime-regions-v1':
            raise ValueError('unsupported runtime catalog')
        entries = []
        seen = set()
        for entry in catalog['entries']:
            ident, family = entry['id'], entry['family']
            if not isinstance(ident, str) or not ident or ident in seen:
                raise ValueError('missing or duplicate runtime catalog ID')
            if not isinstance(family, str) or not family:
                raise ValueError('missing runtime family')
            seen.add(ident)
            load = entry.get('loadAddress')
            if load is not None and (type(load) is not int or not 0 <= load <= 65535):
                raise ValueError('invalid runtime load address')
            windows = []
            for window in entry['windows']:
                start, end, digest = window['start'], window['end'], window['sha256']
                if (type(start) is not int or type(end) is not int or
                        not 0 <= start < end <= 65536):
                    raise ValueError('invalid runtime window extent')
                if not isinstance(digest, str) or not re.fullmatch('[0-9a-f]{64}', digest):
                    raise ValueError('invalid runtime window SHA256')
                windows.append((start, end, digest, window.get('purpose', 'runtime region')))
            windows.sort()
            if not windows or any(a[1] > b[0] for a, b in zip(windows, windows[1:])):
                raise ValueError('empty or overlapping runtime windows')
            entries.append((ident, family, load, tuple(windows)))
        self._entries = tuple(sorted(entries))

    def match(self, data: bytes, *, raw_base: int | None = None) -> list[dict]:
        """Return component evidence only, never a decodable-object contract."""
        prg = as_prg(data, raw_base)
        if len(prg) < 2:
            return []
        base = int.from_bytes(prg[:2], 'little')
        raw = prg[2:]
        matches = []
        for ident, family, load, windows in self._entries:
            if load is not None and load != base:
                continue
            evidence = []
            for start, end, digest, purpose in windows:
                lo, hi = start - base, end - base
                if lo < 0 or hi > len(raw):
                    break
                if hashlib.sha256(raw[lo:hi]).hexdigest() != digest:
                    break
                evidence.append({'kind': 'exact-native-region-sha256',
                                 'start': start, 'end': end, 'sha256': digest,
                                 'purpose': purpose})
            else:
                matches.append({'catalogId': ident, 'family': family,
                                'role': 'runtime-component',
                                'confidence': 'all required runtime regions match exactly',
                                'evidence': evidence, 'layoutValid': None,
                                'layoutError': None, 'decoderAdmitted': False})
        return matches
