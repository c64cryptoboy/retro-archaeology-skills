/* Shared-cache functional-graph classifier using generated exact ROM blocks. */
#define GENERATED_RND_NO_MAIN
#include "generated_rnd_cycle.c"

typedef struct {
    State state;
    uint64_t distance;
    uint64_t lambda;
    uint64_t run_id;
    uint32_t path_index;
    uint8_t used;
    uint8_t classified;
} GraphNode;

typedef struct {
    GraphNode *nodes;
    size_t capacity;
    size_t count;
} Graph;

static State parse_state(const char *text) {
    State result;
    if (strlen(text) != 10) {
        fprintf(stderr, "state must contain exactly 10 hexadecimal digits: %s\n", text);
        exit(2);
    }
    for (unsigned index = 0; index < 5; index++) {
        int high = hex_digit(text[index * 2]);
        int low = hex_digit(text[index * 2 + 1]);
        if (high < 0 || low < 0) {
            fprintf(stderr, "invalid state: %s\n", text);
            exit(2);
        }
        result.b[index] = (uint8_t)((high << 4) | low);
    }
    return result;
}

static size_t graph_find(Graph *graph, State wanted, int create) {
    size_t index = (size_t)hash(wanted) & (graph->capacity - 1);
    while (graph->nodes[index].used && !equal(graph->nodes[index].state, wanted))
        index = (index + 1) & (graph->capacity - 1);
    if (!graph->nodes[index].used && create) {
        if ((graph->count + 1) * 10 >= graph->capacity * 7) {
            fputs("graph table reached 70% load; choose a larger --capacity-power\n", stderr);
            exit(2);
        }
        graph->nodes[index].used = 1;
        graph->nodes[index].state = wanted;
        graph->count++;
    }
    return index;
}

static State next_state(Cpu *cpu, State current) {
    memcpy(cpu->m + RNDX, current.b, 5);
    cpu->m[0x68] = 0;
    return advance(cpu);
}

static void classify(Graph *graph, Cpu *cpu, State start, uint64_t run_id,
                     size_t **path_storage, size_t *path_capacity,
                     uint64_t *transition_count) {
    size_t path_length = 0;
    State current = start;
    uint64_t inherited_distance = 0, lambda = 0;
    size_t cycle_start = 0;
    int found_cycle = 0;

    for (;;) {
        size_t node_index = graph_find(graph, current, 1);
        GraphNode *node = &graph->nodes[node_index];
        if (node->classified) {
            inherited_distance = node->distance;
            lambda = node->lambda;
            break;
        }
        if (node->run_id == run_id) {
            cycle_start = node->path_index;
            lambda = path_length - cycle_start;
            found_cycle = 1;
            break;
        }
        if (path_length == *path_capacity) {
            size_t new_capacity = *path_capacity ? *path_capacity * 2 : 1024;
            size_t *replacement = realloc(*path_storage, new_capacity * sizeof(*replacement));
            if (!replacement) die("realloc path");
            *path_storage = replacement;
            *path_capacity = new_capacity;
        }
        node->run_id = run_id;
        node->path_index = (uint32_t)path_length;
        (*path_storage)[path_length++] = node_index;
        current = next_state(cpu, current);
        (*transition_count)++;
    }

    if (found_cycle) {
        for (size_t index = cycle_start; index < path_length; index++) {
            GraphNode *node = &graph->nodes[(*path_storage)[index]];
            node->distance = 0;
            node->lambda = lambda;
            node->classified = 1;
        }
        inherited_distance = 0;
        for (size_t index = cycle_start; index-- > 0;) {
            GraphNode *node = &graph->nodes[(*path_storage)[index]];
            node->distance = ++inherited_distance;
            node->lambda = lambda;
            node->classified = 1;
        }
    } else {
        for (size_t index = path_length; index-- > 0;) {
            GraphNode *node = &graph->nodes[(*path_storage)[index]];
            node->distance = ++inherited_distance;
            node->lambda = lambda;
            node->classified = 1;
        }
    }
}

static void print_state(State state_value) {
    for (unsigned index = 0; index < 5; index++) printf("%02x", state_value.b[index]);
}

int main(int argc, char **argv) {
    if (argc < 4 || argc > 5) {
        fprintf(stderr, "usage: %s BASIC-ROM KERNAL-ROM STATES.txt [capacity-power]\n", argv[0]);
        return 2;
    }
    char *end = NULL;
    unsigned power = argc == 5 ? (unsigned)strtoul(argv[4], &end, 10) : 20;
    if ((argc == 5 && (!end || *end)) || power < 10 || power > 31) {
        fputs("capacity-power must be in 10..31\n", stderr);
        return 2;
    }
    Graph graph = {0};
    graph.capacity = (size_t)1 << power;
    graph.nodes = calloc(graph.capacity, sizeof(*graph.nodes));
    if (!graph.nodes) die("calloc graph");
    Cpu *cpu = new_cpu(argv[1], argv[2]);
    FILE *input = fopen(argv[3], "r");
    if (!input) die(argv[3]);
    char line[256];
    uint64_t run_id = 0, transition_count = 0;
    size_t *path = NULL, path_capacity = 0;
    puts("state,mu,lambda");
    while (fgets(line, sizeof(line), input)) {
        char *start_text = line;
        while (*start_text == ' ' || *start_text == '\t') start_text++;
        char *end_text = start_text + strcspn(start_text, " \t\r\n#");
        *end_text = 0;
        if (!*start_text) continue;
        State start = parse_state(start_text);
        classify(&graph, cpu, start, ++run_id, &path, &path_capacity, &transition_count);
        GraphNode *answer = &graph.nodes[graph_find(&graph, start, 0)];
        print_state(start);
        printf(",%" PRIu64 ",%" PRIu64 "\n", answer->distance, answer->lambda);
    }
    if (ferror(input)) die("read states");
    fclose(input);
    fprintf(stderr, "starts=%" PRIu64 " unique_states=%zu transitions=%" PRIu64 " table_capacity=%zu\n",
            run_id, graph.count, transition_count, graph.capacity);
    free(path);
    free(cpu);
    free(graph.nodes);
    return 0;
}
