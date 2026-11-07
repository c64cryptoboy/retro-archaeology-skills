# A small relocated-routine example

The existing end-to-end synthetic test provides a first run without game files or emulator captures.  From the skill directory:

```sh
python3 -B -m unittest discover -s scripts/tests -p test_end_to_end_synthetic.py -v
```

The two byte strings in `scripts/tests/test_end_to_end_synthetic.py` deliberately preserve instruction structure while relocating state.  For example:

```text
Left, loaded at $2000        Right, loaded at $8000
LDA $10                     LDA $4000
AND #$0F                    AND #$0F
STA $11                     STA $4001
LDX $12                     LDX $4002
INX                         INX
STX $12                     STX $4002
```

Literal operands differ, but relational operand identities preserve the repeated load/store target.  The immediate mask remains literal.  The complete fixture also changes instruction widths and adjusts its backward branch.

The test creates raw binaries and region manifests in a temporary directory, runs alignment, and requires at least one probable routine, at least 16 relational-exact pairs, zero different pairs in the selected match, and left-byte coverage of at least the left fixture's length minus one.  It then exercises lock serialization and a locked comparison.

**Evidence limit:** the test constructs a synthetic passing calibration object to exercise the lock path; it does not run a real positive/control calibration campaign.  Passing it demonstrates the tool pipeline on deliberately related bytes, not calibrated accuracy, historical borrowing, or meaningful provenance for an unknown pair.  Use the full [workflow](workflow.md) for those investigations.
