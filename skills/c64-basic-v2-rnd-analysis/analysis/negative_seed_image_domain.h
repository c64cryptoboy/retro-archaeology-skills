#ifndef C64_BASIC_RND_NEGATIVE_SEED_IMAGE_DOMAIN_H
#define C64_BASIC_RND_NEGATIVE_SEED_IMAGE_DOMAIN_H

#include <stdint.h>

#define NEGATIVE_SEED_IMAGE_SIZE UINT64_C(10745675776)

static const uint64_t negative_seed_image_category_offsets[25] = {
    UINT64_C(0), UINT64_C(1082130432), UINT64_C(2160066560),
    UINT64_C(3235905536), UINT64_C(4310695936), UINT64_C(5384962048),
    UINT64_C(6458966016), UINT64_C(7532838912), UINT64_C(8606580736),
    UINT64_C(9676128256), UINT64_C(10210902016), UINT64_C(10478288896),
    UINT64_C(10611982336), UINT64_C(10678829056), UINT64_C(10712252416),
    UINT64_C(10728964096), UINT64_C(10737319936), UINT64_C(10741497856),
    UINT64_C(10743586816), UINT64_C(10744631296), UINT64_C(10745153536),
    UINT64_C(10745414656), UINT64_C(10745545216), UINT64_C(10745610496),
    UINT64_C(10745643136),
};

static const uint32_t negative_seed_image_category_counts[25] = {
    UINT32_C(1082130432), UINT32_C(1077936128), UINT32_C(1075838976),
    UINT32_C(1074790400), UINT32_C(1074266112), UINT32_C(1074003968),
    UINT32_C(1073872896), UINT32_C(1073741824), UINT32_C(1069547520),
    UINT32_C(534773760), UINT32_C(267386880), UINT32_C(133693440),
    UINT32_C(66846720), UINT32_C(33423360), UINT32_C(16711680),
    UINT32_C(8355840), UINT32_C(4177920), UINT32_C(2088960),
    UINT32_C(1044480), UINT32_C(522240), UINT32_C(261120),
    UINT32_C(130560), UINT32_C(65280), UINT32_C(32640), UINT32_C(32640),
};

static uint32_t negative_seed_image_mantissa_count(unsigned shifts) {
    return shifts < 24 ? UINT32_C(1) << (30 - shifts) : 128u;
}

static uint32_t negative_seed_image_expand_reversed(uint32_t index,
                                                     unsigned shifts) {
    unsigned high_bit = 31 - shifts;
    if (index >= negative_seed_image_mantissa_count(shifts)) return UINT32_MAX;
    if (shifts == 24) return 0x80u | index;
    return (UINT32_C(1) << high_bit) | ((index >> 7) << 8)
         | 0x80u | (index & 0x7fu);
}

/* State must be the five-byte State type declared by generated_rnd_cycle.c. */
static State negative_seed_image_unrank(uint64_t index) {
    State result = {{0}};
    if (index >= NEGATIVE_SEED_IMAGE_SIZE) return result;
    unsigned shifts = 24;
    while (index < negative_seed_image_category_offsets[shifts]) shifts--;
    uint64_t local = index - negative_seed_image_category_offsets[shifts];
    uint64_t scale = UINT64_C(1) << shifts;
    uint64_t wide_mantissa;
    if (shifts <= 6) {
        uint64_t run_size = 128u * scale + 1u;
        uint64_t run = local / run_size;
        uint64_t within = local % run_size;
        unsigned high_bit = 31 - shifts;
        uint32_t reversed_first = (UINT32_C(1) << high_bit)
                                | ((uint32_t)run << 8) | 0x80u;
        wide_mantissa = (uint64_t)reversed_first * scale + within;
    } else if (shifts == 7) {
        uint32_t reversed_index = (uint32_t)(local / 128u);
        uint32_t contribution_index = (uint32_t)(local % 128u);
        uint32_t reversed = negative_seed_image_expand_reversed(reversed_index, shifts);
        wide_mantissa = (uint64_t)reversed * scale + contribution_index + 1u;
    } else {
        uint32_t reversed_index = (uint32_t)(local / 255u);
        uint32_t contribution_index = (uint32_t)(local % 255u);
        uint32_t reversed = negative_seed_image_expand_reversed(reversed_index, shifts);
        wide_mantissa = (uint64_t)reversed * scale
                      + ((uint64_t)(contribution_index + 1u) << (shifts - 8));
    }
    uint8_t exponent = (uint8_t)(0x80 - shifts);
    uint32_t mantissa;
    if (wide_mantissa == (UINT64_C(1) << 32)) {
        exponent++;
        mantissa = UINT32_C(0x80000000);
    } else {
        mantissa = (uint32_t)wide_mantissa;
    }
    result.b[0] = exponent;
    result.b[1] = (uint8_t)(mantissa >> 24) & 0x7f;
    result.b[2] = (uint8_t)(mantissa >> 16);
    result.b[3] = (uint8_t)(mantissa >> 8);
    result.b[4] = (uint8_t)mantissa;
    return result;
}

#endif
