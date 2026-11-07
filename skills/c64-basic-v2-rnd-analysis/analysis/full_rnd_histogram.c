/* Restartable exact whole-domain C64 BASIC V2 RND functional-graph classifier.
 *
 * Four-byte little-endian metadata entry by canonical rank:
 *   $00000000: unvisited
 *   $FFxxxxxx: current-path marker, low 24 bits = path index + 1
 *   $CCxxxxxx: classified, CC=1..254 cycle-length class, low 24 bits=mu
 *
 * The compact limits are checked. The runner refuses rather than truncating if
 * there are more than 254 distinct cycle lengths or mu/path exceeds 24 bits.
 *
 * Compile with -DFULL_RUNNER_SYNTHETIC -DFULL_RUNNER_DOMAIN_SIZE=1024 for
 * reduced-domain graph/restart validation.
 */
#define _GNU_SOURCE
#define _POSIX_C_SOURCE 200809L
#define GENERATED_RND_NO_MAIN
#include "generated_rnd_cycle.c"
#ifndef FULL_RUNNER_SYNTHETIC
#include "canonical_seed_domain.h"
#endif

#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <stdarg.h>
#include <stdbool.h>
#include <sys/file.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>

#if __BYTE_ORDER__ != __ORDER_LITTLE_ENDIAN__
#error "metadata format currently requires a little-endian host"
#endif

#ifdef FULL_RUNNER_SYNTHETIC
#ifndef FULL_RUNNER_DOMAIN_SIZE
#define FULL_RUNNER_DOMAIN_SIZE 1024u
#endif
#define RUNNER_DOMAIN_SIZE ((uint32_t)FULL_RUNNER_DOMAIN_SIZE)
#else
#define RUNNER_DOMAIN_SIZE CANONICAL_DOMAIN_SIZE
#endif

#define CHECKPOINT_MAGIC UINT64_C(0x324b4348444e5252) /* RRNDHCK2 */
#define CHECKPOINT_VERSION 2u
#define SCHEMA_NAME "c64-basic-rnd-full-histogram-v2"
#define META_VALUE_MASK UINT32_C(0x00ffffff)
#define META_MARKER_CLASS 255u
#define MAX_CYCLE_CLASSES 254u

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
    uint32_t cycle_lengths[MAX_CYCLE_CLASSES];
    uint64_t checksum;
} Checkpoint;

typedef struct {
    uint64_t *counts;
    size_t capacity;
    uint32_t maximum;
} Histogram;

typedef struct {
    Histogram mu;
    Histogram lambda;
    Histogram total;
    Histogram cycle_nodes;
    uint64_t classified;
} Aggregates;

typedef struct {
    const char *basic_path;
    const char *kernal_path;
    const char *workdir;
    int create;
    int sparse;
    uint64_t checkpoint_every;
    uint64_t stop_after_scans;
    uint64_t abort_after_transitions;
} Options;

typedef struct {
    uint32_t *metadata;
    size_t metadata_bytes;
    int metadata_fd;
    Cpu *cpu;
    uint64_t transitions_this_process;
    uint64_t abort_after_transitions;
} Runner;

static volatile sig_atomic_t stop_requested;

static void handle_stop(int signal_number) {
    (void)signal_number;
    stop_requested = 1;
}

static void failf(const char *format, ...) {
    va_list args;
    va_start(args, format);
    vfprintf(stderr, format, args);
    va_end(args);
    fputc('\n', stderr);
    exit(1);
}

static double seconds_now(void) {
    struct timespec value;
    clock_gettime(CLOCK_MONOTONIC, &value);
    return value.tv_sec + value.tv_nsec / 1000000000.0;
}

static uint64_t checkpoint_checksum(const Checkpoint *checkpoint) {
    uint64_t result = checkpoint->magic ^ checkpoint->version ^ checkpoint->domain_size
                    ^ checkpoint->next_scan ^ checkpoint->classified_states
                    ^ checkpoint->checkpoint_sequence ^ checkpoint->complete
                    ^ checkpoint->cycle_class_count ^ UINT64_C(0xc64b451c6502f00d);
    for (unsigned index = 0; index < MAX_CYCLE_CLASSES; index++)
        result = (result << 7 | result >> 57) ^ checkpoint->cycle_lengths[index];
    return result;
}

static void path_join(char *buffer, size_t size, const char *directory, const char *name) {
    int written = snprintf(buffer, size, "%s/%s", directory, name);
    if (written < 0 || (size_t)written >= size) failf("path too long: %s/%s", directory, name);
}

static void write_all(int fd, const void *data, size_t size) {
    const uint8_t *cursor = data;
    while (size) {
        ssize_t written = write(fd, cursor, size);
        if (written < 0) {
            if (errno == EINTR) continue;
            die("write");
        }
        cursor += written;
        size -= (size_t)written;
    }
}

static Checkpoint read_checkpoint(const char *workdir) {
    char path[4096];
    path_join(path, sizeof(path), workdir, "checkpoint.bin");
    int fd = open(path, O_RDONLY);
    if (fd < 0) die(path);
    Checkpoint checkpoint;
    size_t have = 0;
    while (have < sizeof(checkpoint)) {
        ssize_t amount = read(fd, (uint8_t *)&checkpoint + have, sizeof(checkpoint) - have);
        if (amount < 0) {
            if (errno == EINTR) continue;
            die("read checkpoint");
        }
        if (!amount) failf("short checkpoint file: %s", path);
        have += (size_t)amount;
    }
    uint8_t extra;
    if (read(fd, &extra, 1) != 0) failf("checkpoint has trailing data: %s", path);
    close(fd);
    uint64_t expected = checkpoint_checksum(&checkpoint);
    if (checkpoint.magic != CHECKPOINT_MAGIC || checkpoint.version != CHECKPOINT_VERSION
        || checkpoint.domain_size != RUNNER_DOMAIN_SIZE || checkpoint.checksum != expected
        || checkpoint.next_scan > RUNNER_DOMAIN_SIZE
        || checkpoint.cycle_class_count > MAX_CYCLE_CLASSES) {
        failf("invalid or incompatible checkpoint: %s", path);
    }
    for (unsigned index = 0; index < checkpoint.cycle_class_count; index++)
        if (!checkpoint.cycle_lengths[index]) failf("zero cycle length in checkpoint");
    return checkpoint;
}

static void write_checkpoint(const char *workdir, Checkpoint *checkpoint) {
    char path[4096], temporary[4096];
    path_join(path, sizeof(path), workdir, "checkpoint.bin");
    path_join(temporary, sizeof(temporary), workdir, "checkpoint.bin.tmp");
    checkpoint->checksum = checkpoint_checksum(checkpoint);
    int fd = open(temporary, O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (fd < 0) die(temporary);
    write_all(fd, checkpoint, sizeof(*checkpoint));
    if (fsync(fd)) die("fsync checkpoint");
    if (close(fd)) die("close checkpoint");
    if (rename(temporary, path)) die("rename checkpoint");
    int directory_fd = open(workdir, O_RDONLY | O_DIRECTORY);
    if (directory_fd < 0) die(workdir);
    if (fsync(directory_fd)) die("fsync workdir");
    close(directory_fd);
}

static unsigned meta_class(uint32_t entry) {
    return entry >> 24;
}

static uint32_t meta_value(uint32_t entry) {
    return entry & META_VALUE_MASK;
}

static uint32_t pack_meta(unsigned cycle_class, uint32_t value) {
    if (!cycle_class || cycle_class > MAX_CYCLE_CLASSES || value > META_VALUE_MASK)
        failf("metadata field overflow: class=%u value=%" PRIu32, cycle_class, value);
    return (uint32_t)(cycle_class << 24) | value;
}

static uint32_t pack_marker(size_t path_index) {
    if (path_index >= META_VALUE_MASK)
        failf("path exceeds guarded 24-bit compact representation");
    return UINT32_C(0xff000000) | ((uint32_t)path_index + 1);
}

static uint32_t load_meta(const Runner *runner, uint32_t key) {
    return __atomic_load_n(&runner->metadata[key], __ATOMIC_RELAXED);
}

static void store_raw_meta(Runner *runner, uint32_t key, uint32_t entry) {
    __atomic_store_n(&runner->metadata[key], entry, __ATOMIC_RELAXED);
}

static void histogram_add(Histogram *histogram, uint32_t value, uint64_t amount) {
    if (value >= histogram->capacity) {
        size_t capacity = histogram->capacity ? histogram->capacity : 1024;
        while (capacity <= value) capacity *= 2;
        uint64_t *replacement = realloc(histogram->counts, capacity * sizeof(*replacement));
        if (!replacement) die("realloc histogram");
        memset(replacement + histogram->capacity, 0,
               (capacity - histogram->capacity) * sizeof(*replacement));
        histogram->counts = replacement;
        histogram->capacity = capacity;
    }
    histogram->counts[value] += amount;
    if (value > histogram->maximum) histogram->maximum = value;
}

static void aggregate_classified(Aggregates *aggregates, uint32_t mu, uint32_t lambda) {
    if (!lambda) failf("attempted to aggregate an unclassified state");
    uint64_t total = (uint64_t)mu + lambda;
    if (total > RUNNER_DOMAIN_SIZE) failf("mu+lambda exceeds domain size");
    histogram_add(&aggregates->mu, mu, 1);
    histogram_add(&aggregates->lambda, lambda, 1);
    histogram_add(&aggregates->total, (uint32_t)total, 1);
    if (!mu) histogram_add(&aggregates->cycle_nodes, lambda, 1);
    aggregates->classified++;
}

static uint64_t histogram_sum(const Histogram *histogram) {
    uint64_t result = 0;
    if (!histogram->counts) return 0;
    for (uint32_t value = 0; value <= histogram->maximum; value++)
        result += histogram->counts[value];
    return result;
}

static void reset_aggregates(Aggregates *aggregates) {
    free(aggregates->mu.counts);
    free(aggregates->lambda.counts);
    free(aggregates->total.counts);
    free(aggregates->cycle_nodes.counts);
    memset(aggregates, 0, sizeof(*aggregates));
}

static uint32_t class_lambda(const Checkpoint *checkpoint, unsigned cycle_class) {
    if (!cycle_class || cycle_class > checkpoint->cycle_class_count)
        failf("metadata refers to unknown cycle class %u", cycle_class);
    return checkpoint->cycle_lengths[cycle_class - 1];
}

static unsigned find_or_add_cycle_class(Checkpoint *checkpoint, const char *workdir,
                                        uint32_t lambda) {
    for (unsigned index = 0; index < checkpoint->cycle_class_count; index++)
        if (checkpoint->cycle_lengths[index] == lambda) return index + 1;
    if (checkpoint->cycle_class_count == MAX_CYCLE_CLASSES)
        failf("more than %u distinct cycle lengths; refusing compact metadata", MAX_CYCLE_CLASSES);
    unsigned result = ++checkpoint->cycle_class_count;
    checkpoint->cycle_lengths[result - 1] = lambda;
    /* Persist the meaning of a new class before any metadata entry uses it. */
    checkpoint->checkpoint_sequence++;
    write_checkpoint(workdir, checkpoint);
    fprintf(stderr, "registered cycle_class=%u lambda=%" PRIu32 "\n", result, lambda);
    return result;
}

static uint32_t transition_key(Runner *runner, uint32_t key) {
#ifdef FULL_RUNNER_SYNTHETIC
    uint32_t result;
    if (key == 0) result = 1;
    else if (key == 1) result = 2;
    else if (key == 2) result = 0;
    else if (key < RUNNER_DOMAIN_SIZE / 2) result = key / 2;
    else if (key == RUNNER_DOMAIN_SIZE / 2) result = key + 1;
    else if (key == RUNNER_DOMAIN_SIZE / 2 + 1) result = key - 1;
    else result = RUNNER_DOMAIN_SIZE / 2 + (key - RUNNER_DOMAIN_SIZE / 2) / 2;
#else
    State input = canonical_domain_unrank(key);
    memcpy(runner->cpu->m + RNDX, input.b, 5);
    runner->cpu->m[0x68] = 0;
    State output = advance(runner->cpu);
    uint32_t result;
    if (!canonical_domain_rank(output, &result))
        failf("transition escaped canonical domain from key %" PRIu32, key);
#endif
    runner->transitions_this_process++;
    if (runner->abort_after_transitions
        && runner->transitions_this_process >= runner->abort_after_transitions)
        _exit(99); /* Deliberately bypass cleanup/checkpoint for recovery testing. */
    return result;
}

static void classify_path(Runner *runner, Aggregates *aggregates,
                          Checkpoint *checkpoint, const char *workdir, uint32_t start,
                          uint32_t **path_storage, size_t *path_capacity) {
    size_t path_length = 0;
    uint32_t current = start;
    uint32_t inherited_mu = 0, lambda = 0;
    unsigned cycle_class = 0;
    size_t cycle_start = 0;
    int found_cycle = 0;

    for (;;) {
        uint32_t entry = load_meta(runner, current);
        unsigned entry_class = meta_class(entry);
        uint32_t value = meta_value(entry);
        if (entry_class && entry_class != META_MARKER_CLASS) {
            inherited_mu = value;
            cycle_class = entry_class;
            lambda = class_lambda(checkpoint, cycle_class);
            break;
        }
        if (entry_class == META_MARKER_CLASS) {
            if (!value) failf("zero current-path marker at key %" PRIu32, current);
            cycle_start = value - 1;
            if (cycle_start >= path_length)
                failf("invalid current-path marker at key %" PRIu32, current);
            size_t cycle_size = path_length - cycle_start;
            if (!cycle_size || cycle_size > UINT32_MAX) failf("cycle exceeds uint32");
            lambda = (uint32_t)cycle_size;
            cycle_class = find_or_add_cycle_class(checkpoint, workdir, lambda);
            found_cycle = 1;
            break;
        }
        if (entry) failf("invalid metadata encoding at key %" PRIu32, current);
        if (path_length == *path_capacity) {
            size_t capacity = *path_capacity ? *path_capacity * 2 : 1024;
            uint32_t *replacement = realloc(*path_storage, capacity * sizeof(*replacement));
            if (!replacement) die("realloc path");
            *path_storage = replacement;
            *path_capacity = capacity;
        }
        store_raw_meta(runner, current, pack_marker(path_length));
        (*path_storage)[path_length++] = current;
        current = transition_key(runner, current);
    }

    if (found_cycle) {
        for (size_t index = cycle_start; index < path_length; index++) {
            store_raw_meta(runner, (*path_storage)[index], pack_meta(cycle_class, 0));
            aggregate_classified(aggregates, 0, lambda);
        }
        inherited_mu = 0;
        for (size_t index = cycle_start; index-- > 0;) {
            if (inherited_mu == META_VALUE_MASK)
                failf("mu exceeds guarded 24-bit compact representation");
            inherited_mu++;
            store_raw_meta(runner, (*path_storage)[index], pack_meta(cycle_class, inherited_mu));
            aggregate_classified(aggregates, inherited_mu, lambda);
        }
    } else {
        for (size_t index = path_length; index-- > 0;) {
            if (inherited_mu == META_VALUE_MASK)
                failf("mu exceeds guarded 24-bit compact representation");
            inherited_mu++;
            store_raw_meta(runner, (*path_storage)[index], pack_meta(cycle_class, inherited_mu));
            aggregate_classified(aggregates, inherited_mu, lambda);
        }
    }
}

static int bitmap_test(const uint8_t *bitmap, uint32_t key) {
    return bitmap[key >> 3] & (uint8_t)(1u << (key & 7));
}

static void bitmap_set(uint8_t *bitmap, uint32_t key) {
    bitmap[key >> 3] |= (uint8_t)(1u << (key & 7));
}

static void repair_cycles_after_interruption(Runner *runner, const Checkpoint *checkpoint) {
    size_t bitmap_bytes = ((size_t)RUNNER_DOMAIN_SIZE + 7) / 8;
    uint8_t *processed = calloc(bitmap_bytes, 1);
    if (!processed) die("calloc recovery cycle bitmap");
    uint64_t components = 0, cycle_nodes = 0;
    for (uint32_t key = 0; key < RUNNER_DOMAIN_SIZE; key++) {
        uint32_t entry = load_meta(runner, key);
        unsigned cycle_class = meta_class(entry);
        if (!cycle_class || cycle_class == META_MARKER_CLASS || meta_value(entry)
            || bitmap_test(processed, key)) continue;
        uint32_t lambda = class_lambda(checkpoint, cycle_class);
        uint32_t current = key;
        for (uint32_t step = 0; step < lambda; step++) {
            if (bitmap_test(processed, current) && current != key)
                failf("cycle repair crossed a previously processed cycle at key %" PRIu32, current);
            store_raw_meta(runner, current, pack_meta(cycle_class, 0));
            bitmap_set(processed, current);
            cycle_nodes++;
            current = transition_key(runner, current);
        }
        if (current != key)
            failf("stored cycle does not close after lambda=%" PRIu32 " from key %" PRIu32,
                  lambda, key);
        components++;
    }
    free(processed);
    fprintf(stderr, "cycle_repair components=%" PRIu64 " cycle_nodes=%" PRIu64 "\n",
            components, cycle_nodes);
}

static void recover_and_rebuild(Runner *runner, Aggregates *aggregates,
                                const Checkpoint *checkpoint) {
    reset_aggregates(aggregates);
    repair_cycles_after_interruption(runner, checkpoint);
    uint64_t cleared_markers = 0;
    if (madvise(runner->metadata, runner->metadata_bytes, MADV_SEQUENTIAL))
        die("madvise sequential");
    for (uint32_t key = 0; key < RUNNER_DOMAIN_SIZE; key++) {
        uint32_t entry = load_meta(runner, key);
        unsigned cycle_class = meta_class(entry);
        uint32_t value = meta_value(entry);
        if (!cycle_class) {
            if (entry) failf("invalid zero-class metadata at key %" PRIu32, key);
        } else if (cycle_class == META_MARKER_CLASS) {
            store_raw_meta(runner, key, 0);
            cleared_markers++;
        } else {
            aggregate_classified(aggregates, value, class_lambda(checkpoint, cycle_class));
        }
    }
    if (madvise(runner->metadata, runner->metadata_bytes, MADV_RANDOM))
        die("madvise random");
    fprintf(stderr, "recovery classified=%" PRIu64 " cleared_markers=%" PRIu64 "\n",
            aggregates->classified, cleared_markers);
}

static void write_histogram_csv(const char *workdir, const char *name,
                                const Histogram *histogram) {
    char path[4096], temporary[4096], filename[256], tempname[256];
    snprintf(filename, sizeof(filename), "hist-%s.csv", name);
    snprintf(tempname, sizeof(tempname), "hist-%s.csv.tmp", name);
    path_join(path, sizeof(path), workdir, filename);
    path_join(temporary, sizeof(temporary), workdir, tempname);
    FILE *file = fopen(temporary, "w");
    if (!file) die(temporary);
    fputs("value,count\n", file);
    if (histogram->counts) {
        for (uint32_t value = 0; value <= histogram->maximum; value++)
            if (histogram->counts[value])
                fprintf(file, "%" PRIu32 ",%" PRIu64 "\n", value, histogram->counts[value]);
    }
    if (fflush(file) || fsync(fileno(file)) || fclose(file)) die("write histogram");
    if (rename(temporary, path)) die("rename histogram");
}

static void write_cycle_csv(const char *workdir, const Histogram *cycle_nodes) {
    char path[4096], temporary[4096];
    path_join(path, sizeof(path), workdir, "cycle-components.csv");
    path_join(temporary, sizeof(temporary), workdir, "cycle-components.csv.tmp");
    FILE *file = fopen(temporary, "w");
    if (!file) die(temporary);
    fputs("lambda,cycle_nodes,component_count\n", file);
    if (cycle_nodes->counts) {
        for (uint32_t lambda = 1; lambda <= cycle_nodes->maximum; lambda++) {
            uint64_t nodes = cycle_nodes->counts[lambda];
            if (!nodes) continue;
            if (nodes % lambda)
                failf("cycle-node count is not divisible by lambda=%" PRIu32, lambda);
            fprintf(file, "%" PRIu32 ",%" PRIu64 ",%" PRIu64 "\n",
                    lambda, nodes, nodes / lambda);
        }
    }
    if (fflush(file) || fsync(fileno(file)) || fclose(file)) die("write cycle inventory");
    if (rename(temporary, path)) die("rename cycle inventory");
}

static void write_summary(const char *workdir, const Checkpoint *checkpoint,
                          const Aggregates *aggregates, double elapsed,
                          uint64_t transitions_this_process) {
    char path[4096], temporary[4096];
    path_join(path, sizeof(path), workdir, "summary.json");
    path_join(temporary, sizeof(temporary), workdir, "summary.json.tmp");
    FILE *file = fopen(temporary, "w");
    if (!file) die(temporary);
    fprintf(file,
        "{\n"
        "  \"schema\": \"%s\",\n"
        "  \"domainSize\": %" PRIu32 ",\n"
        "  \"metadataBytes\": %zu,\n"
        "  \"metadataLayout\": \"8-bit cycle-length class plus 24-bit mu\",\n"
        "  \"nextScan\": %" PRIu64 ",\n"
        "  \"classifiedStates\": %" PRIu64 ",\n"
        "  \"logicalTransitions\": %" PRIu64 ",\n"
        "  \"transitionsThisProcess\": %" PRIu64 ",\n"
        "  \"checkpointSequence\": %" PRIu64 ",\n"
        "  \"cycleLengthClasses\": %" PRIu32 ",\n"
        "  \"complete\": %s,\n"
        "  \"maxMu\": %" PRIu32 ",\n"
        "  \"maxLambda\": %" PRIu32 ",\n"
        "  \"maxTotal\": %" PRIu32 ",\n"
        "  \"elapsedSecondsThisProcess\": %.6f\n"
        "}\n",
        SCHEMA_NAME, RUNNER_DOMAIN_SIZE, (size_t)RUNNER_DOMAIN_SIZE * sizeof(uint32_t),
        checkpoint->next_scan, aggregates->classified, aggregates->classified,
        transitions_this_process, checkpoint->checkpoint_sequence,
        checkpoint->cycle_class_count, checkpoint->complete ? "true" : "false",
        aggregates->mu.maximum, aggregates->lambda.maximum,
        aggregates->total.maximum, elapsed);
    if (fflush(file) || fsync(fileno(file)) || fclose(file)) die("write summary");
    if (rename(temporary, path)) die("rename summary");
}

static void persist_all(Runner *runner, Checkpoint *checkpoint, const char *workdir,
                        const Aggregates *aggregates, double elapsed) {
    if (histogram_sum(&aggregates->mu) != aggregates->classified
        || histogram_sum(&aggregates->lambda) != aggregates->classified
        || histogram_sum(&aggregates->total) != aggregates->classified)
        failf("histogram totals do not equal classified state count");
    if (msync(runner->metadata, runner->metadata_bytes, MS_SYNC)) die("msync metadata");
    write_histogram_csv(workdir, "mu", &aggregates->mu);
    write_histogram_csv(workdir, "lambda", &aggregates->lambda);
    write_histogram_csv(workdir, "total", &aggregates->total);
    write_cycle_csv(workdir, &aggregates->cycle_nodes);
    checkpoint->classified_states = aggregates->classified;
    checkpoint->checkpoint_sequence++;
    write_summary(workdir, checkpoint, aggregates, elapsed, runner->transitions_this_process);
    write_checkpoint(workdir, checkpoint);
}

static uint64_t parse_u64(const char *text, const char *name) {
    char *end = NULL;
    errno = 0;
    uint64_t value = strtoull(text, &end, 0);
    if (errno || !end || *end) failf("invalid %s: %s", name, text);
    return value;
}

static Options parse_options(int argc, char **argv) {
    if (argc < 5) {
        fprintf(stderr,
            "usage: %s BASIC-ROM KERNAL-ROM WORKDIR (--create|--resume) [options]\n"
            "options: --sparse --checkpoint-every=N --stop-after-scans=N "
            "--abort-after-transitions=N\n", argv[0]);
        exit(2);
    }
    Options options = {
        .basic_path = argv[1], .kernal_path = argv[2], .workdir = argv[3],
        .checkpoint_every = UINT64_C(100000000),
    };
    if (!strcmp(argv[4], "--create")) options.create = 1;
    else if (!strcmp(argv[4], "--resume")) options.create = 0;
    else failf("fourth argument must be --create or --resume");
    for (int index = 5; index < argc; index++) {
        if (!strcmp(argv[index], "--sparse")) options.sparse = 1;
        else if (!strncmp(argv[index], "--checkpoint-every=", 19))
            options.checkpoint_every = parse_u64(argv[index] + 19, "checkpoint interval");
        else if (!strncmp(argv[index], "--stop-after-scans=", 19))
            options.stop_after_scans = parse_u64(argv[index] + 19, "stop scan count");
        else if (!strncmp(argv[index], "--abort-after-transitions=", 26))
            options.abort_after_transitions = parse_u64(argv[index] + 26, "abort transition count");
        else failf("unknown option: %s", argv[index]);
    }
    if (!options.checkpoint_every) failf("checkpoint interval must be nonzero");
    return options;
}

static Runner open_runner(const Options *options, Checkpoint *checkpoint) {
    Runner runner = {0};
    runner.metadata_fd = -1;
    runner.metadata_bytes = (size_t)RUNNER_DOMAIN_SIZE * sizeof(uint32_t);
    runner.abort_after_transitions = options->abort_after_transitions;
    char metadata_path[4096];
    path_join(metadata_path, sizeof(metadata_path), options->workdir, "metadata.bin");

    if (options->create) {
        if (mkdir(options->workdir, 0755)) die(options->workdir);
        runner.metadata_fd = open(metadata_path, O_RDWR | O_CREAT | O_EXCL, 0644);
        if (runner.metadata_fd < 0) die(metadata_path);
        if (ftruncate(runner.metadata_fd, (off_t)runner.metadata_bytes)) die("ftruncate metadata");
        if (!options->sparse) {
            int error = posix_fallocate(runner.metadata_fd, 0, (off_t)runner.metadata_bytes);
            if (error) {
                errno = error;
                die("posix_fallocate metadata");
            }
        }
        *checkpoint = (Checkpoint){
            .magic = CHECKPOINT_MAGIC,
            .version = CHECKPOINT_VERSION,
            .domain_size = RUNNER_DOMAIN_SIZE,
        };
    } else {
        *checkpoint = read_checkpoint(options->workdir);
        runner.metadata_fd = open(metadata_path, O_RDWR);
        if (runner.metadata_fd < 0) die(metadata_path);
        struct stat status;
        if (fstat(runner.metadata_fd, &status)) die("fstat metadata");
        if ((uint64_t)status.st_size != runner.metadata_bytes)
            failf("metadata size mismatch: expected %zu, got %" PRIu64,
                  runner.metadata_bytes, (uint64_t)status.st_size);
    }
    if (flock(runner.metadata_fd, LOCK_EX | LOCK_NB)) die("lock metadata");
    runner.metadata = mmap(NULL, runner.metadata_bytes, PROT_READ | PROT_WRITE,
                           MAP_SHARED, runner.metadata_fd, 0);
    if (runner.metadata == MAP_FAILED) die("mmap metadata");
#ifndef FULL_RUNNER_SYNTHETIC
    runner.cpu = new_cpu(options->basic_path, options->kernal_path);
#else
    (void)options->basic_path;
    (void)options->kernal_path;
#endif
    return runner;
}

int main(int argc, char **argv) {
    (void)state;
    (void)equal;
    (void)hash;
#ifdef FULL_RUNNER_SYNTHETIC
    (void)new_cpu;
    (void)advance;
#endif
    Options options = parse_options(argc, argv);
    signal(SIGINT, handle_stop);
    signal(SIGTERM, handle_stop);

    Checkpoint checkpoint;
    Runner runner = open_runner(&options, &checkpoint);
    Aggregates aggregates = {0};
    if (options.create) {
        write_checkpoint(options.workdir, &checkpoint);
        if (madvise(runner.metadata, runner.metadata_bytes, MADV_RANDOM)) die("madvise random");
    } else {
        recover_and_rebuild(&runner, &aggregates, &checkpoint);
        checkpoint.classified_states = aggregates.classified;
        if (checkpoint.complete && aggregates.classified != RUNNER_DOMAIN_SIZE)
            failf("complete checkpoint has only %" PRIu64 " classified states", aggregates.classified);
    }

    uint32_t *path = NULL;
    size_t path_capacity = 0;
    uint64_t scan = checkpoint.next_scan;
    uint64_t scans_this_process = 0;
    uint64_t next_checkpoint = scan + options.checkpoint_every;
    double started = seconds_now();

    while (scan < RUNNER_DOMAIN_SIZE) {
        uint32_t entry = load_meta(&runner, (uint32_t)scan);
        unsigned entry_class = meta_class(entry);
        if (!entry_class)
            classify_path(&runner, &aggregates, &checkpoint, options.workdir,
                          (uint32_t)scan, &path, &path_capacity);
        else if (entry_class == META_MARKER_CLASS)
            failf("unrecovered current-path marker at scan key %" PRIu64, scan);
        scan++;
        scans_this_process++;
        checkpoint.next_scan = scan;
        if (!(scan % UINT64_C(10000000))) {
            fprintf(stderr,
                "scan=%" PRIu64 "/%" PRIu32 " classified=%" PRIu64
                " transitions=%" PRIu64 " elapsed=%.1f\n",
                scan, RUNNER_DOMAIN_SIZE, aggregates.classified,
                runner.transitions_this_process, seconds_now() - started);
        }
        if (scan >= next_checkpoint || stop_requested
            || (options.stop_after_scans && scans_this_process >= options.stop_after_scans)) {
            checkpoint.complete = scan == RUNNER_DOMAIN_SIZE;
            persist_all(&runner, &checkpoint, options.workdir, &aggregates,
                        seconds_now() - started);
            fprintf(stderr, "checkpoint sequence=%" PRIu64 " next_scan=%" PRIu64
                    " classified=%" PRIu64 "\n", checkpoint.checkpoint_sequence,
                    checkpoint.next_scan, aggregates.classified);
            if (stop_requested
                || (options.stop_after_scans && scans_this_process >= options.stop_after_scans))
                break;
            next_checkpoint = scan + options.checkpoint_every;
        }
    }

    if (scan == RUNNER_DOMAIN_SIZE && !checkpoint.complete) {
        checkpoint.complete = 1;
        persist_all(&runner, &checkpoint, options.workdir, &aggregates,
                    seconds_now() - started);
    }
    fprintf(stderr,
        "finished complete=%" PRIu64 " next_scan=%" PRIu64 " classified=%" PRIu64
        " transitions_this_process=%" PRIu64 " elapsed=%.3f\n",
        checkpoint.complete, checkpoint.next_scan, aggregates.classified,
        runner.transitions_this_process, seconds_now() - started);

    free(path);
    reset_aggregates(&aggregates);
    free(runner.cpu);
    if (munmap(runner.metadata, runner.metadata_bytes)) die("munmap metadata");
    close(runner.metadata_fd);
    return checkpoint.complete ? 0 : 3;
}
