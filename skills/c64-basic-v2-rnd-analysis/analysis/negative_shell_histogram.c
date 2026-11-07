/* Parallel restartable aggregation of the distinct all-valid-negative-FAC seed
 * image outside the retained canonical C64 BASIC V2 RND graph.
 *
 * This includes generated_rnd_cycle.c, a private mechanically ROM-derived
 * artifact. Do not publish that generated file or this compiled executable by
 * default. The hand-written source itself contains no ROM bytes.
 */
#define _GNU_SOURCE
#define _POSIX_C_SOURCE 200809L
#define GENERATED_RND_NO_MAIN
#include "generated_rnd_cycle.c"
#include "canonical_seed_domain.h"
#include "negative_seed_image_domain.h"

#include <errno.h>
#include <fcntl.h>
#include <pthread.h>
#include <signal.h>
#include <stdatomic.h>
#include <stdarg.h>
#include <stdbool.h>
#include <sys/file.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>

#if __BYTE_ORDER__ != __ORDER_LITTLE_ENDIAN__
#error "metadata and checkpoint formats require a little-endian host"
#endif

#define GRAPH_MAGIC UINT64_C(0x324b4348444e5252)
#define GRAPH_VERSION 2u
#define MAX_CLASSES 254u
#define META_VALUE_MASK UINT32_C(0x00ffffff)
#define SHELL_MAGIC UINT64_C(0x314c4c454853444e) /* NDSHELL1 */
#define SHELL_VERSION 1u
#define HIST_LIMIT 65536u

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
} GraphCheckpoint;

typedef struct {
    uint64_t magic;
    uint32_t version;
    uint32_t class_count;
    uint64_t image_size;
    uint64_t chunk_size;
    uint64_t chunk_count;
    uint64_t completed_chunks;
    uint64_t canonical_states;
    uint64_t outer_states;
    uint64_t transitions;
    uint64_t sequence;
    uint64_t complete;
    uint32_t hist_limit;
    uint32_t reserved;
    uint32_t cycle_lengths[MAX_CLASSES];
    uint64_t checksum;
} ShellCheckpoint;

typedef struct Runner Runner;
typedef struct {
    Runner *runner;
    unsigned worker_index;
} Worker;

struct Runner {
    const char *basic_path;
    const char *kernal_path;
    const char *output_dir;
    const uint32_t *metadata;
    size_t metadata_bytes;
    int metadata_fd;
    GraphCheckpoint graph;
    ShellCheckpoint checkpoint;
    uint8_t *completed;
    size_t completed_bytes;
    uint64_t *histogram;
    size_t histogram_cells;
    atomic_uint_fast64_t next_chunk;
    uint64_t schedule_count;
    unsigned schedule_bits;
    pthread_mutex_t merge_mutex;
    uint64_t checkpoint_every;
    uint64_t stop_after_new_chunks;
    uint64_t initial_completed_chunks;
};

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

static uint64_t graph_checksum(const GraphCheckpoint *value) {
    uint64_t result = value->magic ^ value->version ^ value->domain_size
                    ^ value->next_scan ^ value->classified_states
                    ^ value->checkpoint_sequence ^ value->complete
                    ^ value->cycle_class_count ^ UINT64_C(0xc64b451c6502f00d);
    for (unsigned index = 0; index < MAX_CLASSES; index++)
        result = (result << 7 | result >> 57) ^ value->cycle_lengths[index];
    return result;
}

static uint64_t hash_bytes(uint64_t hash_value, const void *data, size_t size) {
    const uint8_t *bytes = data;
    for (size_t index = 0; index < size; index++) {
        hash_value ^= bytes[index];
        hash_value *= UINT64_C(1099511628211);
    }
    return hash_value;
}

static uint64_t shell_checksum(const ShellCheckpoint *checkpoint,
                               const uint8_t *completed, size_t completed_bytes,
                               const uint64_t *histogram, size_t histogram_cells) {
    ShellCheckpoint copy = *checkpoint;
    copy.checksum = 0;
    uint64_t result = UINT64_C(1469598103934665603);
    result = hash_bytes(result, &copy, sizeof(copy));
    result = hash_bytes(result, completed, completed_bytes);
    return hash_bytes(result, histogram, histogram_cells * sizeof(*histogram));
}

static void join_path(char *destination, size_t size, const char *directory,
                      const char *name) {
    int amount = snprintf(destination, size, "%s/%s", directory, name);
    if (amount < 0 || (size_t)amount >= size) failf("path too long");
}

static void write_all(int fd, const void *data, size_t size) {
    const uint8_t *cursor = data;
    while (size) {
        ssize_t amount = write(fd, cursor, size);
        if (amount < 0) {
            if (errno == EINTR) continue;
            die("write");
        }
        cursor += amount;
        size -= (size_t)amount;
    }
}

static int chunk_done(const Runner *runner, uint64_t chunk) {
    return runner->completed[chunk >> 3] & (uint8_t)(1u << (chunk & 7));
}

static void mark_chunk_done(Runner *runner, uint64_t chunk) {
    runner->completed[chunk >> 3] |= (uint8_t)(1u << (chunk & 7));
}

static void write_checkpoint_locked(Runner *runner) {
    char final_path[4096], temporary_path[4096];
    join_path(final_path, sizeof(final_path), runner->output_dir, "checkpoint.bin");
    join_path(temporary_path, sizeof(temporary_path), runner->output_dir,
              "checkpoint.bin.tmp");
    runner->checkpoint.sequence++;
    runner->checkpoint.checksum = shell_checksum(
        &runner->checkpoint, runner->completed, runner->completed_bytes,
        runner->histogram, runner->histogram_cells);
    int fd = open(temporary_path, O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (fd < 0) die(temporary_path);
    write_all(fd, &runner->checkpoint, sizeof(runner->checkpoint));
    write_all(fd, runner->completed, runner->completed_bytes);
    write_all(fd, runner->histogram,
              runner->histogram_cells * sizeof(*runner->histogram));
    if (fsync(fd)) die("fsync shell checkpoint");
    if (close(fd)) die("close shell checkpoint");
    if (rename(temporary_path, final_path)) die("rename shell checkpoint");
    int directory_fd = open(runner->output_dir, O_RDONLY | O_DIRECTORY);
    if (directory_fd < 0) die(runner->output_dir);
    if (fsync(directory_fd)) die("fsync shell directory");
    if (close(directory_fd)) die("close shell directory");
}

static GraphCheckpoint read_graph_checkpoint(const char *run_directory) {
    char path[4096];
    join_path(path, sizeof(path), run_directory, "checkpoint.bin");
    FILE *input = fopen(path, "rb");
    if (!input) die(path);
    GraphCheckpoint value;
    if (fread(&value, sizeof(value), 1, input) != 1
        || fgetc(input) != EOF || fclose(input)) failf("invalid graph checkpoint");
    if (value.magic != GRAPH_MAGIC || value.version != GRAPH_VERSION
        || value.domain_size != CANONICAL_DOMAIN_SIZE
        || value.next_scan != CANONICAL_DOMAIN_SIZE
        || value.classified_states != CANONICAL_DOMAIN_SIZE || !value.complete
        || !value.cycle_class_count || value.cycle_class_count > MAX_CLASSES
        || value.checksum != graph_checksum(&value))
        failf("refusing incomplete, corrupt, or incompatible graph checkpoint");
    return value;
}

static void map_metadata(Runner *runner, const char *run_directory) {
    char path[4096];
    join_path(path, sizeof(path), run_directory, "metadata.bin");
    runner->metadata_fd = open(path, O_RDONLY);
    if (runner->metadata_fd < 0) die(path);
    if (flock(runner->metadata_fd, LOCK_SH | LOCK_NB)) die("lock metadata");
    struct stat status;
    if (fstat(runner->metadata_fd, &status)) die("fstat metadata");
    runner->metadata_bytes = (size_t)CANONICAL_DOMAIN_SIZE * sizeof(uint32_t);
    if ((uint64_t)status.st_size != runner->metadata_bytes)
        failf("metadata size mismatch");
    runner->metadata = mmap(NULL, runner->metadata_bytes, PROT_READ, MAP_SHARED,
                            runner->metadata_fd, 0);
    if (runner->metadata == MAP_FAILED) die("mmap metadata");
#ifdef MADV_RANDOM
    (void)madvise((void *)runner->metadata, runner->metadata_bytes, MADV_RANDOM);
#endif
}

static void initialize_new_checkpoint(Runner *runner, uint64_t chunk_size) {
    memset(&runner->checkpoint, 0, sizeof(runner->checkpoint));
    runner->checkpoint.magic = SHELL_MAGIC;
    runner->checkpoint.version = SHELL_VERSION;
    runner->checkpoint.class_count = runner->graph.cycle_class_count;
    runner->checkpoint.image_size = NEGATIVE_SEED_IMAGE_SIZE;
    runner->checkpoint.chunk_size = chunk_size;
    runner->checkpoint.chunk_count =
        (NEGATIVE_SEED_IMAGE_SIZE + chunk_size - 1) / chunk_size;
    runner->checkpoint.hist_limit = HIST_LIMIT;
    memcpy(runner->checkpoint.cycle_lengths, runner->graph.cycle_lengths,
           sizeof(runner->checkpoint.cycle_lengths));
    runner->completed_bytes = (size_t)((runner->checkpoint.chunk_count + 7) / 8);
    runner->histogram_cells = (size_t)runner->checkpoint.class_count * HIST_LIMIT;
    runner->completed = calloc(runner->completed_bytes, 1);
    runner->histogram = calloc(runner->histogram_cells, sizeof(*runner->histogram));
    if (!runner->completed || !runner->histogram) die("calloc shell checkpoint");
}

static void load_checkpoint(Runner *runner, uint64_t requested_chunk_size) {
    char path[4096];
    join_path(path, sizeof(path), runner->output_dir, "checkpoint.bin");
    FILE *input = fopen(path, "rb");
    if (!input) die(path);
    if (fread(&runner->checkpoint, sizeof(runner->checkpoint), 1, input) != 1)
        failf("short shell checkpoint header");
    ShellCheckpoint *value = &runner->checkpoint;
    if (value->magic != SHELL_MAGIC || value->version != SHELL_VERSION
        || value->class_count != runner->graph.cycle_class_count
        || value->image_size != NEGATIVE_SEED_IMAGE_SIZE
        || value->chunk_size != requested_chunk_size || !value->chunk_count
        || value->hist_limit != HIST_LIMIT
        || memcmp(value->cycle_lengths, runner->graph.cycle_lengths,
                  sizeof(value->cycle_lengths)))
        failf("incompatible shell checkpoint");
    runner->completed_bytes = (size_t)((value->chunk_count + 7) / 8);
    runner->histogram_cells = (size_t)value->class_count * HIST_LIMIT;
    runner->completed = malloc(runner->completed_bytes);
    runner->histogram = malloc(runner->histogram_cells * sizeof(*runner->histogram));
    if (!runner->completed || !runner->histogram) die("malloc shell checkpoint");
    if (fread(runner->completed, 1, runner->completed_bytes, input)
            != runner->completed_bytes
        || fread(runner->histogram, sizeof(*runner->histogram),
                 runner->histogram_cells, input) != runner->histogram_cells
        || fgetc(input) != EOF || fclose(input))
        failf("short or trailing shell checkpoint data");
    if (value->checksum != shell_checksum(value, runner->completed,
                                           runner->completed_bytes,
                                           runner->histogram,
                                           runner->histogram_cells))
        failf("shell checkpoint checksum mismatch");
}

static uint64_t reverse_low_bits(uint64_t value, unsigned bits) {
    uint64_t result = 0;
    for (unsigned index = 0; index < bits; index++) {
        result = (result << 1) | (value & 1u);
        value >>= 1;
    }
    return result;
}

static void *worker_main(void *argument) {
    Worker *worker = argument;
    Runner *runner = worker->runner;
    Cpu *cpu = new_cpu(runner->basic_path, runner->kernal_path);
    State cpu_probe = state(cpu);
    if (!equal(cpu_probe, cpu_probe) || hash(cpu_probe) == UINT64_MAX)
        failf("generated transition support self-check failed");
    uint64_t *counts = calloc(runner->histogram_cells, sizeof(*counts));
    uint32_t *touched = malloc((size_t)runner->checkpoint.chunk_size * sizeof(*touched));
    if (!counts || !touched) die("allocate worker histogram");

    for (;;) {
        if (stop_requested) break;
        uint64_t ticket = atomic_fetch_add(&runner->next_chunk, 1);
        if (ticket >= runner->schedule_count) break;
        uint64_t chunk = reverse_low_bits(ticket, runner->schedule_bits);
        if (chunk >= runner->checkpoint.chunk_count) continue;
        pthread_mutex_lock(&runner->merge_mutex);
        int done = chunk_done(runner, chunk);
        uint64_t new_completed = runner->checkpoint.completed_chunks
                               - runner->initial_completed_chunks;
        int limit_reached = runner->stop_after_new_chunks
                         && new_completed >= runner->stop_after_new_chunks;
        pthread_mutex_unlock(&runner->merge_mutex);
        if (done) continue;
        if (limit_reached) break;

        uint64_t begin = chunk * runner->checkpoint.chunk_size;
        uint64_t end = begin + runner->checkpoint.chunk_size;
        if (end > NEGATIVE_SEED_IMAGE_SIZE) end = NEGATIVE_SEED_IMAGE_SIZE;
        uint64_t canonical = 0, outer = 0;
        size_t touched_count = 0;
        for (uint64_t index = begin; index < end; index++) {
            State seed = negative_seed_image_unrank(index);
            uint32_t canonical_rank;
            if (canonical_domain_rank(seed, &canonical_rank)) {
                canonical++;
                continue;
            }
            memcpy(cpu->m + RNDX, seed.b, sizeof(seed.b));
            State successor = advance(cpu);
            if (!canonical_domain_rank(successor, &canonical_rank))
                failf("worker %u produced noncanonical successor at image index %" PRIu64,
                      worker->worker_index, index);
            uint32_t entry = runner->metadata[canonical_rank];
            unsigned cycle_class = entry >> 24;
            uint32_t mu = entry & META_VALUE_MASK;
            if (!cycle_class || cycle_class > runner->checkpoint.class_count
                || mu + 1 >= HIST_LIMIT)
                failf("invalid successor metadata at canonical rank %" PRIu32,
                      canonical_rank);
            size_t cell = (size_t)(cycle_class - 1) * HIST_LIMIT + mu + 1;
            if (!counts[cell]) touched[touched_count++] = (uint32_t)cell;
            counts[cell]++;
            outer++;
        }

        pthread_mutex_lock(&runner->merge_mutex);
        if (chunk_done(runner, chunk)) failf("duplicate completed chunk %" PRIu64, chunk);
        for (size_t index = 0; index < touched_count; index++) {
            uint32_t cell = touched[index];
            runner->histogram[cell] += counts[cell];
            counts[cell] = 0;
        }
        mark_chunk_done(runner, chunk);
        runner->checkpoint.completed_chunks++;
        runner->checkpoint.canonical_states += canonical;
        runner->checkpoint.outer_states += outer;
        runner->checkpoint.transitions += outer;
        uint64_t completed = runner->checkpoint.completed_chunks;
        if (runner->checkpoint_every && completed % runner->checkpoint_every == 0) {
            write_checkpoint_locked(runner);
            fprintf(stderr,
                    "checkpoint chunks=%" PRIu64 "/%" PRIu64
                    " image=%" PRIu64 " outer=%" PRIu64 "\n",
                    completed, runner->checkpoint.chunk_count,
                    runner->checkpoint.canonical_states + runner->checkpoint.outer_states,
                    runner->checkpoint.outer_states);
        }
        pthread_mutex_unlock(&runner->merge_mutex);
    }
    free(counts);
    free(touched);
    free(cpu);
    return NULL;
}

static uint64_t histogram_sum(const Runner *runner) {
    uint64_t total = 0;
    for (size_t index = 0; index < runner->histogram_cells; index++)
        total += runner->histogram[index];
    return total;
}

static void write_outputs(const Runner *runner, double elapsed) {
    char csv_path[4096], json_path[4096];
    join_path(csv_path, sizeof(csv_path), runner->output_dir, "shell-depth.csv");
    join_path(json_path, sizeof(json_path), runner->output_dir, "summary.json");
    FILE *csv = fopen(csv_path, "w");
    if (!csv) die(csv_path);
    fputs("lambda,mu,count\n", csv);
    uint32_t max_mu = 0;
    for (unsigned code = 0; code < runner->checkpoint.class_count; code++) {
        for (uint32_t mu = 1; mu < HIST_LIMIT; mu++) {
            uint64_t count = runner->histogram[(size_t)code * HIST_LIMIT + mu];
            if (count) {
                fprintf(csv, "%" PRIu32 ",%" PRIu32 ",%" PRIu64 "\n",
                        runner->checkpoint.cycle_lengths[code], mu, count);
                if (mu > max_mu) max_mu = mu;
            }
        }
    }
    if (fclose(csv)) die("close shell-depth.csv");
    FILE *json = fopen(json_path, "w");
    if (!json) die(json_path);
    fprintf(json,
            "{\n"
            "  \"schema\": \"c64-basic-rnd-negative-shell-histogram-v1\",\n"
            "  \"imageStates\": %" PRIu64 ",\n"
            "  \"canonicalImageStates\": %" PRIu64 ",\n"
            "  \"outerStates\": %" PRIu64 ",\n"
            "  \"transitions\": %" PRIu64 ",\n"
            "  \"maxShellMu\": %" PRIu32 ",\n"
            "  \"threadsIndependent\": true,\n"
            "  \"elapsedSecondsThisProcess\": %.6f,\n"
            "  \"complete\": %s\n"
            "}\n",
            runner->checkpoint.canonical_states + runner->checkpoint.outer_states,
            runner->checkpoint.canonical_states, runner->checkpoint.outer_states,
            runner->checkpoint.transitions, max_mu, elapsed,
            runner->checkpoint.complete ? "true" : "false");
    if (fclose(json)) die("close shell summary");
}

int main(int argc, char **argv) {
    if (argc < 6 || argc > 9) {
        fprintf(stderr,
                "usage: %s BASIC-ROM KERNAL-ROM GRAPH-RUN OUTPUT-DIR THREADS"
                " [CHUNK-SIZE] [CHECKPOINT-EVERY] [STOP-AFTER-NEW-CHUNKS]\n",
                argv[0]);
        return 2;
    }
    if (getenv("RND_START")) failf("refusing inherited RND_START environment variable");
    char *end = NULL;
    unsigned threads = (unsigned)strtoul(argv[5], &end, 0);
    if (!end || *end || !threads || threads > 64) failf("invalid thread count");
    uint64_t chunk_size = argc >= 7 ? strtoull(argv[6], &end, 0) : UINT64_C(1000000);
    if (!end || *end || !chunk_size || chunk_size > UINT32_MAX) failf("invalid chunk size");
    uint64_t checkpoint_every = argc >= 8 ? strtoull(argv[7], &end, 0) : 100u;
    if (!end || *end) failf("invalid checkpoint interval");
    uint64_t stop_after = argc >= 9 ? strtoull(argv[8], &end, 0) : 0;
    if (!end || *end) failf("invalid stop-after count");

    Runner runner = {0};
    runner.basic_path = argv[1];
    runner.kernal_path = argv[2];
    runner.output_dir = argv[4];
    runner.metadata_fd = -1;
    runner.checkpoint_every = checkpoint_every;
    runner.stop_after_new_chunks = stop_after;
    runner.graph = read_graph_checkpoint(argv[3]);
    State domain_probe = canonical_domain_unrank(0);
    uint32_t domain_probe_rank;
    if (!canonical_domain_rank(domain_probe, &domain_probe_rank) || domain_probe_rank)
        failf("canonical domain support self-check failed");
    map_metadata(&runner, argv[3]);
    if (mkdir(runner.output_dir, 0755) && errno != EEXIST) die(runner.output_dir);
    char checkpoint_path[4096];
    join_path(checkpoint_path, sizeof(checkpoint_path), runner.output_dir, "checkpoint.bin");
    if (access(checkpoint_path, F_OK) == 0) load_checkpoint(&runner, chunk_size);
    else initialize_new_checkpoint(&runner, chunk_size);
    runner.initial_completed_chunks = runner.checkpoint.completed_chunks;
    runner.schedule_count = 1;
    runner.schedule_bits = 0;
    while (runner.schedule_count < runner.checkpoint.chunk_count) {
        runner.schedule_count <<= 1;
        runner.schedule_bits++;
    }
    atomic_init(&runner.next_chunk, 0);
    if (pthread_mutex_init(&runner.merge_mutex, NULL)) die("pthread_mutex_init");

    signal(SIGINT, handle_stop);
    signal(SIGTERM, handle_stop);
    fprintf(stderr,
            "shell run: threads=%u chunks=%" PRIu64 " chunk_size=%" PRIu64
            " resumed=%" PRIu64 "\n",
            threads, runner.checkpoint.chunk_count, runner.checkpoint.chunk_size,
            runner.checkpoint.completed_chunks);
    double started = seconds_now();
    pthread_t *thread_ids = calloc(threads, sizeof(*thread_ids));
    Worker *workers = calloc(threads, sizeof(*workers));
    if (!thread_ids || !workers) die("calloc threads");
    for (unsigned index = 0; index < threads; index++) {
        workers[index] = (Worker){.runner = &runner, .worker_index = index};
        int error = pthread_create(&thread_ids[index], NULL, worker_main, &workers[index]);
        if (error) failf("pthread_create: %s", strerror(error));
    }
    for (unsigned index = 0; index < threads; index++) {
        int error = pthread_join(thread_ids[index], NULL);
        if (error) failf("pthread_join: %s", strerror(error));
    }
    double elapsed = seconds_now() - started;

    if (runner.checkpoint.completed_chunks == runner.checkpoint.chunk_count) {
        uint64_t image = runner.checkpoint.canonical_states + runner.checkpoint.outer_states;
        uint64_t expected_outer = NEGATIVE_SEED_IMAGE_SIZE - CANONICAL_DOMAIN_SIZE;
        if (image != NEGATIVE_SEED_IMAGE_SIZE
            || runner.checkpoint.canonical_states != CANONICAL_DOMAIN_SIZE
            || runner.checkpoint.outer_states != expected_outer
            || runner.checkpoint.transitions != expected_outer
            || histogram_sum(&runner) != expected_outer)
            failf("completed shell totals failed exact invariants");
        runner.checkpoint.complete = 1;
    }
    write_checkpoint_locked(&runner);
    write_outputs(&runner, elapsed);
    double rate = elapsed ? (runner.checkpoint.transitions
                 - (runner.checkpoint.outer_states - (runner.checkpoint.transitions))) / elapsed : 0;
    (void)rate;
    fprintf(stderr,
            "stopped: new_chunks=%" PRIu64 " elapsed=%.3f complete=%" PRIu64
            " image_total=%" PRIu64 " outer_total=%" PRIu64 "\n",
            runner.checkpoint.completed_chunks - runner.initial_completed_chunks,
            elapsed, runner.checkpoint.complete,
            runner.checkpoint.canonical_states + runner.checkpoint.outer_states,
            runner.checkpoint.outer_states);

    free(thread_ids);
    free(workers);
    free(runner.completed);
    free(runner.histogram);
    pthread_mutex_destroy(&runner.merge_mutex);
    munmap((void *)runner.metadata, runner.metadata_bytes);
    close(runner.metadata_fd);
    return 0;
}
