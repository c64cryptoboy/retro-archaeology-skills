"""Independent test reader for the writer's explicit-status type-0 SMF profile."""
from io import BytesIO
import struct


def parse_smf(data):
    f = BytesIO(data)
    if f.read(12) != b'MThd\x00\x00\x00\x06\x00\x00\x00\x01':
        raise ValueError('not a single-track type-0 SMF')
    division, tag, size = struct.unpack('>H4sI', f.read(10))
    if tag != b'MTrk' or size != len(data) - f.tell():
        raise ValueError('bad track chunk')

    def byte():
        return f.read(1)[0]

    def variable():
        x = 0
        for _ in range(4):
            n = byte()
            x = 128 * x + (n % 128)
            if n < 128:
                return x
        raise ValueError('unterminated VLQ')

    events = []
    time = 0
    while f.tell() < len(data):
        time += variable()
        status = byte()
        if status == 255:
            tag = byte()
            n = variable()
            payload = f.read(n)
            if len(payload) != n:
                raise ValueError('truncated meta')
            events.append((time, 'meta', tag, payload))
        else:
            kind = {8: 'off', 9: 'on', 11: 'cc', 14: 'bend'}[status >> 4]
            ch = 1 + status % 16
            a, b = byte(), byte()
            if max(a, b) > 127:
                raise ValueError('not MIDI data')
            events.append((time, kind, ch, a + 128*b) if kind == 'bend' else
                          (time, kind, ch, a, b))
    return division, events
