#!/usr/bin/env python3
"""Generate the ROM-derived exact FIN decimal-parser accelerator."""
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import generate_specialized_rnd_c as g

CHRGET = bytes.fromhex("e6 7a d0 02 e6 7b ad 00 08 c9 3a b0 0a c9 20 f0 ef 38 e9 30 38 e9 d0 60")
from rnd_paths import ROM_DIR
basic = g.checked(ROM_DIR / 'basic.bin', g.BASIC_SHA256)
kernal = g.checked(ROM_DIR / 'kernal.bin', g.KERNAL_SHA256)
memory = g.make_memory(basic, kernal)
memory[0x73:0x73 + len(CHRGET)] = CHRGET
g.ENTRY = 0xBCF3
cfg = g.collect_cfg(memory)

lines = [g.HEADER, "static int generated_parse(Cpu*c){uint8_t lo,hi;uint16_t return_pc;(void)return_pc;goto L_bcf3;"]
for pc in sorted(cfg):
    if pc == 0x79:
        block = [
            "L_0079: /* CHRGET's self-modified absolute LDA */",
            "    COUNT_BLOCK();",
            "    lda(c,c->m[(uint16_t)(c->m[0x7a]|((uint16_t)c->m[0x7b]<<8))]);",
            "    goto L_007c;",
        ]
    else:
        block = g.instruction_lines(memory, cfg, pc)
        block.insert(1, "    COUNT_BLOCK();")
    lines.extend(block)
lines.append("}\n")
lines.append(r'''
static void load_rom(Cpu*c,const char*path,uint16_t base){FILE*f=fopen(path,"rb");if(!f)die(path);if(fread(c->m+base,1,8192,f)!=8192||fgetc(f)!=EOF){fprintf(stderr,"bad ROM size: %s\n",path);exit(1);}fclose(f);}
int main(int ac,char**av){
    if(ac!=3){fprintf(stderr,"usage: %s BASIC-ROM KERNAL-ROM < literals.txt\n",av[0]);return 2;}
    Cpu*c=calloc(1,sizeof(*c));if(!c)die("calloc");load_rom(c,av[1],0xa000);load_rom(c,av[2],0xe000);
    static const uint8_t chrget[]={0xe6,0x7a,0xd0,0x02,0xe6,0x7b,0xad,0x00,0x08,0xc9,0x3a,0xb0,0x0a,0xc9,0x20,0xf0,0xef,0x38,0xe9,0x30,0x38,0xe9,0xd0,0x60};
    char text[256];
    while(fgets(text,sizeof(text),stdin)){
        size_t n=strcspn(text,"\r\n");text[n]=0;if(!n)continue;
        memset(c->m,0,0x400);memcpy(c->m+0x73,chrget,sizeof(chrget));memcpy(c->m+0x800,text,n+1);
        c->m[0x7a]=0;c->m[0x7b]=8;c->a=(uint8_t)text[0];c->x=c->y=0;c->p=FU|FC;c->sp=0xff;
        if(!generated_parse(c))return 3;
        printf("%s\t%02x%02x%02x%02x%02x%02x\n",text,c->m[0x61],c->m[0x62],c->m[0x63],c->m[0x64],c->m[0x65],c->m[0x66]);fflush(stdout);
    }
    free(c);return 0;
}
''')
out = HERE / "scratch/generated_fin.c"
out.write_text("\n".join(lines))
print(f"generated {len(cfg)} blocks: {out}")
