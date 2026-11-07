"""Portable CLI reporting controls; all input/output operations are mocked."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import g64_extract as g


class ExtractionReportingTests(unittest.TestCase):
    def invoke(self, payload, *, json_mode=False, write_error=None):
        entry = {"name": "TEST", "startTrack": 1, "startSector": 0,
                 "closed": True, "locked": False, "reportedBlocks": 1,
                 "type": "PRG"}
        disk = {"name": "SYNTHETIC", "id": "00", "dosType": "2A"}
        chain = [{"track": 1, "sector": 0}]
        args = ["g64_extract.py", "synthetic.g64", "--extract", "TEST",
                "--output", "derived.prg"]
        if json_mode:
            args.append("--json")
        output = io.StringIO()
        with (patch.object(sys, "argv", args),
              patch.object(g, "read_g64", return_value=({}, {"fixture": True})),
              patch.object(g, "read_directory", return_value=(disk, [entry])),
              patch.object(g, "extract_chain", return_value=(payload, chain)),
              patch.object(Path, "mkdir"),
              patch.object(Path, "write_bytes", side_effect=write_error) as write,
              contextlib.redirect_stdout(output)):
            g.main()
            write.assert_called_once_with(payload)
        return output.getvalue()

    def test_zero_byte_text(self):
        output = self.invoke(b"")
        self.assertIn("0 bytes, load=unavailable,", output)
        self.assertIn(hashlib.sha256(b"").hexdigest(), output)

    def test_one_byte_text(self):
        self.assertIn("1 bytes, load=unavailable,", self.invoke(b"\x01"))

    def test_two_byte_text(self):
        self.assertIn("2 bytes, load=$0801,", self.invoke(b"\x01\x08"))

    def assert_json_extraction(self, payload, expected_address):
        result = json.loads(self.invoke(payload, json_mode=True))
        self.assertEqual(set(result), {"image", "disk", "entries", "extraction"})
        extraction = result["extraction"]
        self.assertEqual(set(extraction), {
            "entry", "output", "byteCount", "sha256", "loadAddress", "chain"})
        self.assertEqual(extraction["loadAddress"], expected_address)
        self.assertEqual(extraction["byteCount"], len(payload))
        self.assertEqual(extraction["sha256"], hashlib.sha256(payload).hexdigest())
        self.assertEqual(extraction["chain"], [{"track": 1, "sector": 0}])
        self.assertEqual(extraction["output"], "derived.prg")

    def test_zero_byte_json(self):
        self.assert_json_extraction(b"", None)

    def test_one_byte_json(self):
        self.assert_json_extraction(b"\x01", None)

    def test_two_byte_json(self):
        self.assert_json_extraction(b"\x01\x08", 0x0801)

    def test_text_write_failure_propagates(self):
        error = OSError("synthetic write refusal")
        with self.assertRaises(OSError) as caught:
            self.invoke(b"", write_error=error)
        self.assertIs(caught.exception, error)

    def test_json_write_failure_propagates(self):
        error = OSError("synthetic write refusal")
        with self.assertRaises(OSError) as caught:
            self.invoke(b"\x01", json_mode=True, write_error=error)
        self.assertIs(caught.exception, error)


if __name__ == "__main__":
    unittest.main()
