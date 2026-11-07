#!/usr/bin/env python3
"""Pinned metadata for externally installed stock C64 and 1541 ROMs."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RomPart:
    url: str
    size: int
    sha256: str


@dataclass(frozen=True)
class Rom:
    filename: str
    base: int
    size: int
    sha256: str
    revision: str
    parts: tuple[RomPart, ...]


ROMS = {
    "basic": Rom(
        "basic.bin", 0xA000, 0x2000,
        "89878cea0a268734696de11c4bae593eaaa506465d2029d619c0e0cbccdfa62d",
        "901226-01",
        (RomPart(
            "http://www.zimmers.net/anonftp/pub/cbm/firmware/computers/c64/basic.901226-01.bin",
            0x2000,
            "89878cea0a268734696de11c4bae593eaaa506465d2029d619c0e0cbccdfa62d",
        ),),
    ),
    "kernal": Rom(
        "kernal.bin", 0xE000, 0x2000,
        "83c60d47047d7beab8e5b7bf6f67f80daa088b7a6a27de0d7e016f6484042721",
        "901227-03",
        (RomPart(
            "http://www.zimmers.net/anonftp/pub/cbm/firmware/computers/c64/kernal.901227-03.bin",
            0x2000,
            "83c60d47047d7beab8e5b7bf6f67f80daa088b7a6a27de0d7e016f6484042721",
        ),),
    ),
    "chargen": Rom(
        "chargen.bin", 0xD000, 0x1000,
        "fd0d53b8480e86163ac98998976c72cc58d5dd8eb824ed7b829774e74213b420",
        "901225-01",
        (RomPart(
            "http://www.zimmers.net/anonftp/pub/cbm/firmware/computers/c64/characters.901225-01.bin",
            0x1000,
            "fd0d53b8480e86163ac98998976c72cc58d5dd8eb824ed7b829774e74213b420",
        ),),
    ),
    "dos1541": Rom(
        "dos1541.bin", 0xC000, 0x4000,
        "d1d45afb46fd4e2b48d93ca367b889d75654a3b7acf73044e51f6d880c09369e",
        "325302-01+901229-05",
        (
            RomPart(
                "http://www.zimmers.net/anonftp/pub/cbm/firmware/drives/new/1541/1541-c000.325302-01.bin",
                0x2000,
                "6fa7b07aff92da66b0a28a52bb3c82ffe310ab0fad2cc473b40137a8d299c7e5",
            ),
            RomPart(
                "http://www.zimmers.net/anonftp/pub/cbm/firmware/drives/new/1541/1541-e000.901229-05.bin",
                0x2000,
                "f973fe75aa79efc863a2f24e3bf7a90dba802a2049a32283182c2924a3d45935",
            ),
        ),
    ),
}
