"""Plain stock C64 memory as seen by the VIC-II, without CPU banking."""
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path


@dataclass(frozen=True)
class State:
    ram: bytes
    vic: bytes
    cia2_pins: int
    color: bytes | None = None
    chargen: bytes | None = None
    known_ram: bytes | None = None
    descriptor_sha256: str | None = None

    def __post_init__(self):
        for label, data, sizes in [('ram', self.ram, (65536,)), ('vic', self.vic, (64,)),
                                   ('color_ram', self.color, (1000, 1024)),
                                   ('chargen', self.chargen, (4096,))]:
            if data is None and label in ('color_ram', 'chargen'):
                continue
            if not isinstance(data, bytes) or len(data) not in sizes:
                raise ValueError(f'{label}: expected bytes of length {sizes}')
        if self.known_ram is not None and (len(self.known_ram) != 65536 or not isinstance(self.known_ram, bytes)):
            raise ValueError('known_ram must be a 65536-byte coverage mask')
        if type(self.cia2_pins) is not int or not 0 <= self.cia2_pins <= 255:
            raise ValueError('cia2_pins must be the effective CIA2 port A pin value, 0 through 255')

    @property
    def bank(self):
        return (~self.cia2_pins & 3) << 14

    @property
    def screen(self):
        return self.bank + ((self.vic[0x18] & 0xf0) << 6)

    def sources(self, address, length):
        if length < 0 or not self.bank <= address <= address + length <= self.bank + 0x4000:
            raise ValueError('fetch outside the selected 16 KiB VIC bank')
        end = address + length
        rom = self.bank + 0x1000 if self.bank in (0, 0x8000) else None
        cuts = [address, end]
        if rom is not None:
            cuts[1:1] = [v for v in (rom, rom + 4096) if address < v < end]
        return [{'address': lo, 'length': hi - lo,
                 'source': 'chargen' if rom is not None and rom <= lo < rom + 4096 else 'ram'}
                for lo, hi in zip(cuts, cuts[1:]) if hi > lo]

    def fetch(self, address, length):
        parts = []
        for span in self.sources(address, length):
            a, n = span['address'], span['length']
            if span['source'] == 'chargen':
                if self.chargen is None:
                    raise ValueError(f'VIC fetch at ${a:04X} needs the 4096-byte chargen ROM; RAM under ROM is not a substitute')
                parts.append(self.chargen[a & 4095:(a & 4095) + n])
            else:
                if self.known_ram is not None:
                    gap = self.known_ram.find(b'\x00', a, a + n)
                    if gap >= 0:
                        raise ValueError(f'VIC fetch needs missing physical RAM at ${gap:04X}')
                parts.append(self.ram[a:a + n])
        return b''.join(parts)

    @classmethod
    def load(cls, capture):
        path = Path(capture)
        descriptor = path.read_bytes()
        spec = json.loads(descriptor)
        if not isinstance(spec, dict) or not {'vic', 'cia2_pins'} <= spec.keys():
            raise ValueError('capture must specify vic and cia2_pins')
        if ('ram' in spec) == ('ram_segments' in spec):
            raise ValueError('supply exactly one of ram and ram_segments')
        def read_block(key):
            name = spec[key]
            if not isinstance(name, str) or not name:
                raise ValueError(f'{key}: expected a file path')
            return (path.parent / name).read_bytes()
        known = None
        if 'ram' in spec:
            ram = read_block('ram')
        else:
            parts = spec['ram_segments']
            if not isinstance(parts, list) or not parts:
                raise ValueError('ram_segments must be a nonempty list of {address, file} objects')
            data, mask = bytearray(65536), bytearray(65536)
            for part in parts:
                if not isinstance(part, dict) or type(part.get('address')) is not int or not isinstance(part.get('file'), str):
                    raise ValueError('each RAM segment requires an integer address and a raw binary file')
                a = part['address']
                part_data = (path.parent / part['file']).read_bytes()
                end = a + len(part_data)
                if not 0 <= a < end <= 65536 or any(mask[a:end]):
                    raise ValueError('RAM segment out of range, empty, or overlapping')
                data[a:end], mask[a:end] = part_data, bytes([1]) * len(part_data)
            ram, known = bytes(data), bytes(mask)
        return cls(ram, read_block('vic'), spec['cia2_pins'],
                   read_block('color_ram') if 'color_ram' in spec else None,
                   read_block('chargen') if 'chargen' in spec else None, known,
                   sha256(descriptor).hexdigest())
