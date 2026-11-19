"""Compose registered VIC-II asset planes for a static preview, not a raster frame."""


def static_composite(background, sprites, *, offset_x, offset_y) -> bytes:
    """Return a new 320 x 200 row-major VIC index plane from extract.decode layers.

    Sprite origin in asset dots = (register X + offset_x, register Y + offset_y).
    Pass the selected sprite layers explicitly; an empty iterable draws none.
    """
    if type(offset_x) is not int or type(offset_y) is not int:
        raise ValueError('registration offsets must be integers')
    if background is None or len(background['pixels']) != 64000 or len(background['priority']) != 8000:
        raise ValueError('need 320 x 200 background indices and packed foreground bits')
    pixels = bytearray(background['pixels'])
    priority = background['priority']
    claimed = bytearray(len(pixels))
    seen = set()
    for layer in sorted(sprites, key=lambda s: s['slot']):
        slot = layer['slot']
        if type(slot) is not int or slot not in range(8) or slot in seen:
            raise ValueError(f'invalid or duplicate sprite slot: {slot}')
        seen.add(slot)
        meta = layer['metadata']
        if not meta['enabled']:
            continue
        if meta['priority'] not in ('behind_background', 'in_front'):
            raise ValueError(f'unknown sprite priority for slot {slot}')
        behind = meta['priority'] == 'behind_background'
        x0, y0 = meta['x'] + offset_x, meta['y'] + offset_y
        width, height, art = layer['width'], layer['height'], layer['expanded_pixels']
        if width not in (24, 48) or height not in (21, 42) or len(art) != width * height:
            raise ValueError(f'invalid expanded plane for slot {slot}')
        for y in range(max(0, y0), min(200, y0 + height)):
            src_row, dst_row = (y - y0) * width, y * 320
            for x in range(max(0, x0), min(320, x0 + width)):
                color, dst = art[src_row + x - x0], dst_row + x
                if color == 255 or claimed[dst]:
                    continue
                # A hidden winner still owns this dot.  No second sprite gets a turn.
                claimed[dst] = 1
                if not (behind and priority[dst // 8] & (0x80 >> (x % 8))):
                    pixels[dst] = color
    return bytes(pixels)


def main():
    import argparse
    import json
    from pathlib import Path
    from extract import State, decode
    from images import png

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('capture', help='existing capture.json for extract.decode')
    parser.add_argument('output', type=Path, help='new preview directory; never replaces an export')
    parser.add_argument('--offset', type=int, nargs=2, metavar=('DX', 'DY'), required=True,
                        help='signed translation added to VIC register positions, in asset dots')
    parser.add_argument('--slots', type=int, nargs='+', choices=range(8), required=True,
                        help='selected slots, in any order; disabled slots draw nothing')
    args = parser.parse_args()
    try:
        scene = decode(State.load(args.capture), slots=args.slots)
        dx, dy = args.offset
        pixels = static_composite(scene['background'], scene['sprites'], offset_x=dx, offset_y=dy)
        args.output.mkdir(exist_ok=False)
        (args.output / 'preview.idx').write_bytes(pixels)
        png(args.output / 'preview.png', 320, 200, pixels)
        metadata = {'scope': 'static asset-plane preview, not a raster frame', 'width': 320,
                    'height': 200, 'register_to_asset_add_xy': [dx, dy], 'slots': args.slots}
        (args.output / 'preview.json').write_text(json.dumps(metadata, indent=2) + '\n', encoding='utf-8')
    except (ValueError, OSError) as exc:
        parser.exit(1, f'preview refused: {exc}\n')


if __name__ == '__main__':
    main()
