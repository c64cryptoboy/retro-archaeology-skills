#ifndef C64_BASIC_RND_CANONICAL_SEED_DOMAIN_H
#define C64_BASIC_RND_CANONICAL_SEED_DOMAIN_H

#include <stdint.h>

#define CANONICAL_DOMAIN_SIZE UINT32_C(0xaf000000)
#define CANONICAL_MIN_INTERMEDIATE_EXPONENT 0x7f
#define CANONICAL_MAX_INTERMEDIATE_EXPONENT 0x98

static const uint32_t canonical_category_offsets[25] = {
    0u, 1082130432u, 1619001344u, 1887436800u, 2155872256u,
    2357198848u, 2491416576u, 2608857088u, 2717908992u, 2826960896u,
    2881486848u, 2908749824u, 2922381312u, 2929197056u, 2932604928u,
    2934308864u, 2935160832u, 2935586816u, 2935799808u, 2935906304u,
    2935959552u, 2935986176u, 2935999488u, 2936006144u, 2936009472u,
};

static const uint32_t canonical_category_counts[25] = {
    1082130432u, 536870912u, 268435456u, 268435456u, 201326592u,
    134217728u, 117440512u, 109051904u, 109051904u, 54525952u,
    27262976u, 13631488u, 6815744u, 3407872u, 1703936u,
    851968u, 425984u, 212992u, 106496u, 53248u,
    26624u, 13312u, 6656u, 3328u, 3328u,
};

static unsigned canonical_contribution_count(unsigned shifts) {
    static const uint8_t small_counts[8] = {2, 1, 1, 2, 3, 4, 7, 13};
    return shifts < 8 ? small_counts[shifts] : 26;
}

static uint32_t canonical_contribution(unsigned shifts, unsigned index) {
    if (index >= canonical_contribution_count(shifts)) return UINT32_MAX;
    if (shifts < 8) {
        uint32_t first = ((CANONICAL_MIN_INTERMEDIATE_EXPONENT << shifts) + 0x80u) >> 8;
        return first + index;
    }
    return (CANONICAL_MIN_INTERMEDIATE_EXPONENT + index) << (shifts - 8);
}

static uint32_t canonical_expand_reversed(uint32_t index, unsigned shifts) {
    unsigned high_bit = 31 - shifts;
    if (shifts == 24) return 0x80u | index;
    return (UINT32_C(1) << high_bit) | ((index >> 7) << 8) | 0x80u | (index & 0x7fu);
}

static int canonical_compress_reversed(uint32_t value, unsigned shifts, uint32_t *index) {
    unsigned high_bit = 31 - shifts;
    if (!(value & 0x80u) || (31u - (unsigned)__builtin_clz(value)) != high_bit) return 0;
    if (shifts == 24) {
        *index = value & 0x7fu;
    } else {
        *index = (((value & ((UINT32_C(1) << high_bit) - 1)) >> 8) << 7)
               | (value & 0x7fu);
    }
    return 1;
}

/* State must be the five-byte State type declared by generated_rnd_cycle.c. */
static State canonical_domain_unrank(uint32_t index) {
    State result = {{0}};
    unsigned shifts = 24;
    while (index < canonical_category_offsets[shifts]) shifts--;
    uint32_t local = index - canonical_category_offsets[shifts];
    uint64_t mantissa;
    if (shifts == 0) {
        uint32_t block = local / 129u;
        uint32_t within = local % 129u;
        mantissa = UINT64_C(0x80000080) + ((uint64_t)block << 8) + within;
        if (mantissa == (UINT64_C(1) << 32)) {
            result.b[0] = 0x81;
            mantissa = UINT32_C(0x80000000);
        } else {
            result.b[0] = 0x80;
        }
    } else {
        unsigned count = canonical_contribution_count(shifts);
        uint32_t reversed_index = local / count;
        unsigned contribution_index = local % count;
        uint32_t reversed = canonical_expand_reversed(reversed_index, shifts);
        mantissa = ((uint64_t)reversed << shifts)
                 + canonical_contribution(shifts, contribution_index);
        result.b[0] = (uint8_t)(0x80 - shifts);
    }
    uint32_t m = (uint32_t)mantissa;
    result.b[1] = (uint8_t)((m >> 24) & 0x7f);
    result.b[2] = (uint8_t)(m >> 16);
    result.b[3] = (uint8_t)(m >> 8);
    result.b[4] = (uint8_t)m;
    return result;
}

static int canonical_domain_rank(State state_value, uint32_t *index) {
    uint32_t mantissa = ((uint32_t)(state_value.b[1] | 0x80) << 24)
                      | ((uint32_t)state_value.b[2] << 16)
                      | ((uint32_t)state_value.b[3] << 8)
                      | state_value.b[4];
    if (state_value.b[1] & 0x80) return 0;
    if (state_value.b[0] == 0x81 && mantissa == UINT32_C(0x80000000)) {
        *index = canonical_category_counts[0] - 1;
        return 1;
    }
    if (state_value.b[0] < 0x68 || state_value.b[0] > 0x80) return 0;
    unsigned shifts = 0x80 - state_value.b[0];
    uint32_t local;
    if (shifts == 0) {
        uint32_t low = mantissa & 0xffu;
        uint32_t upper = mantissa >> 8;
        uint32_t block, within;
        if (low >= 0x80u) {
            block = upper - 0x800000u;
            within = low - 0x80u;
        } else if (low == 0 && upper > 0x800000u) {
            block = upper - 0x800001u;
            within = 128;
        } else {
            return 0;
        }
        local = block * 129u + within;
    } else {
        uint32_t mask = (UINT32_C(1) << shifts) - 1;
        uint32_t contribution = mantissa & mask;
        uint32_t first = canonical_contribution(shifts, 0);
        unsigned contribution_index;
        if (shifts < 8) {
            if (contribution < first) return 0;
            contribution_index = contribution - first;
        } else {
            uint32_t scale = UINT32_C(1) << (shifts - 8);
            if (contribution < first || contribution % scale) return 0;
            contribution_index = (contribution - first) / scale;
        }
        unsigned count = canonical_contribution_count(shifts);
        if (contribution_index >= count) return 0;
        uint32_t reversed_index;
        if (!canonical_compress_reversed(mantissa >> shifts, shifts, &reversed_index)) return 0;
        local = reversed_index * count + contribution_index;
    }
    if (local >= canonical_category_counts[shifts]) return 0;
    *index = canonical_category_offsets[shifts] + local;
    return *index < CANONICAL_DOMAIN_SIZE;
}

#endif
