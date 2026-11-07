/* Export exact joint (cycle length, mu, count) aggregates from completed V2 metadata.
 * This does not use ROM bytes and does not emit per-state records.
 */
#define _POSIX_C_SOURCE 200809L
#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>

#define MAGIC UINT64_C(0x324b4348444e5252)
#define VERSION 2u
#define DOMAIN UINT32_C(0xaf000000)
#define MAX_CLASSES 254u
#define VALUE_MASK UINT32_C(0x00ffffff)

typedef struct {
    uint64_t magic;
    uint32_t version;
    uint32_t domain_size;
    uint64_t next_scan;
    uint64_t classified_states;
    uint64_t checkpoint_sequence;
    uint64_t complete;
    uint32_t cycle_class_count;
    uint32_t reserved;
    uint32_t cycle_lengths[MAX_CLASSES];
    uint64_t checksum;
} Checkpoint;

static void die(const char *message) {
    perror(message);
    exit(1);
}

static uint64_t checksum(const Checkpoint *value) {
    uint64_t result = value->magic ^ value->version ^ value->domain_size
                    ^ value->next_scan ^ value->classified_states
                    ^ value->checkpoint_sequence ^ value->complete
                    ^ value->cycle_class_count ^ UINT64_C(0xc64b451c6502f00d);
    for (unsigned index = 0; index < MAX_CLASSES; index++)
        result = (result << 7 | result >> 57) ^ value->cycle_lengths[index];
    return result;
}

static void join(char *destination, size_t size, const char *directory, const char *name) {
    int amount = snprintf(destination, size, "%s/%s", directory, name);
    if (amount < 0 || (size_t)amount >= size) {
        fputs("path too long\n", stderr);
        exit(1);
    }
}

int main(int argc, char **argv) {
    if (argc != 3) {
        fprintf(stderr, "usage: %s RUN_DIRECTORY OUTPUT.csv\n", argv[0]);
        return 2;
    }
    char checkpoint_path[4096], metadata_path[4096];
    join(checkpoint_path, sizeof(checkpoint_path), argv[1], "checkpoint.bin");
    join(metadata_path, sizeof(metadata_path), argv[1], "metadata.bin");

    FILE *checkpoint_file = fopen(checkpoint_path, "rb");
    if (!checkpoint_file) die(checkpoint_path);
    Checkpoint checkpoint;
    if (fread(&checkpoint, sizeof(checkpoint), 1, checkpoint_file) != 1
        || fgetc(checkpoint_file) != EOF || fclose(checkpoint_file)) {
        fputs("invalid checkpoint size/read\n", stderr);
        return 1;
    }
    if (checkpoint.magic != MAGIC || checkpoint.version != VERSION
        || checkpoint.domain_size != DOMAIN || checkpoint.next_scan != DOMAIN
        || checkpoint.classified_states != DOMAIN || !checkpoint.complete
        || !checkpoint.cycle_class_count || checkpoint.cycle_class_count > MAX_CLASSES
        || checkpoint.checksum != checksum(&checkpoint)) {
        fputs("refusing incomplete, corrupt, or incompatible checkpoint\n", stderr);
        return 1;
    }

    int fd = open(metadata_path, O_RDONLY);
    if (fd < 0) die(metadata_path);
    struct stat status;
    if (fstat(fd, &status)) die("fstat metadata");
    size_t expected_bytes = (size_t)DOMAIN * sizeof(uint32_t);
    if ((uint64_t)status.st_size != expected_bytes) {
        fputs("metadata has wrong size\n", stderr);
        return 1;
    }
    const uint32_t *metadata = mmap(NULL, expected_bytes, PROT_READ, MAP_SHARED, fd, 0);
    if (metadata == MAP_FAILED) die("mmap metadata");
#ifdef MADV_SEQUENTIAL
    (void)madvise((void *)metadata, expected_bytes, MADV_SEQUENTIAL);
#endif

    uint32_t max_mu = 0;
    for (uint32_t rank = 0; rank < DOMAIN; rank++) {
        uint32_t entry = metadata[rank];
        unsigned code = entry >> 24;
        if (!code || code > checkpoint.cycle_class_count) {
            fprintf(stderr, "unclassified/invalid metadata at rank %" PRIu32 "\n", rank);
            return 1;
        }
        uint32_t mu = entry & VALUE_MASK;
        if (mu > max_mu) max_mu = mu;
    }

    size_t stride = (size_t)max_mu + 1;
    size_t cells = (size_t)checkpoint.cycle_class_count * stride;
    if (cells > SIZE_MAX / sizeof(uint64_t)) {
        fputs("joint histogram allocation overflow\n", stderr);
        return 1;
    }
    uint64_t *counts = calloc(cells, sizeof(*counts));
    if (!counts) die("calloc joint histogram");
    for (uint32_t rank = 0; rank < DOMAIN; rank++) {
        uint32_t entry = metadata[rank];
        unsigned code = entry >> 24;
        uint32_t mu = entry & VALUE_MASK;
        counts[(size_t)(code - 1) * stride + mu]++;
    }

    FILE *output = fopen(argv[2], "w");
    if (!output) die(argv[2]);
    fputs("lambda,mu,count\n", output);
    uint64_t total = 0;
    for (unsigned code = 1; code <= checkpoint.cycle_class_count; code++) {
        uint32_t lambda = checkpoint.cycle_lengths[code - 1];
        if (!lambda) {
            fputs("zero cycle length in checkpoint\n", stderr);
            return 1;
        }
        for (uint32_t mu = 0; mu <= max_mu; mu++) {
            uint64_t count = counts[(size_t)(code - 1) * stride + mu];
            total += count;
            if (count)
                fprintf(output, "%" PRIu32 ",%" PRIu32 ",%" PRIu64 "\n",
                        lambda, mu, count);
        }
    }
    if (fclose(output)) die("close output");
    if (total != DOMAIN) {
        fprintf(stderr, "joint histogram sum mismatch: %" PRIu64 "\n", total);
        return 1;
    }
    fprintf(stderr, "exported %" PRIu64 " states; classes=%u max_mu=%" PRIu32 "\n",
            total, checkpoint.cycle_class_count, max_mu);
    free(counts);
    if (munmap((void *)metadata, expected_bytes)) die("munmap metadata");
    if (close(fd)) die("close metadata");
    return 0;
}
