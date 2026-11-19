; Half Rate -- original standalone NTSC C64 program.  No music or game input.
; ca65 -D TOGGLE=1 (treatment) or =0 (matched-mean repeated control).
; ld65 -t none -S 0x07ff; first two file bytes are the PRG load address.
.export start, loop, levels
.word $0801
.word endline
.word 10
.byte $9e, "2061", 0             ; 10 SYS2061
endline: .word 0
start:  .assert start = $080d, lderror, "BASIC entry mismatch"
        sei
        lda #0
        sta $d011                 ; no display badlines
        sta $d015                 ; no sprite DMA
        ldx #$18
clear:  sta $d400,x               ; zero all 25 writable SID registers
        dex
        bpl clear
        sta $c000                 ; one diagnostic increment per volume store in loop
        lda #'V'
        sta $c001
        lda #'D'
        sta $c002
        lda #'G'
        sta $c003
        ldx #0
loop:   lda levels,x              ; 4 cycles; both bytes in same page
        sta $d418                 ; upper nibble stays zero in BOTH cases
        inc $c000                 ; 6 cycles, wraps mod 256
        txa
        eor #1
        tax
        ldy #200
wait:   dey
        bne wait
        jmp loop
levels:
.if TOGGLE
        .byte 2,14
.else
        .byte 8,8
.endif
.assert >levels = >(levels+1), lderror, "indexed load would cross page"
.assert >wait = >(wait+3), lderror, "delay branch would cross page"
