"""Compile three authored inputs and inspect the saved files; no 6502 execution.

Run from a writable directory: python3 -B check_successors.py /path/to/mc.py
"""
import hashlib
from pathlib import Path
import re
import subprocess
import sys
import tempfile

PIN = '947d6af598bebba5f1e8e26b3b9868db7d5866241835cad2520f8d93c9179ffa'
CASES = {
    'if_jump': ('I=258', 'IF I>258 THEN GOTO 40', 'A=1', 'END'),
    'for': ('FOR I=258 TO 258', 'A=1', 'NEXT I', 'END'),
    'if_store': ('I=258', 'IF I>258 THEN A=2', 'A=1', 'END'),
}
TOK = dict(zip(('END','FOR','NEXT','GOTO','IF','TO','THEN','>','='),
               (128,129,130,137,139,164,167,177,178)))

def tokenized(lines):
    word = lambda n: n.to_bytes(2, 'little')
    link = 0x0801
    out = bytearray(word(link))
    for number, line in enumerate(lines, 1):
        body = bytes(TOK[t] if t in TOK else ord(t)
                     for t in re.findall('|'.join(TOK) + '|.', line))
        link += 5 + len(body)
        out += word(link) + word(number * 10) + body + b'\x00'
    return out + b'\x00\x00'

DRIVER = '''
import builtins, hashlib, sys
from pathlib import Path
from types import SimpleNamespace as Obj
path, pin = sys.argv[1:]
source = Path(path).read_bytes()
if hashlib.sha256(source).hexdigest() != pin:
    raise SystemExit('unrecognized compiler hash')
keys = iter(('1', '3'))  # Save then quit.
sys.modules['keyboard'] = Obj(KEY_UP='up', read_event=lambda _: Obj(event_type='up', name=next(keys)))
exec(compile(source, path, 'exec'), {'__name__': '__main__', '__builtins__': builtins})
'''

def compile_case(host, lines):
    with tempfile.TemporaryDirectory(dir='.') as tmp:
        work = Path(tmp)
        data = tokenized(lines)
        (work / 'input.prg').write_bytes(data)
        result = subprocess.run([sys.executable, '-I', '-B', '-c', DRIVER, str(host), PIN],
                                input='input.prg\n49152\nsaved.ml\n', cwd=work,
                                capture_output=True, text=True, timeout=10)
        if result.returncode or not re.search(r'\berrors\s+0\b', result.stdout, re.I):
            raise ValueError(result.stdout + result.stderr)
        return data, (work / 'saved.ml').read_bytes()

def verify(objects):
    # Native addresses, not file offsets.  Specify destinations independently
    # of the generator's offset calculations.  Only read the supplied bytes.
    def at(pc, size):
        off = 2 + pc - 0xc000
        return obj[off:off+size]

    def expect(pc, hex_bytes):
        expected = bytes.fromhex(hex_bytes)
        if at(pc, len(expected)) != expected:
            raise ValueError(f'{name}: wrong code at ${pc:04x}, expected {hex_bytes}')

    def jump(pc, dest):
        expect(pc, '4c ' + dest.to_bytes(2, 'little').hex(' '))

    def branch(pc, opcode, dest):
        expect(pc, opcode)
        target = pc + 2 + int.from_bytes(at(pc+1, 1), 'little', signed=True)
        if target != dest:
            raise ValueError(f'{name}: branch at ${pc:04x} reaches ${target:04x}, not ${dest:04x}')

    for name, obj in objects.items():
        if obj[:2] != bytes.fromhex('00 c0'):
            raise ValueError('wrong load address')
        jump(0xc000, 0xc006)
        expect(0xc006, 'a9 02 a2 01')
        loop = name == 'for'
        head = 0xc00d if loop else 0xc010
        cmp_lo = head + 22
        expect(head, 'ad b8 02 ae b9 02 85 22 86 23 a9 02 a2 01 e4 23')
        branch(head+16, 'f0', cmp_lo)
        expect(cmp_lo, 'c5 22')
        store_i = '8d b8 02 8e b9 02'
        body = 'a9 01 a2 00 8d a8 02 8e a9 02'
        if loop:
            jump(0xc00a, 0xc03b)  # first entry skips comparison and update
            branch(head+18, 'b0', 0xc02c)
            branch(head+20, '90', 0xc029)
            branch(cmp_lo+2, 'f0', 0xc029)
            branch(cmp_lo+4, 'b0', 0xc02c)
            jump(0xc029, 0xc04e)
            expect(0xc02c, 'a9 01 a2 00 18 6d b8 02 a8 8a 6d b9 02 aa 98')
            expect(0xc03b, store_i)
            expect(0xc041, body)
            jump(0xc04b, head)  # NEXT returns to the test, not initialization
            expect(0xc04e, '60')
        else:
            next_line = 0xc02f if name == 'if_jump' else 0xc036
            expect(0xc00a, store_i)
            branch(head+18, 'b0', next_line)
            branch(head+20, '90', 0xc02c)
            branch(cmp_lo+2, 'b0', next_line)
            branch(cmp_lo+4, 'f0', next_line)
            if name == 'if_jump':
                jump(0xc02c, 0xc039)
            else:
                expect(0xc02c, 'a9 02 a2 00 8d a8 02 8e a9 02')
            expect(next_line, body)
            expect(next_line+10, '60')


def check_prefix(objects):
    def fragment(name, native_offset):
        return objects[name][2+native_offset:2+native_offset+24]
    i, f, s = fragment('if_jump', 16), fragment('for', 13), fragment('if_store', 16)
    if i != f or [j for j, (x,y) in enumerate(zip(i,s)) if x != y] != [19]:
        raise ValueError('wrong common prefix or IF displacement delta')


if __name__ == '__main__':
    objects = {}
    for name, lines in CASES.items():
        data, obj = compile_case(Path(sys.argv[1]).resolve(), lines)
        print(f'{name}: errors=0, {len(obj)} bytes, input={hashlib.sha256(data).hexdigest()}, saved={hashlib.sha256(obj).hexdigest()}')
        objects[name] = obj
        print(obj.hex(' '))
    verify(objects)
    check_prefix(objects)
    # A faulty NEXT that jumps to initialization still passes the prefix check.
    corrupt = bytearray(objects['for'])
    corrupt[2+0x4c] = 0x06
    changed = dict(objects, **{'for': bytes(corrupt)})
    check_prefix(changed)
    try:
        verify(changed)
    except ValueError as exc:
        if 'wrong code at $c04b' not in str(exc):
            raise
    else:
        raise ValueError('failed to reject wrong NEXT target')
    print('PASS: all three successor maps, 24-byte match, layout control, and rejected wrong back edge.')
