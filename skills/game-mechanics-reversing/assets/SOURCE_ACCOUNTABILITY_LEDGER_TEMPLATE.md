# [Game] source-unit accountability ledger

Create this near the start of analysis, before mechanics are considered mature. Its purpose is not to guess what is “interesting”; it is to ensure every in-scope source unit is mechanically understood or explicitly carried as an open item until context resolves it.

## Scope and counts

- **Edition/build/hash:**
- **Loaded and executable ranges/modules:**
- **Interpreted-source total:**
- **Confirmed/probable native-code total:**
- **Data/resource total:**
- **Unknown/unclassified total:**
- **Status vocabulary:** understood / mechanically understood, context pending / unreachable / data / excluded / open

## Interpreted/high-level source ledger

Use at least one row per BASIC/source line. Enumerate materially distinct colon-separated statements as `S1`, `S2`, etc. in the same row or split them into rows. Include REM/DATA/unlinked lines so absence from execution is an explicit classification rather than an omission.

| Line/unit | Reachability/entry phase | Mechanical statement effects | Reads | Writes | Calls/branches/fallthrough | ROM/hardware/environment dependencies | Lifecycle relevance | Oddity or contextual question | Evidence | Status |
|---|---|---|---|---|---|---|---|---|---|---|
| | | | | | | | startup / play / death / READY / etc. | | | |

For tokenized BASIC and similar interpreters, explicitly check:

- actual grammar and precedence, rather than reading syntax as another language;
- assignment versus comparison, boolean values, coercion, integer/floating behavior, and evaluation order;
- implicit/default variables and arrays, variable-name significance, allocation side effects, and undefined-value assumptions;
- every `POKE`, `PEEK`, `SYS`, vector change, ROM call, memory reservation, and hardware address;
- linked, hidden/unlinked, DATA, REM, fallthrough, GOTO/GOSUB/ON targets, and unreachable tails;
- what survives or breaks after STOP, END, error, READY, restart, LOAD, save/restore, and warm/cold entry;
- expressions that compute and discard values, tautologies, chained-looking operations, reused scratch names, and statements whose comments/messages disagree with state changes.

## Native-code accountability

Do not linearly interpret data as instructions. First use the disassembly workflow to establish code/data/unknown boundaries and entry points.

The accountability requirement is then:

1. every byte range in scope is classified as confirmed/probable code, confirmed/probable data, unused/padding, excluded, or unknown;
2. every instruction in confirmed reachable code belongs to a block/routine whose mechanical effects, successors, memory/ROM/hardware accesses, and calling assumptions are accounted for;
3. every instruction or effect that does not yet fit the block interpretation is listed as open rather than silently passed over.

A fully annotated disassembly can serve as the instruction ledger. Use the summary below to expose coverage and unresolved areas.

| Range/routine/block | Classification and reachability | Entry sources | Mechanical/semantic role | Inputs | Outputs/clobbers | Reads/writes/calls | Banking/ROM/hardware/timing assumptions | Unexplained instructions/effects | Evidence | Status |
|---|---|---|---|---|---|---|---|---|---|---|
| | | | | | | | | | | |

## Context-revisit queue

Mechanical understanding often precedes knowing why a unit exists. Every context-pending or open item must appear here and be revisited after the state, scheduler, lifecycle, data, protection, and documentation models exist.

| Unit/range | What is already known | Missing context | Why it may matter | Smallest next check | Owner/status | Resolution/evidence |
|---|---|---|---|---|---|---|
| | | | | | | |

## Static-first runtime admission gate

Before broad command, boundary, route, or gameplay emulation begins, this ledger must support separate parser/dispatcher reachability, material state read/write, update/lifecycle, resource/media, and RNG maps plus an indexed runtime-hypothesis list. Early runtime is limited to bounded acquisition of unpacked/generated/banked/overlaid code or resolution of one explicit static blocker; add the acquired material here and resume static analysis before expanding tests.

Do not call source analysis complete because major routines or a winning path are understood. Close this ledger only when every in-scope unit is understood, classified unreachable/data/excluded with evidence, or represented by a specific open item and next check. Later discoveries must update the ledger and trigger context review of related units.
