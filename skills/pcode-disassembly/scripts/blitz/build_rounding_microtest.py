#!/usr/bin/env python3
"""Build a small BASIC V2/BLITZ numeric-boundary differential test."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

LOAD_ADDRESS = 0x0801

# Complete BASIC V2 token map keeps this builder standalone and inspectable.
TOKENS = {
    "END": 0x80, "FOR": 0x81, "NEXT": 0x82, "DATA": 0x83,
    "INPUT#": 0x84, "INPUT": 0x85, "DIM": 0x86, "READ": 0x87,
    "LET": 0x88, "GOTO": 0x89, "RUN": 0x8A, "IF": 0x8B,
    "RESTORE": 0x8C, "GOSUB": 0x8D, "RETURN": 0x8E, "REM": 0x8F,
    "STOP": 0x90, "ON": 0x91, "WAIT": 0x92, "LOAD": 0x93,
    "SAVE": 0x94, "VERIFY": 0x95, "DEF": 0x96, "POKE": 0x97,
    "PRINT#": 0x98, "PRINT": 0x99, "CONT": 0x9A, "LIST": 0x9B,
    "CLR": 0x9C, "CMD": 0x9D, "SYS": 0x9E, "OPEN": 0x9F,
    "CLOSE": 0xA0, "GET": 0xA1, "NEW": 0xA2, "TAB(": 0xA3,
    "TO": 0xA4, "FN": 0xA5, "SPC(": 0xA6, "THEN": 0xA7,
    "NOT": 0xA8, "STEP": 0xA9, "+": 0xAA, "-": 0xAB,
    "*": 0xAC, "/": 0xAD, "^": 0xAE, "AND": 0xAF,
    "OR": 0xB0, ">": 0xB1, "=": 0xB2, "<": 0xB3,
    "SGN": 0xB4, "INT": 0xB5, "ABS": 0xB6, "USR": 0xB7,
    "FRE": 0xB8, "POS": 0xB9, "SQR": 0xBA, "RND": 0xBB,
    "LOG": 0xBC, "EXP": 0xBD, "COS": 0xBE, "SIN": 0xBF,
    "TAN": 0xC0, "ATN": 0xC1, "PEEK": 0xC2, "LEN": 0xC3,
    "STR$": 0xC4, "VAL": 0xC5, "ASC": 0xC6, "CHR$": 0xC7,
    "LEFT$": 0xC8, "RIGHT$": 0xC9, "MID$": 0xCA,
}
TOKEN_CHOICES = sorted(TOKENS, key=len, reverse=True)

SOURCE_LINES = {
    10: 'PRINT"BLITZ ROUNDING TEST"',
    20: 'PRINT"HASH TEST"',
    30: 'FORI=1TO10:READA,B,E',
    40: 'Z%=401*(A*B/401-INT(A*B/401))',
    50: 'IFZ%<>ETHENPRINT"HASH FAIL ";A;B;Z%;E:END',
    60: 'NEXT:PRINT"HASH PASS"',
    70: 'PRINT"ARRAY TEST 10000"',
    80: 'DIML$(82)',
    90: 'FORI=1TO10000',
    100: 'X$=L$(82*RND(0)+1)',
    110: 'NEXT:PRINT"ARRAY PASS"',
    120: 'PRINT"POKE TEST 10000"',
    130: 'FORI=1TO10000',
    140: 'POKE49152,256*RND(0)',
    150: 'NEXT:PRINT"POKE PASS"',
    160: 'PRINT"ALL PASS":END',
    200: 'DATA72,69,156,87,69,389,73,78,79,84,65,246',
    210: 'DATA68,82,362,78,79,146,74,85,274,82,69,43',
    220: 'DATA65,84,246,83,84,154',
}


def tokenize(text: str) -> bytes:
    out = bytearray()
    i = 0
    quote = False
    literal_tail = False
    while i < len(text):
        if text[i] == '"':
            quote = not quote
            out.append(ord('"'))
            i += 1
            continue
        if not quote and not literal_tail:
            token = next((x for x in TOKEN_CHOICES if text.startswith(x, i)), None)
            if token is not None:
                out.append(TOKENS[token])
                i += len(token)
                if token in ("DATA", "REM"):
                    literal_tail = True
                continue
        out.append(ord(text[i]))
        i += 1
    return bytes(out)


def build_prg() -> bytes:
    address = LOAD_ADDRESS
    records = []
    for number, source in sorted(SOURCE_LINES.items()):
        body = tokenize(source)
        next_address = address + 2 + 2 + len(body) + 1
        records.append(
            next_address.to_bytes(2, 'little')
            + number.to_bytes(2, 'little')
            + body
            + b'\0'
        )
        address = next_address
    return LOAD_ADDRESS.to_bytes(2, 'little') + b''.join(records) + b'\0\0'


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--prg', type=Path, required=True)
    parser.add_argument('--listing', type=Path)
    args = parser.parse_args()

    prg = build_prg()
    args.prg.parent.mkdir(parents=True, exist_ok=True)
    args.prg.write_bytes(prg)
    if args.listing:
        args.listing.parent.mkdir(parents=True, exist_ok=True)
        args.listing.write_text(
            '\n'.join(f'{n} {s}' for n, s in sorted(SOURCE_LINES.items())) + '\n',
            encoding='ascii',
        )
    print(f'wrote {args.prg} ({len(prg)} bytes)')
    print(f'sha256 {hashlib.sha256(prg).hexdigest()}')


if __name__ == '__main__':
    main()
