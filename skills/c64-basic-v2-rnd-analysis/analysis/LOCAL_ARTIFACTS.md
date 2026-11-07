# External datasets and compact package boundary

Compact queries use bundled Python/C source, technical references, visualizations, and accepted aggregates.  The package excludes ROM binaries, native executables, failed-run directories, and giant per-state metadata.  Generated ROM-derived C is retained with unresolved provenance/licensing status; see `SOURCES.md`.

## Canonical metadata identity

```text
File:   metadata.bin (inside an external completed-run directory)
Size:   11,744,051,200 bytes (10.9375 GiB)
SHA256: 8b9b38986475acd0a1f10826a968d04dfa695af741ab7b8fb80c2417051264fc
```

Keep metadata with its matching `checkpoint.bin`, `summary.json`, histogram CSVs, `cycle-components.csv`, and derived aggregates.  Set `C64_RND_RUN_DIR` or pass `rnd_query.py ... --run-dir PATH`.  `classify` validates checkpoint and metadata size and reads one entry; it does not stream-hash this huge file.  `verify-results` validates compact hashes and completion, not every metadata entry.  `export_component_depth` performs the documented full metadata scan.

The bundled canonical checkpoint and compact data preserve accepted bytes.  The shell's 7.5-MiB restart bitmap/checkpoint is not needed for queries and is not bundled.  `compact-result-sha256.txt` pins the aggregates, frontiers, search output, and visualization data; it is a packaging manifest, not a replacement for full production validation.

`C64_RND_SHELL_DIR` optionally selects other completed shell aggregates.  Four metadata-dependent report tests and one query-classification test explicitly skip if `metadata.bin` is absent.  ROM-backed tests still require external pinned ROMs; missing ROMs are not an additional skip rule.  Synthetic runner tests require GCC and a suitable POSIX host.  Do not represent skipped tests as full-dataset validation or use metadata from an unrelated run.

Restore an existing verified dataset when available instead of rerunning billions of transitions.  Fresh exhaustive work requires the operator gate in `REPRODUCE.md`.
