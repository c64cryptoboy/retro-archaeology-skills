# Attribution, design evidence, and provenance

Credit earlier fixed-point discoveries separately from exhaustive graph classification.  Historical source explains lineage and broad design intent; it is not an exact build identity or a license grant for the C64 ROM.

## Bundled derived code: unresolved redistribution status

`generated_rnd_cycle.c` and `scratch/generated_fin.c` mechanically specialize the pinned Commodore/Microsoft ROM control flow.  Both are retained with explicit provenance and licensing uncertainty pending the owner’s decision; they must not be presented as cleared or relicensed authored code.  ROM binaries are not bundled.  See the sibling ROM-reference [sources](../../c64-rom-reference/references/SOURCES.md) and repository [notices](../../../THIRD_PARTY_NOTICES.md).  The ChiptuneSAK-derived interpreter retains its source attribution and `CHIPTUNESAK_LICENSE.txt`.

## Constants and historical source

### Direct historical evidence

Microsoft's official MIT-licensed `BASIC-M6502` repository contains the ancestor of this RND routine.  Its comments say that the next value is formed by multiplying the previous value by “a random constant” and adding another “random constant.”  The source lineage also identifies the multiplier as being of order `2^24` and the addend as being of order `2^-24`.

The official source explains the byte exchange explicitly: the high and low bytes are switched to give a random chance of obtaining a result below or above `0.5`.  It then places the old exponent where normalization shifts it into the significand, forces a new exponent, normalizes, and saves the result.

This is stronger evidence for the broad design intent than modern reconstruction.  It does not document how the exact bit patterns were selected, whether alternatives were tested, or any proof of period/distribution.

### Interpretation

The C64 constants are:

```text
A = 11,879,546 = $B5447A                    (order 2^24)
C = 3.927677738602142e-8                    (order 2^-24)
  = $A8B146 / 2^48 exactly
```

Both are inherited 24-bit-looking patterns followed by a zero low byte in the C64's wider approximately 32-bit significand format.  Together with the 1975 comments, this strongly suggests a generator originally designed around the earlier 24-bit/six-digit floating package and later carried into nine-digit BASIC, rather than constants newly optimized for the C64's complete state graph.

The likely intentions were:

- a large multiplier near the significand scale to move and change many significant bits;
- a tiny nonzero addend near the opposite precision scale to perturb low-order state and avoid a purely multiplicative recurrence;
- byte exchange to move low-order changes into high-order positions and balance outputs around `0.5`;
- exponent injection and normalization to fold the result back into the output range.

The exact constants are described only as random constants in the surviving comments.  Claims that they were selected by a particular number-theoretic test, are primes, or satisfy LCG full-period criteria are unsupported.  The multiplier is even, and the exhaustive C64 graph has 15 components with maximum cycle 58,078 rather than a full-period integer-LCG structure.

### Family classification

The closest broad family is an affine/congruential-style multiply-add generator, but the complete transition is better called a **scrambled floating-point affine generator**:

```text
state -> floating multiply-add -> mantissa byte permutation
      -> exponent injection -> normalization/rounding -> next state
```

It is LCG-like in its affine core but is not mathematically the textbook integer recurrence `(a*x+c) mod m` over a fixed modulus.

### Sources and licensing

Preferred official source:

- Microsoft, `BASIC-M6502`: https://github.com/microsoft/BASIC-M6502
- inspected commit: `7460af2c03ae19c0e60ff327489229d2005b9357`
- relevant file: `m6502.asm`, “POLYNOMIAL EVALUATOR AND THE RANDOM NUMBER GENERATOR”
- repository license: MIT, copyright Microsoft Corporation

The official repository describes Microsoft BASIC for 6502 Version 1.1 and includes PET-oriented conditional code.  It is historical lineage evidence, not an exact source/build identity claim for the later C64 BASIC V2 ROM or Commodore's separate KERNAL.

The earlier published Altair printout/OCR independently preserves the `2^24`/`2^-24` comments, but its mirror states no license.  The official MIT repository now supplies the preferred source for routine comments; no source listing is copied into this project.

## Prior Forum64 findings

Primary source thread: “R.I.P. RND(1),” Forum64, 9 June 2020 through 21 August 2023:
https://www.forum64.de/index.php?thread/103072-r-i-p-rnd-1/

Earlier source thread: “Die Fehler des BASIC V2,” especially pages 23 through 25 in March 2014:
https://www.forum64.de/index.php?thread/46576-die-fehler-des-basic-v2/

All 54 posts across the three pages of “R.I.P. RND(1)” were reviewed through archived captures.  The relevant surrounding pages of the earlier thread were also reviewed after the later thread pointed back to it.  This file is a factual English summary, not a copy or full translation.  No forum license was identified.

### Main findings in the thread

1. **Observable fixed behavior and a practical seed.** Mike opened with an exactly constructed seed magnitude `1658186197 / 2^31` (written as products to avoid BASIC literal-conversion loss).  After negative seeding, every printed `RND(1)` is `.166823086`.  Several participants reproduced it in Commodore emulation.

2. **How the seed was found.** Mike later explained that he swept increasingly fine odd dyadic fractions through `[0.5,1.0)`, deliberately keeping the CBM floating exponent fixed, and compared two consecutive positive outputs after each negative seed.  A weekend search in VICE 1.16 xvic at roughly 200x warp eventually found exact equality.  His expectation that a fixed point should exist motivated the search, although a fixed point is not guaranteed for every finite functional graph.

3. **Equivalent source arguments.** Atomcode observed that multiplying or dividing the numerator by powers of two could preserve this particular seeding behavior, subject to BASIC decimal-conversion and rounding details.  This exponent equivalence was explicitly noted as special rather than general.

4. **Large integer brute force.** Atomcode used the C-translated `cbmbasic.exe` and tested integer seed magnitudes from 1 through two billion.  It took several hours and found only `1658186197` producing immediate repeated positive outputs in that interval.  The test did not cover fractional inputs, delayed entry into a short cycle, or the final 29,345,301 integers before our later direct fixed-state integer `2029345301`.

5. **Effective-width reasoning.** Mike argued that the feedback process carries roughly 32 effective bits rather than all possible five-byte FAC encodings, and that his fixed-exponent sweep covered those mantissa possibilities for the particular immediate-equality search.  The thread did not derive the exact closed canonical domain or classify its functional graph.

6. **Short cycles and approximate maximum.** Mike referred to earlier work that entered a cycle of about 700 values after warming up.  The referenced 2014 thread supplies the details: `RND(-7621)`, followed by 100,000 warm-up calls, was reported with period 723; Mike said other seeds frequently gave 58,077.  These are one less than our exact cycle lengths 724 and 58,078, consistent with his BASIC counter counting intervening values rather than all nodes in the closed cycle.  He also hypothesized “thousands” of separate cycles of those lengths and recognized one-time feeder states.  Our exhaustive result instead finds one component/cycle of each length.  In 2023 he stated that the maximum reachable period was approximately `2^16`, but neither thread presented a complete cycle inventory or proof.  The exact maximum is `58,078`.

7. **Simpler BASIC spelling.** In 2023 Mike replaced the original large product expression with `8008/10371`, a continued-fraction approximation accurate enough when evaluated directly inside `RND(...)`.  Atomcode showed an important FAC-rounding subtlety: direct `RND(-8008/10371)` works, but assigning the quotient to a variable first and then passing that variable does not.  He gave `809661.229` and integer `1658186197` as forms that survive the intermediate assignment.

8. **Suggested replacement.** Mike supplied a 6502 implementation of the Numerical Recipes QDRand 32-bit LCG and later a C64 `USR()` wrapper, claiming its full `2^32` period.  He also warned that this generator still has statistical defects for some transformations, such as summing outputs to approximate a Gaussian distribution.

### Related side discussion

Participants corrected an early claim that BASIC RND reads SID noise.  They distinguished the positive pseudorandom recurrence from `RND(0)`, which samples CIA timer/time-of-day registers.  They also discussed SID's 23-bit noise LFSR, user-timed seeding, emulator startup determinism, and other entropy sources.  These were useful side topics but were not the main fixed-point discovery.

### Exact comparison with the later exhaustive analysis

The thread's integer seed can now be located precisely in the complete graph:

```text
RND(-1658186197)
    -> internal RNDX 80 2a d3 ab c6
    -> mu = 1, lambda = 1

one positive advance
    -> fixed RNDX 7e 2a d3 ab c6
```

Thus the thread found a source-level route to a state one step before the fixed point.  Its first printed positive output is the fixed point, so every later output is identical.  The shorter decimal `-809661.229` maps to the same one-step predecessor.

Our later `RND(-2029345301)` maps directly to the fixed-point state itself.  Notably, its magnitude is just above the thread's integer brute-force ceiling of two billion.

The prior thread therefore established:

- that fixed output behavior exists;
- a practical exact BASIC seed family that reaches it after one advance;
- important expression-versus-variable rounding behavior;
- the `RND(-7621)` route to what was counted as a 723-step cycle, plus frequently observed 58,077 counts;
- the existence of feeder states outside cycles;
- and a good approximate upper bound near `2^16`.

It did **not** establish:

- the exact canonical population of 2,936,012,800 states;
- the exact inventory of 15 cycles and their lengths;
- that there is exactly one fixed-point cycle node;
- the four-state total fixed-point basin;
- every basin population and transient-depth distribution;
- maximum `mu=58,681`, exact maximum `lambda=58,078`, or maximum `mu+lambda=116,759`;
- or an exhaustive classification of every canonical internal state.

Accordingly, the existence of the one-cycle behavior and the original practical seed should be credited to the earlier work, while the complete graph, exact uniqueness/basin proof, and exhaustive statistics are new results of this project.

## Bounded prior-art search

A prior search covered exact and variant decimal, rational, FAC, and RNDX signatures for `RND(-4.33901453)` and `RND(-2029345301)`, including `9099573/2097152`, `83 8a d9 35 00`, `76 57 66 2a 0c`, and the paired statistics 58,681 and 116,759.  It checked web indexes, Sourcegraph, public GitHub issue/commit search, Stack Exchange, Hacker News, C64-Wiki, Forum64, and related indexed retrocomputing material.  Unauthenticated GitHub code search was unavailable.

No reviewed source published those exact maximum-total or direct-fixed-state results.  This is a bounded search, not proof against unpublished, unindexed, deleted, print-only, or differently described work.  Say “no prior published evidence was found,” not “nobody has ever found this.”  Mike’s and Atomcode’s earlier fixed-output and period work remains prior art regardless of the search outcome.
