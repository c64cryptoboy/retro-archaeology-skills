/* Extract canonical ranks in the maximum-mu and (maximum-mu - 1) layers
 * of every component from completed V2 metadata. This reads retained metadata
 * only; it evaluates no RND transitions and modifies no run artifacts.
 */
#define _POSIX_C_SOURCE 200809L
#include <fcntl.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
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

static void die(const char *message) { perror(message); exit(1); }

static uint64_t checkpoint_checksum(const Checkpoint *value) {
    uint64_t result = value->magic ^ value->version ^ value->domain_size
                    ^ value->next_scan ^ value->classified_states
                    ^ value->checkpoint_sequence ^ value->complete
                    ^ value->cycle_class_count ^ UINT64_C(0xc64b451c6502f00d);
    for (unsigned index = 0; index < MAX_CLASSES; index++)
        result = (result << 7 | result >> 57) ^ value->cycle_lengths[index];
    return result;
}

static void join(char *destination, size_t size, const char *directory,
                 const char *name) {
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
        || checkpoint.checksum != checkpoint_checksum(&checkpoint)) {
        fputs("refusing incomplete, corrupt, or incompatible checkpoint\n", stderr);
        return 1;
    }

    int fd = open(metadata_path, O_RDONLY);
    if (fd < 0) die(metadata_path);
    struct stat status;
    if (fstat(fd, &status)) die("fstat metadata");
    size_t bytes = (size_t)DOMAIN * sizeof(uint32_t);
    if ((uint64_t)status.st_size != bytes) {
        fputs("metadata has wrong size\n", stderr);
        return 1;
    }
    const uint32_t *metadata = mmap(NULL, bytes, PROT_READ, MAP_SHARED, fd, 0);
    if (metadata == MAP_FAILED) die("mmap metadata");
#ifdef MADV_SEQUENTIAL
    (void)madvise((void *)metadata, bytes, MADV_SEQUENTIAL);
#endif

    uint32_t maxima[MAX_CLASSES] = {0};
    for (uint32_t rank = 0; rank < DOMAIN; rank++) {
        uint32_t entry = metadata[rank];
        unsigned code = entry >> 24;
        uint32_t mu = entry & VALUE_MASK;
        if (!code || code > checkpoint.cycle_class_count) {
            fprintf(stderr, "invalid metadata at rank %" PRIu32 "\n", rank);
            return 1;
        }
        if (mu > maxima[code - 1]) maxima[code - 1] = mu;
    }

    FILE *output = fopen(argv[2], "w");
    if (!output) die(argv[2]);
    fputs("rank,lambda,mu,component_max_mu\n", output);
    uint64_t emitted = 0;
    for (uint32_t rank = 0; rank < DOMAIN; rank++) {
        uint32_t entry = metadata[rank];
        unsigned code = entry >> 24;
        uint32_t mu = entry & VALUE_MASK;
        uint32_t maximum = maxima[code - 1];
        if (mu == maximum || (maximum && mu == maximum - 1)) {
            fprintf(output, "%" PRIu32 ",%" PRIu32 ",%" PRIu32 ",%" PRIu32 "\n",
                    rank, checkpoint.cycle_lengths[code - 1], mu, maximum);
            emitted++;
        }
    }
    if (fclose(output)) die("close output");
    fprintf(stderr, "emitted %" PRIu64 " frontier states across %u components\n",
            emitted, checkpoint.cycle_class_count);

    if (munmap((void *)metadata, bytes)) die("munmap metadata");
    if (close(fd)) die("close metadata");
    return 0;
}
