#!/usr/bin/env python3
"""Extract frozen stock C64 VIC-II assets.  No emulator or third-party packages needed."""
import argparse
from hashlib import sha256
import json
from pathlib import Path

from background import decode_background
from images import PALETTE, png, sheet
from sprites import decode_sprites
from vic_state import State


def decode(state, only='all', slots=range(8)):
    """Return native color-index planes, packed background priority, and reusable source blocks, with no file writes."""
    if only not in ('all', 'background', 'sprites'):
        raise ValueError('only must be all, background, or sprites')
    return {'background': decode_background(state) if only != 'sprites' else None,
            'sprites': decode_sprites(state, slots) if only != 'background' else []}


def export(state, result, output, *, sheets=False, prg=False, asm=False, koala=False, artstudio=False):
    bg = result['background']
    if koala and (bg is None or bg['mode'] != 'multicolor-bitmap'):
        raise ValueError('Koala requires a multicolor bitmap background; no mode conversion is performed')
    if artstudio and (bg is None or bg['mode'] != 'hires-bitmap'):
        raise ValueError('Art Studio requires a hires bitmap background; no mode conversion is performed')
    out = Path(output)
    out.mkdir(exist_ok=False)
    inputs = {'ram': state.ram, 'vic': state.vic, 'color_ram': state.color, 'chargen': state.chargen}
    if state.known_ram is not None:
        inputs['sparse_ram_with_unknown_zero_filled'] = inputs.pop('ram')
        inputs['ram_coverage_mask'] = state.known_ram
    meta = {'format': 'c64-vic-assets-v1', 'capture_descriptor_sha256': state.descriptor_sha256, 'scope': 'frozen asset planes, not a raster capture',
            'palette': PALETTE, 'palette_kind': 'illustrative RGB; index 255 means transparent',
            'cia2_pins': state.cia2_pins, 'bank': state.bank, 'matrix_address': state.screen,
            'input_sha256': {k: sha256(v).hexdigest() for k, v in inputs.items() if v is not None},
            'vic_registers_hex': state.vic.hex(), 'blocks': {}, 'sprites': [], 'sheets': {}}
    def block(name, address, data):
        filename = f'{name}.bin'
        (out / filename).write_bytes(data)
        sources = (state.sources(address, len(data)) if address is not None else
                   [{'source': 'color_ram', 'offset': 0, 'length': len(data)}])
        info = {'file': filename, 'length': len(data), 'vic_address': address,
                'source_spans': sources, 'sha256': sha256(data).hexdigest()}
        if prg and address is not None and all(s['source'] == 'ram' for s in sources):
            info['prg'] = f'{name}.prg'
            (out / info['prg']).write_bytes(address.to_bytes(2, 'little') + data)
        meta['blocks'][name] = info

    if bg is not None:
        png(out / 'screen.png', 320, 200, bg['pixels'])
        (out / 'background.idx').write_bytes(bg['pixels'])
        for key, (a, data) in bg['blocks'].items():
            block(key, a, data)
        bmeta = dict(bg['manifest'], mode=bg['mode'], png='screen.png', indices='background.idx', variants=[])
        if koala:
            blocks = bg['blocks']
            picture = (b'\x00\x60' + blocks['bitmap'][1] + blocks['screen'][1]
                       + bytes(c & 15 for c in blocks['color'][1]) + bytes([state.vic[0x21] & 15]))
            (out / 'screen.koa').write_bytes(picture)
            bmeta['koala'] = {'file': 'screen.koa', 'length': len(picture),
                              'sha256': sha256(picture).hexdigest(), 'load_address': 0x6000}
        if artstudio:
            blocks = bg['blocks']
            picture = b'\x00\x20' + blocks['bitmap'][1] + blocks['screen'][1] + bytes(7)
            (out / 'screen.art').write_bytes(picture)
            bmeta['artstudio'] = {'file': 'screen.art', 'length': len(picture),
                                  'sha256': sha256(picture).hexdigest(), 'load_address': 0x2000}
        priority = bg['priority']
        bmeta['priority'] = {'file': 'background-priority.bin', 'encoding': '1bpp, row-major, MSB first',
                             'stride_bytes': 40, 'length': len(priority), 'sha256': sha256(priority).hexdigest(),
                             'zero': 'background', 'one': 'foreground (in front of a behind sprite)'}
        (out / bmeta['priority']['file']).write_bytes(priority)
        variants = bg['variants']
        if variants:
            (out / 'glyphs').mkdir()
        for i, v in enumerate(variants):
            name = f'glyphs/v{i:03x}.png'
            png(out / name, 8, 8, v['pixels'])
            bmeta['variants'].append(dict({k: val for k, val in v.items() if k != 'pixels'}, id=i, png=name))
        if sheets and variants:
            meta['sheets']['glyph-variants.png'] = sheet(out / 'glyph-variants.png',
                [(i, v['pixels']) for i, v in enumerate(variants)], 8, 8, 16)
        if sheets and 'charset' in bg['blocks']:
            data = bg['blocks']['charset'][1]
            art = [(i//8, bytes((b >> n) & 1 for b in data[i:i+8] for n in range(7, -1, -1)))
                   for i in range(0, len(data), 8)]
            meta['sheets']['raw-glyph-bits.png'] = sheet(out / 'raw-glyph-bits.png', art, 8, 8, 16)
        meta['background'] = bmeta

    slots = result['sprites']
    for v in slots:
        slot = v['slot']
        key = f'slot{slot}'
        block(key, v['address'], v['block'])
        png(out / f'{key}.png', 24, 21, v['pixels'])
        (out / f'{key}.idx').write_bytes(v['pixels'])
        info = dict(v['metadata'], slot=slot, block=key, png=f'{key}.png', indices=f'{key}.idx',
                    expanded_width=v['width'], expanded_height=v['height'])
        if (v['width'], v['height']) != (24, 21):
            info['expanded_png'] = f'{key}-expanded.png'
            png(out / info['expanded_png'], v['width'], v['height'], v['expanded_pixels'])
        meta['sprites'].append(info)
    if sheets and slots:
        meta['sheets']['sprites.png'] = sheet(out / 'sprites.png',
            [(s['slot'], s['pixels']) for s in slots], 24, 21, 4)
    if asm:
        lines = ['; ca65 data labels only. Set segment placement and VIC registers in the caller.',
                 '; Different slots may deliberately reference identical bytes.']
        lines += [f'asset_{name}: .incbin "{info["file"]}"' for name, info in meta['blocks'].items()]
        (out / 'assets.inc').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    # The manifest is written last, after every artifact it describes.
    (out / 'manifest.json').write_text(json.dumps(meta, indent=2) + '\n', encoding='utf-8')
    return meta


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('capture', help='JSON descriptor with paths to physical RAM, VIC registers, and optional inputs')
    p.add_argument('output', help='new output directory; parent must exist')
    p.add_argument('--only', choices=['all', 'background', 'sprites'], default='all')
    p.add_argument('--slots', type=int, nargs='+', choices=range(8), default=list(range(8)), help='sprite slots to fetch')
    p.add_argument('--sheets', action='store_true', help='add labeled native sprite and glyph sheets')
    p.add_argument('--prg', action='store_true', help='add little-endian PRGs for wholly RAM-sourced blocks')
    p.add_argument('--asm', action='store_true', help='add ca65 .incbin labels; no placement is implied')
    editors = p.add_mutually_exclusive_group()
    editors.add_argument('--koala', action='store_true', help='write an uncompressed Koala picture from a multicolor bitmap background')
    editors.add_argument('--artstudio', action='store_true', help='write an uncompressed Art Studio picture from a hires bitmap background')
    args = p.parse_args()
    try:
        if len(set(args.slots)) != len(args.slots):
            raise ValueError('duplicate slot')
        state = State.load(args.capture)
        result = decode(state, args.only, args.slots)
        export(state, result, args.output, sheets=args.sheets, prg=args.prg, asm=args.asm,
               koala=args.koala, artstudio=args.artstudio)
    except (ValueError, OSError) as exc:
        p.exit(1, f'extraction refused: {exc}\n')
    print(f'Wrote {Path(args.output) / "manifest.json"}')


if __name__ == '__main__':
    main()
