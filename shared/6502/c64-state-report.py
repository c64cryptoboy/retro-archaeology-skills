#!/usr/bin/env python3
"""Summarize a 64 KiB C64 CPU-memory snapshot (raw bytes, address 0 first).

I/O register values are meaningful only if the snapshot was captured with I/O visible.
"""
import argparse
from pathlib import Path
from analysis6502 import dump

def le(m,a): return m[a] | m[(a+1)&0xffff]<<8

def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('snapshot', help='exactly 65536 raw CPU-memory bytes')
    args=p.parse_args(); m=Path(args.snapshot).read_bytes()
    if len(m)!=65536: p.error('snapshot must be exactly 65536 bytes')
    port=m[1]; loram=bool(port&1); hiram=bool(port&2); charen=bool(port&4)
    io_visible = charen and (loram or hiram)
    dd00 = d011 = d016 = d018 = bank = screen = charset = None
    if io_visible:
        dd00, d011, d016, d018 = m[0xdd00], m[0xd011], m[0xd016], m[0xd018]
        bank = 3 - (dd00 & 3)
        screen = bank * 0x4000 + ((d018 & 0xf0) << 6)
        charset = bank * 0x4000 + ((d018 & 0x0e) << 10)
    dump({'cpuPort':{'ddr':m[0],'value':port,'loram':loram,'hiram':hiram,'charen':charen,
                     'basicVisible':loram and hiram,'kernalVisible':hiram,'ioVisible':io_visible},
          'vectors':{'nmi':le(m,0xfffa),'reset':le(m,0xfffc),'irq':le(m,0xfffe),
                     'kernalIrqRamVector':le(m,0x0314),'kernalNmiRamVector':le(m,0x0318)},
          'basicPointers':{'txTTAB':le(m,0x2b),'vartab':le(m,0x2d),'arytab':le(m,0x2f),'strend':le(m,0x31),'fretop':le(m,0x33),'memsiz':le(m,0x37)},
          'vic':{'dd00':dd00,'d011':d011,'d016':d016,'d018':d018,'bank':bank,'screenAddress':screen,'charsetAddress':charset},
          'warning':'This is a snapshot interpretation, not proof that RAM-under-ROM/I/O or raster-split state was captured.'})
if __name__=='__main__': main()
