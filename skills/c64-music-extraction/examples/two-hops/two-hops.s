; Original NTSC VBI example.  One instrument, four pitches, no ROM calls.
.import __PLAYER_LOAD__, __NOTES_LOAD__
.segment "STUB"
    jmp install
    jmp play                 ; permanent PSID play entry, linked to run address
install:
    ldx #player_end-player-1
:   lda __PLAYER_LOAD__,x
    sta player,x
    dex
    bpl :-
    ldx #notes_end-notes-1
:   lda __NOTES_LOAD__,x
    sta notes,x
    dex
    bpl :-
    jmp player               ; real init returns to host, not to install

.segment "PLAYER"
player:
    lda #0
    sta frame
    ldx #$18
:   sta $d400,x
    dex
    bpl :-
    lda #$92
    sta $d406                ; sustain/release; attack/decay were cleared
    lda #15
    sta $d418
    rts
play:
    ldx frame
    txa
    and #7
    beq attack
    cmp #6
    bne advance
    lda #$10                 ; triangle, gate off
    sta $d404
    jmp advance
attack:
    txa
    lsr a
    lsr a
    lsr a
    tax
    lda notes,x              ; absolute reference linked for $7400
    sta $d401                ; low frequency byte was cleared at init
    lda #$11
    sta $d404
advance:
    lda frame
    clc
    adc #1
    and #31
    sta frame
    rts
frame: .byte 0
player_end:
.assert player_end-player <= 128, error, "copy index must start nonnegative"

.segment "NOTES"
notes: .byte 14, 17, 21, 16
notes_end:
.assert notes_end-notes <= 128, error, "copy index must start nonnegative"
