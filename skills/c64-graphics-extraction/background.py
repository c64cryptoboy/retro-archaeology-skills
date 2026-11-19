"""Decode the VIC-II background content plane from one frozen state."""


def _tile(rows, palette):
    """Expand eight native rows, most significant bit or bit pair first."""
    if len(palette) == 2:
        return bytes(palette[(row >> shift) & 1] for row in rows for shift in range(7, -1, -1))
    pixels = bytearray()
    for row in rows:
        for shift in (6, 4, 2, 0):
            color = palette[(row >> shift) & 3]
            pixels.extend((color, color))
    return bytes(pixels)


def decode_background(s):
    """Return color indices, packed foreground bits, source blocks, and used text variants."""
    d011, d016, d018 = s.vic[0x11], s.vic[0x16], s.vic[0x18]
    ecm, bitmap, multicolor = bool(d011 & 0x40), bool(d011 & 0x20), bool(d016 & 0x10)
    if ecm and (bitmap or multicolor):
        raise ValueError("Illegal VIC-II background mode: ECM with BMM or MCM")
    if bitmap:
        mode = "multicolor-bitmap" if multicolor else "hires-bitmap"
        kind = "bitmap"
        address = s.bank + ((d018 & 0x08) << 10)
        size = 8000
    else:
        mode = "extended-color-text" if ecm else ("multicolor-character" if multicolor else "hires-character")
        kind = "charset"
        address = s.bank + ((d018 & 0x0E) << 10)
        size = 512 if ecm else 2048

    screen = bytes(s.fetch(s.screen, 1000))
    patterns = bytes(s.fetch(address, size))
    blocks = {"screen": (s.screen, screen), kind: (address, patterns)}
    if not bitmap or multicolor:
        if s.color is None:
            raise ValueError(f"Color RAM required for {mode}")
        colors = bytes(s.color[:1000])
        blocks["color"] = (None, colors)
    bg = tuple(value & 15 for value in s.vic[0x21:0x25])
    pixels = bytearray(320 * 200)
    priority = bytearray(40 * 200)
    variants = {}
    for cell, entry in enumerate(screen):
        if bitmap:
            hi, lo = entry >> 4, entry & 15
            palette = (bg[0], hi, lo, colors[cell] & 15) if multicolor else (lo, hi)
            rows = patterns[cell * 8:cell * 8 + 8]
            tile = _tile(rows, palette)
        else:
            code = entry & 63 if ecm else entry
            ink = colors[cell] & 15
            if multicolor and ink & 8:
                palette = (bg[0], bg[1], bg[2], ink & 7)
            else:
                palette = (bg[entry >> 6] if ecm else bg[0], ink)
            rows = patterns[code * 8:code * 8 + 8]
            key = (code, palette)
            if key not in variants:
                variants[key] = {"code": code, "palette": list(palette), "cells": [],
                                 "pixels": _tile(rows, palette)}
            variant = variants[key]
            variant["cells"].append(cell)
            tile = variant["pixels"]

        cell_y, cell_x = divmod(cell, 40)
        start = cell_y * 8 * 320 + cell_x * 8
        for row, bits in enumerate(rows):
            # In a two-dot selector the high bit sets priority for BOTH dots.
            if len(palette) == 4:
                bits &= 0xAA
                bits |= bits >> 1
            priority[start // 8] = bits
            pixels[start:start + 8] = tile[row * 8:row * 8 + 8]
            start += 320

    manifest = {
        "mode": mode, "width": 320, "height": 200, "columns": 40, "rows": 25,
        "cell_width": 8, "cell_height": 8, "bank": s.bank,
        "blocks": {name: {"address": base, "length": len(data)} for name, (base, data) in blocks.items()},
        "display_enabled": bool(d011 & 0x10), "x_scroll": d016 & 7, "y_scroll": d011 & 7,
        "caveat": "Frozen memory content, not a raster frame.  Display enable, fine scrolling, "
                  "border clipping, raster changes, and sprites are not applied.",
    }
    return {"mode": mode, "pixels": bytes(pixels), "priority": bytes(priority), "blocks": blocks,
            "variants": list(variants.values()), "manifest": manifest}
