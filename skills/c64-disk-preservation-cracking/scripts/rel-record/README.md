# Numbered REL record lookup

Read one record without mounting the disk or extracting a file.  From this directory, with Python 3.9 or later:

```sh
python rel_lookup.py disk.d64 ACCOUNTS 7
python rel_lookup.py --hex-name disk.d64 4143434f554e5453 7
python -B -m unittest -v
```

Use the exact directory filename without padding (ASCII spelling or raw filename bytes in hex) and a one-based record number.  The callable interface is `lookup(image, name, number)`, where the image and name are bytes.  The CLI prints JSON with the raw record in hex, total record count, record length, and ordered source spans.  Each span gives track, sector, offset within the sector (including the link bytes), absolute byte offset in the D64, offset within the record, and byte length.  All offsets are zero-based.  A refusal returns nonzero with a diagnostic on stderr and no record on stdout.

**Strict profile:** exactly 174,848 bytes, standard 35-track geometry, directory chain starting at 18/1 on track 18, and a unique closed REL entry with one or two side sectors.  Each side must identify the same members in the same order as the actual links, carry the correct ordinal and record width, and index all 120 blocks if another side follows.  Record widths are 1 through 254 bytes.  The terminal side-sector count must delimit complete pointer pairs with zero unused slots.  The directory block count must include all data sectors plus every side sector.  The linked data chain must match every indexed pointer in stored order.  The final data byte count must yield whole fixed-width records; an incomplete tail is refused, not truncated.  Record contents are opaque, including zero and padding bytes.

Three or more side sectors, super side sectors, appended sector-error tables, other image sizes, and extraction of other file types are unsupported.  This is not a BAM or whole-disk integrity checker.  The tests construct their own sectors and expected record bytes in memory; no image, emulator, or third-party package is needed.
