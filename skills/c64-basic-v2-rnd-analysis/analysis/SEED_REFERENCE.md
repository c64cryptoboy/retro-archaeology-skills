# Seed domains, reachability, and extrema

Use these results to distinguish canonical state counts, valid negative FAC encodings, and BASIC source spellings.  The formulas, proof boundaries, and retained measurements below concern the pinned stock ROMs in `REPRODUCE.md`; they are not a new exhaustive run.

## Canonical domain

### Canonical starting-state domain

The selected domain is every distinct normalized `RNDX` state representable by the ROM's post-arithmetic byte-shuffle/normalization stage when its intermediate FAC exponent is in `$7F..$98` and its 32-bit mantissa is any normalized mantissa.

This exponent interval is closed for these starts:

- the smallest represented state is approximately `2.99178282148e-8`; multiplying by 11,879,546 and adding the stock constant gives approximately `0.3554102558`, whose FAC exponent is `$7F`;
- the largest represented state is the rounded special value `1.0`; its product plus the stock constant is less than `2^24` and at least `2^23`, whose FAC exponent is `$98`.

For reversed intermediate mantissa `R`, normalization shift `s=clz32(R)`, and intermediate exponent `E`, the stored output significand is:

```text
T = R * 2^s + floor((E * 2^s + 128) / 256)
```

with the known rounded-overflow special case at `1.0`.  The restored implicit intermediate mantissa bit becomes bit 7 of `R`, so `s` is limited to `0..24`.

Taking the union over `E=$7F..$98`, deduplicating rounded contributions, and accounting for overlap between adjacent 128-value runs at `s=0` gives:

```text
2,936,012,800 states = $AF000000
```

This is 68.359375% of `2^32`.  It has an exact rank/unrank mapping to integer keys `0..$AEFFFFFF`; the key is an enumeration index, not merely bytes `$008C-$008F`.

Important domain interpretation: this is the complete closed structural envelope of canonical post-shuffle states.  It deliberately includes a state even if later whole-graph work proves it has no predecessor under the actual multiply/add transition, because it remains a valid canonical starting state.  It excludes arbitrary valid FAC values that do not satisfy this generator-specific post-shuffle format.

Evidence:

- `canonical_seed_domain.py`
- `canonical_seed_domain.h`
- `test_canonical_seed_domain.py`
- 1,000,000 deterministic Python rank/unrank round trips
- C boundary checks and 1,000,000 pseudorandom generated-ROM closure checks
- C closure digest: `67ac54e57794a8cd`

## Negative-FAC image and inverse

### Scope and domain

This result starts with an already evaluated, normalized, nonzero negative value in BASIC's FAC and models the stock negative branch at `$E0D3`.  It answers the machine-value question:

> Which `RNDX` states can be produced from all valid normalized negative FAC encodings?

It does **not** prove which of those FAC values can be written as one decimal literal within C64 BASIC's source-line and parser constraints.  BASIC arithmetic expressions, variables, and machine-level construction are also separate operational reachability questions.

### Confirmed ROM path

At `$E097`, `JSR $BC2B` tests FAC's sign.  A negative value branches to `$E0D3`, bypassing the multiply/add advance at `$E0BE`.

The negative branch:

1. swaps FAC mantissa bytes `$62 <-> $65` and `$63 <-> $64`;
2. clears FAC sign `$66`;
3. copies the original exponent `$61` into rounding byte `$70`;
4. forces FAC exponent `$61` to `$80`;
5. calls normalizer `$B8D7`;
6. stores the rounded packed result in `RNDX` through `$BBD4`/`$BC1B`.

Thus the exponent is not merely discarded: depending on normalization distance, some or all of its bits enter the low significand, with the next bit controlling rounding.

### Exact direct formula

Let:

- `E` be the input exponent, `1 <= E <= 255`;
- `M` be the 32-bit unpacked FAC mantissa, `$80000000 <= M <= $FFFFFFFF`;
- `R = byte_reverse_32(M)`;
- `s = clz32(R)`.

Because the restored leading mantissa bit becomes bit 7 of `R`, `R` is nonzero, bit 7 is one, and `0 <= s <= 24`.

The normalized/rounded output mantissa is:

```text
k = floor((E * 2^s + 128) / 256)
T = R * 2^s + k
```

Normally the output exponent is:

```text
O = 128 - s
```

If `T = 2^32`, ROM rounding renormalizes it to:

```text
T = $80000000
O = 129 - s
```

The stored positive seed is:

```text
O, (T>>24)&$7F, (T>>16)&$FF, (T>>8)&$FF, T&$FF
```

This formula uses integer arithmetic only.

### Exact image size

Valid normalized negative FAC encodings:

```text
255 * 2^31 = 547,608,330,240
```

Distinct reachable five-byte `RNDX` seed states:

```text
10,745,675,776
```

This is approximately 2.502 times `2^32`.  Therefore the set of states immediately produced by `RND(negative)` is **not itself a 32-bit set** when every valid negative FAC encoding is admitted.

Normal output exponents range from `$68` through `$80`.  Eight rounding-overflow boundary states can instead use the next exponent, including `$81` for the `s=0` boundary.  Consequently every negative-seed result is a positive packed value in the closed numerical interval `2^-25 .. 1`.

### Why every extra seed is one positive step from the canonical domain

For any such seed value `x`, the positive branch first computes, in Microsoft floating point,

```text
x * 11,879,546 + ($A8B146 / 2^48)
```

The real-number endpoint bounds are approximately:

```text
x = 2^-25:  0.354038098988...
x = 1:      11,879,546.000000039...
```

These endpoints lie well inside the FAC exponent bins `$7F` and `$98`, respectively; floating-point rounding cannot move either across the neighboring power-of-two boundary.  Thus every possible intermediate positive-advance FAC has exponent `$7F..$98` and a normalized mantissa.

The 2,936,012,800-state canonical domain was constructed as exactly the set of distinct results obtainable when the ROM post-multiply shuffle receives a normalized mantissa with an exponent in `$7F..$98`.  Therefore the first positive advance from every state in the 10,745,675,776-state negative-seed image is in the canonical domain, and every later positive advance remains there.

The 7,809,662,976 image states outside the canonical set are consequently a one-step outer shell, not additional cycles or deeper chains.  This statement is about the all-valid-FAC machine-value image; exact reachability of every input FAC from BASIC source expressions remains a separate question.

Per-normalization-distance counts are emitted by:

```bash
python3 negative_seed_image.py
```

The largest categories are approximately one billion states each for `s=0` through `s=8`; categories then halve rapidly.

### Why the mapping is lossy

The input domain contains 39 varying bits: 31 normalized mantissa bits and eight exponent bits.  The exponent affects only:

```text
k = round_half_up(E * 2^s / 256)
```

For small `s`, many exponent values produce the same `k`.  For `s <= 6`, adjacent reversed mantissas also share one rounded endpoint.  Consequently many negative FAC values map to each seed.

`negative_seed_image.py --seed ...` returns every valid negative FAC preimage of one seed without scanning the complete input domain; it tests at most 25 * 255 algebraic candidates.

### Cold-start seed has no negative-FAC preimage

The reset seed:

```text
80 4f c7 52 58
```

has **zero** valid normalized negative FAC preimages.

For its non-overflow exponent `$80`, the only possible normalization distance is `s=0`.  At `s=0`, `k` is zero or one, so candidate reversed mantissas end in `$58` or `$57`.  A valid reversed input mantissa must have bit 7 set because the original FAC's restored leading bit lands there.  Neither candidate does.  Rounding-overflow outputs have mantissa `$80000000`, so they cannot provide another path.

Therefore no ordinary valid negative BASIC numeric value directly recreates the power-on seed through this ROM mapping.  This does not rule out reaching the reset seed after one or more positive advances.

### `RND(-1)` check

The direct model maps FAC bytes for `-1`:

```text
81 80 00 00 00
```

to:

```text
68 00 81 00 00
```

An actual live immediate-mode `X=RND(-1)` call produced exactly those `RNDX` bytes. 

### Validation

`test_negative_seed_image.py` performs five focused tests:

- direct `-1` mapping and ROM comparison;
- proof-oriented cold-start inverse check;
- exact aggregate image counts;
- exhaustive exponent enumeration across one complete 128-mantissa run in each of the 25 normalization categories;
- 260 boundary/deterministic-random direct-formula comparisons against execution of the pinned ROM from `$E0D3`, with inverse inclusion checks.

These checks require the pinned ROMs; see `REPRODUCE.md`.

## Complete negative-seed statistics

### Scope

This population contains each distinct five-byte `RNDX` state in the image of every valid normalized negative FAC encoding, counted once, together with all states reached by subsequent positive `RND()` advances.  The image contains the entire canonical graph, so the union has:

```text
total distinct states:       10,745,675,776
canonical closed states:      2,936,012,800
one-step outer entry states:  7,809,662,976
cycle nodes:                         79,440
transient states:             10,745,596,336
components/cycles:                        15
```

`RND(0)` and the power-on-only initial state are excluded.  This is an all-valid-FAC machine-value result, not a claim that every input FAC has a one-literal BASIC spelling.  Each distinct resulting `RNDX` state has equal weight regardless of how many FAC inputs map to it.

Every outer state enters the canonical domain after one positive advance.  It adds no cycle or component.

### Final per-cycle table

The median and maximum are positive advances required to first reach the cycle, among all transient states in the corresponding expanded basin.  Cycle nodes (`mu=0`) are excluded from the median.

```text
Loop   Loop length   Transient states   Median steps   Maximum steps
----   -----------   ----------------   ------------   -------------
 1              1                 13              2               3
 2              3                 16              1               2
 3              7            103,045            124             277
 4             23          1,463,420            486           1,168
 5             74             11,877             23              99
 6             85            402,751            197             463
 7            207            156,211             97             443
 8            295          3,809,394            680           1,768
 9            371            660,161            147             570
10            724      1,635,694,813         25,231          49,811
11          2,644         25,517,450          1,380           5,721
12          4,232         29,529,864            758           2,886
13          5,660         48,239,072          1,358           4,977
14          7,036        163,375,067          2,535           7,890
15         58,078      8,836,633,182         18,602          58,681
```

The shell changes some component medians slightly and increases six component maxima by one.  It does not change the global maximum:

```text
maximum mu:          58,681
associated lambda:   58,078
maximum mu+lambda:  116,759
```

Thus `RND(-4.33901453)` remains a practical maximizing negative BASIC seed.

### Exact run

The restartable parallel runner:

1. enumerated every one of the 10,745,675,776 distinct negative-seed image states with a proved dense unrank operation;
2. recognized and skipped the 2,936,012,800 canonical states already represented in retained aggregates;
3. advanced each of the 7,809,662,976 outer states exactly once through the generated pinned-ROM transition;
4. ranked each successor into the retained canonical metadata;
5. accumulated exact `(lambda,mu+1)` counts with eight independent workers.

```text
threads:                       8
image states enumerated:       10,745,675,776
outer transitions evaluated:   7,809,662,976
elapsed production time:       1,977.188 seconds (32m 57s)
checkpoint chunk size:         1,000,000 image states
checkpoint interval:           100 completed chunks
additional final data:         approximately 12 MiB
```

No second giant per-state metadata file was created, and the original 10.94-GiB canonical metadata was not modified.

### Validation and failure detection

Before corrected production:

- 100,000 random/boundary Python dense-image rank/unrank round trips passed;
- 10,000 random negative FAC outputs ranked back into the dense image;
- a one-million-index C/Python unrank digest matched exactly;
- GCC and Clang produced identical reduced shell histograms;
- an independent Python 6502 execution reproduced all 8,356 populated bins from 16 distributed reduced chunks containing 16,000 image states and 10,628 outer transitions.

The first production attempt exposed a worker bug: it enumerated each seed but failed to copy it into `RNDX` before advancing.  Exact total counters still passed, but the automatic comparison against the previously completed targeted frontier analysis rejected its component maxima.  Rejected outputs are not bundled.  Matching totals alone was insufficient; the independent frontier maximum check detected the defect.

Corrected production then passed:

- exact image, canonical, outer, transition, and histogram-total invariants;
- the targeted top-two-layer maximum result for all 15 components;
- an independent recomputation of every final transient count, median, and maximum from the combined CSV;
- final artifact SHA-256 verification.

## Outer-shell maximum proof

### Question

The completed 2,936,012,800-state sweep classified the closed canonical graph followed by positive `RND` calls.  The all-valid-negative-FAC transform can immediately produce 10,745,675,776 distinct `RNDX` states, including a 7,809,662,976-state one-step shell outside the canonical graph.

This analysis asks whether that shell increases the maximum on-ramp depth in each of the 15 components, and in particular whether it increases the global maximum from 58,681 to 58,682.

This is a machine-value result over all valid normalized negative FAC encodings.  It is not a claim that every such FAC can be written as one BASIC decimal literal or source expression.

### Result

```text
lambda  canonical  canonical  shell-adjusted  maximizing  negative FAC
        max mu     max states max mu          states      encodings
     1          2          2              3           3            112
     3          1          2              2           1              1
     7        277          1            277           3            131
    23      1,168          1          1,168          10            309
    74         99          1             99           3            445
    85        463          1            463           6            249
   207        443          1            443          10            193
   295      1,767          2          1,768           6             37
   371        569          3            570           1              1
   724     49,811          1         49,811           6            123
 2,644      5,721          1          5,721          12            302
 4,232      2,885          2          2,886           6             95
 5,660      4,977          1          4,977           4            281
 7,036      7,889          1          7,890           2             48
58,078     58,681          1         58,681           4             84
```

The shell increases the component maximum in six components: cycle lengths 1, 3, 295, 371, 4,232, and 7,036.  It does not increase the global maximum.

Therefore the maximum over the union of the canonical domain and every distinct all-valid-negative-FAC seed state remains:

```text
mu:                            58,681
lambda:                        58,078
mu+lambda:                    116,759
maximizing RNDX states:              4
valid negative FAC encodings:       84
```

The four maximizing internal starts are:

```text
76 57 66 2a 0c   canonical; reached by FAC 83 8a d9 35 00
7a 57 66 2a 0c   outer shell; 4 negative-FAC preimages
7c 57 66 2a 0c   outer shell; 16 negative-FAC preimages
7e 57 66 2a 0c   outer shell; 63 negative-FAC preimages
```

The known practical expression `RND(-4.33901453)` reaches the canonical first state, so it remains a valid maximum-total recommendation.  The source-level spellability of every one of the other 83 FAC encodings was not analyzed here.

The unique canonical maximum state does have one numerical positive-transition predecessor in the allowed value interval:

```text
6b 44 17 b2 75 -> 76 57 66 2a 0c
```

However, `6b 44 17 b2 75` has no valid normalized negative-FAC preimage.  It is therefore unavailable from the all-valid-negative-FAC seed image and cannot extend the result to 116,760 under this scope.

### Why only two canonical layers are needed

For a component with canonical maximum depth `D`, every outer-shell state has depth exactly one plus its canonical successor's depth.  Therefore:

- an outer predecessor of a depth-`D` state raises the component maximum to `D+1`;
- if none exists, outer predecessors of depth-`D-1` states can only tie `D`;
- predecessors of shallower states cannot attain the maximum.

The retained metadata showed only 60 canonical states total across those top two layers in all 15 components.  The analysis did not enumerate the 10.746-billion-state shell.

### Method

1.  `extract_component_frontiers.c` streamed the retained 10.94-GiB metadata twice and extracted all canonical ranks at each component's maximum and maximum-minus-one depths.  It evaluated no transitions and left production artifacts untouched.
2.  `negative_seed_image.seed_preimages` inverted each target's final shuffle and retained all possible pre-shuffle FACs with exponent `$7F..$98`.
3.  `invert_positive_frontiers.c` used the exact generated ROM path and monotone binary search over every normalized positive packed value in `2^-25 .. 1` to find all numeric predecessors of those FACs.
4.  Each candidate was forward-validated through the generated transition, tested for canonical membership, and tested algebraically for all valid normalized negative-FAC preimages.
5.  All 954 numeric predecessor transitions and all 2,915 retained outer-state negative-FAC mappings were independently replayed through the Python 6502 interpreter loaded with the pinned ROMs.

Intermediate counts:

```text
canonical top-two-layer states:           60
possible pre-shuffle FAC targets:      1,123
exact numeric predecessor states:        954
outer negative-image predecessors:       129
negative FAC mappings to those states: 2,915
```

Pinned ROM identities:

```text
BASIC  89878cea0a268734696de11c4bae593eaaa506465d2029d619c0e0cbccdfa62d
KERNAL 83c60d47047d7beab8e5b7bf6f67f80daa088b7a6a27de0d7e016f6484042721
```

## All maximizing starts and source expressions

### Result

Across the image of every valid normalized negative FAC encoding, exactly four
initial `RNDX` states attain the global maximum:

```text
mu = 58,681
lambda = 58,078
total distinct states before repetition = 116,759
```

They are:

```text
76 57 66 2a 0c
7a 57 66 2a 0c
7c 57 66 2a 0c
7e 57 66 2a 0c
```

These are not four disjoint long trajectories.  Every one advances in one
positive `RND` step to the same canonical state:

```text
80 04 d9 84 99
```

That common successor has `mu=58,680`, `lambda=58,078`, and total `116,758`.
Thus the four maximum paths differ only in their first state and then share the
entire remaining tail and cycle.

The first state, `76 57 66 2a 0c`, is the unique deepest canonical state and
has canonical rank `2,900,100,616`.  The other three are outer-shell negative
seed entries.

### Every negative-FAC preimage

The four starts are produced by 84 valid normalized negative FAC encodings.
The following compact ranges enumerate all 84.  FAC bytes are shown as exponent
followed by the restored 32-bit mantissa; the value supplied to `RND` is
negative.

| Initial `RNDX` | Negative FAC encodings | Count |
|---|---|---:|
| `76 57 66 2a 0c` | `83 8a d9 35 00` | 1 |
| `7a 57 66 2a 0c` | exponent `2e..31`, mantissa `a8 98 5d 03` | 4 |
| `7c 57 66 2a 0c` | exponent `b8..c7`, mantissa `a0 62 76 0d` | 16 |
| `7e 57 66 2a 0c` | exponent `01..1f`, mantissa `83 8a d9 35` | 31 |
| `7e 57 66 2a 0c` | exponent `e0..ff`, mantissa `82 8a d9 35` | 32 |

Count check: `1 + 4 + 16 + 31 + 32 = 84`.

These counts are machine-value preimages.  They must not be read as a claim
that every encoding has a one-decimal-literal BASIC spelling.

### One source-level spelling for each start

The following direct-mode expressions were run on the live stock-ROM C64 and
the five bytes at `RNDX` (`$008B-$008F`) were read back:

```basic
X=RND(-4.33901453)
```

produces:

```text
76 57 66 2a 0c
```

```basic
X=RND(-2828557571/65536/65536/65536/65536/65536/65536/32768)
```

produces:

```text
7a 57 66 2a 0c
```

```basic
X=RND(-2690807309*65536*256)
```

produces:

```text
7c 57 66 2a 0c
```

```basic
X=RND(-2190137653*65536*65536*65536*65536)
```

produces:

```text
7e 57 66 2a 0c
```

The integer mantissas and the power-of-two scaling make the three constructed
examples exact in BASIC's binary FAC representation.

### Different ways to write or reach the same path

Equivalent decimal syntax can parse to the same FAC.  For example, the pinned
FIN implementation parses each of these to FAC bytes `83 8a d9 35 00`:

```basic
RND(-4.33901453)
RND(-.433901453E1)
RND(-43.3901453E-1)
RND(-4.339014530)
```

There is also a stronger kind of equivalence caused by the lossy negative-seed
shuffle: distinct FAC values can map to the same `RNDX`.  For example:

```basic
RND(-.4040090873E29)  : REM FAC E0 82 8A D9 35
RND(-.808018175E29)   : REM FAC E1 82 8A D9 35
```

Both map to `RNDX = 7e 57 66 2a 0c`, so they follow exactly the same maximum
trajectory after seeding despite having different numeric arguments.

### Evidence

- The four frontier states and their common metrics come from the completed
  all-valid-negative-FAC outer-shell analysis.
- `rnd_query.py preimages` plus `negative_seed_image.seed_preimages` produced
  the exhaustive `1, 4, 16, 63` inverse counts above.
- The generated stock-ROM transition produced the common successor from each
  of the four starts.
- `rnd_query.py classify 80 04 d9 84 99` returned canonical rank `40,999,837`,
  `mu=58,680`, and `lambda=58,078`.
- The four source expressions were validated live on a stock-ROM C64 during the original investigation.

## Expression-only direct seed proof

### Result

Under ordinary C64 BASIC V2 numeric-literal syntax, the canonical state

```text
RNDX = 77 0a 47 03 00
rank = 2,831,337,243
mu = 11,002
lambda = 724
```

can be seeded directly with the arithmetic expression:

```basic
X=RND(-8463173/16777216)
```

The division is exact: `8463173=$812345` and `16777216=2^24`, so the evaluated negative FAC is:

```text
80 81 23 45 00   (sign $ff held separately in the live FAC)
```

The negative-RND shuffle maps this to `77 0a 47 03 00`.  A live stock-ROM C64 run reproduced those five RNDX bytes.

This state has exactly one valid normalized negative-FAC preimage: `80 81 23 45 00`.  Consequently, an alternate FAC preimage cannot make the same seed literal-accessible.

### Why one numeric literal cannot seed it

The exact input magnitude is approximately `0.504444420337677`.  Every ordinary finite decimal spelling can be normalized to a significant-digit integer `D` and net decimal scale.  For a value in `[0.1,1)`, an `n`-digit `D` must have net scale `10^-n`.  Moving the decimal point or using `E` notation changes only the spelling of this same pair.  Leading zeroes do not affect accumulation; trailing zeroes are additional significant-digit steps and were included.

The pinned ROM's FIN routine first accumulates all digits using positive `FAC = FAC*10 + digit`, then applies the decimal-point/exponent scale.  These operations and their rounding are monotone.  For each significant length 1 through 38, a binary search found the adjacent parser outputs bracketing the target but never the target itself.  At the useful precision the gap is clear:

```text
lower FAC: 80 81 23 44 ff
target:    80 81 23 45 00
upper FAC: 80 81 23 45 01
```

For 39 or more target-sized significant digits, the unscaled accumulator starts near `5.04e38`, exceeding the approximately `1.7e38` FAC maximum before FIN applies the decimal scale.  The ROM therefore takes its overflow path.  Thus no longer decimal spelling closes the gap.

The search covered optional decimal-point placement and equivalent `E` notation through normalization, not merely decimal renderings near the mathematical value.

### Validation

- A mechanically generated C specialization followed the pinned `$BCF3` FIN control flow and exact 6502/FAC semantics.
- It matched the independent Python 6502 ROM interpreter on 100 fixed/random ordinary and scientific literals.
- One hundred groups using equivalent normalized, decimal-point, and `E` spellings produced byte-identical FAC results.
- The target's unique negative-FAC preimage was checked with `negative_seed_image.seed_preimages`.
- The resulting seed's rank and graph classification were read from the completed exhaustive metadata.
- Live C64 BASIC execution of `X=RND(-8463173/16777216)` produced `RNDX = 77 0a 47 03 00`.

Relevant artifacts (source and search log are bundled; compile the executable locally):

```text
scratch/generate_fin_c.py
scratch/generated_fin.c
scratch/generated_fin
scratch/search_literal_reachability.py
scratch/literal-search.log
```

For a small local parser check, first verify the pinned ROM identities as described
in `REPRODUCE.md`.  From this `analysis/` directory, build the bundled source and
supply exactly one fixed literal on stdin:

```bash
cc -O3 -std=c11 scratch/generated_fin.c -o scratch/generated_fin
ROM_DIR="${C64_ROM_DIR:-$PWD/../../c64-rom-reference/assets/roms}"
printf '%s\n' '-.311306466' | ./scratch/generated_fin "$ROM_DIR/basic.bin" "$ROM_DIR/kernal.bin"
```

The output is the input literal, a tab, and FAC bytes `7f9f638fa5ff`, including the
separate negative sign byte.  The generator creates source, not an executable;
no compiled binary is bundled.  This single parser check does not rerun the
historical reachability searches or establish their proof by itself.

The generated C contains mechanically ROM-derived code and is included with the same provenance/licensing-uncertainty notices as `generated_rnd_cycle.c`; its redistribution status is unresolved, and inclusion is not a license grant.

## Sequential integer clock seeds

### Answer

The basin probability for a uniformly selected distinct state from the complete
negative-FAC seed image is exactly:

```text
(transient states + cycle length) / 10,745,675,776
```

That denominator and weighting do not automatically describe integer `TI`
seeds.  The integer seeds form a small, structured subset, so this result counts
them directly.

For every exact positive integer `TI` in `1..5,184,000`, the stock BASIC FAC
was mapped through the negative `RND` seed path and its resulting five-byte
`RNDX` state was looked up in the retained complete canonical metadata.  Each
`TI` value has weight one.  Every integer-derived seed in this range is already
in the canonical domain; no outer-shell transition is needed.

The full-day integer distribution is extremely close to the all-state basin
distribution, but this is an observed exact count, not a consequence of the
global denominator and not a guarantee for short prefixes.

| Loop | Cycle length | Basin / 10,745,675,776 | Global % | `TI` count / 5,184,000 | `TI` % | Difference, percentage points |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 1 | 14 | 0.00000013% | 0 | 0.000000% | -0.00000013 |
| 2 | 3 | 19 | 0.00000018% | 0 | 0.000000% | -0.00000018 |
| 3 | 7 | 103,052 | 0.000959% | 55 | 0.001061% | +0.000102 |
| 4 | 23 | 1,463,443 | 0.013619% | 733 | 0.014140% | +0.000521 |
| 5 | 74 | 11,951 | 0.000111% | 5 | 0.000096% | -0.000015 |
| 6 | 85 | 402,836 | 0.003749% | 215 | 0.004147% | +0.000399 |
| 7 | 207 | 156,418 | 0.001456% | 100 | 0.001929% | +0.000473 |
| 8 | 295 | 3,809,689 | 0.035453% | 1,836 | 0.035417% | -0.000037 |
| 9 | 371 | 660,532 | 0.006147% | 324 | 0.006250% | +0.000103 |
| 10 | 724 | 1,635,695,537 | 15.221895% | 789,294 | 15.225579% | +0.003683 |
| 11 | 2,644 | 25,520,094 | 0.237492% | 12,265 | 0.236593% | -0.000898 |
| 12 | 4,232 | 29,534,096 | 0.274846% | 14,188 | 0.273688% | -0.001158 |
| 13 | 5,660 | 48,244,732 | 0.448969% | 23,332 | 0.450077% | +0.001108 |
| 14 | 7,036 | 163,382,103 | 1.520445% | 78,787 | 1.519811% | -0.000634 |
| 15 | 58,078 | 8,836,691,260 | 82.234858% | 4,262,866 | 82.231211% | -0.003647 |

“Second-largest loop” can be ambiguous.  Loop 14 has the second-longest cycle
and a 1.520445% basin.  The second-largest basin is loop 10, whose cycle is only
724 states but whose feeder trees raise its probability to 15.221895%.

### Short sequential prefixes

Short prefixes need not have the global proportions:

| Positive integer seeds | Nonempty loops | Loop 15 | Loop 10 | Loop 14 | Loop 13 | Largest absolute difference from global |
|---:|---:|---:|---:|---:|---:|---:|
| 60 | 4 | 71.6667% | 25.0000% | 1.6667% | 1.6667% | 10.5682 pp |
| 3,600 | 7 | 81.5833% | 16.0000% | 1.3333% | 0.3611% | 0.7781 pp |
| 216,000 | 12 | 82.1500% | 15.2833% | 1.5282% | 0.4491% | 0.0849 pp |
| 1,000,000 | 13 | 82.1682% | 15.2632% | 1.5410% | 0.4529% | 0.0667 pp |
| 5,184,000 | 13 | 82.2312% | 15.2256% | 1.5198% | 0.4501% | 0.0037 pp |

Loops 1 and 2 receive no integer `TI` seed in this range.  Their all-state
basins contain only 14 and 19 states respectively, so this absence is
consistent with their extremely small global proportions.

### `TI=0` and the stock clock boundary

`RND(-0)` is `RND(0)`, which takes the separate CIA-timer sampling path.  It is
therefore not a deterministic member of the negative-integer count.  If zero is
included in a sequential experiment, its one result must be classified from
the timer-derived state separately.

The commonly stated nominal range is `0..5,183,999`, corresponding to exactly
24 hours at 60 jiffies per second.  Revision-3 KERNAL `UDTIM` at `$F69B` actually
resets after reaching `$4F1A01` (5,184,001), so `$4F1A00` (5,184,000) exists for
one tick.  Including that extra positive value adds one loop-15 seed.  Excluding
it gives 4,262,865 loop-15 seeds out of 5,183,999, or 82.231208%; the practical
conclusion is unchanged.

### Reproduction and validation

```bash
python3 analyze_ti_seed_prefixes.py \
  --output scratch/ti-seed-prefixes.json
```

The implementation uses integer arithmetic only.  It was cross-checked for
10,016 boundary and deterministic-random inputs against the established
`NegativeFac` to `SeedState` model and the independent canonical rank routine.
The retained compact production outputs passed their SHA-256 manifest before
the query.

## Hardware-timer path: RND(0)

The stock C64 ROM does not run the normal multiply-add generator for `RND(0)`.  At `$E09E-$E0B9`, it samples four CIA1 registers and places them directly into the floating-point mantissa:

```text
$DC04  CIA1 timer A low
$DC05  CIA1 timer A high
$DC08  CIA1 time-of-day tenths
$DC09  CIA1 time-of-day seconds
```

It then forces the exponent, normalizes the value, and saves it as the new RND state.  It does not mix these readings with the previous state.

The time-of-day clock is not started by the normal C64 startup, so its two sampled bytes ordinarily remain constant.  That leaves only CIA1 timer A: a deterministic down-counter used for the regular system interrupt.  It repeatedly traverses a relatively small range, and calls made by the same BASIC loop tend to sample it at regular, correlated intervals.  The resulting values therefore form visible patterns rather than independent random samples.  The C64-Wiki demonstration reports an effective set of only 256 values in its particular tight loop; this is an observed timing-loop result, not a universal mathematical limit for every possible call schedule.

The likely historical problem is hardware adaptation: related Commodore machines sampled two useful free-running timers, whereas the same register offsets on the C64's CIA select one timer and two time-of-day fields.  The latter supply no changing bits unless software explicitly starts the TOD clock.

`RND(0)` can still capture some uncertainty when its call time depends on a human action.  A better use is to call it once for a timing-dependent seed and then use `RND(1)` for subsequent values, rather than repeatedly calling `RND(0)` as the generator.

Source checked:

- pinned stock C64 KERNAL ROM, `RND` at `$E097`, hardware-sampling path `$E09E-$E0B9`
- Microsoft `BASIC-M6502` historical source, https://github.com/microsoft/BASIC-M6502
- C64-Wiki, “RND,” revision 43073, https://www.c64-wiki.com/index.php?title=RND&oldid=43073
