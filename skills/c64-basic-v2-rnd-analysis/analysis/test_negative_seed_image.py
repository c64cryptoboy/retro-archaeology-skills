#!/usr/bin/env python3
import random
import unittest

import negative_seed_image as image
import throwaway_rom_cycle as rom
from cpu6502 import Cpu6502Emulator


class NegativeSeedImageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.basic = rom.checked_rom(rom.BASIC_PATH, rom.BASIC_SHA256)
        cls.kernal = rom.checked_rom(rom.KERNAL_PATH, rom.KERNAL_SHA256)

    def rom_map(self, value: image.NegativeFac) -> bytes:
        cpu = Cpu6502Emulator()
        cpu.inject_bytes(0xA000, self.basic)
        cpu.inject_bytes(0xE000, self.kernal)
        cpu.memory[0x61] = value.exponent
        cpu.memory[0x62:0x66] = value.mantissa.to_bytes(4, "big")
        cpu.memory[0x66] = 0xFF
        cpu.init_cpu(0xE0D3)
        cpu.exit_on_empty_stack = True
        instructions = 0
        while cpu.runcpu():
            instructions += 1
            self.assertLess(instructions, 10_000)
        return bytes(cpu.memory[0x8B:0x90])

    def test_known_minus_one_mapping(self):
        value = image.NegativeFac(0x81, 0x80000000)
        self.assertEqual(image.fac_to_seed(value).bytes, bytes.fromhex("68 00 81 00 00"))
        self.assertEqual(self.rom_map(value), bytes.fromhex("68 00 81 00 00"))

    def test_power_on_seed_has_no_valid_negative_fac_preimage(self):
        seed = image.SeedState.from_bytes(bytes.fromhex("80 4f c7 52 58"))
        self.assertEqual(image.seed_preimages(seed), [])

    def test_exact_image_count(self):
        summary = image.image_summary()
        self.assertEqual(summary["validNegativeFacInputs"], 547_608_330_240)
        self.assertEqual(summary["uniqueReachableSeedStates"], 10_745_675_776)
        self.assertEqual(sum(row["inputMantissas"] for row in summary["rows"]), 1 << 31)

    def test_dense_image_rank_round_trips(self):
        probes = {0, image.IMAGE_SIZE - 1}
        for offset, count in zip(image.IMAGE_CATEGORY_OFFSETS, image.IMAGE_CATEGORY_COUNTS):
            probes.add(offset)
            probes.add(offset + count - 1)
        rng = random.Random(0x10_745_675_776)
        probes.update(rng.randrange(image.IMAGE_SIZE) for _ in range(100_000))
        for index in probes:
            self.assertEqual(image.image_rank(image.image_unrank(index)), index)

    def test_fac_outputs_belong_to_dense_image(self):
        rng = random.Random(0xFAC)
        for _ in range(10_000):
            value = image.NegativeFac(
                rng.randrange(1, 256), rng.randrange(0x80000000, 1 << 32)
            )
            seed = image.fac_to_seed(value)
            self.assertEqual(image.image_unrank(image.image_rank(seed)), seed)

    def test_each_shift_category_count_for_one_128_value_run(self):
        for shifts in range(25):
            first_reversed = (1 << (31 - shifts)) + (0 if shifts == 24 else 0x80)
            outputs = set()
            for reversed_mantissa in range(first_reversed, first_reversed + 128):
                self.assertEqual(32 - reversed_mantissa.bit_length(), shifts)
                self.assertTrue(reversed_mantissa & 0x80)
                mantissa = image.reverse_bytes32(reversed_mantissa)
                for exponent in range(1, 256):
                    outputs.add(image.fac_to_seed(image.NegativeFac(exponent, mantissa)).bytes)
            if shifts <= 6:
                expected = 128 * (1 << shifts) + 1
            elif shifts == 7:
                expected = 128 * 128
            else:
                expected = 128 * 255
            self.assertEqual(len(outputs), expected, f"shift category {shifts}")

    def test_direct_model_matches_rom_and_inverse_contains_input(self):
        rng = random.Random(0xE0D3)
        values = [
            image.NegativeFac(1, 0x80000000),
            image.NegativeFac(0x7F, 0xFFFFFFFF),
            image.NegativeFac(0x80, 0xFFFFFFFF),
            image.NegativeFac(0xFF, 0xFFFFFFFF),
        ]
        values.extend(
            image.NegativeFac(rng.randrange(1, 256), rng.randrange(0x80000000, 1 << 32))
            for _ in range(256)
        )
        for value in values:
            seed = image.fac_to_seed(value)
            self.assertEqual(self.rom_map(value), seed.bytes)
            self.assertIn(value, image.seed_preimages(seed))


if __name__ == "__main__":
    unittest.main()
