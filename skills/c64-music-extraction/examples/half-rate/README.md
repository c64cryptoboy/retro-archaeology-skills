# Half Rate: a SID volume-write experiment

Can you hear a periodic sound when none of the three voice gates is on?  These two original C64 PRGs execute the same loop.  One stores 8 over and over at `$D418`; the other stores 2, 14, 2, 14.  The mean volume code is 8 in both.  `$D418` bits 4 through 7 remain zero: no filter response is selected, and the voice-3 dry path is not disconnected.  Neither program starts an oscillator note.

Build in a new directory with cc65's assembler and linker.  Here `src` is the directory containing this README:

```sh
ca65 -D TOGGLE=0 "$src/half-rate.s" -o constant.o
ld65 -t none -S 0x07ff constant.o -o constant.prg
ca65 -D TOGGLE=1 "$src/half-rate.s" -o toggle.o
ld65 -t none -S 0x07ff toggle.o -o toggle.prg
```

Autostart one PRG on a fresh NTSC C64 emulator with a 6581 SID; use a fresh instance for the other.  Each begins with `10 SYS2061`, disables display DMA and maskable interrupts, clears all writable SID registers, and runs until reset.  Do not expect a visible UI.  Load address is `$0801`; the two bytes preceding the BASIC line in the file are the PRG prefix.  The linked programs differ only in the last two bytes (the level table).

**How to check it.**  The program puts `VDG` at `$C001` through `$C003` just before it enters the loop.  The byte at `$C000` counts loop stores modulo 256; read once per video field and add modular differences.  Each loop costs 1,024 uninterrupted CPU cycles.  At about 1.023 MHz that is about 999 stores/s, but only about **499 complete low/high cycles/s**.  Look for the latter frequency, not the former, in the alternating PCM.  Check the same frequency in the constant PCM.  Leave time for startup transients.  Actual levels depend on the emulated SID and signal path; codes are not calibrated volts.

The `*-schedule.csv` files cover all 25 initialization stores and four loop stores (two low/high periods in the alternating arm).  Their timestamps are instruction-end cycles from a CPU-only execution starting at `$080D`, not captured analog or full-machine bus times.  They keep repeated identical stores.  A gate-only event list is empty in both cases: recording the volume writes with timing, or recording PCM, retains a distinction that a list of note-ons discards.
