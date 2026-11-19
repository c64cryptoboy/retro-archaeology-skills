# Reconstruct a registered animation

Use `animation.py` when you know which artwork to draw, where to draw it, and how long the completed pose lasts.  It preserves the native bytes and index planes alongside the movie, so a reader can distinguish a moving sprite from a moving crop, and an opaque black dot from a hole.  It does **not** infer a sequence from neighboring sprite pointers or turn one snapshot into evidence of motion.

## Try it with original synthetic art

From the skill directory, run:

```sh
python3 example.py demo-input
python3 extract.py demo-input/capture.json demo-art --only sprites --slots 0 1
```

Save this as `sequence.json` next to `demo-art`.  This is an invented sequence using the example's two appearances, not observed gameplay.  The frame IDs label completed poses; `layers` lists what to draw back to front.

```json
{
  "format": "c64-animation-v1",
  "origin": [64, 80], "size": [28, 21],
  "clock": {"label": "example scheduler ticks", "hz_num": 60, "hz_den": 1},
  "source_loop": [0, 3], "movie_repeat": true,
  "assets": {
    "body": {"sprite": "demo-art/slot0.bin", "multicolor": true, "own": 3, "shared_0": 2, "shared_1": 7},
    "ink": {"indices": "demo-art/slot1.idx", "size": [24, 21]}
  },
  "frames": [
    {"id": "rest", "hold": 12, "base": "clear", "layers": [{"asset": "body", "at": [64, 80]}]},
    {"id": "accent", "hold": 7, "base": "previous", "layers": [{"asset": "ink", "at": [66, 80]}]},
    {"id": "shift", "hold": 8, "base": "clear", "layers": [{"asset": "body", "at": [66, 80]}, {"asset": "ink", "at": [68, 80]}]}
  ]
}
```

```sh
python3 animation.py sequence.json demo-poses
python3 animation.py sequence.json demo-movie --gif
```

Open `demo-poses/frame-0001.png`, compare its registered artwork with `frame-0000.png`, and inspect `demo-poses/manifest.json`.  The second command additionally produces `demo-movie/animation.gif`.  The callable is `export_animation(sequence_path, output_dir, *, gif=False)` in `animation`; it returns the output manifest.  Supply a new directory with an existing parent for each export.  Only a completed export has a manifest.  Nothing is written back to the inputs.

## Input and output contract

- **Stage and color:** `size` is `[width,height]` in native square dots and `origin` is the shared upper-left `[x,y]` in the source coordinate system.  `at` is an absolute top-left in those same units.  The whole layer rectangle must fit; choose a stage large enough rather than recentering each frame.  `background` is one VIC index or 255 (transparent, the default).  Optional `crop: [left,top,width,height]` is stage-local and fixed across all frames.  Optional integer `scale` performs nearest-neighbor replication after the crop; the default is 1.  Compare discarded margins across **all** frames before calling them padding.  Indices are authoritative; the 16 RGB swatches recorded in the output are the skill's illustrative display palette, not a calibrated monitor.
- **Native source:** each `sprite` file is 63 pattern bytes, optionally followed by its original alignment byte.  No PRG header.  Hires requires `own`; multicolor additionally requires `multicolor: true`, `shared_0` (pair 01), and `shared_1` (pair 11).  Pair 10 is the slot's `own`; pair 00 is transparent.  Native color pairs occupy two dots before any declared `expand_x` or `expand_y` hardware doubling (booleans, default false).  A nominal 24 by 21 sprite is not 12 square pixels wide.  Link different blocks for different poses, or reuse a block with different color/expansion settings under a second asset ID.  Include enabled slots only, or explicitly supply their captured clear index planes.
- **Registered composites:** an `indices` file plus its `size` is a predecoded row-major layer, one byte per dot, values 0 through 15 or 255.  Use it for an independently established composite, an extracted `slotN.idx`, or a rectangular patch.  Do not pass packed sprite bytes as indices.  Retain the capture/decoder provenance for upstream layers.  Paths are relative to the descriptor.  Register all slots against one anchor; draw a multi-slot character as one ordered layer list per pose.  The tool applies your stated order, not guessed VIC priority, collision, background masking, border clipping, or multiplexing.
- **Drawing:** `base: "clear"` starts a new standalone frame at the declared background; `base: "previous"` carries the preceding completed stage.  Frame zero must start clear.  `draw: "over"` (default) skips transparent source dots; `draw: "replace"` copies the full rectangle, including holes.  An absent overlay is not an instruction to erase the old one.  Choose clear, carry, or overwrite from source drawing behavior, not from whether a changed rectangle resembles a new picture.  A sparse positional overwrite is not XOR: map unwritten dots to 255 for `over`, but preserve *written* black as index 0.  If source bytes really are XOR differences, reconstruct them at their native bit depth first; neither layer operation means XOR.  Empty `layers: []` can represent a true blank or a held image, depending on the base.
- **Native evidence:** `asset-NNNN.bin` preserves each declared input as-is, including a sprite's optional pad byte.  `manifest.json` records the input descriptor hash, exact source links, sizes, hashes, layer order, positions, draws, holds, and fractions.  `frame-NNNN.idx` is the **entire uncropped, unscaled** completed stage in native indices, with a SHA-256 per pose.  The corresponding PNG and GIF show the crop and scale, not new source samples.  For a supplied index plane, the source copy proves those indices, not recovery of the upstream packed bytes.

## Timing and source loops

`hold` is a positive number of ticks **after** drawing the listed frame.  The tick frequency in Hz is the exact rational `hz_num / hz_den`; name the actual timebase in `clock.label`.  For a timer-driven source, a tick might be several eligible interrupts, not one video refresh.  Record the observed register setup, gating/divisor, video standard, and startup versus steady-state countdown separately.  Without that evidence, label an illustrative clock as such.  The output records `start_tick` (inclusive), `end_tick` (exclusive), and `seconds: [numerator,denominator]`.  These are scheduled completed poses, not progressive drawing times, pauses, or measured display latency.

`source_loop` is `[first_frame,end_exclusive]` in the supplied frame list, or `null` for unknown/absent.  It records a source transition *after the final hold*, without issuing another draw.  `movie_repeat` is independent: true replays the **entire** exported list from frame zero; false plays it once.  For an intro at 0 and a source loop `[1,4]`, repeating a movie of `0,1,2,3` incorrectly reintroduces the intro if described as steady source playback.  Export the intro once and provide a separate steady `1,2,3` movie initialized from its established full starting pose, or explicitly list observed passes in a finite movie.  For deltas, check the resulting wrap pose against a second source pass: a reset pointer need not restore pixels or a startup divider.

GIF delays are `round(100 × end_time) - round(100 × start_time)` centiseconds, exact rational arithmetic, ties to even.  Rounding each hold alone can drift.  A single encoded loop is quantized once, so its small rounding error can still accumulate across repeats.  An unrepresentable delay (zero or above 65535 centiseconds) refuses GIF output rather than altering the schedule.  The native output still supports those holds.  Actual viewers may clamp short delays.  Each GIF image is a complete rendered stage view with its own delay and restore-to-background disposal.  Identical and fully transparent frames retain distinct entries.  The exporter reopens the GIF and requires matching frame count, dimensions, replay flag, RGBA bytes, and delay at every frame.

## Dependencies and independent check

Python 3.10 or newer and the standard library suffice for native bytes, indices, PNGs, and scheduling.  Only `--gif` (encoding **and** decode-back) needs Pillow; for example, use a disposable `python3 -m venv .venv` and `.venv/bin/python -m pip install Pillow`, then run the command with `.venv/bin/python`.  No system install is needed.  From the skill directory:

```sh
python3 -B -m unittest discover -s tests -p test_graphics_animation.py -v
```

The test's original tick-driven two-slot puppet paints from explicit dot coordinates, independently of the descriptor and sprite decoder.  It compares all eight ticks, including two separate cues with identical pixels, a transparent replacement, and disappearance.  Wrong frame order, shifted hold, and reversed slot order all preserve the run length but disagree with the original.  With Pillow available, the test additionally checks both movie repeat settings, the composited RGBA planes, and the stored delays against that runner.  Without Pillow it checks explicit GIF refusal; it does **not** claim a GIF was decoded.  For another program, supply independent source execution or equivalent evidence for bytes, indices, order, holds, and the wrap before claiming fidelity.
