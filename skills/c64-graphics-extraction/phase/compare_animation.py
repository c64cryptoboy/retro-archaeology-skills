"""Compare declared source loops of two already registered C64 native exports."""
import argparse
import json
from fractions import Fraction
from hashlib import sha256
from pathlib import Path


def positive(n):
    return type(n) is int and n > 0


def header(path):
    m = json.loads(Path(path).read_bytes())
    if m['format'] != 'c64-animation-export-v1' or m['transparent'] != 255:
        raise ValueError('expected a native v1 animation export with transparent index 255')
    size = m.get('size')
    if not isinstance(size, list) or len(size) != 2 or not all(map(positive, size)):
        raise ValueError('missing or invalid native canvas size')
    clock = m.get('clock')
    if not isinstance(clock, dict) or not all(positive(clock.get(k)) for k in ('hz_num', 'hz_den')):
        raise ValueError('missing or invalid rational clock')
    loop = m.get('source_loop')
    if (not isinstance(loop, list) or len(loop) != 2 or not all(type(v) is int for v in loop)
            or not 0 <= loop[0] < loop[1] <= len(m['frames'])):
        raise ValueError('no complete declared source_loop interval')
    return size, Fraction(clock['hz_den'], clock['hz_num']), m['frames'][slice(*loop)]


def planes(path, size, period, frames):
    base = Path(path).resolve().parent
    for frame in frames:
        p = (base / frame['indices']).resolve()
        if not p.is_relative_to(base) or not p.is_file() or p.stat().st_size != size[0]*size[1]:
            raise ValueError('expected an export-local, full-size native index plane')
        plane = p.read_bytes()
        if sha256(plane).hexdigest() != frame['sha256'] or any(15 < c < 255 for c in plane):
            raise ValueError(f'invalid native indices or digest for {p.name}')
        if not positive(frame['hold']):
            raise ValueError('expected a positive integer tick hold')
        duration = frame['hold'] * period
        if [duration.numerator, duration.denominator] != frame['seconds']:
            raise ValueError('frame seconds disagree with hold and clock')
        yield plane, duration


def reflect(plane, width):
    return b''.join(plane[i:i+width][::-1] for i in range(0, len(plane), width))


def runs(frames, ids):
    # Cut at a visible change, not necessarily at the source loop seam.
    changes = []
    t = 0
    for plane, duration in frames:
        key = ids.setdefault(plane, len(ids))
        if not changes or key != changes[-1][1]:
            changes.append((t, key))
        t += duration
    if len(changes) > 1 and changes[0][1] == changes[-1][1]:
        changes.pop(0)
    starts = [s for s, _ in changes] + [changes[0][0] + t]
    tokens = [(key, starts[i+1]-s) for i, (s, key) in enumerate(changes)]
    return starts[:-1], tokens, t


def rotations(needle, ring):
    """All matching rotations, using a prefix table rather than testing every tick."""
    if len(needle) != len(ring):
        return
    n = len(needle)
    prefix = [0] * n
    k = 0
    for i in range(1, n):
        while k and needle[k] != needle[i]:
            k = prefix[k-1]
        k += needle[k] == needle[i]
        prefix[i] = k
    k = 0
    for i in range(2*n-1):
        token = ring[i % n]
        while k and needle[k] != token:
            k = prefix[k-1]
        k += needle[k] == token
        if k == n:
            yield i-n+1
            k = prefix[k-1]


def compare(left, right, *, reflect_x=False):
    """A phase p means left(t) == transformed right(t+p), forward in both."""
    try:
        a, b = header(left), header(right)
        if a[0] != b[0]:
            return {'status': 'not_comparable', 'reason': 'native canvas sizes differ', 'sizes': [a[0], b[0]]}
        ids = {}
        sa, ta, period = runs(planes(left, *a), ids)
        right_planes = list(planes(right, *b))
        sb, tb, duration = runs(right_planes, ids)
        if period != duration:
            return {'status': 'different', 'reason': 'declared loop durations differ',
                    'seconds': [str(period), str(duration)]}
        matches = {}
        for mode in (('identity', 'reflect_x') if reflect_x else ('identity',)):
            if mode == 'reflect_x':
                sb, tb, _ = runs(((reflect(p, b[0][0]), d) for p, d in right_planes), ids)
            phases = sorted((sb[i]-sa[0]) % period for i in rotations(ta, tb))
            matches[mode] = 'any' if phases and len(ta) == 1 else [str(p) for p in phases]
        return {'status': 'match' if any(matches.values()) else 'different',
                'size': a[0], 'loop_seconds': str(period), 'right_phase_seconds': matches}
    except (OSError, KeyError, ValueError, TypeError) as e:
        return {'status': 'not_comparable', 'reason': str(e)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('left')
    parser.add_argument('right')
    parser.add_argument('--reflect-x', action='store_true', help='also test horizontal reflection of the second canvas')
    args = parser.parse_args()
    result = compare(args.left, args.right, reflect_x=args.reflect_x)
    print(json.dumps(result, indent=2))
    raise SystemExit({'match': 0, 'different': 1, 'not_comparable': 2}[result['status']])
