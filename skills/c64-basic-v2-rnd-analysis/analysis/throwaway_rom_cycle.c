/* Throwaway exact-ROM cycle finder for the C64 BASIC V2 RND advance at $E0BE. */
#include <errno.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#define C 0x01
#define Z 0x02
#define D 0x08
#define U 0x20
#define V 0x40
#define N 0x80
#define RNDX 0x008b
#define ENTRY 0xe0be

typedef struct {
    uint8_t m[65536], a, x, y, p, sp;
    uint16_t pc;
} Cpu;

typedef struct { uint8_t b[5]; } State;
typedef struct { State state; uint64_t index; uint8_t used; } SeenSlot;

static uint64_t instruction_count;

static void die(const char *msg) { perror(msg); exit(1); }
static uint8_t fetch(Cpu *c) { return c->m[c->pc++]; }
static uint16_t word(Cpu *c) { uint16_t lo = fetch(c); return lo | ((uint16_t)fetch(c) << 8); }
static uint8_t pop(Cpu *c) { return c->m[0x100 | ++c->sp]; }
static void push(Cpu *c, uint8_t v) { c->m[0x100 | c->sp--] = v; }
static void nz(Cpu *c, uint8_t v) { c->p = (c->p & ~(N|Z)) | (v & N) | (v == 0 ? Z : 0); }
static void lda(Cpu *c, uint8_t v) { c->a = v; nz(c, v); }
static void ldx(Cpu *c, uint8_t v) { c->x = v; nz(c, v); }
static void ldy(Cpu *c, uint8_t v) { c->y = v; nz(c, v); }
static uint16_t izy(Cpu *c, uint8_t z) {
    uint16_t base = c->m[z] | ((uint16_t)c->m[(uint8_t)(z + 1)] << 8);
    return (uint16_t)(base + c->y);
}
static void branch(Cpu *c, int take) { int8_t d = (int8_t)fetch(c); if (take) c->pc = (uint16_t)(c->pc + d); }
static void adc(Cpu *c, uint8_t b) {
    uint8_t a = c->a;
    uint16_t s = (uint16_t)a + b + (c->p & C);
    uint8_t r = (uint8_t)s;
    c->p = (c->p & ~(N|V|Z|C)) | (r & N) | (r == 0 ? Z : 0)
         | ((~(a ^ b) & (a ^ r) & 0x80) ? V : 0) | (s > 0xff ? C : 0);
    c->a = r;
}
static void sbc(Cpu *c, uint8_t b) {
    uint8_t a = c->a;
    uint16_t s = (uint16_t)a + (uint8_t)~b + (c->p & C);
    uint8_t r = (uint8_t)s;
    c->p = (c->p & ~(N|V|Z|C)) | (r & N) | (r == 0 ? Z : 0)
         | (((a ^ r) & (a ^ b) & 0x80) ? V : 0) | (s > 0xff ? C : 0);
    c->a = r;
}
static void cmpa(Cpu *c, uint8_t b) {
    uint8_t r = (uint8_t)(c->a - b);
    c->p = (c->p & ~(N|Z|C)) | (r & N) | (r == 0 ? Z : 0) | (c->a >= b ? C : 0);
}

/* Returns 0 only for the outermost RTS. It traps any opcode not reached by this ROM path. */
static int step(Cpu *c) {
    uint8_t op = fetch(c), z, v;
    uint16_t a, t;
    instruction_count++;
    switch (op) {
    case 0x06: z=fetch(c); v=c->m[z]; c->p=(c->p&~C)|(v>>7); v<<=1; c->m[z]=v; nz(c,v); break;
    case 0x09: lda(c, c->a | fetch(c)); break;
    case 0x10: branch(c, !(c->p&N)); break;
    case 0x16: z=(uint8_t)(fetch(c)+c->x); v=c->m[z]; c->p=(c->p&~C)|(v>>7); v<<=1; c->m[z]=v; nz(c,v); break;
    case 0x18: c->p &= ~C; break;
    case 0x20: a=word(c); t=(uint16_t)(c->pc-1); push(c,(uint8_t)(t>>8)); push(c,(uint8_t)t); c->pc=a; break;
    case 0x24: v=c->m[fetch(c)]; c->p=(c->p&~(N|V|Z))|(v&(N|V))|((c->a&v)?0:Z); break;
    case 0x25: lda(c, c->a & c->m[fetch(c)]); break;
    case 0x26: z=fetch(c); v=c->m[z]; t=(uint16_t)(v<<1)|(c->p&C); c->p=(c->p&~C)|(v>>7); v=(uint8_t)t; c->m[z]=v; nz(c,v); break;
    case 0x2c: a=word(c); v=c->m[a]; c->p=(c->p&~(N|V|Z))|(v&(N|V))|((c->a&v)?0:Z); break;
    case 0x30: branch(c, c->p&N); break;
    case 0x38: c->p |= C; break;
    case 0x45: lda(c, c->a ^ c->m[fetch(c)]); break;
    case 0x49: lda(c, c->a ^ fetch(c)); break;
    case 0x4a: v=c->a; c->p=(c->p&~C)|(v&1); c->a=v>>1; nz(c,c->a); break;
    case 0x4c: c->pc=word(c); break;
    case 0x60:
        if (c->sp == 0xff) return 0;
        z=pop(c); v=pop(c); c->pc=(uint16_t)(z | ((uint16_t)v<<8)); c->pc++; break;
    case 0x65: adc(c,c->m[fetch(c)]); break;
    case 0x66: z=fetch(c); v=c->m[z]; t=(uint16_t)((c->p&C)?0x100:0)|v; c->p=(c->p&~C)|(v&1); v=(uint8_t)(t>>1); c->m[z]=v; nz(c,v); break;
    case 0x69: adc(c,fetch(c)); break;
    case 0x6a: v=c->a; t=(uint16_t)((c->p&C)?0x100:0)|v; c->p=(c->p&~C)|(v&1); c->a=(uint8_t)(t>>1); nz(c,c->a); break;
    case 0x76: z=(uint8_t)(fetch(c)+c->x); v=c->m[z]; t=(uint16_t)((c->p&C)?0x100:0)|v; c->p=(c->p&~C)|(v&1); v=(uint8_t)(t>>1); c->m[z]=v; nz(c,v); break;
    case 0x84: c->m[fetch(c)]=c->y; break;
    case 0x85: c->m[fetch(c)]=c->a; break;
    case 0x86: c->m[fetch(c)]=c->x; break;
    case 0x88: c->y--; nz(c,c->y); break;
    case 0x90: branch(c, !(c->p&C)); break;
    case 0x91: z=fetch(c); c->m[izy(c,z)]=c->a; break;
    case 0x94: z=(uint8_t)(fetch(c)+c->x); c->m[z]=c->y; break;
    case 0x98: lda(c,c->y); break;
    case 0xa0: ldy(c,fetch(c)); break;
    case 0xa2: ldx(c,fetch(c)); break;
    case 0xa4: ldy(c,c->m[fetch(c)]); break;
    case 0xa5: lda(c,c->m[fetch(c)]); break;
    case 0xa6: ldx(c,c->m[fetch(c)]); break;
    case 0xa8: ldy(c,c->a); break;
    case 0xa9: lda(c,fetch(c)); break;
    case 0xb0: branch(c, c->p&C); break;
    case 0xb1: z=fetch(c); lda(c,c->m[izy(c,z)]); break;
    case 0xb4: z=(uint8_t)(fetch(c)+c->x); ldy(c,c->m[z]); break;
    case 0xc8: c->y++; nz(c,c->y); break;
    case 0xc9: cmpa(c,fetch(c)); break;
    case 0xd0: branch(c, !(c->p&Z)); break;
    case 0xe5: sbc(c,c->m[fetch(c)]); break;
    case 0xe6: z=fetch(c); c->m[z]++; nz(c,c->m[z]); break;
    case 0xe9: sbc(c,fetch(c)); break;
    case 0xf0: branch(c, c->p&Z); break;
    default:
        fprintf(stderr,"unsupported opcode $%02x at $%04x\n",op,(uint16_t)(c->pc-1)); exit(2);
    }
    return 1;
}

static void load(Cpu *c, const char *path, uint16_t base) {
    FILE *f=fopen(path,"rb");
    if (!f) die(path);
    if (fread(c->m+base,1,8192,f)!=8192 || fgetc(f)!=EOF) { fprintf(stderr,"bad ROM size: %s\n",path); exit(1); }
    fclose(f);
}
static int hex_digit(char c){if(c>='0'&&c<='9')return c-'0';if(c>='a'&&c<='f')return c-'a'+10;if(c>='A'&&c<='F')return c-'A'+10;return -1;}
static Cpu *new_cpu(const char *basic, const char *kernal) {
    static const uint8_t initial[5]={0x80,0x4f,0xc7,0x52,0x58};
    Cpu *c=calloc(1,sizeof(*c)); if(!c) die("calloc");
    load(c,basic,0xa000); load(c,kernal,0xe000); memcpy(c->m+RNDX,initial,5);
    const char *text=getenv("RND_START");
    if(text){if(strlen(text)!=10){fprintf(stderr,"RND_START must be exactly 10 hexadecimal digits\n");exit(2);}for(unsigned i=0;i<5;i++){int hi=hex_digit(text[i*2]),lo=hex_digit(text[i*2+1]);if(hi<0||lo<0){fprintf(stderr,"invalid RND_START\n");exit(2);}c->m[RNDX+i]=(uint8_t)((hi<<4)|lo);}}
    return c;
}
static State state(const Cpu *c) { State s; memcpy(s.b,c->m+RNDX,5); return s; }
static int equal(State a, State b) { return memcmp(a.b,b.b,5)==0; }
static uint64_t state_hash(State s) {
    uint64_t h=UINT64_C(1469598103934665603);
    for(unsigned i=0;i<5;i++){h^=s.b[i];h*=UINT64_C(1099511628211);}
    return h;
}
static State advance(Cpu *c) {
    c->a=c->x=c->y=0; c->p=U; c->sp=0xff; c->pc=ENTRY;
    while(step(c)) {}
    return state(c);
}
static void show(uint64_t n,State s){printf("%" PRIu64 ": %02x %02x %02x %02x %02x\n",n,s.b[0],s.b[1],s.b[2],s.b[3],s.b[4]);}
static double seconds(void){return (double)clock()/CLOCKS_PER_SEC;}

int main(int argc,char **argv) {
    if(argc<3 || argc>4){fprintf(stderr,"usage: %s BASIC-ROM KERNAL-ROM [--vectors-only|--steps=N|--seen|--digest=N]\n",argv[0]);return 2;}
    Cpu *c=new_cpu(argv[1],argv[2]); State initial=state(c); show(0,initial);
    State s1=advance(c),s2; show(1,s1); s2=advance(c); show(2,s2);
    const uint8_t e1[5]={0x7e,0x3e,0x04,0x7e,0x4e},e2[5]={0x7c,0x40,0x18,0xc8,0x69};
    if(!getenv("RND_START")){
        if(memcmp(s1.b,e1,5)||memcmp(s2.b,e2,5)){fprintf(stderr,"vector mismatch\n");return 1;}
        puts("supplied transition vectors match the pinned ROM");
    }
    if(argc==4 && !strncmp(argv[3],"--steps=",8)) {
        char *end=NULL; uint64_t n=strtoull(argv[3]+8,&end,10);
        if(!end || *end || n<2){fprintf(stderr,"invalid step count\n");return 2;}
        for(uint64_t i=2;i<n;i++) s2=advance(c);
        show(n,s2); free(c); return 0;
    }
    if(argc==4 && !strncmp(argv[3],"--digest=",9)) {
        char *end=NULL;uint64_t n=strtoull(argv[3]+9,&end,10),h=UINT64_C(1469598103934665603);
        if(!end||*end)return 2;
        free(c);c=new_cpu(argv[1],argv[2]);State current=state(c);
        for(uint64_t i=0;i<=n;i++){for(unsigned j=0;j<5;j++){h^=current.b[j];h*=UINT64_C(1099511628211);}if(i<n)current=advance(c);}
        printf("digest through x[%" PRIu64 "]: %016" PRIx64 "\n",n,h);free(c);return 0;
    }
    if(argc==4 && !strcmp(argv[3],"--seen")) {
        enum { SIZE=1<<20 }; SeenSlot *table=calloc(SIZE,sizeof(*table)); if(!table)die("calloc seen");
        free(c);c=new_cpu(argv[1],argv[2]);State current=state(c);uint64_t index=0;
        for(;;index++){
            size_t at=(size_t)state_hash(current)&(SIZE-1);
            while(table[at].used && !equal(table[at].state,current))at=(at+1)&(SIZE-1);
            if(table[at].used){printf("first repeated index: %" PRIu64 "\nfirst seen index (mu): %" PRIu64 "\ncycle (lambda): %" PRIu64 "\n",index,table[at].index,index-table[at].index);break;}
            table[at].used=1;table[at].state=current;table[at].index=index;current=advance(c);
        }
        free(table);free(c);return 0;
    }
    if(argc==4){free(c);return strcmp(argv[3],"--vectors-only")?2:0;}
    free(c); c=new_cpu(argv[1],argv[2]);
    uint64_t power=1,lambda=1,transitions=1; State tortoise=initial,hare=advance(c); double began=seconds();
    while(!equal(tortoise,hare)){
        if(power==lambda){tortoise=hare;power<<=1;lambda=0;}
        hare=advance(c);lambda++;transitions++;
        if(transitions%10000000==0) fprintf(stderr,"phase1 transitions=%" PRIu64 " power=%" PRIu64 " lambda=%" PRIu64 " rate=%.0f/s\n",transitions,power,lambda,transitions/(seconds()-began));
    }
    Cpu *tc=new_cpu(argv[1],argv[2]),*hc=new_cpu(argv[1],argv[2]);
    for(uint64_t i=0;i<lambda;i++) advance(hc);
    uint64_t mu=0; tortoise=state(tc);hare=state(hc);
    while(!equal(tortoise,hare)){tortoise=advance(tc);hare=advance(hc);mu++;transitions+=2;}
    printf("on-ramp (mu): %" PRIu64 "\ncycle (lambda): %" PRIu64 "\nROM transitions evaluated: %" PRIu64 "\n6502 instructions evaluated: %" PRIu64 "\n",mu,lambda,transitions,instruction_count);
    free(c);free(tc);free(hc);return 0;
}
