# Capture single-SID writes with stock VICE 3.10

Use the `dump` **playback** device to keep the order, values, and inter-write CPU cycles that a once-per-frame register snapshot loses.  This is a sound-device write stream, not PCM, a PSID tune, a monitor log, or a bus trace.  No VICE patch, monitor connection, or ChiptuneSAK installation is needed.

## Capture

Use `x64sc` from a VICE 3.10 installation with its normal ROM data and software reSID.  Start in a writable directory and give the dump a **new filename**: the driver truncates its output on open.  For the supplied 77-byte `probe.prg`, run:

```sh
x64sc -console -default -model c64ntsc -sidextra 0 -sidenginemodel resid8580 -sound -sounddev dump -soundarg probe.dump +autostart-warp +autostart-delay-random -autostartprgmode 1 -limitcycles 10000000 -debugcart -autostart probe.prg
```

`-console` suppresses the UI; it does not start a monitor script.  `-debugcart` is only the example's exit device: the PRG writes zero to `$D7FF` when done.  Expect `Opened device 'dump'` (VICE may use backtick quotes), `DBGCART: exit(0)`, normal close, and a text file.  If the cycle limit is hit instead, don't accept a partial specimen.  This recipe was exercised with the 3.10 headless C64SC build, not every packaged UI.

For your own ordinary single-SID PRG, the acquisition flags are `-sound -sounddev dump -soundarg NEWFILE`.  Choose the correct machine/clock and one software SID; do not enable extra audio devices.  Start the program normally, capture a short uninterrupted window, and exit normally to flush the file.  You can omit the example's exit device and use the UI to quit.  Keep the raw dump, run configuration, logs, and evidence for the excerpt boundaries.  Do not use `-soundrecdev dump` or expect simultaneous audible playback from this output device.

## Import

```sh
python3 dump_to_csv.py probe.dump > all-writes.csv
```

Each raw row is `delta_cycles register_offset value` in decimal.  Output is `tick,address,value`; tick zero is the **first included write**.  Each subsequent tick is the previous tick plus that row's delta.  Rows with identical values or zero delta are not combined or sorted.  `$D400 + offset` is a **canonical** SID address, not the CPU's original address.  No initial latch values or end time are supplied.  Keep the raw first delta; it is not elapsed time since the start of a song.

For this probe, inspect the complete dump.  Our run has one startup store (offset 24, value 0), followed immediately by all seven program stores, ending at normal exit.  The seven offset/value pairs are `4/32, 0/52, 1/18, 4/33, 4/33, 4/33, 4/32`.  The first program delta includes startup time and can vary.  The included [`program.dump`](program.dump) is that observed, seven-line excerpt.  For a fresh run, confirm the boundaries before copying the seven original lines into a separate file; do not overwrite the reference.  Never apply that crop by convention to other programs.  Then:

```sh
python3 dump_to_csv.py program.dump > program.csv
python3 verify_probe.py program.csv
```

The check expects relative ticks `0, 6, 12, 18, 22, 347, 353`.  From this directory, interpret those writes with the same decoder used for a larger trace:

```sh
python3 ../trace_states.py sid program.csv --clock-hz 1022730 --tick-hz 1022730 --end-tick 354
```

Here `354` is an explicit analysis cutoff one cycle past the last write, **not** a duration reported by the dump.  Voice 1's known gate transitions occur at ticks 18 and 353.  The first control write establishes a latch, not an inferred attack.  For standard PAL the 3.10 C64 rate is 985248, not 1022730; take the rate from the actual machine configuration.  The audio sampling rate is not the tick rate.

## Admitted input

One bounded, continuous VICE 3.10 C64SC excerpt, default SID base, one enabled software SID, no other sound-producing expansion, no reset, device reopen, or clock change across it.  Bound the original session independently to less than 2³¹ emulated cycles (the probe uses a 10,000,000-cycle limit).  The implementation casts each delta to a C `int`.  Reject negative or out-of-range deltas; the text alone cannot detect all wraps, missing lines, mixed chips, or restarts.  Only offsets 0 through 24 are admitted because those are the SID write latches interpreted by the public decoder.  Other offsets are an error, not silently discarded.  No chip ID, full bus address, PC, bus phase, SID reads, oscillator/envelope trajectory, or audible result is recoverable from these triplets alone.
