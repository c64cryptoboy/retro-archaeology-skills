# Neutral support provenance

The reduction tools and tests have no runtime dependency on a metamorphic
transformer, private evidence tree or emulator harness. Identical support used
by reduction and RND is canonical in `../../../shared/6502/`; retain repository
layout when installing the skill.  Small Python import adapters load the canonical
modules without filesystem symlinks.

The support was originally extracted from an independently developed
metamorphic research effort. This records implementation ancestry, not a
runtime or acceptance-test dependency:

| Module | Extraction source SHA-256 | Extraction note |
|---|---|---|
| `isa6502.py` | `69523c6968a752140edf3e27ed1e338671aba5df553d725bf5480b5652881389` | Documented `OPS` metadata extracted from the original rewriter. |
| `dataflow6502.py` | `c4a390faa1e511d0290430e12ce0b6aae0bdfdf7614c39a3b614d0ef3de2f1ac` | Neutralized import to `isa6502`. |
| `cpu6502.py` | `22783edcdf27874dd83fac90ca402551afb136c5dca6b823c921c21b23aa28e6` | Derived from MIT-licensed ChiptuneSAK; ownership header updated. |
| `routine_runner.py` | `aa27330c55bf9fe0d2538c1d8c2b4783136dd4d5e04362e1b30874efa71c2451` | Exact copy at extraction. |
| `equivalence.py` | `1336c1d69366794f53c33614e1f95b9f6edc510fe1efe2fa3966bf4925606201` | Exact copy at extraction. |

These are historical source hashes, not claims about current module hashes.
The CPU's in-file attribution and
[ChiptuneSAK MIT notice](../../../shared/6502/CHIPTUNESAK_LICENSE.txt) are retained.
The import adapters preserve canonical module locations and do not change the
reduction or emulation algorithms.
