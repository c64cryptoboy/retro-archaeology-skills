/* Validate canonical-domain ranking and closure against generated ROM C. */
#define GENERATED_RND_NO_MAIN
#include "generated_rnd_cycle.c"
#include "canonical_seed_domain.h"

static uint32_t permute32(uint32_t value) {
    value ^= value >> 16;
    value *= UINT32_C(0x7feb352d);
    value ^= value >> 15;
    value *= UINT32_C(0x846ca68b);
    value ^= value >> 16;
    return value;
}

static void show_state(State value) {
    for (unsigned i = 0; i < 5; i++) printf("%s%02x", i ? " " : "", value.b[i]);
}

int main(int argc, char **argv) {
    if (argc < 3 || argc > 4) {
        fprintf(stderr, "usage: %s BASIC-ROM KERNAL-ROM [cases]\n", argv[0]);
        return 2;
    }
    char *end = NULL;
    uint64_t cases = argc == 4 ? strtoull(argv[3], &end, 0) : UINT64_C(1000000);
    if (argc == 4 && (!end || *end)) return 2;
    for (unsigned shifts = 0; shifts < 25; shifts++) {
        uint32_t probes[2] = {
            canonical_category_offsets[shifts],
            canonical_category_offsets[shifts] + canonical_category_counts[shifts] - 1,
        };
        for (unsigned p = 0; p < 2; p++) {
            State value = canonical_domain_unrank(probes[p]);
            uint32_t recovered;
            if (!equal(value, value) || !canonical_domain_rank(value, &recovered) || recovered != probes[p]) {
                fprintf(stderr, "boundary round-trip failed at %" PRIu32 "\n", probes[p]);
                return 1;
            }
        }
    }

    Cpu *cpu = new_cpu(argv[1], argv[2]);
    uint64_t closure_digest = UINT64_C(1469598103934665603);
    uint64_t accepted = 0;
    for (uint64_t candidate = 0; accepted < cases; candidate++) {
        if (candidate > UINT32_MAX) {
            fputs("requested more unique permuted cases than available\n", stderr);
            return 2;
        }
        uint32_t index = permute32((uint32_t)candidate + UINT32_C(0x6502c64));
        if (index >= CANONICAL_DOMAIN_SIZE) continue;
        State input = canonical_domain_unrank(index);
        uint32_t recovered;
        if (!canonical_domain_rank(input, &recovered) || recovered != index) {
            fprintf(stderr, "rank round-trip failed at index %" PRIu32 "\n", index);
            return 1;
        }
        memcpy(cpu->m + RNDX, input.b, 5);
        cpu->m[0x68] = 0;
        State output = advance(cpu);
        uint32_t output_index;
        if (!canonical_domain_rank(output, &output_index)) {
            fprintf(stderr, "closure failed at index %" PRIu32 " input=", index);
            show_state(input);
            fputs(" output=", stderr);
            show_state(output);
            putchar('\n');
            return 1;
        }
        closure_digest ^= hash(input);
        closure_digest *= UINT64_C(1099511628211);
        closure_digest ^= index;
        closure_digest *= UINT64_C(1099511628211);
        closure_digest ^= output_index;
        closure_digest *= UINT64_C(1099511628211);
        accepted++;
    }
    printf("domain_size=%" PRIu32 " ($%08" PRIx32 ") cases=%" PRIu64
           " closure_digest=%016" PRIx64 "\n",
           CANONICAL_DOMAIN_SIZE, CANONICAL_DOMAIN_SIZE, accepted, closure_digest);
    free(cpu);
    return 0;
}
