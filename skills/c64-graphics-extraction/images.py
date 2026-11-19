"""Small deterministic RGBA PNG writer and indexed contact sheet; stdlib only."""
import struct
import zlib

# Illustrative swatches, not a chip revision or calibrated video signal.
PALETTE = [tuple(bytes.fromhex(h)) for h in
           '000000 ffffff 884444 88cccc aa4499 55aa55 443399 dddd77 '
           'aa7744 664422 cc7777 444444 777777 99dd99 7777cc bbbbbb'.split()]
CLEAR = 255
_RGBA = {i: bytes((*rgb, 255)) for i, rgb in enumerate(PALETTE)}
_RGBA[CLEAR] = bytes(4)


def png(path, width, height, pixels):
    if len(pixels) != width * height:
        raise ValueError('image dimensions disagree with index plane')
    def chunk(tag, data):
        return struct.pack('>I', len(data)) + tag + data + struct.pack('>I', zlib.crc32(tag + data))
    raw = b''.join(b'\x00' + b''.join(_RGBA[i] for i in pixels[p:p + width])
                   for p in range(0, len(pixels), width))
    ihdr = struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0)
    path.write_bytes(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', ihdr)
                     + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b''))


# Three by five hex digits.  Labels are outside each native image rectangle.
_FONT = ['75557', '26227', '71747', '71717', '55711', '74717', '74757', '71111',
         '75757', '75717', '25755', '65656', '74447', '65556', '74647', '74644']


def sheet(path, items, width, height, columns):
    """items are (unique numeric label, native index plane).  Return a crop map."""
    cellw = max(width, max(len(f'{i:X}') for i, _ in items) * 4 - 1) + 2
    cellh = height + 8
    cols = min(len(items), columns)
    w, h = cols * cellw, (len(items) + cols - 1) // cols * cellh
    pixels = bytearray([CLEAR]) * (w * h)
    entries = []
    for j, (i, art) in enumerate(items):
        x, y = (j % cols) * cellw + 1, (j // cols) * cellh + 1
        digits = f'{i:X}'
        for d, digit in enumerate(digits):
            for row, bits in enumerate(_FONT[int(digit, 16)]):
                for col in range(3):
                    pixels[(y + row) * w + x + 4*d + col] = 1 if int(bits) & (4 >> col) else 0
        for row in range(height):
            pos = (y + 6 + row) * w + x
            pixels[pos:pos + width] = art[row * width:(row + 1) * width]
        entries.append({'id': i, 'x': x, 'y': y + 6, 'width': width, 'height': height})
    png(path, w, h, pixels)
    return entries
