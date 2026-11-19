# Hear the mixer, not a second attack

Play [Three Doors](three-doors.sid) with NTSC timing, an 8580 SID model, and filtering enabled.  Expect silence, an A4 for about two seconds, and then silence.  Voice 3's gate stays on throughout.  A transcription of the oscillator's pitch and gate alone misses both audible boundaries.

| Hold | Voice 3 into filter? | Filter response mixed? | Dry voice 3 muted? | Stable signal |
|---|---|---|---|---|
| Start | No | Low-pass | Yes | Quiet |
| Play call 120 | Yes | Low-pass | Yes | A4 |
| Play call 240 onward | Yes | None | Yes | Quiet |

In one 48 kHz reSIDfp 8580 recording (libsidplayfp 2.4.2), DC-removed RMS in three 0.8-second windows starting at 1, 3, and 5 seconds was **0, 910.39, and 0** signed 16-bit sample counts.  The middle window measured 439.85 Hz.  Other models need not give the same level or silence floor.  The dry-path disconnect does not prevent the oscillator feeding the filter, and routing the oscillator into the filter does not itself select an audible output.

The [original source](three-doors.s) uses 98 payload bytes.  The [write schedule](register-schedule.csv) records init at tick 0 and play calls starting at 1.  `tick` is a call coordinate, not a measured audio-onset timestamp.  Run the commands below from this directory with fresh output names.  The first command works without an emulator.  Rebuilding the 224-byte PSID also requires ca65 and ld65.

```sh
python3 ../../trace_states.py sid register-schedule.csv --clock-hz 1022727 --tick-hz 1022727/17095 --end-tick 361
ca65 three-doors.s -o player.o
ld65 -t none -S 0x1000 player.o -o player.bin
python3 ../../sidfile.py pack player.bin rebuilt.sid --load 0x1000 --init 0x1000 --play 0x1003 --clock NTSC --rate vbi --model 8580 --name 'Three Doors' --author 'Original routing study' --released 2026
cmp rebuilt.sid three-doors.sid
```
