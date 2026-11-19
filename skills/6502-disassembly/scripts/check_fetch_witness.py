"""Synthetic evidence exercise: one physical RAM byte ($6200), no CPU execution."""

import unittest

# Each tuple is a complete ordered log *for this byte*.  W is a RAM write;
# X is an opcode fetch with its observed value, not just a sampled PC.
INITIAL = 0xE8  # INX
TEMP = 0xCA     # DEX
PATCH = ("W", TEMP)
RESTORE = ("W", INITIAL)
DURING = (PATCH, ("X", TEMP), RESTORE)
AFTER = (PATCH, RESTORE, ("X", INITIAL))


def summarize(events):
    """Check the synthetic log, then project it to evidence without fetch order/value."""
    current = INITIAL
    writes = []
    fetches = []
    for kind, value in events:
        if kind == "W":
            current = value
            writes.append(value)
        elif kind == "X" and value == current:
            fetches.append(value)
        else:
            raise ValueError("event inconsistent with the one-byte RAM model")
    summary = (INITIAL, current, tuple(writes), len(fetches))
    return summary, tuple(fetches)


class FetchWitness(unittest.TestCase):
    def test_split_recordings(self):
        recordings = ((PATCH, RESTORE), (("X", INITIAL),))
        access = [{kind for kind, _ in run} for run in recordings]
        self.assertEqual(set.union(*access), {"W", "X"})
        self.assertFalse(any({"W", "X"} <= kinds for kinds in access))

    def test_same_run_summary_collision(self):
        summary_a, fetched_a = summarize(DURING)
        summary_b, fetched_b = summarize(AFTER)
        self.assertEqual(summary_a, (INITIAL, INITIAL, (TEMP, INITIAL), 1))
        self.assertEqual(summary_a, summary_b)
        self.assertEqual(fetched_a, (TEMP,))
        self.assertEqual(fetched_b, (INITIAL,))

    def test_stale_fetch_value_rejected(self):
        with self.assertRaisesRegex(ValueError, "inconsistent"):
            summarize((PATCH, RESTORE, ("X", TEMP)))


if __name__ == "__main__":
    unittest.main(verbosity=2)
