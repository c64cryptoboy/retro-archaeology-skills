# Comment the operation, not the opcodes

This synthetic routine demonstrates how a flag dependency supports a useful block comment.  It requires Python 3.10 or newer and the repository's `shared/6502/` directory, with no assembler, ROM, or live debugger.

```asm
; Advance a 16-bit little-endian pointer by 40 bytes, modulo 65536.
; Entry: D=0; $10/$11 are ordinary RAM, with no asynchronous observer.
; Output: updated pointer; A contains its low byte; X and Y are preserved.
; Clobbers: A, N, Z, C, and V.  Return uses the caller's ordinary RTS contract.
; Purpose limit: a 40-byte stride alone does not establish a screen pointer.
advance_pointer:
    LDA $10
    CLC
    ADC #$28
    STA $10
    BCC done       ; STA preserves ADC's carry; increment high byte on low wrap.
    INC $11
done:
    RTS
```

The arithmetic establishes `(pointer + 40) modulo 65536`.  The final N/Z flags come from ADC on the no-carry path, but from INC on the carry path; they are not a uniform 16-bit result test.  This is why the contract lists flag clobbers instead of claiming a convenient zero-result condition.

From the skill directory, run:

```sh
python3 -B examples/pointer_step.py
```

The script checks ordinary addition, the last no-carry input, the first carry input, and 16-bit wraparound against a direct arithmetic oracle.  Its eight-instruction bound prevents an accidental infinite loop.  The bundled CPU's empty-stack RTS stop is a test convention, not a hardware stack experiment.  These four cases illustrate the static argument; they do not prove emulator accuracy, decimal behavior, interrupt safety, or the routine's purpose in an unknown program.
