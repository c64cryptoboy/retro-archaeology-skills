; Beacon Ferry: stock C64, LOAD then RUN.  Joystick port 2 steers the cyan ferry.
; The only imported art is the extractor's 64-byte slot0.bin, included once.
.word $0801
.org $0801
        .word eol,10
        .byte $9e,"2061",0       ; 10 SYS2061
 eol:   .word 0
.assert * = 2061, error, "BASIC entry"
        sei
        lda #0
        sta $dc02                ; joystick on CIA1 port A, active low
        sta $d015
        sta $d017
        sta $d01b
        sta $d01d
        sta $d020
        lda $dd02
        ora #3
        sta $dd02
        lda $dd00
        ora #3                   ; bank $0000, not the donor's $4000
        sta $dd00
        lda #$14                 ; $0400 screen, stock uppercase font
        sta $d018
        lda #$1b
        sta $d011
        lda #8
        sta $d016
        lda #6
        sta $d021
        ldx #0
clear:  lda #32
        .repeat 4,i
        sta $0400+256*i,x
        .endrepeat
        lda #14
        .repeat 4,i
        sta $d800+256*i,x
        .endrepeat
        inx
        bne clear
        ; A repeated transit rail lies UNDER the ferry and the dock beacon.
        ldx #39
rail:   lda #'='
        sta $0400+12*40,x
        dex
        bpl rail
        lda #'*'                 ; navigation stars and two rail endcaps
        sta $0400+6*40+5
        sta $0400+8*40+30
        sta $0400+17*40+9
        lda #'.'
        sta $0400+7*40+22
        sta $0400+5*40+34
        sta $0400+17*40+25
        lda #'+'
        sta $0400+12*40
        sta $0400+13*40-1
        ldx #title_end-title-1
head:   lda title,x
        sta $0400+3*40+11,x
        dex
        bpl head
        ldx #guide_end-guide-1
foot:   lda guide,x
        sta $0400+21*40+5,x
        dex
        bpl foot
        lda #<((pattern-$0000)/64)
        sta $07f8                ; slots 0 and 1 point to ONE aligned block
        sta $07f9
        lda #92
        sta $d000
        lda #<284
        sta $d002
        lda #2                   ; bit 8 set only on the dock's X
        sta $d010
        lda #136
        sta $d001
        sta $d003
        lda #2                   ; 01 red, 11 yellow in both slots
        sta $d025
        lda #7
        sta $d026
        lda #3                   ; 10 cyan ferry, 10 light green dock
        sta $d027
        lda #13
        sta $d028
.ifdef WRONG_MODE
        lda #1                   ; only difference: dock reads single bits
.else
        lda #3                   ; both use 2-bit selectors as exported
.endif
        sta $d01c
        lda #3
        sta $d015
        ; Move one dot per video field, outside the visible rail.
next:   bit $d011
        bmi next
vblank: bit $d011
        bpl vblank
        lda $dc00
        and #$0c
        cmp #8
        beq left
        cmp #4
        bne next
        ldx $d000
        lda $d010
        lsr
        bcc advance
        cpx #<284                ; stop at the dock
        beq next
advance: inx
        stx $d000
        bne next
        lda #3                   ; crossed 255 heading right
        sta $d010
        bne next
left:   ldx $d000
        lda $d010
        lsr
        bcs retreat
        cpx #32
        beq next
retreat: dex
        stx $d000
        cpx #255
        bne next
        lda #2                   ; crossed 256 heading left
        sta $d010
        bne next
.repeat 26,i
        .charmap $41+i,1+i       ; screen codes for our captions
.endrepeat
title:  .byte "- BEACON FERRY -"
title_end:
guide:  .byte "PORT 2: STEER THE CYAN FERRY"
guide_end:
; Move to the next VIC slot boundary without linking at the donor address.
.res (-*) & $3f,0
pattern: .incbin "assets/slot0.bin"
.assert (pattern & $3f) = 0, error, "sprite alignment"
.assert * - pattern = 64, error, "expected complete exported slot"
.assert * <= $1000, error, "bank 0 character ROM window"
