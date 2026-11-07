/* Find all positive-RND numeric predecessors for selected pre-shuffle FACs.
 * Includes the private generated ROM-derived transition oracle; do not publish
 * the resulting executable or generated_rnd_cycle.c by default.
 */
#define GENERATED_RND_NO_MAIN
#include "generated_rnd_cycle.c"

#define INPUT_MIN_EXP 0x68u
#define INPUT_REGULAR_EXPONENTS 25u /* $68 through $80 inclusive */
#define MANTISSAS_PER_EXP UINT64_C(0x80000000)
#define INPUT_COUNT (INPUT_REGULAR_EXPONENTS * MANTISSAS_PER_EXP + 1u)

static uint8_t captured_fac[5];

static void capture_intermediate(const Cpu *cpu) {
    memcpy(captured_fac, cpu->m + 0x61, sizeof(captured_fac));
}

static State ordinal_state(uint64_t ordinal) {
    State result;
    uint8_t exponent;
    uint32_t mantissa;
    if (ordinal >= INPUT_COUNT) {
        fputs("input ordinal outside supported range\n", stderr);
        exit(1);
    }
    if (ordinal == INPUT_COUNT - 1) {
        exponent = 0x81;
        mantissa = UINT32_C(0x80000000);
    } else {
        exponent = (uint8_t)(INPUT_MIN_EXP + ordinal / MANTISSAS_PER_EXP);
        mantissa = UINT32_C(0x80000000)
                 + (uint32_t)(ordinal % MANTISSAS_PER_EXP);
    }
    result.b[0] = exponent;
    result.b[1] = (uint8_t)(mantissa >> 24) & 0x7f;
    result.b[2] = (uint8_t)(mantissa >> 16);
    result.b[3] = (uint8_t)(mantissa >> 8);
    result.b[4] = (uint8_t)mantissa;
    return result;
}

static int compare_fac(const uint8_t left[5], const uint8_t right[5]) {
    return memcmp(left, right, 5);
}

static void evaluate(Cpu *cpu, uint64_t ordinal, uint8_t fac[5], State *output) {
    State input = ordinal_state(ordinal);
    memcpy(cpu->m + RNDX, input.b, sizeof(input.b));
    *output = advance(cpu);
    memcpy(fac, captured_fac, 5);
}

static uint64_t lower_bound(Cpu *cpu, const uint8_t target[5], int strict) {
    uint64_t low = 0, high = INPUT_COUNT;
    while (low < high) {
        uint64_t middle = low + (high - low) / 2;
        uint8_t actual[5];
        State ignored;
        evaluate(cpu, middle, actual, &ignored);
        int comparison = compare_fac(actual, target);
        if (comparison < 0 || (strict && comparison == 0)) low = middle + 1;
        else high = middle;
    }
    return low;
}

static int parse_hex5(const char *text, uint8_t result[5]) {
    if (strlen(text) != 10) return 0;
    for (unsigned index = 0; index < 5; index++) {
        int high = hex_digit(text[index * 2]);
        int low = hex_digit(text[index * 2 + 1]);
        if (high < 0 || low < 0) return 0;
        result[index] = (uint8_t)((high << 4) | low);
    }
    return 1;
}

static void print_state(State state_value) {
    for (unsigned index = 0; index < 5; index++) printf("%02x", state_value.b[index]);
}

int main(int argc, char **argv) {
    if (argc != 4) {
        fprintf(stderr, "usage: %s BASIC-ROM KERNAL-ROM TARGETS.csv\n", argv[0]);
        return 2;
    }
    FILE *input = fopen(argv[3], "r");
    if (!input) die(argv[3]);
    char line[1024];
    if (!fgets(line, sizeof(line), input)) {
        fputs("empty target file\n", stderr);
        return 1;
    }

    Cpu *cpu = new_cpu(argv[1], argv[2]);
    State probe = state(cpu);
    if (!equal(probe, probe) || hash(probe) == UINT64_MAX) return 3;
    rnd_intermediate_hook = capture_intermediate;
    puts("rank,lambda,mu,component_max_mu,target_state,intermediate_fac,predecessor_state");

    uint64_t rows = 0, predecessors = 0;
    while (fgets(line, sizeof(line), input)) {
        uint32_t rank, lambda, mu, maximum;
        char target_text[11], fac_text[11];
        if (sscanf(line, "%" SCNu32 ",%" SCNu32 ",%" SCNu32 ",%" SCNu32
                         ",%10[0123456789abcdefABCDEF],%10[0123456789abcdefABCDEF]",
                   &rank, &lambda, &mu, &maximum, target_text, fac_text) != 6) {
            fprintf(stderr, "invalid input row: %s", line);
            return 1;
        }
        uint8_t target_bytes[5], target_fac[5];
        if (!parse_hex5(target_text, target_bytes) || !parse_hex5(fac_text, target_fac)) {
            fprintf(stderr, "invalid hex input row: %s", line);
            return 1;
        }
        uint64_t first = lower_bound(cpu, target_fac, 0);
        uint64_t after = lower_bound(cpu, target_fac, 1);
        if (after < first || after - first > 1024) {
            fputs("unexpected predecessor interval size\n", stderr);
            return 1;
        }
        uint8_t boundary_fac[5];
        State boundary_output;
        if (first) {
            evaluate(cpu, first - 1, boundary_fac, &boundary_output);
            if (compare_fac(boundary_fac, target_fac) >= 0) {
                fputs("invalid lower-bound predecessor\n", stderr);
                return 1;
            }
        }
        if (first < INPUT_COUNT) {
            evaluate(cpu, first, boundary_fac, &boundary_output);
            if (compare_fac(boundary_fac, target_fac) < 0) {
                fputs("invalid lower bound\n", stderr);
                return 1;
            }
        }
        if (after) {
            evaluate(cpu, after - 1, boundary_fac, &boundary_output);
            if (compare_fac(boundary_fac, target_fac) > 0) {
                fputs("invalid upper-bound predecessor\n", stderr);
                return 1;
            }
        }
        if (after < INPUT_COUNT) {
            evaluate(cpu, after, boundary_fac, &boundary_output);
            if (compare_fac(boundary_fac, target_fac) <= 0) {
                fputs("invalid upper bound\n", stderr);
                return 1;
            }
        }
        for (uint64_t ordinal = first; ordinal < after; ordinal++) {
            uint8_t actual_fac[5];
            State output;
            evaluate(cpu, ordinal, actual_fac, &output);
            if (memcmp(actual_fac, target_fac, 5)
                || memcmp(output.b, target_bytes, 5)) {
                fputs("inverse candidate failed exact forward validation\n", stderr);
                return 1;
            }
            printf("%" PRIu32 ",%" PRIu32 ",%" PRIu32 ",%" PRIu32 ",%s,%s,",
                   rank, lambda, mu, maximum, target_text, fac_text);
            print_state(ordinal_state(ordinal));
            putchar('\n');
            predecessors++;
        }
        rows++;
    }
    if (ferror(input) || fclose(input)) die("read/close targets");
    fprintf(stderr, "processed %" PRIu64 " intermediate FACs; found %" PRIu64
                    " exact numeric predecessors\n", rows, predecessors);
    free(cpu);
    return 0;
}
