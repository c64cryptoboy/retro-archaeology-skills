#!/usr/bin/env python3
"""Build a conservative recursive 6502 control-flow graph from a PRG.

Only official opcodes in dis6502.py are decoded.  Targets outside the PRG are
reported but never decoded, so this tool does not guess at ROM or banked RAM.
"""
import argparse
import hashlib
import json
from collections import defaultdict, deque
from pathlib import Path

from dis6502 import ops, fmt, validate_extent

BRANCHES = {'BPL', 'BMI', 'BVC', 'BVS', 'BCC', 'BCS', 'BNE', 'BEQ'}
TERMINATORS = {'BRK', 'RTS', 'RTI'}
READS = {'LDA', 'LDX', 'LDY', 'CMP', 'CPX', 'CPY', 'ADC', 'SBC', 'AND', 'ORA', 'EOR', 'BIT'}
WRITES = {'STA', 'STX', 'STY', 'INC', 'DEC', 'ASL', 'LSR', 'ROL', 'ROR'}


def word(bs):
    return bs[1] | (bs[2] << 8)


def decode(mem, base, pc):
    offset = pc - base
    if not 0 <= offset < len(mem):
        return None
    opcode = mem[offset]
    if opcode not in ops:
        return {'pc': pc, 'bytes': [opcode], 'mnemonic': f'???${opcode:02X}',
                'mode': 'unknown', 'length': 1, 'invalid': True}
    mnemonic, mode, length = ops[opcode]
    bs = mem[offset:offset + length]
    if len(bs) != length:
        return {'pc': pc, 'bytes': list(bs), 'mnemonic': mnemonic, 'mode': mode,
                'length': length, 'truncated': True}
    return {'pc': pc, 'bytes': list(bs), 'mnemonic': mnemonic, 'mode': mode,
            'length': length, 'operand': fmt(mode, bs, pc)}


def target(ins):
    if ins['mode'] == 'rel':
        offset = ins['bytes'][1]
        return (ins['pc'] + 2 + (offset - 256 if offset >= 128 else offset)) & 0xffff
    if ins['mode'] == 'abs':
        return word(ins['bytes'])
    return None


def check_inline_jsr(mem, base, note):
    """Check the file identity and direct call, not the supplied return semantics."""
    digest = hashlib.sha256(base.to_bytes(2, 'little') + bytes(mem)).hexdigest()
    if note['sha256'].lower() != digest:
        raise ValueError('inline JSR conflict: SHA-256 does not match the complete PRG')
    offset = note['site'] - base
    if not (0 <= offset and offset + 4 <= len(mem)) or mem[offset] != 0x20:
        raise ValueError('inline JSR conflict: site must contain a complete JSR and argument byte')
    if word(mem[offset:offset + 3]) != note['callee']:
        raise ValueError('inline JSR conflict: encoded target does not match supplied callee')
    if not note['siteEvidence'].strip() or not note['calleeEvidence'].strip():
        raise ValueError('inline JSR requires site evidence and evidence for the adjusted return')
    return {**note, 'argument': note['site'] + 3, 'value': mem[offset + 3],
            'continuation': (note['site'] + 4) & 0xffff}


def analyze(mem, base, entries, maximum, *, inline_jsr=None):
    validate_extent(mem, base)
    end = base + len(mem)
    note = check_inline_jsr(mem, base, inline_jsr) if inline_jsr is not None else None
    queue = deque(entries)
    seen, instructions, edges = set(), {}, []
    data_xrefs, stops = defaultdict(list), []

    def add_edge(source, destination, kind):
        edges.append({'from': source, 'to': destination, 'kind': kind,
                      'internal': base <= destination < end})
        if base <= destination < end and destination not in seen:
            queue.append(destination)

    while queue and len(instructions) < maximum:
        pc = queue.popleft()
        while pc not in seen and base <= pc < end and len(instructions) < maximum:
            ins = decode(mem, base, pc)
            seen.add(pc)
            instructions[pc] = ins
            if ins.get('invalid') or ins.get('truncated'):
                stops.append({'at': pc, 'reason': 'invalid_or_truncated_opcode'})
                break
            mnemonic, mode = ins['mnemonic'], ins['mode']
            next_pc = (pc + ins['length']) & 0xffff

            # Record absolute operands as data xrefs except transfers, which are CFG edges.
            if mode in {'abs', 'abx', 'aby'} and mnemonic not in {'JSR', 'JMP'}:
                address = word(ins['bytes'])
                access = 'write' if mnemonic in WRITES else 'read' if mnemonic in READS else 'access'
                data_xrefs[address].append({'from': pc, 'kind': access, 'mnemonic': mnemonic})

            if mnemonic in BRANCHES:
                add_edge(pc, target(ins), 'branch')
                add_edge(pc, next_pc, 'fallthrough')
                break
            if mnemonic == 'JSR':
                add_edge(pc, target(ins), 'call')
                if note and pc == note['site']:
                    add_edge(pc, note['continuation'], 'analyst_supplied_continuation')
                else:
                    add_edge(pc, next_pc, 'fallthrough')
                break
            if mnemonic == 'JMP' and mode == 'abs':
                add_edge(pc, target(ins), 'jump')
                break
            if mnemonic == 'JMP' and mode == 'ind':
                stops.append({'at': pc, 'reason': 'unresolved_indirect_jump',
                              'pointer': word(ins['bytes'])})
                break
            if mnemonic in TERMINATORS:
                stops.append({'at': pc, 'reason': mnemonic.lower()})
                break
            if not base <= next_pc < end:
                stops.append({'at': pc, 'reason': 'falls_outside_prg'})
                break
            pc = next_pc

    result = {
        'loadAddress': base, 'endAddressExclusive': end,
        'entries': sorted(entries),
        'instructions': [instructions[pc] for pc in sorted(instructions)],
        'edges': edges,
        'dataXrefs': [{'address': address, 'references': refs}
                      for address, refs in sorted(data_xrefs.items())],
        'stops': stops,
        'limitReached': len(instructions) >= maximum,
    }

    if note:
        if note['site'] not in seen:
            raise ValueError('inline JSR not applied: site not reached within the analysis budget')
        arg = note['argument']
        # Include entry/edge evidence even when the instruction budget stopped decoding.
        note['codeConflict'] = (arg in result['entries'] or any(e['to'] == arg for e in edges)
                                or any(pc <= arg < pc + len(i['bytes']) for pc, i in instructions.items()))
        result['inlineJsr'] = note
    return result


def inline_jsr_summary(note):
    lines = [f"PRG SHA-256: {note['sha256']}",
             f"JSR ${note['site']:04X} to ${note['callee']:04X}; inline argument "
             f"${note['argument']:04X} = ${note['value']:02X}; analyst-supplied continuation "
             f"${note['continuation']:04X} (not observed execution).",
             f"Site evidence: {note['siteEvidence']}", f"Callee evidence: {note['calleeEvidence']}"]
    if note['codeConflict']:
        lines.append('Conflict: independent code evidence overlaps the inline argument; both interpretations retained.')
    return lines


def print_report(result):
    print(f"PRG ${result['loadAddress']:04X}-${result['endAddressExclusive'] - 1:04X}; "
          f"entries: {', '.join(f'${x:04X}' for x in result['entries'])}")
    print('\nReachable instructions:')
    for ins in result['instructions']:
        raw = bytes(ins['bytes']).hex(' ')
        suffix = ' ; INVALID/INCOMPLETE' if ins.get('invalid') or ins.get('truncated') else ''
        print(f"{ins['pc']:04X}: {raw:<8} {ins['mnemonic']:<6} {ins.get('operand', '')}{suffix}")
    print('\nControl-flow edges:')
    for edge in result['edges']:
        external = '' if edge['internal'] else ' (outside PRG)'
        print(f"${edge['from']:04X} -> ${edge['to']:04X}  {edge['kind']}{external}")
    if 'inlineJsr' in result:
        print('\nAnalyst-supplied inline JSR:')
        print('\n'.join(inline_jsr_summary(result['inlineJsr'])))
    if result['dataXrefs']:
        print('\nAbsolute data references:')
        for item in result['dataXrefs']:
            refs = ', '.join(f"${ref['from']:04X} {ref['mnemonic']} ({ref['kind']})" for ref in item['references'])
            print(f"${item['address']:04X}: {refs}")
    if result['stops']:
        print('\nStopped paths:')
        for stop in result['stops']:
            extra = f" (${stop['reason']})"
            if 'pointer' in stop:
                extra += f" pointer=${stop['pointer']:04X}"
            print(f"${stop['at']:04X}{extra}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('prg', type=Path, help='PRG including its two-byte load address')
    parser.add_argument('--entry', action='append', type=lambda v: int(v, 0),
                        help='entry address (repeatable; default is PRG load address)')
    parser.add_argument('--max-instructions', type=int, default=10000)
    parser.add_argument('--json', action='store_true', help='emit structured JSON')
    parser.add_argument('--inline-jsr', nargs=5, action='append',
                        metavar=('SHA256', 'SITE', 'CALLEE', 'SITE_EVIDENCE', 'CALLEE_EVIDENCE'),
                        help='one reviewed call consuming one inline byte; hash the complete PRG, '
                             'use 0x-prefixed hex addresses, and quote each evidence string')
    args = parser.parse_args()
    blob = args.prg.read_bytes()
    if len(blob) < 3:
        parser.error('PRG must include a two-byte load address and at least one byte')
    base = blob[0] | (blob[1] << 8)
    try:
        note = None
        if args.inline_jsr:
            if len(args.inline_jsr) != 1:
                parser.error('only one inline JSR contract is supported')
            sha, site, callee, site_evidence, callee_evidence = args.inline_jsr[0]
            note = dict(sha256=sha, site=int(site, 0), callee=int(callee, 0),
                        siteEvidence=site_evidence, calleeEvidence=callee_evidence)
        result = analyze(blob[2:], base, args.entry or [base], args.max_instructions, inline_jsr=note)
    except ValueError as exc:
        parser.error(str(exc))
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print_report(result)


if __name__ == '__main__':
    main()
