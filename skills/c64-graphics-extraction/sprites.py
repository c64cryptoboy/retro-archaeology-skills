"""Extract independent VIC-II sprite layers from one register and memory snapshot."""

TRANSPARENT = 255


def _decode_pixels(block, enabled, multicolor, own, shared_0, shared_1):
    if not enabled:
        return bytes([TRANSPARENT]) * (24 * 21)

    # Each of the 21 rows is three bytes, MSB first.  Byte 63 is padding.
    if multicolor:
        colors = (TRANSPARENT, shared_0, own, shared_1)
        return bytes(colors[(value >> shift) & 3] for value in block[:63]
                     for shift in (6, 4, 2, 0) for _ in range(2))
    return bytes(own if value & (1 << bit) else TRANSPARENT
                 for value in block[:63] for bit in range(7, -1, -1))


def _expand_pixels(pixels, expand_x, expand_y):
    if not (expand_x or expand_y):
        return pixels
    result = bytearray()
    for start in range(0, len(pixels), 24):
        row = pixels[start:start + 24]
        if expand_x:
            row = bytes(color for color in row for _ in range(2))
        result.extend(row * (2 if expand_y else 1))
    return bytes(result)


def decode_sprites(s, slots=range(8)):
    """Return one uncomposited layer per slot in input order, including disabled slots.

    Coordinates are raw VIC register positions, not offsets into a cropped screen.
    Both pixel buffers are row-major palette indices with 255 denoting transparency.
    The pointer and all 64 block bytes must be VIC-visible, even for a disabled slot.
    """
    vic = s.vic
    shared_0, shared_1 = vic[0x25] & 15, vic[0x26] & 15
    layers = []
    for slot in slots:
        if slot not in range(8):
            raise ValueError(f"invalid sprite slot: {slot}")
        mask = 1 << slot
        pointer_address = s.screen + 0x3F8 + slot
        pointer_value = s.fetch(pointer_address, 1)[0]
        address = s.bank + 64 * pointer_value
        block = bytes(s.fetch(address, 64))

        enabled = bool(vic[0x15] & mask)
        multicolor = bool(vic[0x1C] & mask)
        expand_x = bool(vic[0x1D] & mask)
        expand_y = bool(vic[0x17] & mask)
        own = vic[0x27 + slot] & 15
        pixels = _decode_pixels(block, enabled, multicolor, own, shared_0, shared_1)
        layers.append({
            "slot": slot, "address": address, "block": block, "pixels": pixels,
            "expanded_pixels": _expand_pixels(pixels, expand_x, expand_y),
            "width": 48 if expand_x else 24, "height": 42 if expand_y else 21,
            "metadata": {
                "enabled": enabled, "mode": "multicolor" if multicolor else "hires",
                "pointer_address": pointer_address, "pointer_value": pointer_value,
                "x": vic[2 * slot] + (256 if vic[0x10] & mask else 0),
                "y": vic[2 * slot + 1],
                "priority": "behind_background" if vic[0x1B] & mask else "in_front",
                "colors": {"own": own, "shared_0": shared_0, "shared_1": shared_1},
                "expand_x": expand_x, "expand_y": expand_y,
                "provenance": {"memory_view": "VIC-visible", "bank_base": s.bank,
                               "screen_base": s.screen, "block_address": address},
            },
        })
    return layers
