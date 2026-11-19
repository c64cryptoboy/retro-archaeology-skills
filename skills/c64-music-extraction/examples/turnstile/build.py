"""Build Turnstile only.  This is not a general BASIC tokenizer or SID writer."""
from pathlib import Path
import re
import struct
import sys


def build():
    # This listing uses no strings, comments, keyword-bearing DATA, or abbreviations.
    tokens = dict(FOR=0x81, NEXT=0x82, DATA=0x83, READ=0x87, GOTO=0x89,
                  IF=0x8b, RESTORE=0x8c, POKE=0x97, TO=0xa4, THEN=0xa7, PEEK=0xc2)
    tokens.update({"+": 0xaa, "=": 0xb2})
    program = bytearray()
    for line in Path(__file__).with_name("turnstile.bas").read_text("ascii").splitlines():
        number, body = line.split(" ", 1)
        encoded = bytearray()
        for part in re.findall(r"[A-Z]+|.", body):
            if part in tokens:
                encoded.append(tokens[part])
            elif re.fullmatch(r"[A-Z0-9 ,():]", part):
                encoded.extend(part.encode("ascii"))
            else:
                raise ValueError(f"unsupported source text: {part!r}")
        link = 0x0801 + len(program) + 5 + len(encoded)
        program.extend(struct.pack("<HH", link, int(number)) + encoded + b"\0")
    header = struct.pack(">4s7HI32s32s32sH4x", b"RSID", 2, 0x7c, 0, 0, 0, 2, 1, 0,
                         b"Turnstile", b"Original BASIC study", b"2026 MIT", 0x002a)
    return header + b"\x01\x08" + program + b"\0\0"


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python3 build.py OUTPUT.sid")
    Path(sys.argv[1]).write_bytes(build())
