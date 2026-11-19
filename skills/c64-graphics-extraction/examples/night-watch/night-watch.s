; Night Watch -- a blinking owl on a stock NTSC C64.  LOAD, then RUN.
; Build: ca65 night-watch.s -o owl.o && ld65 -t none owl.o -o night-watch.prg
        .word $0801
        .org $0801
        .word endline,10
        .byte $9e,"2061",0          ; 10 SYS2061
endline:.word 0
.assert * = 2061, error, "wrong SYS address"

screen  = $4400
chars   = $4800
eye     = chars+8                 ; screen code 1
nest    = 11*40+19                ; top left of the 2 by 3 character owl

        sei
        lda #$0b
        sta $d011                 ; hide setup
        lda #0
        sta $d015                 ; no sprites
        sta $d020                 ; black border
        ldx #0
clear:  .repeat 4,i
        sta screen+i*256,x
        .endrepeat
        .repeat 8,i
        sta chars+i*256,x         ; all glyphs, including blank code 0
        .endrepeat
        inx
        bne clear
        lda #3                    ; cyan feathers
ink:    .repeat 4,i
        sta $d800+i*256,x
        .endrepeat
        inx
        bne ink
        lda #7                    ; yellow eyes
        sta $d800+nest+40
        sta $d800+nest+41
        ldx #31
feathers:
        lda plumage,x
        sta chars+16,x            ; codes 2 through 5
        dex
        bpl feathers
        lda #2
        sta screen+nest
        lda #3
        sta screen+nest+1
        lda #1
        sta screen+nest+40        ; left AND right eye fetch the same glyph
        sta screen+nest+41
        lda #4
        sta screen+nest+80
        lda #5
        sta screen+nest+81
        lda $dd02
        ora #3
        sta $dd02
        lda $dd00
        and #$fc
        ora #2
        sta $dd00                 ; bank $4000
        lda #$12
        sta $d018                 ; screen $4400, character RAM $4800
        lda #8
        sta $d016                 ; 40 columns, hires text
        lda #6
        sta $d021                 ; blue night sky
        jsr next_edge
        lda #$1b
        sta $d011                 ; display enabled for the upcoming field

open:   ldy #0
        jsr patch
        ldx #32
        jsr hold
        ldy #8
        jsr patch
        ldx #8
        jsr hold
        jmp open                  ; no more writes to the matrix or color RAM

patch:  ldx #0
row:    lda eyelids,y
        sta eye,x                 ; change both eyes with one eight-byte copy
        iny
        inx
        cpx #8
        bne row
        rts

hold:   jsr next_edge
field_done:
        dex                       ; just completed one visible field
        bne hold
        rts
next_edge:                        ; NTSC raster 256, after visible content
low:    bit $d011
        bmi low                   ; leave any current high-raster interval
high:   bit $d011
        bpl high                  ; wait for next low-to-high transition
        rts

eyelids:
        .byte %00111100,%01111110,%11100111,%11000011
        .byte %11000011,%11100111,%01111110,%00111100
        .byte %00000000,%00000000,%00000000,%11000011
        .byte %01100110,%00111100,%00000000,%00000000
plumage:                          ; left and right ear tufts, then breast and feet
        .byte $80,$c0,$e0,$f0,$9c,$87,$43,$3c
        .byte $01,$03,$07,$0f,$39,$e1,$c2,$3c
        .byte $43,$61,$30,$19,$0c,$07,$15,$3f
        .byte $c2,$86,$0c,$98,$30,$e0,$a8,$fc
.export field_done
