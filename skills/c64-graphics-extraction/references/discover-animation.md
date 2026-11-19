# Recover a sprite loop from displayed fields

To find the shortest loop a player actually saw, compare the whole actor at the same point in successive strides.  A pointer cycle is a lead, not a playback schedule: a disabled slot can cycle, and a program can redraw a shape without changing its pointer.

1. **Pair state with display.** Record the edition, video standard, starting state, input changes, and field clock.  Capture a steady action for at least two candidate cycles.  Keep separate columns for the sampled field and raster line, and for the displayed field.  Use a visible change to check which picture the sample predicts; a long hold cannot distinguish a one-field error.  If a slot is reassigned partway down the screen, log its state at each relevant raster band.  Without that evidence, report the sampled layers, not a reconstruction of the field.
2. **Build one row per actor slot per displayed field.** Record enable, pointer resolved through the active VIC bank and screen, identity of the fetched shape, full X and Y, colors, mode, expansion, and priority.  Keep the original block for provenance, but exclude its alignment padding from visible shape comparisons.  Group slots by checking that their ordered composite follows the actor in the picture, not merely that they move together.
3. **Remove travel, not acting.** Measure the common displacement against a stable gameplay reference.  Keep that travel as a separate track; subtract the same displacement from every layer.  Use one canvas and pivot for the whole cycle.  Do not center each silhouette or pin an independently bobbing part.  Compose enabled layers back to front in native color indices, keeping transparent dots distinct from opaque black.

### Worked ledger (invented)

Each cell gives `pointer:shape @ (x,y)` at display time.  Both slots are enabled, with fixed colors and modes.  The rear plate is a stable reference; a visible front lamp changes from a ring to a bar in the same storage.  Common travel is four dots right per field, with no vertical travel.

| Display field | Rear plate | Front lamp | Lamp relative to plate | Registered pose |
|---:|---|---|---|---|
| 0 | P:plate @ (40,60) | Q:ring @ (48,64) | (8,4) | A |
| 1 | P:plate @ (44,60) | Q:ring @ (52,64) | (8,4) | A |
| 2 | P:plate @ (48,60) | Q:bar @ (57,63) | (9,3) | B |
| 3 | P:plate @ (52,60) | Q:ring @ (60,64) | (8,4) | A |
| 4 | P:plate @ (56,60) | Q:ring @ (64,64) | (8,4) | A |
| 5 | P:plate @ (60,60) | Q:bar @ (69,63) | (9,3) | B |

With the plate at local `(0,0)`, hand the renderer two ordered layer lists: **A** = plate, then ring at `(8,4)`, held two field ticks; **B** = plate, then bar at `(9,3)`, held one.  Loop back to A **after** B’s hold.  Field 3 confirms the wrap; it is not an extra terminal pose.  The pointers alone predict no change at all.

### Finite actions: keep the landing

A jump or throw need not wrap.  Capture the approach, action, landing, and enough subsequent ordinary motion to establish the boundary.  For a jump, retain the whole trajectory on one stage.  Measure both the anchor slot and the lowest visible dot against a stationary background: tucking limbs can increase clearance without moving the anchor.  A disabled layer contributes no ink, even when its pointer still changes.  Compare against the same approach without the triggering input; a second useful control holds each pose’s lowest dot at ground level.  Check vacated pixels as well as the moving silhouette, preserve the landing hold, and export a finite GIF with no loop extension.

### Decide between competing loops

- **Seven poses or fourteen?** Treat both as hypotheses.  At each displayed field, substitute the corresponding pose from the other half at the *correct* travel position.  Compare the full registered color planes and holds, not just pointers, outlines, or one body part.  One visible accent that differs rejects the seven-pose repeat; it does not by itself establish fourteen distinct pictures.  Count distinct planes separately, and verify the longer ordered schedule across a second pass.  If only an obscured layer differs, report a layer difference, not a visible pose.
- **Opposite direction or different starting phase?** Capture the opposite input; do not manufacture it by flipping the first movie.  Remove its travel independently.  Test every cyclic start in forward time, first unchanged, then horizontally reflected on the same canvas.  Require agreement of colors, transparency, and exact holds; report ties.  Reverse order is a separate hypothesis.  A reflected match at a nonzero phase establishes equivalence of the two recorded loops, not what the game does at the instant of turning.
- **Check against display.** Put each registered pose back at its recorded position over an independently observed background.  Compare the actor rectangle, holes included, against each field of a video-only replay with the same inputs.  At a visible change, try the adjacent *different* pose or shift a hold by one tick.  If the wrong schedule passes too, that region or interval cannot establish the distinction.  A GIF that decodes correctly verifies the export, not the capture.

To recover the code that produces a sequence, trace the writes to **every** participating sprite pointer back to their table, index, and conditional offsets.  Two slots can read a repeating table while a third selects a different overlay on the second pass.  Trace the hold counter separately: which interrupt increments it, which foreground comparison consumes it, and whether the sample is before or after that update.  Seed the model once with the first observed phase and counter, and predict subsequent fields without feeding their observations back in.  A shifted start that still predicts the main body, or a wrong delay that occasionally produces the right pose, tests whether the other layers and timing really distinguish your explanation.

Use field ticks only when they describe the observed holds.  For a bitmap drawn in pieces, compare completed planes instead: distinguish untouched dots from writes of black, test overwrite versus XOR on a nonzero destination, and time the final hold from the actual scheduler.  If only decoder and timer evidence exists, label the result a scheduled reconstruction, not observed gameplay.

**A timer tick is not necessarily one video field.**  If an independent CIA timer switches bitmap banks, count timer underflows between bank changes and separately count the displayed fields between completed poses.  A capture can straddle the switch: compare its changing dots against both adjacent poses, and list it as a transition field instead of silently accepting the nearer pose or inventing another full pose.  Repeated integer field counts over a few loops do not establish an integer long-term period when the two clocks differ.

**Preserve the stored canvas; crop copies for presentation.**  A black strip common to every observed pose may be encoded artwork, not a limit on what the decoder can draw.  Check the edge on every completed pose and retain the full bytes and placement in the master.  To distinguish a stored margin from a decoder clip, change only an edge selector in a disposable input and follow the original write.  If it paints color there, cropping is an editorial choice.  Label the changed control as such; it is not original art.
