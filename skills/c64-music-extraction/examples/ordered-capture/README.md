# Capture ordered SID stores with ChiptuneSAK (optional)

A player can raise a gate before or after setting its pitch and still leave the same registers at the end of the call.  This example records the stores themselves.  It uses the original `examples/glass-steps.sid` from the C64 music extraction skill: single SID at `$D400`, NTSC VBI, init `$1000`, play `$1003`, and subtune index 0.  `capture(path)` checks the file's SHA-256 before execution.  Only those shipped bytes are supported.

## Read the fixture without installing anything

Run these commands **from this example directory**.  Set `skill` to the directory containing `trace_states.py` and `examples/glass-steps.sid`.

```sh
skill=/path/to/c64-music-extraction
python3 -B "$skill/trace_states.py" sid glass-steps-writes.csv --clock-hz 1022727 --tick-hz 1022727/17095 --end-tick 119 > glass-states.json
```

For this original tune, the clock arguments **model** one play call per 17,095 NTSC CPU clocks.  No call spacing was measured.  Init seeds the latches at tick 0, before play call 0; the projection assigns **no duration** to init.  In the first interval, `writes` ends with the pitch low byte, high byte, and gate-on; `gate_edges` places that edge at write index 30 (zero-based, including init).  Voice 1 holds word 6430 until the next pitch, with its first gate fall at call 11.  The last fall is at 116, not the end of the excerpt.

## Regenerate only if you want to execute the player

Use an environment that can import [ChiptuneSAK 0.3.1 at revision `8759135`](https://github.com/c64cryptoboy/ChiptuneSAK/tree/8759135b5c9c26dc9da155b006c575243ba5304a) and its dependencies.  The `SidImport` hook is an implementation detail of **that revision**, not a stable API.  Its `setup.py` declares Python 3.8+, matplotlib, mido, more-itertools, numpy, and parameterized.  This example was exercised on Python 3.12.3.  An existing checkout on `PYTHONPATH` with its runtime dependencies suffices.  No install, download, test-resource setup, or library modification is performed by this example.  The stored CSV and the skill's default tests do not depend on this adapter.

```sh
python3 -B chiptunesak_capture.py "$skill/examples/glass-steps.sid" fresh.csv
python3 -B check_glass_steps.py "$skill"
```

`fresh.csv` must not already exist.  The first command reports `60 writes; --end-tick 119`.  The callable returns `(rows, end_tick)`; `end_tick` is the number of play calls **including calls with no writes**.  It is not the last write's tick plus one.  A fresh importer receives `seconds=2` as a call-budget input, not a report of recorded seconds.

| CSV field | Meaning |
|---|---|
| `phase`, `call` | `init,-1`, then `play` with zero-based `play_call_num`; taken at the call, not inferred from possibly trimmed note rows. |
| `order` | Zero-based SID-store ordinal within that call.  Preserve CSV row order, including repeated values. |
| `emulator_cycle_in_call` | Importer's local instruction-cycle count at the callback.  Resets for each entry; not a register's physical write cycle. |
| `tick` | `max(0, call)` for the decoder: init precedes play at the shared tick 0.  Do not sort equal ticks by address or `order`. |
| `address`, `value` | Original CPU address and byte in decimal, for canonical write registers `$D400` through `$D418` only. |

## What the hook sees (and misses)

- [`SidImport.import_sid`](https://github.com/c64cryptoboy/ChiptuneSAK/blob/8759135b5c9c26dc9da155b006c575243ba5304a/chiptunesak/sid.py#L1428-L1435) installs `track_io_settings` before init.  The observer forwards to `super()` so the normal importer keeps its ordered I/O history.  It records only when `cpu_state.see_io` is true **at that write**.  A write to RAM under the SID is not a SID write.  This is the thin emulator's `$01` mapping, not a full PLA or port-DDR model.
- [`ThinC64Emulator.set_mem`](https://github.com/c64cryptoboy/ChiptuneSAK/blob/8759135b5c9c26dc9da155b006c575243ba5304a/chiptunesak/thin_c64_emulator.py#L166-L200) calls the hook with the original address **before** its own mirror handling.  A write at `$D424` does not arrive as `$D404`.  The adapter refuses visible writes to `$D419` through `$D7FF`, including aliases, rather than silently dropping or folding them.  Other chips and scheduler writes are not recorded.
- [`fetch` and `runcpu`](https://github.com/c64cryptoboy/ChiptuneSAK/blob/8759135b5c9c26dc9da155b006c575243ba5304a/chiptunesak/emulator_6502.py#L603-L627) fetch the opcode and charge its base cycles before the handler.  For `STA abs`, callback `cpu.pc` is already **on the operand**, not the store opcode.  No PC is exported.  [`INC`](https://github.com/c64cryptoboy/ChiptuneSAK/blob/8759135b5c9c26dc9da155b006c575243ba5304a/chiptunesak/emulator_6502.py#L525-L528) assigns the result only once; the NMOS read-modify-write instruction's old-value bus write has no separate callback.  Accept only observed ordinary STA/STX/STY stores to the canonical block, and refuse any other writing opcode there.  Do not substitute a fabricated dummy write.

This is a callback trace, **not a full bus trace, IRQ scheduler, SID audio render, or untrusted-code sandbox**.  No support is claimed for RSID, multi-chip, mirrors, SID readback effects, digi timing, variable cadence, or unknown players.  The opt-in check executes a temporary derivative of Glass Steps with the gate moved ahead of the pitch stores.  Its call-end voice states still match, but its first edge moves from index 30 to 28.  The public `capture()` does not admit that derivative.
