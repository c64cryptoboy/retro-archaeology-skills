# Exhaustive C64 BASIC V2 `RND()` functional-graph report

## Executive summary

The stock C64 BASIC V2 positive `RND()` advance was exhaustively classified over its closed canonical post-shuffle state domain:

```text
canonical states:       2,936,012,800  ($AF000000)
functional components:             15
cycle lengths:                      15 distinct values
cycle nodes total:             79,440  (0.00270571% of states)
maximum on-ramp, mu:            58,681
maximum cycle, lambda:          58,078
maximum mu+lambda:             116,759
run time:                    8,518.809 s (2h 22m)
```

Every state has one successor.  Every one of the 15 weak components contains one directed cycle with inward-feeding trees.  In this domain no two cycles happen to have the same length.

The most useful practical seed depends on what “best” means:

- **Simplest seed with the maximum eventual period:** `RND(-1)`.  It has `mu=35,736`, `lambda=58,078`, and `mu+lambda=93,814`.
- **Maximum number of distinct internal states before the first repeat from a negative BASIC seed:** `RND(-4.33901453)` is one practical maximizing form.  It has `mu=58,681`, `lambda=58,078`, and `mu+lambda=116,759`; targeted outer-shell inversion proves no valid negative FAC can exceed it.

The second recommendation is unique among the 2,936,012,800 canonical states.  The pinned BASIC ROM parser converts the literal to FAC bytes `83 8a d9 35 00` (with negative sign held separately), and the negative `RND` path maps it to `RNDX = 76 57 66 2a 0c`, canonical rank 2,900,100,616.

This maximum was first established over the closed canonical positive-advance domain.  If every valid normalized negative FAC encoding is admitted, `RND(negative)` can immediately produce 10,745,675,776 distinct seed states, including states outside that domain.  Those extra states are a one-step seed shell rather than additional closed components: the next positive advance enters the canonical domain and remains there.  A targeted exact inverse analysis of every component's top two depth layers proved that the shell does not increase the global maximum: it remains `mu=58,681`, `lambda=58,078`, and `mu+lambda=116,759`.  Four internal starting states attain it under the expanded machine-value scope; the known `RND(-4.33901453)` form reaches the sole canonical one.  See the outer-shell maximum proof in `SEED_REFERENCE.md`.

“Longest sequence” does not mean statistically good by modern standards, and none of this generator should be used for cryptography.

## What the generator actually is

The routine is often described loosely as a floating-point linear congruential generator.  A more accurate description is:

> an affine update performed by Microsoft's custom floating-point package, followed by a byte permutation, exponent injection, normalization, and rounding.

For a positive argument, the C64 ROM at `$E0BE`:

1. loads the previous five-byte `RNDX` value from `$008B-$008F`;
2. multiplies it by the floating constant at `$E08D`;
3. adds the floating constant at `$E092`;
4. swaps the four mantissa bytes in pairs, equivalent to reversing their order;
5. moves the intermediate exponent into the guard/extension byte;
6. forces exponent `$80`, normalizes, rounds, and stores the next `RNDX`.

The stock C64 constants are:

```text
E08D: 98 35 44 7A 00  = 11,879,546 exactly
E092: 68 28 B1 46 00  ≈ 3.927677738602142 × 10^-8
```

This resembles the affine part of an LCG, but it is **not** the textbook integer recurrence `(a*x+c) mod m`.  Calling it simply “an LCG on floats” hides the byte shuffle and software floating-point semantics that determine the actual finite graph.

The positive argument's magnitude is irrelevant: any positive value advances once.  A negative argument replaces the state deterministically.  Zero takes the separate timer/entropy path, which was outside this exhaustive study.

## Floating-point format and why exact analysis is awkward

The C64 does not use IEEE 754.  That is not itself a bug: the Microsoft implementation predates the first IEEE 754 standard and uses its own five-byte packed format plus a larger internal FAC workspace.

For a nonzero packed value:

- one byte stores a biased exponent;
- four bytes carry an approximately nine-decimal-digit significand;
- the sign occupies the high bit of the first stored mantissa byte;
- the normalized leading significand bit is implicit in storage;
- the live FAC uses separate sign and guard/extension state during arithmetic.

A host `float` or even an idealized exact multiply-then-truncate model is not an exact substitute.  Carry propagation, intermediate normalization, the guard byte, and ROM rounding can change low bits and therefore change the eventual graph.  Concrete rejected-model counterexamples were found during this work.

There are historical bugs in the broader Microsoft BASIC family.  Michael Steil documents that generic nine-digit Microsoft versions stored the two random constants one byte short, while Commodore fixed that constant problem by at least the VIC-20.  The stock C64 bytes above include the fifth zero byte, so **do not describe that particular constant bug as present in the C64 generator**.

Exhaustion was valuable for proving the global inventory, but it was not the only possible analysis.  The negative-seed map and canonical domain were derived algebraically before the sweep.

## Did Bill Gates write it?

The broad lineage is clear; attribution of this exact routine is not.

Michael Steil writes that Ric Weiland, Bill Gates, and Monte Davidoff produced Microsoft BASIC for the MOS 6502 in 1976 by converting the Intel 8080 version.  His publication of Microsoft's 1978 source describes it as the oldest publicly available source containing Bill Gates's code.  The original division of labor says:

```text
Paul Allen:    non-runtime infrastructure
Bill Gates:    runtime statements, functions, operators, expression machinery, etc.
Monte Davidoff: floating-point math package
```

The random-number code sits with the floating-point/polynomial code and depends heavily on that package.  This makes “Bill Gates wrote C64 `RND`” too strong.  A defensible short-form statement is:

> “This is descended from early Microsoft BASIC code associated with Bill Gates, Ric Weiland, and Monte Davidoff. Gates wrote major runtime portions, while Davidoff is credited with the floating-point math package. I could not establish who personally wrote this exact random-number routine.”

Also avoid saying the C64 ROM is a direct build of the surviving 1978 source.  Steil's family-tree work says C64/VIC-20 BASIC V2 descends through Commodore's PET BASIC 4.0 line with later features stripped for space.

## Complete graph inventory

All counts below weight each canonical starting state equally.

| Cycle `lambda` | Basin states | Domain share | Components |
|---:|---:|---:|---:|
| 1 | 4 | 0.000000136% | 1 |
| 3 | 5 | 0.000000170% | 1 |
| 7 | 28,119 | 0.000957727% | 1 |
| 23 | 399,539 | 0.0136082% | 1 |
| 74 | 3,268 | 0.000111307% | 1 |
| 85 | 110,484 | 0.00376306% | 1 |
| 207 | 42,612 | 0.00145136% | 1 |
| 295 | 1,040,855 | 0.0354513% | 1 |
| 371 | 180,640 | 0.00615256% | 1 |
| 724 | 446,900,555 | 15.2213422% | 1 |
| 2,644 | 6,973,622 | 0.237520% | 1 |
| 4,232 | 8,069,330 | 0.274840% | 1 |
| 5,660 | 13,183,137 | 0.449015% | 1 |
| 7,036 | 44,649,715 | 1.520760% | 1 |
| 58,078 | 2,414,430,915 | 82.2350269% | 1 |

Two components dominate:

```text
lambda 58,078: 82.2350%
lambda    724: 15.2213%
combined:       97.4564%
```

The smallest “duds” are real but extremely rare.  The fixed-point component has only four starts in its entire basin, and the three-cycle component has five.  Only 541,419 starts, 0.01844%, end in any cycle shorter than 100.  Conversely, 17.7650% of states miss the maximum period.

The one-cycle behavior itself was previously demonstrated by Mike on Forum64 in 2020 with an exact BASIC expression that reaches the fixed point after one positive advance; later posts simplified the expression and discussed FAC-rounding subtleties.  An earlier 2014 Forum64 discussion used `RND(-7621)` to count 723 intervening values in the exact 724-node cycle, frequently observed a 58,077 count for the exact 58,078-node cycle, and recognized feeder states; Mike later estimated the maximum period near `2^16`.  This project's new contribution is the exact internal-state identification, direct fixed-state seed, complete canonical domain, proof of one fixed cycle with a four-state basin, all 15 cycle lengths, and exhaustive transient/component statistics.  A bounded online search found no prior publication of the maximum-total seed/result or the specific direct fixed-state seed, but this is not proof against unindexed or unpublished work.  See `SOURCES.md` for attribution and search limits.

Only 79,440 states lie directly on cycles.  The remaining 2,935,933,360 states are in trees feeding those cycles.

## Exact histogram statistics

These statistics are weighted by canonical starting states -- not by distinct lengths and not by components.

| Measure | `mu` | `lambda` | `mu+lambda` |
|---|---:|---:|---:|
| Minimum | 0 | 1 | 1 |
| Mean | 20,890.406768 | 48,021.124501 | 68,911.531269 |
| Median | 19,313 | 58,078 | 71,870 |
| 90th percentile | 41,396 | 58,078 | 98,244 |
| 95th percentile | 45,193 | 58,078 | 103,113 |
| 99th percentile | 51,317 | 58,078 | 109,395 |
| 99.9th percentile | 54,937 | 58,078 | 113,015 |
| Maximum | 58,681 | 58,078 | 116,759 |

Counts near the maximum:

| At least this `mu+lambda` | Starting states | Share |
|---:|---:|---:|
| 100,000 | 244,218,266 | 8.31802% |
| 110,000 | 21,594,525 | 0.735505% |
| 115,000 | 578,729 | 0.0197114% |
| 116,000 | 164,008 | 0.00558608% |
| 116,500 | 15,470 | 0.000526905% |
| 116,700 | 1,775 | 0.0000604561% |
| 116,750 | 103 | 0.00000350816% |
| 116,759 | 1 | 0.0000000340598% |

The deterministic 1% pilot was impressively close: exact versus pilot means differed by about 1.26 for `mu`, 3.28 for `lambda`, and 2.02 for `mu+lambda`; the total median was exactly 71,870 in both.  The pilot nevertheless missed the length-1 and length-3 cycles, demonstrating why sampling could not prove the rare-component inventory.

## Recommended seeds

### Maximum internal nonrepeat length

```basic
X=RND(-4.33901453)
```

Exact internal evidence:

```text
parsed negative FAC: 83 8a d9 35 00
resulting RNDX:      76 57 66 2a 0c
canonical rank:       2,900,100,616
mu:                              58,681
lambda:                          58,078
mu+lambda:                      116,759
number of canonical states with that total: 1
```

After seeding, successive `RND(1)` calls reach the cycle after 58,681 advances.  The state seen at advance 58,681 appears again at advance 116,759 and every 58,078 advances thereafter.

### Simpler maximum-period seed

```basic
X=RND(-1)
```

This is easier to explain and still enters the longest cycle:

```text
resulting RNDX: 68 00 81 00 00
mu:                      35,736
lambda:                  58,078
mu+lambda:               93,814
```

Use the long literal only when maximizing the distinct internal prefix is the point of the demonstration.  For ordinary reproducibility, `RND(-1)` is clearer.  Neither choice guarantees good multidimensional distribution or independence.

## Small complete orbit

No cycle of length five exists.  The nearest compact example selected is `mu=5`, `lambda=7`:

```basic
10 X=RND(-.311306466)
20 FOR I=0 TO 18
30 PRINT I;X
40 X=RND(1)
50 NEXT I
```

The literal parses to negative FAC `7f 9f 63 8f a5` and creates seed `80 25 8f 63 9f`.  Its complete unique orbit is:

| index | five-byte state | approximate value | role |
|---:|:---|---:|:---|
| 0 | `80 25 8f 63 9f` | 0.6467191947 | ramp |
| 1 | `80 58 54 75 eb` | 0.8450387667 | ramp |
| 2 | `80 66 94 2d 9a` | 0.9006985188 | ramp |
| 3 | `7f 78 e2 89 47` | 0.4861033343 | ramp |
| 4 | `80 57 bd 3a b1` | 0.8427311594 | ramp |
| 5 | `80 12 7f c2 99` | 0.5722619651 | cycle entry |
| 6 | `80 2d 08 77 d0` | 0.6759104617 | cycle |
| 7 | `80 57 8a 0a f6` | 0.8419501162 | cycle |
| 8 | `7e 09 06 7a 62` | 0.1338137743 | cycle |
| 9 | `7d 4b b8 66 15` | 0.09947280647 | cycle |
| 10 | `7e 77 78 fe 42` | 0.2416724899 | cycle |
| 11 | `80 57 bd 3a b0` | 0.8427311592 | cycle |
| 12 | `80 12 7f c2 99` | repeats index 5 | repeat |

Indexes 4 and 11 differ in the last state byte even though BASIC's formatted decimal output may make them look identical.  That is a useful demonstration of why internal five-byte equality, not printed text, was used.

Prepared artifacts:

- `visualization/small-mu5-lambda7.bas`
- `visualization/small-mu5-lambda7.json`
- `visualization/small-mu5-lambda7.dot`
- `visualization/small-mu5-lambda7.svg`

## Visualization recommendations

A literal node-and-edge drawing of 2.936 billion states would be unreadable and enormous.  Use several truthful views instead:

1. **Cycle/basin bar chart:** all 15 cycle lengths with start counts on a log scale.  This immediately shows the 58,078 and 724 giants without hiding the one- and three-cycles.
2. **Survival curve for `mu+lambda`:** answers “what fraction gives at least N distinct internal states?” This communicates near-maximum options better than a conventional histogram alone.
3. **Binned `mu+lambda` histogram:** log-count bars expose both the main mass and rare tail.
4. **Component/depth atlas:** one column per component, vertical depth=`mu`, color=count.  Normalize brightness per component but print absolute basin percentages so small components remain visible without misleading the viewer.
5. **Selected literal subgraphs:** render complete small examples in DOT/SVG with state bytes.  This is the only scale at which literal nodes and edges are pedagogically useful.
6. **Optional Hilbert/rank atlas:** color canonical ranks by component or depth.  This can be visually striking, but must be labeled as an encoding-space atlas; neighboring pixels are not necessarily graph neighbors.

Avoid a force-directed layout of all states.  Even if technically tiled, it would imply spatial/topological information that the aggregate data does not preserve.

Standalone tools now provided:

```text
analyze_final_histograms.py   exact weighted statistics and checksums
render_histograms.py          three-panel standalone SVG
export_component_depth.c      stream 10.94-GiB metadata to exact joint counts
render_component_depth.py     aggregate whole-graph component/depth SVG
render_small_graph.py         DOT and standalone SVG for selected small orbit
```

Generated views:

```text
visualization/rnd-histograms.svg
visualization/rnd-component-depth.svg
visualization/small-mu5-lambda7.svg
visualization/small-mu5-lambda7.dot
```

The SVGs open directly in a browser and require no Python packages.  Graphviz is optional if a different rendering of the DOT file is desired.

## Method and validation

The transition oracle was generated from the hash-pinned stock ROM control flow and retains exact 6502 registers, flags, stack, wrapping, FAC scratch, guard-byte, and rounding behavior.  It uses no host floating point.  It was differentially checked against an independent Python 6502 ROM interpreter, supplied vectors, one million-step stream digests, randomized starts, GCC, Clang, ASan, and UBSan.

The full runner classified every canonical state once using a restartable 4-byte direct-index table.  Final checks established:

- all metadata states classified;
- `mu`, `lambda`, and `mu+lambda` histogram totals each equal 2,936,012,800;
- cycle-node counts are divisible by their cycle lengths;
- the resulting component count is exactly 15;
- exact output hashes were retained;
- an independent post-run streaming pass exported all 2,936,012,800 `(component,mu)` assignments in 7.97 seconds and reproduced the same maximum `mu`.

`test_final_report.py` additionally re-runs the pinned BASIC decimal parser for both recommended literals, verifies their exact FAC and seed bytes against metadata, and reproduces the complete small orbit.

## Scope boundaries

The exhaustive denominator is the closed canonical post-shuffle state domain, not:

- all arbitrary five-byte FAC bit patterns;
- all `2^40` nominal byte combinations;
- all BASIC decimal literals or expressions;
- the much larger immediate image of every valid negative FAC input;
- the `RND(0)` timer path.

The canonical domain contains 2,936,012,800 states, exactly `$AF000000` and 68.359375% of `2^32`.  Its key is an enumeration rank that includes exponent distinctions; it is not merely the four payload bytes of `RNDX`.

## Sources

- Microsoft, “Microsoft BASIC for 6502 Microprocessor — Version 1.1” (official MIT-licensed historical source; lineage reference, not an exact C64 BASIC V2 build): https://github.com/microsoft/BASIC-M6502
- Michael Steil, “Microsoft BASIC for 6502 Original Source Code [1978]” (2015): https://www.pagetable.com/?p=774
- Michael Steil, “Create your own Version of Microsoft BASIC for 6502” (2008): https://www.pagetable.com/?p=46
- Reconstructed multi-target Microsoft BASIC source: https://github.com/mist64/msbasic
- Forum64, “Die Fehler des BASIC V2” (RND discussion in 2014): https://www.forum64.de/index.php?thread/46576-die-fehler-des-basic-v2/
- Forum64, “R.I.P. RND(1)” (2020–2023): https://www.forum64.de/index.php?thread/103072-r-i-p-rnd-1/
- Source revision inspected for this report: `2a0bc2fe0db13f8cf1b5c40b1d5617263cdb9cb4`
- Pinned C64 BASIC ROM SHA-256: `89878cea0a268734696de11c4bae593eaaa506465d2029d619c0e0cbccdfa62d`
- Pinned C64 KERNAL ROM SHA-256: `83c60d47047d7beab8e5b7bf6f67f80daa088b7a6a27de0d7e016f6484042721`

## Reproduction and provenance

These are retained exhaustive results, not a fresh run.  Use `REPRODUCE.md` for compact validation, external ROM requirements, and the separate expensive reproduction gate.  `SEED_REFERENCE.md` preserves the negative-seed proofs, and `VALIDATION.md` records oracle and restart evidence.  ROM-derived generated C remains explicitly unresolved pending owner decision; see `SOURCES.md`.
