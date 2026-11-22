"""Narrow grammar delta for one exact PETSpeed $2245 runtime.

No runtime bytes or private assets are required.  The canonical base is pinned
as a whole so future primary, secondary, or contextual grammar additions cannot
silently become admissions for this runtime.  The ordinary decoder still checks
the exact runtime, entry stub, layout, operands, and target boundaries.
"""
from copy import deepcopy
import hashlib
import json


RUNTIME_SHA256 = '02fff9b629da0d6f927549c4c0e7777fc6d31b040ae41c1b9630f114bd4e6af5'
BASE_PROFILE_SHA256 = 'd22ff6f07884e6012c221f9cda1013e7bf8eb16a677737603e1219df75ee9260'


def _rule(mnemonic: str, operand: str, comment: str, evidence: str) -> dict:
    return dict(mnemonic=mnemonic, operand=operand, control='fallthrough',
                comment=comment, evidence='Exact 02fff9b6 runtime: ' + evidence)


def build_profile(base_profile: dict) -> dict:
    """Return an independent profile; reject any unreviewed base revision."""
    digest = hashlib.sha256(json.dumps(base_profile, sort_keys=True).encode()).hexdigest()
    if digest != BASE_PROFILE_SHA256:
        raise ValueError('variant_02fff9b6 requires the reviewed canonical base profile')
    p = deepcopy(base_profile)
    p.update(id='petspeed-c64-02fff9b6-2245', runtimeSha256=RUNTIME_SHA256)
    p['opcodes'].update({
        '86': _rule('POWER_REVERSED', 'none',
                    'FAC := incoming FAC ^ incoming ARG',
                    '$0832 -> $1CA3; $1A08 swaps accumulators before the common '
                    '$1C0E/$1C79 power paths; no inline fetch.'),
        'AF': _rule('OPEN_SECONDARY', 'none',
                    'OPEN with FAC secondary address, stacked device and logical file, and empty filename',
                    '$0884 -> $18A0, X=$5E selects $18BD; $190F/$0D34 pop '
                    'numeric values, then $FFC0 OPEN and $0926 fetch; no payload.'),
        'B4': _rule('SGN_VARIANT_BC39', 'none',
                    'Integer FAC gives -1/0/+1; with stock BASIC, floating nonzero gives '
                    'integer -32383 and floating zero gives 0; not ordinary BASIC SGN',
                    '$16E8 floating path calls $BC39 at $16EC, not $BC2B.  '
                    'The unchanged caller stores returned A in both integer bytes '
                    '($64/$65); nonzero floating sign conversion leaves A=$81.  '
                    'Integer path $1717 is unchanged; no inline operand.'),
        'C7': _rule('CHR_STRING', 'none',
                    'FAC := one-character string after numeric byte conversion/range check',
                    '$08B4 -> $1E9E; $17BB checks the byte, $65 is staged at '
                    '$0100, then $1D6E allocates length one; no inline operand.'),
        'F2': _rule('LOAD_STRING_ELEMENT_AT', 'u16le',
                    'FAC := three-byte string descriptor at ${value:04X}; '
                    'absolute element address, not a recovered array/subscript',
                    '$090A -> $204E; $21A6 reads two little-endian address bytes; '
                    '$202C copies length/pointer into $64 through $66 and sets B5=$FF.'),
    })
    p['opcodes']['80']['selectors']['0A'] = _rule(
        'STATUS_ARG', 'none', 'ARG := sign-extended KERNAL status byte ST ($90)',
        '$0826 -> $1982; selector X=$14 reads $19AC -> $25C6.  '
        '$155F consumes the selector; $25C6 through $25D6 sets B6=1, '
        'copies $90 to $6D, and sign-extends into $6C; no payload.')
    p['limitations'] += [
        'Exact runtime only; inherited grammar is pinned to the reviewed base.  '
        'No classic extension or $2267-only additions are inherited.',
        'SGN_VARIANT_BC39 is deliberately not lifted as ordinary SGN.  The floating '
        'result is derived statically for stock BASIC 901226-01 '
        '(SHA-256 89878cea0a268734696de11c4bae593eaaa506465d2029d619c0e0cbccdfa62d); '
        'input type, reachability, and execution are not established.',
        'Optional STOP checking compares $91 with $EF, not $7F.  Its installer '
        'selectors 80/11 and 80/12 remain unsupported.',
        'Differing bytes after the RTS at $27F1 remain part of the exact hash; '
        'no claim that they are globally unused.',
    ]
    return p
