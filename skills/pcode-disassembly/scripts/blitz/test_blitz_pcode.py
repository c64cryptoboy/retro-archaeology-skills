import json
import tempfile
import unittest
from pathlib import Path

import blitz_pcode as bp


class BlitzPcodeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        # Payload includes instruction fixtures at $1000 and two 7-byte variables at $1040.
        payload = bytearray(0x60)
        fixture = bytes.fromhex(
            "b5 "              # small 5
            "a6 c5 "           # u8 197
            "a7 02 91 "        # u16 657
            "e9 41 "           # short string A
            "e7 03 42 43 44 "  # long string BCD
            "1a 10 20 "        # gosub $1020
            "52 10 30 "        # branch $1030
            "1f 08 "           # skip target address+8
            "1b 06 10 20 10 30"  # ON table: total size 6, two targets
        )
        payload[: len(fixture)] = fixture
        payload[0x20] = 0x1D
        payload[0x30] = 0x4F
        payload[0x40:0x47] = bytes.fromhex("53 00 00 00 00 00 00")
        payload[0x47:0x4E] = bytes.fromhex("41 80 00 00 00 00 00")
        self.prg = self.root / "fixture.prg"
        self.prg.write_bytes((0x1000).to_bytes(2, "little") + payload)
        image = bp.load_prg(self.prg)
        self.profile = {
            "schema": "blitz-pcode-profile-v1",
            "id": "test",
            "sourcePrgSha256": image.sha256,
            "layout": {
                "initPcode": 0x1000,
                "variableTable": 0x1040,
                "variableCount": 2,
                "variableRecordSize": 7,
            },
            "opcodeFamilies": [
                {"minimum": "80", "maximum": "9F", "mnemonic": "LOAD_VAR", "operand": "none", "variableIndexMask": 31, "confidence": "test"},
                {"minimum": "B0", "maximum": "BF", "mnemonic": "CONST_SMALL", "operand": "none", "valueMask": 15, "confidence": "test"},
                {"minimum": "E8", "maximum": "EF", "mnemonic": "CONST_STRING", "operand": "inline_string_short", "confidence": "test"},
            ],
            "exactOpcodes": {
                "A6": {"mnemonic": "CONST_U8", "operand": "u8"},
                "A7": {"mnemonic": "CONST_U16", "operand": "u16be"},
                "E7": {"mnemonic": "CONST_STRING", "operand": "inline_string_u8"},
                "1A": {"mnemonic": "GOSUB", "operand": "target_be16", "control": "gosub"},
                "1B": {"mnemonic": "ON_GOTO", "operand": "on_table", "control": "multi_branch"},
                "1D": {"mnemonic": "RETURN", "operand": "none", "control": "return"},
                "1F": {"mnemonic": "IF_SKIP", "operand": "skip_u8", "control": "branch"},
                "4F": {"mnemonic": "END", "operand": "none", "control": "return"},
                "52": {"mnemonic": "IF_GOTO", "operand": "target_be16", "control": "branch"},
            },
        }

    def tearDown(self):
        self.temp.cleanup()

    def test_family_operands_and_strings(self):
        image = bp.load_prg(self.prg)
        names = bp.variable_names(image, self.profile)
        self.assertEqual(names, ["S", "A$"])
        expected = [
            (0x1000, 1, 5),
            (0x1001, 2, 197),
            (0x1003, 3, 657),
        ]
        for address, size, value in expected:
            record = bp.decode_one(image, self.profile, address, names)
            self.assertEqual((record["size"], record["value"]), (size, value))
        self.assertEqual(bp.decode_one(image, self.profile, 0x1006)["text"], "A")
        self.assertEqual(bp.decode_one(image, self.profile, 0x1008)["text"], "BCD")

    def test_fac5_exact_decode(self):
        self.assertEqual(bp.decode_fac5(bytes.fromhex("90 50 20 00 00")), 53280)
        self.assertEqual(bp.decode_fac5(bytes.fromhex("00 00 00 00 00")), 0)

    def test_targets_and_on_table(self):
        image = bp.load_prg(self.prg)
        self.assertEqual(bp.decode_one(image, self.profile, 0x100D)["target"], 0x1020)
        self.assertEqual(bp.decode_one(image, self.profile, 0x1010)["target"], 0x1030)
        skip = bp.decode_one(image, self.profile, 0x1013)
        self.assertEqual(skip["target"], 0x101B)
        table = bp.decode_one(image, self.profile, 0x1015)
        self.assertEqual(table["size"], 6)
        self.assertEqual(table["targets"], [0x1020, 0x1030])

    def test_unknown_length_is_explicit(self):
        image = bp.load_prg(self.prg)
        image.data[0:0] if False else None  # Image remains immutable.
        # $104E is zero, an expression operator and therefore known; $1031 is an unprofiled direct opcode.
        altered = bytearray(image.data)
        altered[0x31] = 0x70
        unknown_image = bp.Image(image.path, image.load, bytes(altered), image.sha256)
        record = bp.decode_one(unknown_image, self.profile, 0x1031)
        self.assertIsNone(record["size"])
        self.assertIn("must stop", record["diagnostic"])

    def test_trace_override_is_data_driven(self):
        image = bp.load_prg(self.prg)
        trace = self.root / "trace.json"
        trace.write_text(json.dumps({
            "entries": [{"address": 0x1000, "opcode": 0xB6}],
            "memoryPatches": [{"address": 0x1000, "original": 0xB5, "observed": 0xB6}],
        }))
        result = bp.validate_trace(image, self.profile, trace)
        self.assertEqual(result["errors"], [])

    def test_conservative_for_next_pairing(self):
        records = [
            {"address": 0x2000, "size": 2, "operandKind": "descriptor_u8", "descriptorOffset": 7},
            {"address": 0x2002, "size": 1, "control": "for_setup"},
            {"address": 0x2003, "size": 1},
            {"address": 0x2004, "size": 2, "operandKind": "descriptor_u8", "descriptorOffset": 7},
            {"address": 0x2006, "size": 1, "control": "next"},
        ]
        inferred = bp.infer_structured_loop_targets(records)
        self.assertEqual(inferred, [{"address": 0x2006, "setup": 0x2002, "target": 0x2003, "descriptorOffset": 7}])
        self.assertEqual(records[-1]["target"], 0x2003)
        self.assertEqual(records[-1]["targetConfidence"], "strong-structure")

    def test_length_prefixed_data_block(self):
        data_prg = self.root / "data.prg"
        data_prg.write_bytes((0x3000).to_bytes(2, "little") + b"\x03ABC\x02DE\xFF")
        profile = {
            "layout": {
                "dataStart": 0x3000,
                "dataEndExclusive": 0x3008,
                "dataEncoding": "length-prefixed-strings-ff",
            }
        }
        result = bp.decode_data_block(bp.load_prg(data_prg), profile)
        self.assertEqual([record["text"] for record in result["records"][:-1]], ["ABC", "DE"])
        self.assertEqual(result["records"][-1]["kind"], "terminator")

    def test_inline_basic_tail_stops_at_unquoted_colon(self):
        inline = self.root / "inline.prg"
        inline.write_bytes((0x2000).to_bytes(2, "little") + b'\x18,"A:B",9:\x4f')
        profile = {
            "schema": "blitz-pcode-profile-v1",
            "id": "inline",
            "exactOpcodes": {
                "18": {"mnemonic": "SYS", "operand": "inline_basic_to_colon"},
                "4F": {"mnemonic": "END", "operand": "none", "control": "return"},
            },
        }
        record = bp.decode_one(bp.load_prg(inline), profile, 0x2000)
        self.assertEqual(record["text"], ',"A:B",9')
        self.assertEqual(record["size"], 10)
        self.assertEqual(record["terminator"], 0x3A)

    def test_def_fn_header_exposes_body_and_skip_edges(self):
        function = self.root / "function.prg"
        function.write_bytes(
            (0x1100).to_bytes(2, "little")
            + bytes.fromhex("37 b1 00 2c 00 0a b1 b1 09 39 4f")
        )
        profile = {
            "schema": "blitz-pcode-profile-v1",
            "id": "function",
            "layout": {"variableCount": 0, "variableRecordSize": 7, "variableTable": 0x110B},
            "opcodeFamilies": [
                {"minimum": "B0", "maximum": "BF", "mnemonic": "CONST_SMALL", "operand": "none", "valueMask": 15},
            ],
            "exactOpcodes": {
                "09": {"mnemonic": "MULTIPLY", "operand": "none"},
                "37": {"mnemonic": "DEF_FN", "operand": "def_fn_header", "control": "def_fn"},
                "39": {"mnemonic": "FN_RETURN", "operand": "none", "control": "return"},
                "4F": {"mnemonic": "END", "operand": "none", "control": "return"},
            },
        }
        image = bp.load_prg(function)
        header = bp.decode_one(image, profile, 0x1100)
        self.assertEqual(header["functionDescriptorOffset"], 0x00B1)
        self.assertEqual(header["parameterDescriptorOffset"], 0x002C)
        self.assertEqual(bp.successors(header, profile)[0], [0x110A, 0x1106])
        result = bp.recursive_decode(image, profile, [0x1100], 0x1100, 0x110B)
        self.assertEqual(result["coverage"]["decodedBytes"], 11)
        self.assertEqual([item["address"] for item in result["instructions"]], [0x1100, 0x1106, 0x1107, 0x1108, 0x1109, 0x110A])

    def test_truncation_refuses(self):
        short = self.root / "short.prg"
        short.write_bytes((0x2000).to_bytes(2, "little") + b"\xE7\x05AB")
        with self.assertRaisesRegex(bp.DecodeError, "truncated"):
            bp.decode_one(bp.load_prg(short), self.profile, 0x2000)


if __name__ == "__main__":
    unittest.main()
