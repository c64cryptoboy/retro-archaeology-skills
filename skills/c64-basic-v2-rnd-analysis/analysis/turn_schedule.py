#!/usr/bin/env python3
"""Replay two declared turn schedules on the bundled, ROM-checked small orbit."""
import json
from pathlib import Path
from typing import NamedTuple

ORBIT = Path(__file__).resolve().parent / "visualization/small-mu5-lambda7.json"


class Turn(NamedTuple):
    tested: int
    discarded: int | None
    encounter: bool


def replay(orbit: dict, *, extra_below_half: bool) -> tuple[list[Turn], list[Turn]]:
    """Return transient and repeating turns, indexed by the draw tested first."""
    nodes = orbit["nodes"]
    states = [bytes.fromhex(node["stateBytes"]) for node in nodes]
    repeat = orbit.get("nextRepeatedState", {})
    entry = orbit.get("repeatTo", -1)
    if not (0 <= entry < len(states) and orbit.get("repeatFrom") == len(states) - 1
            and repeat.get("index") == len(states) and repeat.get("sameAs") == entry
            and bytes.fromhex(repeat.get("stateBytes", "")) == states[entry]
            and all(len(s) == 5 and s[0] and s[1] < 0x80 for s in states)
            and [node["index"] for node in nodes] == list(range(len(states)))
            and len(set(states)) == len(states)):
        raise ValueError("frequency undetermined: expected a complete closed orbit")

    def advance(i: int) -> int:
        return i + 1 if i + 1 < len(states) else entry

    first_seen = {}
    turns = []
    i = advance(0)  # The negative seed result at index 0 is not tested.
    while i not in first_seen:
        first_seen[i] = len(turns)
        # These are positive normalized packed results.  At powers of two
        # the fraction field is zero, so strict comparisons need only the exponent.
        takes_extra = extra_below_half and states[i][0] < 0x80  # X < 1/2
        discarded = advance(i) if takes_extra else None
        turns.append(Turn(i, discarded, states[i][0] < 0x7E))  # X < 1/8
        i = advance(discarded if discarded is not None else i)
    cut = first_seen[i]
    return turns[:cut], turns[cut:]


if __name__ == "__main__":
    orbit = json.loads(ORBIT.read_text(encoding="utf-8"))
    for extra in (False, True):
        print("Extra draw if X < 1/2" if extra else "One draw per turn")
        transient, repeating = replay(orbit, extra_below_half=extra)
        for phase, turns in (("transient", transient), ("repeating", repeating)):
            print(f"  {phase}: encounters={sum(t.encounter for t in turns)}, turns={len(turns)}")
            for turn in turns:
                print(f"    tested={turn.tested} discarded={turn.discarded} encounter={turn.encounter}")
