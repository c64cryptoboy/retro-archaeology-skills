# Stock ROM manifest

The four pinned ROM images below are **not bundled**.  Supply matching files under `assets/roms/` in the skill directory, or use `C64_ROM_DIR` for an external location.  Their original rights and licensing uncertainty are documented in [SOURCES.md](SOURCES.md); the repository license does not relicense them.  If explicitly run by the user, `scripts/download-roms.py` acquires these revisions and hash-checks each downloaded part and the final image before atomic installation.  Verification does not download missing files.

## C64 BASIC

- Local file: `basic.bin`
- Revision: `901226-01`
- CPU range: `$A000-$BFFF`
- Size: 8 KiB
- SHA-256: `89878cea0a268734696de11c4bae593eaaa506465d2029d619c0e0cbccdfa62d`
- Source: `http://www.zimmers.net/anonftp/pub/cbm/firmware/computers/c64/basic.901226-01.bin`
- Note: C64 BASIC's functional implementation continues into KERNAL through `$E39F`.

## C64 KERNAL

- Local file: `kernal.bin`
- Revision: `901227-03`
- CPU range: `$E000-$FFFF`
- Size: 8 KiB
- SHA-256: `83c60d47047d7beab8e5b7bf6f67f80daa088b7a6a27de0d7e016f6484042721`
- Source: `http://www.zimmers.net/anonftp/pub/cbm/firmware/computers/c64/kernal.901227-03.bin`
- Note: revision 3 is the common final C64 KERNAL revision.

## C64 character generator

- Local file: `chargen.bin`
- Revision: `901225-01`
- CPU range: `$D000-$DFFF` when mapped
- Size: 4 KiB
- SHA-256: `fd0d53b8480e86163ac98998976c72cc58d5dd8eb824ed7b829774e74213b420`
- Source: `http://www.zimmers.net/anonftp/pub/cbm/firmware/computers/c64/characters.901225-01.bin`
- Note: standard North American C64 character-generator ROM.

## 1541 DOS

- Local file: `dos1541.bin`
- Revision: `325302-01+901229-05`
- CPU range: `$C000-$FFFF`
- Size: 16 KiB
- SHA-256: `d1d45afb46fd4e2b48d93ca367b889d75654a3b7acf73044e51f6d880c09369e`
- Source parts, concatenated in address order:
  1. `$C000-$DFFF`: `http://www.zimmers.net/anonftp/pub/cbm/firmware/drives/new/1541/1541-c000.325302-01.bin`, 8 KiB, SHA-256 `6fa7b07aff92da66b0a28a52bb3c82ffe310ab0fad2cc473b40137a8d299c7e5`
  2. `$E000-$FFFF`: `http://www.zimmers.net/anonftp/pub/cbm/firmware/drives/new/1541/1541-e000.901229-05.bin`, 8 KiB, SHA-256 `f973fe75aa79efc863a2f24e3bf7a90dba802a2049a32283182c2924a3d45935`

The supplied `$C000` URL is only the lower 8 KiB half. The complete pinned 1541 image requires the matching `$E000` half; the downloader verifies both before joining them.
