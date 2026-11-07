"""Shared, deliberately conservative helpers for offline 6502-analysis scripts."""
import json
from pathlib import Path
from dis6502 import ops

BRANCHES = {'BPL', 'BMI', 'BVC', 'BVS', 'BCC', 'BCS', 'BNE', 'BEQ'}


def number(value):
    return int(value, 0)


def load_prg(path):
    blob = Path(path).read_bytes()
    if len(blob) < 3:
        raise ValueError('PRG needs a two-byte load address and at least one byte')
    return blob[0] | blob[1] << 8, bytearray(blob[2:])


def save_prg(path, base, memory):
    Path(path).write_bytes(bytes((base & 255, base >> 8)) + bytes(memory))


def decode(memory, base, pc):
    i = pc - base
    if not 0 <= i < len(memory): return None
    op = memory[i]
    if op not in ops: return {'pc': pc, 'opcode': op, 'invalid': True, 'length': 1}
    mnemonic, mode, length = ops[op]
    bs = memory[i:i + length]
    return {'pc': pc, 'opcode': op, 'mnemonic': mnemonic, 'mode': mode,
            'length': length, 'bytes': list(bs), 'truncated': len(bs) != length}


def operand_word(ins):
    return ins['bytes'][1] | ins['bytes'][2] << 8


def read_json(path):
    return json.loads(Path(path).read_text())


def dump(value):
    print(json.dumps(value, indent=2, sort_keys=True))
