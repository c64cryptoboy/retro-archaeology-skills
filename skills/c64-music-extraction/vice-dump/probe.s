; Original C64 PRG.  Load the file at $0801.  SYS 2061 starts probe.
        .org $07ff
        .word $0801
        .word basic_end, 10
        .byte $9e, "2061", 0
basic_end: .word 0
probe:  sei
        lda #0
        sta $d011       ; turn display off
        sta $d015       ; no sprite DMA
high:   bit $d011
        bpl high
low:    bit $d011
        bmi low         ; enter fresh field, before possible display fetches
        lda #$20
        sta $d404       ; first selected write, tick 0
        lda #$34
        sta $d400
        lda #$12
        sta $d401
        lda #$21
        sta $d404
        sta $d404       ; repeated write is intentional
        ldx #64
wait:   dex
        bne wait        ; same-page branch, 63 taken and 1 not taken
        sta $d424       ; single-SID mirror of $d404
        lda #$20
        sta $d404       ; gate off
        lda #0
        sta $d7ff       ; VICE -debugcart normal exit, not a SID write
stop:   jmp stop
