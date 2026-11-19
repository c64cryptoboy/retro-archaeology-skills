# Replay a sprite slot used twice in one field

When the same slot drew two complete sprites in separate vertical bands, its final register state alone loses the upper sprite.  Render each tuple separately with the existing graphics core, then take only its rows.  Do not pass two copies of one slot to the static compositor as simultaneous sprites.

## Run the synthetic example

From this example directory, use Python 3.10 or newer.  No emulator, ROM, Pillow, or private files are needed.

```sh
python3 -B fixture.py demo-out
python3 -B -m unittest discover -s . -v
```

Open `demo-out/replay.png` (new directory required).  The 128 bytes in `shapes.bin` are two authored, 64-byte sprite blocks: a yellow arrow and a red ring.  The example uses slot 0 twice on a known blank background.  Its registered sprite tops are rows 35 and 130; row 100 separates the two bands.  The PNG uses the core's illustrative palette.

## Apply the recipe

Decode the evidenced slot from each state with `decode(state, only="sprites", slots=[slot])["sprites"][0]`.  Pass those layers in **display order**, the common decoded background, and your measured registration to `two_bands.replay(background, upper, lower, first_lower_row=cut, offset_x=dx, offset_y=dy)`.  The cut is the **first lower active-area row**, not a VIC raster register.  The two bands cover rows `[0, cut)` and `[cut, 200)`.  Each whole sprite height, not just its opaque dots, must fit its band.  The result is a 320 × 200 index plane suitable for `images.png`.

Use this only when the following are established independently of the proposed picture:

- Both tuples belong to the **same field and enabled slot**.  The correct position, pattern bytes, pointer, color, and mode were in effect for each complete appearance.  A pair of unrelated pauses is not evidence.
- The background, priority plane, and register-to-content registration apply to both bands, with no other visible sprites to explain.  The example tests unexpanded hires sprites fully inside the active area.
- A complete-row join is supported: all changes relevant to reuse occur away from the sprite dots, with no unresolved in-flight fetch or mid-line visual change.  The code checks geometry, not timing evidence.  Do not search for a cut that makes the output match.

Check the predicted masks against an independent unmerged field.  If a cut bisects a sprite, if only end-state data survive, or if a border or mid-line effect matters, this recipe is not evidence of the displayed field.
