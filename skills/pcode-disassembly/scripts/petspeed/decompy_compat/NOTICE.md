# PETSpeed compact compatibility backend

This attributed adaptation preserves an existing compact BASIC translator while exposing its address choices for inspection.  It is a reading aid for the exact JMP $2267 revision admitted by the caller, not recovered original source or a behavioral-equivalence guarantee.

## Source and license

Adapted software: EgonOlsen71/PetspeedDecompy, pinned commit `3d4360e8b481c2157fccac0458f3556a2d3ea311`:

- <https://github.com/EgonOlsen71/PetspeedDecompy/tree/3d4360e8b481c2157fccac0458f3556a2d3ea311>
- [`bin/basic_v2.py`](https://github.com/EgonOlsen71/PetspeedDecompy/blob/3d4360e8b481c2157fccac0458f3556a2d3ea311/bin/basic_v2.py)
- [`bin/petspeed_core.py`](https://github.com/EgonOlsen71/PetspeedDecompy/blob/3d4360e8b481c2157fccac0458f3556a2d3ea311/bin/petspeed_core.py)
- [`bin/speedcode.py`](https://github.com/EgonOlsen71/PetspeedDecompy/blob/3d4360e8b481c2157fccac0458f3556a2d3ea311/bin/speedcode.py)
- [`LICENSE.txt`](https://github.com/EgonOlsen71/PetspeedDecompy/blob/3d4360e8b481c2157fccac0458f3556a2d3ea311/LICENSE.txt)

`LICENSE.txt` is an exact copy of the pinned Unlicense.  This package does not import the upstream repository's fixtures, compiler, GUI, native runtime, or private validation data.  New adaptation code and synthetic tests are also offered under the Unlicense.  The surrounding repository's license does not replace this notice or upstream license.

## Specific changes

- Use relative imports, with no CLI, GUI, external dependency, or implicit fixture lookup.  `basic_v2.py` is unchanged apart from attribution.
- Replace textual `@XXXX` branch placeholders with typed `BranchReference` fragments.  Resolving a branch can no longer rewrite matching bytes inside a string literal or other non-target text.  Single branches and ON tables both use structured references.
- Construct an embedded string-literal NUL using `CHR$(0)`, rather than placing a line-terminating zero byte inside the BASIC body.  Existing quote handling and non-NUL literal spellings are retained.  Other control bytes remain literal PETSCII; detokenized text can therefore contain display controls or line separators.
- Retain upstream floating-literal spelling when its decimal is strictly within half an encoded-significand unit of the exact value.  Otherwise, use eleven significant digits instead of ten.  For example, the artificial value `1 + 2**-31` was previously printed as `1`.  The check uses exact rational arithmetic, not an emulation or execution of the BASIC ROM's decimal parser.
- Add structured statement and target evidence, without changing upstream statement ordering, generated variable names, generated line numbers, arithmetic operand order, or branch-selection policy.
- Add self-contained synthetic regression tests.  These demonstrate literal corruption, NUL refusal, and numeric precision loss independently of commercial or upstream fixtures.  They also exercise duplicate ON destinations, retained arithmetic ordering, generated DATA evidence, and existing refusals.

## APIs

The compatibility entry points retain their upstream calling conventions:

```python
from decompy_compat import basic_v2, petspeed_core, speedcode

image = petspeed_core.read_image(data)
code = speedcode.instructions(image)
lines = petspeed_core.decompile(data)  # list[basic_v2.BasicLine]
text = basic_v2.detokenize(lines[0].body)
prg = basic_v2.write_program(lines)
```

Additional APIs:

```python
result = petspeed_core.decompile_with_evidence(data)  # speedcode.DecodedProgram
# Or translate an already read image, without appending source DATA:
result = speedcode.decode_with_evidence(image)
```

`DecodedProgram` fields:

- `lines: list[BasicLine]`: exactly the corresponding compatibility API's output.
- `statements: tuple[StatementEvidence, ...]`: one record per output line, in order.  Each record has `line: BasicLine`, `emission_address: int | None`, `branch_targets: tuple[int, ...]`, and `generated: str | None`.  An emission address is the exact instruction site passed to the translator's emit operation, **not** an inferred expression start or complete dependency span.  Branch destinations preserve occurrence order and duplicates.  Generated `DIM` and appended `DATA` lines have `emission_address=None` and the corresponding `generated` value; ordinary emitted lines have `generated=None`.
- `targets: tuple[TargetEvidence, ...]`: unique encoded destinations, sorted by address.  Each record has `address: int`, `line_number: int`, `emission_address: int`, and `policy: str`, currently `"next-emission"`.  This exposes the exact generated target line and its actual emission site, even when they differ from the encoded destination.

`Instruction` records from `instructions(image)` separately expose `address`, `opcode`, `argument`, and exclusive `after`.  No textual target parsing is required.  Do not treat literal `@XXXX` text as a reference.

## Scope and known limits

The caller must enforce its exact runtime fingerprint gate.  `read_image` retains upstream structural/header checks, and `instructions` retains handler-address and operand checks; neither authenticates native handler contents.  This backend does not extend another revision's admission.

The legacy next-emission mapping is disclosed, not repaired or certified.  A destination at a valid instruction boundary may still map past expression setup, and linear symbolic state can cross control-flow entries.  Indexed two-dimensional expressions may duplicate effects such as RND.  These remain fidelity limits; the evidence API does not establish safe entry points, dependency coverage, or execution equivalence.  DATA quotation restrictions, statement coverage restrictions, BASIC line limits, and other upstream refusals remain.  Arithmetic order is deliberately preserved, not blindly reversed because an operation looks noncommutative.

No payload execution is required by the tests, and emitted programs must not be presumed safe or equivalent.  From the directory containing this package:

```sh
python3 -m unittest discover -s decompy_compat -t . -v
```
