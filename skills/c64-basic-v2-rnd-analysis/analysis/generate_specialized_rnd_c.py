#!/usr/bin/env python3
"""Generate direct C basic blocks for the pinned C64 BASIC RND advance path.

The generated file is a local, ROM-derived test artifact. It still loads the
verified ROMs at runtime for data constants, but does not decode opcodes while
advancing the RNG.
"""

from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path

from isa6502 import OPS

HERE = Path(__file__).resolve().parent

BASIC_SHA256 = "89878cea0a268734696de11c4bae593eaaa506465d2029d619c0e0cbccdfa62d"
KERNAL_SHA256 = "83c60d47047d7beab8e5b7bf6f67f80daa088b7a6a27de0d7e016f6484042721"
ENTRY = 0xE0BE
BRANCHES = {"BPL", "BMI", "BVC", "BVS", "BCC", "BCS", "BNE", "BEQ"}
TERMINATORS = {"RTS", "RTI", "BRK"}


def checked(path: Path, expected: str) -> bytes:
    data = path.read_bytes()
    actual = hashlib.sha256(data).hexdigest()
    if len(data) != 8192 or actual != expected:
        raise SystemExit(f"unexpected ROM {path}: size={len(data)} sha256={actual}")
    return data


def make_memory(basic: bytes, kernal: bytes) -> bytearray:
    memory = bytearray(65536)
    memory[0xA000:0xC000] = basic
    memory[0xE000:0x10000] = kernal
    return memory


def target(memory: bytearray, pc: int) -> int:
    return memory[pc + 1] | memory[pc + 2] << 8


def collect_cfg(memory: bytearray) -> dict[int, tuple[str, str, int]]:
    work = [ENTRY]
    result: dict[int, tuple[str, str, int]] = {}
    while work:
        pc = work.pop()
        if pc in result:
            continue
        op = memory[pc]
        if op not in OPS:
            raise SystemExit(f"unsupported opcode ${op:02X} reached statically at ${pc:04X}")
        mnemonic, mode, length = OPS[op]
        result[pc] = mnemonic, mode, length
        fallthrough = (pc + length) & 0xFFFF
        if mnemonic in TERMINATORS:
            continue
        if mnemonic == "JMP":
            if mode == "abs":
                work.append(target(memory, pc))
            # An indirect jump is retained as a generated refusal block.
            continue
        if mnemonic == "JSR":
            work.extend((fallthrough, target(memory, pc)))
            continue
        if mnemonic in BRANCHES:
            displacement = memory[pc + 1]
            if displacement >= 0x80:
                displacement -= 0x100
            work.extend((fallthrough, (fallthrough + displacement) & 0xFFFF))
            continue
        work.append(fallthrough)
    return result


def addr_expr(mode: str, operand: int) -> str:
    if mode == "zp":
        return f"0x{operand:02x}"
    if mode == "zpx":
        return f"(uint8_t)(0x{operand:02x}+c->x)"
    if mode == "zpy":
        return f"(uint8_t)(0x{operand:02x}+c->y)"
    if mode == "abs":
        return f"0x{operand:04x}"
    if mode == "abx":
        return f"(uint16_t)(0x{operand:04x}+c->x)"
    if mode == "aby":
        return f"(uint16_t)(0x{operand:04x}+c->y)"
    if mode == "izx":
        return f"izx(c,0x{operand:02x})"
    if mode == "izy":
        return f"izy(c,0x{operand:02x})"
    raise ValueError(f"mode {mode} has no address expression")


def operand_value(memory: bytearray, pc: int, mode: str) -> tuple[int, str]:
    if mode == "imm":
        operand = memory[pc + 1]
        return operand, f"0x{operand:02x}"
    if mode in {"zp", "zpx", "zpy", "izx", "izy"}:
        operand = memory[pc + 1]
    elif mode in {"abs", "abx", "aby"}:
        operand = target(memory, pc)
    else:
        raise ValueError(f"mode {mode} has no operand value")
    return operand, f"c->m[{addr_expr(mode, operand)}]"


def instruction_lines(memory: bytearray, cfg: dict[int, tuple[str, str, int]], pc: int) -> list[str]:
    mnemonic, mode, length = cfg[pc]
    nxt = (pc + length) & 0xFFFF
    opbytes = " ".join(f"{b:02x}" for b in memory[pc:pc + length])
    out = [f"L_{pc:04x}: /* {opbytes:<8} {mnemonic} {mode} */"]
    if pc == 0xE0C9:
        out.append("    if(rnd_multiply_input_hook)rnd_multiply_input_hook(c);")
    if pc == 0xE0CC:
        out.append("    if(rnd_product_hook)rnd_product_hook(c);")
    if pc == 0xE0D3:
        out.append("    if(rnd_intermediate_hook)rnd_intermediate_hook(c);")

    def finish(statement: str = "") -> list[str]:
        if statement:
            out.append(f"    {statement}")
        out.append(f"    goto L_{nxt:04x};")
        return out

    if mnemonic in {"LDA", "LDX", "LDY", "ADC", "SBC", "AND", "ORA", "EOR", "CMP", "CPX", "CPY", "BIT"}:
        _, value = operand_value(memory, pc, mode)
        if mnemonic == "LDA": return finish(f"lda(c,{value});")
        if mnemonic == "LDX": return finish(f"ldx(c,{value});")
        if mnemonic == "LDY": return finish(f"ldy(c,{value});")
        if mnemonic == "ADC": return finish(f"adc(c,{value});")
        if mnemonic == "SBC": return finish(f"sbc(c,{value});")
        if mnemonic == "AND": return finish(f"lda(c,(uint8_t)(c->a&{value}));")
        if mnemonic == "ORA": return finish(f"lda(c,(uint8_t)(c->a|{value}));")
        if mnemonic == "EOR": return finish(f"lda(c,(uint8_t)(c->a^{value}));")
        if mnemonic == "CMP": return finish(f"cmp8(c,c->a,{value});")
        if mnemonic == "CPX": return finish(f"cmp8(c,c->x,{value});")
        if mnemonic == "CPY": return finish(f"cmp8(c,c->y,{value});")
        if mnemonic == "BIT": return finish(f"bit(c,{value});")

    if mnemonic in {"STA", "STX", "STY"}:
        operand = memory[pc + 1] if length == 2 else target(memory, pc)
        address = addr_expr(mode, operand)
        register = {"STA": "a", "STX": "x", "STY": "y"}[mnemonic]
        return finish(f"c->m[{address}]=c->{register};")

    if mnemonic in {"ASL", "LSR", "ROL", "ROR"}:
        if mode == "acc":
            return finish(f"c->a={mnemonic.lower()}(c,c->a);")
        operand = memory[pc + 1] if length == 2 else target(memory, pc)
        address = addr_expr(mode, operand)
        return finish(f"c->m[{address}]={mnemonic.lower()}(c,c->m[{address}]);")

    if mnemonic in {"INC", "DEC"}:
        operand = memory[pc + 1] if length == 2 else target(memory, pc)
        address = addr_expr(mode, operand)
        delta = "+1" if mnemonic == "INC" else "-1"
        return finish(f"c->m[{address}]=(uint8_t)(c->m[{address}]{delta});nz(c,c->m[{address}]);")

    simple = {
        "CLC": "c->p&=(uint8_t)~FC;",
        "SEC": "c->p|=FC;",
        "TAY": "ldy(c,c->a);",
        "TYA": "lda(c,c->y);",
        "TAX": "ldx(c,c->a);",
        "TXA": "lda(c,c->x);",
        "INY": "c->y++;nz(c,c->y);",
        "DEY": "c->y--;nz(c,c->y);",
        "INX": "c->x++;nz(c,c->x);",
        "DEX": "c->x--;nz(c,c->x);",
        "PLA": "lda(c,pop(c));",
        "PHA": "push(c,c->a);",
        "PHP": "push(c,(uint8_t)(c->p|0x30));",
        "PLP": "c->p=(uint8_t)(pop(c)|FU);",
    }
    if mnemonic in simple:
        return finish(simple[mnemonic])

    if mnemonic in BRANCHES:
        displacement = memory[pc + 1]
        if displacement >= 0x80:
            displacement -= 0x100
        branch_target = (nxt + displacement) & 0xFFFF
        conditions = {
            "BPL": "!(c->p&FN)", "BMI": "c->p&FN",
            "BVC": "!(c->p&FV)", "BVS": "c->p&FV",
            "BCC": "!(c->p&FC)", "BCS": "c->p&FC",
            "BNE": "!(c->p&FZ)", "BEQ": "c->p&FZ",
        }
        out.append(f"    if({conditions[mnemonic]}) goto L_{branch_target:04x};")
        out.append(f"    goto L_{nxt:04x};")
        return out

    if mnemonic == "JSR":
        destination = target(memory, pc)
        return_address = (nxt - 1) & 0xFFFF
        out.append(f"    push(c,0x{return_address >> 8:02x});push(c,0x{return_address & 0xff:02x});")
        out.append(f"    goto L_{destination:04x};")
        return out

    if mnemonic == "JMP":
        if mode == "abs":
            out.append(f"    goto L_{target(memory, pc):04x};")
        else:
            out.append(f"    fprintf(stderr,\"refusing indirect JMP reached at ${pc:04X}\\n\");return 0;")
        return out

    if mnemonic == "RTS":
        out.append("    if(c->sp==0xff)return 1;")
        out.append("    lo=pop(c);hi=pop(c);return_pc=(uint16_t)((lo|((uint16_t)hi<<8))+1);")
        out.append("    switch(return_pc){")
        for address in sorted(cfg):
            out.append(f"    case 0x{address:04x}:goto L_{address:04x};")
        out.append("    default:fprintf(stderr,\"unrecognized generated return PC $%04x\\n\",return_pc);return 0;")
        out.append("    }")
        return out

    if mnemonic == "BRK":
        out.append(f"    fprintf(stderr,\"refusing BRK reached at ${pc:04X}\\n\");return 0;")
        return out

    raise SystemExit(f"generator has no semantics for {mnemonic} {mode} at ${pc:04X}")


HEADER = r'''/* Generated by generate_specialized_rnd_c.py from pinned C64 ROM control flow.
 * Local ROM-derived validation artifact: do not publish this generated file by default. */
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#define FC 0x01
#define FZ 0x02
#define FU 0x20
#define FV 0x40
#define FN 0x80
#define RNDX 0x008b

typedef struct { uint8_t m[65536],a,x,y,p,sp; } Cpu;
typedef struct { uint8_t b[5]; } State;
typedef void (*RndArithmeticHook)(const Cpu*);
static RndArithmeticHook rnd_multiply_input_hook;
static RndArithmeticHook rnd_product_hook;
static RndArithmeticHook rnd_intermediate_hook;
typedef struct { State state;uint64_t index;uint8_t used; } SeenSlot;
#ifdef COUNT_GENERATED_BLOCKS
static uint64_t generated_instructions;
#define COUNT_BLOCK() (generated_instructions++)
#else
#define COUNT_BLOCK() ((void)0)
#ifndef GENERATED_RND_NO_MAIN
static const uint64_t generated_instructions=0;
#endif
#endif
static void die(const char*s){perror(s);exit(1);}
static void nz(Cpu*c,uint8_t x){c->p=(uint8_t)((c->p&~(FN|FZ))|(x&FN)|(x==0?FZ:0));}
static void lda(Cpu*c,uint8_t x){c->a=x;nz(c,x);} static void ldx(Cpu*c,uint8_t x){c->x=x;nz(c,x);} static void ldy(Cpu*c,uint8_t x){c->y=x;nz(c,x);}
static void push(Cpu*c,uint8_t x){c->m[0x100|c->sp--]=x;} static uint8_t pop(Cpu*c){return c->m[0x100|++c->sp];}
static uint16_t izy(Cpu*c,uint8_t z){return (uint16_t)((c->m[z]|((uint16_t)c->m[(uint8_t)(z+1)]<<8))+c->y);}
static void adc(Cpu*c,uint8_t b){uint8_t a=c->a;uint16_t s=(uint16_t)a+b+(c->p&FC);uint8_t r=(uint8_t)s;c->p=(uint8_t)((c->p&~(FN|FV|FZ|FC))|(r&FN)|(r==0?FZ:0)|((~(a^b)&(a^r)&0x80)?FV:0)|(s>0xff?FC:0));c->a=r;}
static void sbc(Cpu*c,uint8_t b){uint8_t a=c->a;uint16_t s=(uint16_t)a+(uint8_t)~b+(c->p&FC);uint8_t r=(uint8_t)s;c->p=(uint8_t)((c->p&~(FN|FV|FZ|FC))|(r&FN)|(r==0?FZ:0)|(((a^r)&(a^b)&0x80)?FV:0)|(s>0xff?FC:0));c->a=r;}
static void cmp8(Cpu*c,uint8_t a,uint8_t b){uint8_t r=(uint8_t)(a-b);c->p=(uint8_t)((c->p&~(FN|FZ|FC))|(r&FN)|(r==0?FZ:0)|(a>=b?FC:0));}
static void bit(Cpu*c,uint8_t b){c->p=(uint8_t)((c->p&~(FN|FV|FZ))|(b&(FN|FV))|((c->a&b)?0:FZ));}
static uint8_t asl(Cpu*c,uint8_t x){c->p=(uint8_t)((c->p&~FC)|(x>>7));x<<=1;nz(c,x);return x;}
static uint8_t lsr(Cpu*c,uint8_t x){c->p=(uint8_t)((c->p&~FC)|(x&1));x>>=1;nz(c,x);return x;}
static uint8_t rol(Cpu*c,uint8_t x){uint16_t t=(uint16_t)(x<<1)|(c->p&FC);c->p=(uint8_t)((c->p&~FC)|(x>>7));x=(uint8_t)t;nz(c,x);return x;}
static uint8_t ror(Cpu*c,uint8_t x){uint16_t t=(uint16_t)((c->p&FC)?0x100:0)|x;c->p=(uint8_t)((c->p&~FC)|(x&1));x=(uint8_t)(t>>1);nz(c,x);return x;}
'''

FOOTER = r'''
static void load(Cpu*c,const char*path,uint16_t base){FILE*f=fopen(path,"rb");if(!f)die(path);if(fread(c->m+base,1,8192,f)!=8192||fgetc(f)!=EOF){fprintf(stderr,"bad ROM size: %s\n",path);exit(1);}fclose(f);}
static int hex_digit(char x){if(x>='0'&&x<='9')return x-'0';if(x>='a'&&x<='f')return x-'a'+10;if(x>='A'&&x<='F')return x-'A'+10;return -1;}
static Cpu*new_cpu(const char*b,const char*k){static const uint8_t init[5]={0x80,0x4f,0xc7,0x52,0x58};Cpu*c=calloc(1,sizeof(*c));if(!c)die("calloc");load(c,b,0xa000);load(c,k,0xe000);memcpy(c->m+RNDX,init,5);const char*t=getenv("RND_START");if(t){if(strlen(t)!=10){fputs("RND_START must be exactly 10 hexadecimal digits\n",stderr);exit(2);}for(unsigned i=0;i<5;i++){int hi=hex_digit(t[i*2]),lo=hex_digit(t[i*2+1]);if(hi<0||lo<0){fputs("invalid RND_START\n",stderr);exit(2);}c->m[RNDX+i]=(uint8_t)((hi<<4)|lo);}}return c;}
static State state(const Cpu*c){State s;memcpy(s.b,c->m+RNDX,5);return s;} static int equal(State a,State b){return !memcmp(a.b,b.b,5);}
static State advance(Cpu*c){c->a=c->x=c->y=0;c->p=FU;c->sp=0xff;if(!generated_advance(c))exit(2);return state(c);}
static uint64_t hash(State s){uint64_t h=UINT64_C(1469598103934665603);for(unsigned i=0;i<5;i++){h^=s.b[i];h*=UINT64_C(1099511628211);}return h;}
#ifndef GENERATED_RND_NO_MAIN
static void show(uint64_t n,State s){printf("%"PRIu64": %02x %02x %02x %02x %02x\n",n,s.b[0],s.b[1],s.b[2],s.b[3],s.b[4]);}
int main(int ac,char**av){if(ac<3||ac>4){fprintf(stderr,"usage: %s BASIC-ROM KERNAL-ROM [--vectors-only|--steps=N|--seen|--digest=N]\n",av[0]);return 2;}Cpu*c=new_cpu(av[1],av[2]);State initial=state(c);show(0,initial);State s1=advance(c),s2=advance(c);show(1,s1);show(2,s2);const uint8_t e1[5]={0x7e,0x3e,0x04,0x7e,0x4e},e2[5]={0x7c,0x40,0x18,0xc8,0x69};if(!getenv("RND_START")){if(memcmp(s1.b,e1,5)||memcmp(s2.b,e2,5)){fputs("vector mismatch\n",stderr);return 1;}puts("supplied transition vectors match generated C");}
if(ac==4&&!strcmp(av[3],"--vectors-only")){free(c);return 0;}
if(ac==4&&!strncmp(av[3],"--steps=",8)){char*e;uint64_t n=strtoull(av[3]+8,&e,10);if(*e||n<2)return 2;for(uint64_t i=2;i<n;i++)s2=advance(c);show(n,s2);free(c);return 0;}
if(ac==4&&!strncmp(av[3],"--digest=",9)){char*e;uint64_t n=strtoull(av[3]+9,&e,10);if(*e)return 2;free(c);c=new_cpu(av[1],av[2]);State s=state(c);uint64_t h=UINT64_C(1469598103934665603);for(uint64_t i=0;i<=n;i++){for(unsigned j=0;j<5;j++){h^=s.b[j];h*=UINT64_C(1099511628211);}if(i<n)s=advance(c);}printf("digest through x[%"PRIu64"]: %016"PRIx64"\n",n,h);free(c);return 0;}
if(ac==4&&!strcmp(av[3],"--seen")){enum{SIZE=1<<20};SeenSlot*t=calloc(SIZE,sizeof(*t));if(!t)die("calloc seen");free(c);c=new_cpu(av[1],av[2]);State s=state(c);for(uint64_t i=0;;i++){size_t at=(size_t)hash(s)&(SIZE-1);while(t[at].used&&!equal(t[at].state,s))at=(at+1)&(SIZE-1);if(t[at].used){printf("first repeated index: %"PRIu64"\nfirst seen index (mu): %"PRIu64"\ncycle (lambda): %"PRIu64"\n",i,t[at].index,i-t[at].index);break;}t[at].used=1;t[at].state=s;t[at].index=i;s=advance(c);}free(t);free(c);return 0;}
if(ac==4){return 2;}free(c);c=new_cpu(av[1],av[2]);uint64_t power=1,lambda=1,transitions=1;State tortoise=initial,hare=advance(c);while(!equal(tortoise,hare)){if(power==lambda){tortoise=hare;power<<=1;lambda=0;}hare=advance(c);lambda++;transitions++;}Cpu*tc=new_cpu(av[1],av[2]),*hc=new_cpu(av[1],av[2]);for(uint64_t i=0;i<lambda;i++)advance(hc);uint64_t mu=0;tortoise=state(tc);hare=state(hc);while(!equal(tortoise,hare)){tortoise=advance(tc);hare=advance(hc);mu++;transitions+=2;}printf("on-ramp (mu): %"PRIu64"\ncycle (lambda): %"PRIu64"\ncounted transitions: %"PRIu64"\ngenerated blocks: %"PRIu64"\n",mu,lambda,transitions,generated_instructions);free(c);free(tc);free(hc);return 0;}
#endif
'''


def generate(memory: bytearray, cfg: dict[int, tuple[str, str, int]]) -> str:
    lines = [HEADER, "static int generated_advance(Cpu*c){uint8_t lo,hi;uint16_t return_pc;(void)return_pc;goto L_e0be;"]
    for pc in sorted(cfg):
        block = instruction_lines(memory, cfg, pc)
        block.insert(1, "    COUNT_BLOCK();")
        lines.extend(block)
    lines.append("}\n")
    lines.append(FOOTER)
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    from rnd_paths import ROM_DIR as rom_dir
    parser.add_argument("--basic", type=Path, default=rom_dir / "basic.bin")
    parser.add_argument("--kernal", type=Path, default=rom_dir / "kernal.bin")
    parser.add_argument("--output", type=Path, default=HERE / "generated_rnd_cycle.c")
    args = parser.parse_args()
    memory = make_memory(checked(args.basic, BASIC_SHA256), checked(args.kernal, KERNAL_SHA256))
    cfg = collect_cfg(memory)
    text = generate(memory, cfg)
    args.output.write_text(text)
    print(f"generated {len(cfg)} instruction blocks in {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
