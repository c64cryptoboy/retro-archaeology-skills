; Evidence-only source correspondence for synthetic_fixture.py.  Not assembled or executed.
; Three ALTERNATIVE consumers at $1000, never linked together.
; Precondition supplied by fixture: flat 6502 RAM, $F0/$F1 = $1040.
; This is not a historical compiler, language, or authorship specimen.

; VM consumer ($1000-$102F inclusive)
; Address  Bytes     Source                    Meaning
; 1000     A0 00     LDY #$00                  FETCH
; 1002     B1 F0     LDA ($F0),Y               read cursor byte
; 1004     E6 F0     INC $F0                   advance cursor
; 1006     D0 02     BNE $100A
; 1008     E6 F1     INC $F1
; 100A     60        RTS
; 100B     20 00 10  JSR $1000                 DISPATCH: fetch token
; 100E     C9 00     CMP #$00
; 1010     F0 1D     BEQ $102F                 STOP
; 1012     C9 01     CMP #$01
; 1014     F0 05     BEQ $101B                 LITERAL
; 1016     C9 02     CMP #$02
; 1018     F0 07     BEQ $1021                 JUMP
; 101A     00        BRK                       unsupported token, error
; 101B     20 00 10  JSR $1000                 consume/discard one literal
; 101E     4C 0B 10  JMP $100B
; 1021     20 00 10  JSR $1000                 low byte of stream address
; 1024     AA        TAX
; 1025     20 00 10  JSR $1000                 high byte of stream address
; 1028     85 F1     STA $F1
; 102A     86 F0     STX $F0
; 102C     4C 0B 10  JMP $100B
; 102F     60        RTS                       STOP
; Stream $1040: 01 7F | 02 45 10 | 00.

; Generic direct-address-cell consumer ($1000-$1024 inclusive)
; 1000     A0 00     LDY #$00
; 1002     B1 F0     LDA ($F0),Y
; 1004     85 F2     STA $F2                   target low
; 1006     C8        INY
; 1007     B1 F0     LDA ($F0),Y
; 1009     85 F3     STA $F3                   target high
; 100B     18        CLC
; 100C     A5 F0     LDA $F0
; 100E     69 02     ADC #$02
; 1010     85 F0     STA $F0
; 1012     90 02     BCC $1016
; 1014     E6 F1     INC $F1
; 1016     6C F2 00  JMP ($00F2)               execution, not merely pointer data
; 1019-101F: zero padding, not consumer instructions
; 1020     4C 00 10  JMP $1000                 continue with next cell
; 1023: zero padding
; 1024     60        RTS                       return to caller
; Stream $1040: 20 10 | 24 10.  Cell width is two bytes, with no operands.
; This small generic dispatcher has no dictionary, stacks, or language implementation.
; The public CFG stops at $1016's unresolved indirect jump; the supplied rule table
; supplies handler meanings, and the checker does not pretend the CFG recovered them.

; Ordinary pointer-data reader ($1000-$100C inclusive)
; 1000     A2 00     LDX #$00
; 1002     BD 40 10  LDA $1040,X
; 1005     95 F2     STA $F2,X                 copy four bytes to scratch, no dispatch
; 1007     E8        INX
; 1008     E0 04     CPX #$04
; 100A     D0 F6     BNE $1002
; 100C     60        RTS
; SAME region bytes as the direct-address-cell example: 20 10 | 24 10.
; An address-looking table is not threaded code merely because its cells fit.
