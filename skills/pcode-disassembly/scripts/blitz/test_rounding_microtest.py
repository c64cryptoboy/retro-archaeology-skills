import hashlib
import unittest

import build_rounding_microtest as micro


class RoundingMicrotestTests(unittest.TestCase):
    def test_deterministic_prg_and_links(self):
        prg = micro.build_prg()
        self.assertEqual(len(prg), 454)
        self.assertEqual(
            hashlib.sha256(prg).hexdigest(),
            "976f7edb81988e59ece8cbf1e703b148e7b91c500d04d1b767f1084d806abd6e",
        )
        self.assertEqual(prg[:2], b"\x01\x08")

        offset = 2
        address = micro.LOAD_ADDRESS
        seen = []
        while True:
            next_address = int.from_bytes(prg[offset:offset + 2], "little")
            if next_address == 0:
                break
            self.assertGreater(next_address, address)
            seen.append(int.from_bytes(prg[offset + 2:offset + 4], "little"))
            offset += next_address - address
            address = next_address
        self.assertEqual(seen, sorted(micro.SOURCE_LINES))
        self.assertEqual(offset, len(prg) - 2)

    def test_material_constructs_remain_present(self):
        self.assertEqual(micro.tokenize('PRINT"POKE"'), bytes([0x99]) + b'"POKE"')
        self.assertIn("Z%=401*(A*B/401-INT(A*B/401))", micro.SOURCE_LINES.values())
        self.assertIn("X$=L$(82*RND(0)+1)", micro.SOURCE_LINES.values())
        self.assertIn("POKE49152,256*RND(0)", micro.SOURCE_LINES.values())


if __name__ == "__main__":
    unittest.main()
