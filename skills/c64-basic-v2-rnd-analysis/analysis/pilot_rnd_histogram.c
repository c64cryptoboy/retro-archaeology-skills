/* Exact histogram pilot over deterministic canonical-domain starting states. */
#define GENERATED_RND_NO_MAIN
#include "generated_rnd_cycle.c"
#include "canonical_seed_domain.h"

#include <errno.h>

#define EMPTY_KEY UINT32_MAX

typedef struct {
    uint32_t key;
    uint32_t value;  /* current path index while lambda=0; classified distance otherwise */
    uint32_t lambda; /* zero only while the node is on the current path */
} CompactNode;

typedef struct {
    CompactNode *nodes;
    size_t capacity;
    size_t count;
} CompactGraph;

typedef struct {
    uint64_t *counts;
    size_t capacity;
    uint32_t maximum;
} Histogram;

static uint32_t permute32(uint32_t value) {
    value ^= value >> 16;
    value *= UINT32_C(0x7feb352d);
    value ^= value >> 15;
    value *= UINT32_C(0x846ca68b);
    value ^= value >> 16;
    return value;
}

static size_t find_node(CompactGraph *graph, uint32_t key, int create, int *created) {
    size_t index = ((uint64_t)key * UINT64_C(0x9e3779b97f4a7c15))
                 & (graph->capacity - 1);
    while (graph->nodes[index].key != EMPTY_KEY && graph->nodes[index].key != key)
        index = (index + 1) & (graph->capacity - 1);
    if (created) *created = 0;
    if (graph->nodes[index].key == EMPTY_KEY && create) {
        if ((graph->count + 1) * 10 >= graph->capacity * 7) {
            fputs("graph table reached 70% load; choose a larger capacity power\n", stderr);
            exit(2);
        }
        graph->nodes[index].key = key;
        graph->nodes[index].value = 0;
        graph->nodes[index].lambda = 0;
        graph->count++;
        if (created) *created = 1;
    }
    return index;
}

static uint32_t next_key(CompactGraph *graph, Cpu *cpu, uint32_t key,
                         uint64_t *transition_count) {
    (void)graph;
    State input = canonical_domain_unrank(key);
    memcpy(cpu->m + RNDX, input.b, 5);
    cpu->m[0x68] = 0;
    State output = advance(cpu);
    uint32_t result;
    if (!canonical_domain_rank(output, &result)) {
        fprintf(stderr, "transition escaped canonical domain from key %" PRIu32 "\n", key);
        exit(1);
    }
    (*transition_count)++;
    return result;
}

static size_t classify(CompactGraph *graph, Cpu *cpu, uint32_t start,
                       uint32_t **path_storage, size_t *path_capacity,
                       uint64_t *transition_count) {
    size_t path_length = 0;
    uint32_t current = start;
    uint32_t inherited_distance = 0, lambda = 0;
    size_t cycle_start = 0;
    int found_cycle = 0;

    for (;;) {
        int created;
        size_t node_index = find_node(graph, current, 1, &created);
        CompactNode *node = &graph->nodes[node_index];
        if (!created && node->lambda) {
            inherited_distance = node->value;
            lambda = node->lambda;
            break;
        }
        if (!created) {
            cycle_start = node->value;
            size_t cycle_size = path_length - cycle_start;
            if (!cycle_size || cycle_size > UINT32_MAX) {
                fputs("cycle length exceeds compact field\n", stderr);
                exit(1);
            }
            lambda = (uint32_t)cycle_size;
            found_cycle = 1;
            break;
        }
        if (path_length == *path_capacity) {
            size_t new_capacity = *path_capacity ? *path_capacity * 2 : 1024;
            uint32_t *replacement = realloc(*path_storage, new_capacity * sizeof(*replacement));
            if (!replacement) die("realloc path");
            *path_storage = replacement;
            *path_capacity = new_capacity;
        }
        if (path_length > UINT32_MAX) {
            fputs("path length exceeds compact field\n", stderr);
            exit(1);
        }
        node->value = (uint32_t)path_length;
        (*path_storage)[path_length++] = (uint32_t)node_index;
        current = next_key(graph, cpu, current, transition_count);
    }

    if (found_cycle) {
        for (size_t index = cycle_start; index < path_length; index++) {
            CompactNode *node = &graph->nodes[(*path_storage)[index]];
            node->value = 0;
            node->lambda = lambda;
        }
        inherited_distance = 0;
        for (size_t index = cycle_start; index-- > 0;) {
            if (inherited_distance == UINT32_MAX) {
                fputs("distance exceeds compact field\n", stderr);
                exit(1);
            }
            CompactNode *node = &graph->nodes[(*path_storage)[index]];
            node->value = ++inherited_distance;
            node->lambda = lambda;
        }
    } else {
        for (size_t index = path_length; index-- > 0;) {
            if (inherited_distance == UINT32_MAX) {
                fputs("distance exceeds compact field\n", stderr);
                exit(1);
            }
            CompactNode *node = &graph->nodes[(*path_storage)[index]];
            node->value = ++inherited_distance;
            node->lambda = lambda;
        }
    }
    return find_node(graph, start, 0, NULL);
}

static void histogram_add(Histogram *histogram, uint64_t value) {
    if (value > UINT32_MAX) {
        fputs("histogram value exceeds current pilot representation\n", stderr);
        exit(1);
    }
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
    histogram->counts[value]++;
    if (value > histogram->maximum) histogram->maximum = (uint32_t)value;
}

static void write_histogram(const char *prefix, const char *name, const Histogram *histogram) {
    char path[4096];
    if (snprintf(path, sizeof(path), "%s-%s.csv", prefix, name) >= (int)sizeof(path)) {
        fputs("output path too long\n", stderr);
        exit(2);
    }
    FILE *output = fopen(path, "w");
    if (!output) die(path);
    fputs("value,count\n", output);
    for (uint32_t value = 0; value <= histogram->maximum; value++) {
        if (histogram->counts[value])
            fprintf(output, "%" PRIu32 ",%" PRIu64 "\n", value, histogram->counts[value]);
    }
    if (fclose(output)) die(path);
}

static double seconds_now(void) {
    struct timespec value;
    timespec_get(&value, TIME_UTC);
    return value.tv_sec + value.tv_nsec / 1000000000.0;
}

int main(int argc, char **argv) {
    if (argc != 6) {
        fprintf(stderr, "usage: %s BASIC-ROM KERNAL-ROM STARTS CAPACITY-POWER OUTPUT-PREFIX\n", argv[0]);
        return 2;
    }
    char *end = NULL;
    uint64_t requested = strtoull(argv[3], &end, 0);
    if (!end || *end || !requested || requested > UINT32_MAX) {
        fputs("STARTS must be in 1..4294967295\n", stderr);
        return 2;
    }
    unsigned power = (unsigned)strtoul(argv[4], &end, 0);
    if (!end || *end || power < 10 || power > 31) {
        fputs("CAPACITY-POWER must be in 10..31\n", stderr);
        return 2;
    }

    CompactGraph graph = {0};
    graph.capacity = (size_t)1 << power;
    if (graph.capacity > SIZE_MAX / sizeof(*graph.nodes)) {
        fputs("graph allocation size overflow\n", stderr);
        return 2;
    }
    graph.nodes = malloc(graph.capacity * sizeof(*graph.nodes));
    if (!graph.nodes) die("malloc graph");
    memset(graph.nodes, 0xff, graph.capacity * sizeof(*graph.nodes));

    Cpu *cpu = new_cpu(argv[1], argv[2]);
    State initial_probe = state(cpu);
    if (!equal(initial_probe, initial_probe) || hash(initial_probe) == UINT64_MAX) return 3;
    uint32_t *path = NULL;
    size_t path_capacity = 0;
    Histogram mu = {0}, lambda = {0}, total = {0};
    uint64_t transitions = 0, candidates = 0, accepted = 0;
    double started = seconds_now();

    while (accepted < requested) {
        if (candidates > UINT32_MAX) {
            fputs("exhausted the 32-bit sample permutation\n", stderr);
            return 1;
        }
        uint32_t key = permute32((uint32_t)candidates + UINT32_C(0x06502c64));
        candidates++;
        if (key >= CANONICAL_DOMAIN_SIZE) continue;
        size_t answer_index = classify(&graph, cpu, key,
                                       &path, &path_capacity, &transitions);
        CompactNode *answer = &graph.nodes[answer_index];
        histogram_add(&mu, answer->value);
        histogram_add(&lambda, answer->lambda);
        histogram_add(&total, (uint64_t)answer->value + answer->lambda);
        accepted++;
        if (!(accepted % 100000)) {
            fprintf(stderr, "starts=%" PRIu64 " unique=%zu transitions=%" PRIu64
                    " elapsed=%.1f\n", accepted, graph.count, transitions,
                    seconds_now() - started);
        }
    }

    write_histogram(argv[5], "mu", &mu);
    write_histogram(argv[5], "lambda", &lambda);
    write_histogram(argv[5], "total", &total);

    char summary_path[4096];
    if (snprintf(summary_path, sizeof(summary_path), "%s-summary.json", argv[5])
        >= (int)sizeof(summary_path)) {
        fputs("summary path too long\n", stderr);
        return 2;
    }
    FILE *summary = fopen(summary_path, "w");
    if (!summary) die(summary_path);
    fprintf(summary,
        "{\n"
        "  \"schema\": \"c64-basic-rnd-histogram-pilot-v1\",\n"
        "  \"domainSize\": %" PRIu32 ",\n"
        "  \"sampleMethod\": \"32-bit bijective mix followed by rank rejection\",\n"
        "  \"sampleOffset\": \"0x06502c64\",\n"
        "  \"sampleStarts\": %" PRIu64 ",\n"
        "  \"permutationCandidates\": %" PRIu64 ",\n"
        "  \"uniqueGraphStates\": %zu,\n"
        "  \"transitions\": %" PRIu64 ",\n"
        "  \"graphCapacity\": %zu,\n"
        "  \"graphNodeBytes\": %zu,\n"
        "  \"maxMu\": %" PRIu32 ",\n"
        "  \"maxLambda\": %" PRIu32 ",\n"
        "  \"maxTotal\": %" PRIu32 ",\n"
        "  \"elapsedSeconds\": %.6f\n"
        "}\n",
        CANONICAL_DOMAIN_SIZE, accepted, candidates, graph.count, transitions,
        graph.capacity, sizeof(CompactNode), mu.maximum, lambda.maximum,
        total.maximum, seconds_now() - started);
    if (fclose(summary)) die(summary_path);

    fprintf(stderr, "complete starts=%" PRIu64 " unique=%zu transitions=%" PRIu64
            " elapsed=%.3f node_bytes=%zu\n", accepted, graph.count, transitions,
            seconds_now() - started, sizeof(CompactNode));
    free(total.counts);
    free(lambda.counts);
    free(mu.counts);
    free(path);
    free(cpu);
    free(graph.nodes);
    return 0;
}
