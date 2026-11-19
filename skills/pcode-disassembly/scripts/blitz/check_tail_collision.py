"""Offline producer/origin check. Only newly authored BASIC is compiled; no PRG is run."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory


PINNED_JS_SHA256 = '11773b01342bbe56d780f1b8035f889a54756a87a9b16a04a42449ff6a78433a'


def one_line(body, suffix=b''):
    # Load address, next record link, line number 10, NUL, zero link, optional non-BASIC bytes.
    start = 0x0801
    return (start.to_bytes(2, 'little') + (start + 5 + len(body)).to_bytes(2, 'little')
            + b'\x0a\x00' + body + b'\x00\x00\x00' + suffix)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('producer', type=Path, help='pinned Reblitz64 docs/reblitz64.js')
    ap.add_argument('reader', type=Path, help='pcode-disassembly scripts/reconstruct/reconstruct.py')
    args = ap.parse_args()
    producer, reader = args.producer.resolve(), args.reader.resolve()
    require(hashlib.sha256(producer.read_bytes()).hexdigest() == PINNED_JS_SHA256, 'wrong producer')
    base = b'A\xb20'  # A=0
    stmt = base + b':\x80:\x997'  # :END:PRINT7
    trailer = bytes.fromhex('b7 3e 4f')  # literal 7, PRINT, END
    sources = {'statements': one_line(stmt), 'opaque': one_line(base, trailer),
               'no_tail': one_line(base), 'changed_tail': one_line(base, b'\xb8' + trailer[1:])}
    with TemporaryDirectory() as td:
        d = Path(td)
        objects = {}
        for name, content in sources.items():
            src, obj = d / (name + '.src'), d / (name + '.prg')
            src.write_bytes(content)
            log = subprocess.run(['node', producer, src, obj], cwd=d, check=True,
                                 capture_output=True, text=True, timeout=15).stdout
            require(('Copying 3 bytes trailing' in log) == (name in {'opaque', 'changed_tail'}),
                    f'{name}: unexpected producer copy report')
            objects[name] = obj.read_bytes()
        require(objects['statements'] == objects['opaque'], 'distinct origins did not collide')
        require(len(objects['opaque']) == len(objects['no_tail']) + 3, 'tail was not retained')
        a, b = objects['opaque'], objects['changed_tail']
        require(len(a) == len(b), 'one-byte replacement changed extent')
        diff = [i for i in range(len(a)) if a[i] != b[i]]
        require(len(diff) == 1 and a[diff[0]:diff[0]+3] == trailer and b[diff[0]] == 0xb8,
                'expected only the literal byte to change')
        for name, expected in [('opaque', ['END', 'PRINT 7', 'END']), ('no_tail', ['A = 0', 'END']),
                               ('changed_tail', ['END', 'PRINT 8', 'END'])]:
            report = d / (name + '.json')
            subprocess.run([sys.executable, '-B', reader, d / (name + '.prg'), '--json-output', report],
                           cwd=d, stdout=subprocess.DEVNULL, check=True, timeout=15,
                           env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
            j = json.loads(report.read_text())
            main_text = [g['text'] for g in j['groups'] if all(i['region'] == 'main' for i in g['instructions'])]
            require(main_text[-len(expected):] == expected, f'{name}: unexpected headings {main_text}')
            print(f'{name}: {main_text}')
        print(f'PASS: different source files, identical {len(a)}-byte objects; SHA-256 {hashlib.sha256(a).hexdigest()}')
        print(f'Changing the opaque literal changes only file offset ${diff[0]:04X}.')


if __name__ == '__main__':
    main()
