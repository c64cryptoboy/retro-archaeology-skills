#!/usr/bin/env python3
import argparse
from pathlib import Path
ops={
0x00:('BRK','imp',1),0x01:('ORA','izx',2),0x05:('ORA','zp',2),0x06:('ASL','zp',2),0x08:('PHP','imp',1),0x09:('ORA','imm',2),0x0a:('ASL','acc',1),0x0d:('ORA','abs',3),0x0e:('ASL','abs',3),
0x10:('BPL','rel',2),0x11:('ORA','izy',2),0x15:('ORA','zpx',2),0x16:('ASL','zpx',2),0x18:('CLC','imp',1),0x19:('ORA','aby',3),0x1d:('ORA','abx',3),0x1e:('ASL','abx',3),
0x20:('JSR','abs',3),0x21:('AND','izx',2),0x24:('BIT','zp',2),0x25:('AND','zp',2),0x26:('ROL','zp',2),0x28:('PLP','imp',1),0x29:('AND','imm',2),0x2a:('ROL','acc',1),0x2c:('BIT','abs',3),0x2d:('AND','abs',3),0x2e:('ROL','abs',3),
0x30:('BMI','rel',2),0x31:('AND','izy',2),0x35:('AND','zpx',2),0x36:('ROL','zpx',2),0x38:('SEC','imp',1),0x39:('AND','aby',3),0x3d:('AND','abx',3),0x3e:('ROL','abx',3),
0x40:('RTI','imp',1),0x41:('EOR','izx',2),0x45:('EOR','zp',2),0x46:('LSR','zp',2),0x48:('PHA','imp',1),0x49:('EOR','imm',2),0x4a:('LSR','acc',1),0x4c:('JMP','abs',3),0x4d:('EOR','abs',3),0x4e:('LSR','abs',3),
0x50:('BVC','rel',2),0x51:('EOR','izy',2),0x55:('EOR','zpx',2),0x56:('LSR','zpx',2),0x58:('CLI','imp',1),0x59:('EOR','aby',3),0x5d:('EOR','abx',3),0x5e:('LSR','abx',3),
0x60:('RTS','imp',1),0x61:('ADC','izx',2),0x65:('ADC','zp',2),0x66:('ROR','zp',2),0x68:('PLA','imp',1),0x69:('ADC','imm',2),0x6a:('ROR','acc',1),0x6c:('JMP','ind',3),0x6d:('ADC','abs',3),0x6e:('ROR','abs',3),
0x70:('BVS','rel',2),0x71:('ADC','izy',2),0x75:('ADC','zpx',2),0x76:('ROR','zpx',2),0x78:('SEI','imp',1),0x79:('ADC','aby',3),0x7d:('ADC','abx',3),0x7e:('ROR','abx',3),
0x81:('STA','izx',2),0x84:('STY','zp',2),0x85:('STA','zp',2),0x86:('STX','zp',2),0x88:('DEY','imp',1),0x8a:('TXA','imp',1),0x8c:('STY','abs',3),0x8d:('STA','abs',3),0x8e:('STX','abs',3),
0x90:('BCC','rel',2),0x91:('STA','izy',2),0x94:('STY','zpx',2),0x95:('STA','zpx',2),0x96:('STX','zpy',2),0x98:('TYA','imp',1),0x99:('STA','aby',3),0x9a:('TXS','imp',1),0x9d:('STA','abx',3),
0xa0:('LDY','imm',2),0xa1:('LDA','izx',2),0xa2:('LDX','imm',2),0xa4:('LDY','zp',2),0xa5:('LDA','zp',2),0xa6:('LDX','zp',2),0xa8:('TAY','imp',1),0xa9:('LDA','imm',2),0xaa:('TAX','imp',1),0xac:('LDY','abs',3),0xad:('LDA','abs',3),0xae:('LDX','abs',3),
0xb0:('BCS','rel',2),0xb1:('LDA','izy',2),0xb4:('LDY','zpx',2),0xb5:('LDA','zpx',2),0xb6:('LDX','zpy',2),0xb8:('CLV','imp',1),0xb9:('LDA','aby',3),0xba:('TSX','imp',1),0xbc:('LDY','abx',3),0xbd:('LDA','abx',3),0xbe:('LDX','aby',3),
0xc0:('CPY','imm',2),0xc1:('CMP','izx',2),0xc4:('CPY','zp',2),0xc5:('CMP','zp',2),0xc6:('DEC','zp',2),0xc8:('INY','imp',1),0xc9:('CMP','imm',2),0xca:('DEX','imp',1),0xcc:('CPY','abs',3),0xcd:('CMP','abs',3),0xce:('DEC','abs',3),
0xd0:('BNE','rel',2),0xd1:('CMP','izy',2),0xd5:('CMP','zpx',2),0xd6:('DEC','zpx',2),0xd8:('CLD','imp',1),0xd9:('CMP','aby',3),0xdd:('CMP','abx',3),0xde:('DEC','abx',3),
0xe0:('CPX','imm',2),0xe1:('SBC','izx',2),0xe4:('CPX','zp',2),0xe5:('SBC','zp',2),0xe6:('INC','zp',2),0xe8:('INX','imp',1),0xe9:('SBC','imm',2),0xea:('NOP','imp',1),0xec:('CPX','abs',3),0xed:('SBC','abs',3),0xee:('INC','abs',3),
0xf0:('BEQ','rel',2),0xf1:('SBC','izy',2),0xf5:('SBC','zpx',2),0xf6:('INC','zpx',2),0xf8:('SED','imp',1),0xf9:('SBC','aby',3),0xfd:('SBC','abx',3),0xfe:('INC','abx',3),}
def fmt(mode, bs, pc):
    """Format supplied instruction bytes, refusing incomplete operands."""
    if mode=='imp': return ''
    if mode=='acc': return 'A'
    required = 3 if mode in {'abs', 'abx', 'aby', 'ind'} else 2
    if len(bs) < required:
        raise ValueError(f'incomplete {mode} instruction: expected {required} bytes, got {len(bs)}')
    b = bs[1]
    w = b | (bs[2] << 8) if required == 3 else b
    if mode=='imm': return f'#$%02X'%b
    if mode=='zp': return f'$%02X'%b
    if mode=='zpx': return f'$%02X,X'%b
    if mode=='zpy': return f'$%02X,Y'%b
    if mode=='abs': return f'$%04X'%w
    if mode=='abx': return f'$%04X,X'%w
    if mode=='aby': return f'$%04X,Y'%w
    if mode=='ind': return f'($%04X)'%w
    if mode=='izx': return f'($%02X,X)'%b
    if mode=='izy': return f'($%02X),Y'%b
    if mode=='rel':
        off=b-256 if b>=128 else b; return f'$%04X'%((pc+2+off) & 0xffff)

def validate_extent(mem, base):
    """Require a linear image wholly inside the 16-bit address space."""
    if not 0 <= base <= 0xffff:
        raise ValueError('PRG load address must be a 16-bit address')
    if base + len(mem) > 0x10000:
        raise ValueError('PRG load range exceeds 16-bit address space')


def main():
    parser = argparse.ArgumentParser(description='Disassemble a linear 6502 PRG image.')
    parser.add_argument('prg', type=Path)
    parser.add_argument('start', type=lambda v: int(v, 0), nargs='?')
    parser.add_argument('count', type=lambda v: int(v, 0), nargs='?', default=64)
    args = parser.parse_args()
    data = args.prg.read_bytes()
    if len(data) < 3:
        parser.error('PRG must include a two-byte load address and at least one byte')
    base = data[0] | (data[1] << 8)
    mem = data[2:]
    try:
        validate_extent(mem, base)
    except ValueError as exc:
        parser.error(str(exc))
    pc = args.start if args.start is not None else base
    if not base <= pc < base + len(mem):
        parser.error('start address must be inside the PRG image')
    if args.count < 0:
        parser.error('count must be nonnegative')
    for _ in range(args.count):
        i = pc - base
        if not 0 <= i < len(mem):
            break
        op = mem[i]
        m, mode, l = ops.get(op, (f'???${op:02X}', 'imp', 1))
        bs = mem[i:i+l]
        if len(bs) < l:
            print(f'{pc:04X}: {bs.hex(" "):<8} {m:3} ; INCOMPLETE (expected {l} bytes)')
            break
        print(f'{pc:04X}: {bs.hex(" "):<8} {m:3} {fmt(mode,bs,pc)}')
        pc += l

if __name__ == '__main__':
    main()
