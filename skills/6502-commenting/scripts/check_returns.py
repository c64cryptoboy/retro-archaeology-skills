"""Run only this authored caller and callee with the public shared/6502 helper."""
import unittest

from cpu6502 import Cpu6502Emulator, FC


CALLER, CALLEE = 0x4700, 0x4800
CALLER_S = 0xD4
CODE = bytes.fromhex("8A 48 A2 3C B0 03 68 AA 60 68 AA 60")
# At $480A only: TSX instead of TAX.  Both instructions write X.
ALTERED = CODE[:10] + b"\xBA" + CODE[11:]


def observe(code, x, carry):
    cpu = Cpu6502Emulator()
    cpu.memory[CALLER:CALLER + 3] = bytes.fromhex("20 00 48")  # JSR $4800
    cpu.memory[CALLEE:CALLEE + len(code)] = code
    cpu.pc, cpu.sp, cpu.x = CALLER, CALLER_S, x
    if carry:
        cpu.flags |= FC
    cpu.runcpu()  # execute the call
    if cpu.pc != CALLEE:
        raise AssertionError("caller did not reach the callee")
    entry_s = cpu.sp
    for _ in range(7):
        pc, before_s = cpu.pc, cpu.sp
        if not CALLEE <= pc < CALLEE + len(code):
            raise AssertionError(f"left callee at ${pc:04X} without RTS")
        cpu.runcpu()
        if pc in (0x4808, 0x480B):
            return pc, entry_s, before_s, cpu.pc, cpu.sp, cpu.a, cpu.x
    raise AssertionError("no return within seven callee instructions")


class ReturnsTest(unittest.TestCase):
    def check_variant(self, code, altered):
        for carry in (0, 1):
            for x in range(256):
                with self.subTest(carry=carry, x=x):
                    # Independent oracle: RTS site, S at entry/RTS, resumed PC/S, A, X.
                    want_x = 0xD2 if altered and carry else x
                    self.assertEqual(observe(code, x, carry),
                                     (0x480B if carry else 0x4808, 0xD2, 0xD2,
                                      0x4703, 0xD4, x, want_x))

    def test_both_returns_restore_x(self):
        self.check_variant(CODE, False)

    def test_changed_arm_balances_stack_but_uses_wrong_source(self):
        self.check_variant(ALTERED, True)


if __name__ == "__main__":
    unittest.main()
