import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from render_alignment6502 import presentation_rows, render_table, select_match


def instruction(address, mnemonic, operand=""):
    text = mnemonic if not operand else f"{mnemonic} {operand}"
    return {"address": address, "mnemonic": mnemonic, "text": text}


class RenderAlignmentTests(unittest.TestCase):
    def test_renderer_preserves_gap_as_blank_side(self):
        match = {
            "columns": [
                {
                    "left": instruction(0x1000, "LDA", "$20"),
                    "right": instruction(0x2000, "LDA", "$40"),
                    "relation": "relational-exact",
                },
                {
                    "left": None,
                    "right": instruction(0x2002, "CLC"),
                    "relation": "right-gap",
                },
                {
                    "left": instruction(0x1002, "ADC", "#$01"),
                    "right": instruction(0x2003, "ADC", "#$01"),
                    "relation": "relational-exact",
                },
            ]
        }
        rendered = render_table(match, "APPLE II", "C64")
        lines = rendered.splitlines()
        self.assertIn("$1000", lines[3])
        self.assertIn("$2000", lines[3])
        self.assertNotIn("$100", lines[4].split("|")[0])
        self.assertIn("$2002", lines[4].split("|")[1])
        self.assertIn("$1002", lines[5])
        self.assertIn("$2003", lines[5])

    def test_replacement_hunk_uses_non_overlapping_rows(self):
        columns = [
            {
                "left": instruction(0x6096, "LDA", "#$99"),
                "right": instruction(0x5FDC, "LDA", "#$99"),
                "relation": "relational-exact",
            },
            {
                "left": None,
                "right": instruction(0x5FDE, "STA", "($7E),Y"),
                "relation": "gap-left",
            },
            {
                "left": instruction(0x6098, "STA", "$D1"),
                "right": instruction(0x5FE0, "INY"),
                "relation": "different",
            },
            {
                "left": instruction(0x609A, "STA", "$D2"),
                "right": instruction(0x5FE1, "STA", "($7E),Y"),
                "relation": "different",
            },
            {
                "left": instruction(0x609C, "INC", "$D5"),
                "right": instruction(0x5FE3, "INC", "$55"),
                "relation": "relational-exact",
            },
        ]
        rows = presentation_rows(columns)
        self.assertEqual(len(rows), 7)
        self.assertEqual([row[0][0] for row in rows], ["$6096", "", "", "", "$6098", "$609A", "$609C"])
        self.assertEqual([row[1][0] for row in rows], ["$5FDC", "$5FDE", "$5FE0", "$5FE1", "", "", "$5FE3"])

        raw_rows = presentation_rows(columns, pair_differences=True)
        self.assertEqual(len(raw_rows), 5)
        self.assertEqual(raw_rows[2][0][0], "$6098")
        self.assertEqual(raw_rows[2][1][0], "$5FE0")

    def test_default_selects_longest_supporting_run(self):
        document = {
            "comparisons": [
                {
                    "matches": [
                        {"id": "short", "metrics": {"longestSupportingRun": 4}},
                        {"id": "long", "metrics": {"longestSupportingRun": 7}},
                    ]
                }
            ]
        }
        _, match = select_match(document)
        self.assertEqual(match["id"], "long")


if __name__ == "__main__":
    unittest.main()
