/* Probe the exact generated ROM path at the pre-shuffle $E0D3 boundary. */
#define GENERATED_RND_NO_MAIN
#include "generated_rnd_cycle.c"

static uint8_t intermediate[6];

static void capture_intermediate(const Cpu *cpu) {
    memcpy(intermediate, cpu->m + 0x61, sizeof(intermediate));
}

static void print_five(State value) {
    for (unsigned i = 0; i < 5; i++) {
        if (i) putchar(' ');
        printf("%02x", value.b[i]);
    }
}

int main(int argc, char **argv) {
    if (argc < 3 || argc > 4) {
        fprintf(stderr, "usage: %s BASIC-ROM KERNAL-ROM [count]\n", argv[0]);
        return 2;
    }
    char *end = NULL;
    uint64_t count = argc == 4 ? strtoull(argv[3], &end, 0) : 32;
    if (argc == 4 && (!end || *end)) {
        fputs("invalid count\n", stderr);
        return 2;
    }
    Cpu *cpu = new_cpu(argv[1], argv[2]);
    rnd_intermediate_hook = capture_intermediate;
    puts("index,input,fac_exp,fac_m0,fac_m1,fac_m2,fac_m3,guard,output");
    for (uint64_t index = 0; index < count; index++) {
        State before = state(cpu);
        if (!equal(before, before) || hash(before) == UINT64_MAX) return 3;
        State after = advance(cpu);
        printf("%" PRIu64 ",", index);
        print_five(before);
        for (unsigned i = 0; i < sizeof(intermediate); i++) printf(",%02x", intermediate[i]);
        putchar(',');
        print_five(after);
        putchar('\n');
    }
    free(cpu);
    return 0;
}
