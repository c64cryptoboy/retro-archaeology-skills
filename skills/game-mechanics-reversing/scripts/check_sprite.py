"""Original sparse resource.  Check ordinary hires sprites, not an emulator."""

resource = bytearray(127)
resource[0], resource[63], resource[64] = 0x80, 0x80, 0x40


def dots(pattern):
    assert len(pattern) == 63
    return {(8 * (i % 3) + bit, i // 3)
            for i, byte in enumerate(pattern) for bit in range(8)
            if byte & (0x80 >> bit)}


# Two adjacent pointer entries in a screen at $0400, bank at $0000.
for stride, expected in [(63, {(0, 0), (9, 0)}), (64, {(1, 0)})]:
    ram = bytearray(0x4000)
    ram[0x07F8:0x07FA] = bytes([0x80, 0x81])
    for i, dest in enumerate((0x2000, 0x2040)):
        ram[dest:dest + 63] = resource[i * stride:i * stride + 63]
    masks = []
    for ptr in ram[0x07F8:0x07FA]:
        base = ptr << 6
        masks.append(dots(ram[base:base + 63]))
    assert masks == [{(0, 0)}, expected]
    overlap = masks[0] & masks[1]  # Same origin; no X/Y expansion.
    assert overlap == ({(0, 0)} if stride == 63 else set())
    print(f'source step {stride}: second dots={sorted(masks[1])}; overlap={sorted(overlap)}')
