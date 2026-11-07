# Timing policy

## Ordinary

Byte size is the primary objective, but report best/typical/worst cycle changes and changed intermediate effects. Ordinary does not mean timing is automatically irrelevant; it means the artifact contract permits the selected changes.

## Interrupt

A reduction is admissible only when it is no slower on every affected declared path. Local Stage-1 rules remove fixed-cycle instructions or fuse same-address loads, so they satisfy this requirement. Later branch/loop rewrites require pathwise comparison, final-address branch/page effects, entry/exit overhead, and relevant hardware stalls.

A handler's unused housekeeping can be bypassed only under an explicit application contract. For example, a C64 handler entered through the stock `$FF48` dispatcher may jump to `$EA81` for `PLA; TAY; PLA; TAX; PLA; RTI` when CIA/KERNAL keyboard, clock, and cursor work is deliberately unnecessary and interrupt sources are handled appropriately.

## Cycle-exact

Refuse automatic rewriting. Indicators include:

- NOPs or otherwise unnecessary instructions forming visible padding;
- branch alternatives engineered to equal cycle totals;
- raster-line polling and timed VIC writes;
- Apple II speaker/audio loops;
- 1541 bit loops and fast-loader bus code;
- self-modifying delay constants;
- comments/tables naming PAL/NTSC cycles;
- repeated unrolled operations adjacent to I/O.

Detection is advisory and incomplete. The user/artifact contract remains authoritative, but do not silently optimize through obvious indicators.

## Unrolled loops

Preserve apparent unrolling by default in every policy. A separate user-approved transformation may roll it up only after recording the original timing purpose, new worst-case cycles, deadline/headroom, and hardware consequences. Merely finding repeated instruction sequences is not permission to outline or loop them.
