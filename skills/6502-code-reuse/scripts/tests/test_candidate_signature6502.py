import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from anchor_scan6502 import decode_window, shape_tokens
from candidate_signature6502 import find_matches, is_subsequence


class CandidateSignatureTests(unittest.TestCase):
    def test_shape_subsequence_retains_immediates_and_allows_insertion(self):
        # LDY #0; LDA ($10),Y; STA $20; INY; LDA ($10),Y; STA $21
        reference = bytes.fromhex("a000 b110 8520 c8 b110 8521")
        decoded = decode_window(reference, 0, 6, base_address=None)
        self.assertIsNotNone(decoded)
        shape = shape_tokens(decoded)

        # Relocated operands and one target-only CLC insertion still match.
        target = bytes.fromhex("ff a000 b140 8560 c8 18 b140 8561 ff")
        matches = find_matches(target, shape, maximum_insertions=1)
        self.assertEqual([(m["startOffset"], m["insertedInstructions"]) for m in matches], [(1, 1)])

        # A changed immediate is deliberately not scrubbed.
        changed = bytes.fromhex("a001 b140 8560 c8 18 b140 8561")
        self.assertEqual(find_matches(changed, shape, maximum_insertions=1), [])

    def test_subsequence_requires_order(self):
        self.assertTrue(is_subsequence((1, 2, 3), (1, 9, 2, 3)))
        self.assertFalse(is_subsequence((1, 2, 3), (1, 3, 2)))


if __name__ == "__main__":
    unittest.main()
