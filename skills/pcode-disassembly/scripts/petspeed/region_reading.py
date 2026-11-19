#!/usr/bin/env python3
"""Local BASIC idioms for the classic PETSpeed interval decoder (not executable source).

Only the binary + an explicitly supplied code interval enter the CLI.  Folds describe
straight-line execution from their first instruction, not all possible entry states.
"""
import argparse
from pathlib import Path

if __package__:
    from .petspeed_region import disassemble_region
else:
    from petspeed_region import disassemble_region


def string_literal(hex_bytes):
    """Render PETSCII conservatively; do not substitute an ASCII glyph for $60."""
    data = bytes.fromhex(hex_bytes)
    parts, run = [], ''
    for b in data:
        if 32 <= b <= 90 and b != 34:
            run += chr(b)
        else:
            if run:
                parts.append('"' + run + '"')
                run = ''
            parts.append(f'CHR$({b})')
    if run or not parts:
        parts.append('"' + run + '"')
    return ' + '.join(parts)


FAC = {'LOAD_FAC_VAR', 'LOAD_FAC_EXT_VAR'}
ARG = {'LOAD_ARG_VAR', 'LOAD_ARG_EXT_VAR'}
STORE = {'STORE_FAC_VAR', 'STORE_FAC_EXT_VAR'}


def _candidate(rows, names):
    def match(*pattern):
        return len(names) >= len(pattern) and all(n in p if isinstance(p, set) else n == p
                                                   for n, p in zip(names, pattern))

    def operand(i, key):
        return rows[i]['operands'][key]

    def var(i, string=False, key='variable'):
        return f'V_{operand(i, key):04X}' + ('$' if string else '')

    def literal(i):
        return string_literal(operand(i, 'stringHex'))

    def target(i):
        return f'L_{operand(i, "target"):04X}'

    if match('CONST_U8_FAC', 'SELECT_INPUT_FILE', 'GET_STRING', STORE, 'GET_STRING', STORE, 'RESTORE_CHANNELS') and operand(0, 'value') > 0:
        return 7, f'GET#{operand(0, "value")}, {var(3, True)}, {var(5, True)}', 'one channel selection; first GET and store precede second GET and store; then restore'
    if match('CONST_U8_FAC', 'SELECT_OUTPUT_FILE', FAC, 'PEEK', 'CHR_STRING', 'PRINT_STRING', 'RESTORE_CHANNELS') and operand(0, 'value') > 0:
        return (7, f'PRINT#{operand(0, "value")}, CHR$(PEEK({var(2)}));',
                'select file first; one PEEK at the numeric address, then CHR$ allocation, print without added newline, and restore on success')
    for verb, op, string in [('INPUT', 'INPUT_NUMBER', False), ('GET', 'GET_STRING', True)]:
        read = ('INPUT_BEGIN', op) if verb == 'INPUT' else (op,)
        pattern = ('CONST_U8_FAC', 'SELECT_INPUT_FILE', *read, STORE, 'RESTORE_CHANNELS')
        if match(*pattern) and operand(0, 'value') > 0:
            return len(pattern), f'{verb}#{operand(0, "value")}, {var(len(pattern)-2, string)}', 'single field; store precedes channel restore'
    if match(FAC, 'FOR_LIMIT', 'ZERO_FAC', 'FOR_ENTER') and operand(0, 'variable') != operand(3, 'value'):
        return 4, f'FOR {var(3, key="value")} = 0 TO {var(0)}', 'limit captured before zero initialization; frame must be established'
    if match(FAC | {'CONST_STRING_FAC'}, ARG, 'STRING_EQUAL', 'SKIP_IF_FALSE'):
        right = literal(0) if names[0] == 'CONST_STRING_FAC' else var(0, True)
        left = var(1, True)
        # The guarded fallthrough arm can be folded only if false skips precisely that arm.
        if match(names[0], ARG, 'STRING_EQUAL', 'SKIP_IF_FALSE', 'GOTO'):
            if operand(3, 'target') == rows[4]['address'] + rows[4]['size']:
                return 5, f'IF {left} = {right} THEN GOTO {target(4)}', 'raw string comparison'
        if (match('CONST_STRING_FAC', ARG, 'STRING_EQUAL', 'SKIP_IF_FALSE', 'ZERO_FAC', 'CHR_STRING', STORE)
                and operand(0, 'stringHex') == '' and operand(1, 'variable') == operand(6, 'variable')
                and operand(3, 'target') == rows[6]['address'] + rows[6]['size']):
            return 7, f'IF {left} = "" THEN {left} = CHR$(0)', 'allocate and store a one-byte NUL only on empty-string fallthrough; not an EOF test'
        if match(names[0], ARG, 'STRING_EQUAL', 'SKIP_IF_FALSE', 'CONST_STRING_FAC', STORE):
            if operand(3, 'target') == rows[5]['address'] + rows[5]['size']:
                return 6, f'IF {left} = {right} THEN {var(5, True)} = {literal(4)}', 'fresh string comparison before the assignment'
        return 4, f'IF {left} <> {right} THEN GOTO {target(3)}', 'zero test of string equality'
    if match('CONST_STRING_FAC', STORE):
        return 2, f'{var(1, True)} = {literal(0)}', 'typed scalar store'
    if match(FAC, ARG, 'CONCAT', STORE):
        return 4, f'{var(3, True)} = {var(1, True)} + {var(0, True)}', 'ARG followed by FAC'
    if match('ARRAY_BASE', FAC, 'STRING_ARRAY_DEST', 'LOAD_FAC_EXT_VAR', 'STORE_ELEMENT'):
        assignment = f'AR_{operand(0, "value"):04X}$({var(1)}) = {var(3, True)}'
        return 5, 'REM string path: ' + assignment, ('index/destination prepared before RHS load; a fresh negative FAC tag selects the descriptor path. '
                                                     'Assignment describes ordinary successful completion, not an atomic store or a guarantee of RHS type.')
    if (match(FAC, 'ASC', 'PUSH_FAC', FAC, 'ASC', 'CONST_I16_ARG', 'MULTIPLY', 'POP_ARG', 'ADD', STORE)
            and operand(5, 'value') == 256):
        return (10, f'{var(9)} = ASC({var(0, True)}) + ASC({var(3, True)}) * 256',
                'evaluate and save first ASC before second ASC; byte values, exact unsigned sum before typed destination conversion; no empty-string or I/O guarantee')
    if match('GOTO'):
        return 1, 'GOTO ' + target(0), 'encoded jump'
    if match('GOSUB'):
        return 1, 'GOSUB ' + target(0), 'encoded call; return is frame-dependent'
    if match('NEXT') or match('RETURN'):
        return 1, names[0], 'runtime-managed destination, not inferred here'
    return None


def reading_groups(region):
    """Project canonical rows.  Preserve every row, and never hide a known branch entry."""
    if region.get('schema') != 'petspeed-region-v1' or not region['completeIntervalDecode']:
        raise ValueError('a complete classic PETSpeed interval is required')
    rows = region['instructions']
    targets = {e['target'] for e in region['encodedTargets']}
    groups = []
    pos = 0
    while pos < len(rows):
        window = rows[pos:pos+10]
        # Do not include any instruction after an interior alternate entry, even
        # if the same opcode sequence at a single-entry site would be readable.
        for j in range(1, len(window)):
            if window[j]['address'] in targets:
                window = window[:j]
                break
        hit = _candidate(window, [r['mnemonic'] for r in window])
        if hit is None:
            count, statement, note = 1, 'REM VM ' + window[0]['mnemonic'], window[0]['comment']
        else:
            count, statement, note = hit
        groups.append({'address': window[0]['address'], 'text': statement, 'note': note,
                       'instructions': window[:count]})
        pos += count
    return groups


def render(region):
    lines = ['BASIC-like straight-line reading from a supplied interval; not executable or recovered source.',
             'Labels are addresses. V_ names are storage aliases; $ marks string context. External entry, file success, and frame state are not established.',
             'A folded statement describes entry at its first instruction; byte addresses and qualifications follow each statement.']
    for group in reading_groups(region):
        lines.append(f'L_{group["address"]:04X}: {group["text"]}')
        raw = ' '.join(r['bytes'] for r in group['instructions'])
        lines.append(f'        ; {raw.upper()}  {group["note"]}')
    return '\n'.join(lines) + '\n'


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('program', type=Path)
    p.add_argument('--start', type=lambda s: int(s, 0), required=True)
    p.add_argument('--stop', type=lambda s: int(s, 0), required=True, help='exclusive stop')
    args = p.parse_args()
    try:
        print(render(disassemble_region(args.program.read_bytes(), args.start, args.stop)), end='')
    except (OSError, ValueError) as exc:
        p.exit(2, f'REFUSED: {exc}\n')


if __name__ == '__main__':
    main()
