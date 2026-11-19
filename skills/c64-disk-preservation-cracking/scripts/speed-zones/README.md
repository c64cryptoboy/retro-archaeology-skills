# Inspect one G64 speed entry

This read-only Python 3 diagnostic distinguishes a whole-track speed zone from a pointer to packed per-byte zones.  It prints JSON to stdout, or a refusal to stderr with exit status 1.  It has no media-writing or extraction mode and needs only the standard library.

```sh
python3 -B g64_speed.py capture.g64 --slot 70
python3 -B -m unittest -v
```

Run these commands from this directory.  Slot zero is track 1; each subsequent slot adds half a track.  A run is `[start, end_exclusive, zone]`, measured in bytes of the selected GCR track payload, excluding its two-byte length.  File offsets are absolute.  A speed entry of 0 through 3 is a literal zone; a larger entry is the file offset of a map.  For each packed map byte, read two-bit fields from most significant to least significant.  Report only the recorded track length, merging adjacent equal zones even across a map-byte boundary.  Ignore unused fields in the last byte.

Format evidence: the [G64 format description](https://ist.uwaterloo.ca/~schepers/formats/G64.TXT), in its “Speed entry $FF” diagram, labels the leftmost pair as the first byte and the rightmost pair as the fourth.  It is those labels, not the symmetric example value, that establish field order.

Scope: single-sided version-0 `GCR-1541`, up to 84 slots.  Only the selected slot, its declared payload, and its required speed fields are inspected.  The tool neither certifies the image’s complete layout nor validates other slots, unused allocation space, GCR contents, sectors, flux, or physical timing.
