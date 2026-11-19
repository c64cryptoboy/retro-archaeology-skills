"""Compile four authored BASIC inputs; compare saved bytes without executing them.

Usage: python3 check_pointer.py /path/to/microcompiler/python/mc.py
Python standard library only.  No fixture, tool, or clone is written in place.
"""
import hashlib
from pathlib import Path
import re
import subprocess
import sys
import tempfile


HOST_SHA = '947d6af598bebba5f1e8e26b3b9868db7d5866241835cad2520f8d93c9179ffa'
CASES = {
    'plain': ('POKE 16385,16905', 'END'),
    'inline': ('POKE 16385,PEEK(16905)', 'END'),
    'split': ('T=PEEK(16905)', 'POKE 16385,T', 'END'),
    'other_destination': ('POKE 17414,PEEK(16905)', 'END'),
}
TOKENS = {'POKE': 0x97, 'PEEK': 0xc2, '=': 0xb2, 'END': 0x80}


def fixture(lines):
    link = 0x0801
    word = lambda x: x.to_bytes(2, 'little')
    out = bytearray(word(link))
    for i, line in enumerate(lines, 1):
        body = bytes(TOKENS[s] if s in TOKENS else ord(s)
                     for s in re.findall(r'POKE|PEEK|END|.', line))
        link += 5 + len(body)
        out.extend(word(link) + word(10*i) + body + b'\x00')
    return bytes(out) + b'\x00\x00'


# Execute the exact pinned host source as a script, substituting two menu
# keystrokes for the optional keyboard device.  SYS SAVE writes a file on host.
DRIVER = '''
import builtins, hashlib, sys
from pathlib import Path
from types import SimpleNamespace as Obj
keys = iter(('1', '3'))   # Save, quit.  Never select run or recompile.
sys.modules['keyboard'] = Obj(KEY_UP='up', read_event=lambda _: Obj(event_type='up', name=next(keys)))
path, digest = sys.argv[1:]
source = Path(path).read_bytes()
if hashlib.sha256(source).hexdigest() != digest:
    raise SystemExit('unrecognized compiler hash')
exec(compile(source, path, 'exec'), {'__name__': '__main__', '__builtins__': builtins})
'''


def compile_one(host, statements):
    data = fixture(statements)
    with tempfile.TemporaryDirectory() as work:
        (Path(work) / 'input.prg').write_bytes(data)
        result = subprocess.run([sys.executable, '-I', '-B', '-c', DRIVER, str(host), HOST_SHA],
                                cwd=work, input='input.prg\n49152\nsaved.ml\n', text=True,
                                capture_output=True, timeout=10)
        if result.returncode or not re.search(r'\berrors\s+0\b', result.stdout, re.I):
            raise ValueError(result.stdout + result.stderr)
        return data, (Path(work) / 'saved.ml').read_bytes()


def expected():
    # Independent straight-line specification, including both pointer definitions.
    entry = '00 c0 4c 06 c0 4c 74 a4'  # prefix, entry JMP, bypassed helper slot
    p = 'a9 01 a2 40'  # $4001
    q = 'a9 09 a2 42'  # $4209
    r = 'a9 06 a2 44'  # $4406
    ptr = '85 22 86 23'
    peek = 'a2 00 a0 00 b1 22'  # zero-extended byte, indirect read with Y=0
    poke = 'a0 00 91 22'        # indirect write with Y=0
    save_t, load_t = '8d ce 02 8e cf 02', 'ad ce 02 ae cf 02'
    bodies = {'plain': [p, ptr, q, poke], 'inline': [p, ptr, q, ptr, peek, poke],
              'split': [q, ptr, peek, save_t, p, ptr, load_t, poke],
              'other_destination': [r, ptr, q, ptr, peek, poke]}
    return {k: bytes.fromhex(' '.join([entry, *parts, '60 00 00'])) for k, parts in bodies.items()}


def main(host):
    specs = expected()
    saved = {}
    for name, lines in CASES.items():
        src, obj = compile_one(host, lines)
        if obj != specs[name]:
            raise ValueError(f'{name}: expected {specs[name].hex(" ")}; got {obj.hex(" ")}')
        saved[name] = obj
        print(f'{name}: errors=0; {len(obj)} saved bytes; source={hashlib.sha256(src).hexdigest()}; saved={hashlib.sha256(obj).hexdigest()}')
        print(obj.hex(' '))
    diffs = [(i, a, b) for i, (a,b) in enumerate(zip(saved['inline'], saved['other_destination'])) if a != b]
    if diffs != [(9, 1, 6), (11, 0x40, 0x44)]:
        raise ValueError(f'unexpected original destination changes: {diffs}')
    print('PASS: four complete saved objects and the original-destination delta; no target execution.')


if __name__ == '__main__':
    main(Path(sys.argv[1]).resolve())
