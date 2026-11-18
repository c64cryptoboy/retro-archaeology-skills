"""Exact-runtime PETSpeed profile adapter; no image, ROM, or source assets.

Canonical helper API::

    profile = variant_2267.build_profile(base_profile)
    result = petspeed.disassemble(prg, profile)

``base_profile`` is the canonical petspeed_profile.json already loaded as a dict.
The helper performs no file I/O and never mutates that dict.  It returns the
existing petspeed-runtime-profile-v1 schema; the ordinary decoder retains all
runtime/stub/region/operand/target gates.  This is not a recognizer or translator.

Grammar variants: retain the admitted canonical forms, qualifying INPUT's
changed empty-field continuation; add 86, A1, A8, AF, C7, ED, EE, EF, F1, F2,
F4, and secondary 0B/0D.  FD/FE/FF are independently admitted merged handlers:
one unsigned index byte, record = $2900 + SEVEN * index, logical slot = 32+index.
Compact slots remain $2800 + EIGHT * slot.  Numeric INPUT/READ/GET and string
READ consume contextual 41/42; string INPUT/GET consume only 41.  These are
not standalone opcodes.  Literal floats retain six explicit accumulator bytes,
not packed-ROM hidden-bit encoding.  Unlisted forms/selectors still refuse.

Used versus unused grammar is a corpus property, not an admission mechanism.
Nine development streams exercise A1/A8, AF/C7, ED/F4, FD/FE/FF, and 0B/0D;
86, EE/EF/F1/F2 are native-supported but unused there.  Synthetic tests exercise
both groups, but establish decoding, not execution or BASIC equivalence.
"""

from copy import deepcopy


RUNTIME_SHA256 = '3b13c8c451db362fdd3fafa91832f3484dd9fd3eac0fcff792b82e9484a9131a'
BASE_RUNTIME_SHA256 = 'cee17449b6e9700af4642546477c06dbb42413888fa5e594ebded33014c5dbaf'

# Explicit admission set: future base-profile additions need their own review.
_BASE_OPS = set(('40 43 46 49 4C 4F 52 55 80 81 82 83 84 85 87 88 89 '
                 '8A 8B 8C 8D 8E 8F 90 91 92 93 94 95 96 97 98 99 '
                 '9A 9B 9C 9D 9E 9F A0 A2 A3 A4 A5 A6 A7 A9 AA AB '
                 'AC AE B0 B1 B3 B4 B5 B6 B7 B8 B9 BA BB BC BD BE BF '
                 'C0 C1 C2 C3 C4 C5 C6 C8 C9 CA CB CC CD CE CF D0 D1 '
                 'D2 D3 D4 D5 D6 D7 D8 D9 DA DB DC DD DE DF E0 E1 E2 '
                 'E3 E4 E5 E6 E7 E8 E9 EA EB EC F0 F3 F5 F7 F8 F9 '
                 'FA FB FC FD FE FF').split())
_BASE_SELECTORS = {'01', '03', '05', '06', '08', '0E', '0F', '10'}
_BASE_OPERANDS = {
    '40': 'i16le', '43': 'float6', '46': 'string8', '49': 'i16le',
    '4C': 'float6', '4F': 'string8', '52': 'u8', '55': 'u8',
    'A7': 'u16le', 'AC': 'u16be', 'CD': 'u16le', 'D1': 'u16le',
    'D2': 'u16le', 'D4': 'u8', 'E1': 'u16le', 'E2': 'branch_table8le',
    'F0': 'u16le', 'F3': 'u16le', 'FA': 'definition16le8',
    'FB': 'u16le', 'FC': 'u16le', 'FD': 'u8', 'FE': 'u8', 'FF': 'u8',
}
_BASE_MODIFIERS = dict(D6='input-store', D7='string-input-store',
                       D9='input-store', DA='input-store', DB='input-store',
                       DC='string-input-store')

# Native entry addresses for inherited forms.  These are not a global relocation
# delta: the shared extended-variable tail and final helpers move differently.
_ROOTS = dict(item.split(':') for item in (
    '40:0AEB 43:0B1D 46:0B66 49:0B04 4C:0B33 4F:0B8A 52:0B42 55:0B54 '
    '80:19A4 81:1AD4 82:1A9B 83:1B50 84:1BFE 85:1C2A 87:1A79 '
    '88:1B11 89:1BF5 8A:1414 8B:1214 8C:121D 8D:11A5 8E:0C7D '
    '8F:11BD 90:11EA 91:1DD0 92:1E39 93:120B 94:1202 95:1226 '
    '96:122F 97:1420 98:1D4A 99:1D4E 9A:1D52 9B:1D56 9C:1D41 '
    '9D:1D38 9E:13FC 9F:1F84 A0:1F84 A2:1FE2 A3:1FE2 A4:23E5 '
    'A5:201D A6:201D A7:2394 A9:1F24 AA:1EE4 AB:1408 AC:1098 '
    'AE:18BE B0:18D0 B1:1900 B3:142C B4:170A B5:16F3 B6:1725 '
    'B7:17B5 B8:1F6D B9:16E9 BA:175B BB:1747 BC:177F BD:1764 '
    'BE:176D BF:1776 C0:1788 C1:1791 C2:1811 C3:1CCF C4:1E93 '
    'C5:1CDD C6:1F58 C8:2364 C9:228E CA:2267 CB:0D5A CC:0C9B '
    'CD:0D97 CE:17C0 CF:0BBC D0:0C6D D1:12ED D2:12FC D3:236A '
    'D4:12CA D5:0EE7 D6:146D D7:15CC D8:1315 D9:163C DA:16A1 '
    'DB:183A DC:1855 DD:1E4E DE:1E6D DF:1F2E E0:1EEB E1:18A8 '
    'E2:133F E3:18A1 E4:186E E5:190D E6:191A E7:0C46 E8:179A '
    'E9:1927 EA:0C57 EB:16CE EC:0C40 F0:206A F3:20F8 F5:1395 '
    'F7:13DE F8:210E F9:20E0 FA:2370 FB:240F FC:21AF '
    'FD:246A FE:246A FF:246A').split())
_SECONDARY_ROOTS = dict(item.split(':') for item in
                        '01:195C 03:1958 05:2599 06:25BB 08:25EE 0E:2626 0F:263D 10:264C'.split())


def _rule(mnemonic: str, operand: str, comment: str, evidence: str) -> dict:
    return dict(mnemonic=mnemonic, operand=operand, control='fallthrough',
                comment=comment, evidence='Exact $2267 runtime: ' + evidence)


def build_profile(base_profile: dict) -> dict:
    """Return a deep, independent exact-$2267 profile from the canonical dict.

    Raises ValueError for a different base revision or unreviewed base grammar.
    No fallback hash, permissive mode, runtime bytes, or private files are used.
    """
    expected = dict(schema='petspeed-runtime-profile-v1',
                    runtimeSha256=BASE_RUNTIME_SHA256, entryBytes='4c4522',
                    loadAddress=0x0801, entryAddress=0x0819,
                    runtimeStart=0x0826, runtimeEnd=0x2800,
                    variableBase=0x2800, variableStride=8,
                    headerWords=dict(data=0x081C, arrays=0x081E,
                                     initialization=0x0820, codeCursor=0x0822,
                                     topCode=0x0824))
    if any(base_profile.get(k) != v for k, v in expected.items()):
        raise ValueError('variant_2267 requires the canonical base profile')
    ops = base_profile['opcodes']
    if (set(ops) != _BASE_OPS or
            set(ops['80']['selectors']) != _BASE_SELECTORS or
            any(rule.get('operand', 'none') != _BASE_OPERANDS.get(op, 'none') or
                rule.get('modifierTable') != _BASE_MODIFIERS.get(op)
                for op, rule in ops.items()) or
            any(rule.get('operand', 'none') != 'none'
                for rule in ops['80']['selectors'].values()) or
            [(f['first'], f['last'], f['operand']) for f in base_profile['families']]
            != [(0, 31, 'none'), (32, 63, 'none'), (96, 127, 'none')] or
            {name: set(table) for name, table in base_profile['modifierTables'].items()}
            != {'input-store': {'41', '42'}, 'string-input-store': {'41'}}):
        raise ValueError('variant_2267 requires the reviewed canonical grammar')
    p = deepcopy(base_profile)
    p.update(id='petspeed-c64-2267-3b13c8c4', entryBytes='4c6722',
             runtimeSha256=RUNTIME_SHA256,
             status='exact-runtime partial grammar; native-supported forms only')
    # Replace provenance, rather than copying application names or treating old
    # native addresses as addresses in this variant.  Semantics derive from the
    # bounded native pairing of the canonical subset plus the checks below.
    for op, spec in p['opcodes'].items():
        spec['evidence'] = (f'Exact $2267 runtime entry ${_ROOTS[op]}; '
                            'canonical-subset native pairing, with $10/$11 FAC/ARG tags; '
                            'static normal-path admission, not execution equivalence')
        if op == '80':
            for selector, rule in spec['selectors'].items():
                rule['evidence'] = (f'Exact $2267 secondary entry ${_SECONDARY_ROOTS[selector]}; '
                                    '$19A4/$1581 consume selector; canonical native pairing')
    for family, address in zip(p['families'], ('0999', '0955', '09D7')):
        family['evidence'] = f'Exact $2267 compact-family entry ${address}; unchanged eight-byte records'
    for table in p['modifierTables'].values():
        for rule in table.values():
            rule['evidence'] = ('Exact $2267 numeric corridor $1547 consumes 41/42; '
                                'string corridor $162B consumes only 41; $1581 advances cursor')
    p['opcodes']['AB']['comment'] = 'ARG := integer 0 ($6C/$6D := 0, $11 := 1); no inline operand'
    for op in ('D6', 'D7'):
        rule = p['opcodes'][op]
        rule['mnemonic'] += '_EMPTY_SKIP'
        rule['comment'] += ('; empty default-channel input skips the following form via $143C '
                            'instead of assigning (store modifier applies only on parsed-field path)')

    additions = {
        '86': _rule('POWER_REVERSED', 'none',
                    'FAC := old FAC ^ old ARG; exchange/conversion and arithmetic errors apply; ARG not preserved',
                    '$1CC5 exchanges via $1A2A then selects $1C30/$1C9B; no inline bytes'),
        'A1': _rule('ARRAY_PAIR_LOAD_FAC', 'none',
                    'load typed element using n=(FACword*descriptor.multiplier+ARGword) mod 65536; '
                    'selected descriptor type and native scaling carry apply; not a bounds-checked DIM expression',
                    '$21DF saves dispatch X=$42; descriptor at base-3; $2202 multiply, $222B add; '
                    '$223A selects load tails $1F84/$1FE2/$201D; no inline bytes'),
        'A8': _rule('ARRAY_PAIR_DEST', 'none',
                    'prepare element destination using n=(FACword*descriptor.multiplier+ARGword) mod 65536; '
                    'native wrap/scaling carry and valid selected descriptor required',
                    '$21DF with X=$50; shared multiply/add, $223A selects prepared $3D/$3E destination; no payload'),
        'AF': _rule('OPEN_SECONDARY', 'none',
                    'OPEN using FAC secondary address; pop device and logical file from runtime stack',
                    '$18C2 with X=$5E selects $18DF, two stack pops then $FFC0; no inline bytes'),
        'C7': _rule('CHR_STRING', 'none',
                    'FAC := one-character string from checked numeric FAC; conversion, allocation, and errors apply',
                    '$1EC0 calls $17DD checked conversion, writes character to $0100, sets $10=FF; '
                    '$1D90 allocates; $1ED5 fetches next opcode'),
        'ED': _rule('LOAD_ARG_PACKED_NUMBER_AT', 'u16le',
                    'load packed numeric record at ${value:04X} into ARG; nonzero exponent unpacks float, '
                    'zero exponent loads following integer high/low bytes; sets $11',
                    '$2089 via $21C8 address reader; nonzero exponent restores hidden mantissa bit; '
                    'zero exponent goes to integer path, not unconditional zero; total three bytes'),
        'EE': _rule('LOAD_ARG_INTEGER_AT', 'u16le',
                    'load high/low bytes at ${value:04X} into ARG $6C/$6D; $11 := 1',
                    '$2076 via $21C8, integer load tail; total three bytes'),
        'EF': _rule('LOAD_ARG_TRIPLE_AT_PRESERVE_TAG', 'u16le',
                    'sequentially load three bytes at ${value:04X} into ARG $6C..$6E; '
                    '$11 unchanged; not an unconditional typed string or atomic snapshot',
                    '$20B4 via $21C8; three sequential loads, no tag write; total three bytes'),
        'F1': _rule('LOAD_FAC_INTEGER_AT', 'u16le',
                    'load high/low bytes at ${value:04X} into FAC $64/$65; $10 := 1',
                    '$2064 via $21C8 then integer load; total three bytes'),
        'F2': _rule('LOAD_STRING_ELEMENT_AT', 'u16le',
                    'load descriptor at ${value:04X} into FAC $64..$66; $10 := FF; '
                    'valid descriptor and string ownership required',
                    '$2070 via $21C8 then string load tail; total three bytes'),
        'F4': _rule('STORE_INTEGER_ELEMENT_AT', 'u16le',
                    'convert/store FAC high/low word at ${value:04X}; $10 unchanged; '
                    'normal return and writable nonaliasing ordinary RAM required',
                    '$20CA via $21C8 -> $20E0; floating path calls $BC1B/$B1AA; '
                    'two stores then $0926; errors need not continue at P+3'),
    }
    p['opcodes'].update(additions)
    for op, role in (('FD', 'FAC'), ('FE', 'ARG'), ('FF', 'FAC')):
        rule = p['opcodes'][op]
        rule['variableIndex'] = dict(base=0x2900, stride=7, firstSlot=32)
        rule['comment'] = (f"{'store' if op == 'FF' else 'load'} {role} "
                           + ('in' if op == 'FF' else 'from')
                           + ' extended slot {slot} (${variable:04X}), record $2900+7*index; '
                           + ('honor destination type and managed-string rules, not a raw record copy'
                              if op == 'FF' else 'record[6]&FB supplies tag; rounding extension not reset'))
        rule['evidence'] = ('Exact $2267 $246A consumes one unsigned index; $2474/$248F compute '
                            '$2900+7*i; X=FA/FC/FE selects FAC $2429, ARG $2499, '
                            'or typed store $24DA with fixed/float/string paths; total two bytes')
    p['opcodes']['80']['selectors'].update({
        '0B': _rule('TIME_ARG', 'none',
                    'ARG := jiffy clock using runtime integer/float representation; '
                    'accumulator bodies temporarily exchanged and rounding extension cleared',
                    '$19D0 -> $25BB with X=$16; $1A4A body exchange; $AF84 clock read; '
                    '$25D1 selects ARG tag $11 and exchange back; selector only'),
        '0D': _rule('TIME_STRING_ARG_CLOBBER_FAC_TYPE', 'none',
                    'ARG := six-character clock string; FAC type $10 := FF; '
                    'collection may also alter saved accumulator bodies; not pure TI$',
                    '$19D4 -> $25EE with X=$1A; $1A4A exchanges bodies, $AF84/$BE68 '
                    'format clock; allocator $1D90 writes $10; $261E writes $11; selector only'),
    })
    p['variantEvidence'] = dict(
        workspaceTypeFlags=dict(FAC=0x10, ARG=0x11),
        basis='canonical-subset native pairing plus exact merged/direct/array/selector handler checks',
        newlyAdmittedOpcodes=sorted(additions), newlyAdmittedSelectors=['0B', '0D'],
        extendedRecord=dict(base=0x2900, stride=7, firstSlot=32),
        excludedExamples=['AD', 'B2', 'F6', '80/00', '80/04', '80/07', '80/0A'])
    p['limitations'] += [
        'Only the exact $2267 runtime fingerprint and JMP stub are admitted, not the PETSpeed family generally.',
        'FAC/ARG tags are $10/$11.  Native normal-return contracts assume valid VM/heap/stack state, '
        'binary arithmetic, stable mapping/stream, benign interrupts, and ordinary nonaliasing memory.',
        'Array pair forms use descriptor-based native wrap and carry, not recovered source dimensions or checked bounds.',
        'EF preserves ARG type; F4 preserves FAC type; FD/FE and float literals do not reset the rounding extension.',
        'INPUT_EMPTY_SKIP is not ordinary guaranteed assignment; contextual stores describe only parsed fields.',
        'Clock-string ARG loading clobbers FAC type; collection can alter accumulator bodies.',
        'Native static evidence and nine development byte partitions do not establish reachability, '
        'application correctness, original BASIC, or execution equivalence.',
    ]
    return p
