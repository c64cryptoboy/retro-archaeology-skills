#!/usr/bin/env python3
"""Construct synthetic bytes and assertions, without assembling or executing a target."""
import argparse
import hashlib
import json
from pathlib import Path

BASE = 0x1000
START = 0x1040
# Source correspondence is in synthetic-consumers.asm.  Never executed by this lane.
VM_CONSUMER = bytes.fromhex(
    'a000 b1f0 e6f0 d002 e6f1 60 200010 c900 f01d c901 f005 c902 f007 00 '
    '200010 4c0b10 200010 aa 200010 85f1 86f0 4c0b10 60')
THREAD_CONSUMER = bytes.fromhex(
    'a000 b1f0 85f2 c8 b1f0 85f3 18 a5f0 6902 85f0 9002 e6f1 6cf200')
THREAD_CONSUMER += bytes(0x20 - len(THREAD_CONSUMER)) + bytes.fromhex('4c0010 00 60')
TABLE_CONSUMER = bytes.fromhex('a200 bd4010 95f2 e8 e004 d0f6 60')


def sha(blob):
    return hashlib.sha256(blob).hexdigest()


def example(kind='vm'):
    if kind == 'vm':
        consumer = VM_CONSUMER
        stream = bytes.fromhex('017f 024510 00')
        representation, width, operation = 'vm-opcodes', 1, 'dispatch'
        rules = [
            {'token': 0, 'operandBytes': 0, 'flow': 'stop', 'evidence': 'synthetic-consumers.asm: STOP returns'},
            {'token': 1, 'operandBytes': 1, 'flow': 'next', 'evidence': 'synthetic-consumers.asm: LITERAL fetches one byte'},
            {'token': 2, 'operandBytes': 2, 'flow': 'jump', 'targetOffset': 0,
             'evidence': 'synthetic-consumers.asm: JUMP fetches low/high absolute cursor'},
        ]
        entry = 0x100B
    else:
        consumer = THREAD_CONSUMER if kind == 'thread' else TABLE_CONSUMER
        stream = bytes.fromhex('2010 2410')
        representation, width = 'threaded-cells', 2
        operation = 'dispatch' if kind == 'thread' else 'data-read'
        rules = [
            {'token': 0x1020, 'operandBytes': 0, 'flow': 'next', 'evidence': 'synthetic-consumers.asm: cell $1020 returns to dispatch'},
            {'token': 0x1024, 'operandBytes': 0, 'flow': 'stop', 'evidence': 'synthetic-consumers.asm: cell $1024 returns to caller'},
        ]
        entry = BASE
    data = consumer + bytes(START - BASE - len(consumer)) + stream
    worksheet = {
        'schema': 'regional-consumer-worksheet-v1',
        'input': {'format': 'raw', 'base': BASE, 'sha256': sha(data), 'cpu': '6502',
                  'mappingEvidence': 'Synthetic flat memory; cursor precondition $F0/$F1=$1040 is supplied, not observed.'},
        'region': {'start': START, 'end': BASE + len(data), 'entries': [START],
                   'evidence': 'Synthetic stream byte range constructed by synthetic_fixture.py.',
                   'roleEvidence': 'Supplied synthetic application stream, not a historical artifact.'},
        'componentPins': [],
        'consumer': {'start': BASE, 'end': BASE + len(consumer), 'sha256': sha(consumer),
                     'operation': operation, 'representation': representation,
                     'nativeEntries': [entry],
                     'evidence': 'Supplied correspondence to synthetic-consumers.asm; the tool does not prove the semantics.',
                     'reachabilityEvidence': None,
                     'contract': {'tokenBytes': width, 'byteOrder': 'little', 'rules': rules}},
    }
    return data, worksheet


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    args.directory.mkdir(parents=True, exist_ok=True)
    for kind in ('vm', 'thread', 'table'):
        data, worksheet = example(kind)
        with (args.directory / (kind + '.bin')).open('xb') as output:
            output.write(data)
        with (args.directory / (kind + '.json')).open('x') as output:
            output.write(json.dumps(worksheet, indent=2) + '\n')


if __name__ == '__main__':
    main()
