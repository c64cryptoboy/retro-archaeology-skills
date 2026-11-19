#!/usr/bin/env python3
"""Export a declared sequence of registered C64 asset layers, not a raster recording."""
import argparse
from fractions import Fraction
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path

from images import CLEAR, PALETTE, png
from sprites import _decode_pixels, _expand_pixels


def _int(value, name, minimum=None):
    if type(value) is not int or (minimum is not None and value < minimum):
        raise ValueError(f'invalid {name}: {value!r}')
    return value


def _ints(value, n, name, minimum=None):
    if not isinstance(value, list) or len(value) != n:
        raise ValueError(f'{name} must have {n} integers')
    return tuple(_int(v, name, minimum) for v in value)


def _bool(value, name):
    if type(value) is not bool:
        raise ValueError(f'{name} must be true or false')
    return value


def _color(value):
    if _int(value, 'color') not in range(16):
        raise ValueError('expected a VIC index from 0 through 15')
    return value


def _load_asset(root, spec):
    if ('sprite' in spec) == ('indices' in spec):
        raise ValueError('asset needs exactly one sprite or indices path')
    if 'sprite' in spec:
        data = (root / spec['sprite']).read_bytes()
        if len(data) not in (63, 64):
            raise ValueError('sprite must have 63 pattern bytes and at most one alignment byte')
        mc = _bool(spec.get('multicolor', False), 'multicolor')
        own = _color(spec['own'])
        colors = (_color(spec['shared_0']), _color(spec['shared_1'])) if mc else (0, 0)
        pixels = _decode_pixels(data, True, mc, own, *colors)
        ex, ey = (_bool(spec.get(k, False), k) for k in ('expand_x', 'expand_y'))
        return data, _expand_pixels(pixels, ex, ey), 24 << ex, 21 << ey
    w, h = _ints(spec['size'], 2, 'index size', 1)
    data = (root / spec['indices']).read_bytes()
    if len(data) != w*h or set(data) - {*range(16), CLEAR}:
        raise ValueError('index plane has wrong size or non-VIC, nontransparent values')
    return data, data, w, h


def _preview(stage, stride, crop, scale):
    x, y, w, h = crop
    out = bytearray()
    for row in range(y, y+h):
        start = row*stride + x
        dots = stage[start:start+w]
        if scale != 1:
            dots = bytes(dot for dot in dots for _ in range(scale))
        out.extend(dots * scale)
    return bytes(out)


def _draw(stage, size, origin, layer, assets):
    _, pixels, w, h = assets[layer['asset']]
    x, y = _ints(layer['at'], 2, 'layer at')
    x, y = x - origin[0], y - origin[1]
    width, height = size
    if x < 0 or y < 0 or x+w > width or y+h > height:
        raise ValueError('layer does not fit the fixed stage; check origin and size')
    draw = layer.get('draw', 'over')
    if draw not in ('over', 'replace'):
        raise ValueError('draw must be over or replace')
    for r in range(h):
        start = (y+r)*width + x
        row = pixels[r*w:(r+1)*w]
        if draw == 'replace':
            stage[start:start+w] = row
        else:
            for c, dot in enumerate(row):
                if dot != CLEAR:
                    stage[start+c] = dot


def _gif(path, size, previews, delays, repeat, Image):
    # A multi-image save may merge identical poses or encode transparent deltas
    # over stale dots.  Have Pillow compress each *complete* stage separately.
    # Keep one logical screen/global color table and every graphic control + image.
    palette = bytes(channel for rgb in PALETTE for channel in rgb).ljust(768, b'\0')
    header = None
    with path.open('xb') as stream:
        for plane, cs in zip(previews, delays):
            im = Image.frombytes('P', size, plane)
            im.putpalette(palette)
            buf = BytesIO()
            im.save(buf, format='GIF', optimize=False, duration=10*cs, background=CLEAR,
                    transparency=CLEAR, disposal=2)
            data = buf.getvalue()
            # GIF89a logical screen descriptor + advertised global color table.
            end = 13 + 3 * (2 << (data[10] & 7))
            if not data.startswith(b'GIF89a') or not data[10] & 128 or not data.endswith(b';'):
                raise ValueError('unexpected single-frame GIF layout')
            if header is None:
                header = data[:end]
                stream.write(header)
                if repeat:
                    stream.write(b'!\xff\x0bNETSCAPE2.0\x03\x01\x00\x00\x00')
            elif header != data[:end]:
                raise ValueError('single-frame GIF palette or dimensions changed')
            stream.write(data[end:-1])
        stream.write(b';')
    # Check the actual decoder-composited, disposed movie, not PNGs or local rectangles.
    with Image.open(path) as movie:
        if (movie.size != size or movie.n_frames != len(previews) or
                movie.info.get('loop') != (0 if repeat else None)):
            raise ValueError('GIF round-trip geometry, frame count, or repeat mismatch')
        for i, (plane, cs) in enumerate(zip(previews, delays)):
            movie.seek(i)
            expected = Image.frombytes('P', size, plane)
            expected.putpalette(palette)
            expected.info['transparency'] = CLEAR
            if (movie.info.get('duration') != 10*cs or
                    movie.convert('RGBA').tobytes() != expected.convert('RGBA').tobytes()):
                raise ValueError(f'GIF round-trip dot, alpha, or hold mismatch at frame {i}')


def export_animation(sequence_path, output_dir, *, gif=False):
    """Render an ordered c64-animation-v1 JSON file to a new directory; return its manifest."""
    path, out = Path(sequence_path), Path(output_dir)
    raw = path.read_bytes()
    spec = json.loads(raw)
    if spec['format'] != 'c64-animation-v1':
        raise ValueError('expected c64-animation-v1')
    origin = _ints(spec['origin'], 2, 'origin')
    size = w, h = _ints(spec['size'], 2, 'stage size', 1)
    bg = _int(spec.get('background', CLEAR), 'background')
    if bg != CLEAR:
        _color(bg)
    crop = x, y, cw, ch = _ints(spec.get('crop', [0, 0, w, h]), 4, 'crop', 0)
    if not cw or not ch or x+cw > w or y+ch > h:
        raise ValueError('crop must be a nonempty rectangle inside the stage')
    scale = _int(spec.get('scale', 1), 'scale', 1)
    view = cw*scale, ch*scale
    clock = spec['clock']
    if not isinstance(clock['label'], str) or not clock['label'].strip():
        raise ValueError('clock needs a label stating the tick basis')
    period = Fraction(_int(clock['hz_den'], 'hz_den', 1), _int(clock['hz_num'], 'hz_num', 1))
    frames, loop = spec['frames'], spec['source_loop']
    if not isinstance(frames, list) or not frames:
        raise ValueError('expected an ordered nonempty frames array')
    if loop is not None:
        a, b = _ints(loop, 2, 'source_loop')
        if not 0 <= a < b <= len(frames):
            raise ValueError('source_loop must be a half-open frame interval within the list')
    repeat = _bool(spec['movie_repeat'], 'movie_repeat')
    if gif:
        try:
            from PIL import Image
        except ImportError as exc:
            raise ValueError('verified GIF requires Pillow; omit --gif for PNG and native evidence') from exc
        if max(view) > 65535:
            raise ValueError('GIF dimensions cannot exceed 65535')

    assets = {name: _load_asset(path.parent, obj) for name, obj in spec['assets'].items()}
    out.mkdir(exist_ok=False)
    meta = {'format': 'c64-animation-export-v1', 'sequence_sha256': sha256(raw).hexdigest(),
            'origin': list(origin), 'size': list(size), 'background': bg, 'crop': list(crop),
            'scale': scale, 'palette': [list(rgb) for rgb in PALETTE], 'transparent': CLEAR,
            'clock': clock, 'source_loop': loop, 'movie_repeat': repeat, 'assets': {}, 'frames': []}
    for i, (name, (data, _, aw, ah)) in enumerate(assets.items()):
        filename = f'asset-{i:04}.bin'
        (out / filename).write_bytes(data)
        meta['assets'][name] = {'input': spec['assets'][name], 'file': filename,
                                'size_dots': [aw, ah], 'bytes': len(data), 'sha256': sha256(data).hexdigest()}

    stage = None
    ticks = boundary = 0
    previews, delays = [], []
    for i, frame in enumerate(frames):
        if not isinstance(frame['id'], str) or not frame['id']:
            raise ValueError('each frame requires a nonempty string id')
        if frame['base'] == 'clear':
            stage = bytearray([bg]) * (w*h)
        elif frame['base'] != 'previous' or stage is None:
            raise ValueError('base must be clear or previous; first frame must clear')
        if not isinstance(frame['layers'], list):
            raise ValueError('layers must be ordered back to front')
        for layer in frame['layers']:
            _draw(stage, size, origin, layer, assets)
        hold = _int(frame['hold'], 'hold', 1)
        ticks += hold
        # Exact rational boundaries, nearest centisecond (halves to even).
        end = round(100*ticks*period)
        cs, boundary = end - boundary, end
        if gif and not 1 <= cs <= 65535:
            raise ValueError(f'frame {i} has an unrepresentable GIF hold ({cs} cs); omit --gif')
        stem = f'frame-{i:04}'
        (out / (stem + '.idx')).write_bytes(stage)
        preview = _preview(stage, w, crop, scale)
        png(out / (stem + '.png'), *view, preview)
        if gif:
            previews.append(preview)
            delays.append(cs)
        duration = hold*period
        meta['frames'].append(dict(frame, indices=stem+'.idx', png=stem+'.png', sha256=sha256(stage).hexdigest(),
                                   start_tick=ticks-hold, end_tick=ticks, seconds=[duration.numerator, duration.denominator],
                                   gif_cs=cs))
    if gif:
        _gif(out / 'animation.gif', view, previews, delays, repeat, Image)
        meta['gif'] = {'file': 'animation.gif', 'centiseconds': boundary, 'decoded_rgba_and_holds_match': True}
    # A partial/failed output has no completion manifest.  Never replace an old export.
    (out / 'manifest.json').write_text(json.dumps(meta, indent=2) + '\n', encoding='utf-8')
    return meta


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('sequence', help='ordered animation JSON descriptor')
    p.add_argument('output', help='new output directory')
    p.add_argument('--gif', action='store_true', help='write and decode-check a GIF using Pillow')
    args = p.parse_args()
    try:
        export_animation(args.sequence, args.output, gif=args.gif)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        p.exit(1, f'animation refused: {exc}\n')
    print(f'Wrote {Path(args.output) / "manifest.json"}')


if __name__ == '__main__':
    main()
