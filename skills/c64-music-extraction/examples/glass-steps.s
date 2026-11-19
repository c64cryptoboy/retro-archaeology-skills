; Glass Steps: original single-voice NTSC étude. Assemble with ca65,
; link at $1000 (no PRG prefix). Entry stubs keep the ABI independent of layout.
.segment "CODE"
        jmp init                ; $1000, A=0 (only tune)
        jmp play                ; $1003, once per video frame

init:   lda #0
        sta phase
        sta note
        ldx #$18                ; turn off filters and other voices, too
clear:  sta $d400,x
        dex
        bpl clear
        lda #$08                ; attack 0, decay 8
        sta $d405
        lda #$a3                ; sustain A, release 3
        sta $d406
        lda #$0f
        sta $d418
        rts

play:   lda phase
        beq attack
        cmp #11
        bne advance
        lda #$20                ; saw stays selected during release
        sta $d404
        jmp advance
attack: ldx note
        lda freq_lo,x
        sta $d400
        lda freq_hi,x
        sta $d401
        lda #$21                ; saw + gate
        sta $d404
        inx
        txa
        and #3
        sta note
advance:
        inc phase
        lda phase
        cmp #15
        bne done
        lda #0
        sta phase
done:   rts

; G4, B-flat4, F4, D5. round(freq_Hz * 2^24 / 1022727).
freq_lo: .byte $1e,$df,$61,$a3
freq_hi: .byte $19,$1d,$16,$25
phase:   .byte 0
note:    .byte 0
