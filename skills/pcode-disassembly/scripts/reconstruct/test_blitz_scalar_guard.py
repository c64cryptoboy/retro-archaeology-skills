"""Raw scalar-name positions are part of the leaf-FN admission contract."""
import unittest
from test_blitz_leaf_fn import fixture, output


class ScalarNameGuardTests(unittest.TestCase):
    def report_with_formal(self, raw, displayed, family="blitz"):
        report = fixture(family)
        report["scalarRecords"][0].update(bytes=raw.hex() + "00" * 5, name=displayed)
        for row in report["instructions"]:
            if row.get("variableIndex") == 0:
                row["variable"] = displayed
        return report

    def test_leading_nul_does_not_become_a_valid_formal(self):
        for family in ("blitz", "austrospeed"):
            for letter in range(0x41, 0x5B):
                with self.subTest(family=family, letter=letter):
                    _, text = output(self.report_with_formal(bytes([0, letter]), chr(letter), family), family)
                    self.assertIn("REM DEF_FN", text)
                    self.assertNotIn("RETURN FN F_9 =", text)

    def test_valid_raw_name_positions_keep_existing_admission(self):
        for family in ("blitz", "austrospeed"):
            for raw, name in ((b"Q\0", "Q"), (b"Q0", "Q0"), (b"QZ", "QZ")):
                with self.subTest(family=family, raw=raw):
                    _, text = output(self.report_with_formal(raw, name, family), family)
                    self.assertIn("DEF FN F_9(" + name + ")", text)
                    self.assertIn("RETURN FN F_9 =", text)


if __name__ == "__main__":
    unittest.main()
