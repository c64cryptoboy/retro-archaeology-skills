# Read-only Apple and Atari disk-image readers

These small readers make source and data files available for a game-mechanics audit without starting an emulator or altering the disk image.  They extract raw file bytes and structural metadata, not BASIC source listings.  Use them as an intake step, then route the extracted language or machine code to the appropriate analysis workflow.

## Supported boundary

| Tool | Supported input | Explicit exclusions |
|---|---|---|
| `tools/apple_dos33.py` | 143,360-byte Apple II DOS 3.3 image: 35 tracks, 16 sectors per track, 256 bytes per sector, in `.do` logical-sector order | Physical-sector-order images, ProDOS, 13-sector disks, nibble/flux images, protection decoding, and filesystem repair |
| `tools/atari_dos2.py` | ATR container with 128-byte sectors and DOS 2.0 allocation | 256-byte sectors, DOS 2.5 extended allocation, other DOS variants, protection decoding, and filesystem repair |

A filename extension does not establish the format.  Apple logical coordinates map directly to `(track * 16 + sector) * 256`; no additional physical skew is applied.  Atari container capacity is separate from filesystem allocation: extra physical sectors do not enlarge the DOS 2.0 allocation map.  Its bitmap covers sectors 0 through 719; sector 0 does not exist, and boot, VTOC, and directory sectors are not ordinary file-data sectors.

The Atari profile also requires at least 720 physical sectors, VTOC code 2, and initial allocation count 707.  Nonzero sector 1024 is conservatively refused as ambiguous DOS 2.5/VTOC2 evidence, not positively identified as DOS 2.5.  The manifest retains uninterpreted ATR header bytes, including nonzero header flags.

Neither tool executes extracted programs, detokenizes BASIC, repairs bad links, recovers deleted files, or certifies that an apparently intact file is a complete or correct game implementation.  Keep deleted entries, malformed chains, and unsupported variants separate from trustworthy source evidence.  Do not substitute reconstructed or padded bytes silently for missing evidence.

## Run from this skill directory

Requirements: Python 3.10 or later, with only its standard library.  Keep all three files in `tools/` together.  No Pi extension, emulator, network access, or private workspace is required.

```sh
python3 tools/apple_dos33.py /path/to/disk.do /path/to/new-apple-output
```

```sh
python3 tools/atari_dos2.py /path/to/disk.atr /path/to/new-atari-output
```

Use `--expected-sha256` with a known 64-digit hexadecimal digest when the input identity must be pinned.  The output directory must not exist, its parent must already exist, and no output ancestor may be a symlink.  An existing output directory is refused even if empty.  Choose a new destination for each extraction rather than mixing runs.

The input is read only.  The CLI accepts regular files up to a 16 MiB safety limit; this resource bound is not a claim that additional disk formats are supported.  Pipes and device files are refused before reading.  Output names are generated from directory/catalog slots rather than disk-supplied filenames, so duplicate, hostile, or nonportable on-disk names cannot select host paths.  Original name bytes remain metadata.  Each run writes `manifest.json`, including the input's name, byte count, and SHA-256, plus an artifact inventory with byte counts and SHA-256 hashes.  These hashes establish byte identity, not semantic validity.

Always inspect the manifest's structural diagnostics before admitting an extracted file to an audit.  A successful CLI exit means the extraction packet was written, not that every file is intact.  Unsupported containers and fatal parse failures exit nonzero without creating output.  An I/O failure during writing can leave a partial packet; preserve it as a failed run, and use a fresh destination after resolving the cause.  The fresh-directory checks prevent accidental overwrite and preexisting symlink redirection; they are not a sandbox against another process changing paths concurrently.

## Reading the packet

- **Apple:** `files` lists active catalog slots; raw catalog sectors retain the surrounding evidence.  `data_sectors` records each observed sector's logical file position.  Gaps, duplicate logical slots, and broken allocation chains suppress assembled file artifacts.  `allocated.bin` means contiguous observed allocation, not verified application content.  A/I/B length headers split in-bounds allocations into `header.bin`, `payload.bin`, and `slack.bin`; text and unsupported types have no invented logical payload.  Read the top-level `issues`, including overlaps and allocation-count mismatches, even when a bounded payload exists.
- **Atari:** `entries` retains all 64 directory slots.  `allocated.bin` contains observed chain sectors, `observed-payload.bin` contains the bytes admitted by their used-byte counts, `slack.bin` retains unused data capacity, and `trailers.bin` retains link/owner/count bytes.  Only issue-free file entries receive `payload.bin`; read both per-entry and global `issues`.  Extra physical sectors and unowned allocated sectors remain separate evidence, not recovered files.  Short nonfinal sectors are accepted when their boundaries and links are otherwise valid.

## Tests and integration

Run the synthetic tests from any checkout of the skill:

```sh
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

The tests construct artificial disk structures; no commercial game disk is included or required.  Output-path tests require a symlink-capable filesystem and permission to create symlinks; the FIFO probe is POSIX-only.  They cover declared format boundaries, malformed chains, identity and output-path handling, and regression cases that previously produced misleading extraction results.  Do not weaken structural checks because one title's damaged file fails them.

For a small Python integration, each reader exposes `read_image(data: bytes) -> tuple[dict, dict[str, bytes]]`.  It returns a JSON-compatible manifest and a mapping from safe relative artifact paths to bytes, without filesystem writes.  The shared `extract_image(reader, input_path, output_path, *, expected_sha256=None) -> dict` adds the read-only input and fresh-output contract.  Keep reader-specific metadata with the extracted bytes when handing them to another tool.

## Provenance

The readers are newly authored tools; no third-party implementation, BASIC token table, commercial image, or extracted game payload is bundled.  Format references are credited separately from implementation licensing:

- Apple II DOS and ProDOS Mini-Manual, [questions 20 and 21](https://mirrors.apple2.org.za/apple.cabi.net/FAQs.and.INFO/A2.CSA2.FAQS.IN.HTML/apple.II.dos.and.prodos.mi.html).  The consulted format excerpt is a secondary reference with no license statement in the saved excerpt; this package does not claim it is public domain or reproduce its prose.
- Joseph H. Allen's Atari Disk Tools [format documentation](https://github.com/jhallen/atari-tools/blob/835d5a6fc1258921949fe92400adb789c398b9c3/readme.md#atr-header-format) and [`atr.c`](https://github.com/jhallen/atari-tools/blob/835d5a6fc1258921949fe92400adb789c398b9c3/atr.c), revision `835d5a6fc1258921949fe92400adb789c398b9c3`.  The source is copyright 2011 Joseph H. Allen and GPL-1.0-or-later; it was consulted as a format reference, not bundled or copied as the implementation.  Its ATR description credits Nick Kennedy's SIO2PC documentation, originally linked at <http://pages.suddenlink.net/wa5bdu/readme.txt>.
- The Atari documentation cites [Inside Atari DOS, chapter 2](http://www.atariarchives.org/iad/chapter2.php) for short sectors, including short nonfinal sectors.  A short sector alone is not proof of corruption.

Reference materials retain their own copyright and licensing status.  Consulting a format does not establish either code derivation or permission to redistribute a referenced implementation.  Token decoders and their reference materials are outside this reader package.
