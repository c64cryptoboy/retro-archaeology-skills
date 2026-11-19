; Three Doors: a single unbroken triangle A4, phrased only by the mixer.
; One SID, NTSC 8580.  The host calls init once, then play once per VBI.
.setcpu "6502"
.segment "CODE"
jmp init                   ; $1000
jmp play                   ; $1003

init:
        lda #0
        sta ticks
        sta $d404          ; voices 1 and 2: no oscillator waveform or gate
        sta $d40b
        sta $d417          ; A: voice 3 direct, zero resonance
        sta $d413          ; fast attack, zero decay setting
        lda #$f0
        sta $d414          ; full sustain
        lda #7
        sta $d415
        lda #$ff
        sta $d416          ; cutoff code $7ff, held throughout
        lda #$9f
        sta $d418          ; mute dry voice 3, LP selected, volume 15
        lda #$32
        sta $d40e
        lda #$1c
        sta $d40f          ; $1c32, about 440 Hz at NTSC
        lda #$08
        sta $d412          ; TEST before the note, not between holds
        lda #$11
        sta $d412          ; triangle + gate, TEST clear; only attack
        rts

play:
        lda ticks
        cmp #240
        beq done           ; hold C indefinitely without counter wrap
        inc ticks
        lda ticks
        cmp #120
        bne later
        lda #$04
        sta $d417          ; B: change ONLY the input route
        rts
later:  cmp #240
        bne done
        lda #$8f
        sta $d418          ; C: remove ONLY the LP response from output
 done:  rts
ticks:  .byte 0
